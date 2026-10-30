# Integration with the plant's systems

[← Back to README](../README.md)

Ridgeview is fictional, so this page assumes the systems a combined-cycle plant of its size typically runs. Each connector reads a plain export, so swapping one platform for another means writing one small reader function in [ingest.py](../ingest.py).

![Systems and data boundary: Maximo, Teams and the shift log feed ingest.py, which redacts personal data inside the plant network. agent.py sends only redacted text to the Claude API and receives JSON. Outputs go to a backlog report for managers and, after preview and approval, to Jira Cloud.](../docs/integration.svg)

## Where reports come from

| System | What it holds | Sample export | How it would be pulled in production |
|---|---|---|---|
| IBM Maximo | Service requests filed against the robot (classification `ROBOTICS-SPOT`) | [maximo_service_requests.json](../data/sources/maximo_service_requests.json) | Maximo REST (OSLC) API with a read-only integration account, filtered by classification and date |
| Microsoft Teams | Messages in the `#spot-robot` channel | [teams_spot_robot_channel.json](../data/sources/teams_spot_robot_channel.json) | Microsoft Graph channel-messages API with an app registration that has read-only, admin-consented access to that one channel |
| Control room shift log | Operator entries tagged "Robot inspection" | [shift_log.csv](../data/sources/shift_log.csv) | Scheduled CSV export from the eLogbook |

The sample exports hold the same 20 reports as the evaluation set, spread across the three systems. The personal details in them, such as names, emails, a phone number and a badge ID, are fictional and are there to exercise the redaction step. This repo includes the file readers; the production API pulls above are the next step and depend on the plant's credentials and network rules.

`ingest.py` maps every source onto one format:

| Field | Maximo | Teams | Shift log |
|---|---|---|---|
| `id` | `ticketid` (SR-10431) | `TEAMS-` + message ID | `entry_no` |
| `date`, `shift` | `reportdate` | `createdDateTime` | `timestamp` |
| `author_role` | `reportedby` → roster role | `userPrincipalName` → roster role | `author` → roster role |
| `mission` | location description | not stated | `area` |
| `text` | long description, redacted | message body (HTML stripped), redacted | entry, redacted |

Shift is derived from the local time: 07:00 to 18:59 is day shift. The IDs stay the source system's own, so anyone with access can trace a ticket back to the original report and its author.

## Where results go

**To engineering, as Jira tickets.** [publish_jira.py](../publish_jira.py) turns each backlog item into a Jira Cloud issue through the REST API (v3):

| Jira field | Filled from |
|---|---|
| Summary | Ticket title |
| Priority | P1 → High, P2 → Medium, P3 → Low |
| Description | Problem, likely cause, proposed feature, acceptance criteria, business outcomes, impact estimate, report IDs |
| Labels | `spot-agent`, the category, one `kpi-…` label per business outcome, one `spot-src-…` label per source report |

The `kpi-…` labels let the business filter Jira by outcome, for example every open fix that improves availability. The `spot-src-…` labels prevent duplicates: before creating an issue, the script searches for any existing issue that already carries one of its report labels and skips it if found.

It previews by default. `python publish_jira.py` writes the exact payloads to `output/jira_preview.json` without contacting Jira. Only `--apply` creates issues. It needs these environment variables: `JIRA_BASE_URL` (HTTPS only), `JIRA_EMAIL`, `JIRA_API_TOKEN` and `JIRA_PROJECT_KEY`, plus `JIRA_ISSUE_TYPE` if the project doesn't use `Task`.

**To the business, as a report.** `output/backlog.md` and the charts from `make_figures.py` give operations, reliability and plant management the ranked list and the KPI each fix moves. These can be shared however the plant already shares reports, for example on SharePoint or in a Teams channel.

## A weekly cycle

```bash
python ingest.py --since 2026-10-22                  # last week's reports, redacted
python agent.py --input output/inbox.json --out output/week-43
python publish_jira.py --backlog output/week-43/backlog.json            # review the preview
python publish_jira.py --backlog output/week-43/backlog.json --apply    # robotics lead approves
```

## Tested

- `ingest.py` on the sample exports: it produced 20 reports (10 from Maximo, 7 from Teams, 3 from the shift log). It removed 2 phone numbers, 1 email, 3 names and 1 badge ID, and replaced every author with their role. No roster name, email, user ID or badge number remained in the inbox, and redacting the clean evaluation set changed nothing.
- `agent.py --input output/inbox.json`: ran end to end on the redacted inbox.
- `publish_jira.py --apply`: run against a local mock of the Jira Cloud API. It checked the endpoints, authentication, the description format (Atlassian Document Format), label format and duplicate skipping. It has not been run against a live Jira site.
