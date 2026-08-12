#!/usr/bin/env python3
"""Synchronize data/releases.json with IGDB using Twitch client credentials."""
from __future__ import annotations
import argparse, hashlib, json, os, re, time, unicodedata
import urllib.error, urllib.parse, urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "releases.json"
IGDB_BASE = "https://api.igdb.com/v4"
TOKEN_URL = "https://id.twitch.tv/oauth2/token"
REQUEST_DELAY = 0.28
PAGE_LIMIT = 500

TARGET_PLATFORM_SPECS = {
    "PC": {"names": {"pc (microsoft windows)", "microsoft windows", "windows"}, "slugs": {"win", "windows", "pc-microsoft-windows"}},
    "PS5": {"names": {"playstation 5", "ps5"}, "slugs": {"ps5", "playstation-5"}},
    "Switch": {"names": {"nintendo switch"}, "slugs": {"switch", "nintendo-switch"}},
    "Switch 2": {"names": {"nintendo switch 2", "switch 2"}, "slugs": {"switch-2", "nintendo-switch-2"}},
}
INCLUDED_GAME_TYPES = {
    "main game",
    "dlc",
    "expansion",
    "standalone expansion",
    "episode",
    "season",
    "remake",
    "remaster",
    "expanded game",
    "port",
    "pack addon",
    "update",
}

TYPE_TO_RELEASE_TYPE = {
    "main game": "Game",
    "dlc": "DLC / add-on",
    "expansion": "DLC / expansion",
    "standalone expansion": "Standalone expansion",
    "episode": "Episode / add-on",
    "season": "Season / add-on",
    "remake": "Game / remake",
    "remaster": "Game / remaster",
    "expanded game": "Expanded edition",
    "port": "Platform release",
    "pack addon": "Add-on pack",
    "update": "Major update",
}
REGION_PRIORITY = {2:0, 8:1, None:2, 1:3}
PLATFORM_ORDER = {"PC":0,"PS5":1,"Switch":2,"Switch 2":3}

def norm_space(v): return re.sub(r"\s+", " ", v or "").strip()
def normalize_title(value):
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"\s*[—–-]\s*(playstation\s*5|ps5|nintendo\s+switch(?:\s*2)?|switch\s*2|current[- ]platform|pc)(?:\s*/\s*(?:playstation\s*5|ps5|nintendo\s+switch(?:\s*2)?|switch\s*2|pc))*\s+release\s*$", "", value, flags=re.I)
    value = value.lower().replace("&", " and ")
    return norm_space(re.sub(r"[^a-z0-9]+", " ", value))
def stable_uid(game_id, platforms, release_type):
    s=f"igdb|{game_id}|{'|'.join(sorted(platforms))}|{release_type}".lower()
    return hashlib.sha1(s.encode()).hexdigest()[:22]+"@game-release-calendar"
def iso_from_unix(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat(timespec="seconds") if ts else None
def exact_day(row):
    try: return date(int(row["y"]), int(row["m"]), int(row["d"]))
    except (KeyError,TypeError,ValueError): return None

def http_json(url, method="GET", headers=None, data=None):
    req=urllib.request.Request(url,method=method,headers=headers or {},data=data.encode() if isinstance(data,str) else data)
    try:
        with urllib.request.urlopen(req,timeout=45) as r: return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body=e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code} for {url}: {body[:1000]}") from e

class IGDB:
    def __init__(self,cid,secret):
        q=urllib.parse.urlencode({"client_id":cid,"client_secret":secret,"grant_type":"client_credentials"})
        token=http_json(f"{TOKEN_URL}?{q}",method="POST")
        self.headers={"Client-ID":cid,"Authorization":f"Bearer {token['access_token']}","Accept":"application/json","Content-Type":"text/plain"}
    def query(self,endpoint,body):
        x=http_json(f"{IGDB_BASE}/{endpoint}",method="POST",headers=self.headers,data=body); time.sleep(REQUEST_DELAY)
        if not isinstance(x,list): raise RuntimeError(f"Unexpected IGDB response from {endpoint}: {x!r}")
        return x
    def paged(self,endpoint,base):
        out=[]; off=0
        while True:
            page=self.query(endpoint,f"{base}\nlimit {PAGE_LIMIT}; offset {off};")
            out.extend(page)
            if len(page)<PAGE_LIMIT: break
            off+=PAGE_LIMIT
        return out

