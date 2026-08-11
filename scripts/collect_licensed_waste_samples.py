#!/usr/bin/env python3
"""Collect small, review-only samples from clearly licensed waste datasets."""

import argparse
import hashlib
import io
import json
import random
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image, ImageFile

from collect_open_images import make_contact_sheet


BASE_DIR = Path(__file__).resolve().parents[1]
REVIEW_ROOT = BASE_DIR / "dataset_review" / "licensed_samples"
PROVENANCE_PATH = BASE_DIR / "data_provenance" / "licensed-waste-samples.jsonl"
REPORT_PATH = BASE_DIR / "reports" / "licensed-waste-samples.md"
HEADERS = {"User-Agent": "EcoSort-Licensed-Dataset-Collector/1.0 (educational)"}
ImageFile.LOAD_TRUNCATED_IMAGES = True

REALWASTE_TREE_URL = (
    "https://huggingface.co/api/datasets/shahzaibvohra/realwaste/tree/main"
    "?recursive=true&expand=false"
)
REALWASTE_BASE_URL = (
    "https://huggingface.co/datasets/shahzaibvohra/realwaste/resolve/main/"
)
MENDELEY_API_URL = "https://data.mendeley.com/public-api/datasets/h5pxbsdz4m"

TARGETS = {
    "realwaste-food-organics": {
        "source": "realwaste",
        "match": "Food Organics_",
        "expected_label": "manual_organic_review",
        "license": "CC BY-NC-SA 4.0",
        "source_page": "https://doi.org/10.24432/C5SS4G",
    },
    "realwaste-vegetation": {
        "source": "realwaste",
        "match": "Vegetation_",
        "expected_label": "leaf",
        "license": "CC BY-NC-SA 4.0",
        "source_page": "https://doi.org/10.24432/C5SS4G",
    },
    "mendeley-cardboard": {
        "source": "mendeley",
        "match": "Cardboard",
        "expected_label": "cardboard",
        "license": "CC BY 4.0",
        "source_page": "https://doi.org/10.17632/h5pxbsdz4m.1",
    },
    "mendeley-paper": {
        "source": "mendeley",
        "match": "Paper",
        "expected_label": "newspaper",
        "license": "CC BY 4.0",
        "source_page": "https://doi.org/10.17632/h5pxbsdz4m.1",
    },
    "mendeley-plastic": {
        "source": "mendeley",
        "match": "Plastic",
        "expected_label": "manual_plastic_review",
        "license": "CC BY 4.0",
        "source_page": "https://doi.org/10.17632/h5pxbsdz4m.1",
    },
    "mendeley-metal": {
        "source": "mendeley",
        "match": "Metal",
        "expected_label": "manual_metal_review",
        "license": "CC BY 4.0",
        "source_page": "https://doi.org/10.17632/h5pxbsdz4m.1",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-per-target", type=int, default=20)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20260812)
    parser.add_argument("--target", action="append", choices=sorted(TARGETS))
    parser.add_argument(
        "--mendeley-metadata",
        type=Path,
        help="Optional cached response from the Mendeley public dataset API.",
    )
    return parser.parse_args()


def request_json(url: str, timeout: int):
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.json()


def load_manifest() -> dict[str, dict]:
    if not PROVENANCE_PATH.exists():
        return {}
    records = {}
    for line in PROVENANCE_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            records[record["source_key"]] = record
    return records


def write_manifest(records: dict[str, dict]) -> None:
    PROVENANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(records[key], ensure_ascii=False, sort_keys=True)
             for key in sorted(records)]
    PROVENANCE_PATH.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def realwaste_candidates(timeout: int) -> list[dict]:
    items = []
    next_url = REALWASTE_TREE_URL
    while next_url:
        response = requests.get(next_url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        items.extend(response.json())
        next_url = response.links.get("next", {}).get("url")
    return [
        {
            "source_key": f"realwaste:{item['path']}",
            "filename": Path(item["path"]).name,
            "source_url": REALWASTE_BASE_URL + quote(item["path"], safe="/") + "?download=true",
            "source_path": item["path"],
            "source_sha256": None,
        }
        for item in items
        if item.get("type") == "file" and item.get("path", "").lower().endswith(".jpg")
    ]


def mendeley_candidates(timeout: int, metadata_path: Path | None = None) -> list[dict]:
    dataset = (
        json.loads(metadata_path.read_text(encoding="utf-8-sig"))
        if metadata_path
        else request_json(MENDELEY_API_URL, timeout)
    )
    return [
        {
            "source_key": f"mendeley:{item['id']}",
            "filename": item["filename"],
            "source_url": item["content_details"]["download_url"],
            "source_path": item["filename"],
            "source_sha256": item["content_details"].get("sha256_hash"),
        }
        for item in dataset["files"]
        if item.get("status") == "COMPLETED"
        and item.get("content_details", {}).get("content_type", "").startswith("image/")
    ]


def normalize_image(raw: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    return image


def write_report(records: dict[str, dict]) -> None:
    counts = Counter(record["target_id"] for record in records.values())
    lines = [
        "# Licensed waste sample collection",
        "",
        f"- Review images: {len(records)}",
        "- Status: pending object review; not promoted to training.",
        "- RealWaste license: CC BY-NC-SA 4.0.",
        "- Recyclable Waste Image Dataset license: CC BY 4.0.",
        "",
        "| Target | Expected mapping | Review images |",
        "| --- | --- | ---: |",
    ]
    for target_id, target in TARGETS.items():
        lines.append(
            f"| {target_id} | {target['expected_label']} | {counts[target_id]} |"
        )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args()
    selected = set(args.target or TARGETS)
    source_cache = {}
    records = load_manifest()
    rng = random.Random(args.seed)

    for target_id in TARGETS:
        if target_id not in selected:
            continue
        target = TARGETS[target_id]
        if target["source"] not in source_cache:
            source_cache[target["source"]] = (
                realwaste_candidates(args.timeout)
                if target["source"] == "realwaste"
                else mendeley_candidates(args.timeout, args.mendeley_metadata)
            )
        candidates = [
            item for item in source_cache[target["source"]]
            if target["match"].lower() in item["filename"].lower()
        ]
        rng.shuffle(candidates)
        folder = REVIEW_ROOT / target_id
        folder.mkdir(parents=True, exist_ok=True)
        current = sum(record["target_id"] == target_id for record in records.values())
        added = 0
        for item in candidates:
            if current + added >= args.max_per_target:
                break
            if item["source_key"] in records:
                continue
            try:
                response = requests.get(
                    item["source_url"], headers=HEADERS, timeout=args.timeout
                )
                response.raise_for_status()
                raw = response.content
                image = normalize_image(raw)
                content_hash = hashlib.sha256(raw).hexdigest()
                destination = folder / f"licensed_{content_hash[:16]}.jpg"
                image.save(destination, "JPEG", quality=90, optimize=True)
                records[item["source_key"]] = {
                    **item,
                    "target_id": target_id,
                    "expected_label": target["expected_label"],
                    "dataset_license": target["license"],
                    "source_page": target["source_page"],
                    "local_file": str(destination.relative_to(BASE_DIR)).replace("\\", "/"),
                    "download_sha256": content_hash,
                    "review_status": "pending_object_review",
                }
                added += 1
            except (requests.RequestException, OSError) as error:
                print(f"[WARN] {target_id} {item['filename']}: {error}")
        make_contact_sheet(folder)
        write_manifest(records)
        write_report(records)
        print(f"[OK] {target_id}: added={added}, total={current + added}")

    print(f"Review root: {REVIEW_ROOT}")
    print(f"Provenance: {PROVENANCE_PATH}")
    print(f"Report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
