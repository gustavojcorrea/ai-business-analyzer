"""Render the README and appendix figures (docs/*.svg) from the latest agent run.

Usage:
  python agent.py          # produces output/backlog.json and output/classifications.json
  python make_figures.py   # writes docs/pipeline.svg, docs/flow.svg, docs/impact.svg

Plain SVG, no dependencies. Each file carries light and dark colours and follows the
viewer's colour scheme.
"""

import json
from html import escape
from pathlib import Path

import agent

DOCS_DIR = agent.ROOT / "docs"
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

# Categorical slots in fixed order (validated light/dark against the chart surfaces).
LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181"]

CATEGORY_LABELS = {
    "perception": "Perception",
    "mobility_route": "Mobility / route",
    "sensing": "Sensing",
    "alerts": "Alerts",
    "feature_request": "Feature request",
}
DIMENSION_LABELS = {
    "worker_safety_exposure": "Worker safety exposure",
    "downtime_risk": "Downtime risk",
    "missed_measurement_points_per_week": "Missed measurement points",
    "false_alarm_callouts_per_month": "False-alarm callouts",
}


def style(n_series):
    """Role tokens as CSS classes; dark values apply when the viewer's OS is in dark mode."""
    light = "\n".join(f"  .s{i} {{ fill: {c}; }} .b{i} {{ stroke: {c}; }}" for i, c in enumerate(LIGHT[:n_series]))
    dark = "\n".join(f"    .s{i} {{ fill: {c}; }} .b{i} {{ stroke: {c}; }}" for i, c in enumerate(DARK[:n_series]))
    return f"""<style>
  svg {{ font-family: {FONT}; }}
  .surface {{ fill: #fcfcfb; stroke: rgba(11,11,11,0.10); }}
  .t1 {{ fill: #0b0b0b; }} .t2 {{ fill: #52514e; }} .t3 {{ fill: #898781; }}
  .grid {{ stroke: #e1e0d9; }} .axis {{ stroke: #c3c2b7; }}
  .box {{ fill: #fcfcfb; stroke: #c3c2b7; }} .box-model {{ fill: #eef4fc; stroke: #86b6ef; }}
  .pill-model {{ fill: #2a78d6; }} .pill-local {{ fill: #52514e; }} .on-pill {{ fill: #ffffff; }}
  .arrow {{ stroke: #898781; fill: none; }} .arrowhead {{ fill: #898781; }}
  .num {{ font-variant-numeric: tabular-nums; }}
  .hurdle {{ fill: #d03b3b; }} .gain {{ fill: #0ca30c; }}
  .boundary {{ fill: none; stroke: #898781; }}
{light}
  @media (prefers-color-scheme: dark) {{
    .surface {{ fill: #1a1a19; stroke: rgba(255,255,255,0.10); }}
    .t1 {{ fill: #f0efec; }} .t2 {{ fill: #c3c2b7; }} .t3 {{ fill: #898781; }}
    .grid {{ stroke: #2c2c2a; }} .axis {{ stroke: #383835; }}
    .box {{ fill: #1a1a19; stroke: #383835; }} .box-model {{ fill: #16263b; stroke: #256abf; }}
    .pill-model {{ fill: #3987e5; }} .pill-local {{ fill: #52514e; }}
{dark}
  }}
</style>"""


def svg(width, height, body, n_series, title, desc):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-labelledby="title desc">\n<title id="title">{escape(title)}</title>\n'
        f'<desc id="desc">{escape(desc)}</desc>\n{style(n_series)}\n'
        f'<rect class="surface" x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="12"/>\n'
        + "\n".join(body)
        + "\n</svg>\n"
    )


def text(x, y, s, cls="t1", size=13, anchor="start", weight=400):
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" font-size="{size}" text-anchor="{anchor}" '
        f'font-weight="{weight}">{escape(str(s))}</text>'
    )