def resolve_platforms(api):
    rows=api.query("platforms","fields id,name,slug,abbreviation; limit 500;")
    id_to_label={}
    for label,spec in TARGET_PLATFORM_SPECS.items():
        matches=[]
        for r in rows:
            name=norm_space(str(r.get("name",""))).lower(); slug=norm_space(str(r.get("slug",""))).lower(); abbr=norm_space(str(r.get("abbreviation",""))).lower()
            score=None
            if name in spec["names"]: score=0
            elif slug in spec["slugs"]: score=1
            elif abbr in spec["names"]|spec["slugs"]: score=2
            elif label=="Switch 2" and "switch 2" in name: score=3
            if score is not None: matches.append((score,int(r["id"])))
        if matches:
            matches.sort(); id_to_label[matches[0][1]]=label
        else: print(f"::warning::Could not resolve IGDB platform {label}; skipping it.")
    if not id_to_label: raise RuntimeError("No target IGDB platforms could be resolved.")
    return id_to_label

def normalize_game_type(value):
    value = norm_space(str(value)).lower()
    value = re.sub(r"[_/\\-]+", " ", value)
    return norm_space(value)


def resolve_game_types(api):
    rows = api.query("game_types", "fields id,type; limit 500;")

    resolved = {
        int(r["id"]): normalize_game_type(r.get("type", ""))
        for r in rows
    }

    print("Resolved IGDB game types:")
    for game_type_id, game_type_name in sorted(resolved.items()):
        print(f"  {game_type_id}: {game_type_name}")

    return resolved
def resolve_statuses(api): return {int(r["id"]):norm_space(str(r.get("name",""))) for r in api.query("release_date_statuses","fields id,name; limit 500;")}

def fetch_release_rows(api,pids,start_day,end_day):
    rows={}; cur=start_day; pid=",".join(map(str,pids))
    while cur<=end_day:
        stop=min(cur+timedelta(days=119),end_day)
        lo=int(datetime.combine(cur,datetime.min.time(),tzinfo=timezone.utc).timestamp())
        hi=int(datetime.combine(stop+timedelta(days=1),datetime.min.time(),tzinfo=timezone.utc).timestamp())-1
        base=("fields id,d,m,y,date,human,date_format,game,platform,region,release_region,status,updated_at; "
              f"where platform = ({pid}) & date >= {lo} & date <= {hi}; sort date asc;")
        for r in api.paged("release_dates",base): rows[int(r["id"])]=r
        cur=stop+timedelta(days=1)
    return list(rows.values())

def fetch_games(api,ids):
    out={}; ids=sorted(set(ids))
    for i in range(0,len(ids),350):
        block=",".join(map(str,ids[i:i+350]))
        body=("fields id,name,slug,url,game_type,first_release_date,parent_game,version_parent,updated_at; "
              f"where id = ({block}); limit 500;")
        for r in api.query("games",body): out[int(r["id"])]=r
    return out

def choose_platform_rows(rows):
    by=defaultdict(list)
    for r in rows: by[int(r["platform"])].append(r)
    chosen=[]
    for _,opts in by.items():
        opts.sort(key=lambda r:(REGION_PRIORITY.get(r.get("region"),4),-int(r.get("updated_at") or 0)))
        chosen.append(opts[0])
    return chosen

def release_type_for(type_name,day,first_ts):
    kind=TYPE_TO_RELEASE_TYPE.get(type_name,"Game")
    if kind=="Game" and first_ts and day>datetime.fromtimestamp(int(first_ts),tz=timezone.utc).date(): return "Platform release"
    return kind

def title_for(name,platforms,day,first_ts):
    if first_ts and day>datetime.fromtimestamp(int(first_ts),tz=timezone.utc).date(): return f"{name} — {' / '.join(platforms)} release"
    return name

