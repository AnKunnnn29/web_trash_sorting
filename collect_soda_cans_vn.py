#!/usr/bin/env python3
"""
Thu thập ảnh lon nước ngọt các thương hiệu phổ biến tại Việt Nam
Mục tiêu: 200-300 ảnh để train model nhận diện chính xác

Brands:
- Coca Cola, Pepsi, 7Up, Sprite, Fanta
- Sting, Number 1, Red Bull, Monster
- C2, Revive, Aquafina
- Trà xanh 0 độ, Lipton
"""

import os
import sys
import time
import json
import requests
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATASET_DIR = BASE_DIR / 'dataset'
OUTPUT_DIR = DATASET_DIR / 'soda_can'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Keywords tìm kiếm (tiếng Việt + tiếng Anh)
SEARCH_QUERIES = [
    # Các thương hiệu quốc tế
    'coca cola can vietnam',
    'pepsi can vietnam',
    'sprite can',
    '7up can',
    'fanta orange can',
    'mountain dew can',
    
    # Thương hiệu Việt Nam
    'sting energy drink can',
    'number 1 energy drink vietnam',
    'revive isotonic can vietnam',
    'c2 tea can vietnam',
    'lipton tea can vietnam',
    'tra xanh 0 do can',
    
    # Các từ khóa chung
    'aluminum can soda',
    'soft drink can',
    'energy drink can',
    'soda can recycling',
    'empty soda can',
    'crushed soda can',
    'soda can top view',
    'aluminum beverage can',
]

TARGET_IMAGES = 250  # Mục tiêu thu thập
downloaded = 0

def download_from_wikimedia(query, max_results=30):
    """Thu thập từ Wikimedia Commons"""
    global downloaded
    
    print(f"\n[Wikimedia] Searching: {query}")
    
    url = 'https://commons.wikimedia.org/w/api.php'
    params = {
        'action': 'query',
        'format': 'json',
        'generator': 'search',
        'gsrsearch': f'filemime:image {query}',
        'gsrlimit': max_results,
        'prop': 'imageinfo',
        'iiprop': 'url|size',
        'iiurlwidth': 640
    }
    
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        
        if 'query' not in data or 'pages' not in data['query']:
            print(f"  No results")
            return
        
        pages = data['query']['pages']
        count = 0
        
        for page_id, page in pages.items():
            if downloaded >= TARGET_IMAGES:
                break
                
            if 'imageinfo' not in page:
                continue
            
            info = page['imageinfo'][0]
            img_url = info.get('thumburl') or info.get('url')
            
            if not img_url:
                continue
            
            # Download
            try:
                img_res = requests.get(img_url, timeout=10)
                if img_res.status_code == 200:
                    # Generate unique filename
                    ext = img_url.split('.')[-1].split('?')[0]
                    if ext not in ['jpg', 'jpeg', 'png']:
                        ext = 'jpg'
                    
                    filename = f'wm_{downloaded:05d}_{page_id}.{ext}'
                    filepath = OUTPUT_DIR / filename
                    
                    with open(filepath, 'wb') as f:
                        f.write(img_res.content)
                    
                    downloaded += 1
                    count += 1
                    print(f"  [{downloaded}/{TARGET_IMAGES}] {filename}")
                    time.sleep(0.5)
                    
            except Exception as e:
                print(f"  Error downloading: {e}")
                continue
        
        print(f"  Downloaded {count} images from this query")
        
    except Exception as e:
        print(f"  Error: {e}")

def download_from_openverse(query, max_results=30):
    """Thu thập từ Openverse"""
    global downloaded
    
    print(f"\n[Openverse] Searching: {query}")
    
    url = 'https://api.openverse.org/v1/images/'
    headers = {
        'User-Agent': 'TrashSortingSTEAM/1.0 (Educational Project)'
    }
    params = {
        'q': query,
        'page_size': max_results,
        'license': 'cc0,pdm,by,by-sa,by-nc,by-nd,by-nc-sa,by-nc-nd',
    }
    
    try:
        res = requests.get(url, params=params, headers=headers, timeout=10)
        data = res.json()
        
        if 'results' not in data or len(data['results']) == 0:
            print(f"  No results")
            return
        
        count = 0
        
        for item in data['results']:
            if downloaded >= TARGET_IMAGES:
                break
            
            img_url = item.get('url')
            if not img_url:
                continue
            
            # Download
            try:
                img_res = requests.get(img_url, timeout=10, headers=headers)
                if img_res.status_code == 200:
                    # Generate filename
                    item_id = item.get('id', 'unknown')
                    ext = img_url.split('.')[-1].split('?')[0].lower()
                    if ext not in ['jpg', 'jpeg', 'png']:
                        ext = 'jpg'
                    
                    filename = f'ov_{downloaded:05d}_{item_id[:8]}.{ext}'
                    filepath = OUTPUT_DIR / filename
                    
                    with open(filepath, 'wb') as f:
                        f.write(img_res.content)
                    
                    downloaded += 1
                    count += 1
                    print(f"  [{downloaded}/{TARGET_IMAGES}] {filename}")
                    time.sleep(0.5)
                    
            except Exception as e:
                continue
        
        print(f"  Downloaded {count} images from this query")
        
    except Exception as e:
        print(f"  Error: {e}")

def main():
    print('=' * 70)
    print('Thu thập ảnh LON NƯỚC NGỌT VIỆT NAM')
    print('=' * 70)
    print(f'Output: {OUTPUT_DIR}')
    print(f'Target: {TARGET_IMAGES} images')
    print(f'Current: {len(list(OUTPUT_DIR.glob("*.jpg")) + list(OUTPUT_DIR.glob("*.png")))} images')
    print()
    
    # Đếm ảnh hiện có
    global downloaded
    existing = list(OUTPUT_DIR.glob('wm_*.jpg')) + list(OUTPUT_DIR.glob('ov_*.jpg'))
    downloaded = len(existing)
    
    if downloaded >= TARGET_IMAGES:
        print(f'✅ Already have {downloaded} images. Target reached!')
        return
    
    print(f'Starting from {downloaded} existing images...\n')
    
    # Thu thập từ cả 2 nguồn
    for query in SEARCH_QUERIES:
        if downloaded >= TARGET_IMAGES:
            break
        
        # Wikimedia Commons
        download_from_wikimedia(query, max_results=20)
        time.sleep(1)
        
        if downloaded >= TARGET_IMAGES:
            break
        
        # Openverse
        download_from_openverse(query, max_results=20)
        time.sleep(1)
    
    print('\n' + '=' * 70)
    print(f'✅ DONE! Downloaded {downloaded} images')
    print(f'📁 Location: {OUTPUT_DIR}')
    print(f'📊 Total files: {len(list(OUTPUT_DIR.glob("*")))}')
    print()
    print('Next steps:')
    print('  1. Xem qua ảnh và xóa những ảnh không phù hợp')
    print('  2. Chạy lại training: py -3.7 train_dl_model.py')
    print('  3. Model mới sẽ nhận diện lon nước ngọt tốt hơn!')
    print('=' * 70)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f'\n\n⚠️  Interrupted. Downloaded {downloaded} images so far.')
        print(f'Run again to continue from where you left off.')
