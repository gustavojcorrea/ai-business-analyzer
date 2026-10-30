"""Publish the ranked backlog to Jira Cloud as one issue per backlog item.

Preview is the default: nothing is sent until you pass --apply. Before creating an issue it checks
whether any existing issue already carries a label for one of the same source reports, so re-running
the agent doesn't file duplicates.

Usage:
  python publish_jira.py              # preview -> output/jira_preview.json, no network calls
  python publish_jira.py --apply      # create the issues (needs the JIRA_* variables below)

Environment:
  JIRA_BASE_URL     e.g. https://ridgeview.atlassian.net
  JIRA_EMAIL        account email for the API token
  JIRA_API_TOKEN    Jira API token (never logged or written to disk)
  JIRA_PROJECT_KEY  e.g. ROBO
  JIRA_ISSUE_TYPE   default: Task
"""

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

import agent
import safety

# Agent priority -> Jira's default priority scheme. Adjust if the project uses a custom scheme.
PRIORITY_NAMES = {1: "High", 2: "Medium", 3: "Low"}
FOOTER = (
    "Drafted by spot-feedback-agent from redacted operator reports. Reporter identities stay in the source "
    "systems; look them up by report ID. Review before scheduling."
)


def label_for(report_id):
    # Jira labels can't contain spaces; keep them short and predictable for de-duplication.
    return "spot-src-" + re.sub(r"[^A-Za-z0-9_-]", "-", report_id)


def paragraph(text):
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def heading(text):
    return {"type": "heading", "attrs": {"level": 3}, "content": [{"type": "text", "text": text}]}


def bullets(lines):
    return {"type": "bulletList", "content": [{"type": "listItem", "content": [paragraph(l)]} for l in lines]}


def description(ticket, rank):
    imp = ticket["impact"]
    return {
        "type": "doc",
        "version": 1,
        "content": [
            paragraph(f"Backlog rank {rank} · impact score {ticket['impact_score']} / 100 · "
                      f"reports: {', '.join(ticket['item_ids'])}"),
            heading("Problem"), paragraph(ticket["problem"]),
            heading("Likely cause"), paragraph(ticket["likely_cause"]),
            heading("Proposed feature"), paragraph(ticket["proposed_feature"]),
            heading("Acceptance criteria"), bullets(ticket["acceptance_criteria"]),
            heading("Business outcomes if fixed"),
            bullets([f"{agent.SITE_KPIS[o['kpi']].split(' (')[0]}: {o['effect']}" for o in ticket["business_outcomes"]]),
            heading("Impact estimate"),
            bullets([
                f"Worker safety exposure: {imp['worker_safety_exposure']}/5",
                f"Downtime risk: {imp['downtime_risk']}/5",
                f"Missed measurement points per week: {imp['missed_measurement_points_per_week']}",
                f"False-alarm callouts per month: {imp['false_alarm_callouts_per_month']}",
            ]),
            paragraph(imp["rationale"]),
            paragraph(FOOTER),
        ],
    }


def issue_payload(ticket, rank, project_key, issue_type):
    return {
        "fields": {
            "project": {"key": project_key},
            "issuetype": {"name": issue_type},
            "summary": ticket["title"][:250],  # Jira's summary limit is 255 characters
            "priority": {"name": PRIORITY_NAMES[ticket["priority"]]},
            "labels": ["spot-agent", f"spot-{ticket['category'].replace('_', '-')}",
                       *[f"kpi-{o['kpi'].replace('_', '-')}" for o in ticket["business_outcomes"]],
                       *[label_for(i) for i in ticket["item_ids"]]],
            "description": description(ticket, rank),
        }
    }


class Jira:
    def __init__(self, base_url, email, token):
        self.base_url = base_url.rstrip("/")
        if not self.base_url.startswith("https://"):
            sys.exit("JIRA_BASE_URL must start with https:// so the API token is never sent in clear text")
        self._auth = "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()

    def _request(self, method, path, body=None):
        req = urllib.request.Request(
            self.base_url + path,
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": self._auth, "Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:500]
            raise RuntimeError(f"Jira {method} {path.split('?')[0]} failed: HTTP {e.code}: {detail}") from None

    def find_existing(self, project_key, labels):
        jql = f'project = "{project_key}" AND labels in ({", ".join(json.dumps(l) for l in labels)})'
        query = urllib.parse.urlencode({"jql": jql, "fields": "summary", "maxResults": 5})
        return [issue["key"] for issue in self._request("GET", f"/rest/api/3/search/jql?{query}").get("issues", [])]

    def create(self, payload):
        return self._request("POST", "/rest/api/3/issue", payload)["key"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backlog", type=agent.Path, default=agent.OUT_DIR / "backlog.json")
    parser.add_argument("--apply", action="store_true", help="create the issues in Jira (default: preview only)")
    parser.add_argument("--limit", type=int, help="only publish the top N backlog items")
    args = parser.parse_args()

    tickets = json.loads(args.backlog.read_text())[: args.limit]
    project_key = os.environ.get("JIRA_PROJECT_KEY", "ROBO")
    issue_type = os.environ.get("JIRA_ISSUE_TYPE", "Task")
    payloads = [issue_payload(t, rank, project_key, issue_type) for rank, t in enumerate(tickets, 1)]
    audit = safety.AuditLog(agent.OUT_DIR / "audit.jsonl")

    if not args.apply:
        preview = agent.OUT_DIR / "jira_preview.json"
        agent.write_json(preview, payloads)
        for rank, (t, p) in enumerate(zip(tickets, payloads), 1):
            print(f"  {rank:>2}. [{p['fields']['priority']['name']:<6}] {t['title'][:90]}")
        print(f"\nPreview only: {len(payloads)} issues for project {project_key} written to {preview}.\n"
              "Review them, then re-run with --apply to create them.", file=sys.stderr)
        audit.write("jira_preview", issues=len(payloads), project=project_key)
        return

    missing = [v for v in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_PROJECT_KEY") if not os.environ.get(v)]
    if missing:
        sys.exit(f"Set {', '.join(missing)} before running with --apply.")
    jira = Jira(os.environ["JIRA_BASE_URL"], os.environ["JIRA_EMAIL"], os.environ["JIRA_API_TOKEN"])

    created, skipped = [], []
    for t, payload in zip(tickets, payloads):
        existing = jira.find_existing(project_key, [label_for(i) for i in t["item_ids"]])
        if existing:
            skipped.append(existing[0])
            print(f"  skip   {existing[0]:<10} already tracks reports {', '.join(t['item_ids'])}")
            continue
        key = jira.create(payload)
        created.append(key)
        print(f"  create {key:<10} {t['title'][:80]}")
    audit.write("jira_publish", project=project_key, created=created, skipped=skipped)
    print(f"\nCreated {len(created)} issues, skipped {len(skipped)} already tracked.", file=sys.stderr)


if __name__ == "__main__":
    main()
