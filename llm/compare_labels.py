import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def main():
    folder = Path(__file__).parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--predicted", default="ollama_100_results.json")
    parser.add_argument("--report", default="comparison_report.json")
    args = parser.parse_args()
    labeled = json.loads((folder / "labeled_notices.json").read_text(encoding="utf-8"))
    predicted = json.loads((folder / args.predicted).read_text(encoding="utf-8"))
    expected = {item["post_no"]: item["category"] for item in labeled}
    actual = {item["post_no"]: item["category"] for item in predicted}
    ids = sorted(expected.keys() & actual.keys())
    correct = sum(expected[post_no] == actual[post_no] for post_no in ids)
    category_totals = Counter(expected[post_no] for post_no in ids)
    category_correct = Counter(
        expected[post_no] for post_no in ids if expected[post_no] == actual[post_no]
    )
    confusion = defaultdict(Counter)
    mismatches = []
    titles = {item["post_no"]: item["title"] for item in labeled}
    for post_no in ids:
        truth = expected[post_no]
        guess = actual[post_no]
        confusion[truth][guess] += 1
        if truth != guess:
            mismatches.append(
                {
                    "post_no": post_no,
                    "title": titles[post_no],
                    "expected": truth,
                    "predicted": guess,
                }
            )
    report = {
        "labeled_count": len(labeled),
        "predicted_count": len(predicted),
        "compared_count": len(ids),
        "correct_count": correct,
        "accuracy": round(correct / len(ids), 4) if ids else 0,
        "category_recall": {
            category: {
                "correct": category_correct[category],
                "total": total,
                "recall": round(category_correct[category] / total, 4),
            }
            for category, total in sorted(category_totals.items())
        },
        "confusion": {truth: dict(guesses) for truth, guesses in confusion.items()},
        "mismatches": mismatches,
    }
    (folder / args.report).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"정확도: {correct}/{len(ids)} ({report['accuracy']:.1%})")
    for mismatch in mismatches:
        print(
            f"{mismatch['post_no']} | 정답: {mismatch['expected']} | "
            f"모델: {mismatch['predicted']} | {mismatch['title']}"
        )


if __name__ == "__main__":
    main()
