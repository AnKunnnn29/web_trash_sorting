#!/usr/bin/env python3
"""Promote manually reviewed open-source images into the training dataset."""

import hashlib
import json
import shutil
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
REVIEW_FILE = BASE_DIR / "config" / "open-image-review.json"
REPORT_FILE = BASE_DIR / "reports" / "open-image-promotion.md"
PROVENANCE_FILE = BASE_DIR / "data_provenance" / "open-images.jsonl"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    review = json.loads(REVIEW_FILE.read_text(encoding="utf-8"))
    provenance_by_file = {}
    if PROVENANCE_FILE.exists():
        for line in PROVENANCE_FILE.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                provenance_by_file[record.get("local_file")] = record
    existing = {}
    for path in (BASE_DIR / "dataset").glob("*/*"):
        if path.is_file():
            existing.setdefault(sha256(path), path)

    promoted = []
    skipped = []
    accepted_sources = {
        relative_path
        for relative_paths in review["accepted"].values()
        for relative_path in relative_paths
    }
    for label, relative_paths in review["accepted"].items():
        destination_dir = BASE_DIR / "dataset" / label
        destination_dir.mkdir(parents=True, exist_ok=True)
        for relative_path in relative_paths:
            if relative_path not in provenance_by_file:
                skipped.append((relative_path, "missing provenance"))
                continue
            source = BASE_DIR / relative_path
            if not source.exists():
                skipped.append((relative_path, "missing"))
                continue
            digest = sha256(source)
            if digest in existing:
                skipped.append((relative_path, "duplicate"))
                continue
            destination = destination_dir / f"open_{digest[:12]}.jpg"
            shutil.copy2(source, destination)
            existing[digest] = destination
            promoted.append((label, relative_path, destination.relative_to(BASE_DIR).as_posix()))

    promoted_by_source = {source: destination for _, source, destination in promoted}
    if provenance_by_file:
        records = []
        for record in provenance_by_file.values():
            source = record.get("local_file")
            if source in accepted_sources:
                record["review_status"] = "accepted"
                if source in promoted_by_source:
                    record["dataset_file"] = promoted_by_source[source]
            elif source and source.startswith("dataset_review/open_images/"):
                record["review_status"] = "rejected"
            records.append(record)
        PROVENANCE_FILE.write_text(
            "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
            encoding="utf-8",
        )

    lines = [
        "# Open image promotion",
        "",
        f"- Accepted and promoted: {len(promoted)}",
        f"- Skipped: {len(skipped)}",
        "- Review policy: manual object-level visual review before promotion.",
        "",
        "| Label | Source review file | Dataset file |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| {label} | `{source}` | `{destination}` |" for label, source, destination in promoted)
    if skipped:
        lines.extend(["", "## Skipped", ""])
        lines.extend(f"- `{path}`: {reason}" for path, reason in skipped)
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Promoted {len(promoted)} images; skipped {len(skipped)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
