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
import time
import json
import argparse
import numpy as np
import pandas as pd
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
from tensorflow.keras.applications import EfficientNetB0
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input as mobilenet_preprocess
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout, BatchNormalization
from tensorflow.keras.models import Model
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau, ModelCheckpoint
from tensorflow.keras.optimizers import Adam

# ── Cấu hình ────────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR  = os.path.join(BASE_DIR, 'dataset')
MODEL_H5     = os.path.join(BASE_DIR, 'saved_model_keras') # Thay đổi thành folder để tránh lỗi .h5 của EfficientNet
TFJS_OUT_DIR = os.path.join(BASE_DIR, 'public', 'tfjs_model')
DATASET_MAPPING_PATH = os.path.join(BASE_DIR, 'config', 'dataset-labels.json')

IMG_SIZE     = (224, 224)
BATCH_SIZE   = 32
EPOCHS       = 30          # EarlyStopping sẽ dừng sớm nếu không cải thiện
LR_INITIAL   = 1e-3
LR_FINETUNE  = 1e-5
MIN_IMAGES   = 20          # Class nào ít hơn mức này sẽ bị cảnh báo

# ── Label Mapping ────────────────────────────────────────────────────────────
# Đây là nguồn chuẩn dùng chung cho training, validation và benchmark.
with open(DATASET_MAPPING_PATH, encoding='utf-8') as mapping_file:
    FOLDER_TO_ID = json.load(mapping_file)

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
def build_generators(dataset_dir, max_per_class=None):
    filepaths = []
    labels = []

    # Quét thư mục và tạo mapping
    for folder in os.listdir(dataset_dir):
        folder_path = os.path.join(dataset_dir, folder)
        if os.path.isdir(folder_path):
            frontend_id = FOLDER_TO_ID.get(folder)
            if not frontend_id:
                print(f"⚠️ Bỏ qua folder {folder} vì không có trong mapping")
                continue
            for file in os.listdir(folder_path):
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    filepaths.append(os.path.join(folder_path, file))
                    labels.append(frontend_id)

    df = pd.DataFrame({'filepath': filepaths, 'label': labels})
    if max_per_class:
        df = (
            df.groupby('label', group_keys=False)
              .apply(lambda g: g.sample(n=min(len(g), max_per_class), random_state=42))
              .reset_index(drop=True)
        )
        print(f"Giới hạn tối đa {max_per_class} ảnh/class để train nhanh.")
    print(f"Tổng số ảnh thu thập: {len(df)}")
    print(f"Số lượng classes (frontend ids): {df['label'].nunique()}")
    val_parts = []
    train_parts = []
    for _, group in df.groupby('label'):
        val_part = group.sample(frac=0.2, random_state=42)
        train_part = group.drop(val_part.index)
        val_parts.append(val_part)
        train_parts.append(train_part)

    train_df = pd.concat(train_parts).sample(frac=1, random_state=42).reset_index(drop=True)
    val_df = pd.concat(val_parts).sample(frac=1, random_state=42).reset_index(drop=True)
    class_labels = sorted(df['label'].unique())

    train_datagen = ImageDataGenerator(
        rotation_range=30,
        width_shift_range=0.15,
        height_shift_range=0.15,
        shear_range=0.15,
        zoom_range=0.2,
        horizontal_flip=True,
        brightness_range=[0.7, 1.3],
        fill_mode='nearest'
    )
    val_datagen = ImageDataGenerator()

    train_gen = train_datagen.flow_from_dataframe(
        dataframe=train_df,
        x_col='filepath',
        y_col='label',
        target_size=IMG_SIZE,
        batch_size=BATCH_SIZE,
        class_mode='categorical',
        classes=class_labels,
        seed=42
    )
    val_gen = val_datagen.flow_from_dataframe(
        dataframe=val_df,
        x_col='filepath',
        y_col='label',
        target_size=IMG_SIZE,
        batch_size=BATCH_SIZE,
        class_mode='categorical',
        classes=class_labels,
        seed=42,
        shuffle=False
    )

    class_indices = train_gen.class_indices
    class_labels_dict = {v: k for k, v in class_indices.items()}
    class_labels = [class_labels_dict[i] for i in range(len(class_labels_dict))]

    return train_gen, val_gen, class_labels