def truncate(s, max_chars):
    if len(s) <= max_chars:
        return s
    cut = s[: max_chars - 1].rsplit(" ", 1)[0].rstrip(",:;/-")
    return cut + "…"


def bar_path(x, y, w, h, r=4):
    """Rectangle with only the data end (right side) rounded."""
    r = min(r, w, h / 2)
    return (
        f"M{x:.1f},{y:.1f} H{x + w - r:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} "
        f"V{y + h - r:.1f} Q{x + w:.1f},{y + h:.1f} {x + w - r:.1f},{y + h:.1f} H{x:.1f} Z"
    )


def wrap(s, max_chars):
    lines, line = [], ""
    for word in s.split():
        if line and len(line) + 1 + len(word) > max_chars:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return lines + [line] if line else lines


# --- Figure 0: business process, before and after ---------------------------------------

def process_figure(n_items, n_issues, category_accuracy):
    # (title, detail, note) per step. Rows line up so each manual step faces its replacement.
    before = [
        ("Reports come in", "Emails, shift logs, radio calls, chat",
         "Scattered across channels; the same failure is described in different words."),
        ("Manual sorting", "Robotics lead reads and sorts reports, usually weekly",
         "Slow, and the categories depend on who does the sorting."),
        ("Spot duplicates", "From memory, across weeks of reports",
         "Repeats are filed as separate jobs or missed, hiding the pattern."),
        ("Write tickets", "An engineer rewrites reports into tickets",
         "Vague tickets; back-and-forth to recover tag numbers, readings and cause."),
        ("Prioritise in a meeting", "Ranked by judgement and the urgency of the day",
         "No shared measure of business impact; the loudest issue wins."),
        ("Engineering builds fixes", "Works the backlog as prioritised",
         "Safety issues (an unseen H2 alert, a gas sensor under-reading) can sit in the pile."),
    ]
    after = [
        ("Reports come in", "Same channels, collected into one feedback file", None,
         "One feed, so nothing depends on who happened to read which email."),
        ("Classify reports", "Category and priority, with a written rationale", "Claude",
         f"Every report triaged on arrival with one rubric. {category_accuracy} categories correct on the test set."),
        ("Merge duplicates", "Reports with one root cause become one issue", "Claude",
         f"{n_items} reports became {n_issues} issues in this run; report counts show how widespread a problem is."),
        ("Draft tickets", "Problem, likely cause, proposed feature, acceptance criteria", "Claude",
         "Engineering-ready first draft that keeps the tag numbers and readings."),
        ("Score and rank", "Missed readings, downtime, false callouts, safety", "Python",
         "Transparent weights; the same estimates always give the same ranking."),
        ("Lead reviews, team builds", "Approves or reorders the ranked backlog", None,
         "People keep the final say and spend their time on fixes, not sorting."),
    ]

    W, top, row_h, box_w, box_h = 1040, 150, 100, 214, 70
    cols = [(24, "Today: manual triage", "Every step is done by hand"),
            (540, "With the feedback agent", "AI does the reading, sorting and drafting; people decide")]
    body = [
        text(24, 38, "Where the agent fits in the plant's feedback process", size=17, weight=600),
        text(24, 60, "Same people, same reports. The agent takes over the reading, sorting and first drafts "
             "between the report and the engineering decision.", cls="t2"),
        f'<line class="grid" x1="{W / 2:.0f}" y1="92" x2="{W / 2:.0f}" y2="{top + len(before) * row_h - 20}" '
        f'stroke-width="1"/>',
    ]
    for x, title, sub in cols:
        body.append(text(x, 108, title, size=15, weight=600))
        body.append(text(x, 127, sub, cls="t3", size=12))

    def step(x, y, title, detail, pill):
        model = pill == "Claude"
        out = [f'<rect class="{"box-model" if model else "box"}" x="{x}" y="{y}" width="{box_w}" '
               f'height="{box_h}" rx="10" stroke-width="1"/>',
               text(x + 12, y + 22, title, size=13, weight=600)]
        for k, line in enumerate(wrap(detail, 32)[:2]):
            out.append(text(x + 12, y + 41 + k * 15, line, cls="t2", size=12))
        if pill:
            pw = 12 + len(pill) * 6.6
            out.append(f'<rect class="{"pill-model" if model else "pill-local"}" x="{x + box_w - pw - 8:.1f}" '
                       f'y="{y + 9}" width="{pw:.1f}" height="17" rx="8.5"/>')
            out.append(text(x + box_w - pw / 2 - 8, y + 21.5, pill, cls="on-pill", size=11, anchor="middle",
                            weight=600))
        return out

    def note(x, y, kind, s):
        cls, glyph, label = ("hurdle", "!", "Hurdle") if kind == "hurdle" else ("gain", "✓", "Gain")
        out = [f'<circle class="{cls}" cx="{x + 9}" cy="{y + 9}" r="9"/>',
               text(x + 9, y + 13.5, glyph, cls="on-pill", size=12, anchor="middle", weight=700),
               text(x + 26, y + 13.5, label, size=12, weight=600)]
        for k, line in enumerate(wrap(s, 36)[:3]):
            out.append(text(x + 26, y + 30 + k * 15, line, cls="t2", size=12))
        return out

    for r in range(len(before)):
        y = top + r * row_h
        for (x, *_), (title, detail, *rest) in zip(cols, (before[r], after[r])):
            pill, msg = (None, rest[0]) if len(rest) == 1 else rest
            body += step(x, y, title, detail, pill)
            body += note(x + box_w + 16, y + 4, "hurdle" if x == cols[0][0] else "gain", msg)
            if r:
                cx = x + box_w / 2
                body.append(f'<line class="arrow" x1="{cx}" y1="{y - row_h + box_h + 3}" x2="{cx}" y2="{y - 8}" '
                            f'stroke-width="1.5"/>')
                body.append(f'<path class="arrowhead" d="M{cx},{y - 2} l-4.5,-7 h9 z"/>')

    H = top + len(before) * row_h + 4
    return svg(W, H, body, 0, "Feedback process before and after the agent",
               "Two side-by-side flowcharts. Left: the manual feedback process and its hurdles at each step. "
               "Right: the same process with the agent classifying, merging, drafting and ranking, and the gain "
               "at each step.")


