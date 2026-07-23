#!/usr/bin/env python3
"""Build fixed hard-negative and brand holdout manifests before training."""

import csv
import hashlib
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
SPLIT = BASE_DIR / "reports" / "training-split.csv"
HARD_NEGATIVE_OUTPUT = BASE_DIR / "reports" / "milk-carton-hard-negatives.csv"
BRAND_ROOT = BASE_DIR / "tmp" / "brand-smoke-test"
BRAND_OUTPUT = BASE_DIR / "reports" / "brand-holdout.csv"
HARD_NEGATIVE_LABELS = {
    "battery",
    "bottle",
    "cardboard",
    "leaf",
    "newspaper",
    "plastic_bag",
    "shampoo_bottle",
    "soda_can",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_hard_negatives() -> int:
    with SPLIT.open(encoding="utf-8", newline="") as stream:
        rows = [
            row for row in csv.DictReader(stream)
            if row["split"] == "test" and row["label"] in HARD_NEGATIVE_LABELS
        ]
    fields = ["filepath", "label", "split", "group_id", "sha256", "dhash"]
    with HARD_NEGATIVE_OUTPUT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row[field] for field in fields} for row in rows)
    return len(rows)


def write_brand_holdout() -> int:
    rows = []
    for brand_dir in sorted(BRAND_ROOT.iterdir()):
        if not brand_dir.is_dir():
            continue
        for path in sorted(brand_dir.iterdir()):
            if path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                continue
            rows.append({
                "filepath": path.relative_to(BASE_DIR).as_posix(),
                "brand": brand_dir.name,
                "expected_label": "milk_carton",
                "sha256": sha256(path),
                "source_kind": "product_page_smoke_holdout",
            })
    unique = {}
    for row in rows:
        unique.setdefault(row["sha256"], row)
    fields = ["filepath", "brand", "expected_label", "sha256", "source_kind"]
    with BRAND_OUTPUT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(unique.values())
    return len(unique)


def main() -> int:
    hard_negatives = write_hard_negatives()
    brands = write_brand_holdout()
    print(f"Hard negatives: {hard_negatives}")
    print(f"Brand holdout: {brands}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
