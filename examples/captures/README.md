# Dữ liệu đo thật để xem ngoại tuyến

Copyright © 2026 HALA Academy · MIT.

| Bản thu JSON/BIN | Nội dung | Nguồn |
|---|---|---|
| pwm | PWM 1 kHz, duty 50%, 8192 mẫu ở 32000 S/s | Thu USB mới ngày 2026-10-23, dùng trong ảnh hướng dẫn |
| uart-host-rx | Host gửi HELLO, thiết bị trả hello | Lượt kiểm transport sau chuẩn hóa cây nguồn |
| canfd-ext-tx | CAN FD ID 29-bit, 64 byte, BRS; chỉ gói đầu có ACK | Qualification lịch sử được chọn lọc |
| canfd-tx | CAN FD ID 11-bit, 64 byte, BRS; ACK từ STM32F103 thật | Kiểm thử phần cứng ngày 2026-10-23 qua ST-Link V2 |
| flexray-a | FlexRay Kênh A, Static Frame ID 0x123, 254 byte payload | Kiểm thử phần cứng ngày 2026-10-23 qua ST-Link V2 |

```sh
python tools/lab.py gui --open examples/captures/pwm.json
```

Giữ JSON/BIN cùng tên để kiểm raw SHA256. Không cần board để xem dữ liệu.
Metadata chỉ chứa thông tin thu/giải mã. Đây là bằng chứng cho phiên đo tương ứng,
không chứng minh firmware mới của người tải đã PASS.
