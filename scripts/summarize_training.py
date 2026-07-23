#!/usr/bin/env python3
"""Summarize candidate experiments and enforce the model replacement gate."""

from __future__ import annotations

import json
import hashlib
import statistics
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
MODEL_ROOT = BASE_DIR / "model_candidates"
BASELINE_PATH = BASE_DIR / "reports" / "baseline-clean-split-current.json"
SPLIT_PATH = BASE_DIR / "reports" / "training-split.csv"
OUTPUT_PATH = BASE_DIR / "reports" / "training-candidate-summary.md"
CRITICAL_LABELS = [
    "milk_carton", "bottle", "bread", "wipe", "pen", "plastic_bag", "styrofoam"
]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def mean(records: list[dict], getter) -> float:
    return statistics.mean(getter(record) for record in records)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    baseline = load(BASELINE_PATH)
    split_hash = file_sha256(SPLIT_PATH)
    candidate_paths = sorted(MODEL_ROOT.glob("e4-seed-*/metrics.json"))
    e4 = [
        record for record in (load(path) for path in candidate_paths)
        if record.get("split_sha256") == split_hash
    ]
    if not e4:
        raise SystemExit(
            "No E4 candidate was trained/evaluated on the current split. "
            "Run training before summarizing."
        )
    macro_values = [record["test"]["macro_f1"] for record in e4]
    external_values = [record["external_test"]["accuracy"] for record in e4]
    macro_mean = statistics.mean(macro_values)
    macro_std = statistics.pstdev(macro_values)
    external_mean = statistics.mean(external_values)
    external_std = statistics.pstdev(external_values)

    gate = {
        "three_current_split_seeds": len(e4) >= 3,
        "accuracy_not_below_baseline": (
            mean(e4, lambda record: record["test"]["accuracy"])
            >= baseline["test"]["accuracy"]
        ),
        "macro_f1_not_below_baseline": (
            macro_mean >= baseline["test"]["macro_f1"]
        ),
        "macro_f1_std_le_2pp": macro_std <= 0.02,
        "external_milk_recall_ge_75": external_mean >= 0.75,
        "external_accepted_accuracy_ge_90": mean(
            e4, lambda record: record["external_test"]["accepted_accuracy"]
        ) >= 0.90,
        "external_coverage_ge_60": mean(
            e4, lambda record: record["external_test"]["coverage_at_45"]
        ) >= 0.60,
        "external_std_le_2pp": external_std <= 0.02,
        "milk_carton_f1_not_below_baseline": mean(
            e4, lambda record: record["test"]["per_label"]["milk_carton"]["f1"]
        ) >= baseline["test"]["per_label"]["milk_carton"]["f1"],
    }
    replace_model = all(gate.values())
    lines = [
        "# Candidate training summary",
        "",
        f"- Decision: **{'REPLACE baseline' if replace_model else 'KEEP baseline'}**",
        "- Scope: local data/model work only; no hardware or deployment.",
        "",
        "## Experiment comparison",
        "",
        "| Model | Seeds | Test accuracy | Test macro F1 | External milk recall |",
        "| --- | ---: | ---: | ---: | ---: |",
        f"| Current-split baseline | 1 | {percent(baseline['test']['accuracy'])} | "
        f"{percent(baseline['test']['macro_f1'])} | "
        f"{percent(baseline['external_test']['accuracy'])} |",
        f"| E4: L2 + Dropout 0.3 + smoothing 0.05 | {len(e4)} | "
        f"{percent(mean(e4, lambda r: r['test']['accuracy']))} | "
        f"{percent(macro_mean)} ± {percent(macro_std)} | "
        f"{percent(external_mean)} ± {percent(external_std)} |",
        "",
        "## E4 seeds",
        "",
        "| Seed | Test accuracy | Macro F1 | External milk recall |",
        "| ---: | ---: | ---: | ---: |",
    ]
    for record in e4:
        lines.append(
            f"| {record['seed']} | {percent(record['test']['accuracy'])} | "
            f"{percent(record['test']['macro_f1'])} | "
            f"{percent(record['external_test']['accuracy'])} |"
        )
    lines.extend([
        "",
        "## Mean recall for critical labels (E4)",
        "",
        "| Label | Recall |",
        "| --- | ---: |",
    ])
    for label in CRITICAL_LABELS:
        value = mean(
            e4, lambda record, current=label:
            record["test"]["per_label"][current]["recall"]
        )
        lines.append(f"| {label} | {percent(value)} |")
    lines.extend([
        "",
        "## Quality gate",
        "",
        "| Gate | Result |",
        "| --- | --- |",
    ])
    for name, passed in gate.items():
        lines.append(f"| {name} | {'PASS' if passed else 'FAIL'} |")
    lines.extend([
        "",
        f"Only metrics matching current split SHA-256 `{split_hash}` are included. "
        "The baseline internal-test score remains a regression reference because the "
        "old model may have seen some source images. The 15 boxed-milk images, brand "
        "smoke holdout, hard negatives and real-camera holdout are separate gates.",
        "",
        "No production model files are replaced when any mandatory gate fails.",
        "",
    ])
    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"replace_model={replace_model}")
    print(f"report={OUTPUT_PATH}")


if __name__ == "__main__":
    main()
