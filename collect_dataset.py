#!/usr/bin/env python3
"""
Thu thập ảnh dataset rác thải từ nhiều nguồn public domain.

Nguồn sử dụng (không cần API key):
  1. Wikimedia Commons API  — ảnh CC license
  2. Openverse API           — ảnh CC license (WordPress Foundation)
  3. Unsplash Source         — ảnh free (query-based)
  4. Lorem Picsum            — fallback nếu cần

Cách chạy:
  py -3.7 -m pip install requests pillow tqdm
  py -3.7 collect_dataset.py
"""

import os, sys, io, time, hashlib, json, random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Fix Windows console unicode printing issues
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# ── Tự động cài dependencies ─────────────────────────────────────────────────
def ensure_deps():
    import subprocess
    for pkg, imp in [('requests','requests'), ('Pillow','PIL'), ('tqdm','tqdm')]:
        try:
            __import__(imp)
        except ImportError:
            print(f"Cài {pkg}...")
            subprocess.run([sys.executable,'-m','pip','install','--quiet',pkg], check=True)
ensure_deps()

import requests
from PIL import Image
from tqdm import tqdm

# ── Cấu hình ─────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
DATASET_DIR = BASE_DIR / 'dataset'
TARGET      = 200      # Số ảnh mục tiêu mỗi class (Đã tăng để tải thêm ảnh)
MIN_BYTES   = 5_000    # Bỏ qua < 5 KB
MIN_PX      = 80       # Bỏ qua ảnh nhỏ hơn 80px
WORKERS     = 8
TIMEOUT     = 15

HEADERS = {
    'User-Agent': 'TrashSorter-Dataset-Collector/2.0 (educational; non-commercial)'
}

# ── Class definitions ─────────────────────────────────────────────────────────
# Mỗi class có nhiều từ khoá để tăng số lượng kết quả
CLASSES = {
    # HỮU CƠ (GREEN)
    'banana':         ['banana peel', 'rotten banana', 'discarded banana peel'],
    'apple':          ['apple core', 'rotten apple', 'bitten apple', 'discarded apple'],
    'orange':         ['orange peel', 'mandarin peel', 'citrus peel waste'],
    'egg_shell':      ['egg shell', 'cracked eggshell', 'broken egg'],
    'bread':          ['moldy bread', 'stale bread', 'bread crust', 'piece of bread'],
    'leaf':           ['dry leaf', 'dead leaves', 'fallen leaves', 'lá chuối', 'lá bàng rụng'],
    'bone':           ['chicken bone', 'animal bone', 'leftover bones'],
    'coffee':         ['coffee grounds waste', 'used coffee filter'],
    # TÁI CHẾ (GREEN)
    'bottle':         ['empty plastic water bottle', 'crushed plastic bottle', 'pet bottle'],
    'soda_can':       ['empty soda can', 'crushed aluminum can', 'tin can waste'],
    'newspaper':      ['old newspaper', 'torn newspaper', 'crumpled paper'],
    'cardboard':      ['cardboard box waste', 'torn cardboard', 'corrugated cardboard'],
    'book':           ['old book', 'torn notebook', 'stack of old books'],
    'shampoo_bottle': ['empty shampoo bottle', 'lotion bottle waste', 'detergent bottle'],
    'glass_bottle':   ['empty glass bottle', 'broken glass bottle', 'wine bottle waste'],
    'metal_fork':     ['rusty metal fork', 'old metal spoon', 'bent cutlery'],
    'milk_carton':    ['milk carton waste', 'tetra pak', 'hộp sữa giấy', 'vỏ hộp sữa vinamilk'],
    # VÔ CƠ / RÁC CÒN LẠI (YELLOW)
    'plastic_bag':    ['plastic shopping bag waste', 'plastic bag pollution', 'nylon bag', 'túi bóng kính', 'túi nilon rác'],
    'styrofoam':      ['styrofoam food container', 'polystyrene box waste', 'takeaway foam box'],
    'ceramic':        ['broken ceramic plate', 'shattered porcelain', 'broken bowl'],
    'diaper':         ['used baby diaper', 'soiled diaper waste'],
    'pen':            ['broken ballpoint pen', 'plastic pen waste'],
    'wipe':           ['used wet wipe', 'dirty tissue paper', 'crumpled napkin'],
    'cigarette':      ['cigarette butt', 'cigarette litter', 'smoked cigarette'],
    'chewing_gum':    ['chewed gum', 'bubble gum waste', 'gum on sidewalk'],
    # NGUY HẠI (RED)
    'battery':        ['used aa battery', 'dead alkaline battery', 'corroded battery'],
    'lightbulb':      ['broken lightbulb', 'burnt out fluorescent bulb'],
    'thermometer':    ['mercury thermometer', 'glass thermometer'],
    'chemical_bottle':['empty medicine bottle', 'pill bottle waste', 'medical waste'],
    'electronic':     ['broken phone charger', 'cut usb cable', 'e-waste keyboard'],
    'aerosol':        ['empty aerosol can', 'spray paint can waste']
}

