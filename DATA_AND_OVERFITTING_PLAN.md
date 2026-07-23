# Kế hoạch dữ liệu và chống overfitting

## 1. Kết luận ngắn

Chuỗi `Data -> L2 -> L1 -> Dropout -> Early Stop -> Augment` không phù hợp nếu
hiểu là thêm lần lượt mọi kỹ thuật vào cùng một model.

- Augmentation phải nằm trong pipeline train ngay từ đầu và chỉ chạy trên train.
- Early stopping phải được dùng trong mọi thí nghiệm.
- L2 và Dropout nên được đánh giá độc lập rồi mới thử kết hợp.
- L1 không phải lựa chọn mặc định cho EfficientNet transfer learning; chỉ giữ
  như một nhánh ablation nhỏ.
- Việc quan trọng nhất hiện nay là làm sạch duplicate, sửa label conflict và tạo
  test split cố định trước khi thay regularization.

## 2. Kết quả kiểm kê hiện tại

### Dataset

- 9.665 ảnh sau khi thêm dữ liệu mới.
- 0 ảnh không đọc được.
- 2.369 bản sao exact vượt quá bản đầu tiên.
- 2.425 ảnh vượt quá bản đầu tiên nếu nhóm theo dHash.
- 35 nhóm exact duplicate xuất hiện ở nhiều nhãn khác nhau.
- 40 nhóm dHash xuất hiện ở nhiều nhãn khác nhau.

Ví dụ có cùng một file nằm đồng thời trong `bottle`, `chemical_bottle`,
`glass_bottle` hoặc `pen`. Đây là nguồn label noise và validation leakage nghiêm
trọng hơn việc thiếu L1/L2.

Xem [reports/dataset-audit.md](reports/dataset-audit.md) và
`reports/dataset-audit.json`.

### Bao bì sữa Việt Nam

Đã tìm 117 ảnh từ Open Food Facts và kiểm duyệt contact sheet:

- Chấp nhận 20 ảnh hộp giấy Vinamilk/TH và biến thể tương tự.
- Chấp nhận 25 ảnh chai probiotic/Yakult/Probi.
- Loại ảnh cốc sữa chua, mì gói, nước trái cây và kết quả sai hình dạng.
- Hộp giấy được thêm vào `milk_carton`.
- Chai probiotic nằm ở folder `probiotic_bottle` và map về output `bottle`.

Model baseline trên 45 ảnh mới:

- Top-1 accuracy: 13,3%.
- `milk_carton` recall: 30%.
- `bottle` recall trên chai probiotic: 0%.
- 16/25 chai probiotic bị đoán thành `shampoo_bottle`.

Điều này xác nhận model hiện tại chưa tổng quát tốt sang bao bì sữa Việt Nam.
Xem [reports/ai-vietnam-milk-before-retrain.md](reports/ai-vietnam-milk-before-retrain.md).

## 3. Phân loại đúng vật liệu

Không gộp hộp giấy và chai Yakult/Probi vào cùng output:

| Bao bì | Folder dữ liệu | Output model | Lý do |
|---|---|---|---|
| Tetra Pak/hộp giấy | `milk_carton` | `milk_carton` | Nhiều lớp giấy, nhựa, nhôm |
| Yakult/Probi dạng chai | `probiotic_bottle` | `bottle` | Bao bì nhựa, hình dạng chai |

Việc giữ folder riêng cho phép kiểm tra recall riêng dù hai loại chai dùng chung
output phân loại cuối.

## 4. Kế hoạch bổ sung dữ liệu

### Tập train

Ưu tiên ảnh thật chụp bằng camera giống môi trường ứng dụng:

| Nhóm | Bổ sung tối thiểu | Yêu cầu |
|---|---:|---|
| `probiotic_bottle` | +125 | Yakult, Probi, TH; chai đơn, rỗng, móp, nhiều góc |
| `milk_carton` | +130 | Vinamilk, TH, Dutch Lady, Nutifood; có/không ống hút |
| `styrofoam` | +150 | Hộp sạch/bẩn, đóng/mở, nền và ánh sáng khác nhau |
| `bread` | +150 | Mẩu nhỏ, lát bánh, vỏ bánh, bánh cũ; tránh cả ổ bánh đẹp |
| `wipe` | +150 | Khăn ướt vò nhàu, khăn lau bẩn, nhiều màu/nền |
| `pen` | +150 | Bút đơn, gãy, mất nắp, vỏ bút; tránh hộp nhiều bút |
| `plastic_bag` | +150 | Trong suốt, màu, vò nhàu, có chữ, ảnh sau sử dụng |

Quy tắc nguồn:

- Ảnh studio/trang sản phẩm không quá 25% một lớp.
- Ít nhất 75% là ảnh camera thực tế, nhiều phông nền và khoảng cách.
- Một vật thể vật lý chụp nhiều góc phải có cùng `group_id`.
- Không đưa các góc của cùng vật thể sang cả train và validation/test.
- Không tạo file augmentation rồi tính chúng như ảnh mới.

### Tập test độc lập

