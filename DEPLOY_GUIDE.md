# 🚀 Hướng Dẫn Deploy Lên Web

## Cấu hình hiện tại: Vercel + Qwen backend

EcoSort chỉ còn hai chế độ nhận diện: Qwen Vision và model EcoSort Local. Qwen được gọi qua Vercel Function tại `/api/qwen-vision`; API key không nằm trong mã JavaScript phía trình duyệt.

1. Trong Vercel, mở **Project → Settings → Environment Variables**.
2. Thêm `QWEN_API_KEY` với giá trị key DashScope. Không dùng tiền tố `VITE_`.
3. Tùy chọn: thêm `QWEN_ALLOWED_ORIGINS` với domain production, ví dụ `https://ecosort.vercel.app`.
4. Áp dụng cho **Production** và **Preview** nếu cần, sau đó redeploy.
5. Trong **Firewall**, tạo rate-limit rule cho đường dẫn `/api/qwen-vision`, giới hạn khoảng 20–24 request/phút/IP.

Nếu Qwen hết quota, hết hạn hoặc lỗi xác thực, frontend tự chuyển sang model EcoSort Local.

---

## 📊 So Sánh 3 Options

| Tiêu chí | Option 1: Full Stack | Option 2: Teachable Machine | Option 3: Gemini API |
|----------|---------------------|----------------------------|---------------------|
| **Độ khó** | 🔴 Khó | 🟢 Dễ | 🟢 Dễ |
| **Chi phí** | 💰 $5-15/tháng | ✅ Miễn phí | 💰 ~$1/1000 requests |
| **Accuracy** | 🟡 63.6% | 🟡 60-70% | 🟢 95%+ |
| **Setup time** | ⏱️ 1-2 giờ | ⏱️ 30 phút | ⏱️ 10 phút |
| **Maintenance** | 🔴 Cao | 🟢 Thấp | 🟢 Thấp |

**Khuyến nghị**: 
- Dự án học đường, demo → **Option 2 (Teachable Machine)**
- Production, nhiều người dùng → **Option 1 (Full Stack)**
- Budget không giới hạn, cần best quality → **Option 3 (Gemini)**

---

## 🎓 Option 2: Teachable Machine (KHUYÊN DÙNG)

### Bước 1: Train Model Mới

1. Mở https://teachablemachine.withgoogle.com/
2. Chọn **Image Project** → **Standard image model**
3. Tạo 22 classes tương ứng:
   - Tái chế: Plastic, Paper, Cardboard, Glass, Metal, etc.
   - Hữu cơ: Apple, Banana, Orange, etc.
   - Nguy hại: Battery
   - Rác thải: Trash

4. Upload ảnh từ `dataset/` folder:
   ```
   Click "Upload" → Select all images in dataset/plastic/ → Add to "Plastic" class
   Click "Upload" → Select all images in dataset/paper/ → Add to "Paper" class
   ... (lặp lại cho 22 classes)
   ```

5. Click **"Train Model"** (chờ 5-10 phút)

6. Test model bằng webcam

7. Click **"Export Model"** → **"Upload my model"** 
   - Copy URL: `https://teachablemachine.withgoogle.com/models/xxxxx/`

### Bước 2: Build Frontend

```bash
npm run build
```

Folder `dist/` sẽ được tạo với các file sau:
```
dist/
├── index.html
├── assets/
│   ├── main-[hash].js
│   └── style-[hash].css
└── sounds/
```

### Bước 3: Deploy Lên Netlify

#### Cách 1: Drag & Drop (Đơn giản nhất)

1. Mở https://app.netlify.com/
2. Đăng ký/Đăng nhập (miễn phí)
3. Click **"Add new site"** → **"Deploy manually"**
4. Kéo thả folder `dist/` vào
5. Đợi 30 giây → Có link: `https://your-app-name.netlify.app`

#### Cách 2: GitHub (Tự động deploy khi push code)

