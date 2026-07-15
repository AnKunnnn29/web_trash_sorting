# 🥤 Hướng Dẫn Thêm Dataset Lon Nước Ngọt Việt Nam

## 📋 Vấn Đề

Dataset hiện tại có **tin_can** (lon thiếc) nhưng không đủ đa dạng để nhận diện các thương hiệu lon nước ngọt phổ biến tại Việt Nam như:
- 🥤 Coca Cola, Pepsi, Sprite, 7Up, Fanta
- ⚡ Sting, Number 1, Red Bull, Monster
- 🍵 C2, Revive, Lipton, Trà xanh 0 độ

## ✅ Giải Pháp

### Bước 1: Thu Thập Ảnh (Đang Chạy)

Script `collect_soda_cans_vn.py` đang tự động tải 250 ảnh lon nước ngọt từ:
- Wikimedia Commons
- Openverse

**Thời gian**: ~10 phút

### Bước 2: Kiểm Tra & Làm Sạch Dataset

Sau khi script chạy xong:

```bash
# Mở thư mục chứa ảnh
explorer dataset\soda_can
```

**Xem qua và xóa những ảnh:**
- ❌ Không phải lon nước ngọt (chai nhựa, ly giấy)
- ❌ Ảnh quá mờ hoặc quá tối
- ❌ Ảnh có watermark lớn che khuất
- ❌ Ảnh chứa quá nhiều vật thể khác

**Giữ lại:**
- ✅ Lon nước ngọt rõ ràng (đầy hoặc rỗng)
- ✅ Góc chụp đa dạng (trên, nghiêng, nằm)
- ✅ Nhiều thương hiệu khác nhau
- ✅ Background đa dạng

**Mục tiêu**: Giữ lại ít nhất **150-200 ảnh tốt**

### Bước 3: Train Lại Model

```bash
# Chạy training với dataset mới
py -3.7 train_dl_model.py
```

**Thời gian**: ~30-45 phút (tùy dataset size)

Model mới sẽ:
- Có thêm class **soda_can** (hoặc update **tin_can** với data mới)
- Nhận diện lon nước ngọt Việt Nam chính xác hơn
- File output: `trash_classifier_model.h5`

### Bước 4: Test Model Mới

**Option A: Dùng Python API**
```bash
# Terminal 1: Khởi động API (model mới tự động load)
py -3.7 api_server.py

# Terminal 2: Khởi động web
npm run dev
```

**Option B: Dùng Teachable Machine**
- Train lại model trên https://teachablemachine.withgoogle.com/
- Upload ảnh từ `dataset/soda_can/`
- Test và export

### Bước 5: Deploy

Model mới sẽ tự động được sử dụng. Không cần thay đổi code!

---

## 📊 Kết Quả Mong Đợi

### Trước khi thêm dataset
```
Lon Coca Cola  → ❌ Nhận diện thành "metal" (chung chung)
Lon Sting      → ❌ Nhận diện thành "tin_can" (không chính xác)
Lon Pepsi      → ❌ Không nhận diện được
```

### Sau khi thêm dataset + train lại
```
Lon Coca Cola  → ✅ Nhận diện thành "soda_can" (80%+ confidence)
Lon Sting      → ✅ Nhận diện thành "soda_can" (75%+ confidence)
Lon Pepsi      → ✅ Nhận diện thành "soda_can" (80%+ confidence)
```

---

## 🎯 Tips Cải Thiện Accuracy

### 1. Chụp thêm ảnh thật từ trường học
```
- Mang các lon nước ngọt phổ biến đến trường
- Chụp ~20-30 ảnh/thương hiệu
- Góc chụp: trên, nghiêng, nằm ngang
- Background: bàn, sàn, tay cầm
- Lưu vào: dataset/soda_can/
```

### 2. Data Augmentation
Training script đã tự động làm:
- ✅ Xoay ảnh (±25°)
- ✅ Zoom in/out (±20%)
- ✅ Điều chỉnh độ sáng
- ✅ Lật ngang