- 50 ảnh mới cho mỗi nhãn ưu tiên.
- Không lấy từ Open Food Facts hoặc dataset train.
- Chụp sau khi đã đóng băng train/validation split.
- Giữ toàn bộ ảnh của cùng vật thể/phiên chụp trong một split.
- Không dùng tập test để chọn hyperparameter.

## 5. Pipeline chống overfitting đề xuất

```text
Làm sạch nhãn và duplicate
  -> group-aware train/validation/test split
  -> augmentation chỉ trên train
  -> EfficientNetB0 pretrained, freeze backbone
  -> head nhỏ + L2 hoặc Dropout
  -> fine-tune block cuối, giữ BatchNorm frozen
  -> EarlyStopping + restore best weights
  -> đánh giá test một lần
```

### Augmentation

Giữ mức vừa phải để không biến đổi vật liệu:

- Rotation: ±15° đến ±20°.
- Translation: 10%.
- Zoom: 10–15%.
- Brightness: 0,8–1,2.
- Contrast nhẹ.
- Horizontal flip.
- Random crop/occlusion nhẹ nếu vật thể vẫn nhận biết được.

Không dùng vertical flip cho hộp/chai và không rotation 30° cho toàn bộ ảnh nếu
camera thực tế luôn giữ vật thể gần thẳng đứng.

### Regularization khuyến nghị

- L2 `1e-4` trên Dense head: ứng viên chính.
- Dropout: thử một lớp `0.2` và `0.3`; không mặc định dùng cả `0.4` rồi `0.2`.
- Label smoothing: thử `0.05`.
- L1: chỉ thử `1e-6` như ablation; loại nếu macro F1 hoặc recall lớp yếu giảm.
- Early stopping: monitor `val_loss`, `patience=4`, `min_delta=0.002`,
  `restore_best_weights=True`.
- Fine-tune: learning rate `1e-5`, mở theo block và giữ BatchNormalization frozen.

Tham khảo workflow EfficientNet chính thức của Keras:
<https://keras.io/examples/vision/image_classification_efficientnet_fine_tuning/>.

## 6. Ma trận thí nghiệm

Mỗi thí nghiệm phải dùng cùng split và chạy 3 seed.

| ID | Data | L2 | L1 | Dropout | Label smoothing | Mục đích |
|---|---|---:|---:|---:|---:|---|
| E0 | Dataset sạch cũ | 0 | 0 | 0.4 + 0.2 | 0 | Baseline tương thích |
| E1 | Dataset sạch + ảnh mới | 0 | 0 | 0.4 + 0.2 | 0 | Đo tác động của data |
| E2 | Như E1 | 1e-4 | 0 | 0.2 | 0 | Thử L2 |
| E3 | Như E1 | 0 | 0 | 0.3 | 0 | Thử Dropout |
| E4 | Như E1 | 1e-4 | 0 | 0.3 | 0.05 | Ứng viên đề xuất |
| E5 | Như E1 | 0 | 1e-6 | 0.3 | 0 | Kiểm chứng L1 |

Augmentation và early stopping áp dụng giống nhau cho E0–E5; chúng không phải
hai bước cuối chỉ thêm vào một model đã train.

## 7. Tiêu chí chọn model

Metric chính:

- Macro F1 trên validation, sau đó xác nhận trên test.
- Recall của `milk_carton`, `bottle`, `bread`, `wipe`, `pen`, `plastic_bag`.
- Coverage và accuracy trong các dự đoán vượt threshold.
- Chênh lệch train/validation loss.

Chỉ thay baseline nếu:

- Macro F1 test tăng ít nhất 3 điểm phần trăm.
- Không lớp quan trọng nào giảm recall quá 5 điểm phần trăm.
- `milk_carton` recall trên tập camera mới đạt ít nhất 75%.
- `probiotic_bottle -> bottle` recall đạt ít nhất 70%.
- Kết quả trung bình 3 seed ổn định, độ lệch chuẩn macro F1 không quá 2 điểm.

## 8. Nguồn dữ liệu

- Open Food Facts API và giấy phép ảnh:
  <https://openfoodfacts.github.io/openfoodfacts-server/api/>.
- Hướng dẫn tải ảnh Open Food Facts:
  <https://openfoodfacts.github.io/openfoodfacts-server/api/how-to-download-images/>.
- Yakult Việt Nam xác nhận dạng chai 65 ml:
  <https://www.yakult.vn/gioi-thieu.html>.
- Vinamilk Probi 65 ml:
  <https://www.vinamilk.com.vn/products/sua-chua-uong-probi-co-duong>.
- Danh mục sản phẩm TH true MILK:
  <https://www.thmilk.vn/en/products-eng/>.
- Keras EfficientNet fine-tuning:
  <https://keras.io/examples/vision/image_classification_efficientnet_fine_tuning/>.
- TensorFlow transfer learning:
  <https://www.tensorflow.org/guide/keras/transfer_learning>.
- Keras EarlyStopping:
  <https://keras.io/api/callbacks/early_stopping/>.
- Keras Dropout:
  <https://keras.io/api/layers/regularization_layers/dropout/>.
