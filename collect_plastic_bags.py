"""
Script thu thập dataset cho túi nilong (plastic bags)
Sử dụng Wikimedia Commons và Openverse API
"""

import os
import requests
import hashlib
import time
from pathlib import Path

# Cấu hình
OUTPUT_DIR = "dataset/plastic_bag"
TARGET_COUNT = 250  # Số lượng ảnh mục tiêu
DELAY_BETWEEN_REQUESTS = 0.5  # Delay giữa các request (giây)

# Từ khóa tìm kiếm (tiếng Anh và tiếng Việt)
SEARCH_KEYWORDS = [
    "plastic bag",
    "shopping bag plastic",
    "grocery bag plastic",
    "polythene bag",
    "carry bag plastic",
    "plastic shopping bag white",
    "plastic bag trash",
    "plastic bag waste",
    "plastic bag pollution",
    "disposable plastic bag",
    "supermarket plastic bag",
    "transparent plastic bag",
    "black plastic bag",
    "white plastic bag",
    "plastic bag close up",
]

def setup_output_dir():
    """Tạo thư mục output nếu chưa có"""
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    print(f"✅ Thư mục lưu trữ: {OUTPUT_DIR}")

def get_existing_count():
    """Đếm số ảnh đã có trong thư mục"""
    if not os.path.exists(OUTPUT_DIR):
        return 0
    files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith(('.jpg', '.jpeg', '.png'))]
    return len(files)

