"""Collect Spot feedback from the plant's systems, strip personal data, and write the agent's inbox.

Sources (read-only exports; see appendix/integration.md for how each is pulled in production):
  - Maximo service requests   data/sources/maximo_service_requests.json  (OSLC REST API JSON)
  - Teams #spot-robot channel  data/sources/teams_spot_robot_channel.json (Microsoft Graph messages JSON)
  - Control room shift log     data/sources/shift_log.csv                  (eLogbook CSV export)

Usage:
  python ingest.py                     # writes output/inbox.json
  python ingest.py --since 2026-10-01  # only reports on or after a date
  python agent.py --input output/inbox.json
"""

import argparse
import csv
import html
import json
import re
import sys
from collections import Counter
from datetime import date, datetime

import agent
import safety

SOURCES_DIR = agent.DATA_DIR / "sources"
DAY_SHIFT_HOURS = range(7, 19)  # 07:00-18:59 local is day shift at Ridgeview


def read_maximo(path):
    for sr in json.loads(path.read_text())["member"]:
        yield {
            "id": sr["ticketid"],
            "source": "maximo",
            "timestamp": sr["reportdate"],
            "author": sr["reportedby"],
            "mission": sr.get("location_description") or sr["location"],
            "text": sr["description_longdescription"],
        }


def read_teams(path):
    for msg in json.loads(path.read_text())["value"]:
        if msg["messageType"] != "message":
            continue
        yield {
            "id": f"TEAMS-{msg['id'][-6:]}",
            "source": "teams",
            "timestamp": msg["createdDateTime"],
            "author": msg["from"]["user"]["userPrincipalName"],
            "mission": "not stated",
            "text": html.unescape(re.sub(r"<[^>]+>", "", msg["body"]["content"])).strip(),
        }


def read_shift_log(path):
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            yield {
                "id": row["entry_no"],
                "source": "shift_log",
                "timestamp": row["timestamp"],
                "author": row["author"],
                "mission": row["area"],
                "text": row["entry"],
            }


READERS = {
    "maximo_service_requests.json": read_maximo,
    "teams_spot_robot_channel.json": read_teams,
    "shift_log.csv": read_shift_log,
}


def normalise(record, roster):
    """Map a source record to the agent's input format. The author's identity is replaced by their role."""
    ts = datetime.fromisoformat(record["timestamp"])
    text, removed = safety.redact(record["text"], roster)
    item = {
        "id": record["id"],
        "source": record["source"],
        "date": ts.date().isoformat(),
        "author_role": roster.role_of(record["author"]),
        "shift": "day" if ts.hour in DAY_SHIFT_HOURS else "night",
        "mission": record["mission"],
        "text": text,
    }
    return item, removed


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--since", type=date.fromisoformat, help="only include reports on or after this date")
    parser.add_argument("--sources", type=agent.Path, default=SOURCES_DIR, help="directory with the exports")
    parser.add_argument("--out", type=agent.Path, default=agent.OUT_DIR / "inbox.json")
    args = parser.parse_args()

    roster = safety.Roster(args.sources / "roster.csv")
    items, removed_total, per_source = [], Counter(), Counter()
    for filename, reader in READERS.items():
        path = args.sources / filename
        if not path.exists():
            print(f"  skipping {filename}: not found", file=sys.stderr)
            continue
        for record in reader(path):
            item, removed = normalise(record, roster)
            if args.since and date.fromisoformat(item["date"]) < args.since:
                continue
            items.append(item)
            removed_total.update(removed)
            per_source[item["source"]] += 1

    items.sort(key=lambda i: (i["date"], i["id"]))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    agent.write_json(args.out, items)
    safety.AuditLog(args.out.parent / "audit.jsonl").write(
        "ingest", items=len(items), per_source=dict(per_source), redacted=dict(removed_total),
        inbox_sha256=safety.sha256(args.out.read_text()),
    )
    sources = ", ".join(f"{n} from {s}" for s, n in per_source.items())
    redacted = ", ".join(f"{n} {k.replace('_', ' ')}{'s' if n != 1 else ''}" for k, n in removed_total.items()) or "nothing"
    print(f"Wrote {len(items)} reports to {args.out} ({sources}).", file=sys.stderr)
    print(f"Redacted before sending: {redacted}. Author names replaced with job roles.", file=sys.stderr)


if __name__ == "__main__":
    main()
