#!/usr/bin/env python3
"""Fail-fast data readiness gate that must pass before candidate training."""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
SPLIT = BASE_DIR / "reports" / "training-split.csv"
HARD_NEGATIVES = BASE_DIR / "reports" / "milk-carton-hard-negatives.csv"
BRAND_HOLDOUT = BASE_DIR / "reports" / "brand-holdout.csv"
PROVENANCE_DIR = BASE_DIR / "data_provenance"
REAL_CAMERA = BASE_DIR / "evaluation" / "real_camera_holdout"
OUTPUT_JSON = BASE_DIR / "reports" / "pretraining-readiness.json"
OUTPUT_MD = BASE_DIR / "reports" / "pretraining-readiness.md"
EXPECTED_BRANDS = {"kun": 3, "lof": 3, "milo": 4}
HARD_NEGATIVE_LABELS = {
    "battery", "bottle", "cardboard", "leaf", "newspaper", "plastic_bag",
    "shampoo_bottle", "soda_can",
}


def add(results: list[dict], name: str, status: str, detail: str) -> None:
    results.append({"check": name, "status": status, "detail": detail})


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def main() -> int:
    results = []
    rows = read_csv(SPLIT)
    split_counts = Counter(row["split"] for row in rows)
    label_splits = Counter((row["label"], row["split"]) for row in rows)

    for field in ("group_id", "sha256", "dhash"):
        splits = defaultdict(set)
        for row in rows:
            splits[row[field]].add(row["split"])
        conflicts = sum(len(values) > 1 for values in splits.values())
        add(
            results,
            f"{field} leakage",
            "PASS" if conflicts == 0 else "FAIL",
            f"{conflicts} values cross splits",
        )

    labels = sorted({row["label"] for row in rows})
    low_train = {
        label: label_splits[(label, "train")]
        for label in labels if label_splits[(label, "train")] < 15
    }
    low_eval = {
        label: (
            label_splits[(label, "validation")],
            label_splits[(label, "test")],
        )
        for label in labels
        if min(
            label_splits[(label, "validation")],
            label_splits[(label, "test")],
        ) < 4
    }
    add(
        results,
        "minimum train support",
        "PASS" if not low_train else "FAIL",
        f"{len(labels)} labels; below 15: {low_train or 'none'}",
    )
    sparse_train = {
        label: label_splits[(label, "train")]
        for label in labels if label_splits[(label, "train")] < 30
    }
    add(
        results,
        "sparse train labels",
        "WARN" if sparse_train else "PASS",
        f"below 30 clean sources: {sparse_train or 'none'}",
    )
    add(
        results,
        "minimum validation/test support",
        "PASS" if not low_eval else "FAIL",
        f"below 4: {low_eval or 'none'}",
    )
    milk_counts = {
        split: label_splits[("milk_carton", split)]
        for split in ("train", "validation", "test", "external_test")
    }
    milk_ok = (
        milk_counts["train"] >= 150
        and milk_counts["validation"] >= 30
        and milk_counts["test"] >= 30
        and milk_counts["external_test"] >= 15
    )
    add(results, "milk_carton support", "PASS" if milk_ok else "FAIL", str(milk_counts))

    hard_rows = read_csv(HARD_NEGATIVES)
    hard_counts = Counter(row["label"] for row in hard_rows)
    missing_hard = {
        label: hard_counts[label]
        for label in HARD_NEGATIVE_LABELS if hard_counts[label] < 10
    }
    add(
        results,
        "hard-negative holdout",
        "PASS" if not missing_hard else "FAIL",
        f"{len(hard_rows)} images; below 10: {missing_hard or 'none'}",
    )

    brand_rows = read_csv(BRAND_HOLDOUT)
    brand_counts = Counter(row["brand"].lower() for row in brand_rows)
    missing_brands = {
        brand: f"{brand_counts[brand]}/{minimum}"
        for brand, minimum in EXPECTED_BRANDS.items()
        if brand_counts[brand] < minimum
    }
    training_hashes = {row["sha256"] for row in rows if row["split"] == "train"}
    brand_overlap = sum(row["sha256"] in training_hashes for row in brand_rows)
    brand_ok = not missing_brands and brand_overlap == 0
    add(
        results,
        "brand smoke holdout",
        "PASS" if brand_ok else "FAIL",
        f"counts={dict(brand_counts)}, train overlap={brand_overlap}",
    )

    provenance_files = set()
    pending_promoted = []
    for manifest in PROVENANCE_DIR.glob("*.jsonl"):
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            dataset_file = record.get("dataset_file")
            if dataset_file:
                provenance_files.add(dataset_file.replace("\\", "/"))
                if record.get("review_status") in {"pending", "pending_object_review"}:
                    pending_promoted.append(dataset_file)
    sourced_files = {
        path.relative_to(BASE_DIR).as_posix()
        for path in (BASE_DIR / "dataset").glob("*/*")
        if path.name.startswith(("off_", "open_"))
    }
    missing_provenance = sorted(sourced_files - provenance_files)
    provenance_ok = not missing_provenance and not pending_promoted
    add(
        results,
        "provenance and review state",
        "PASS" if provenance_ok else "FAIL",
        f"sourced files without provenance={len(missing_provenance)}, "
        f"pending promoted={len(pending_promoted)}",
    )

    orphan_count = 0
    structured_manifest = (
        PROVENANCE_DIR / "openfoodfacts-milk-carton-structured.jsonl"
    )
    if structured_manifest.exists():
        codes = {
            str(json.loads(line)["code"])
            for line in structured_manifest.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        review_dir = BASE_DIR / "dataset_review" / "milk_carton_structured"
        for path in review_dir.glob("off_*"):
            match = re.match(r"off_([^_]+)_", path.name)
            if match and match.group(1) not in codes:
                orphan_count += 1
    add(
        results,
        "review download orphans",
        "WARN" if orphan_count else "PASS",
        f"{orphan_count} untracked review-only files; excluded from dataset",
    )

    real_images = [
        path for path in REAL_CAMERA.rglob("*")
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}
    ] if REAL_CAMERA.exists() else []
    add(
        results,
        "real-camera external holdout",
        "PASS" if len(real_images) >= 30 else "WARN",
        f"{len(real_images)}/30 images; required before production promotion",
    )

    failures = [item for item in results if item["status"] == "FAIL"]
    warnings = [item for item in results if item["status"] == "WARN"]
    payload = {
        "ready_for_experimental_training": not failures,
        "ready_for_production_promotion": not failures and not warnings,
        "split_counts": dict(split_counts),
        "checks": results,
    }
    OUTPUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# Pre-training readiness",
        "",
        f"- Experimental training: {'READY' if not failures else 'BLOCKED'}",
        "- Production promotion: "
        + ("READY" if not failures and not warnings else "BLOCKED"),
        f"- Failures: {len(failures)}",
        f"- Warnings: {len(warnings)}",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    lines.extend(
        f"| {item['check']} | {item['status']} | {item['detail']} |"
        for item in results
    )
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