def download_image(url, filename):
    """Download ảnh từ URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10, stream=True)
        response.raise_for_status()
        
        # Kiểm tra content type
        content_type = response.headers.get('content-type', '')
        if 'image' not in content_type.lower():
            print(f"  ⚠️  Không phải ảnh: {content_type}")
            return False
        
        # Lưu file
        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Kiểm tra kích thước file
        file_size = os.path.getsize(filepath)
        if file_size < 5000:  # Nhỏ hơn 5KB có thể là ảnh lỗi
            os.remove(filepath)
            print(f"  ⚠️  Ảnh quá nhỏ ({file_size} bytes)")
            return False
        
        return True
    except Exception as e:
        print(f"  ❌ Lỗi download: {str(e)[:50]}")
        return False

def search_wikimedia_commons(keyword, max_results=30):
    """Tìm kiếm ảnh từ Wikimedia Commons"""
    print(f"\n🔍 Wikimedia Commons: '{keyword}'")
    
    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": "6",  # File namespace
        "gsrsearch": keyword,
        "gsrlimit": max_results,
        "prop": "imageinfo",
        "iiprop": "url|size",
        "iiurlwidth": 800,
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if "query" not in data or "pages" not in data["query"]:
            print("  ⚠️  Không tìm thấy kết quả")
            return []
        
        images = []
        for page in data["query"]["pages"].values():
            if "imageinfo" in page and len(page["imageinfo"]) > 0:
                info = page["imageinfo"][0]
                if "url" in info:
                    images.append(info["url"])
        
        print(f"  ✅ Tìm thấy {len(images)} ảnh")
        return images
    
    except Exception as e:
        print(f"  ❌ Lỗi API: {str(e)[:60]}")
        return []

def search_openverse(keyword, max_results=30):
    """Tìm kiếm ảnh từ Openverse (Creative Commons)"""
    print(f"\n🔍 Openverse: '{keyword}'")
    
    url = "https://api.openverse.engineering/v1/images/"
    params = {
        "q": keyword,
        "page_size": max_results,
        "license": "cc0,pdm,by,by-sa",  # Các license cho phép sử dụng
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if "results" not in data:
            print("  ⚠️  Không tìm thấy kết quả")
            return []
        
        images = [item["url"] for item in data["results"] if "url" in item]
        print(f"  ✅ Tìm thấy {len(images)} ảnh")
        return images
    
    except Exception as e:
        print(f"  ❌ Lỗi API: {str(e)[:60]}")
        return []

def generate_filename(url, keyword):
    """Tạo tên file duy nhất từ URL"""
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    keyword_clean = keyword.replace(" ", "_").replace("/", "_")[:20]
    return f"plastic_bag_{keyword_clean}_{url_hash}.jpg"

def main():
    print("=" * 70)
    print("🛍️  SCRIPT THU THẬP DATASET: TÚI NILONG (PLASTIC BAGS)")
    print("=" * 70)
    
    setup_output_dir()
    
    existing = get_existing_count()
    print(f"\n📊 Trạng thái hiện tại: {existing}/{TARGET_COUNT} ảnh")
    
    if existing >= TARGET_COUNT:
        print("✅ Đã đủ số lượng ảnh mục tiêu!")
        return
    
    needed = TARGET_COUNT - existing
    print(f"🎯 Cần thu thập thêm: {needed} ảnh\n")
    
    downloaded = 0
    all_image_urls = []
    
    # Thu thập URLs từ cả 2 nguồn
    for keyword in SEARCH_KEYWORDS:
        if downloaded >= needed:
            break
        
        # Wikimedia Commons
        wikimedia_urls = search_wikimedia_commons(keyword, max_results=20)
        all_image_urls.extend(wikimedia_urls)
        
        time.sleep(DELAY_BETWEEN_REQUESTS)
        
        # Openverse
        openverse_urls = search_openverse(keyword, max_results=20)
        all_image_urls.extend(openverse_urls)
        
        time.sleep(DELAY_BETWEEN_REQUESTS)
    
    # Loại bỏ URLs trùng lặp
    all_image_urls = list(set(all_image_urls))
    print(f"\n📥 Tổng số URL thu thập được: {len(all_image_urls)}")
    print("⬇️  Bắt đầu download...\n")
    
    # Download từng ảnh
    for idx, url in enumerate(all_image_urls, 1):
        if downloaded >= needed:
            break
        
        print(f"[{idx}/{len(all_image_urls)}] {url[:60]}...")
        
        # Tạo tên file
        keyword_for_file = SEARCH_KEYWORDS[idx % len(SEARCH_KEYWORDS)]
        filename = generate_filename(url, keyword_for_file)
        
        # Kiểm tra file đã tồn tại chưa
        filepath = os.path.join(OUTPUT_DIR, filename)
        if os.path.exists(filepath):
            print("  ⏭️  Đã tồn tại, bỏ qua")
            continue
        
        # Download
        if download_image(url, filename):
            downloaded += 1
            print(f"  ✅ Thành công! ({existing + downloaded}/{TARGET_COUNT})")
        
        time.sleep(DELAY_BETWEEN_REQUESTS)
    
    # Tổng kết
    print("\n" + "=" * 70)
    print("📊 KẾT QUẢ THU THẬP")
    print("=" * 70)
    final_count = get_existing_count()
    print(f"✅ Tổng số ảnh hiện có: {final_count}/{TARGET_COUNT}")
    print(f"📥 Đã download trong lần chạy này: {downloaded}")
    
    if final_count >= TARGET_COUNT:
        print("🎉 Hoàn thành thu thập dataset cho túi nilong!")
    else:
        remaining = TARGET_COUNT - final_count
        print(f"⚠️  Còn thiếu {remaining} ảnh. Chạy lại script để tiếp tục.")
    
    print(f"\n📁 Thư mục dataset: {os.path.abspath(OUTPUT_DIR)}")
    print("\n💡 Bước tiếp theo:")
    print("   1. Kiểm tra chất lượng ảnh trong thư mục")
    print("   2. Xóa các ảnh không phù hợp (nếu có)")
    print("   3. Chạy lại script nếu cần thêm ảnh")
    print("   4. Train lại model: py -3.7 train_dl_model.py")
    print("=" * 70)

if __name__ == "__main__":
    main()
