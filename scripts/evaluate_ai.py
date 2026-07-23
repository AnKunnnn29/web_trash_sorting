#!/usr/bin/env python3
"""Run a deterministic smoke benchmark against the current SavedModel.

The repository dataset may overlap with training data, so this report is useful
for regression detection only. Use a separate unseen dataset for release metrics.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = BASE_DIR / "saved_model_keras"
DEFAULT_DATASET = BASE_DIR / "dataset"
DEFAULT_MAPPING = BASE_DIR / "config" / "dataset-labels.json"
DEFAULT_LABELS = BASE_DIR / "public" / "tfjs_model" / "labels.json"
DEFAULT_JSON_REPORT = BASE_DIR / "reports" / "ai-baseline.json"
DEFAULT_MD_REPORT = BASE_DIR / "reports" / "ai-baseline.md"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    parser.add_argument(
        "--provenance",
        type=Path,
        default=None,
        help="Evaluate approved dataset_file records from a JSONL provenance manifest.",
    )
    parser.add_argument("--samples-per-label", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--threshold", type=float, default=0.45)
    parser.add_argument("--seed", type=int, default=20260723)
    parser.add_argument("--json-report", type=Path, default=DEFAULT_JSON_REPORT)
    parser.add_argument("--markdown-report", type=Path, default=DEFAULT_MD_REPORT)
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def collect_samples(
    dataset_dir: Path,
    mapping: dict[str, str],
    samples_per_label: int,
    seed: int,
) -> list[tuple[Path, str]]:
    grouped: dict[str, list[Path]] = defaultdict(list)
    for folder_name, expected_label in mapping.items():
        folder = dataset_dir / folder_name
        if not folder.is_dir():
            continue
        grouped[expected_label].extend(
            path
            for path in folder.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )

    rng = random.Random(seed)
    samples: list[tuple[Path, str]] = []
    for label in sorted(grouped):
        paths = sorted(grouped[label])
        rng.shuffle(paths)
        samples.extend((path, label) for path in paths[:samples_per_label])
    return samples


def collect_provenance_samples(
    provenance_path: Path,
    mapping: dict[str, str],
) -> list[tuple[Path, str]]:
    samples = []
    for line in provenance_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("review_status") != "approved" or not record.get("dataset_file"):
            continue
        group = record.get("group")
        expected = mapping.get(group)
        if not expected:
            continue
        samples.append((BASE_DIR / record["dataset_file"], expected))
    return samples


def load_image(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        image = image.convert("RGB").resize((224, 224), Image.BILINEAR)
        return np.asarray(image, dtype=np.float32)


def safe_div(numerator: int | float, denominator: int | float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def evaluate(args: argparse.Namespace) -> dict:
    try:
        import tensorflow as tf
    except ImportError as error:
        raise SystemExit(
            "TensorFlow is unavailable. Run with the project Python 3.7 environment: "
            "py -3.7 scripts/evaluate_ai.py"
        ) from error

    mapping = load_json(args.mapping)
    labels = load_json(args.labels)
    samples = (
        collect_provenance_samples(args.provenance, mapping)
        if args.provenance
        else collect_samples(
            args.dataset,
            mapping,
            max(1, args.samples_per_label),
            args.seed,
        )
    )
    if not samples:
        raise SystemExit(f"No evaluation images found in {args.dataset}")

    loaded = tf.saved_model.load(str(args.model))
    inference = loaded.signatures["serving_default"]
    input_name = next(iter(inference.structured_input_signature[1]))
    output_name = next(iter(inference.structured_outputs))

    records = []
    skipped = []
    for batch_start in range(0, len(samples), args.batch_size):
        batch_samples = samples[batch_start:batch_start + args.batch_size]
        arrays = []
        valid_samples = []
        for path, expected in batch_samples:
            try:
                arrays.append(load_image(path))
                valid_samples.append((path, expected))
            except Exception as error:  # corrupt or unsupported image
                skipped.append({"path": str(path), "error": str(error)})
        if not arrays:
            continue

        batch = tf.convert_to_tensor(np.stack(arrays), dtype=tf.float32)
        probabilities = inference(**{input_name: batch})[output_name].numpy()
        for (path, expected), scores in zip(valid_samples, probabilities):
            best_index = int(np.argmax(scores))
            confidence = float(scores[best_index])
            predicted = labels[best_index]
            records.append({
                "path": str(path.relative_to(BASE_DIR)),
                "expected": expected,
                "predicted": predicted,
                "confidence": confidence,
                "accepted": confidence >= args.threshold,
                "correct": predicted == expected,
            })

    expected_counts = Counter(record["expected"] for record in records)
    predicted_counts = Counter(record["predicted"] for record in records)
    true_positive = Counter(
        record["expected"] for record in records if record["correct"]
    )
    per_label = {}
    for label in labels:
        tp = true_positive[label]
        precision = safe_div(tp, predicted_counts[label])
        recall = safe_div(tp, expected_counts[label])
        f1 = safe_div(2 * precision * recall, precision + recall)
        per_label[label] = {
            "samples": expected_counts[label],
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    accepted = [record for record in records if record["accepted"]]
    correct = sum(record["correct"] for record in records)
    accepted_correct = sum(record["correct"] for record in accepted)
    evaluated_labels = [label for label in labels if expected_counts[label]]
    confusion = Counter(
        (record["expected"], record["predicted"])
        for record in records
        if not record["correct"]
    )

    provenance_note = (
        "Images are newly collected, manually approved product images from the "
        "provenance manifest. They were not added until after the baseline model "
        "was trained, but are not a substitute for an independent camera test set."
    )
    dataset_note = (
        "Images come from the repository dataset and may overlap training data. "
        "Do not treat these metrics as independent release accuracy."
    )
    return {
        "report_type": "provenance_benchmark" if args.provenance else "smoke_benchmark",
        "data_note": provenance_note if args.provenance else dataset_note,
        "model_path": str(args.model.relative_to(BASE_DIR)),
        "labels_path": str(args.labels.relative_to(BASE_DIR)),
        "seed": args.seed,
        "threshold": args.threshold,
        "samples_per_label": None if args.provenance else args.samples_per_label,
        "sample_count": len(records),
        "skipped_count": len(skipped),
        "accuracy": safe_div(correct, len(records)),
        "coverage": safe_div(len(accepted), len(records)),
        "accepted_accuracy": safe_div(accepted_correct, len(accepted)),
        "average_confidence": safe_div(
            sum(record["confidence"] for record in records),
            len(records),
        ),
        "macro_f1": safe_div(
            sum(per_label[label]["f1"] for label in evaluated_labels),
            len(evaluated_labels),
        ),
        "per_label": per_label,
        "top_confusions": [
            {"expected": pair[0], "predicted": pair[1], "count": count}
            for pair, count in confusion.most_common(15)
        ],
        "skipped": skipped,
        "records": records,
    }


def write_reports(report: dict, json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# AI baseline smoke benchmark",
        "",
        f"> {report['data_note']}",
        "",
        f"- Samples: {report['sample_count']}",
        f"- Top-1 accuracy: {report['accuracy']:.1%}",
        f"- Macro F1: {report['macro_f1']:.1%}",
        f"- Coverage at threshold {report['threshold']:.0%}: {report['coverage']:.1%}",
        f"- Accuracy among accepted predictions: {report['accepted_accuracy']:.1%}",
        f"- Average confidence: {report['average_confidence']:.1%}",
        "",
        "## Per-label metrics",
        "",
        "| Label | Samples | Precision | Recall | F1 |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, metrics in report["per_label"].items():
        lines.append(
            f"| {label} | {metrics['samples']} | {metrics['precision']:.1%} "
            f"| {metrics['recall']:.1%} | {metrics['f1']:.1%} |"
        )

    lines.extend(["", "## Most common confusions", ""])
    if report["top_confusions"]:
        lines.extend([
            "| Expected | Predicted | Count |",
            "|---|---|---:|",
        ])
        for item in report["top_confusions"]:
            lines.append(
                f"| {item['expected']} | {item['predicted']} | {item['count']} |"
            )
    else:
        lines.append("No incorrect predictions in this sample.")

    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args()
    report = evaluate(args)
    write_reports(report, args.json_report, args.markdown_report)
    print(
        "AI smoke benchmark complete: "
        f"accuracy={report['accuracy']:.1%}, "
        f"macro_f1={report['macro_f1']:.1%}, "
        f"coverage={report['coverage']:.1%}, "
        f"samples={report['sample_count']}"
    )
    print(f"Markdown report: {args.markdown_report}")
    print(f"JSON report: {args.json_report}")


if __name__ == "__main__":
    main()
