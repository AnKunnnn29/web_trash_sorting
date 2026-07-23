#!/usr/bin/env python3
"""Promote reviewed structured-search cartons into dataset/milk_carton."""

import hashlib
import json
import shutil
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG = BASE_DIR / "config" / "milk-carton-structured-review.json"
PROVENANCE = BASE_DIR / "data_provenance" / "openfoodfacts-milk-carton-structured.jsonl"
DESTINATION = BASE_DIR / "dataset" / "milk_carton"
REPORT = BASE_DIR / "reports" / "milk-carton-structured-promotion.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    review = json.loads(CONFIG.read_text(encoding="utf-8"))
    accepted = set(review["accepted_codes"])
    rejected = set(review["rejected_codes"])
    records = [
        json.loads(line)
        for line in PROVENANCE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    known = {
        sha256(path): path
        for path in DESTINATION.iterdir()
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}
    }
    promoted = []
    skipped = []
    for record in records:
        code = str(record["code"])
        if code in rejected:
            record["review_status"] = "rejected"
            record["review_note"] = review["rejected_codes"][code]
            continue
        if code not in accepted:
            continue
        source = BASE_DIR / record["local_file"]
        if not source.exists():
            skipped.append((code, "missing review file"))
            continue
        digest = sha256(source)
        if digest in known:
            record["review_status"] = "approved_existing"
            record["dataset_file"] = known[digest].relative_to(BASE_DIR).as_posix()
            skipped.append((code, "exact duplicate already in dataset"))
            continue
        destination = DESTINATION / f"off_structured_{code}_{digest[:10]}.jpg"
        shutil.copy2(source, destination)
        known[digest] = destination
        record["review_status"] = "approved"
        record["dataset_file"] = destination.relative_to(BASE_DIR).as_posix()
        promoted.append((code, record.get("brands") or "", record["dataset_file"]))

    PROVENANCE.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    lines = [
        "# Structured milk-carton promotion",
        "",
        f"- Promoted: {len(promoted)}",
        f"- Skipped: {len(skipped)}",
        f"- Rejected during visual review: {len(rejected)}",
        "",
        "| Barcode | Brand | Dataset file |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| {code} | {brand} | `{path}` |" for code, brand, path in promoted)
    if skipped:
        lines.extend(["", "## Skipped", ""])
        lines.extend(f"- {code}: {reason}" for code, reason in skipped)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Promoted {len(promoted)}; skipped {len(skipped)}; rejected {len(rejected)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
