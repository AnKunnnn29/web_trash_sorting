#!/usr/bin/env python3
"""Build a deterministic, duplicate-safe train/validation/test manifest."""

from __future__ import annotations

import csv
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image


BASE_DIR = Path(__file__).resolve().parents[1]
DATASET_DIR = BASE_DIR / "dataset"
MAPPING_PATH = BASE_DIR / "config" / "dataset-labels.json"
EXTERNAL_PROVENANCE = (
    BASE_DIR / "data_provenance" / "openfoodfacts-boxed-milk-brands.jsonl"
)
PROVENANCE_DIR = BASE_DIR / "data_provenance"
OUTPUT_PATH = BASE_DIR / "reports" / "training-split.csv"
REPORT_PATH = BASE_DIR / "reports" / "training-split.md"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
SEED = 20260723


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dhash(path: Path) -> str:
    with Image.open(path) as image:
        grayscale = image.convert("L").resize((9, 8), Image.BILINEAR)
        pixels = list(grayscale.getdata())
    value = 0
    for y in range(8):
        for x in range(8):
            value = (value << 1) | int(
                pixels[y * 9 + x] > pixels[y * 9 + x + 1]
            )
    return f"{value:016x}"


def external_holdout_paths() -> set[str]:
    paths = set()
    if not EXTERNAL_PROVENANCE.exists():
        return paths
    for line in EXTERNAL_PROVENANCE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("review_status") == "approved" and record.get("dataset_file"):
            paths.add(record["dataset_file"].replace("\\", "/"))
    return paths


def provenance_groups() -> dict[str, str]:
    groups = {}
    for manifest_path in sorted(PROVENANCE_DIR.glob("*.jsonl")):
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            dataset_file = record.get("dataset_file")
            code = record.get("code")
            if dataset_file and code:
                groups[dataset_file.replace("\\", "/")] = f"off-sku:{code}"
    return groups


def infer_source_group(relative: str, label: str, provenance: dict[str, str]) -> str:
    if relative in provenance:
        return provenance[relative]
    stem = Path(relative).stem
    webcam = re.match(r"^(webcam_.+)_\d{3}$", stem)
    if webcam:
        return f"webcam-session:{label}:{webcam.group(1)}"
    downloaded = re.match(r"^dl_\d+_([0-9a-f]+)$", stem)
    if downloaded:
        return f"download-source:{label}:{downloaded.group(1)}"
    return f"file:{relative}"


def collect_records(mapping: dict[str, str]) -> list[dict]:
    records = []
    provenance = provenance_groups()
    for folder in sorted(DATASET_DIR.iterdir()):
        if not folder.is_dir() or folder.name not in mapping:
            continue
        label = mapping[folder.name]
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            relative = str(path.relative_to(BASE_DIR)).replace("\\", "/")
            records.append({
                "filepath": relative,
                "label": label,
                "source_folder": folder.name,
                "sha256": sha256(path),
                "dhash": dhash(path),
                "source_group": infer_source_group(relative, label, provenance),
            })
    return records


def cross_label_hashes(records: list[dict], field: str) -> set[str]:
    labels_by_hash = defaultdict(set)
    for record in records:
        labels_by_hash[record[field]].add(record["label"])
    return {
        image_hash for image_hash, labels in labels_by_hash.items()
        if len(labels) > 1
    }


