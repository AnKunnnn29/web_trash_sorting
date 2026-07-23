#!/usr/bin/env python3
"""Collect duplicate-safe milk-carton candidates from Open Food Facts API v2."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw


BASE_DIR = Path(__file__).resolve().parents[1]
REVIEW_DIR = BASE_DIR / "dataset_review" / "milk_carton_structured"
PROVENANCE = BASE_DIR / "data_provenance" / "openfoodfacts-milk-carton-structured.jsonl"
REPORT = BASE_DIR / "reports" / "milk-carton-structured-collection.md"
SEARCH_URL = "https://world.openfoodfacts.org/api/v2/search"
HEADERS = {
    "User-Agent": "EcoSortDatasetCollector/1.2 (educational computer-vision project)"
}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
PACKAGING_WORDS = ("carton", "tetra", "brick", "aseptic", "paperboard", "box")
CATEGORIES = (
    ("Flavoured milks", True),
    ("Soy milks", True),
    ("Plant-based beverages", True),
    ("UHT milks", False),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-downloads", type=int, default=60)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--timeout", type=int, default=35)
    parser.add_argument("--delay", type=float, default=6.5)
    parser.add_argument(
        "--category",
        action="append",
        help="Only query this configured category; repeat to select multiple.",
    )
    return parser.parse_args()


def dhash(image: Image.Image) -> str:
    gray = image.convert("L").resize((9, 8), Image.BILINEAR)
    pixels = list(gray.getdata())
    value = 0
    for y in range(8):
        for x in range(8):
            value = (value << 1) | int(pixels[y * 9 + x] > pixels[y * 9 + x + 1])
    return f"{value:016x}"


def known_hashes() -> set[str]:
    hashes = set()
    for root in (BASE_DIR / "dataset", BASE_DIR / "dataset_review"):
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if (
                not path.is_file()
                or path.suffix.lower() not in IMAGE_EXTENSIONS
                or "contact-sheet" in path.name
            ):
                continue
            try:
                with Image.open(path) as image:
                    hashes.add(dhash(image))
            except Exception:
                pass
    return hashes


def load_manifest() -> dict[str, dict]:
    if not PROVENANCE.exists():
        return {}
    records = {}
    for line in PROVENANCE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            records[record["code"]] = record
    return records


def search(category: str, args: argparse.Namespace) -> list[dict]:
    params = {
        "categories_tags_en": category,
        "fields": (
            "code,product_name,product_name_en,brands,countries_tags,"
            "categories_tags,packaging,packaging_tags,packagings,"
            "image_front_url,image_url"
        ),
        "page_size": args.page_size,
    }
    for attempt in range(3):
        try:
            response = requests.get(
                SEARCH_URL, params=params, headers=HEADERS, timeout=args.timeout
            )
            if response.status_code == 200:
                return response.json().get("products", [])
            print(f"[WARN] {category}: HTTP {response.status_code}")
        except requests.RequestException as error:
            print(f"[WARN] {category}: {error}")
        if attempt < 2:
            time.sleep(3 * (attempt + 1))
    return []


def packaging_text(product: dict) -> str:
    values = [
        product.get("packaging", ""),
        product.get("packaging_tags", []),
        product.get("packagings", []),
    ]
    return " ".join(str(value) for value in values).lower()


def is_candidate(product: dict, require_packaging: bool) -> bool:
    image_url = product.get("image_front_url") or product.get("image_url")
    if not product.get("code") or not image_url:
        return False
    if not require_packaging:
        return True
    return any(word in packaging_text(product) for word in PACKAGING_WORDS)


def download(url: str, timeout: int):
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        if len(response.content) < 5_000:
            return None
        image = Image.open(io.BytesIO(response.content)).convert("RGB")
        if min(image.size) < 180:
            return None
        return image, response.content
    except Exception as error:
        print(f"[WARN] image: {error}")
        return None


def make_contact_sheet() -> None:
    paths = sorted(
        path for path in REVIEW_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        and path.name != "_contact-sheet.jpg"
    )
    if not paths:
        return
    size, caption, columns = 180, 30, 5
    rows = (len(paths) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * size, rows * (size + caption)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(paths):
        with Image.open(path) as image:
            image = image.convert("RGB")
            image.thumbnail((size - 12, size - 12))
            x = index % columns * size + (size - image.width) // 2
            y = index // columns * (size + caption) + (size - image.height) // 2
            sheet.paste(image, (x, y))
        draw.text(
            (index % columns * size + 4, index // columns * (size + caption) + size + 4),
            path.stem.split("_")[1],
            fill="black",
        )
    sheet.save(REVIEW_DIR / "_contact-sheet.jpg", quality=90)


def write_outputs(records: dict[str, dict]) -> None:
    PROVENANCE.parent.mkdir(parents=True, exist_ok=True)
    PROVENANCE.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False) + "\n"
            for record in sorted(records.values(), key=lambda item: item["code"])
        ),
        encoding="utf-8",
    )
    counts = {}
    for record in records.values():
        counts[record["category_query"]] = counts.get(record["category_query"], 0) + 1
    lines = [
        "# Structured milk-carton collection",
        "",
        f"- Review candidates: {len(records)}",
        "- Source: Open Food Facts API v2",
        "- Status: pending visual package review; not yet training data.",
        "",
        "| Query | Candidates |",
        "| --- | ---: |",
    ]
    lines.extend(f"| {category} | {counts.get(category, 0)} |" for category, _ in CATEGORIES)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    records = load_manifest()
    hashes = known_hashes()
    candidates = {}
    selected_categories = [
        item for item in CATEGORIES
        if not args.category or item[0] in set(args.category)
    ]
    for index, (category, require_packaging) in enumerate(selected_categories):
        products = search(category, args)
        for product in products:
            if is_candidate(product, require_packaging):
                candidates.setdefault(str(product["code"]), (product, category))
        print(
            f"[OK] {category}: products={len(products)}, "
            f"candidates_total={len(candidates)}",
            flush=True,
        )
        if index < len(selected_categories) - 1:
            time.sleep(args.delay)

    added = 0
    for code, (product, category) in candidates.items():
        if len(records) >= args.max_downloads:
            break
        if code in records:
            continue
        image_url = product.get("image_front_url") or product.get("image_url")
        result = download(image_url, args.timeout)
        if not result:
            continue
        image, raw = result
        image_hash = dhash(image)
        if image_hash in hashes:
            continue
        content_hash = hashlib.sha256(raw).hexdigest()
        destination = REVIEW_DIR / f"off_{code}_{content_hash[:10]}.jpg"
        image.save(destination, "JPEG", quality=92, optimize=True)
        hashes.add(image_hash)
        records[code] = {
            "group": "milk_carton",
            "code": code,
            "product_name": product.get("product_name_en") or product.get("product_name"),
            "brands": product.get("brands"),
            "category_query": category,
            "countries_tags": product.get("countries_tags"),
            "packaging": product.get("packaging"),
            "packaging_tags": product.get("packaging_tags"),
            "local_file": destination.relative_to(BASE_DIR).as_posix(),
            "image_url": image_url,
            "product_url": f"https://world.openfoodfacts.org/product/{code}",
            "license": "CC BY-SA (Open Food Facts product images)",
            "sha256": content_hash,
            "dhash": image_hash,
            "review_status": "pending",
        }
        added += 1
    write_outputs(records)
    make_contact_sheet()
    print(f"[DONE] added={added}, review_total={len(records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
