#!/usr/bin/env python3
"""
Train mô hình phân loại rác thải cho Trạm STEAM
Sử dụng MobileNetV2 Transfer Learning + tự động convert sang TF.js

Cách chạy:
  py -3.7 train_dl_model.py

Dataset structure:
  dataset/
    ├── plastic/        (chai nhựa, túi nilon, ống hút)
    ├── paper/          (giấy, báo, hộp giấy)
    ├── cardboard/      (thùng carton)
    ├── glass/          (chai thủy tinh)
    ├── metal/          (lon nhôm, kim loại)
    ├── trash/          (rác hỗn hợp còn lại)
    ├── apple/          (rác hữu cơ - táo)
    ├── banana/         (rác hữu cơ - chuối)
    └── ...
"""

import os
import sys
import json
import time
import numpy as np
import scipy  # Import trước để Keras 2.10 nhận diện được

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# ── Thêm các đường dẫn site-packages để tìm TensorFlow ─────────────────────
# Xử lý trường hợp TF được cài ở AppData\Roaming (--user install)
import site
_extra_paths = [
    os.path.join(os.environ.get('APPDATA', ''), 'Python', 'Python37', 'site-packages'),
    os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Python', 'Python37', 'lib', 'site-packages'),
]
for _p in _extra_paths:
    if _p and os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

# ── Bật logging sớm để xem tiến trình ───────────────────────────────────────
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

print("Starting TensorFlow...")
import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout, BatchNormalization
from tensorflow.keras.models import Model
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau, ModelCheckpoint
from tensorflow.keras.optimizers import Adam

# ── Cấu hình ────────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR  = os.path.join(BASE_DIR, 'dataset')
MODEL_H5     = os.path.join(BASE_DIR, 'trash_classifier_model.h5')
TFJS_OUT_DIR = os.path.join(BASE_DIR, 'public', 'tfjs_model')

IMG_SIZE     = (224, 224)
BATCH_SIZE   = 32
EPOCHS       = 30          # EarlyStopping sẽ dừng sớm nếu không cải thiện
LR_INITIAL   = 1e-3
LR_FINETUNE  = 1e-5
MIN_IMAGES   = 20          # Class nào ít hơn mức này sẽ bị cảnh báo

# Map tên thư mục → ID trong mockData.js
# Cho phép nhiều thư mục dataset → cùng 1 category
FOLDER_TO_ID = {
    # Tái chế (green)
    'plastic':          'plastic',
    'plastic_bottle':   'plastic',
    'plastic_bag':      'plastic_bag',
    'plastic_straw':    'plastic_straw',
    'paper':            'newspaper',
    'newspaper':        'newspaper',
    'cardboard':        'cardboard',
    'cardboard_box':    'cardboard',
    'glass':            'glass_bottle',
    'glass_bottle':     'glass_bottle',
    'metal':            'metal_can',
    'tin_can':          'metal_can',
    'soda_can':         'soda_can',
    'paper_cup':        'paper_cup',
    # Hữu cơ (green)
    'apple':            'apple',
    'banana':           'banana',
    'orange':           'orange',
    'bread':            'bread',
    'egg_shell':        'egg_shell',
    'bone':             'bone',
    'leaf':             'leaf',
    'coffee':           'coffee',
    # Rác còn lại (yellow)
    'trash':            'trash',
    'candy_wrapper':    'candy_wrapper',
    'tissue_paper':     'tissue_paper',
    # Nguy hại (red)
    'battery':          'battery',
}

# ── Kiểm tra device ──────────────────────────────────────────────────────────
gpus = tf.config.list_physical_devices('GPU')
device = '/GPU:0' if gpus else '/CPU:0'
print(f"Sử dụng device: {device}")
print(f"Dataset path: {DATASET_DIR}\n")

