# Data

[← Back to README](../README.md)

- [data/feedback.json](../data/feedback.json) holds 20 synthetic feedback items. Each one has an ID, a date, the author's role, the shift, the mission and free text. They are written the way operators actually write: specific tag numbers, times and readings, some guesses at the cause, and some frustration.
- [data/labels.json](../data/labels.json) holds the reference category and priority for each item:
  - Categories: perception 4, sensing 5, mobility_route 5, alerts 3, feature_request 3.
  - Priorities: P1 7, P2 11, P3 2.
- The duplicates are deliberate. There are three glare reports, three reports of thermal alarms contradicted by DCS current, three stairwell reports, two battery reports and three unseen-alert reports. There are also near-misses that should *not* merge. The dirty sight glass (FB-019) and the gauge glare look alike but have different fixes. The same goes for the gas sensor under-reading (FB-020) and the thermal false alarms.
- Some items sit on a category boundary on purpose. FB-006 complains about callouts, but the root cause is sensing. FB-011 is phrased like a feature request, but it describes a route that can't be completed. Those are the items the eval is meant to probe.

**Priority rubric:**

- **P1:** worker safety exposure or a critical measurement (drum level, H2/H2S, safety valves) missed or wrong.
- **P2:** degraded operations or nuisance callouts.
- **P3:** nice-to-have coverage.
