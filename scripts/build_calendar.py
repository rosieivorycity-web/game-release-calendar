#!/usr/bin/env python3
"""Build game-releases.ics and data/metadata.json from data/releases.json."""
from pathlib import Path
from datetime import date, datetime, timezone, timedelta
import hashlib, json
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/"data"/"releases.json"; OUT=ROOT/"game-releases.ics"; META=ROOT/"data"/"metadata.json"
def esc(v): return str(v).replace("\\","\\\\").replace("\n","\\n").replace(",","\\,").replace(";","\\;")
def fold(line,max_octets=73):
    out=[]; cur=""
    for ch in line:
        cand=cur+ch
        if len(cand.encode("utf-8"))>max_octets: out.append(cur); cur=" "+ch
        else: cur=cand
    out.append(cur); return "\r\n".join(out)
def uid(e):
    if e.get("uid"): return e["uid"]
    h=hashlib.sha1(f'{e["title"]}|{e.get("release_type","Game")}'.lower().encode()).hexdigest()[:20]; return f"{h}@game-release-calendar"
def icon(kind,status="confirmed"):
    if "cancel" in status.lower(): return "❌"
    k=kind.lower()
    if any(x in k for x in ("dlc","expansion","add-on","pack")): return "🧩"
    if "update" in k: return "✨"
    if "platform release" in k or "port" in k: return "🚀"
    return "🎮"
def stamp(day): return datetime.strptime(day,"%Y-%m-%d").replace(hour=12,tzinfo=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
p=json.loads(DATA.read_text(encoding="utf-8")); cal=p["calendar"]; events=sorted(p["events"],key=lambda e:(e["date"],e["title"].lower()))
lines=["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//Game Release Calendar//GitHub Pages//EN","CALSCALE:GREGORIAN","METHOD:PUBLISH",f'X-WR-CALNAME:{esc(cal["name"])}',f'X-WR-CALDESC:{esc(cal["description"])}',"X-PUBLISHED-TTL:PT24H","REFRESH-INTERVAL;VALUE=DURATION:PT24H"]
for e in events:
    s=date.fromisoformat(e["date"]); en=s+timedelta(days=1); verified=e.get("last_verified",e["date"]); lm=stamp(verified); kind=e.get("release_type","Game"); plats=e.get("platforms",[]); st=e.get("status","confirmed")
    cats=["GAME RELEASE"]+[x.upper().replace(" ","_") for x in plats]; low=kind.lower()
    if any(x in low for x in ("dlc","expansion","add-on","pack")): cats.append("DLC")
    if "update" in low: cats.append("UPDATE")
    desc=[f'Platforms: {" • ".join(plats)}',f'Release type: {kind}',f'Price: {e.get("price","TBA / not verified")}',f'Status: {st.title()}',f'Last verified: {verified}']
    if e.get("igdb_release_status"): desc.append(f'IGDB release status: {e["igdb_release_status"]}')
    if e.get("notes"): desc.append(f'Notes: {e["notes"]}')
    if e.get("source"): desc.append(f'Source: {e["source"]}')
    lines += ["BEGIN:VEVENT",f'UID:{uid(e)}',f'DTSTAMP:{lm}',f'LAST-MODIFIED:{lm}',f'SEQUENCE:{int(e.get("sequence",0))}',f'DTSTART;VALUE=DATE:{s.strftime("%Y%m%d")}',f'DTEND;VALUE=DATE:{en.strftime("%Y%m%d")}',f'SUMMARY:{esc(icon(kind,st)+" "+e["title"])}',f'DESCRIPTION:{esc(chr(10).join(desc))}']
    if e.get("source"): lines.append(f'URL:{e["source"]}')
    lines += [f'CATEGORIES:{",".join(esc(c) for c in cats)}',"TRANSP:TRANSPARENT",f'STATUS:{"CANCELLED" if "cancel" in st.lower() else "CONFIRMED"}',"END:VEVENT"]
lines.append("END:VCALENDAR"); OUT.write_text("\r\n".join(fold(x) for x in lines)+"\r\n",encoding="utf-8",newline="")
fingerprint=hashlib.sha256(json.dumps(events,sort_keys=True,ensure_ascii=False).encode()).hexdigest(); old={}
if META.exists():
    try: old=json.loads(META.read_text(encoding="utf-8"))
    except Exception: old={}
generated=old.get("generated_at") if old.get("data_fingerprint")==fingerprint else None
if not generated: generated=datetime.now(timezone.utc).isoformat(timespec="seconds")
META.write_text(json.dumps({"calendar_name":cal["name"],"event_count":len(events),"first_event":events[0]["date"] if events else None,"last_event":events[-1]["date"] if events else None,"generated_at":generated,"data_fingerprint":fingerprint,"feed":"game-releases.ics","platforms":cal.get("platforms",[])},indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
print(f"Built {OUT.name}: {len(events)} events")
