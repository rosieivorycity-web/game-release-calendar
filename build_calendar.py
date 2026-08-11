#!/usr/bin/env python3
"""Build game-releases.ics and data/metadata.json from data/releases.json.

No third-party packages are required.
"""
from pathlib import Path
from datetime import date, datetime, timezone, timedelta
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "releases.json"
OUT = ROOT / "game-releases.ics"
META = ROOT / "data" / "metadata.json"

def esc(value):
    return (str(value).replace("\\", "\\\\")
            .replace("\n", "\\n")
            .replace(",", "\\,")
            .replace(";", "\\;"))

def fold(line, max_octets=73):
    """RFC 5545-style folding, keeping physical lines comfortably below 75 octets."""
    out = []
    current = ""
    for ch in line:
        candidate = current + ch
        if len(candidate.encode("utf-8")) > max_octets:
            out.append(current)
            current = " " + ch
        else:
            current = candidate
    out.append(current)
    return "\r\n".join(out)

def stable_uid(event):
    if event.get("uid"):
        return event["uid"]
    basis = f'{event["title"]}|{event.get("release_type","Game")}'.strip().lower()
    digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:20]
    return f"{digest}@game-release-calendar"

def icon_for(kind):
    k = kind.lower()
    if "dlc" in k or "expansion" in k or "add-on" in k:
        return "🧩"
    if "update" in k:
        return "✨"
    if "platform release" in k:
        return "🚀"
    return "🎮"

def dt_utc_from_iso_day(day):
    return datetime.strptime(day, "%Y-%m-%d").replace(
        hour=12, minute=0, second=0, tzinfo=timezone.utc
    ).strftime("%Y%m%dT%H%M%SZ")

payload = json.loads(DATA.read_text(encoding="utf-8"))
cal = payload["calendar"]
events = sorted(payload["events"], key=lambda e: (e["date"], e["title"].lower()))

lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Game Release Calendar//GitHub Pages//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    f'X-WR-CALNAME:{esc(cal["name"])}',
    f'X-WR-CALDESC:{esc(cal["description"])}',
    "X-PUBLISHED-TTL:PT24H",
    "REFRESH-INTERVAL;VALUE=DURATION:PT24H",
]

for event in events:
    start = date.fromisoformat(event["date"])
    end = start + timedelta(days=1)
    verified = event.get("last_verified", event["date"])
    last_modified = dt_utc_from_iso_day(verified)
    kind = event.get("release_type", "Game")
    platforms = event.get("platforms", [])
    categories = ["GAME RELEASE"] + [p.upper().replace(" ", "_") for p in platforms]
    low = kind.lower()
    if "dlc" in low or "expansion" in low or "add-on" in low:
        categories.append("DLC")
    if "update" in low:
        categories.append("UPDATE")

    desc_parts = [
        f'Platforms: {" • ".join(platforms)}',
        f'Release type: {kind}',
        f'Price: {event.get("price","TBA / not verified")}',
        f'Status: {event.get("status","confirmed").title()}',
        f'Last verified: {verified}',
    ]
    if event.get("notes"):
        desc_parts.append(f'Notes: {event["notes"]}')
    if event.get("source"):
        desc_parts.append(f'Source: {event["source"]}')

    lines += [
        "BEGIN:VEVENT",
        f'UID:{stable_uid(event)}',
        f'DTSTAMP:{last_modified}',
        f'LAST-MODIFIED:{last_modified}',
        f'SEQUENCE:{int(event.get("sequence", 0))}',
        f'DTSTART;VALUE=DATE:{start.strftime("%Y%m%d")}',
        f'DTEND;VALUE=DATE:{end.strftime("%Y%m%d")}',
        f'SUMMARY:{esc(icon_for(kind) + " " + event["title"])}',
        f'DESCRIPTION:{esc(chr(10).join(desc_parts))}',
    ]
    if event.get("source"):
        lines.append(f'URL:{event["source"]}')
    lines += [
        f'CATEGORIES:{",".join(esc(c) for c in categories)}',
        "TRANSP:TRANSPARENT",
        "STATUS:CONFIRMED",
        "END:VEVENT",
    ]

lines.append("END:VCALENDAR")
OUT.write_text("\r\n".join(fold(line) for line in lines) + "\r\n", encoding="utf-8", newline="")

fingerprint = hashlib.sha256(
    json.dumps(events, sort_keys=True, ensure_ascii=False).encode("utf-8")
).hexdigest()

existing = {}
if META.exists():
    try:
        existing = json.loads(META.read_text(encoding="utf-8"))
    except Exception:
        existing = {}

generated_at = existing.get("generated_at")
if existing.get("data_fingerprint") != fingerprint or not generated_at:
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

metadata = {
    "calendar_name": cal["name"],
    "event_count": len(events),
    "first_event": events[0]["date"] if events else None,
    "last_event": events[-1]["date"] if events else None,
    "generated_at": generated_at,
    "data_fingerprint": fingerprint,
    "feed": "game-releases.ics",
    "platforms": cal.get("platforms", []),
}
META.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"Built {OUT.name}: {len(events)} events")
