# How it works

[← Back to README](../README.md)

![Pipeline diagram: feedback.json flows through 1 Classify (20 Claude calls), 2 Merge (1 Claude call, 20 reports to 11 issues), 3 Ticket (11 Claude calls) and 4 Rank (Python) into backlog.md. Classifications also feed eval.py, which compares them with labels.json.](../docs/pipeline.svg)

1. **Classify.** Each item gets one category, a priority from 1 to 3 and a one-line summary. The categories are `perception`, `mobility_route`, `sensing`, `alerts` and `feature_request`, and the system prompt defines each one by root cause, so a thermal false alarm counts as `sensing` even when the complaint is about being paged.
2. **Merge duplicates.** One call sees every classified item and groups the ones that a single engineering fix would resolve. The code then enforces that every item ends up in exactly one issue: unknown IDs and IDs used twice are dropped, and any item left out becomes its own issue.
3. **Draft a ticket and estimate impact.** For each issue Claude writes the problem, the likely cause and a proposed feature, plus 2-4 acceptance criteria. It also estimates four impact dimensions:
   - missed measurement points per week
   - downtime risk (1-5)
   - false-alarm callouts per month
   - worker safety exposure (1-5)

   In the same call it maps the fix to the **site KPIs** it improves, most important first, with a one-sentence effect grounded in the reports. Claude is told not to invent dollar figures or numbers the reports can't support. The KPIs are a fixed list (`SITE_KPIS` in [agent.py](../agent.py)), so every ticket speaks the same business language:

   | KPI | What it covers |
   |---|---|
   | Plant availability | Unplanned downtime, forced outages, derates |
   | Revenue at risk | Lost MWh from trips or derates |
   | Inspection coverage | Share of planned readings captured and usable |
   | Maintenance and callout cost | Overtime, unnecessary dispatches, manual rounds |
   | Worker safety | Exposure in hazardous areas: gas, HV, stairs, hot work |
   | Environmental compliance | CEMS data availability, permit reporting |
   | Alarm response time | Time from detection to acknowledgement |

   The backlog report lists which fixes move each KPI, and the Jira tickets carry one `kpi-…` label per outcome so the business can filter by outcome.
4. **Rank.** Python, not the model, combines the four dimensions into a 0-100 **impact score**, so the ranking is deterministic and easy to audit:

   | Dimension | Weight | Normalisation |
   |---|---:|---|
   | Worker safety exposure | 35 | (score − 1) / 4 |
   | Downtime risk | 30 | (score − 1) / 4 |
   | Missed measurement points / week | 20 | capped at 100 |
   | False-alarm callouts / month | 15 | capped at 10 |

   Issues are sorted by impact score. Ties go to the more urgent operator priority (the lowest priority number among the issue's reports), then to the issue with more reports. The weights are `IMPACT_WEIGHTS` in [agent.py](../agent.py).

Every call uses structured outputs (`output_config.format` with a JSON schema), so responses parse without any cleanup. The calls also opt into server-side refusal fallback (`fallbacks: "default"`): if a safety classifier wrongly declines a request about hydrogen or H2S, the API retries it on a recommended model instead of failing the run.

Reports reach the model wrapped in `<report>` tags and already redacted, and every call is written to `output/audit.jsonl`. See [Data safety](data-safety.md).

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `SPOT_AGENT_MODEL` | `claude-opus-5-5` | Model for all calls |
| `SPOT_AGENT_EFFORT` | `medium` | `low` / `medium` / `high` / `xhigh` / `max` |
| `SPOT_AGENT_WORKERS` | `5` | Parallel API calls |

A full run makes 20 classification calls, 1 grouping call and one ticket call per issue: 32 calls for the sample, costing about $0.71 (see the [pipeline review](pipeline-review.md)).

## Commands

```bash
python ingest.py                   # pull Maximo, Teams and shift-log exports, redact -> output/inbox.json
python agent.py --input output/inbox.json   # run on the redacted inbox
python agent.py                    # run on the evaluation set -> output/backlog.md, backlog.json, classifications.json
python agent.py --classify-only    # step 1 only
python publish_jira.py             # preview Jira tickets -> output/jira_preview.json
python publish_jira.py --apply     # create them (needs JIRA_* variables, see integration.md)
python cost_report.py --write-appendix   # measured tokens and cost, projections, ROI -> appendix/pipeline-review.md
python eval.py                     # classify all items, then score against data/labels.json
python eval.py --predictions output/classifications.json   # re-score the last agent run, no API calls
python eval.py --write-appendix    # also write the results into appendix/evaluation.md
python make_figures.py             # redraw the figures in docs/ from the latest output/
```
