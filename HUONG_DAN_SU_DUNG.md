# 🎯 Hướng Dẫn Sử Dụng Hệ Thống Phân Loại Rác AI

## ✅ Tình Trạng Hiện Tại

### Đã Hoàn Thành
- ✅ Training model AI với 22 loại rác (3489 ảnh train, 63.6% accuracy)
- ✅ Model đã được lưu: `trash_classifier_model.h5` (10.5 MB)
- ✅ Web app với chế độ auto-scan (không cần bấm nút)
- ✅ Tích hợp Python Flask API server để chạy model
- ✅ Giao diện đẹp, thân thiện với trẻ em

### 22 Loại Rác Đã Train
1. **Tái chế**: plastic, plastic_bottle, plastic_bag, plastic_straw, paper, cardboard, cardboard_box, glass, metal, tin_can, paper_cup
2. **Hữu cơ**: apple, banana, orange, bread, egg_shell, bone, leaf
3. **Nguy hại**: battery
4. **Rác thải**: trash, candy_wrapper, tissue_paper

---

## 🚀 Cách Chạy Hệ Thống

### Bước 1: Khởi động Python API Server
Mở terminal **thứ nhất** và chạy:
```bash
py -3.7 api_server.py
```

Bạn sẽ thấy:
```
🚀 Trash Classification API Server
API running at: http://localhost:5000
Model: trash_classifier_model.h5
Classes: 22
```

### Bước 2: Khởi động Web App
Mở terminal **thứ hai** và chạy:
```bash
npm run dev
```

Web app sẽ mở tại: `http://localhost:3000`

### Bước 3: Cấu hình trong Web App
1. Mở trình duyệt: `http://localhost:3000`
2. Click nút ⚙️ (Cài đặt) ở góc trên phải
3. Trong phần **"Python AI API Server"**, nhập: `http://localhost:5000`
4. Click **"Lưu Cấu Hình & Kết Nối"**
5. Status sẽ hiển thị: **🐍 Python AI API** (màu xanh)

### Bước 4: Bắt Đầu Sử Dụng
1. Click **"Bắt đầu trò chơi 🚀"**
2. Đưa vật rác vào khung hình vuông trên camera
3. Giữ yên trong **1.5 giây** → AI sẽ tự động nhận diện!
4. Hệ thống sẽ hướng dẫn bỏ vào thùng rác đúng

---

## 🎮 Chế Độ Hoạt Động

### 1. Auto-Scan (Mặc định)
- Đưa rác vào camera → AI tự động quét sau 1.5s giữ yên
- Nút hiển thị: **"🤖 Tự động: BẬT"** (màu xanh)
- Thanh tiến trình hiển thị khi đang đếm ngược
- Cooldown 3s sau mỗi lần scan

### 2. Manual Scan (Thủ công)
- Click nút **"🤖 Tự động: BẬT"** để chuyển sang **"✋ Tự động: TẮT"**
- Đưa rác vào camera
- Bấm nút **"📸 Chụp thủ công"** để scan

---

## 🔧 Các Tùy Chọn AI

Hệ thống hỗ trợ nhiều nguồn AI (theo thứ tự ưu tiên):

### 1. 🐍 Python Flask API (Khuyên dùng)
- **Ưu điểm**: Nhanh, chính xác, sử dụng model đã train
- **Cách dùng**: Chạy `py -3.7 api_server.py`
- **Cấu hình**: Nhập `http://localhost:5000` trong Settings

### 2. 🎓 Teachable Machine
- **Ưu điểm**: Không cần backend, dễ train model mới
- **Cách dùng**: 
  1. Train model tại https://teachablemachine.withgoogle.com/
  2. Export model → Copy URL
  3. Paste URL vào Settings

### 3. ✨ Gemini Vision API
- **Ưu điểm**: Cực kỳ chính xác, nhận diện đa dạng
- **Nhược điểm**: Cần API key, tốn quota
- **Cách dùng**:
  1. Lấy free API key: https://aistudio.google.com/
  2. Paste key vào Settings

### 4. 🔍 MobileNet (Fallback)
- **Ưu điểm**: Không cần cấu hình, chạy tự động
- **Nhược điểm**: Độ chính xác thấp với rác
- **Khi nào dùng**: Khi không có option nào khác

---

## 📊 Hiệu Suất Model

