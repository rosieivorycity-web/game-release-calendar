#!/usr/bin/env python3
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "releases.json"
ICS = ROOT / "game-releases.ics"

errors = []
payload = json.loads(DATA.read_text(encoding="utf-8"))
events = payload.get("events", [])

seen_uid = set()
for i, e in enumerate(events, start=1):
    for required in ("date", "title", "platforms", "release_type", "source"):
        if required not in e:
            errors.append(f"Event {i} missing {required}: {e.get('title','(untitled)')}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", e.get("date","")):
        errors.append(f"Bad date on {e.get('title','(untitled)')}: {e.get('date')}")
    uid = e.get("uid")
    if uid:
        if uid in seen_uid:
            errors.append(f"Duplicate UID: {uid}")
        seen_uid.add(uid)

if not ICS.exists():
    errors.append("game-releases.ics was not generated")
else:
    raw = ICS.read_text(encoding="utf-8")
    if not raw.startswith("BEGIN:VCALENDAR"):
        errors.append("ICS missing BEGIN:VCALENDAR")
    if not raw.rstrip().endswith("END:VCALENDAR"):
        errors.append("ICS missing END:VCALENDAR")
    count = raw.count("BEGIN:VEVENT")
    if count != len(events):
        errors.append(f"ICS has {count} events but JSON has {len(events)}")

if errors:
    print("VALIDATION FAILED")
    for error in errors:
        print(" -", error)
    sys.exit(1)

print(f"Validation passed: {len(events)} events")
