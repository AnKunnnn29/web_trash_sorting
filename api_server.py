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
MODEL_PATH = os.path.join(BASE_DIR, 'trash_classifier_model.h5')
LABELS_PATH = os.path.join(BASE_DIR, 'public', 'tfjs_model', 'labels.json')

print('Loading model...')
model = tf.keras.models.load_model(MODEL_PATH)
print(f'Model loaded: {model.input_shape} -> {model.output_shape}')

# Load labels
with open(LABELS_PATH, 'r') as f:
    labels = json.load(f)
print(f'Labels: {labels}')

# Load trash items metadata
sys.path.insert(0, os.path.join(BASE_DIR, 'src'))
try:
    # Read mockData.js and parse it (simplified)
    mock_path = os.path.join(BASE_DIR, 'src', 'mockData.js')
    with open(mock_path, 'r', encoding='utf-8') as f:
        mock_content = f.read()
    # Extract trashItems array (very basic parsing)
    import re
    items_match = re.search(r'export const trashItems = (\[.*?\]);', mock_content, re.DOTALL)
    if items_match:
        items_json = items_match.group(1)
        # Convert JS to JSON (replace single quotes, remove trailing commas)
        items_json = items_json.replace("'", '"').replace(',\n]', '\n]').replace(',\n  ]', '\n  ]')
        trash_items = json.loads(items_json)
        trash_dict = {item['id']: item for item in trash_items}
        print(f'Loaded {len(trash_dict)} trash items from mockData')
    else:
        trash_dict = {}
except Exception as e:
    print(f'Could not load mockData: {e}')
    trash_dict = {}

def preprocess_image(base64_str):
    """Decode base64 -> PIL -> numpy array normalized"""
    img_data = base64.b64decode(base64_str)
    img = Image.open(BytesIO(img_data)).convert('RGB')
    img = img.resize((224, 224))
    arr = np.array(img, dtype=np.float32) / 255.0
    return np.expand_dims(arr, axis=0)

def predict_image(base64_str):
    """Run inference and return top prediction"""
    input_tensor = preprocess_image(base64_str)
    output = model.predict(input_tensor, verbose=0)
    probs = output[0]
    
    top_idx = int(np.argmax(probs))
    top_prob = float(probs[top_idx])
    top_label = labels[top_idx]
    
    # Find matching trash item
    item = trash_dict.get(top_label, {})
    
    return {
        'class': top_label,
        'confidence': top_prob,
        'emoji': item.get('emoji', '❓'),
        'name': item.get('name', top_label),
        'bin': item.get('bin', 'unknown')
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
        print('🚀 Trash Classification API Server')
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