def make_candidates(releases,games,pmap,types,statuses):
    bygame=defaultdict(list)
    for r in releases:
        if exact_day(r): bygame[int(r["game"])].append(r)
    out=[]
     for gid,rows in bygame.items():
        g=games.get(gid)

        if not g or g.get("version_parent"):
            continue

        raw_type = g.get("game_type")
        t = types.get(int(raw_type) if raw_type is not None else -1, "")

        if t not in INCLUDED_GAME_TYPES:
            continue

        bydate=defaultdict(list)
        for r in choose_platform_rows(rows):
            d=exact_day(r)
            if d: bydate[d].append(r)
        for d,rr in bydate.items():
            plats=sorted({pmap[int(r["platform"])] for r in rr if int(r["platform"]) in pmap},key=lambda x:PLATFORM_ORDER.get(x,99))
            if not plats: continue
            st=[statuses.get(int(r.get("status") or -1),"") for r in rr]; st=next((x for x in st if x),"")
            cancelled="cancel" in st.lower(); first=g.get("first_release_date")
            kind=release_type_for(t,d,first)
            out.append({"game_id":gid,"base_name":norm_space(g.get("name","")),"title":title_for(norm_space(g.get("name","")),plats,d,first),
                        "date":d.isoformat(),"platforms":plats,"release_type":kind,"status":"cancelled" if cancelled else "confirmed",
                        "igdb_release_status":st or None,"igdb_updated_at":iso_from_unix(max(int(r.get("updated_at") or 0) for r in rr)),
                        "igdb_release_date_ids":sorted(int(r["id"]) for r in rr),
                        "source":g.get("url") or (f"https://www.igdb.com/games/{g.get('slug')}" if g.get("slug") else "https://www.igdb.com/")})
    return sorted(out,key=lambda e:(e["date"],e["title"].lower(),",".join(e["platforms"])))

def overlap(e,c): return len(set(e.get("platforms",[])) & set(c.get("platforms",[])))
def compatible(a,b):
    a=(a or "").lower(); b=(b or "").lower()
    if a==b or "platform release" in (a,b): return True
    if any(x in a for x in ("dlc","add-on","expansion")) and any(x in b for x in ("dlc","add-on","expansion")): return True
    return a=="game" and b.startswith("game")
def find_match(events,c,claimed):
    m=[(overlap(e,c),i) for i,e in enumerate(events) if i not in claimed and e.get("igdb_game_id")==c["game_id"]]
    if m: return sorted(m,reverse=True)[0][1]
    target=normalize_title(c["base_name"]); m=[]
    for i,e in enumerate(events):
        if i in claimed or normalize_title(e.get("title",""))!=target or not compatible(e.get("release_type",""),c["release_type"]): continue
        m.append((overlap(e,c),i))
    if not m: return None
    m.sort(reverse=True)
    if len(m)>1 and m[0][0]==m[1][0]==0: return None
    return m[0][1]
def verified_day(v):
    try: return date.fromisoformat((v or "")[:10])
    except ValueError: return date.min
def updated_day(c):
    try: return datetime.fromisoformat(c["igdb_updated_at"].replace("Z","+00:00")).date()
    except Exception: return date.min

def merge(e,c,today):
    changes=[]; source_kind=e.get("source_kind","manual")
    if e.get("igdb_game_id")!=c["game_id"]: e["igdb_game_id"]=c["game_id"]; changes.append("linked to IGDB")
    for k in ("igdb_release_date_ids","igdb_updated_at","igdb_release_status"):
        if c.get(k) is not None and e.get(k)!=c[k]: e[k]=c[k]; changes.append(f"{k} refreshed")
    if (source_kind=="igdb" or updated_day(c)>=verified_day(e.get("last_verified"))) and e.get("date")!=c["date"]:
        old=e.get("date"); e["date"]=c["date"]; e["last_verified"]=today.isoformat(); e["sequence"]=int(e.get("sequence",0))+1; changes.append(f"date {old} → {c['date']}")
    if source_kind=="igdb":
        for k in ("title","platforms","release_type","source"):
            if e.get(k)!=c[k]: e[k]=c[k]; changes.append(f"{k} updated"); e["sequence"]=int(e.get("sequence",0))+1 if k!="source" else int(e.get("sequence",0))
    else:
        plats=sorted(set(e.get("platforms",[]))|set(c["platforms"]),key=lambda x:PLATFORM_ORDER.get(x,99))
        if plats!=e.get("platforms",[]): e["platforms"]=plats; e["sequence"]=int(e.get("sequence",0))+1; changes.append("platforms expanded")
    if c["status"]=="cancelled" and e.get("status")!="cancelled": e["status"]="cancelled"; e["sequence"]=int(e.get("sequence",0))+1; e["last_verified"]=today.isoformat(); changes.append("marked cancelled")
    elif source_kind=="igdb" and c["status"]!=e.get("status"): e["status"]=c["status"]; e["sequence"]=int(e.get("sequence",0))+1; changes.append(f"status → {c['status']}")
    return changes

