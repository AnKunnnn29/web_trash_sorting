# Firmware RFID EcoSort

Firmware dành cho ESP32 DevKit và đầu đọc MFRC522. ESP32 hoạt động như bàn phím
Bluetooth có tên **EcoSort RFID** để dùng với iPhone, iPad, Android hoặc máy
tính. Khi đọc được thẻ, thiết bị gửi chuỗi như sau rồi nhấn Enter:

```text
ECOSORT:banana
```

Firmware vẫn gửi một dòng JSON qua USB Serial ở tốc độ `115200` để kiểm tra:

```json
{"type":"rfid","itemId":"banana"}
```

## Nối dây

| MFRC522 | ESP32 DevKit |
| --- | --- |
| 3.3V | 3V3 |
| GND | GND |
| SDA/SS | GPIO 5 |
| SCK | GPIO 18 |
| MOSI | GPIO 23 |
| MISO | GPIO 19 |
| RST | GPIO 22 |
| IRQ | Không nối |

MFRC522 chỉ dùng nguồn 3,3 V.

## Nạp và sử dụng

1. Cài `MFRC522 by GithubCommunity` trong Arduino Library Manager.
2. Với ESP32 Arduino core 3.x, tải bản `sakuls-ESP32-BLE-Keyboard` tương thích
   core mới và cài qua **Sketch → Include Library → Add .ZIP Library...**:
   <https://github.com/sakul-the-one/sakuls-ESP32-BLE-Keyboard/archive/refs/heads/master.zip>
3. Mở **Tools → Manage Libraries...**, tìm `NimBLE-Arduino` của **h2zero** và
   cài phiên bản `2.5.0`. Đây là dependency bắt buộc của bản BLE Keyboard trên.
4. Mở `ecosort_rfid.ino`, chọn `ESP32 Dev Module` và đúng cổng COM.
5. Upload firmware. Nếu cần, giữ `BOOT` trong lúc Arduino IDE hiện
   `Connecting...` và thả khi bắt đầu ghi.
6. Trên điện thoại/tablet, mở **Cài đặt → Bluetooth** và ghép đôi với
   **EcoSort RFID**.
7. Mở web, bấm **Bắt đầu khám phá** rồi quét thẻ. Website nhận tín hiệu bàn
   phím Bluetooth mà không cần mở ô nhập liệu.

Trên máy tính có thể dùng USB thay cho Bluetooth: đóng Serial Monitor, mở web
bằng Chrome hoặc Edge, bấm **Kết nối RFID USB trên máy tính**, chọn ESP32 rồi
bấm **Connect**.

Sáu thẻ cuối được gán lặp lại cho `banana`, `bottle`, `soda_can`, `newspaper`,
`milk_carton` và `plastic_bag`.
