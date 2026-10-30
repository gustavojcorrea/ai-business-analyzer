# spot-feedback-agent

Turns operator and technician feedback about Boston Dynamics Spot inspection robots into a ranked engineering backlog, using the Claude API. Every item in the backlog is sorted by business impact and mapped to the site outcome that fixing it improves, such as less unplanned downtime, protected generation revenue, better inspection coverage, lower callout costs or safer work.

**The scenario.** Ridgeview Combined Cycle is a fictional 750 MW power plant, modelled on Boston Dynamics' case studies at [Wien Energie](https://bostondynamics.com/case-studies/spot-makes-austrias-largest-power-plant-safer/) in Vienna and [J-POWER](https://bostondynamics.com/case-studies/spot-at-j-power/) in Japan. At both plants, Spot walks routine rounds reading gauges, taking thermal images and measuring gas. At Ridgeview, the staff who rely on those rounds report what goes wrong (glare on gauges, false thermal alarms, missions aborted on stairs, alerts nobody sees at night), and this agent turns those reports into a prioritised list of fixes.

![Two side-by-side flowcharts. Left, today's manual process: reports arrive scattered across channels, a lead sorts them by hand, duplicates are spotted from memory, an engineer rewrites them into tickets, priorities are set in a meeting, and safety issues can sit in the pile. Right, with the agent: reports are collected into one file, Claude classifies them, merges duplicates and drafts tickets, Python scores and ranks them, and the lead reviews the ranked backlog before engineering builds.](docs/process.svg)

The agent takes over the reading, sorting and first drafts. People still make the final call.

## What it does

1. **Classifies** each report by category and priority.
2. **Merges** reports that describe the same problem.
3. **Drafts** an engineering ticket for each problem, covering the cause, the fix and acceptance criteria.
4. **Maps** each fix to the site KPIs it improves, and says roughly by how much.
5. **Ranks** the backlog by business impact: safety, downtime, missed readings and false alarms.

![Pipeline diagram: feedback.json flows through 1 Classify (20 Claude calls), 2 Merge (1 Claude call, 20 reports to 11 issues), 3 Ticket (11 Claude calls) and 4 Rank (Python) into backlog.md. Classifications also feed eval.py, which compares them with labels.json.](docs/pipeline.svg)

## How it fits the plant's systems

Reports are pulled from the systems the plant already uses: IBM Maximo service requests, a Microsoft Teams channel and the control room shift log. Results go back out as a ranked report for management and as Jira tickets for the robotics team.

![Systems and data boundary: Maximo, Teams and the shift log feed ingest.py, which redacts personal data inside the plant network. agent.py sends only redacted text to the Claude API and receives JSON. Outputs go to a backlog report for managers and, after preview and approval, to Jira Cloud.](docs/integration.svg)

**Data safety:**

- Names, emails, phone numbers and badge IDs are removed on the plant side before anything is sent. Each author is replaced by their job role.
- Report text is treated as data, never as instructions. The agent has no tools and can only return structured JSON.
- Nothing is written to Jira until a person reviews the preview and runs it with `--apply`.
- Every API call is logged, with no content.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...

python ingest.py                               # pull and redact reports from the plant systems
python agent.py --input output/inbox.json      # build the ranked backlog
python publish_jira.py                         # preview the Jira tickets (add --apply to create them)
python cost_report.py                          # tokens, cost and ROI
```

## Results

On 20 sample reports:

- **Categories:** 20 out of 20 correct.
- **Priorities:** 17 out of 20 correct, and every miss was off by one level.
- **Merging:** the 20 reports became 11 issues, matching the duplicate groups built into the data. Running the same reports through Maximo, Teams and the shift log gave the same 11 groups.
- **Top issue:** robot alerts that go unseen on night shift.

**What fixing the top issues would improve:**

| Rank | Fix | Main site outcome |
|---:|---|---|
| 1 | Route robot alerts to the control room alarm list and operator handhelds | **Alarm response time:** from the reported 4 hours (H2 alert) and 1.5 days (pump oil alert) to minutes |
| 2 | Check thermal alarms against live load before paging anyone | **Callout cost:** about 4 unnecessary night callouts a month avoided |
| 3 | Fix the gas sensor that under-reads H2S | **Worker safety:** no more false "all clear" before staff enter a toxic area |
| 4 | Detect and recapture gauge images spoiled by glare | **Inspection coverage:** about 12 usable gauge readings a week recovered |
| 5 | Wait, retry or reroute when people are on the stairs | **Inspection coverage:** about 30 missed readings a week recovered |

![Matrix of the 11 ranked backlog issues against seven site KPIs. Inspection coverage and maintenance cost are each improved by 9 fixes, plant availability by 6, worker safety by 5, alarm response by 2 and emissions compliance by 1. No fix was mapped to revenue at risk directly.](docs/outcomes.svg)

No fix in this run was mapped to revenue directly. Revenue protection shows up through plant availability: the six fixes that cut the risk of an undetected trip or derate.

![Flow diagram: each of the 20 feedback items, coloured by its predicted category, flows into one of 11 issues ranked by impact score. The three unseen-alert reports merge into the top issue, three thermal reports into the second, and the glare, stairwell and battery reports each merge into one issue further down. The other issues each come from a single report.](docs/flow.svg)

![Stacked bar chart of each issue's impact score, split into contributions from worker safety exposure, downtime risk, missed measurement points and false-alarm callouts. The alerts issue is driven mostly by safety and downtime, the battery-range issue mostly by missed measurement points, and the H2S sensor issue mostly by safety. The three new-inspection-point requests score close to zero.](docs/impact.svg)

## Cost and ROI

**Measured:** one run on 20 reports used about 81,000 tokens (32 API calls) and cost **$0.71**, about 3.5 cents per report. It took just over a minute. Two-thirds of the cost is drafting the tickets.

**Projected**, running once a day on that day's new reports:

| Scenario | Reports / day | API cost / year | Triage time saved / year | Net value / year | ROI |
|---|---:|---:|---:|---:|---:|
| One robot, quiet | 1 | $13 | 73 h | $2,237 | 0.5× |
| One robot, busy | 5 | $65 | 365 h | $28,465 | 6.5× |
| Robot fleet | 20 | $259 | 1,460 h | $126,821 | 27.7× |

The API bill is small. The case rests on how many reports the plant gets and how long manual triage really takes. The table assumes:
- 15 minutes of manual triage per report, against 3 minutes reviewing the agent's draft
- $90 an hour for engineer time
- 4 hours a month of upkeep

Separately, the agent's own estimates say the current backlog, once fixed, would avoid about 18 false-alarm callouts a month, roughly $52,000 a year in on-call overtime. The full breakdown and assumptions are in the [pipeline review](appendix/pipeline-review.md).

## Appendix

- [How it works](appendix/how-it-works.md): the pipeline, the impact score, site KPIs and settings.
- [Integration](appendix/integration.md): the plant systems, field mappings, the Jira format and a weekly cycle.
- [Data safety](appendix/data-safety.md): what leaves the plant, the controls and their limits.
- [Pipeline review](appendix/pipeline-review.md): measured tokens and cost, daily and annual projections, ROI.
- [Data](appendix/data.md): the sample reports and how they were labelled.
- [Example backlog](appendix/example-backlog.md): the full ranked output with every ticket's business outcomes.
- [Evaluation](appendix/evaluation.md): detailed scores and the three priority misses.
- [Basis for the scenario](appendix/scenario.md): the Boston Dynamics case studies.