1. Push code lên GitHub:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/your-username/trash-sorting.git
   git push -u origin main
   ```

2. Vào Netlify → **"Import from Git"** → Connect GitHub

3. Settings:
   - **Build command**: `npm run build`
   - **Publish directory**: `dist`

4. Click **"Deploy"**

### Bước 4: Cấu Hình Teachable Machine URL

1. Mở web app đã deploy: `https://your-app.netlify.app`
2. Click ⚙️ Settings
3. Trong mục **"Link mô hình AI (Teachable Machine)"**:
   - Paste URL từ Bước 1: `https://teachablemachine.withgoogle.com/models/xxxxx/`
4. Click **"Lưu Cấu Hình"**
5. Status sẽ hiển thị: **🎓 Teachable Machine sẵn sàng**

### ✅ Hoàn Thành!

Web app giờ đã hoạt động hoàn toàn online!

---

## 🌐 Option 1: Full Stack (Frontend + Backend)

### Phần A: Deploy Backend (Python API)

#### A1: Chuẩn Bị Files

Tạo `requirements.txt`:
```txt
tensorflow==2.10.0
flask==2.2.5
flask-cors==5.0.0
pillow==9.5.0
scipy
gunicorn==21.2.0
```

Tạo `Procfile` (cho Heroku/Render):
```
web: gunicorn api_server:app
```

Sửa `api_server.py` (thay dòng cuối):
```python
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
```

#### A2: Deploy Lên Render (Miễn Phí)

1. Đăng ký https://render.com/
2. Click **"New"** → **"Web Service"**
3. Connect GitHub repository
4. Settings:
   - **Environment**: Python 3.7
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn api_server:app`
   - **Instance Type**: Free

5. Thêm file vào repo:
   - `api_server.py`
   - `requirements.txt`
   - `trash_classifier_model.h5`
   - `public/tfjs_model/labels.json`
   - `src/mockData.js`

6. Click **"Create Web Service"**

7. Đợi 5-10 phút → Có URL: `https://your-api.onrender.com`

8. Test: Mở `https://your-api.onrender.com/health` → Phải thấy:
   ```json
   {"status":"ok","model":"loaded","classes":22}
   ```

#### A3: Tối Ưu Backend

**⚠️ Lưu ý**: Free tier của Render sẽ sleep sau 15 phút không dùng → Cold start ~30s

**Giải pháp**:
1. Nâng cấp lên paid tier ($7/tháng) → Always online
2. Hoặc dùng Railway.app (free 500h/tháng)
3. Hoặc setup cron job ping server mỗi 10 phút

### Phần B: Deploy Frontend

1. Build với API URL:
   ```bash
   # Không cần thay đổi gì, chỉ build
   npm run build
   ```

2. Deploy lên Netlify (như Option 2)

3. Sau khi deploy, vào Settings:
   - Nhập **"Python AI API Server"**: `https://your-api.onrender.com`
   - Click **"Lưu Cấu Hình"**

### ✅ Hoàn Thành!

---

## ✨ Option 3: Gemini Vision API

### Bước 1: Lấy API Key

1. Mở https://aistudio.google.com/
2. Đăng nhập Google
3. Click **"Get API Key"** → **"Create API key in new project"**
4. Copy API key (dạng: `AIzaSyXXXXXXXXXXXXXXXXXXXXX`)

### Bước 2: Deploy Frontend

```bash
npm run build
```

Deploy `dist/` lên Netlify (như Option 2)

### Bước 3: Cấu Hình API Key

1. Mở web app: `https://your-app.netlify.app`
2. Click ⚙️ Settings
3. Trong mục **"Khóa API Gemini (Vision AI)"**:
   - Paste API key vừa copy
4. Click **"Lưu Cấu Hình"**
5. Status sẽ hiển thị: **✨ Gemini Vision**

### ⚠️ Giới Hạn Free Tier

- **15 requests/phút**
- **1500 requests/ngày**
- Nếu vượt quá → Nâng cấp lên paid: $0.00025/image

### ✅ Hoàn Thành!

---

## 🔧 Cấu Hình Domain Tùy Chỉnh