def assign_splits(records: list[dict], external_paths: set[str]) -> tuple[list[dict], Counter]:
    excluded_exact = cross_label_hashes(records, "sha256")
    excluded_visual = cross_label_hashes(records, "dhash")
    exclusions = Counter()
    unique = {}
    external = []

    for record in records:
        if record["sha256"] in excluded_exact:
            exclusions["cross_label_exact"] += 1
            continue
        if record["dhash"] in excluded_visual:
            exclusions["cross_label_visual"] += 1
            continue
        key = (record["label"], record["dhash"])
        if record["filepath"] in external_paths:
            external.append(record)
            continue
        if key in unique:
            exclusions["within_label_visual_duplicate"] += 1
            continue
        unique[key] = record

    # Ensure no training item can duplicate an external holdout image.
    external_hashes = {record["dhash"] for record in external}
    clean = []
    for record in unique.values():
        if record["dhash"] in external_hashes:
            exclusions["external_holdout_duplicate"] += 1
        else:
            clean.append(record)

    by_label = defaultdict(list)
    for record in clean:
        by_label[record["label"]].append(record)

    rng = random.Random(SEED)
    assigned = []
    for label, items in sorted(by_label.items()):
        source_groups = defaultdict(list)
        for item in items:
            source_groups[item["source_group"]].append(item)
        groups = sorted(
            source_groups.values(),
            key=lambda group: group[0]["source_group"],
        )
        rng.shuffle(groups)
        count = len(items)
        test_count = max(1, round(count * 0.15))
        val_count = max(1, round(count * 0.15))
        if count - test_count - val_count < 1:
            raise RuntimeError(f"Not enough clean images for label {label}: {count}")
        split_groups = {"test": [], "validation": [], "train": []}
        split_sizes = Counter()
        for group in groups:
            if split_sizes["test"] < test_count:
                split = "test"
            elif split_sizes["validation"] < val_count:
                split = "validation"
            else:
                split = "train"
            split_groups[split].append(group)
            split_sizes[split] += len(group)
        if not split_groups["train"]:
            donor = max(("test", "validation"), key=lambda name: len(split_groups[name]))
            split_groups["train"].append(split_groups[donor].pop())
        for split, grouped_items in split_groups.items():
            for group in grouped_items:
                for record in group:
                    assigned.append({
                        **record,
                        "split": split,
                        "group_id": record["source_group"],
                    })

    for record in external:
        assigned.append({
            **record,
            "split": "external_test",
            "group_id": record["source_group"],
        })
    return assigned, exclusions


def write_outputs(records: list[dict], exclusions: Counter, total: int) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "filepath", "label", "split", "group_id", "source_group", "sha256",
        "dhash", "source_folder"
    ]
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(records, key=lambda item: (item["split"], item["label"], item["filepath"])))

    split_counts = Counter(record["split"] for record in records)
    label_split_counts = Counter((record["label"], record["split"]) for record in records)
    labels = sorted({record["label"] for record in records})
    lines = [
        "# Duplicate-safe training split",
        "",
        f"- Source images scanned: {total}",
        f"- Images retained: {len(records)}",
        f"- Train: {split_counts['train']}",
        f"- Validation: {split_counts['validation']}",
        f"- Internal test: {split_counts['test']}",
        f"- External boxed-milk test: {split_counts['external_test']}",
        f"- Excluded cross-label exact conflicts: {exclusions['cross_label_exact']}",
        f"- Excluded cross-label visual conflicts: {exclusions['cross_label_visual']}",
        f"- Removed within-label visual duplicates: {exclusions['within_label_visual_duplicate']}",
        f"- Removed duplicates of external holdout: {exclusions['external_holdout_duplicate']}",
        "",
        "| Label | Train | Validation | Test | External |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for label in labels:
        lines.append(
            f"| {label} | {label_split_counts[(label, 'train')]} | "
            f"{label_split_counts[(label, 'validation')]} | "
            f"{label_split_counts[(label, 'test')]} | "
            f"{label_split_counts[(label, 'external_test')]} |"
        )
    lines.extend([
        "",
        "All exact/dHash conflicts crossing output labels are excluded. Within-label "
        "dHash duplicates are represented once. Images from the same SKU, webcam "
        "session, or known download source stay in one split. The latest boxed-milk "
        "images stay outside training so the baseline and candidate can be compared "
        "on the same data.",
        "",
    ])
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    records = collect_records(mapping)
    assigned, exclusions = assign_splits(records, external_holdout_paths())
    write_outputs(assigned, exclusions, len(records))
    counts = Counter(record["split"] for record in assigned)
    print(f"Split manifest: {OUTPUT_PATH}")
    print(dict(counts))
    print(f"Excluded: {dict(exclusions)}")


if __name__ == "__main__":
    main()
