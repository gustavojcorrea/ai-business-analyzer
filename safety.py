"""Data-safety helpers: redact personal data before it leaves the plant, and keep a content-free audit log.

Redaction is deterministic and local (regexes + the site roster), so the redacted text can be checked
before anything is sent. It is a safety net, not a guarantee: names of people who are not in the roster
(visiting contractors, for example) are not caught. See appendix/data-safety.md.
"""

import csv
import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
# North American style numbers and extensions: 555-0142, (555) 010-4471, +1 555 010 4471, ext. 4471
PHONE = re.compile(r"(?:\+?\d{1,2}[ .-]?)?(?:\(\d{3}\)[ .-]?|\b\d{3}[ .-])?\d{3}[ .-]\d{4}\b|\bext\.? ?\d{3,5}\b", re.I)
EMPLOYEE_ID = re.compile(r"\bE\d{5}\b")  # Ridgeview badge numbers; set this per site


class Roster:
    """Maps names, system user IDs and emails to job roles. The roster itself never leaves the plant."""

    def __init__(self, path):
        with open(path, newline="") as f:
            self.people = list(csv.DictReader(f))
        self._by_key = {}
        for p in self.people:
            for key in (p["name"], p["maximo_user"], p["email"]):
                self._by_key[key.lower()] = p["role"]
        # Longest first so "Sam Reilly" is replaced before "Sam".
        names = sorted({n for p in self.people for n in (p["name"], p["name"].split()[0])}, key=len, reverse=True)
        self._name_pattern = re.compile(r"@?\b(" + "|".join(map(re.escape, names)) + r")\b")
        self._role_by_name = {}
        for p in self.people:
            self._role_by_name[p["name"]] = p["role"]
            self._role_by_name.setdefault(p["name"].split()[0], p["role"])

    def role_of(self, key):
        return self._by_key.get((key or "").strip().lower(), "Staff (role not in roster)")

    def redact_names(self, text):
        return self._name_pattern.subn(lambda m: f"[{self._role_by_name[m.group(1)]}]", text)


def redact(text, roster):
    """Return (redacted_text, counts). Counts are per type so ingestion can report what was removed."""
    counts = {}
    text, counts["email"] = EMAIL.subn("[email]", text)
    text, counts["phone"] = PHONE.subn("[phone]", text)
    text, counts["employee_id"] = EMPLOYEE_ID.subn("[employee ID]", text)
    text, counts["name"] = roster.redact_names(text)
    return text, {k: v for k, v in counts.items() if v}


class AuditLog:
    """Append-only JSONL log of what was sent where. Stores hashes and counts, never content."""

    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()

    def write(self, event, **fields):
        record = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": event, **fields}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a") as f:
                f.write(json.dumps(record) + "\n")


def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()
