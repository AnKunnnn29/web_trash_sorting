#!/usr/bin/env python3
"""Audit dataset balance, unreadable files, and duplicate-image leakage risks."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image


BASE_DIR = Path(__file__).resolve().parents[1]
DATASET_DIR = BASE_DIR / "dataset"
MAPPING_PATH = BASE_DIR / "config" / "dataset-labels.json"
DEFAULT_JSON_REPORT = BASE_DIR / "reports" / "dataset-audit.json"
DEFAULT_MD_REPORT = BASE_DIR / "reports" / "dataset-audit.md"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET_DIR)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--json-report", type=Path, default=DEFAULT_JSON_REPORT)
    parser.add_argument("--markdown-report", type=Path, default=DEFAULT_MD_REPORT)
    return parser.parse_args()


def dhash(image: Image.Image) -> str:
    grayscale = image.convert("L").resize((9, 8), Image.BILINEAR)
    pixels = list(grayscale.getdata())
    value = 0
    for y in range(8):
        for x in range(8):
            value = (value << 1) | int(pixels[y * 9 + x] > pixels[y * 9 + x + 1])
    return f"{value:016x}"


def inspect_image(item: tuple[Path, str]) -> dict:
    path, label = item
    try:
        content = path.read_bytes()
        with Image.open(path) as image:
            image.load()
            width, height = image.size
            visual_hash = dhash(image)
        return {
            "path": str(path.relative_to(BASE_DIR)).replace("\\", "/"),
            "label": label,
            "sha256": hashlib.sha256(content).hexdigest(),
            "dhash": visual_hash,
            "width": width,
            "height": height,
        }
    except Exception as error:
        return {
            "path": str(path.relative_to(BASE_DIR)).replace("\\", "/"),
            "label": label,
            "error": str(error),
        }


def duplicate_groups(records: list[dict], key: str) -> list[dict]:
    grouped = defaultdict(list)
    for record in records:
        if record.get(key):
            grouped[record[key]].append(record)
    result = []
    for hash_value, members in grouped.items():
        if len(members) < 2:
            continue
        labels = sorted({member["label"] for member in members})
        result.append({
            key: hash_value,
            "count": len(members),
            "labels": labels,
            "cross_label": len(labels) > 1,
            "paths": [member["path"] for member in members],
        })
    return sorted(result, key=lambda item: (-item["count"], item[key]))


def main() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    inputs = []
    for folder, label in mapping.items():
        folder_path = args.dataset / folder
        if not folder_path.is_dir():
            continue
        inputs.extend(
            (path, label)
            for path in folder_path.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        records = list(executor.map(inspect_image, inputs))

    unreadable = [record for record in records if record.get("error")]
    valid = [record for record in records if not record.get("error")]
    exact_groups = duplicate_groups(valid, "sha256")
    visual_groups = duplicate_groups(valid, "dhash")
    label_counts = Counter(record["label"] for record in valid)

    report = {
        "image_count": len(records),
        "valid_count": len(valid),
        "unreadable_count": len(unreadable),
        "label_counts": dict(sorted(label_counts.items())),
        "exact_duplicate_groups": len(exact_groups),
        "exact_duplicate_files": sum(group["count"] - 1 for group in exact_groups),
        "visual_duplicate_groups": len(visual_groups),
        "visual_duplicate_files": sum(group["count"] - 1 for group in visual_groups),
        "cross_label_exact_groups": sum(group["cross_label"] for group in exact_groups),
        "cross_label_visual_groups": sum(group["cross_label"] for group in visual_groups),
        "unreadable": unreadable,
        "exact_duplicates": exact_groups,
        "visual_duplicates": visual_groups,
    }
    args.json_report.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_report.parent.mkdir(parents=True, exist_ok=True)
    args.json_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Dataset audit",
        "",
        f"- Images: {report['image_count']}",
        f"- Unreadable: {report['unreadable_count']}",
        f"- Exact duplicate files beyond the first copy: {report['exact_duplicate_files']}",
        f"- Same-dHash files beyond the first copy: {report['visual_duplicate_files']}",
        f"- Exact duplicate groups crossing labels: {report['cross_label_exact_groups']}",
        f"- Same-dHash groups crossing labels: {report['cross_label_visual_groups']}",
        "",
        "## Label counts",
        "",
        "| Label | Images |",
        "|---|---:|",
    ]
    lines.extend(f"| {label} | {count} |" for label, count in sorted(label_counts.items()))
    lines.extend([
        "",
        "Same-dHash groups are review candidates, not automatic deletions. A simple",
        "perceptual hash can collide for visually simple images.",
        "",
    ])
    args.markdown_report.write_text("\n".join(lines), encoding="utf-8")

    print(
        f"Dataset audit complete: images={report['image_count']}, "
        f"unreadable={report['unreadable_count']}, "
        f"exact_duplicate_files={report['exact_duplicate_files']}, "
        f"visual_duplicate_files={report['visual_duplicate_files']}"
    )


if __name__ == "__main__":
    main()
