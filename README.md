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

### Kiểm tra chất lượng

```bash
# Validate mapping/model, chạy unit test, build và browser test
npm run check:full

# Chạy smoke benchmark với SavedModel hiện tại
npm run evaluate:ai
```

Chi tiết kết quả nhận diện nằm trong
[reports/ai-baseline.md](reports/ai-baseline.md). Benchmark này dùng ảnh trong
dataset hiện tại nên phù hợp để phát hiện hồi quy, không thay thế tập test độc lập.

Kế hoạch bổ sung dữ liệu Việt Nam và chống overfitting:
[DATA_AND_OVERFITTING_PLAN.md](DATA_AND_OVERFITTING_PLAN.md).

Kết quả split sạch và train model ứng viên:

- [reports/training-split.md](reports/training-split.md)
- [reports/training-candidate-summary.md](reports/training-candidate-summary.md)
- [PROJECT_AI_COMPLETION_REPORT.md](PROJECT_AI_COMPLETION_REPORT.md)

### Thu thập ảnh qua Google

Collector dùng Google Programmable Search JSON API và chỉ tải kết quả vào
`dataset_review/google`; không tự động đưa ảnh vào training:

```powershell
# Xem toàn bộ truy vấn mà không cần credentials
npm run collect:google:plan

# Tài khoản Google API hiện có
$env:GOOGLE_CSE_API_KEY = "..."
$env:GOOGLE_CSE_ID = "..."

# Thu thập một hoặc nhiều nhóm
npm run collect:google -- --target kun-carton --target lof-carton --target milo-carton
```

Kết quả gồm contact sheet, provenance URL và báo cáo coverage. Bộ lọc Creative
Commons của Google chỉ hỗ trợ tìm kiếm; vẫn phải mở `context_url`, xác minh giấy
phép và kiểm duyệt đúng vật thể trước khi promotion.

Nếu không có Google API key, dùng nguồn mở không cần credentials:

```powershell
npm run collect:open-images -- --target kun-carton --target lof-carton --target milo-carton
npm run collect:open-images
```

Nguồn gồm Openverse và Wikimedia Commons; metadata tác giả, giấy phép và trang
gốc được giữ trong `data_provenance/open-images.jsonl`. Ảnh mới luôn đi vào
`dataset_review/open_images` trước. Sau khi duyệt contact sheet, cập nhật
`config/open-image-review.json` rồi mới chạy:

```powershell
npm run promote:open-images
```

Thu thập bổ sung hộp sữa/hộp đồ uống giấy theo category và metadata bao bì của
Open Food Facts:

```powershell
npm run collect:milk-cartons
```

Ảnh được lưu trong `dataset_review/milk_carton_structured`. Sau khi cập nhật
`config/milk-carton-structured-review.json`, chạy:

```powershell
npm run promote:milk-cartons
```

### Kiểm tra trước khi train

Mỗi lần dữ liệu thay đổi, tạo lại split và các holdout cố định rồi chạy readiness
gate:

```powershell
npm run prepare:training-data
npm run prepare:pretraining-assets
npm run check:pretraining
```

Không bắt đầu train nếu gate có trạng thái `FAIL`. Trạng thái `WARN` về
real-camera holdout không chặn một experiment, nhưng chặn việc thay model đang
chạy. Ảnh camera hoàn toàn mới được đặt tại
`evaluation/real_camera_holdout` và tuyệt đối không sao chép vào train trước khi
so sánh model.

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
- **Architecture**: EfficientNetB0 Transfer Learning
- **Classes**: 31 loại rác
- **Training data local**: 9.680 ảnh trong 44 thư mục, ánh xạ về 31 nhãn
- **Duplicate-safe split**: 5.042 train, 1.079 validation, 1.079 test và 15 external test
- **Baseline smoke accuracy**: 68,4% trên 310 ảnh từ dataset hiện có
- **Model trình duyệt**: TF.js Graph Model, khoảng 10 MB
- **Trạng thái model**: giữ baseline; các ứng viên E2/E4 chưa vượt quality gate

> Smoke benchmark có thể chứa ảnh đã dùng khi train và chỉ phù hợp để phát hiện
> hồi quy. Xem báo cáo tại [reports/ai-baseline.md](reports/ai-baseline.md).

### Train Lại Model

```bash
# 1. Thu thập thêm ảnh (tùy chọn)
py -3.7 collect_dataset.py

# 2. Tạo split cố định, loại duplicate và label conflict
npm run prepare:training-data

# 3. Train ứng viên trong thư mục riêng, không ghi đè baseline
npm run train:candidate:e2
npm run train:candidate:e4

# 4. Đánh giá baseline và tổng hợp quality gate
npm run evaluate:clean-split
npm run summarize:training
```

Chỉ convert/đưa model ứng viên vào `public/tfjs_model` sau khi báo cáo quality
gate kết luận `REPLACE baseline`.

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
├── dataset/                   # 🖼️ Training images (9.620 ảnh)
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
- **Smoke Accuracy**: 68,4%
- **Macro F1**: 66,4%
- **Coverage tại threshold 45%**: 65,5%
- **Accuracy trên dự đoán được chấp nhận**: 84,2%
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