# ── Xây dựng model ───────────────────────────────────────────────────────────
def build_model(num_classes, backbone='efficientnet'):
    if backbone == 'mobilenetv2':
        inputs = tf.keras.Input(shape=(224, 224, 3), name='input')
        base = MobileNetV2(
            weights='imagenet',
            include_top=False,
            input_shape=(224, 224, 3)
        )
        x = tf.keras.layers.Lambda(mobilenet_preprocess, name='mobilenet_preprocess')(inputs)
        x = base(x, training=False)
        model_input = inputs
    else:
        base = EfficientNetB0(
            weights='imagenet',
            include_top=False,
            input_shape=(224, 224, 3)
        )
        model_input = base.input

    # Đóng băng tất cả layers base ban đầu
    base.trainable = False

    x = x if backbone == 'mobilenetv2' else base.output
    x = GlobalAveragePooling2D()(x)
    x = BatchNormalization()(x)
    x = Dense(256, activation='relu')(x)
    x = Dropout(0.4)(x)
    x = Dense(128, activation='relu')(x)
    x = Dropout(0.2)(x)
    out = Dense(num_classes, activation='softmax')(x)

    model = Model(inputs=model_input, outputs=out)
    model.compile(
        optimizer=Adam(learning_rate=LR_INITIAL),
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )
    return model, base

