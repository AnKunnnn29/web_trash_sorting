# Báo cáo hoàn thiện giai đoạn dữ liệu và AI

Ngày cập nhật: 23/07/2026

## Phạm vi

Đã hoàn thiện các hạng mục có thể thực hiện hoàn toàn trong workspace:

- Chuẩn hóa logic nhận diện và cấu hình frontend.
- Unit test, browser test, accessibility và model smoke test.
- Thu thập/kiểm duyệt dữ liệu bao bì sữa Việt Nam.
- Lập danh mục nhãn hàng sữa hộp đang được xác minh tại Việt Nam.
- Audit duplicate, label conflict và ảnh lỗi.
- Tạo split cố định chống leakage.
- Triển khai augmentation, L2, Dropout, label smoothing, early stopping.
- Train E2 và E4; E4 chạy ba seed.
- Đánh giá internal test và external boxed-milk test.
- Áp dụng quality gate trước khi thay model.

Không thực hiện phần cứng hoặc deploy.

## Dữ liệu

- Tổng ảnh local: 9.680.
- 44 folder dữ liệu ánh xạ về 31 output label.
- 0 ảnh không đọc được.
- `milk_carton`: 267 ảnh.
- `probiotic_bottle`: 25 ảnh, ánh xạ về output `bottle`.
- 26 nhãn hàng/dòng sữa hộp được ghi trong
  `config/vietnam-boxed-milk-brands.json`.
- 15 ảnh sữa hộp mới nhất được giữ ngoài train làm external test.

Khi tạo split:

- Loại 2.305 duplicate thị giác trong cùng nhãn.
- Loại 145 file thuộc nhóm exact duplicate xung đột nhãn.
- Loại thêm 15 file thuộc nhóm dHash xung đột nhãn.
- Giữ 5.042 train, 1.079 validation, 1.079 internal test và 15 external test.

Dataset gốc không bị xóa. Việc làm sạch được thể hiện bằng manifest
`reports/training-split.csv`, giúp tái lập và tránh thao tác phá hủy.

## Phương án chống overfitting đã áp dụng

Pipeline:

```text
audit + loại conflict/duplicate
  -> split cố định
  -> augmentation chỉ trên train
  -> MobileNetV2 pretrained, freeze backbone
  -> Dense head + L2
  -> Dropout
  -> fine-tune 30 layer cuối, giữ BatchNorm frozen
  -> EarlyStopping theo val_loss
  -> internal test + external test
```

Augmentation dùng rotation ±18°, translation 10%, zoom 15%, brightness
0,8–1,2 và horizontal flip. Không augmentation validation/test.

Các thí nghiệm:

- E2: L2 `1e-4`, Dropout `0.2`.
- E4: L2 `1e-4`, Dropout `0.3`, label smoothing `0.05`.
- L1 không được chọn vì dữ liệu/label leakage là rủi ro lớn hơn và E4 đã cho
  thấy regularization mạnh hơn chưa cải thiện tổng thể.

## Kết quả

| Model | Test accuracy | Macro F1 | External milk recall |
| --- | ---: | ---: | ---: |
| Baseline hiện tại | 62,4% | 59,2% | 40,0% |
| E2 | 53,6% | 42,3% | 73,3% |
| E4, trung bình 3 seed | 54,6% | 42,8% | 68,9% |

E4 ổn định về macro F1 (độ lệch chuẩn 0,5 điểm) nhưng external milk recall có
độ lệch chuẩn 6,3 điểm. Recall trung bình của các lớp yếu vẫn thấp:

- `milk_carton`: 56,0%.
- `bottle`: 54,0%.
- `bread`: 47,6%.
- `wipe`: 29,5%.
- `pen`: 34,9%.
- `plastic_bag`: 28,5%.
- `styrofoam`: 0,0%.

## Quyết định

**Giữ model baseline hiện tại.**

Không copy model ứng viên sang `saved_model_keras` hoặc `public/tfjs_model` vì:

- Macro F1 không tăng tối thiểu 3 điểm.
- External milk recall trung bình chưa đạt 75%.
- External result chưa ổn định qua ba seed.
- `styrofoam` và nhiều lớp quan trọng giảm mạnh.

Việc không thay model là kết quả của quality gate, không phải do pipeline train
chưa chạy.

## Công việc còn phụ thuộc dữ liệu mới

Phần code/pipeline đã hoàn tất. Điểm nghẽn còn lại là dữ liệu camera thực tế:

- `styrofoam`: cần tối thiểu 150 ảnh mới.
- `wipe`, `pen`, `plastic_bag`, `bread`: mỗi lớp cần khoảng 150 ảnh.
- `milk_carton`: cần thêm khoảng 130 ảnh camera thực tế.
- `probiotic_bottle`: cần thêm khoảng 125 ảnh camera thực tế.
- Tập test release: 30–50 ảnh hoàn toàn mới cho mỗi nhãn ưu tiên.

Ảnh phải bao gồm vật thể đã qua sử dụng, nhiều góc, phông nền và ánh sáng; các
góc của cùng một vật thể phải dùng chung `group_id`. Không dùng ảnh trang sản
phẩm làm phần lớn tập train và không dùng lại ảnh test để chọn hyperparameter.

Khi có số ảnh này, quy trình tiếp theo chỉ cần:

```bash
npm run audit:data
npm run prepare:training-data
npm run train:candidate:e4
npm run evaluate:clean-split
npm run summarize:training
npm run check:full
```

Chỉ khi quality gate chuyển sang `REPLACE baseline` mới thực hiện convert TF.js
và thay model mặc định.
