#!/usr/bin/env python3
"""Collect openly licensed images from Openverse and Wikimedia Commons."""

from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import requests
from PIL import Image, ImageDraw


BASE_DIR = Path(__file__).resolve().parents[1]
QUERY_CONFIG = BASE_DIR / "config" / "google-data-queries.json"
REVIEW_ROOT = BASE_DIR / "dataset_review" / "open_images"
PROVENANCE_PATH = BASE_DIR / "data_provenance" / "open-images.jsonl"
REPORT_PATH = BASE_DIR / "reports" / "open-image-collection.md"
OPENVERSE_URL = "https://api.openverse.org/v1/images/"
COMMONS_URL = "https://commons.wikimedia.org/w/api.php"
HEADERS = {
    "User-Agent": "EcoSortDatasetCollector/1.0 (educational computer-vision project)"
}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", action="append")
    parser.add_argument("--results-per-query", type=int, default=8)
    parser.add_argument("--max-downloads-per-target", type=int, default=25)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--query", action="append", help="Override configured queries.")
    parser.add_argument(
        "--provider",
        choices=["all", "openverse", "wikimedia"],
        default="all",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def clean_html(value: object) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


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


def existing_hashes() -> set[str]:
    hashes = set()
    for root in (BASE_DIR / "dataset", REVIEW_ROOT):
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if (
                not path.is_file()
                or path.name.startswith("_")
                or path.suffix.lower() not in IMAGE_EXTENSIONS
            ):
                continue
            try:
                with Image.open(path) as image:
                    hashes.add(dhash(image))
            except Exception:
                pass
    return hashes


def load_manifest() -> dict[str, dict]:
    if not PROVENANCE_PATH.exists():
        return {}
    records = {}
    for line in PROVENANCE_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            records[f"{record['provider']}:{record['source_id']}"] = record
    return records


def write_manifest(records: dict[str, dict]) -> None:
    PROVENANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROVENANCE_PATH.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False) + "\n"
            for record in sorted(
                records.values(),
                key=lambda item: (
                    item["target_id"], item["provider"], item["source_id"]
                ),
            )
        ),
        encoding="utf-8",
    )


def search_openverse(query: str, limit: int, timeout: int) -> list[dict]:
    response = requests.get(
        OPENVERSE_URL,
        params={
            "q": query,
            "page_size": min(limit, 20),
            "license_type": "commercial,modification",
            "mature": "false",
        },
        headers=HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    results = []
    for item in response.json().get("results", [])[:limit]:
        if not item.get("url"):
            continue
        results.append({
            "provider": "openverse",
            "source_id": item.get("id") or item["url"],
            "title": item.get("title"),
            "image_url": item["url"],
            "context_url": item.get("foreign_landing_url"),
            "creator": item.get("creator"),
            "creator_url": item.get("creator_url"),
            "license": item.get("license"),
            "license_version": item.get("license_version"),
            "license_url": item.get("license_url"),
            "source_collection": item.get("source"),
            "width": item.get("width"),
            "height": item.get("height"),
        })
    return results


def search_commons(query: str, limit: int, timeout: int) -> list[dict]:
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": min(limit, 20),
        "prop": "imageinfo",
        "iiprop": "url|mime|extmetadata",
        "iiurlwidth": "1024",
        "format": "json",
        "formatversion": 2,
    }
    response = requests.get(
        COMMONS_URL, params=params, headers=HEADERS, timeout=timeout
    )
    if response.status_code == 429:
        time.sleep(3)
        response = requests.get(
            COMMONS_URL, params=params, headers=HEADERS, timeout=timeout
        )
    if response.status_code == 429:
        print(f"[WARN] Wikimedia rate-limited query {query!r}; skipped")
        return []
    response.raise_for_status()
    results = []
    for page in response.json().get("query", {}).get("pages", []):
        info = (page.get("imageinfo") or [{}])[0]
        metadata = info.get("extmetadata") or {}
        image_url = info.get("thumburl") or info.get("url")
        if not image_url or not str(info.get("mime", "")).startswith("image/"):
            continue
        license_name = metadata.get("LicenseShortName", {}).get("value", "")
        normalized_license = license_name.upper()
        if not (
            "CC" in normalized_license
            or "PUBLIC DOMAIN" in normalized_license
            or normalized_license == "PD"
        ):
            continue
        results.append({
            "provider": "wikimedia_commons",
            "source_id": str(page.get("pageid") or page.get("title")),
            "title": page.get("title"),
            "image_url": image_url,
            "context_url": info.get("descriptionurl"),
            "creator": clean_html(metadata.get("Artist", {}).get("value")),
            "creator_url": None,
            "license": license_name,
            "license_version": None,
            "license_url": metadata.get("LicenseUrl", {}).get("value"),
            "source_collection": "wikimedia_commons",
            "width": info.get("width"),
            "height": info.get("height"),
        })
    return results[:limit]


