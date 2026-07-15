#!/usr/bin/env python3
"""
Convert .h5 model to TF.js GraphModel format (more compatible with MobileNet base)
Uses SavedModel as intermediate format to avoid custom layer issues
"""
import os, sys, json, shutil
import scipy
import numpy as np

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import tensorflow as tf

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
H5_PATH     = os.path.join(BASE_DIR, 'trash_classifier_model.h5')
SAVED_DIR   = os.path.join(BASE_DIR, 'saved_model_temp')
OUT_DIR     = os.path.join(BASE_DIR, 'public', 'tfjs_model')
LABELS_PATH = os.path.join(OUT_DIR, 'labels.json')

print('=' * 70)
print('Convert Keras H5 -> TF.js GraphModel')
print('=' * 70)

# 1. Load model
print(f'\n[1/3] Load model: {H5_PATH}')
model = tf.keras.models.load_model(H5_PATH)
print(f'  Input: {model.input_shape}, Output: {model.output_shape}')
print(f'  Params: {model.count_params():,}')

# 2. Load labels
print(f'\n[2/3] Load labels')
labels = []
if os.path.exists(LABELS_PATH):
    with open(LABELS_PATH, 'r') as f:
        labels = json.load(f)
else:
    dataset_dir = os.path.join(BASE_DIR, 'dataset')
    if os.path.exists(dataset_dir):
        labels = sorted([d for d in os.listdir(dataset_dir)
                         if os.path.isdir(os.path.join(dataset_dir, d))])
print(f'  Labels ({len(labels)}): {", ".join(labels[:5])}...')

# 3. Export to SavedModel format (TF standard)
print(f'\n[3/3] Export to SavedModel: {SAVED_DIR}')
if os.path.exists(SAVED_DIR):
    shutil.rmtree(SAVED_DIR)

# Explicitly define the serving signature
@tf.function(input_signature=[tf.TensorSpec(shape=[None, 224, 224, 3], dtype=tf.float32, name='input')])
def serving_fn(input_tensor):
    # Normalize input if needed (model expects 0-1 range)
    return {'output': model(input_tensor, training=False)}

# Save with explicit signature
tf.saved_model.save(
    model,
    SAVED_DIR,
    signatures={'serving_default': serving_fn}
)
print('  ✓ SavedModel created')

# Check if we can load it back
try:
    loaded = tf.saved_model.load(SAVED_DIR)
    print('  ✓ SavedModel validated')
except Exception as e:
    print(f'  ⚠️ Validation failed: {e}')

# 4. Now we need to convert SavedModel -> TF.js format
# Since tensorflowjs package won't install on Py3.7, we'll create a simple wrapper
print(f'\n--- CONVERSION OPTIONS ---')
print(f'SavedModel is ready at: {SAVED_DIR}')
print(f'')
print(f'Option A: Use Node.js CLI (recommended):')
print(f'  npm install -g @tensorflow/tfjs-converter')
print(f'  tensorflowjs_converter \\')
print(f'    --input_format=tf_saved_model \\')
print(f'    --output_format=tfjs_graph_model \\')
print(f'    {SAVED_DIR} \\')
print(f'    {OUT_DIR}')
print(f'')
print(f'Option B: Use Python 3.8+ (upgrade Python):')
print(f'  pip install tensorflowjs')
print(f'  tensorflowjs_converter --input_format keras {H5_PATH} {OUT_DIR}')
print(f'')

# Try to use tf.saved_model directly to create a simpler format
# This creates a frozen graph that TF.js can potentially load
os.makedirs(OUT_DIR, exist_ok=True)

# Save labels
with open(LABELS_PATH, 'w') as f:
    json.dump(labels, f, indent=2)
print(f'✓ labels.json saved: {len(labels)} classes')

print(f'\n⚠️  Manual conversion needed - see options above')

# ─────────────────────────────────────────────────────────────────────────────
# Extract weights theo dung chuan TF.js LayersModel
# Format yeu cau:
#   model.json:
#     format: 'layers-model'
#     modelTopology: <gia tri tra ve boi model.to_json() - parse thanh dict>
#     weightsManifest: [{ paths, weights }]
# ─────────────────────────────────────────────────────────────────────────────

print('Extracting weights...')

weight_specs = []
weight_data  = bytearray()

for layer in model.layers:
    ws = layer.get_weights()
    if not ws:
        continue
    name = layer.name
    # Ten weight theo chuan Keras: layername/kernel, layername/bias, etc.
    keras_suffixes = ['kernel', 'bias', 'gamma', 'beta', 'moving_mean', 'moving_variance']
    for i, w in enumerate(ws):
        arr = w.astype(np.float32)
        raw = arr.tobytes()
        pad = (4 - len(raw) % 4) % 4
        suf = keras_suffixes[i] if i < len(keras_suffixes) else ('w' + str(i))
        weight_specs.append({
            'name':  name + '/' + suf,
            'shape': list(arr.shape),
            'dtype': 'float32',
        })
        weight_data.extend(raw)
        weight_data.extend(b'\x00' * pad)

print(str(len(weight_specs)) + ' tensors, ' + str(round(len(weight_data)/1e6,1)) + ' MB')

# Ghi .bin
bin_path = os.path.join(OUT_DIR, 'group1-shard1of1.bin')
with open(bin_path, 'wb') as f:
    f.write(weight_data)

# ─────────────────────────────────────────────────────────────────────────────
# model.json - dung format TF.js LayersModel chinh xac:
#   modelTopology phai la dict parse tu model.to_json()
#   KHONG long them 1 cap nua
# ─────────────────────────────────────────────────────────────────────────────
model_topology = json.loads(model.to_json())  # day chinh la dict can dung

model_json = {
    'format':          'layers-model',
    'generatedBy':     'keras v' + tf.keras.__version__,
    'convertedBy':     'custom-converter',
    'modelTopology':   model_topology,          # <-- dung truc tiep, khong wrap
    'weightsManifest': [{
        'paths':   ['group1-shard1of1.bin'],
        'weights': weight_specs,
    }],
}

model_json_path = os.path.join(OUT_DIR, 'model.json')
with open(model_json_path, 'w') as f:
    json.dump(model_json, f)

# Ghi labels.json
with open(LABELS_PATH, 'w') as f:
    json.dump(labels, f, indent=2)

print('Done.')
print('  model.json  : ' + str(os.path.getsize(model_json_path)) + ' bytes')
print('  weights.bin : ' + str(os.path.getsize(bin_path)) + ' bytes')
print('  labels.json : ' + str(len(labels)) + ' classes')

# Validate: check top-level keys
with open(model_json_path) as f:
    check = json.load(f)
print('Validation - modelTopology class_name:', check['modelTopology'].get('class_name', '??'))
print('Validation - first weight name:', check['weightsManifest'][0]['weights'][0]['name'])
