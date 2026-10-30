# Evaluation

[← Back to README](../README.md)

[eval.py](../eval.py) compares the agent's category and priority predictions with [data/labels.json](../data/labels.json). It reports:
- category accuracy
- exact priority accuracy
- priority within ±1
- joint accuracy
- per-category precision and recall
- a confusion matrix
- every miss, with the model's own rationale

<!-- EVAL:START -->
| Metric | Score |
|---|---:|
| Category accuracy | **100%** (20/20) |
| Priority accuracy (exact) | **85%** (17/20) |
| Priority within ±1 | 100% |
| Category and priority both correct | 85% |

| Category | Support | Precision | Recall |
|---|---:|---:|---:|
| perception | 4 | 100% | 100% |
| mobility_route | 5 | 100% | 100% |
| sensing | 5 | 100% | 100% |
| alerts | 3 | 100% | 100% |
| feature_request | 3 | 100% | 100% |

| Item | Label | Predicted | Model rationale |
|---|---|---|---|
| FB-013 | alerts P1 | alerts P2 | The root cause is correct findings not reaching the right person in time (notification channel, night coverage, escalation), which delays reaction; no specific safety incident or missed critical reading is reported, so priority 2. |
| FB-015 | feature_request P2 | feature_request P3 | This asks for new inspection coverage while nothing is broken today, and it would replace an existing manual operator check with no direct safety exposure, so it is a priority-3 feature request. |
| FB-018 | sensing P2 | sensing P1 | The root cause is an acoustic sensor finding made without DCS process context, so it is sensing; it is priority 1 because a false HP steam leak alarm on every run trains staff to ignore real high-pressure steam leak alarms. |

_Model: claude-opus-5-5, effort: medium._
<!-- EVAL:END -->

Twenty items is a smoke test, not a benchmark. One item is worth 5 points of accuracy, so treat differences of one or two items between runs or models as noise.
