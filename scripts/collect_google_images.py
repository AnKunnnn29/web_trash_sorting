#!/usr/bin/env python3
"""Collect license-filtered Google image results into a manual-review area.

Requires GOOGLE_CSE_API_KEY and GOOGLE_CSE_ID. Search results never go directly
to dataset/: every image remains pending until its object class and source
license have been manually verified.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

import requests
from PIL import Image, ImageDraw


BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "config" / "google-data-queries.json"
REVIEW_ROOT = BASE_DIR / "dataset_review" / "google"
PROVENANCE_PATH = BASE_DIR / "data_provenance" / "google-image-results.jsonl"
REPORT_PATH = BASE_DIR / "reports" / "google-data-collection.md"
SEARCH_ENDPOINT = "https://customsearch.googleapis.com/customsearch/v1"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
HEADERS = {
    "User-Agent": "EcoSortDatasetCollector/1.0 (educational computer-vision project)"
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        action="append",
        help="Target id from config; repeat to select several. Defaults to all.",
    )
    parser.add_argument(
        "--results-per-query",
        type=int,
        default=20,
        help="Requested results per query (1-100, API returns pages of 10).",
    )
    parser.add_argument("--max-downloads-per-target", type=int, default=80)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the plan without requiring credentials or network.",
    )
    return parser.parse_args()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


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


def load_manifest() -> dict[str, dict]:
    if not PROVENANCE_PATH.exists():
        return {}
    records = {}
    for line in PROVENANCE_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            records[record["image_url"]] = record
    return records


def write_manifest(records: dict[str, dict]) -> None:
    PROVENANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROVENANCE_PATH.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False) + "\n"
            for record in sorted(
                records.values(),
                key=lambda item: (item["target_id"], item["image_url"]),
            )
        ),
        encoding="utf-8",
    )


def existing_hashes() -> set[str]:
    hashes = set()
    roots = [BASE_DIR / "dataset", REVIEW_ROOT]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            try:
                with Image.open(path) as image:
                    hashes.add(dhash(image))
            except Exception:
                pass
    return hashes


def google_search(
    query: str,
    config: dict,
    api_key: str,
    engine_id: str,
    result_limit: int,
    timeout: int,
    delay: float,
) -> list[dict]:
    items = []
    for start in range(1, min(result_limit, 100) + 1, 10):
        page_size = min(10, result_limit - len(items))
        response = requests.get(
            SEARCH_ENDPOINT,
            params={
                "key": api_key,
                "cx": engine_id,
                "q": query,
                "searchType": "image",
                "rights": config["licenseFilter"],
                "safe": "active",
                "gl": "vn",
                "hl": "vi",
                "imgSize": "large",
                "num": page_size,
                "start": start,
            },
            headers=HEADERS,
            timeout=timeout,
        )
        if response.status_code != 200:
            try:
                message = response.json().get("error", {}).get("message")
            except Exception:
                message = response.text[:200]
            raise RuntimeError(
                f"Google API failed ({response.status_code}) for {query!r}: {message}"
            )
        page_items = response.json().get("items", [])
        items.extend(page_items)
        if len(page_items) < page_size:
            break
        if len(items) < result_limit:
            time.sleep(delay)
    return items


def download_image(url: str, timeout: int) -> tuple[Image.Image, bytes, str] | None:
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").split(";")[0]
        if not content_type.startswith("image/") or len(response.content) < 8_000:
            return None
        image = Image.open(io.BytesIO(response.content)).convert("RGB")
        if min(image.size) < 256:
            return None
        return image, response.content, content_type
    except Exception as error:
        print(f"[WARN] Download failed {url}: {error}")
        return None


def make_contact_sheet(target_dir: Path) -> None:
    paths = sorted(
        path for path in target_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not paths:
        return
    thumb = 180
    caption = 28
    columns = 5
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
    sheet.save(target_dir / "_contact-sheet.jpg", quality=90)


def collect_target(
    target: dict,
    config: dict,
    args: argparse.Namespace,
    credentials: tuple[str, str],
    manifest: dict[str, dict],
    hashes: set[str],
) -> int:
    api_key, engine_id = credentials
    target_dir = REVIEW_ROOT / target["id"]
    target_dir.mkdir(parents=True, exist_ok=True)
    current_count = sum(
        record["target_id"] == target["id"]
        and record.get("review_status") != "download_failed"
        for record in manifest.values()
    )
    added = 0
    candidates = {}
    for query_index, query in enumerate(target["queries"]):
        for item in google_search(
            query,
            config,
            api_key,
            engine_id,
            args.results_per_query,
            args.timeout,
            args.delay,
        ):
            if item.get("link"):
                candidates[item["link"]] = (item, query)
        if query_index < len(target["queries"]) - 1:
            time.sleep(args.delay)

    for image_url, (item, query) in candidates.items():
        if current_count + added >= args.max_downloads_per_target:
            break
        if image_url in manifest:
            continue
        downloaded = download_image(image_url, args.timeout)
        if not downloaded:
            continue
        image, raw_data, content_type = downloaded
        image_hash = dhash(image)
        if image_hash in hashes:
            continue
        content_hash = hashlib.sha256(raw_data).hexdigest()
        destination = target_dir / f"google_{slug(target['id'])}_{content_hash[:12]}.jpg"
        image.save(destination, "JPEG", quality=92, optimize=True)
        hashes.add(image_hash)
        added += 1
        manifest[image_url] = {
            "provider": config["provider"],
            "target_id": target["id"],
            "expected_label": target["expectedLabel"],
            "query": query,
            "title": item.get("title"),
            "image_url": image_url,
            "context_url": item.get("image", {}).get("contextLink"),
            "display_domain": item.get("displayLink"),
            "mime": item.get("mime") or content_type,
            "source_width": item.get("image", {}).get("width"),
            "source_height": item.get("image", {}).get("height"),
            "license_search_filter": config["licenseFilter"],
            "license_status": "must_verify_on_context_page",
            "local_file": str(destination.relative_to(BASE_DIR)).replace("\\", "/"),
            "sha256": content_hash,
            "dhash": image_hash,
            "review_status": "pending_object_and_license_review",
        }
    make_contact_sheet(target_dir)
    print(
        f"[OK] {target['id']}: candidates={len(candidates)}, "
        f"added={added}, total={current_count + added}"
    )
    return added


def write_report(config: dict, manifest: dict[str, dict]) -> None:
    counts = Counter(record["target_id"] for record in manifest.values())
    lines = [
        "# Google image data collection",
        "",
        f"- Provider: {config['provider']}",
        f"- License search filter: `{config['licenseFilter']}`",
        f"- Downloaded review images: {len(manifest)}",
        "- Promotion policy: manual object and source-license review required.",
        "",
        "| Target | Expected label | Review images | Target | Remaining |",
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
        "A Google license filter is discovery metadata, not final proof. Open each "
        "`context_url` in the provenance manifest and confirm the exact license before "
        "promotion. Search result images must not be copied directly into training.",
        "",
    ])
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args()
    if not 1 <= args.results_per_query <= 100:
        raise SystemExit("--results-per-query must be between 1 and 100")
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    selected_ids = set(args.target or [])
    targets = [
        target for target in config["targets"]
        if not selected_ids or target["id"] in selected_ids
    ]
    unknown = selected_ids - {target["id"] for target in config["targets"]}
    if unknown:
        raise SystemExit(f"Unknown target(s): {', '.join(sorted(unknown))}")
    if args.dry_run:
        print(f"Provider: {config['provider']}")
        print(f"License filter: {config['licenseFilter']}")
        for target in targets:
            print(
                f"- {target['id']} -> {target['expectedLabel']}: "
                f"{len(target['queries'])} queries"
            )
            for query in target["queries"]:
                print(f"    {query}")
        return

    api_key = os.environ.get("GOOGLE_CSE_API_KEY", "").strip()
    engine_id = os.environ.get("GOOGLE_CSE_ID", "").strip()
    if not api_key or not engine_id:
        raise SystemExit(
            "Missing GOOGLE_CSE_API_KEY or GOOGLE_CSE_ID. "
            "Use --dry-run to inspect the plan without credentials."
        )
    REVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    hashes = existing_hashes()
    for target in targets:
        collect_target(
            target,
            config,
            args,
            (api_key, engine_id),
            manifest,
            hashes,
        )
        write_manifest(manifest)
        write_report(config, manifest)
    print(f"Review root: {REVIEW_ROOT}")
    print(f"Provenance: {PROVENANCE_PATH}")
    print(f"Coverage report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
