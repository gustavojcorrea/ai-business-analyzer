"""Score the agent's category and priority predictions against data/labels.json.

Usage:
  python eval.py                                   # classify all items now (calls the API), then score
  python eval.py --predictions output/classifications.json   # score an earlier run, no API calls
  python eval.py --write-appendix                  # also replace the results block in appendix/evaluation.md
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import agent

LABELS_PATH = agent.DATA_DIR / "labels.json"
RESULTS_DOC = agent.ROOT / "appendix" / "evaluation.md"
RESULTS_BLOCK = re.compile(r"(<!-- EVAL:START -->\n).*?(<!-- EVAL:END -->)", re.DOTALL)


def score(predictions, labels):
    preds = {p["id"]: p for p in predictions}
    missing = sorted(set(labels) - set(preds))
    if missing:
        sys.exit(f"Predictions are missing ids: {', '.join(missing)}")

    n = len(labels)
    cat_ok = {i: preds[i]["category"] == labels[i]["category"] for i in labels}
    pri_ok = {i: preds[i]["priority"] == labels[i]["priority"] for i in labels}
    pri_near = {i: abs(preds[i]["priority"] - labels[i]["priority"]) <= 1 for i in labels}

    per_category = {}
    for cat in agent.CATEGORIES:
        ids = [i for i in labels if labels[i]["category"] == cat]
        predicted = [i for i in labels if preds[i]["category"] == cat]
        correct = sum(cat_ok[i] for i in ids)
        per_category[cat] = {
            "support": len(ids),
            "recall": correct / len(ids) if ids else None,
            "precision": correct / len(predicted) if predicted else None,
        }

    return {
        "n": n,
        "category_accuracy": sum(cat_ok.values()) / n,
        "priority_accuracy": sum(pri_ok.values()) / n,
        "priority_within_1": sum(pri_near.values()) / n,
        "both_correct": sum(cat_ok[i] and pri_ok[i] for i in labels) / n,
        "per_category": per_category,
        "confusion": Counter((labels[i]["category"], preds[i]["category"]) for i in labels),
        "errors": [
            {
                "id": i,
                "label": f"{labels[i]['category']} P{labels[i]['priority']}",
                "predicted": f"{preds[i]['category']} P{preds[i]['priority']}",
                "rationale": preds[i].get("rationale", ""),
            }
            for i in sorted(labels)
            if not (cat_ok[i] and pri_ok[i])
        ],
    }


def pct(x):
    return "n/a" if x is None else f"{x:.0%}"


def render(results):
    r = results
    lines = [
        f"| Metric | Score |",
        f"|---|---:|",
        f"| Category accuracy | **{pct(r['category_accuracy'])}** ({round(r['category_accuracy'] * r['n'])}/{r['n']}) |",
        f"| Priority accuracy (exact) | **{pct(r['priority_accuracy'])}** ({round(r['priority_accuracy'] * r['n'])}/{r['n']}) |",
        f"| Priority within ±1 | {pct(r['priority_within_1'])} |",
        f"| Category and priority both correct | {pct(r['both_correct'])} |",
        "",
        "| Category | Support | Precision | Recall |",
        "|---|---:|---:|---:|",
        *[
            f"| {cat} | {m['support']} | {pct(m['precision'])} | {pct(m['recall'])} |"
            for cat, m in r["per_category"].items()
        ],
        "",
    ]
    if r["errors"]:
        lines += ["| Item | Label | Predicted | Model rationale |", "|---|---|---|---|"]
        lines += [f"| {e['id']} | {e['label']} | {e['predicted']} | {e['rationale']} |" for e in r["errors"]]
    else:
        lines.append("No misclassified items.")
    lines += ["", f"_Model: {agent.MODEL}, effort: {agent.EFFORT}._"]
    return "\n".join(lines) + "\n"


def print_confusion(confusion):
    cats = agent.CATEGORIES
    width = max(len(c) for c in cats) + 2
    print("Confusion matrix (rows = label, columns = predicted):")
    print(" " * width + "".join(f"{c[:8]:>10}" for c in cats))
    for actual in cats:
        print(f"{actual:<{width}}" + "".join(f"{confusion.get((actual, p), 0):>10}" for p in cats))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--predictions", type=Path, help="score this classifications.json instead of calling the API")
    parser.add_argument("--write-appendix", action="store_true", help="write the results into appendix/evaluation.md")
    args = parser.parse_args()

    labels = json.loads(LABELS_PATH.read_text())
    if args.predictions:
        predictions = json.loads(args.predictions.read_text())
    else:
        client = agent.make_client()
        agent.AUDIT.write("run_start", kind="eval", input="data/feedback.json", items=len(labels), model=agent.MODEL)
        print(f"Classifying {len(labels)} items with {agent.MODEL}...", file=sys.stderr)
        predictions = agent.classify_all(client, agent.load_feedback())
        agent.OUT_DIR.mkdir(exist_ok=True)
        agent.write_json(agent.OUT_DIR / "classifications.json", predictions)

    results = score(predictions, labels)
    report = render(results)
    print(report)
    print_confusion(results["confusion"])

    if args.write_appendix:
        doc = RESULTS_DOC.read_text()
        if not RESULTS_BLOCK.search(doc):
            sys.exit(f"{RESULTS_DOC} has no <!-- EVAL:START --> / <!-- EVAL:END --> block")
        RESULTS_DOC.write_text(RESULTS_BLOCK.sub(lambda m: m.group(1) + report + m.group(2), doc))
        print(f"\nUpdated {RESULTS_DOC}", file=sys.stderr)


if __name__ == "__main__":
    main()