# ── Nguồn 1: Wikimedia Commons ───────────────────────────────────────────────
def wikimedia_urls(query: str, limit=50) -> list:
    urls = []
    try:
        params = {
            'action': 'query',
            'generator': 'search',
            'gsrnamespace': '6',
            'gsrsearch': f'filetype:jpg {query}',
            'gsrlimit': str(min(limit, 50)),
            'prop': 'imageinfo',
            'iiprop': 'url|size|mime',
            'format': 'json',
        }
        r = requests.get(
            'https://commons.wikimedia.org/w/api.php',
            params=params, headers=HEADERS, timeout=20
        )
        for page in r.json().get('query', {}).get('pages', {}).values():
            info = page.get('imageinfo', [{}])[0]
            url  = info.get('url', '')
            mime = info.get('mime', '')
            w, h = info.get('width', 0), info.get('height', 0)
            if url and 'jpeg' in mime and w >= MIN_PX and h >= MIN_PX:
                urls.append(url)
    except Exception as e:
        pass
    return urls

# ── Nguồn 2: Openverse (WordPress / CC Search) ───────────────────────────────
def openverse_urls(query: str, limit=20) -> list:
    urls = []
    try:
        r = requests.get(
            'https://api.openverse.org/v1/images/',
            params={'q': query, 'page_size': str(min(limit,20)),
                    'license_type': 'commercial,modification', 'format': 'json'},
            headers=HEADERS, timeout=20
        )
        if r.status_code == 200:
            for item in r.json().get('results', []):
                url = item.get('url', '')
                if url:
                    urls.append(url)
    except Exception:
        pass
    return urls

# ── Nguồn 3: Flickr CC Search qua Openverse (trang 2) ───────────────────────
def openverse_page2_urls(query: str, limit=20) -> list:
    """Lấy thêm ảnh từ trang 2 Openverse"""
    urls = []
    try:
        r = requests.get(
            'https://api.openverse.org/v1/images/',
            params={'q': query, 'page': '2', 'page_size': str(min(limit,20)),
                    'license_type': 'commercial,modification', 'format': 'json'},
            headers=HEADERS, timeout=20
        )
        if r.status_code == 200:
            for item in r.json().get('results', []):
                url = item.get('url', '')
                if url:
                    urls.append(url)
    except Exception:
        pass
    return urls

# ── Download 1 ảnh ───────────────────────────────────────────────────────────
def download_one(url: str, dest: Path) -> bool:
    if dest.exists():
        return True  # Đã có rồi
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        if r.status_code != 200:
            return False
        data = r.content
        if len(data) < MIN_BYTES:
            return False
        img = Image.open(io.BytesIO(data)).convert('RGB')
        if img.width < MIN_PX or img.height < MIN_PX:
            return False
        img.save(dest, 'JPEG', quality=88, optimize=True)
        return True
    except Exception:
        return False