def download(url: str, timeout: int) -> tuple[Image.Image, bytes] | None:
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        if response.status_code == 429:
            time.sleep(2)
            response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("image/") or len(response.content) < 8_000:
            return None
        image = Image.open(io.BytesIO(response.content)).convert("RGB")
        if min(image.size) < 256:
            return None
        return image, response.content
    except Exception as error:
        print(f"[WARN] {url}: {error}")
        return None


def make_contact_sheet(folder: Path) -> None:
    paths = sorted(
        path for path in folder.iterdir()
        if path.is_file()
        and not path.name.startswith("_")
        and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not paths:
        return
    thumb, caption, columns = 180, 28, 5
    rows = (len(paths) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb, rows * (thumb + caption)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(paths):
        with Image.open(path) as source:
            image = source.convert("RGB")
            image.thumbnail((thumb - 12, thumb - 12))
            x = (index % columns) * thumb + (thumb - image.width) // 2
            y = (index // columns) * (thumb + caption) + (thumb - image.height) // 2
            sheet.paste(image, (x, y))
        draw.text(
            (
                (index % columns) * thumb + 5,
                (index // columns) * (thumb + caption) + thumb + 4,
            ),
            path.stem[-16:],
            fill="black",
        )
    sheet.save(folder / "_contact-sheet.jpg", quality=90)


def collect_target(
    target: dict,
    args: argparse.Namespace,
    manifest: dict[str, dict],
    hashes: set[str],
) -> int:
    folder = REVIEW_ROOT / target["id"]
    folder.mkdir(parents=True, exist_ok=True)
    current = sum(
        record["target_id"] == target["id"] for record in manifest.values()
    )
    candidates = {}
    for query in args.query or target["queries"]:
        searches = []
        if args.provider in {"all", "openverse"}:
            searches.append(
                search_openverse(query, args.results_per_query, args.timeout)
            )
        if args.provider in {"all", "wikimedia"}:
            searches.append(
                search_commons(query, args.results_per_query, args.timeout)
            )
        for items in searches:
            for item in items:
                item["query"] = query
                candidates[f"{item['provider']}:{item['source_id']}"] = item

    added = 0
    for key, item in candidates.items():
        if current + added >= args.max_downloads_per_target:
            break
        if key in manifest:
            continue
        result = download(item["image_url"], args.timeout)
        if not result:
            continue
        image, raw = result
        image_hash = dhash(image)
        if image_hash in hashes:
            continue
        content_hash = hashlib.sha256(raw).hexdigest()
        destination = folder / f"{item['provider']}_{content_hash[:12]}.jpg"
        image.save(destination, "JPEG", quality=92, optimize=True)
        hashes.add(image_hash)
        added += 1
        manifest[key] = {
            **item,
            "target_id": target["id"],
            "expected_label": target["expectedLabel"],
            "local_file": str(destination.relative_to(BASE_DIR)).replace("\\", "/"),
            "sha256": content_hash,
            "dhash": image_hash,
            "review_status": "pending_object_review",
        }
    make_contact_sheet(folder)
    print(
        f"[OK] {target['id']}: candidates={len(candidates)}, "
        f"added={added}, total={current + added}"
    )
    return added


def write_report(config: dict, records: dict[str, dict]) -> None:
    counts = Counter(record["target_id"] for record in records.values())
    providers = Counter(record["provider"] for record in records.values())
    lines = [
        "# Open image collection",
        "",
        f"- Review images: {len(records)}",
        f"- Providers: {dict(providers)}",
        "- Sources: Openverse and Wikimedia Commons",
        "- Status: pending object review; not promoted to training.",
        "",
        "| Target | Expected | Review images | Desired | Remaining |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for target in config["targets"]:
        count = counts[target["id"]]
        desired = target["targetReviewImages"]
        lines.append(
            f"| {target['id']} | {target['expectedLabel']} | {count} | "
            f"{desired} | {max(0, desired - count)} |"
        )
    lines.extend([
        "",
        "License, creator and source-page metadata are retained in "
        "`data_provenance/open-images.jsonl`. Review contact sheets and reject "
        "irrelevant search results before promotion.",
        "",
    ])
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args()
    config = json.loads(QUERY_CONFIG.read_text(encoding="utf-8"))
    selected = set(args.target or [])
    targets = [
        target for target in config["targets"]
        if not selected or target["id"] in selected
    ]
    unknown = selected - {target["id"] for target in config["targets"]}
    if unknown:
        raise SystemExit(f"Unknown target(s): {', '.join(sorted(unknown))}")
    if args.dry_run:
        for target in targets:
            print(f"{target['id']}: {len(target['queries'])} queries")
        return
    REVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    hashes = existing_hashes()
    for target in targets:
        try:
            collect_target(target, args, manifest, hashes)
        except Exception as error:
            print(f"[WARN] Target {target['id']} failed: {error}")
        write_manifest(manifest)
        write_report(config, manifest)
    print(f"Review root: {REVIEW_ROOT}")
    print(f"Provenance: {PROVENANCE_PATH}")
    print(f"Report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