# --- Figure 1: pipeline -----------------------------------------------------------------

def pipeline_figure(n_items, n_issues):
    W, H = 1040, 330
    body = [
        text(24, 38, "How the agent turns feedback into a backlog", size=17, weight=600),
        text(24, 60, f"Three Claude API steps with JSON-schema outputs, then a deterministic ranking step in Python. "
             f"{n_items + 1 + n_issues} API calls per run.", cls="t2"),
    ]
    nodes = [
        ("feedback.json", f"{n_items} operator and", "technician reports", None),
        ("1 · Classify", "category, priority,", "one-line summary", f"Claude × {n_items}"),
        ("2 · Merge", "duplicates into", f"issues ({n_items} → {n_issues})", "Claude × 1"),
        ("3 · Ticket", "ticket draft +", "4 impact estimates", f"Claude × {n_issues}"),
        ("4 · Rank", "0–100 impact score,", "sorted backlog", "Python"),
        ("backlog.md", "ranked tickets", "+ backlog.json", None),
    ]
    box_w, box_h, gap, top = 146, 104, 26, 96
    x0 = (W - (len(nodes) * box_w + (len(nodes) - 1) * gap)) / 2
    centers = []
    for i, (name, l1, l2, pill) in enumerate(nodes):
        x = x0 + i * (box_w + gap)
        centers.append(x + box_w / 2)
        model = pill is not None and pill.startswith("Claude")
        body.append(f'<rect class="{"box-model" if model else "box"}" x="{x:.1f}" y="{top}" width="{box_w}" '
                    f'height="{box_h}" rx="10" stroke-width="1"/>')
        body.append(text(x + 14, top + 28, name, size=14, weight=600))
        body.append(text(x + 14, top + 52, l1, cls="t2", size=12))
        body.append(text(x + 14, top + 69, l2, cls="t2", size=12))
        if pill:
            pw = 8 + len(pill) * 6.6
            body.append(f'<rect class="{"pill-model" if model else "pill-local"}" x="{x + 14:.1f}" y="{top + 79}" '
                        f'width="{pw:.1f}" height="18" rx="9"/>')
            body.append(text(x + 14 + pw / 2, top + 92, pill, cls="on-pill", size=11, anchor="middle", weight=600))
        if i:
            ax1, ax2, ay = x - gap + 4, x - 6, top + box_h / 2
            body.append(f'<line class="arrow" x1="{ax1:.1f}" y1="{ay}" x2="{ax2:.1f}" y2="{ay}" stroke-width="1.5"/>')
            body.append(f'<path class="arrowhead" d="M{ax2 + 5:.1f},{ay} l-7,-4.5 v9 z"/>')

    # Evaluation branch under step 1.
    ex, ey, ew, eh = centers[1] - box_w / 2, top + box_h + 46, box_w * 2 + gap, 62
    body.append(f'<line class="arrow" x1="{centers[1]:.1f}" y1="{top + box_h + 2}" x2="{centers[1]:.1f}" '
                f'y2="{ey - 7}" stroke-width="1.5" stroke-dasharray="0"/>')
    body.append(f'<path class="arrowhead" d="M{centers[1]:.1f},{ey - 1} l-4.5,-7 h9 z"/>')
    body.append(text(centers[1] + 8, top + box_h + 28, "classifications.json", cls="t3", size=12))
    body.append(f'<rect class="box" x="{ex:.1f}" y="{ey}" width="{ew}" height="{eh}" rx="10" stroke-width="1"/>')
    body.append(text(ex + 14, ey + 26, "eval.py  ← labels.json", size=14, weight=600))
    body.append(text(ex + 14, ey + 46, "category and priority accuracy, confusion matrix", cls="t2", size=12))

    # Legend for the box styles.
    lx, ly = centers[3] - box_w / 2, ey + 14
    body.append(f'<rect class="box-model" x="{lx:.1f}" y="{ly}" width="16" height="12" rx="3" stroke-width="1"/>')
    body.append(text(lx + 24, ly + 11, "Claude API call (structured JSON output)", cls="t2", size=12))
    body.append(f'<rect class="box" x="{lx:.1f}" y="{ly + 22}" width="16" height="12" rx="3" stroke-width="1"/>')
    body.append(text(lx + 24, ly + 33, "File or local Python step", cls="t2", size=12))

    return svg(W, H, body, 0, "Agent pipeline",
               "Feedback flows through classify, merge, ticket and rank steps into a ranked backlog; "
               "classifications also feed the evaluation script.")


