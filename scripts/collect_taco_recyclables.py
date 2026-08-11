#!/usr/bin/env python3
"""Collect review-only recyclable object crops from the official TACO dataset."""

import argparse
import hashlib
import io
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import requests
from PIL import Image, ImageFile

from collect_open_images import make_contact_sheet


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TACO_ROOT = BASE_DIR / "tmp" / "TACO"
REVIEW_ROOT = BASE_DIR / "dataset_review" / "taco_recyclables"
PROVENANCE_PATH = BASE_DIR / "data_provenance" / "taco-recyclables.jsonl"
REPORT_PATH = BASE_DIR / "reports" / "taco-recyclables-collection.md"
HEADERS = {"User-Agent": "EcoSort-TACO-Collector/1.0 (educational; review-only)"}
ImageFile.LOAD_TRUNCATED_IMAGES = True


CATEGORY_MAP = {
    "Drink can": ("soda-can", "soda_can"),
    "Food Can": ("soda-can", "soda_can"),
    "Drink carton": ("milk-carton", "milk_carton"),
    "Meal carton": ("milk-carton", "milk_carton"),
    "Disposable plastic cup": ("plastic-cup", "bottle"),
    "Other plastic cup": ("plastic-cup", "bottle"),
    "Other plastic container": ("plastic-container", "bottle"),
    "Single-use carrier bag": ("plastic-bag", "plastic_bag"),
    "Polypropylene bag": ("plastic-bag", "plastic_bag"),
    "Normal paper": ("paper", "newspaper"),
    "Magazine paper": ("paper", "newspaper"),
    "Wrapping paper": ("paper", "newspaper"),
    "Corrugated carton": ("cardboard", "cardboard"),
    "Other carton": ("cardboard", "cardboard"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taco-root", type=Path, default=DEFAULT_TACO_ROOT)
    parser.add_argument("--max-per-target", type=int, default=25)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260811)
    return parser.parse_args()


def load_manifest() -> dict[int, dict]:
    if not PROVENANCE_PATH.exists():
        return {}
    records = {}
    for line in PROVENANCE_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            records[int(record["annotation_id"])] = record
    return records


def write_manifest(records: dict[int, dict]) -> None:
    PROVENANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True)
             for _, record in sorted(records.items())]
    PROVENANCE_PATH.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def download_image(url: str, timeout: int) -> tuple[Image.Image, bytes]:
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    raw = response.content
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    return image, raw


def crop_annotation(
    image: Image.Image,
    bbox: list[float],
    source_width: int,
    source_height: int,
) -> Image.Image:
    x, y, width, height = bbox
    scale_x = image.width / max(source_width, 1)
    scale_y = image.height / max(source_height, 1)
    x *= scale_x
    width *= scale_x
    y *= scale_y
    height *= scale_y
    pad_x = width * 0.18
    pad_y = height * 0.18
    left = max(0, int(x - pad_x))
    top = max(0, int(y - pad_y))
    right = min(image.width, int(x + width + pad_x))
    bottom = min(image.height, int(y + height + pad_y))
    return image.crop((left, top, right, bottom))


def write_report(records: dict[int, dict]) -> None:
    counts = defaultdict(int)
    for record in records.values():
        counts[record["target_id"]] += 1
    lines = [
        "# TACO recyclable collection",
        "",
        f"- Review crops: {len(records)}",
        "- Source: official TACO annotations and Flickr-hosted source images.",
        "- Status: pending object and source-image license review; not promoted to training.",
        "- Split rule: keep crops with the same `source_image_id` in one data split.",
        "",
        "| Target | Expected label | Review crops |",
        "| --- | --- | ---: |",
    ]
    targets = sorted(set(CATEGORY_MAP.values()))
    for target_id, expected_label in targets:
        lines.append(f"| {target_id} | {expected_label} | {counts[target_id]} |")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args()
    annotation_path = args.taco_root / "data" / "annotations.json"
    if not annotation_path.exists():
        raise SystemExit(
            "TACO annotations not found. Clone https://github.com/pedropro/TACO "
            f"to {args.taco_root} first."
        )

    taco = json.loads(annotation_path.read_text(encoding="utf-8"))
    categories = {item["id"]: item["name"] for item in taco["categories"]}
    images = {item["id"]: item for item in taco["images"]}
    candidates = defaultdict(list)
    for annotation in taco["annotations"]:
        category_name = categories[annotation["category_id"]]
        if category_name in CATEGORY_MAP:
            target_id, expected_label = CATEGORY_MAP[category_name]
            candidates[target_id].append((annotation, category_name, expected_label))

    rng = random.Random(args.seed)
    records = load_manifest()
    for target_id, entries in sorted(candidates.items()):
        folder = REVIEW_ROOT / target_id
        folder.mkdir(parents=True, exist_ok=True)
        rng.shuffle(entries)
        current = sum(record["target_id"] == target_id for record in records.values())
        added = 0
        image_cache = {}
        for annotation, category_name, expected_label in entries:
            if current + added >= args.max_per_target:
                break
            annotation_id = int(annotation["id"])
            if annotation_id in records:
                continue
            image_meta = images[annotation["image_id"]]
            url = image_meta.get("flickr_640_url") or image_meta.get("flickr_url")
            if not url:
                continue
            try:
                if image_meta["id"] not in image_cache:
                    image_cache[image_meta["id"]] = download_image(url, args.timeout)[0]
                crop = crop_annotation(
                    image_cache[image_meta["id"]],
                    annotation["bbox"],
                    image_meta["width"],
                    image_meta["height"],
                )
                if crop.width < 64 or crop.height < 64:
                    continue
                digest = hashlib.sha256(
                    f"{image_meta['id']}:{annotation_id}:{annotation['bbox']}".encode("utf-8")
                ).hexdigest()
                destination = folder / f"taco_{digest[:16]}.jpg"
                crop.save(destination, "JPEG", quality=92, optimize=True)
                records[annotation_id] = {
                    "annotation_id": annotation_id,
                    "source_image_id": int(image_meta["id"]),
                    "source_category": category_name,
                    "target_id": target_id,
                    "expected_label": expected_label,
                    "bbox": annotation["bbox"],
                    "source_url": url,
                    "source_page": image_meta.get("flickr_url") or url,
                    "local_file": str(destination.relative_to(BASE_DIR)).replace("\\", "/"),
                    "annotation_source": "https://github.com/pedropro/TACO",
                    "annotation_license": "MIT",
                    "image_license": None,
                    "review_status": "pending_license_and_object_review",
                }
                added += 1
            except (requests.RequestException, OSError) as error:
                print(f"[WARN] {target_id} image {image_meta['id']}: {error}")
        make_contact_sheet(folder)
        write_manifest(records)
        write_report(records)
        print(f"[OK] {target_id}: added={added}, total={current + added}")

    print(f"Review root: {REVIEW_ROOT}")
    print(f"Provenance: {PROVENANCE_PATH}")
    print(f"Report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
