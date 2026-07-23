#!/usr/bin/env python3
"""Promote reviewed Vietnamese dairy images into the training dataset."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
REVIEW_CONFIG = BASE_DIR / "config" / "vietnam-milk-review.json"
PROVENANCE_PATH = BASE_DIR / "data_provenance" / "openfoodfacts-vietnam-milk.jsonl"
DATASET_DIR = BASE_DIR / "dataset"


def main() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    review = json.loads(REVIEW_CONFIG.read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in PROVENANCE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    approved = {
        (group, code)
        for group, config in review.items()
        for code in config["approvedCodes"]
    }

    promoted = 0
    missing = []
    for record in records:
        key = (record["group"], record["code"])
        if key not in approved:
            record["review_status"] = "rejected"
            continue

        source = BASE_DIR / record["local_file"]
        if not source.exists():
            missing.append(str(source))
            record["review_status"] = "approved_missing_file"
            continue

        destination_folder = DATASET_DIR / review[record["group"]]["destinationFolder"]
        destination_folder.mkdir(parents=True, exist_ok=True)
        destination = destination_folder / source.name
        if not destination.exists():
            shutil.copy2(source, destination)
            promoted += 1
        record["review_status"] = "approved"
        record["dataset_file"] = str(destination.relative_to(BASE_DIR)).replace("\\", "/")

    PROVENANCE_PATH.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False) + "\n"
            for record in sorted(records, key=lambda item: (item["group"], item["code"]))
        ),
        encoding="utf-8",
    )

    print(f"Promoted {promoted} reviewed images.")
    print(f"Approved records: {sum(record['review_status'] == 'approved' for record in records)}")
    if missing:
        print("Missing approved files:")
        for path in missing:
            print(f"  {path}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
