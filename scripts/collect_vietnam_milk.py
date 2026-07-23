#!/usr/bin/env python3
"""Collect openly licensed Vietnamese dairy-packaging images for manual review.

Images are intentionally downloaded to dataset_review/ instead of dataset/.
Only promote an image after verifying the package material and removing near
duplicates. Product images from Open Food Facts are CC BY-SA; keep the generated
manifest when reusing them.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw


BASE_DIR = Path(__file__).resolve().parents[1]
REVIEW_DIR = BASE_DIR / "dataset_review"
PROVENANCE_PATH = BASE_DIR / "data_provenance" / "openfoodfacts-vietnam-milk.jsonl"
SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"
HEADERS = {
    "User-Agent": "EcoSortDatasetCollector/1.0 (educational computer-vision project)"
}
SEARCH_DELAY_SECONDS = 6.5
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}

GROUPS = {
    "milk_carton": {
        "queries": [
            "TH true milk",
            "Vinamilk fresh milk",
            "Dutch Lady milk",
        ],
        "include": ("milk", "sữa", "true juice milk"),
        "exclude": (
            "powder", "bột", "condensed", "đặc", "bịch", "bag",
            "butter", "bơ", "yogurt cup", "sữa chua ăn",
        ),
    },
    "probiotic_bottle": {
        "queries": [
            "Yakult",
            "Vinamilk Probi",
        ],
        "include": ("yakult", "probi", "probiotic", "fermented", "lacto"),
        "exclude": (),
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--group",
        action="append",
        choices=sorted(GROUPS),
        help="Collect one group; repeat for multiple groups. Defaults to all.",
    )
    parser.add_argument("--max-per-group", type=int, default=100)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--timeout", type=int, default=30)
    return parser.parse_args()


def normalize_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def dhash(image: Image.Image) -> str:
    grayscale = image.convert("L").resize((9, 8), Image.BILINEAR)
    pixels = list(grayscale.getdata())
    value = 0
    for y in range(8):
        for x in range(8):
            value = (value << 1) | int(pixels[y * 9 + x] > pixels[y * 9 + x + 1])
    return f"{value:016x}"


def existing_hashes(folder: Path) -> set[str]:
    hashes = set()
    if not folder.exists():
        return hashes
    for path in folder.iterdir():
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            try:
                with Image.open(path) as image:
                    hashes.add(dhash(image))
            except Exception:
                continue
    return hashes


def search_products(query: str, page_size: int, timeout: int) -> list[dict]:
    response = requests.get(
        SEARCH_URL,
        params={
            "search_terms": query,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": page_size,
            "fields": (
                "code,product_name,product_name_vi,brands,countries_tags,"
                "packaging_tags,image_front_url,image_url"
            ),
        },
        headers=HEADERS,
        timeout=timeout,
    )
    if response.status_code != 200:
        print(f"[WARN] Open Food Facts search failed for {query!r}: HTTP {response.status_code}")
        return []
    return response.json().get("products", [])


def is_candidate(product: dict, config: dict) -> bool:
    text = normalize_text(" ".join([
        str(product.get("product_name", "")),
        str(product.get("product_name_vi", "")),
        str(product.get("brands", "")),
        " ".join(product.get("packaging_tags") or []),
    ]))
    return (
        any(keyword in text for keyword in config["include"])
        and not any(keyword in text for keyword in config["exclude"])
        and bool(product.get("image_front_url") or product.get("image_url"))
    )


def download_image(url: str, timeout: int) -> tuple[Image.Image, bytes] | None:
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        if len(response.content) < 5_000:
            return None
        image = Image.open(io.BytesIO(response.content)).convert("RGB")
        if min(image.size) < 160:
            return None
        return image, response.content
    except Exception as error:
        print(f"[WARN] Image download failed: {error}")
        return None


def load_manifest() -> dict[tuple[str, str], dict]:
    records = {}
    if not PROVENANCE_PATH.exists():
        return records
    for line in PROVENANCE_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        records[(record["group"], record["code"])] = record
    return records


def write_manifest(records: dict[tuple[str, str], dict]) -> None:
    PROVENANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(records.values(), key=lambda item: (item["group"], item["code"]))
    PROVENANCE_PATH.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in ordered),
        encoding="utf-8",
    )


def make_contact_sheet(folder: Path, group: str) -> None:
    paths = sorted(
        path for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not paths:
        return
    thumb_size = 180
    caption_height = 28
    columns = 5
    rows = (len(paths) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb_size, rows * (thumb_size + caption_height)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(paths):
        with Image.open(path) as image:
            image = image.convert("RGB")
            image.thumbnail((thumb_size - 12, thumb_size - 12))
            x = (index % columns) * thumb_size + (thumb_size - image.width) // 2
            y = (index // columns) * (thumb_size + caption_height) + (thumb_size - image.height) // 2
            sheet.paste(image, (x, y))
        caption = path.stem[-18:]
        draw.text(
            ((index % columns) * thumb_size + 5, (index // columns) * (thumb_size + caption_height) + thumb_size + 4),
            caption,
            fill="black",
        )
    sheet.save(REVIEW_DIR / f"{group}-contact-sheet.jpg", quality=90)


def collect_group(group: str, args: argparse.Namespace, manifest: dict) -> int:
    config = GROUPS[group]
    folder = REVIEW_DIR / group
    folder.mkdir(parents=True, exist_ok=True)
    hashes = existing_hashes(folder)
    candidates = {}

    for index, query in enumerate(config["queries"]):
        for product in search_products(query, args.page_size, args.timeout):
            if is_candidate(product, config) and product.get("code"):
                candidates[str(product["code"])] = product
        if index < len(config["queries"]) - 1:
            time.sleep(SEARCH_DELAY_SECONDS)

    added = 0
    for code, product in sorted(candidates.items()):
        if len(hashes) >= args.max_per_group:
            break
        image_url = product.get("image_front_url") or product.get("image_url")
        result = download_image(image_url, args.timeout)
        if not result:
            continue
        image, raw_data = result
        image_hash = dhash(image)
        if image_hash in hashes:
            continue

        content_hash = hashlib.sha256(raw_data).hexdigest()
        filename = f"off_{code}_{content_hash[:10]}.jpg"
        destination = folder / filename
        image.save(destination, "JPEG", quality=92, optimize=True)
        hashes.add(image_hash)
        added += 1
        manifest[(group, code)] = {
            "group": group,
            "code": code,
            "product_name": product.get("product_name_vi") or product.get("product_name"),
            "brands": product.get("brands"),
            "local_file": str(destination.relative_to(BASE_DIR)).replace("\\", "/"),
            "image_url": image_url,
            "product_url": f"https://world.openfoodfacts.org/product/{quote(code)}",
            "license": "CC BY-SA (Open Food Facts product images)",
            "sha256": content_hash,
            "dhash": image_hash,
            "review_status": "pending",
        }

    make_contact_sheet(folder, group)
    print(f"[OK] {group}: candidates={len(candidates)}, added={added}, review_total={len(hashes)}")
    return added


def main() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args()
    groups = args.group or sorted(GROUPS)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    for group_index, group in enumerate(groups):
        collect_group(group, args, manifest)
        if group_index < len(groups) - 1:
            time.sleep(SEARCH_DELAY_SECONDS)
    write_manifest(manifest)
    print(f"Review images before promotion: {REVIEW_DIR}")
    print(f"Attribution manifest: {PROVENANCE_PATH}")


if __name__ == "__main__":
    main()
