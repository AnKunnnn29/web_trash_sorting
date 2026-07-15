# 🐍 Hướng Dẫn Sử Dụng Python AI API

## Vấn đề
Model `.h5` không thể convert sang TF.js vì có lỗi incompatibility với MobileNetV2 base layers.

## Giải pháp: Python Flask API Server
Thay vì chạy model trong browser, ta chạy model trên **Python server** và frontend gửi ảnh qua API.

---

## Cách Sử Dụng

### Bước 1: Cài đặt dependencies (đã xong)
```bash
py -3.7 -m pip install flask flask-cors pillow
```

### Bước 2: Khởi động API server
```bash
py -3.7 api_server.py
```

Server sẽ chạy tại: `http://localhost:5000`

### Bước 3: Cấu hình trong Web App
1. Mở web app: `npm run dev`
2. Click nút ⚙️ (Settings) ở góc trên
3. Trong mục **"Python AI API Server"**, nhập: `http://localhost:5000`
4. Click **"Lưu Cấu Hình"**
5. Status indicator sẽ hiển thị: **🐍 Python AI API**

---

## Ưu điểm
✅ Không cần convert model sang TF.js  
✅ Sử dụng trực tiếp file `.h5` đã train  
✅ Inference nhanh hơn (dùng TensorFlow native)  
✅ Không bị lỗi custom layers  
✅ Dễ debug và monitor  

## Nhược điểm
⚠️ Cần chạy Python server song song với web app  
⚠️ Không hoạt động khi deploy lên web hosting tĩnh (cần server backend)  

---

## Thứ Tự Ưu Tiên AI Models
1. 🐍 **Python Flask API** (nếu server đang chạy)
2. 🎓 **Teachable Machine** (nếu có URL trong settings)
3. ✨ **Gemini Vision API** (nếu có API key)
4. 🔍 **MobileNet** (fallback mặc định)

---

## API Endpoints

### `GET /health`
Kiểm tra server status
```json
{
  "status": "ok",
  "model": "loaded",
  "classes": 22
}
```

### `POST /predict`
Nhận diện vật thể trong ảnh

**Request:**
```json
{
  "image": "base64_encoded_jpeg_string"
}
```

**Response:**
```json
{
  "class": "plastic_bottle",
  "confidence": 0.92,
  "emoji": "🍾",
  "name": "Chai nhựa",
  "bin": "recycle"
}
```

---

## Troubleshooting

### Server không khởi động được
- Kiểm tra file `trash_classifier_model.h5` có tồn tại không
- Kiểm tra Python 3.7 và TensorFlow 2.10 đã cài đúng chưa
- Chạy lệnh: `py -3.7 -c "import tensorflow as tf; print(tf.__version__)"`

### Web app không kết nối được
- Kiểm tra server đang chạy: mở `http://localhost:5000/health` trong browser
- Kiểm tra CORS đã enable trong Flask (đã có sẵn trong code)
- Kiểm tra firewall không block port 5000

### Inference chậm
- Python API có thể chậm hơn TF.js khi chạy trên CPU
- Nếu có GPU, cài CUDA để tăng tốc
- Hoặc giảm tần suất gọi API (đã set 1s/lần trong auto-scan mode)

---

## Hosting Production

Khi deploy lên production, bạn có 2 lựa chọn:

### Option A: Deploy Python API lên cloud
- Heroku, Railway, Render, Google Cloud Run
- Update `python_api_url` trong settings thành URL production

### Option B: Dùng Teachable Machine hoặc Gemini API
- Không cần backend Python
- Nhập URL hoặc API key trong settings
- Phù hợp với static hosting (Netlify, Vercel, GitHub Pages)

---

## Files Liên Quan
- `api_server.py` - Flask API server
- `trash_classifier_model.h5` - Trained model (31 MB)
- `public/tfjs_model/labels.json` - Class labels
- `src/main.js` - Frontend logic với API integration
