#!/usr/bin/env python3
"""Collect openly licensed boxed-milk images brand by brand for review."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw


BASE_DIR = Path(__file__).resolve().parents[1]
CATALOG_PATH = BASE_DIR / "config" / "vietnam-boxed-milk-brands.json"
REVIEW_ROOT = BASE_DIR / "dataset_review" / "boxed_milk_brands"
PROVENANCE_PATH = (
    BASE_DIR / "data_provenance" / "openfoodfacts-boxed-milk-brands.jsonl"
)
REPORT_PATH = BASE_DIR / "reports" / "vietnam-boxed-milk-brand-coverage.md"
SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"
HEADERS = {
    "User-Agent": "EcoSortDatasetCollector/1.1 (educational computer-vision project)"
}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
INCLUDE = ("milk", "sữa", "lait", "leche", "latte", "milo", "ovaltine", "fami", "soja", "soy")
EXCLUDE = (
    "powder", "bột", "condensed", "đặc", "yogurt cup", "sữa chua ăn",
    "butter", "cheese", "ice cream", "chocolate bar",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-per-brand", type=int, default=6)
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--delay", type=float, default=6.5)
    parser.add_argument(
        "--brand",
        action="append",
        help="Only collect this brand slug; repeat to select multiple brands.",
    )
    return parser.parse_args()


def normalize_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def dhash(image: Image.Image) -> str:
    grayscale = image.convert("L").resize((9, 8), Image.BILINEAR)
    pixels = list(grayscale.getdata())
    value = 0
    for y in range(8):
        for x in range(8):
            value = (value << 1) | int(
                pixels[y * 9 + x] > pixels[y * 9 + x + 1]
            )
    return f"{value:016x}"


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
                "packaging,packaging_tags,image_front_url,image_url"
            ),
        },
        headers=HEADERS,
        timeout=timeout,
    )
    if response.status_code != 200:
        print(f"[WARN] Search failed for {query!r}: HTTP {response.status_code}")
        return []
    return response.json().get("products", [])


def is_candidate(product: dict) -> bool:
    text = normalize_text(" ".join([
        str(product.get("product_name", "")),
        str(product.get("product_name_vi", "")),
        str(product.get("brands", "")),
        str(product.get("packaging", "")),
        " ".join(product.get("packaging_tags") or []),
    ]))
    return (
        any(keyword in text for keyword in INCLUDE)
        and not any(keyword in text for keyword in EXCLUDE)
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


def read_manifest() -> dict[tuple[str, str], dict]:
    records = {}
    if not PROVENANCE_PATH.exists():
        return records
    for line in PROVENANCE_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            records[(record["brand_slug"], record["code"])] = record
    return records


def write_manifest(records: dict[tuple[str, str], dict]) -> None:
    PROVENANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(records.values(), key=lambda item: (item["brand_slug"], item["code"]))
    PROVENANCE_PATH.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in ordered),
        encoding="utf-8",
    )


def existing_hashes() -> set[str]:
    hashes = set()
    for path in REVIEW_ROOT.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            try:
                with Image.open(path) as image:
                    hashes.add(dhash(image))
            except Exception:
                pass
    return hashes


def make_contact_sheet(folder: Path) -> None:
    paths = sorted(
        path for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not paths:
        return
    thumb = 200
    caption = 30
    columns = 4
    rows = (len(paths) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb, rows * (thumb + caption)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(paths):
        with Image.open(path) as image:
            image = image.convert("RGB")
            image.thumbnail((thumb - 12, thumb - 12))
            x = (index % columns) * thumb + (thumb - image.width) // 2
            y = (index // columns) * (thumb + caption) + (thumb - image.height) // 2
            sheet.paste(image, (x, y))
        draw.text(
            ((index % columns) * thumb + 5, (index // columns) * (thumb + caption) + thumb + 5),
            path.stem.split("_")[1],
            fill="black",
        )
    sheet.save(folder / "_contact-sheet.jpg", quality=90)


def collect_brand(brand: dict, args: argparse.Namespace, manifest: dict, hashes: set[str]) -> int:
    folder = REVIEW_ROOT / brand["slug"]
    folder.mkdir(parents=True, exist_ok=True)
    existing_codes = {
        code for (slug, code), record in manifest.items()
        if slug == brand["slug"] and (BASE_DIR / record["local_file"]).exists()
    }
    candidates = {}
    for query_index, query in enumerate(brand["queries"]):
        for product in search_products(query, args.page_size, args.timeout):
            if product.get("code") and is_candidate(product):
                candidates[str(product["code"])] = (product, query)
        if query_index < len(brand["queries"]) - 1:
            time.sleep(args.delay)

    added = 0
    for code, (product, query) in sorted(candidates.items()):
        if len(existing_codes) + added >= args.max_per_brand:
            break
        if code in existing_codes:
            continue
        image_url = product.get("image_front_url") or product.get("image_url")
        result = download_image(image_url, args.timeout)
        if not result:
            continue
        image, raw_data = result
        image_hash = dhash(image)
        if image_hash in hashes:
            continue
        content_hash = hashlib.sha256(raw_data).hexdigest()
        destination = folder / f"off_{code}_{content_hash[:10]}.jpg"
        image.save(destination, "JPEG", quality=92, optimize=True)
        hashes.add(image_hash)
        added += 1
        manifest[(brand["slug"], code)] = {
            "group": "milk_carton",
            "brand": brand["name"],
            "brand_slug": brand["slug"],
            "segment": brand["segment"],
            "code": code,
            "product_name": product.get("product_name_vi") or product.get("product_name"),
            "openfoodfacts_brands": product.get("brands"),
            "search_query": query,
            "local_file": str(destination.relative_to(BASE_DIR)).replace("\\", "/"),
            "image_url": image_url,
            "product_url": f"https://world.openfoodfacts.org/product/{quote(code)}",
            "market_verification_url": brand["verificationUrl"],
            "license": "CC BY-SA (Open Food Facts product images)",
            "sha256": content_hash,
            "dhash": image_hash,
            "review_status": "pending",
        }
    make_contact_sheet(folder)
    print(
        f"[OK] {brand['name']}: candidates={len(candidates)}, "
        f"added={added}, total={len(existing_codes) + added}"
    )
    return added


def write_report(catalog: dict, records: dict[tuple[str, str], dict]) -> None:
    counts = Counter(record["brand_slug"] for record in records.values())
    approved = Counter(
        record["brand_slug"] for record in records.values()
        if record["review_status"] == "approved"
    )
    lines = [
        "# Vietnamese boxed-milk brand coverage",
        "",
        f"- Checked at: {catalog['checkedAt']}",
        f"- Catalog brands: {len(catalog['brands'])}",
        f"- Openly licensed review images: {len(records)}",
        f"- Approved training images from this catalog: {sum(approved.values())}",
        "",
        "| Brand | Segment | Review images | Approved | Status |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for brand in catalog["brands"]:
        count = counts[brand["slug"]]
        status = "review pending" if count else "licensed image gap"
        if approved[brand["slug"]]:
            status = "added to dataset"
        lines.append(
            f"| [{brand['name']}]({brand['verificationUrl']}) | {brand['segment']} | "
            f"{count} | {approved[brand['slug']]} | {status} |"
        )
    lines.extend([
        "",
        "Official/retailer product pages verify market presence only. They are not copied "
        "into the training set. Training candidates here come from Open Food Facts under "
        "CC BY-SA and still require package-shape and duplicate review.",
        "",
    ])
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args()
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    selected = set(args.brand or [])
    brands = [
        brand for brand in catalog["brands"]
        if not selected or brand["slug"] in selected
    ]
    unknown = selected - {brand["slug"] for brand in catalog["brands"]}
    if unknown:
        raise SystemExit(f"Unknown brand slug(s): {', '.join(sorted(unknown))}")
    REVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest()
    hashes = existing_hashes()
    for index, brand in enumerate(brands):
        collect_brand(brand, args, manifest, hashes)
        write_manifest(manifest)
        write_report(catalog, manifest)
        if index < len(brands) - 1:
            time.sleep(args.delay)
    print(f"Review root: {REVIEW_ROOT}")
    print(f"Coverage report: {REPORT_PATH}")
    print(f"Attribution manifest: {PROVENANCE_PATH}")


if __name__ == "__main__":
    main()