def new_event(c,today):
    return {"uid":stable_uid(c["game_id"],c["platforms"],c["release_type"]),"date":c["date"],"title":c["title"],"platforms":c["platforms"],
            "release_type":c["release_type"],"price":"TBA / not verified","notes":"Automatically added from IGDB. Release date is synchronized; price is not.",
            "source":c["source"],"source_kind":"igdb","status":c["status"],"last_verified":today.isoformat(),"sequence":0,
            "igdb_game_id":c["game_id"],"igdb_release_date_ids":c["igdb_release_date_ids"],"igdb_updated_at":c["igdb_updated_at"],"igdb_release_status":c.get("igdb_release_status")}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--days-back",type=int,default=45); ap.add_argument("--days-ahead",type=int,default=730); ap.add_argument("--dry-run",action="store_true"); ap.add_argument("--no-add-new",action="store_true"); args=ap.parse_args()
    cid=os.environ.get("IGDB_CLIENT_ID","").strip(); secret=os.environ.get("IGDB_CLIENT_SECRET","").strip()
    if not cid or not secret: raise SystemExit("IGDB_CLIENT_ID and IGDB_CLIENT_SECRET must be set.")
    payload=json.loads(DATA_FILE.read_text(encoding="utf-8")); events=payload.get("events",[]); today=date.today(); start=today-timedelta(days=max(0,args.days_back)); end=today+timedelta(days=max(1,args.days_ahead))
    api=IGDB(cid,secret); pmap=resolve_platforms(api); types=resolve_game_types(api); statuses=resolve_statuses(api)
    print("Resolved platforms:"); [print(f"  {label}: IGDB platform {pid}") for pid,label in sorted(pmap.items(),key=lambda x:PLATFORM_ORDER.get(x[1],99))]
    rel=fetch_release_rows(api,sorted(pmap),start,end); games=fetch_games(api,[int(r["game"]) for r in rel]); candidates=make_candidates(rel,games,pmap,types,statuses)
    print(f"IGDB scan: {len(rel)} release-date records, {len(games)} games, {len(candidates)} eligible dated release groups.")
    claimed=set(); added=[]; updated=[]; linked=0; skipped=0
    for c in candidates:
        idx=find_match(events,c,claimed)
        if idx is not None:
            claimed.add(idx); ch=merge(events[idx],c,today)
            if "linked to IGDB" in ch: linked+=1
            meaningful=[x for x in ch if x!="linked to IGDB"]
            if meaningful: updated.append((events[idx]["title"],meaningful))
            continue
        if args.no_add_new: continue
        if c["status"]=="cancelled": skipped+=1; continue
        e=new_event(c,today); events.append(e); added.append(e["title"])
    limit=int(os.environ.get("IGDB_MAX_NEW_EVENTS","2000"))
    if len(added)>limit: raise RuntimeError(f"IGDB wanted to add {len(added)} new events, above safety limit {limit}. No file was written.")
    events.sort(key=lambda e:(e.get("date","9999-99-99"),e.get("title","").lower())); payload["events"]=events; payload.setdefault("calendar",{})["event_count"]=len(events); payload["calendar"]["igdb_sync"]={"enabled":True,"last_scan":today.isoformat(),"window_start":start.isoformat(),"window_end":end.isoformat(),"platforms":list(TARGET_PLATFORM_SPECS)}
    print(f"Linked existing curated entries to IGDB: {linked}"); print(f"Updated existing entries: {len(updated)}")
    for title,ch in updated[:50]: print(f"  UPDATE: {title}: {', '.join(ch)}")
    if len(updated)>50: print(f"  ...and {len(updated)-50} more updates")
    print(f"Added new entries: {len(added)}")
    for title in added[:50]: print(f"  ADD: {title}")
    if len(added)>50: print(f"  ...and {len(added)-50} more additions")
    if skipped: print(f"Skipped already-cancelled new entries: {skipped}")
    if args.dry_run: print("Dry run: data/releases.json was not written."); return
    DATA_FILE.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); print(f"Wrote {DATA_FILE} with {len(events)} events.")
if __name__=="__main__": main()