# ── Fine-tuning: mở khóa thêm layers ────────────────────────────────────────
def finetune_model(model, base_model, train_gen, val_gen):
    print("\n--- FINE-TUNING (mở thêm 40 layers cuối của EfficientNetB0) ---")

    # Mở khóa 40 layers cuối của base model
    for layer in base_model.layers[-40:]:
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
def convert_to_tfjs(saved_model_dir, output_dir, class_labels):
    """Convert Keras model from SavedModel → TF.js GraphModel using standard tools"""
    import shutil
    import subprocess

    print(f"\n--- CHUYỂN ĐỔI SANG TENSORFLOW.JS (Cho Vercel) ---")

    # 3. Call TFJS Converter via npx
    print(f"Converting SavedModel to TF.js GraphModel...")
    if os.path.exists(output_dir):
        # Delete old model files but keep labels.json if it exists
        for filename in os.listdir(output_dir):
            if filename != "labels.json":
                file_path = os.path.join(output_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
    else:
        os.makedirs(output_dir, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "tensorflowjs.converters.converter",
        "--input_format=tf_saved_model",
        "--output_format=tfjs_graph_model",
        saved_model_dir,
        output_dir,
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"  ✅ Chuyển đổi TF.js thành công tại: {output_dir}")
    except subprocess.CalledProcessError as e:
        print(f"  ⚠️ Lỗi khi chạy npx: {e}")
        print("  Hãy đảm bảo bạn đã cài Node.js. Chạy thử: npm install -g @tensorflow/tfjs-converter")
    
    # 4. Ghi labels.json cho server API và frontend
    labels_path = os.path.join(output_dir, 'labels.json')
    with open(labels_path, 'w', encoding='utf-8') as lf:
        json.dump(class_labels, lf, ensure_ascii=False, indent=2)
    print(f"  ✅ Đã lưu file {labels_path}")

    # Ghi labels.json vào saved_model_keras cho backend API đọc
    api_labels_path = os.path.join(BASE_DIR, 'saved_model_keras', 'labels.json')
    with open(api_labels_path, 'w', encoding='utf-8') as lf:
        json.dump(class_labels, lf, ensure_ascii=False, indent=2)

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--convert-tfjs', action='store_true', help='Convert model to TF.js format after training')
    parser.add_argument('--quick', action='store_true', help='Train a faster CPU-friendly model for webcam testing')
    parser.add_argument('--epochs', type=int, default=None, help='Override phase 1 epoch count')
    parser.add_argument('--max-per-class', type=int, default=None, help='Limit images per class for faster training')
    parser.add_argument('--backbone', choices=['efficientnet', 'mobilenetv2'], default=None, help='CNN backbone')
    args = parser.parse_args()

    t0 = time.time()
    backbone = args.backbone or ('mobilenetv2' if args.quick else 'efficientnet')
    phase1_epochs = args.epochs or (5 if args.quick else EPOCHS)
    max_per_class = args.max_per_class or (120 if args.quick else None)
    skip_finetune = args.quick
    print(f"Chế độ train: backbone={backbone}, epochs={phase1_epochs}, max_per_class={max_per_class or 'all'}, fine_tune={not skip_finetune}")
    
    # 1. Kiểm tra dataset
    classes = check_dataset(DATASET_DIR)
    
    # 2. Chuẩn bị dữ liệu
    train_gen, val_gen, class_labels = build_generators(DATASET_DIR, max_per_class=max_per_class)
    num_classes = len(class_labels)
    
    # Lưu thứ tự class để dùng trong TF.js
    class_indices = train_gen.class_indices          # {'apple': 0, 'banana': 1, ...}
    idx_to_class  = {v: k for k, v in class_indices.items()}
    class_labels  = [idx_to_class[i] for i in range(num_classes)]
    print(f"Thứ tự labels: {class_labels}")
    
    # 3. Build model
    model, base_model = build_model(num_classes, backbone=backbone)
    
    # 4. Training phase 1: chỉ train top layers
    callbacks_phase1 = [
        EarlyStopping(patience=2 if args.quick else 5, restore_best_weights=True, monitor='val_accuracy', verbose=1),
        ReduceLROnPlateau(factor=0.5, patience=1 if args.quick else 3, min_lr=1e-6, verbose=1),
    ]
    
    print(f"\nPhase 1: Training top layers ({phase1_epochs} epochs max)...")
    history_p1 = model.fit(
        train_gen,
        epochs=phase1_epochs,
        validation_data=val_gen,
        callbacks=callbacks_phase1
    )
    
    # Phase 1 xong → load lại best checkpoint (ModelCheckpoint đã lưu rồi)
    # model hiện tại đang ở best weights nhờ restore_best_weights=True
    best_val_acc_p1 = max(history_p1.history['val_accuracy'])
    print(f"\nPhase 1 best val_accuracy: {best_val_acc_p1:.2%}")
    phase1_weights = model.get_weights()

    if skip_finetune:
        print("\nQuick mode: bỏ qua fine-tuning để tiết kiệm thời gian trên CPU.")
    else:
        # 5. Fine-tuning phase 2 — chỉ chạy nếu phase 1 ổn
        # Dùng ModelCheckpoint riêng để chỉ ghi đè nếu CẢI THIỆN được phase 1
        callbacks_ft = [
            EarlyStopping(patience=4, restore_best_weights=True, monitor='val_accuracy', verbose=1),
            ReduceLROnPlateau(factor=0.5, patience=2, min_lr=1e-7, verbose=1),
        ]

        print(f"\n--- FINE-TUNING (mở thêm 40 layers cuối của {backbone}) ---")
        for layer in base_model.layers[-40:]:
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
        else:
            print(f"\n⚠️  Fine-tuning không cải thiện ({best_val_acc_ft:.2%} < {best_val_acc_p1:.2%})")
            print("   Khôi phục lại trọng số tốt nhất của Phase 1...")
            model.set_weights(phase1_weights)
    
    elapsed = time.time() - t0
    print(f"\n✅ Đã hoàn tất training ({elapsed/60:.1f} phút)")

    # Luôn luôn lưu model vào saved_model_keras bất kể có convert hay không
    import shutil
    print("\nLưu model vào saved_model_keras...")
    if os.path.exists(MODEL_H5):
        shutil.rmtree(MODEL_H5)

    @tf.function(input_signature=[tf.TensorSpec(shape=[None, 224, 224, 3], dtype=tf.float32, name='input')])
    def serving_fn(input_tensor):
        return {'output': model(input_tensor, training=False)}

    tf.saved_model.save(
        model,
        MODEL_H5,
        signatures={'serving_default': serving_fn}
    )
    api_labels_path = os.path.join(MODEL_H5, 'labels.json')
    with open(api_labels_path, 'w', encoding='utf-8') as lf:
        json.dump(class_labels, lf, ensure_ascii=False, indent=2)
    print("✅ Đã lưu model và labels.json thành công vào saved_model_keras")

    # 7. Convert sang TF.js (Optional)
    if args.convert_tfjs:
        try:
            convert_to_tfjs(MODEL_H5, TFJS_OUT_DIR, class_labels)
            print(f"\n✅ Model TF.js (GraphModel) sẵn sàng tại: {TFJS_OUT_DIR}")
            print("   Sẵn sàng host trên Vercel!")
        except Exception as e:
            print(f"\n⚠️  Lỗi convert TF.js: {e}")
    else:
        print(f"\n⚠️  Bỏ qua bước convert TF.js. Chạy với --convert-tfjs để tạo file cho Vercel.")
    
    print("\n--- XONG ---")

if __name__ == '__main__':
    main()
