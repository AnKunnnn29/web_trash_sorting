# ⚡ Quick Start - Phân Loại Rác AI

## 🏃 Chạy Local (Development)

### Terminal 1: API Server
```bash
py -3.7 api_server.py
```
✅ Server chạy tại: http://localhost:5000

### Terminal 2: Web App
```bash
npm run dev
```
✅ Web app tại: http://localhost:3000

### Cấu hình trong Web
1. Click ⚙️ Settings
2. **Python AI API Server**: `http://localhost:5000`
3. Click **Lưu Cấu Hình**
4. Status: 🐍 **Python AI API** (màu xanh)

---

## 🌐 Deploy Production

### 🎓 Option A: Teachable Machine (KHUYÊN DÙNG - Free)
```bash
# 1. Train model tại https://teachablemachine.withgoogle.com/
# 2. Build frontend
npm run build

# 3. Deploy dist/ lên Netlify (drag & drop)
# 4. Vào Settings → Nhập Teachable Machine URL
```

### 🌐 Option B: Full Stack (Backend + Frontend)
```bash
# 1. Deploy backend
# - Push code (với api_server.py, requirements.txt, .h5) lên GitHub
# - Connect với Render.com
# - URL: https://your-api.onrender.com

# 2. Deploy frontend
npm run build
# - Deploy dist/ lên Netlify
# - Vào Settings → Nhập backend URL
```

### ✨ Option C: Gemini Vision (Paid API)
```bash
# 1. Lấy API key từ https://aistudio.google.com/
# 2. Build & deploy
npm run build
# 3. Vào Settings → Nhập Gemini API key
```

**Chi tiết**: Xem `DEPLOY_GUIDE.md`

---

## 📁 Files Quan Trọng

### Development
- `api_server.py` - Backend API (chạy model .h5)
- `src/main.js` - Frontend logic + AI integration
- `train_dl_model.py` - Train model mới
- `collect_dataset.py` - Thu thập thêm ảnh

### Deployment
- `dist/` - Built frontend (sau `npm run build`)
- `requirements.txt` - Python dependencies cho backend
- `Procfile` - Config cho Render/Heroku
- `.gitignore` - Loại trừ files nặng khỏi Git

### Documentation
- `HUONG_DAN_SU_DUNG.md` - Hướng dẫn đầy đủ tiếng Việt
- `DEPLOY_GUIDE.md` - Chi tiết 3 options deploy
- `README_API.md` - API documentation

---

## 🐛 Fix Lỗi Nhanh

### API không chạy
```bash
py -3.7 -m pip install flask flask-cors pillow
```

### Web không connect API
1. Kiểm tra API đang chạy: http://localhost:5000/health
2. Check Settings có đúng URL không
3. Reload web (Ctrl+R)

### Camera không hoạt động
1. Cho phép quyền camera trong browser
2. Close apps khác đang dùng camera

### AI nhận diện sai
1. Tăng ánh sáng
2. Đặt vật chính giữa khung hình
3. Giữ camera ổn định 1.5s
4. Hoặc dùng Gemini API (chính xác hơn)

---

## 💡 Tips

### Train model chính xác hơn
```bash
# Thu thập thêm 100-200 ảnh/loại
py -3.7 collect_dataset.py

# Train lại
py -3.7 train_dl_model.py
```

### Deploy nhanh nhất
1. Train trên Teachable Machine (30 phút)
2. Build: `npm run build`
3. Drag & drop `dist/` lên Netlify
4. Done! ✅

### Tiết kiệm chi phí
- Development: Python API (free local)
- Production: Teachable Machine (free) hoặc Gemini API ($0-10/tháng)

---

## 📊 Model Hiện Tại

- **22 classes**: apple, banana, battery, bone, bread, candy_wrapper, cardboard, cardboard_box, egg_shell, glass, leaf, metal, orange, paper, paper_cup, plastic, plastic_bag, plastic_bottle, plastic_straw, tin_can, tissue_paper, trash
- **Training data**: 3489 ảnh
- **Validation accuracy**: 63.6%
- **Model size**: 10.5 MB (.h5)

---

## 🆘 Cần Trợ Giúp?

1. Đọc `HUONG_DAN_SU_DUNG.md` (chi tiết)
2. Đọc `DEPLOY_GUIDE.md` (deploy options)
3. Check browser console (F12) xem error logs
4. Check API server terminal xem request logs

---

**🎉 Chúc bạn thành công!**