# ── Kiểm tra dataset ─────────────────────────────────────────────────────────
def check_dataset(dataset_dir):
    if not os.path.exists(dataset_dir):
        print(f"❌ Thư mục dataset không tồn tại: {dataset_dir}")
        print("Chạy: py -3.7 collect_dataset.py  để thu thập ảnh tự động")
        sys.exit(1)
    
    classes = [d for d in os.listdir(dataset_dir) 
               if os.path.isdir(os.path.join(dataset_dir, d))]
    
    if not classes:
        print("❌ Không tìm thấy thư mục class nào trong dataset!")
        sys.exit(1)
    
    print("--- BẮT ĐẦU TRAINING ---")
    print(f"Classes found: {classes}")
    print(f"Number of classes: {len(classes)}")
    print("Checking class sizes...")
    
    small_classes = []
    for cls in classes:
        cls_dir = os.path.join(dataset_dir, cls)
        imgs = [f for f in os.listdir(cls_dir) 
                if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        count = len(imgs)
        print(f"  {cls}: {count} images")
        if count < MIN_IMAGES:
            small_classes.append((cls, count))
    
    if small_classes:
        print(f"\n⚠️  Các class quá ít ảnh (< {MIN_IMAGES}):")
        for cls, cnt in small_classes:
            print(f"    {cls}: {cnt} ảnh → kết quả nhận diện sẽ kém")
        print("  Chạy: py -3.7 collect_dataset.py  để thu thập thêm\n")
    
    return classes

# ── Chuẩn bị data generators ─────────────────────────────────────────────────
def build_generators(dataset_dir):
    train_datagen = ImageDataGenerator(
        rescale=1./255,
        rotation_range=25,
        width_shift_range=0.15,
        height_shift_range=0.15,
        shear_range=0.15,
        zoom_range=0.2,
        horizontal_flip=True,
        brightness_range=[0.7, 1.3],
        fill_mode='nearest',
        validation_split=0.2
    )

    train_gen = train_datagen.flow_from_directory(
        dataset_dir,
        target_size=IMG_SIZE,
        batch_size=BATCH_SIZE,
        class_mode='categorical',
        subset='training',
        shuffle=True
    )

    val_gen = train_datagen.flow_from_directory(
        dataset_dir,
        target_size=IMG_SIZE,
        batch_size=BATCH_SIZE,
        class_mode='categorical',
        subset='validation',
        shuffle=False
    )
    
    print(f"Train: {train_gen.samples} samples, Val: {val_gen.samples} samples")
    return train_gen, val_gen

# ── Xây dựng model ───────────────────────────────────────────────────────────
def build_model(num_classes):
    base = MobileNetV2(
        weights='imagenet',
        include_top=False,
        input_shape=(224, 224, 3)
    )
    # Đóng băng tất cả layers base ban đầu
    base.trainable = False

    x = base.output
    x = GlobalAveragePooling2D()(x)
    x = BatchNormalization()(x)
    x = Dense(256, activation='relu')(x)
    x = Dropout(0.4)(x)
    x = Dense(128, activation='relu')(x)
    x = Dropout(0.2)(x)
    out = Dense(num_classes, activation='softmax')(x)

    model = Model(inputs=base.input, outputs=out)
    model.compile(
        optimizer=Adam(learning_rate=LR_INITIAL),
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )
    return model, base

# ── Fine-tuning: mở khóa thêm layers ────────────────────────────────────────
def finetune_model(model, base_model, train_gen, val_gen):
    print("\n--- FINE-TUNING (mở thêm 30 layers cuối của MobileNetV2) ---")
    
    # Mở khóa 30 layers cuối của base model
    for layer in base_model.layers[-30:]:
        layer.trainable = True
    
    model.compile(
        optimizer=Adam(learning_rate=LR_FINETUNE),
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )
    
    callbacks = [
        EarlyStopping(patience=5, restore_best_weights=True, monitor='val_accuracy'),
        ReduceLROnPlateau(factor=0.5, patience=3, min_lr=1e-7, monitor='val_loss'),
    ]
    
    history = model.fit(
        train_gen,
        epochs=10,
        validation_data=val_gen,
        callbacks=callbacks
    )
    return history

# ── Convert sang TF.js format ────────────────────────────────────────────────
def convert_to_tfjs(model_h5_path, output_dir, class_labels):
    """Convert .h5 → TF.js LayersModel format dùng h5py (không cần TF DLL)"""
    import h5py
    
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\n--- CHUYỂN ĐỔI SANG TENSORFLOW.JS ---")
    print(f"Output: {output_dir}")
    
    with h5py.File(model_h5_path, 'r') as f:
        # Đọc model config
        model_config = None
        for attr_key in ['model_config', b'model_config']:
            if attr_key in f.attrs:
                val = f.attrs[attr_key]
                if isinstance(val, bytes):
                    val = val.decode('utf-8')
                model_config = json.loads(val)
                break
        
        if model_config is None:
            print("⚠️  Không đọc được model config")
            model_config = {}
        
        # Extract tất cả weights
        weight_specs = []
        weight_bytes  = bytearray()
        
        def collect_weights(name, obj):
            if isinstance(obj, h5py.Dataset) and obj.ndim > 0:
                arr = obj[:].astype(np.float32)
                raw = arr.tobytes()
                # Align to 4-byte boundary
                pad = (4 - len(raw) % 4) % 4
                weight_specs.append({
                    'name': name,
                    'shape': list(arr.shape),
                    'dtype': 'float32',
                })
                weight_bytes.extend(raw)
                weight_bytes.extend(b'\x00' * pad)
        
        if 'model_weights' in f:
            f['model_weights'].visititems(collect_weights)
        else:
            f.visititems(collect_weights)
    
    # Ghi file binary weights
    bin_path = os.path.join(output_dir, 'group1-shard1of1.bin')
    with open(bin_path, 'wb') as bf:
        bf.write(weight_bytes)
    
    # Ghi model.json
    topology = {
        'format': 'layers-model',
        'generatedBy': 'trash-steam-converter/1.0',
        'convertedBy': None,
        'modelTopology': model_config,
        'weightsManifest': [{
            'paths': ['group1-shard1of1.bin'],
            'weights': weight_specs
        }]
    }
    
    model_json_path = os.path.join(output_dir, 'model.json')
    with open(model_json_path, 'w', encoding='utf-8') as mf:
        json.dump(topology, mf, ensure_ascii=False)
    
    # Ghi labels.json
    labels_path = os.path.join(output_dir, 'labels.json')
    with open(labels_path, 'w', encoding='utf-8') as lf:
        json.dump(class_labels, lf, ensure_ascii=False, indent=2)
    
    # In thống kê
    bin_size = os.path.getsize(bin_path)
    print(f"  ✅ model.json      : {os.path.getsize(model_json_path):>10,} bytes")
    print(f"  ✅ weights.bin     : {bin_size:>10,} bytes ({bin_size/1e6:.1f} MB)")
    print(f"  ✅ labels.json     : {class_labels}")

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    t0 = time.time()
    
    # 1. Kiểm tra dataset
    classes = check_dataset(DATASET_DIR)
    
    # 2. Chuẩn bị dữ liệu
    train_gen, val_gen = build_generators(DATASET_DIR)
    num_classes = train_gen.num_classes
    
    # Lưu thứ tự class để dùng trong TF.js
    class_indices = train_gen.class_indices          # {'apple': 0, 'banana': 1, ...}
    idx_to_class  = {v: k for k, v in class_indices.items()}
    class_labels  = [idx_to_class[i] for i in range(num_classes)]
    print(f"Thứ tự labels: {class_labels}")
    
    # 3. Build model
    model, base_model = build_model(num_classes)
    
    # 4. Training phase 1: chỉ train top layers
    callbacks_phase1 = [
        EarlyStopping(patience=5, restore_best_weights=True, monitor='val_accuracy', verbose=1),
        ReduceLROnPlateau(factor=0.5, patience=3, min_lr=1e-6, verbose=1),
        ModelCheckpoint(MODEL_H5, save_best_only=True, monitor='val_accuracy', verbose=0),
    ]
    
    print(f"\nPhase 1: Training top layers ({EPOCHS} epochs max)...")
    history_p1 = model.fit(
        train_gen,
        epochs=EPOCHS,
        validation_data=val_gen,
        callbacks=callbacks_phase1
    )
    
    # Phase 1 xong → load lại best checkpoint (ModelCheckpoint đã lưu rồi)
    # model hiện tại đang ở best weights nhờ restore_best_weights=True
    best_val_acc_p1 = max(history_p1.history['val_accuracy'])
    print(f"\nPhase 1 best val_accuracy: {best_val_acc_p1:.2%}")
    
    # 5. Fine-tuning phase 2 — chỉ chạy nếu phase 1 ổn
    # Dùng ModelCheckpoint riêng để chỉ ghi đè nếu CẢI THIỆN được phase 1
    ft_checkpoint = MODEL_H5.replace('.h5', '_ft.h5')
    callbacks_ft = [
        EarlyStopping(patience=4, restore_best_weights=True, monitor='val_accuracy', verbose=1),
        ReduceLROnPlateau(factor=0.5, patience=2, min_lr=1e-7, verbose=1),
        ModelCheckpoint(ft_checkpoint, save_best_only=True, monitor='val_accuracy', verbose=0),
    ]
    
    print("\n--- FINE-TUNING (mở thêm 30 layers cuối của MobileNetV2) ---")
    for layer in base_model.layers[-30:]:
        layer.trainable = True
    model.compile(
        optimizer=Adam(learning_rate=LR_FINETUNE),
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )
    history_ft = model.fit(
        train_gen,
        epochs=10,
        validation_data=val_gen,
        callbacks=callbacks_ft
    )
    
    # Chỉ dùng fine-tuned model nếu nó thực sự tốt hơn
    best_val_acc_ft = max(history_ft.history['val_accuracy'])
    if best_val_acc_ft > best_val_acc_p1:
        print(f"\n✅ Fine-tuning cải thiện: {best_val_acc_p1:.2%} → {best_val_acc_ft:.2%}")
        import shutil
        shutil.copy(ft_checkpoint, MODEL_H5)
    else:
        print(f"\n⚠️  Fine-tuning không cải thiện ({best_val_acc_ft:.2%} < {best_val_acc_p1:.2%})")
        print("   Giữ lại model Phase 1 tốt hơn.")
        # MODEL_H5 đã được ModelCheckpoint phase 1 lưu sẵn
    
    # Xóa file checkpoint tạm
    if os.path.exists(ft_checkpoint):
        os.remove(ft_checkpoint)
    
    # 6. Lưu model tốt nhất
    model.save(MODEL_H5)
    elapsed = time.time() - t0
    print(f"\n✅ Đã lưu model: {MODEL_H5} ({elapsed/60:.1f} phút)")
    
    # 7. Convert sang TF.js
    try:
        import h5py
        convert_to_tfjs(MODEL_H5, TFJS_OUT_DIR, class_labels)
        print(f"\n✅ Model TF.js sẵn sàng tại: {TFJS_OUT_DIR}")
        print("   Trong settings của web, nhập URL: /tfjs_model/model.json")
    except ImportError:
        print("\n⚠️  Cần h5py để convert: py -3.7 -m pip install h5py")
    except Exception as e:
        print(f"\n⚠️  Lỗi convert TF.js: {e}")
    
    print("\n--- XONG ---")

if __name__ == '__main__':
    main()
