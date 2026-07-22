#!/usr/bin/env python3
"""Collect extra images for underrepresented trash classes."""

import hashlib
import io
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from PIL import Image
from tqdm import tqdm

BASE_DIR = Path(__file__).parent
DATASET_DIR = BASE_DIR / "dataset"
TARGET = 200
WORKERS = 8
TIMEOUT = 15
MIN_BYTES = 5_000
MIN_PX = 96
HEADERS = {
    "User-Agent": "TrashSorter-TargetedCollector/1.0 (educational; non-commercial)"
}

TARGET_CLASSES = {
    "pen": [
        "ballpoint pen isolated",
        "broken ballpoint pen",
        "used ballpoint pen",
        "plastic pen on table",
        "discarded pen",
        "old pen waste",
        "blue ballpoint pen",
        "pen cap plastic",
        "cheap plastic pens",
        "writing pen close up",
    ],
    "aerosol": [
        "aerosol spray can",
        "empty spray can",
        "spray paint can",
        "insecticide spray can",
        "deodorant aerosol can",
        "air freshener spray can",
        "rusty aerosol can",
        "used aerosol can",
        "paint spray can waste",
    ],
    "styrofoam": [
        "styrofoam food container",
        "foam takeout box",
        "polystyrene food box",
        "disposable foam lunch box",
        "white foam packaging",
        "styrofoam cup waste",
        "foam tray food packaging",
        "expanded polystyrene waste",
    ],
    "metal_fork": [
        "metal fork isolated",
        "old metal fork",
        "bent fork",
        "rusty fork",
        "used spoon fork",
        "stainless steel fork",
        "metal cutlery waste",
        "discarded cutlery",
    ],
    "milk_carton": [
        "milk carton",
        "empty milk carton",
        "tetra pak milk carton",
        "juice carton waste",
        "paper milk box",
        "school milk carton",
        "flattened milk carton",
    ],
    "electronic": [
        "broken phone charger",
        "usb cable waste",
        "old keyboard e waste",
        "broken computer mouse",
        "discarded electronics",
        "electronic waste cable",
        "old power adapter",
        "broken headphones cable",
    ],
    "shampoo_bottle": [
        "empty shampoo bottle",
        "used shampoo bottle",
        "plastic shampoo bottle",
        "empty conditioner bottle",
        "body wash bottle empty",
        "detergent bottle waste",
        "lotion bottle empty",
    ],
}


def image_count(folder: Path) -> int:
    return sum(1 for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})


def wikimedia_urls(query: str, page: int = 0, limit: int = 50) -> list[str]:
    try:
        response = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "generator": "search",
                "gsrnamespace": "6",
                "gsrsearch": f"filetype:jpg {query}",
                "gsrlimit": str(limit),
                "gsroffset": str(page * limit),
                "prop": "imageinfo",
                "iiprop": "url|size|mime",
                "format": "json",
            },
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        urls = []
        for page_data in response.json().get("query", {}).get("pages", {}).values():
            info = page_data.get("imageinfo", [{}])[0]
            url = info.get("url", "")
            mime = info.get("mime", "")
            width = info.get("width", 0)
            height = info.get("height", 0)
            if url and "jpeg" in mime and width >= MIN_PX and height >= MIN_PX:
                urls.append(url)
        return urls
    except Exception:
        return []


def openverse_urls(query: str, page: int = 1, limit: int = 20) -> list[str]:
    try:
        response = requests.get(
            "https://api.openverse.org/v1/images/",
            params={
                "q": query,
                "page": str(page),
                "page_size": str(limit),
                "license_type": "commercial,modification",
                "format": "json",
            },
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        if response.status_code != 200:
            return []
        return [item.get("url", "") for item in response.json().get("results", []) if item.get("url")]
    except Exception:
        return []


def download_one(url: str, dest: Path) -> bool:
    if dest.exists():
        return True
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        if response.status_code != 200:
            return False
        data = response.content
        if len(data) < MIN_BYTES:
            return False
        img = Image.open(io.BytesIO(data)).convert("RGB")
        if img.width < MIN_PX or img.height < MIN_PX:
            return False
        img.save(dest, "JPEG", quality=88, optimize=True)
        return True
    except Exception:
        return False


def collect_class(class_name: str, queries: list[str]) -> None:
    out_dir = DATASET_DIR / class_name
    out_dir.mkdir(parents=True, exist_ok=True)
    current = image_count(out_dir)
    if current >= TARGET:
        print(f"[OK] {class_name:<16} {current} images")
        return

    needed = TARGET - current
    print(f"\n[COLLECT] {class_name}: current={current}, need={needed}")
    urls = []
    for query in queries:
        wm_count = 0
        ov_count = 0
        for page in range(5):
            found = wikimedia_urls(query, page=page)
            wm_count += len(found)
            urls.extend(found)
            time.sleep(0.15)
        for page in range(1, 6):
            found = openverse_urls(query, page=page)
            ov_count += len(found)
            urls.extend(found)
            time.sleep(0.15)
        print(f"  {query}: WM={wm_count} OV={ov_count}")

    unique = list(dict.fromkeys(urls))
    random.shuffle(unique)
    print(f"  unique urls: {len(unique)}")

    downloaded = 0
    with tqdm(total=needed, desc=f"  {class_name}", unit="img", leave=False) as pbar:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {}
            for idx, url in enumerate(unique):
                digest = hashlib.md5(url.encode("utf-8")).hexdigest()[:10]
                dest = out_dir / f"targeted_{current + idx:05d}_{digest}.jpg"
                futures[pool.submit(download_one, url, dest)] = dest
                if len(futures) >= needed * 4:
                    break

            for future in as_completed(futures):
                if future.result():
                    downloaded += 1
                    pbar.update(1)
                if downloaded >= needed:
                    break

    print(f"  downloaded={downloaded}, total={image_count(out_dir)}")


def main() -> None:
    for class_name, queries in TARGET_CLASSES.items():
        collect_class(class_name, queries)


if __name__ == "__main__":
    main()
