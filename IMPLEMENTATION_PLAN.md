# Kế hoạch phát triển EcoSort

## Phạm vi hiện tại

Giai đoạn này tập trung vào ứng dụng web và khả năng nhận diện AI. Kết nối thiết
bị vật lý và triển khai production chưa nằm trong phạm vi.

Kiến trúc chuẩn:

```text
camera -> crop trung tâm -> TF.js Graph Model -> confidence/margin gate
       -> heuristic thị giác -> bỏ phiếu 3/5 frame -> xác nhận 0,7 giây
```

Model TF.js đóng gói tại `public/tfjs_model/` là engine mặc định. SavedModel tại
`saved_model_keras/` được dùng để train, convert và chạy benchmark offline.

## Các giai đoạn đã hoàn thành

### 1. Chuẩn hóa mã nguồn

- Cấu hình nhận diện tập trung trong `src/aiConfig.js`.
- Logic lọc dự đoán được tách sang `src/predictionSmoothing.js`.
- Logic tính điểm được tách sang `src/scoring.js`.
- Mapping dataset dùng chung nằm tại `config/dataset-labels.json`.
- Training, validation và benchmark cùng đọc một mapping.

Các giá trị baseline vẫn được giữ nguyên: input 224×224, threshold mặc định 45%,
cửa sổ 5 frame, tối thiểu 3 phiếu và margin 8%.

### 2. Kiểm thử tự động

- Unit test: cấu hình, smoothing, scoring, ánh xạ nhãn và heuristic.
- Browser test: vòng chơi, reset điểm, lỗi quyền camera và mobile overflow.
- Model smoke test: tải Graph Model thật và chạy inference trong Chromium.
- Accessibility test: không chấp nhận lỗi axe mức serious hoặc critical.
- `npm run check:full` chạy toàn bộ validate, unit test, build và browser test.

### 3. Đánh giá AI baseline

Chạy:

```bash
npm run evaluate:ai
```

Kết quả được ghi vào:

- `reports/ai-baseline.md`
- `reports/ai-baseline.json`

Đây là smoke benchmark dùng ảnh trong dataset hiện tại. Ảnh có thể đã xuất hiện
trong quá trình train, vì vậy không được dùng kết quả này như accuracy độc lập.

### 4. UX camera và accessibility

- Lỗi camera được hiển thị ngay tại khung camera.
- Có nút thử lại camera.
- Ưu tiên camera sau trên thiết bị di động.
- Dừng scan animation và confetti khi trang không còn hiển thị.
- Tôn trọng `prefers-reduced-motion`.
- Điểm số dùng chữ số tabular.
- Có kiểm thử responsive trên viewport desktop và mobile.

## Công việc AI tiếp theo

1. Thu thập một tập test mới chưa từng dùng để train.
2. Mỗi nhãn cần tối thiểu 30–50 ảnh test trong nhiều điều kiện ánh sáng/phông nền.
3. Chạy benchmark bằng `--dataset <thu-muc-test>`.
4. Ưu tiên cải thiện các nhãn có F1 thấp trong báo cáo baseline.
5. Train model mới dưới tên phiên bản khác; không ghi đè baseline.
6. Chỉ thay model mặc định nếu macro F1, coverage và kiểm thử camera thực tế tốt hơn.

## Lệnh làm việc

```bash
npm run dev
npm run validate
npm run test
npm run test:e2e
npm run evaluate:ai
npm run check:full
```
