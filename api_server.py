#!/usr/bin/env python3
"""
Simple Flask API server for trash classification
Frontend gửi ảnh → API trả về prediction

Usage:
  py -3.7 api_server.py

API Endpoint:
  POST /predict
  Body: {"image": "base64_encoded_jpeg"}
  Response: {"class": "plastic_bottle", "confidence": 0.92, "emoji": "🍾", "name": "Chai nhựa"}
"""
import os, sys, json, base64
from io import BytesIO
import scipy
import numpy as np
from PIL import Image

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import tensorflow as tf

# Load model at startup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'saved_model_keras')
LABELS_PATH = os.path.join(MODEL_PATH, 'labels.json')

if not os.path.exists(MODEL_PATH):
    print(f"\n⚠️  Không tìm thấy model tại: {MODEL_PATH}")
    print("   Vui lòng chạy `python train_dl_model.py` trước.\n")
    sys.exit(1)

if not os.path.exists(LABELS_PATH):
    print(f"\n⚠️  Không tìm thấy file labels tại: {LABELS_PATH}")
    print("   Vui lòng train lại model.\n")
    sys.exit(1)

print('Loading model...')
loaded = tf.saved_model.load(MODEL_PATH)
model_fn = loaded.signatures["serving_default"]
print(f'Model loaded successfully via SavedModel.')

# Load labels
with open(LABELS_PATH, 'r') as f:
    labels = json.load(f)
print(f'Labels: {labels}')

# Load trash items metadata
try:
    trash_items_path = os.path.join(BASE_DIR, 'src', 'trashItems.json')
    with open(trash_items_path, 'r', encoding='utf-8') as f:
        trash_items = json.load(f)
    trash_dict = {item['id']: item for item in trash_items if 'id' in item}
    print(f'Loaded {len(trash_dict)} trash items from trashItems.json')
except Exception as e:
    print(f'Could not load trashItems.json: {e}')
    try:
        mock_path = os.path.join(BASE_DIR, 'src', 'mockData.js')
        with open(mock_path, 'r', encoding='utf-8') as f:
            mock_content = f.read()
        import re
        trash_dict = {}
        for block in re.findall(r'\{([^\}]+)\}', mock_content):
            if 'id:' in block:
                item = {}
                for key in ['id', 'name', 'category', 'emoji']:
                    m = re.search(fr"{key}:\s*['\"]([^'\"]+)['\"]", block)
                    if m:
                        item[key] = m.group(1)
                if 'id' in item:
                    trash_dict[item['id']] = item
        print(f'Loaded {len(trash_dict)} trash items from mockData fallback')
    except Exception as fallback_error:
        print(f'Could not load mockData fallback: {fallback_error}')
        trash_dict = {}

def decode_image(base64_str):
    """Decode base64 image payload into RGB PIL image."""
    img_data = base64.b64decode(base64_str)
    return Image.open(BytesIO(img_data)).convert('RGB')

def looks_like_red_soda_can(img):
    """Detect the common webcam case of a tall red/white soda can."""
    small = img.resize((224, 224))
    arr = np.array(small, dtype=np.float32)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    red_mask = (r > 90) & (r > g * 1.25) & (r > b * 1.15)
    red_ratio = float(np.mean(red_mask))
    if red_ratio < 0.035:
        return False

    ys, xs = np.where(red_mask)
    if len(xs) == 0:
        return False

    width = int(xs.max() - xs.min() + 1)
    height = int(ys.max() - ys.min() + 1)
    aspect = height / max(width, 1)

    # Tight can crops are tall; hand-held webcam crops can be wider but have a lot of red.
    return aspect >= 1.35 or red_ratio >= 0.12

def looks_like_white_paper_scrap(img):
    """Detect small dry white paper scraps that the classifier often sees as wipe."""
    small = img.resize((224, 224))
    arr = np.array(small, dtype=np.float32)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    brightness = (r + g + b) / 3.0
    saturation_proxy = np.maximum.reduce([r, g, b]) - np.minimum.reduce([r, g, b])

    white_mask = (brightness > 145) & (saturation_proxy < 58) & (r > 125) & (g > 125) & (b > 125)

    # Ignore border UI/light leaks; the object should be mostly inside the scan area.
    yy, xx = np.indices(white_mask.shape)
    center_mask = (xx > 28) & (xx < 196) & (yy > 24) & (yy < 200)
    white_mask = white_mask & center_mask

    white_ratio = float(np.mean(white_mask))
    if white_ratio < 0.025 or white_ratio > 0.45:
        return False

    try:
        from scipy import ndimage
        labels_img, count = ndimage.label(white_mask)
        if count == 0:
            return False
        sizes = ndimage.sum(white_mask, labels_img, range(1, count + 1))
        largest_label = int(np.argmax(sizes) + 1)
        component = labels_img == largest_label
    except Exception:
        component = white_mask

    ys, xs = np.where(component)
    if len(xs) == 0:
        return False

    width = int(xs.max() - xs.min() + 1)
    height = int(ys.max() - ys.min() + 1)
    component_ratio = float(len(xs)) / float(224 * 224)
    bbox_area_ratio = float(width * height) / float(224 * 224)
    aspect = max(width, height) / max(min(width, height), 1)

    # Paper scraps are visible, irregular white objects; reject tiny highlights and full backgrounds.
    return (
        component_ratio >= 0.02
        and bbox_area_ratio >= 0.035
        and width >= 24
        and height >= 24
        and aspect <= 4.0
    )