### Netlify
1. Vào **Site settings** → **Domain management**
2. Click **"Add custom domain"**
3. Nhập domain: `trash-sorting.yourdomain.com`
4. Cập nhật DNS:
   ```
   Type: CNAME
   Name: trash-sorting
   Value: your-app.netlify.app
   ```

### Render (Backend)
1. Vào **Settings** → **Custom Domains**
2. Add domain: `api.yourdomain.com`
3. Cập nhật DNS theo hướng dẫn

---

## 🐛 Troubleshooting

### Lỗi: CORS khi gọi API từ frontend
**Nguyên nhân**: Backend chưa cho phép domain frontend

**Giải pháp**: Sửa `api_server.py`:
```python
from flask_cors import CORS
app = Flask(__name__)
CORS(app, origins=['https://your-app.netlify.app'])
```

### Lỗi: Model file quá lớn (>100MB)
**Nguyên nhân**: GitHub không cho phép file >100MB

**Giải pháp**:
1. Dùng Git LFS:
   ```bash
   git lfs install
   git lfs track "*.h5"
   git add .gitattributes
   git commit -m "Add Git LFS"
   ```

2. Hoặc host model trên Google Drive/Dropbox và download khi deploy

### Lỗi: API server chậm (cold start)
**Nguyên nhân**: Free tier của Render/Heroku sleep sau 15 phút

**Giải pháp**:
1. Nâng cấp paid tier
2. Setup ping script (keep-alive)
3. Dùng Railway (ít bị sleep hơn)

---

## 💰 Chi Phí Ước Tính

### Option 2: Teachable Machine
- **Frontend (Netlify)**: $0/tháng
- **Total**: **$0/tháng** ✅

### Option 1: Full Stack
- **Frontend (Netlify)**: $0/tháng
- **Backend (Render Free)**: $0/tháng (có giới hạn)
- **Backend (Render Paid)**: $7/tháng
- **Backend (Railway)**: $5/tháng (500h free)
- **Total**: **$0-7/tháng**

### Option 3: Gemini API
- **Frontend (Netlify)**: $0/tháng
- **Gemini API**: 
  - Free tier: 1500 requests/ngày = $0
  - Paid: $0.00025/image ≈ $2.5/10,000 images
- **Total**: **$0-10/tháng** (tùy lưu lượng)

---

## 📝 Checklist Deploy

### Trước khi deploy
- [ ] Test kỹ local (cả 3 AI options)
- [ ] Build thử: `npm run build`
- [ ] Check `dist/` folder có đầy đủ files
- [ ] Commit code lên Git

### Option 1 (Full Stack)
- [ ] Deploy backend lên Render/Railway
- [ ] Test API endpoint: `/health`
- [ ] Deploy frontend lên Netlify
- [ ] Update API URL trong Settings
- [ ] Test full flow trên production

### Option 2 (Teachable Machine)
- [ ] Train model trên Teachable Machine
- [ ] Test model accuracy
- [ ] Export và copy URL
- [ ] Deploy frontend lên Netlify
- [ ] Update Teachable Machine URL
- [ ] Test full flow

### Option 3 (Gemini)
- [ ] Lấy Gemini API key
- [ ] Test API với sample request
- [ ] Deploy frontend lên Netlify
- [ ] Update API key trong Settings
- [ ] Test full flow

---

## 🎯 Kết Luận

**Dự án học đường → Option 2 (Teachable Machine)**
- Miễn phí, đơn giản, đủ tốt cho demo

**Dự án thật, nhiều user → Option 1 (Full Stack)**
- Kiểm soát hoàn toàn, không giới hạn requests

**Cần accuracy cao nhất → Option 3 (Gemini)**
- Chất lượng tốt nhất nhưng tốn phí

**Khuyến nghị của tôi**: Bắt đầu với **Option 2**, nếu user base tăng thì nâng cấp lên **Option 1**.

---

**📚 Tài liệu tham khảo:**
- [Netlify Docs](https://docs.netlify.com/)
- [Render Docs](https://render.com/docs)
- [Teachable Machine](https://teachablemachine.withgoogle.com/)
- [Gemini API](https://ai.google.dev/)
