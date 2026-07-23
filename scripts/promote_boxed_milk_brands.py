#!/usr/bin/env python3
"""Promote manually reviewed boxed-milk images without duplicating existing data."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
REVIEW_PATH = BASE_DIR / "config" / "boxed-milk-brand-review.json"
PROVENANCE_PATH = (
    BASE_DIR / "data_provenance" / "openfoodfacts-boxed-milk-brands.jsonl"
)
CATALOG_PATH = BASE_DIR / "config" / "vietnam-boxed-milk-brands.json"
REPORT_PATH = BASE_DIR / "reports" / "vietnam-boxed-milk-brand-coverage.md"
DATASET_DIR = BASE_DIR / "dataset"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_report(catalog: dict, records: list[dict]) -> None:
    by_slug = {}
    for record in records:
        by_slug.setdefault(record["brand_slug"], []).append(record)
    lines = [
        "# Vietnamese boxed-milk brand coverage",
        "",
        f"- Checked at: {catalog['checkedAt']}",
        f"- Catalog brands: {len(catalog['brands'])}",
        f"- Openly licensed review images: {len(records)}",
        f"- Newly added training images: "
        f"{sum(r['review_status'] == 'approved' for r in records)}",
        f"- Approved images already present: "
        f"{sum(r['review_status'] == 'approved_existing' for r in records)}",
        "",
        "| Brand | Segment | Review images | In dataset | Status |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for brand in catalog["brands"]:
        brand_records = by_slug.get(brand["slug"], [])
        in_dataset = sum(
            record["review_status"] in {"approved", "approved_existing"}
            for record in brand_records
        )
        if in_dataset:
            status = "added / already present"
        elif brand_records:
            status = "reviewed; no suitable carton"
        else:
            status = "licensed image gap"
        lines.append(
            f"| [{brand['name']}]({brand['verificationUrl']}) | {brand['segment']} | "
            f"{len(brand_records)} | {in_dataset} | {status} |"
        )
    lines.extend([
        "",
        "Market pages verify that the brand/product is available in Vietnam; their images "
        "were not copied. Training images come from Open Food Facts under CC BY-SA, were "
        "manually checked as paper cartons, and retain per-image provenance.",
        "",
    ])
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in PROVENANCE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    approved = {
        (slug, code)
        for slug, codes in review["approvedCodesByBrand"].items()
        for code in codes
    }
    destination_folder = DATASET_DIR / review["destinationFolder"]
    destination_folder.mkdir(parents=True, exist_ok=True)
    existing_by_hash = {
        file_sha256(path): path
        for path in destination_folder.iterdir()
        if path.is_file()
    }
    promoted = 0
    existing = 0
    rejected = 0
    for record in records:
        key = (record["brand_slug"], record["code"])
        if key not in approved:
            record["review_status"] = "rejected"
            record["review_note"] = review["reviewNotes"].get(
                record["code"], "not approved during visual review"
            )
            rejected += 1
            continue
        source = BASE_DIR / record["local_file"]
        if not source.exists():
            record["review_status"] = "approved_missing_file"
            continue
        source_hash = file_sha256(source)
        if source_hash in existing_by_hash:
            destination = existing_by_hash[source_hash]
            record["review_status"] = "approved_existing"
            existing += 1
        else:
            destination = destination_folder / source.name
            shutil.copy2(source, destination)
            existing_by_hash[source_hash] = destination
            record["review_status"] = "approved"
            promoted += 1
        record["dataset_file"] = str(destination.relative_to(BASE_DIR)).replace("\\", "/")

    PROVENANCE_PATH.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False) + "\n"
            for record in sorted(records, key=lambda item: (item["brand_slug"], item["code"]))
        ),
        encoding="utf-8",
    )
    write_report(catalog, records)
    print(f"Newly promoted: {promoted}")
    print(f"Approved but already present: {existing}")
    print(f"Rejected: {rejected}")
    print(f"Dataset milk_carton total: {sum(1 for p in destination_folder.iterdir() if p.is_file())}")


if __name__ == "__main__":
    main()