# ── Thu thập 1 class ─────────────────────────────────────────────────────────
def collect_class(class_name: str, keywords: list, target: int) -> int:
    cls_dir = DATASET_DIR / class_name
    cls_dir.mkdir(parents=True, exist_ok=True)

    current = len(list(cls_dir.glob('*.jpg')))
    if current >= target:
        print(f"  ✅  {class_name:<22} {current} ảnh (đủ)")
        return current

    needed = target - current
    print(f"\n📥 {class_name} — cần {needed} ảnh (hiện có {current})...")

    all_urls = []
    for kw in keywords:
        wm  = wikimedia_urls(kw, limit=40)
        ov  = openverse_urls(kw, limit=20)
        ov2 = openverse_page2_urls(kw, limit=20)
        all_urls += wm + ov + ov2
        print(f"   '{kw}': WM={len(wm)} OV={len(ov)+len(ov2)}")
        time.sleep(0.3)

    # Deduplicate + shuffle
    seen, unique = set(), []
    for u in all_urls:
        if u and u not in seen:
            seen.add(u)
            unique.append(u)
    random.shuffle(unique)

    if not unique:
        print(f"   ⚠️  Không tìm được URL nào!")
        return current

    print(f"   Tổng {len(unique)} URLs duy nhất, tải {needed} ảnh...")

    downloaded = 0
    idx = current
    todo = unique[:max(needed * 5, len(unique))]  # Dự phòng thất bại

    with tqdm(total=needed, desc=f"  {class_name}", unit='img', leave=False) as pbar:
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            batch_size = min(100, len(todo))
            futures = {}

            def submit_batch(start, size):
                for url in todo[start:start+size]:
                    if len(futures) >= needed * 3:
                        break
                    h = hashlib.md5(url.encode()).hexdigest()[:8]
                    dest = cls_dir / f"dl_{idx:05d}_{h}.jpg"
                    futures[ex.submit(download_one, url, dest)] = dest

            submit_batch(0, batch_size)
            submitted = batch_size

            for fut in as_completed(futures):
                if fut.result():
                    downloaded += 1
                    pbar.update(1)
                if downloaded >= needed:
                    break
                # Submit thêm nếu cần
                if submitted < len(todo) and downloaded + (len(futures) - sum(1 for f in futures if f.done())) < needed:
                    next_b = min(50, len(todo) - submitted)
                    if next_b > 0:
                        submit_batch(submitted, next_b)
                        submitted += next_b

    final = len(list(cls_dir.glob('*.jpg')))
    status = "✅" if final >= 50 else ("⚠️ " if final >= 20 else "❌")
    print(f"  {status} {class_name}: tải được {downloaded} → tổng {final} ảnh")
    return final

# ── Verify & xóa ảnh lỗi ────────────────────────────────────────────────────
def verify_all():
    print("\n🔍 Kiểm tra ảnh corrupt...")
    removed = 0
    for cls_dir in sorted(DATASET_DIR.iterdir()):
        if not cls_dir.is_dir():
            continue
        for p in list(cls_dir.glob('*.jpg')):
            try:
                with Image.open(p) as img:
                    img.verify()
                with Image.open(p) as img:
                    img.convert('RGB')
            except Exception:
                p.unlink(missing_ok=True)
                removed += 1
    print(f"  Đã xóa {removed} ảnh lỗi" if removed else "  Tất cả hợp lệ ✅")

# ── Thống kê ─────────────────────────────────────────────────────────────────
def summary():
    print("\n📊 THỐNG KÊ DATASET:")
    print("─" * 45)
    total = 0
    for d in sorted(DATASET_DIR.iterdir()):
        if not d.is_dir():
            continue
        n = len(list(d.glob('*.jpg'))) + len(list(d.glob('*.jpeg')))
        icon = "✅" if n >= 50 else ("⚠️ " if n >= 20 else "❌")
        print(f"  {icon} {d.name:<22} {n:>5} ảnh")
        total += n
    print("─" * 45)
    print(f"  {'TỔNG CỘNG':<22} {total:>5} ảnh")

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("🗑️  THU THẬP DATASET RÁC — Wikimedia + Openverse + DDG")
    print("=" * 55)
    print(f"Thư mục  : {DATASET_DIR}")
    print(f"Mục tiêu : {TARGET} ảnh/class\n")

    for cls_name, keywords in CLASSES.items():
        collect_class(cls_name, keywords, TARGET)

    verify_all()
    summary()

    print("\n✅ XONG! Chạy tiếp:")
    print("   py -3.7 train_dl_model.py")

if __name__ == '__main__':
    main()