### Accuracy đạt được
- **Phase 1 (freeze base)**: 63.6% validation accuracy
- **Fine-tuning**: Không cải thiện (giữ Phase 1)
- **Training time**: 31 phút (CPU)

### Cách cải thiện
1. **Thu thập thêm data**:
   ```bash
   py -3.7 collect_dataset.py
   ```
   
2. **Train lại model**:
   ```bash
   py -3.7 train_dl_model.py
   ```

3. **Khởi động lại API server** để load model mới

---

## 🐛 Xử Lý Lỗi

### Lỗi: API server không khởi động
**Triệu chứng**: `ModuleNotFoundError: No module named 'flask'`

**Giải pháp**:
```bash
py -3.7 -m pip install flask flask-cors pillow
```

### Lỗi: Web app không kết nối API
**Triệu chứng**: Status vẫn hiển thị MobileNet thay vì Python API

**Kiểm tra**:
1. API server có đang chạy? → Mở http://localhost:5000/health
2. URL trong Settings đúng chưa? → Phải là `http://localhost:5000` (không có `/` cuối)
3. CORS có bị block? → Check browser console (F12)

### Lỗi: Camera không hoạt động
**Triệu chứng**: "Không truy cập được Camera"

**Giải pháp**:
1. Cho phép quyền camera trong browser
2. Đảm bảo không có app nào khác đang dùng camera
3. Reload trang (Ctrl+R)

### Lỗi: AI nhận diện sai
**Nguyên nhân**: 
- Vật thể không nằm trong 22 loại đã train
- Ánh sáng kém
- Vật thể bị che khuất
- Model accuracy chưa cao

**Giải pháp**:
1. Tăng ánh sáng
2. Đặt vật thể chính giữa khung hình
3. Giữ camera ổn định
4. Train lại với nhiều data hơn
5. Hoặc dùng Gemini API (chính xác hơn)

---

## 📁 Cấu Trúc Project

```
web_trash_sorting/
├── api_server.py              # 🐍 Flask API server
├── train_dl_model.py          # 🧠 Training script
├── collect_dataset.py         # 📸 Dataset collector
├── convert_model.py           # 🔄 Model converter (không dùng nữa)
├── trash_classifier_model.h5  # 💾 Trained model (10.5 MB)
├── package.json               # 📦 Node.js dependencies
├── vite.config.js             # ⚡ Vite configuration
├── index.html                 # 🎨 Main HTML
├── src/
│   ├── main.js                # 🎯 App logic + AI integration
│   ├── mockData.js            # 📊 Trash items database
│   ├── sound.js               # 🔊 Sound effects
│   └── style.css              # 💅 Styling
├── public/
│   ├── tfjs_model/            # (Không dùng - có lỗi conversion)
│   │   ├── model.json
│   │   ├── group1-shard1of1.bin
│   │   └── labels.json
│   └── sounds/                # 🎵 Audio files
├── dataset/                   # 🖼️ Training images (3489 ảnh)
│   ├── apple/
│   ├── banana/
│   ├── plastic/
│   └── ...
└── README_API.md              # 📖 API documentation
```

---

## 🌐 Deploy Production

### Option A: Deploy Python API
**Platforms**: Heroku, Railway, Render, Google Cloud Run

**Bước 1**: Tạo `requirements.txt`
```txt
tensorflow==2.10.0
flask==2.2.5
flask-cors==5.0.0
pillow==9.5.0
scipy
```

**Bước 2**: Tạo `Procfile`
```
web: python api_server.py
```

**Bước 3**: Deploy và update URL trong Settings

### Option B: Dùng Teachable Machine/Gemini
**Platforms**: Netlify, Vercel, GitHub Pages (static hosting)

**Ưu điểm**: Không cần backend  
**Nhược điểm**: Phải dùng external AI service

---

## 🎓 Tài Liệu Tham Khảo

- [TensorFlow.js](https://www.tensorflow.org/js)
- [Teachable Machine](https://teachablemachine.withgoogle.com/)
- [Google Gemini API](https://aistudio.google.com/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Vite Documentation](https://vitejs.dev/)

---

## 👨‍💻 Hỗ Trợ

Nếu gặp vấn đề, check:
1. Browser console (F12) để xem error logs
2. API server terminal để xem request logs
3. `README_API.md` để hiểu chi tiết về API

---

**🎉 Chúc bạn thành công với dự án Trạm STEAM phân loại rác!**
