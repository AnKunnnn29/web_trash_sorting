# 🌍 Trạm STEAM Phân Loại Rác Thông Minh

> **Hệ thống nhận diện và phân loại rác tự động dùng AI, dành cho trẻ em học về bảo vệ môi trường**

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.7-blue.svg)
![TensorFlow](https://img.shields.io/badge/tensorflow-2.10-orange.svg)
![Node](https://img.shields.io/badge/node-24.x-green.svg)

---

## ✨ Tính Năng

- 🤖 **Auto-Scan**: Đưa rác vào camera → AI tự động nhận diện sau khoảng 0.7s ổn định
- 🎯 **31 loại rác**: Plastic, Paper, Glass, Metal, Organic, Battery, v.v.
- 🧠 **AI nhất quán**: Cùng model TF.js và heuristic trên localhost lẫn Vercel
- 🎨 **Giao diện thân thiện**: Thiết kế dành cho trẻ em, có âm thanh + hiệu ứng
- 📊 **Theo dõi tiến độ**: Điểm số, accuracy, leaderboard
- 🌐 **Deploy dễ dàng**: Frontend và model chạy trực tiếp trên Vercel

---

## 🎨 Open Design System

Giao diện sử dụng package `design-systems/ecosort/` theo hợp đồng Open Design:

- `manifest.json`: metadata và các file chuẩn của package.
- `DESIGN.md`: nguyên tắc thương hiệu, component, accessibility và anti-pattern.
- `tokens.css`: nguồn chuẩn cho màu sắc, typography, spacing, radius, elevation và motion.

Khi thay đổi giao diện, cập nhật `DESIGN.md` trước nếu quyết định thiết kế thay đổi, sau đó chỉnh token tương ứng trong `tokens.css`. Không thêm màu, shadow, radius hoặc thời lượng chuyển động trực tiếp vào component nếu đã có semantic token phù hợp.

`src/style.css` import trực tiếp package này, vì vậy các token được sử dụng trong bản build thực tế.

## 🚀 Quick Start

### Development (Local)

```bash
npm install
npm run dev
```

Mở URL do Vite hiển thị. Model chạy trực tiếp trong trình duyệt; không cần khởi động Python API.

### Deploy (Production)

**Vercel (khuyên dùng)**
```bash
npm run build
```

Kết nối repository GitHub với Vercel, dùng build command `npm run build` và output directory `dist`. Vercel và localhost đều tải `public/tfjs_model/model.json`, cùng ba weight shard và cùng pipeline hậu xử lý.

**Chi tiết đầy đủ**: [DEPLOY_GUIDE.md](DEPLOY_GUIDE.md)

---

## 📋 Cài Đặt

### Requirements
- **Python 3.7** (để chạy model)
- **Node.js 24+** (để build frontend)
- **Webcam** (để chụp ảnh)

### Installation

```bash
# 1. Clone repo
git clone https://github.com/your-username/web_trash_sorting.git
cd web_trash_sorting

# 2. Install Python dependencies
py -3.7 -m pip install flask flask-cors pillow tensorflow==2.10.0 scipy

# 3. Install Node dependencies
npm install

# 4. Build frontend
npm run build
```

---

## 🧠 Model AI

### Hiện Tại
- **Architecture**: MobileNetV2 Transfer Learning
- **Classes**: 22 loại rác phổ biến
- **Training data**: 3489 ảnh (80% train, 20% validation)
- **Validation accuracy**: 63.6%
- **Size**: 10.5 MB (.h5 format)

### Train Lại Model

```bash
# 1. Thu thập thêm ảnh (tùy chọn)
py -3.7 collect_dataset.py

# 2. Train model
py -3.7 train_dl_model.py

# 3. Model mới sẽ được lưu tại: trash_classifier_model.h5
```

---

## 📁 Cấu Trúc Project

```
web_trash_sorting/
├── api_server.py              # 🐍 Flask API server
├── train_dl_model.py          # 🧠 Training script
├── trash_classifier_model.h5  # 💾 Trained model
│
├── src/
│   ├── main.js                # 🎯 App logic
│   ├── mockData.js            # 📊 Trash database
│   ├── sound.js               # 🔊 Sound effects
│   └── style.css              # 💅 Styling
│
├── public/
│   ├── sounds/                # 🎵 Audio files
│   └── tfjs_model/            # ⚠️ Không dùng (lỗi conversion)
│
├── dataset/                   # 🖼️ Training images (3489 ảnh)
│   ├── plastic/
│   ├── paper/
│   └── ...
│
└── docs/
    ├── HUONG_DAN_SU_DUNG.md  # 📖 Hướng dẫn tiếng Việt
    ├── DEPLOY_GUIDE.md       # 🚀 Deploy options
    ├── README_API.md         # 🔌 API docs
    └── QUICK_START.md        # ⚡ Quick reference
```

---

## 🎓 Sử Dụng

### Chế Độ Auto-Scan (Mặc định)
1. Bấm **"Bắt đầu trò chơi"**
2. Đưa rác vào khung vuông trên camera
3. Giữ yên **1.5 giây** → AI tự động scan
4. Làm theo hướng dẫn bỏ rác vào đúng thùng

### Chế Độ Manual
1. Click nút **"🤖 Tự động: BẬT"** → Chuyển sang **"✋ Tự động: TẮT"**
2. Đưa rác vào camera
3. Bấm **"📸 Chụp thủ công"**

### AI khi deploy

Model TF.js đóng gói trong repository là engine mặc định ở mọi hostname. Pipeline gồm cùng preprocessing 224×224, confidence gate, lọc ổn định 3/5 frame và heuristic cho lon đỏ/giấy trắng. `api_server.py` chỉ còn là công cụ kiểm thử backend độc lập, không được frontend tự động ưu tiên trên localhost.

---

## 🌐 Deployment Options

### Option 1: Static + Teachable Machine (Free)
✅ Miễn phí hoàn toàn  
✅ Deploy đơn giản (Netlify)  
⚠️ Phải train lại model

**Best for**: Học đường, demo, prototype

### Option 2: Full Stack (Backend + Frontend)
✅ Dùng model đã train  
✅ Kiểm soát hoàn toàn  
⚠️ Chi phí $5-15/tháng

**Best for**: Production, nhiều user

### Option 3: Static + Gemini API
✅ Accuracy cao nhất (95%+)  
✅ Deploy đơn giản  
⚠️ Chi phí API ($0-10/tháng)

**Best for**: Budget không giới hạn

**Chi tiết**: [DEPLOY_GUIDE.md](DEPLOY_GUIDE.md)

---

## 🛠️ Tech Stack

### Frontend
- **Vite** - Build tool
- **Vanilla JS** - No framework overhead
- **TensorFlow.js** - ML in browser
- **Web APIs** - Camera, Audio, Canvas

### Backend (Optional)
- **Flask** - Python web framework
- **TensorFlow 2.10** - Model inference
- **Gunicorn** - Production server
- **Pillow** - Image processing

### AI/ML
- **MobileNetV2** - Base architecture
- **Transfer Learning** - Fine-tuned for trash
- **Data Augmentation** - Rotation, zoom, brightness
- **Early Stopping** - Prevent overfitting

---

## 📊 Performance

### Model Metrics
- **Validation Accuracy**: 63.6%
- **Training Time**: 31 minutes (CPU)
- **Inference Time**: phụ thuộc CPU/GPU và WebGL của trình duyệt; model chạy phía client

### Cách Cải Thiện
1. Thu thập thêm 100-200 ảnh/class
2. Train lâu hơn (thêm epochs)
3. Dùng augmentation mạnh hơn
4. Hoặc chuyển sang Gemini API (accuracy 95%+)

---

## 🐛 Troubleshooting

### Model convert lỗi
→ Chạy `npm run validate` để kiểm tra model, labels và đủ ba weight shard trước khi deploy.

### Camera không hoạt động
→ Cho phép quyền camera trong browser settings

### Nhận diện sai
→ Tăng ánh sáng, giữ camera ổn định, hoặc dùng Gemini API

**Chi tiết**: [HUONG_DAN_SU_DUNG.md](HUONG_DAN_SU_DUNG.md)

---

## 📚 Documentation

- [🇻🇳 Hướng Dẫn Sử Dụng](HUONG_DAN_SU_DUNG.md) - Đầy đủ tiếng Việt
- [🚀 Deploy Guide](DEPLOY_GUIDE.md) - 3 deployment options
- [🔌 API Reference](README_API.md) - Backend API docs
- [⚡ Quick Start](QUICK_START.md) - Quick reference card

---

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork repo
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

---

## 📝 License

MIT License - see [LICENSE](LICENSE) file

---

## 👏 Credits

- **MobileNetV2**: Google Research
- **TensorFlow**: Google
- **Teachable Machine**: Google Creative Lab
- **Icons**: Emoji characters
- **Dataset**: Wikimedia Commons + Openverse

---

## 📧 Contact

- **Author**: Thanh An Nguyen
- **Project**: Trạm STEAM Phân Loại Rác
- **GitHub**: [web_trash_sorting](https://github.com/your-username/web_trash_sorting)

---

**⭐ Nếu project này hữu ích, hãy cho 1 star nhé! ⭐**

---

## 🗺️ Roadmap

- [ ] Support thêm 50+ loại rác
- [ ] Multi-language (English, Vietnamese)
- [ ] Mobile app (React Native)
- [ ] Raspberry Pi integration
- [ ] Arduino/ESP32 hardware control
- [ ] Voice instructions cho trẻ nhỏ
- [ ] Gamification với badges & rewards
- [ ] Teacher dashboard với analytics

---

Made with ❤️ for a cleaner planet 🌍