def preprocess_image(img):
    """PIL -> numpy array (0-255; model includes its own preprocessing layer)."""
    img = img.resize((224, 224))
    arr = np.array(img, dtype=np.float32)
    return np.expand_dims(arr, axis=0)

def predict_image(base64_str):
    """Run inference and return top prediction"""
    img = decode_image(base64_str)
    input_tensor = preprocess_image(img)
    # Perform inference via signature
    tensor_in = tf.constant(input_tensor, dtype=tf.float32)
    output_dict = model_fn(input=tensor_in)
    probs = output_dict['output'].numpy()[0]
    
    ranked_indices = np.argsort(probs)[::-1][:3]
    top_idx = int(ranked_indices[0])
    top_prob = float(probs[top_idx])
    top_label = labels[top_idx]
    
    # Find matching trash item
    item = trash_dict.get(top_label, {})
    top_predictions = []
    for idx in ranked_indices:
        idx = int(idx)
        label = labels[idx]
        meta = trash_dict.get(label, {})
        top_predictions.append({
            'class': label,
            'confidence': float(probs[idx]),
            'name': meta.get('name', label),
            'category': meta.get('category', 'unknown')
        })

    if looks_like_red_soda_can(img) and top_label != 'soda_can':
        soda_item = trash_dict.get('soda_can', {})
        soda_confidence = min(0.98, max(top_prob + 0.02, 0.74))
        top_predictions = [pred for pred in top_predictions if pred['class'] != 'soda_can']
        top_predictions.insert(0, {
            'class': 'soda_can',
            'confidence': soda_confidence,
            'name': soda_item.get('name', 'soda_can'),
            'category': soda_item.get('category', 'green')
        })
        top_predictions = top_predictions[:3]
        return {
            'class': 'soda_can',
            'confidence': soda_confidence,
            'emoji': soda_item.get('emoji', '🥤'),
            'name': soda_item.get('name', 'soda_can'),
            'category': soda_item.get('category', 'green'),
            'top_predictions': top_predictions,
            'heuristic': 'red_soda_can'
        }

    paper_candidate_labels = {'wipe', 'chewing_gum', 'newspaper', 'milk_carton', 'plastic_bag', 'diaper'}
    paper_blocked_labels = {'soda_can', 'bottle', 'glass_bottle', 'shampoo_bottle', 'aerosol'}
    if (
        top_label not in paper_blocked_labels
        and looks_like_white_paper_scrap(img)
        and (top_label in paper_candidate_labels or top_prob < 0.55)
    ):
        paper_item = trash_dict.get('newspaper', {})
        paper_confidence = min(0.86, max(top_prob + 0.28, 0.62))
        top_predictions = [pred for pred in top_predictions if pred['class'] != 'newspaper']
        top_predictions.insert(0, {
            'class': 'newspaper',
            'confidence': paper_confidence,
            'name': paper_item.get('name', 'newspaper'),
            'category': paper_item.get('category', 'green')
        })
        top_predictions = top_predictions[:3]
        return {
            'class': 'newspaper',
            'confidence': paper_confidence,
            'emoji': paper_item.get('emoji', '📰'),
            'name': paper_item.get('name', 'newspaper'),
            'category': paper_item.get('category', 'green'),
            'top_predictions': top_predictions,
            'heuristic': 'white_paper_scrap'
        }
    
    return {
        'class': top_label,
        'confidence': top_prob,
        'emoji': item.get('emoji', '❓'),
        'name': item.get('name', top_label),
        'category': item.get('category', 'unknown'),
        'top_predictions': top_predictions
    }

# ── Flask App ────────────────────────────────────────────────────────────────
try:
    from flask import Flask, request, jsonify
    from flask_cors import CORS
    
    app = Flask(__name__)
    CORS(app)  # Enable CORS for frontend
    
    @app.route('/predict', methods=['POST'])
    def predict():
        try:
            data = request.get_json()
            if not data or 'image' not in data:
                return jsonify({'error': 'Missing image field'}), 400
            
            result = predict_image(data['image'])
            return jsonify(result)
        
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({'status': 'ok', 'model': 'loaded', 'classes': len(labels)})
    
    if __name__ == '__main__':
        print('\n' + '=' * 70)
        print('[START] Trash Classification API Server')
        print('=' * 70)
        print(f'Model: {MODEL_PATH}')
        print(f'Classes: {len(labels)}')
        
        # Đọc PORT từ environment variable (cho Render/Heroku)
        port = int(os.environ.get('PORT', 5000))
        
        print(f'\nAPI running at: http://localhost:{port}')
        print('Endpoints:')
        print('  POST /predict  - Send {"image": "base64_jpeg"}')
        print('  GET  /health   - Check server status')
        print('\nPress Ctrl+C to stop')
        print('=' * 70 + '\n')
        
        app.run(host='0.0.0.0', port=port, debug=False)

except ImportError:
    print('\n⚠️  Flask not installed. Install it with:')
    print('  py -3.7 -m pip install flask flask-cors')
    print('\nThen run:')
    print('  py -3.7 api_server.py')
