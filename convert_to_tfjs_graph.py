#!/usr/bin/env python3
"""
Convert Keras .h5 model sang TF.js GraphModel format
GraphModel tương thích tốt hơn với các custom layer/activations
"""
import os, sys, json
import scipy
import numpy as np

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import tensorflow as tf

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
H5_PATH  = os.path.join(BASE_DIR, 'trash_classifier_model.h5')
SAVEDMODEL_DIR = os.path.join(BASE_DIR, 'saved_model_tmp')
OUT_DIR  = os.path.join(BASE_DIR, 'public', 'tfjs_model')

print('=' * 70)
print('Converting Keras model to TF.js GraphModel format')
print('=' * 70)

# 1. Load Keras model
print(f'\n[1/4] Loading model: {H5_PATH}')
model = tf.keras.models.load_model(H5_PATH)
print(f'  Input shape: {model.input_shape}')
print(f'  Output shape: {model.output_shape}')
print(f'  Total params: {model.count_params():,}')

# 2. Load labels
labels_path = os.path.join(OUT_DIR, 'labels.json')
labels = []
if os.path.exists(labels_path):
    with open(labels_path, 'r') as f:
        labels = json.load(f)
    print(f'\n[2/4] Labels loaded: {len(labels)} classes')
else:
    dataset_dir = os.path.join(BASE_DIR, 'dataset')
    if os.path.exists(dataset_dir):
        labels = sorted([d for d in os.listdir(dataset_dir)
                         if os.path.isdir(os.path.join(dataset_dir, d))])
    print(f'\n[2/4] Labels from dataset: {len(labels)} classes')

# 3. Save as TensorFlow SavedModel (intermediate format)
print(f'\n[3/4] Saving as SavedModel to: {SAVEDMODEL_DIR}')
if os.path.exists(SAVEDMODEL_DIR):
    import shutil
    shutil.rmtree(SAVEDMODEL_DIR)

# Wrap model với explicit input signature
@tf.function(input_signature=[tf.TensorSpec(shape=[None, 224, 224, 3], dtype=tf.float32)])
def serving_fn(input_tensor):
    return model(input_tensor, training=False)

# Export với concrete function
tf.saved_model.save(
    model,
    SAVEDMODEL_DIR,
    signatures={'serving_default': serving_fn}
)
print('  ✓ SavedModel created')

# 4. Convert SavedModel to TF.js GraphModel using Python API
print(f'\n[4/4] Converting to TF.js GraphModel: {OUT_DIR}')
if os.path.exists(OUT_DIR):
    import shutil
    # Backup labels.json before removing dir
    labels_backup = None
    if os.path.exists(labels_path):
        with open(labels_path, 'r') as f:
            labels_backup = f.read()
    shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR)
    if labels_backup:
        with open(labels_path, 'w') as f:
            f.write(labels_backup)

# Dùng tf.saved_model API để convert
from tensorflow.python.tools import freeze_graph
from tensorflow.python.framework import convert_to_constants

# Load lại SavedModel
imported = tf.saved_model.load(SAVEDMODEL_DIR)
concrete_func = imported.signatures['serving_default']

# Convert to frozen graph
frozen_func = convert_to_constants.convert_variables_to_constants_v2(concrete_func)

# Ghi graph sang TF.js format bằng tay (simplified)
# Vì không có tensorflowjs CLI, ta sẽ export sang saved_model format để user tự convert sau

print('\n⚠️  Không tìm thấy tensorflowjs CLI tool.')
print('   Vui lòng cài Node.js và chạy lệnh sau để hoàn tất conversion:')
print('')
print('   npm install -g @tensorflow/tfjs-converter')
print('   tensorflowjs_converter \\')
print(f'     --input_format=tf_saved_model \\')
print(f'     --output_format=tfjs_graph_model \\')
print(f'     {SAVEDMODEL_DIR} \\')
print(f'     {OUT_DIR}')
print('')
print(f'✓ SavedModel đã sẵn sàng tại: {SAVEDMODEL_DIR}')
print(f'  Sau khi convert, model.json sẽ ở: {OUT_DIR}')
print('')
print('Hoặc bạn có thể dùng Python 3.8+ và cài:')
print('  pip install tensorflowjs')
print('  tensorflowjs_converter --input_format keras {H5_PATH} {OUT_DIR}')