# --- Figure 2: items -> issues flow -----------------------------------------------------

def flow_figure(classified, tickets):
    W, unit, group_gap, top = 1040, 20, 16, 104
    cat_index = {c: i for i, c in enumerate(agent.CATEGORIES)}
    pred = {c["id"]: c["category"] for c in classified}

    # Left column: items grouped by predicted category, in the fixed category order.
    items = sorted(pred, key=lambda i: (cat_index[pred[i]], i))
    item_y, y, groups = {}, top, []
    for cat in agent.CATEGORIES:
        ids = [i for i in items if pred[i] == cat]
        if not ids:
            continue
        groups.append((cat, y, len(ids)))
        for i in ids:
            item_y[i] = y
            y += unit
        y += group_gap
    total_h = y - group_gap - top

    # Right column: issues in rank order, each as tall as its number of reports.
    issue_gap = (total_h - len(items) * unit) / max(len(tickets) - 1, 1)
    slot_y, issue_rows, y = {}, [], top
    for rank, t in enumerate(tickets, 1):
        ids = sorted(t["item_ids"], key=lambda i: item_y[i])
        issue_rows.append((rank, t, y, len(ids)))
        for i in ids:
            slot_y[i] = y
            y += unit
        y += issue_gap

    x_item, x_issue, node_w = 250, 650, 10
    body = [
        text(24, 38, f"From {len(items)} feedback items to {len(tickets)} ranked issues", size=17, weight=600),
        text(24, 60, "Each band is one feedback item. Colour is the category Claude assigned; "
             "bands that converge were merged as duplicates.", cls="t2"),
        text(x_item + node_w, top - 18, "Feedback item", cls="t3", size=12, anchor="end", weight=600),
        text(x_issue + node_w + 12, top - 18, "Issue (rank · title)", cls="t3", size=12, weight=600),
        text(W - 24, top - 18, "Impact", cls="t3", size=12, anchor="end", weight=600),
    ]
    for i in items:
        c = cat_index[pred[i]]
        y1, y2 = item_y[i] + 1, slot_y[i] + 1
        x1, x2, h = x_item + node_w, x_issue, unit - 2
        mx = (x1 + x2) / 2
        body.append(
            f'<path class="s{c}" fill-opacity="0.38" d="M{x1},{y1:.1f} C{mx},{y1:.1f} {mx},{y2:.1f} {x2},{y2:.1f} '
            f'V{y2 + h:.1f} C{mx},{y2 + h:.1f} {mx},{y1 + h:.1f} {x1},{y1 + h:.1f} Z"/>'
        )
        body.append(f'<rect class="s{c}" x="{x_item}" y="{y1:.1f}" width="{node_w}" height="{h}" rx="2"/>')
        body.append(text(x_item - 8, item_y[i] + 14, i, cls="t2", size=12, anchor="end"))
    for cat, gy, n in groups:
        c = cat_index[cat]
        cy = gy + n * unit / 2
        body.append(f'<rect class="s{c}" x="24" y="{cy - 12:.1f}" width="10" height="10" rx="2"/>')
        body.append(text(42, cy - 3, CATEGORY_LABELS[cat], size=13, weight=600))
        body.append(text(42, cy + 14, f"{n} item{'s' if n != 1 else ''}", cls="t3", size=12))
    for rank, t, iy, n in issue_rows:
        c = cat_index[t["category"]]
        h = n * unit - 2
        body.append(f'<rect class="s{c}" x="{x_issue}" y="{iy + 1:.1f}" width="{node_w}" height="{h}" rx="2"/>')
        cy = iy + n * unit / 2 + 4.5
        body.append(text(x_issue + node_w + 12, cy, f"{rank}", cls="t3", size=12, weight=600))
        body.append(text(x_issue + node_w + 32, cy, truncate(t["title"], 42), size=13))
        body.append(text(W - 24, cy, f"{t['impact_score']:.1f}", cls="t1 num", size=13, anchor="end", weight=600))

    H = top + total_h + 32
    return svg(W, H, body, len(agent.CATEGORIES), "Feedback items merged into ranked issues",
               "Flow diagram linking each feedback item, coloured by predicted category, to the ranked issue it was "
               "merged into.")