### 3. Thêm nhiều classes riêng
Nếu muốn phân biệt từng thương hiệu:
```
dataset/
├── coca_cola/       (150 ảnh)
├── pepsi/           (150 ảnh)
├── sting/           (150 ảnh)
├── number_one/      (150 ảnh)
└── c2_tea/          (150 ảnh)
```

Nhưng điều này cần:
- **Nhiều data hơn**: 150+ ảnh/thương hiệu
- **Training lâu hơn**: ~1-2 giờ
- **Accuracy có thể thấp hơn**: Do các thương hiệu giống nhau

**Khuyến nghị**: Giữ nguyên **soda_can** (tất cả lon nước ngọt) để model đơn giản và chính xác hơn.

---

## 🔄 Workflow Cập Nhật Dataset

### Khi cần thêm data cho bất kỳ loại rác nào:

1. **Thu thập ảnh**
   ```bash
   # Sửa keywords trong collect_dataset.py hoặc tạo script mới
   py -3.7 collect_soda_cans_vn.py
   ```

2. **Làm sạch dataset**
   ```bash
   # Xem và xóa ảnh không phù hợp
   explorer dataset\soda_can
   ```

3. **Train lại**
   ```bash
   py -3.7 train_dl_model.py
   ```

4. **Test**
   ```bash
   # Python API
   py -3.7 api_server.py
   
   # Hoặc Teachable Machine
   # Upload ảnh và train online
   ```

5. **Deploy**
   - Model mới tự động được sử dụng
   - Không cần thay đổi code frontend

---

## 📈 Theo Dõi Progress

### Check số lượng ảnh hiện có
```bash
dir dataset\soda_can
```

### Check training progress
Khi chạy `train_dl_model.py`, theo dõi:
```
Epoch 1/30
110/110 [==============================] - 73s
loss: 2.1962 - accuracy: 0.3775 - val_accuracy: 0.4930

→ val_accuracy càng cao càng tốt (mục tiêu: >70%)
```

### Test inference speed
```bash
# API server sẽ log mỗi request
py -3.7 api_server.py

# Check terminal output khi test:
[INFO] Prediction: soda_can (0.85) - 245ms
```

---

## 🐛 Troubleshooting

### Script download bị lỗi
```
Error: Expecting value: line 1 column 1
```
→ API timeout, chạy lại script (nó sẽ tiếp tục từ chỗ dừng)

### Training bị OOM (Out of Memory)
```
ResourceExhaustedError: OOM when allocating tensor
```
→ Giảm BATCH_SIZE trong `train_dl_model.py`:
```python
BATCH_SIZE = 16  # Thay vì 32
```

### Model không cải thiện
```
val_accuracy stuck at 60%
```
→ Cần thêm data:
- Chụp thêm ảnh thật
- Hoặc dùng Gemini API (không cần train)

---

## 🎓 Best Practices

### 1. Quality > Quantity
- **150 ảnh tốt** > **500 ảnh tệ**
- Ảnh rõ nét, đa dạng góc độ
- Không cần HD, 640x480 là đủ

### 2. Balance Dataset
- Mỗi class nên có số lượng ảnh tương đương
- soda_can: 200 ảnh
- plastic_bottle: 127 ảnh → Thu thập thêm để balance

### 3. Regular Retraining
- Mỗi 1-2 tuần, thu thập thêm 50-100 ảnh mới
- Train lại model
- Accuracy sẽ tăng dần theo thời gian

### 4. Monitor Real Usage
- Theo dõi những loại rác nào bị nhận diện sai
- Ưu tiên thu thập thêm data cho loại đó
- Cải thiện từng bước

---

## 📞 Support

Nếu gặp vấn đề:
1. Check console logs (F12)
2. Check API server logs
3. Xem lại [HUONG_DAN_SU_DUNG.md](HUONG_DAN_SU_DUNG.md)

---

**🥤 Chúc bạn thành công với dataset lon nước ngọt!**