# --- Figure 3: what drives each impact score --------------------------------------------

def impact_figure(tickets):
    W, top, row_h, bar_h = 1040, 124, 34, 20
    x0, x_max = 470, 960
    dims = list(agent.IMPACT_WEIGHTS)
    scale_max = max(10, -(-max(t["impact_score"] for t in tickets) // 10) * 10)
    sx = (x_max - x0) / scale_max

    body = [
        text(24, 38, "What drives each issue's impact score", size=17, weight=600),
        text(24, 60, "Score = weighted sum of four estimates (0–100). Segment length is each dimension's "
             "contribution in points.", cls="t2"),
    ]
    lx = 24
    for k, dim in enumerate(dims):
        label = f"{DIMENSION_LABELS[dim]} ({agent.IMPACT_WEIGHTS[dim]})"
        body.append(f'<rect class="s{k}" x="{lx}" y="{82}" width="12" height="12" rx="3"/>')
        body.append(text(lx + 18, 92.5, label, cls="t2", size=12))
        lx += 30 + len(label) * 6.4

    plot_bottom = top + len(tickets) * row_h - (row_h - bar_h)
    for v in range(0, int(scale_max) + 1, 10):
        x = x0 + v * sx
        body.append(f'<line class="{"axis" if v == 0 else "grid"}" x1="{x:.1f}" y1="{top - 8}" x2="{x:.1f}" '
                    f'y2="{plot_bottom + 8}" stroke-width="1"/>')
        body.append(text(x, plot_bottom + 26, v, cls="t3 num", size=12, anchor="middle"))

    for rank, t in enumerate(tickets, 1):
        y = top + (rank - 1) * row_h
        body.append(text(24, y + 14.5, rank, cls="t3", size=12, weight=600))
        body.append(text(44, y + 14.5, truncate(t["title"], 62), size=13))
        imp = t["impact"]
        parts = [(k, contribution(dim, imp)) for k, dim in enumerate(dims)]
        parts = [(k, v) for k, v in parts if v * sx >= 3]  # slivers under 3px read as artefacts, not data
        x = x0
        for j, (k, v) in enumerate(parts):
            w = v * sx - (2 if j < len(parts) - 1 else 0)  # 2px surface gap between segments
            last = j == len(parts) - 1
            if last:
                body.append(f'<path class="s{k}" d="{bar_path(x, y, max(w, 1), bar_h)}"/>')
            else:
                body.append(f'<rect class="s{k}" x="{x:.1f}" y="{y}" width="{max(w, 1):.1f}" height="{bar_h}"/>')
            x += v * sx
        end = x0 + t["impact_score"] * sx
        body.append(text(end + 8, y + 14.5, f"{t['impact_score']:.1f}", cls="t1 num", size=13, weight=600))

    H = plot_bottom + 48
    return svg(W, H, body, len(dims), "Impact score breakdown by issue",
               "Stacked horizontal bars showing how worker safety, downtime risk, missed measurements and false "
               "alarms contribute to each ranked issue's impact score.")


# --- Figure 4: systems and the data boundary --------------------------------------------

def integration_figure():
    W, H = 1040, 500
    body = [
        text(24, 38, "How it plugs into the plant's systems", size=17, weight=600),
        text(24, 60, "Reports are pulled read-only and stripped of personal data on the plant side. Only redacted "
             "text crosses to the Claude API.", cls="t2"),
        '<rect class="boundary" x="24" y="84" width="992" height="250" rx="12" stroke-width="1.5" '
        'stroke-dasharray="6 5"/>',
        text(40, 106, "Ridgeview IT network (plant side)", cls="t3", size=12, weight=600),
    ]

    def box(x, y, w, h, title, lines, pill=None):
        model = pill == "Claude"
        out = [f'<rect class="{"box-model" if model else "box"}" x="{x}" y="{y}" width="{w}" height="{h}" rx="10" '
               f'stroke-width="1"/>', text(x + 12, y + 22, title, size=13, weight=600)]
        out += [text(x + 12, y + 40 + k * 15, line, cls="t2", size=12) for k, line in enumerate(lines)]
        if pill:
            pw = 12 + len(pill) * 6.6
            out.append(f'<rect class="{"pill-model" if model else "pill-local"}" x="{x + w - pw - 8:.1f}" '
                       f'y="{y + 9}" width="{pw:.1f}" height="17" rx="8.5"/>')
            out.append(text(x + w - pw / 2 - 8, y + 21.5, pill, cls="on-pill", size=11, anchor="middle", weight=600))
        return out

    def arrow(d, tip, direction):
        dx, dy = {"right": (-7, -4.5), "down": (-4.5, -7), "up": (-4.5, 7)}[direction]
        head = (f"M{tip[0]},{tip[1]} l{dx},{dy} v9 z" if direction == "right"
                else f"M{tip[0]},{tip[1]} l{dx},{dy} h9 z")
        return [f'<path class="arrow" d="{d}" stroke-width="1.5"/>', f'<path class="arrowhead" d="{head}"/>']

    sources = [("IBM Maximo", "service requests"), ("Microsoft Teams", "#spot-robot channel"),
               ("Shift log (eLogbook)", "control room entries")]
    for k, (title, sub) in enumerate(sources):
        y = 124 + k * 64
        body += box(44, y, 200, 48, title, [sub])
        body += arrow(f"M244,{y + 24} L{288 - 6},205", (288, 205), "right") if k == 1 else \
            [f'<path class="arrow" d="M244,{y + 24} L282,205" stroke-width="1.5"/>']
    body += box(290, 150, 190, 110, "ingest.py", ["read-only pull", "names → job roles", "redact emails, phones,",
                                                  "badge IDs"], "Python")
    body += arrow("M480,205 H518", (524, 205), "right")
    body += box(526, 150, 190, 110, "agent.py", ["classify, merge,", "draft tickets, rank,", "map to site KPIs"],
                "Claude")
    body += arrow("M716,205 H740 V159 H750", (756, 159), "right")
    body += arrow("M740,205 V249 H750", (756, 249), "right")
    body += box(762, 124, 234, 70, "backlog.md + charts", ["for operations, reliability", "and plant management"])
    body += box(762, 214, 234, 70, "publish_jira.py", ["preview first; --apply creates", "tickets, skips duplicates"],
                "Python")

    body += box(526, 384, 190, 56, "Claude API", ["Anthropic, over HTTPS"])
    body += box(762, 384, 234, 56, "Jira Cloud", ["ROBO project, robotics team"])
    body += arrow("M604,262 V376", (604, 382), "down")
    body += arrow("M640,382 V268", (640, 262), "up")
    body += [text(594, 352, "sends: redacted text,", cls="t2", size=12, anchor="end"),
             text(594, 367, "role, shift, mission", cls="t2", size=12, anchor="end"),
             text(650, 300, "returns:", cls="t2", size=12), text(650, 315, "JSON only", cls="t2", size=12)]
    body += arrow("M879,286 V376", (879, 382), "down")
    body += [text(871, 352, "tickets with report IDs,", cls="t2", size=12, anchor="end"),
             text(871, 367, "no names", cls="t2", size=12, anchor="end")]
    body.append(text(24, 476, "Stays on the plant side: names, emails, phone numbers, badge IDs, the staff roster and "
                     "the audit log (hashes and token counts, no content).", cls="t2", size=12))
    return svg(W, H, body, 0, "Systems and data boundary",
               "Maximo, Teams and the shift log feed ingest.py, which redacts personal data inside the plant network. "
               "agent.py sends only redacted text to the Claude API and receives JSON. Outputs go to a backlog "
               "report for managers and, after preview and approval, to Jira Cloud.")


# --- Figure 5: issues mapped to site KPIs -----------------------------------------------

KPI_SHORT = {
    "availability": ["Plant", "availability"],
    "revenue_at_risk": ["Revenue", "at risk"],
    "inspection_coverage": ["Inspection", "coverage"],
    "maintenance_cost": ["Maintenance", "cost"],
    "worker_safety": ["Worker", "safety"],
    "environmental_compliance": ["Emissions", "compliance"],
    "alarm_response": ["Alarm", "response"],
}


def outcomes_figure(tickets):
    W, top, row_h = 1040, 150, 34
    x_col0, col_w = 450, 81
    kpis = list(agent.SITE_KPIS)
    body = [
        text(24, 38, "Which site KPIs each fix improves", size=17, weight=600),
        text(24, 60, "Rows are backlog issues in rank order. A filled dot is the main KPI the fix moves; a ring is "
             "a secondary one.", cls="t2"),
        f'<circle class="s0" cx="30" cy="84" r="6"/>', text(42, 88.5, "Main outcome", cls="t2", size=12),
        f'<circle class="b0" cx="150" cy="84" r="5" fill="none" stroke-width="2"/>',
        text(162, 88.5, "Secondary outcome", cls="t2", size=12),
    ]
    for c, kpi in enumerate(kpis):
        cx = x_col0 + c * col_w + col_w / 2
        for k, line in enumerate(KPI_SHORT[kpi]):
            body.append(text(cx, top - 26 + k * 14, line, cls="t2", size=11.5, anchor="middle", weight=600))
    bottom = top + len(tickets) * row_h
    for r, t in enumerate(tickets):
        y = top + r * row_h
        cy = y + row_h / 2
        body.append(f'<line class="grid" x1="20" y1="{y + row_h}" x2="{W - 20}" y2="{y + row_h}" stroke-width="1"/>')
        body.append(text(24, cy + 4.5, r + 1, cls="t3", size=12, weight=600))
        body.append(text(44, cy + 4.5, truncate(t["title"], 56), size=13))
        for k, o in enumerate(t["business_outcomes"]):
            cx = x_col0 + kpis.index(o["kpi"]) * col_w + col_w / 2
            body.append(f'<circle class="s0" cx="{cx}" cy="{cy}" r="7"/>' if k == 0 else
                        f'<circle class="b0" cx="{cx}" cy="{cy}" r="5.5" fill="none" stroke-width="2"/>')
    for c, kpi in enumerate(kpis):
        n = sum(any(o["kpi"] == kpi for o in t["business_outcomes"]) for t in tickets)
        body.append(text(x_col0 + c * col_w + col_w / 2, bottom + 22, f"{n} fix{'es' if n != 1 else ''}",
                         cls="t3 num", size=12, anchor="middle"))
    return svg(W, bottom + 40, body, 1, "Backlog issues mapped to site KPIs",
               "Matrix of ranked backlog issues against seven site KPIs, marking the main and secondary KPI each fix "
               "would improve.")


def contribution(dim, impact):
    """Points a single dimension adds to the impact score (mirrors agent.impact_score)."""
    weight = agent.IMPACT_WEIGHTS[dim]
    value = impact[dim]
    if dim in ("worker_safety_exposure", "downtime_risk"):
        return weight * (value - 1) / 4
    cap = agent.MISSED_POINTS_CAP if dim == "missed_measurement_points_per_week" else agent.FALSE_ALARM_CAP
    return weight * min(max(value, 0), cap) / cap


def main():
    tickets = json.loads((agent.OUT_DIR / "backlog.json").read_text())
    classified = json.loads((agent.OUT_DIR / "classifications.json").read_text())
    labels = json.loads((agent.DATA_DIR / "labels.json").read_text())
    correct = sum(c["category"] == labels[c["id"]]["category"] for c in classified)
    DOCS_DIR.mkdir(exist_ok=True)
    figures = {
        "process.svg": process_figure(len(classified), len(tickets), f"{correct}/{len(classified)}"),
        "pipeline.svg": pipeline_figure(len(classified), len(tickets)),
        "flow.svg": flow_figure(classified, tickets),
        "impact.svg": impact_figure(tickets),
        "outcomes.svg": outcomes_figure(tickets),
        "integration.svg": integration_figure(),
    }
    for name, content in figures.items():
        (DOCS_DIR / name).write_text(content)
        print(f"Wrote {DOCS_DIR / name}")


if __name__ == "__main__":
    main()
