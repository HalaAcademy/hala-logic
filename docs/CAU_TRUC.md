# Cây thư mục chuẩn

```text
USB/
├── README.md
├── LICENSE                         # MIT · HALA Academy
├── CONTRIBUTING.md
├── CHANGELOG.md
├── THIRD_PARTY_NOTICES.md
├── requirements.txt
├── Makefile                        # Wrapper cho CLI Python
├── firmware/
│   ├── README.md
│   ├── monitor/                    # Source monitor riêng
│   │   ├── startup.c
│   │   ├── runtime.c
│   │   ├── protocol.c
│   │   ├── capture.c / .h
│   │   ├── stimulus.c / .h
│   │   ├── layout.h
│   │   └── linker.ld
│   └── platform/stm32f103/          # Clock, GPIO nền tảng, USB CDC
├── examples/
│   ├── README.md
│   ├── common/                     # Startup/linker và helper GPIO/timer
│   ├── gpio/pwm/
│   ├── uart/{transmit,receive}/
│   ├── lin/{transmit,subscriber_publisher}/
│   ├── can/
│   │   ├── transmit/
│   │   ├── transmit_extended/
│   │   ├── remote_request/
│   │   ├── remote_request_extended/
│   │   ├── receive/
│   │   └── transmit_legacy/
│   ├── canfd/{transmit,transmit_extended,receive}/
│   ├── flexray/
│   │   ├── transmit_channel_a/
│   │   ├── transmit_channel_b/
│   │   ├── receive_channel_a/
│   │   └── receive_channel_b/
│   ├── system/fault/
│   └── captures/                   # Mẫu đo thật chọn lọc để xem ngoại tuyến
├── host/
│   ├── gui.py                      # Chỉ COM/USB + thu/phát + xem sóng
│   ├── session.py                  # Acquisition và frame stimulus
│   ├── client.py                   # USB CDC
│   ├── config.py
│   ├── decode.py / canfd.py / flexray.py
│   ├── stimulus.py
│   ├── measurements.py
│   ├── export.py
│   └── monitor.py                  # CLI USB kỹ thuật
├── tools/
│   ├── lab.py                      # Entry point build/nạp/debug; mở GUI
│   ├── check_repo.py
│   ├── source_release.py
│   └── device/                     # Build, ELF validator, OpenOCD, readback
├── tests/
│   ├── unit/
│   └── hardware/                   # GDB, oracle và acceptance runner
├── configs/
│   ├── lab.json                    # Giá trị mặc định, không có đường dẫn máy
│   ├── examples.json               # Danh mục build, GUI không đọc file này
│   ├── local.json                  # Tùy chọn cá nhân, bị gitignore
│   └── openocd/{stlink,stlink-hla}.cfg
├── profiles/                       # Profile giao thức và nguồn tham chiếu
├── docs/
│   ├── BAT_DAU.md
│   ├── SU_DUNG_TOOL.md
│   ├── CAI_DAT_{WINDOWS,MACOS,LINUX}.md
│   ├── NAP_VA_DEBUG.md
│   ├── images/
│   └── technical/                  # Thiết kế, ma trận và tiến độ
├── .github/                        # CI, issue/PR templates
└── build/                          # Sinh tự động, không đưa lên Git
```

Mỗi thư mục bài có `main.c`, `README.md`, `Makefile`. Các biến thể mở rộng/RTR/kênh dùng chung implementation qua include để không nhân bản thuật toán; đây là các build preset code, không phải mẫu trong GUI. Danh mục build nằm ở configs/examples.json.

## Ranh giới công cụ

HALA Logic chỉ biết kết nối USB và tín hiệu: không import OpenOCD, ELF validator hay danh mục ví dụ. Công cụ nạp nằm ở tools/device; source monitor nằm firmware/monitor. Lập trình viên tự build/nạp ví dụ bằng CLI, sau đó mở tool như một thiết bị phân tích sóng thông thường.

## Cấu hình

Tạo configs/local.json nếu cần ghi đè, ví dụ:

```json
{"tools":{"gdb":"gdb-multiarch"},"swd_khz":25,"serial_port":null}
```

Cổng trong GUI được chọn trực tiếp; nếu chọn Tự động thì dùng serial_port từ cấu hình hoặc tìm theo VID/PID. `HALA_CONFIG` chọn file JSON override khác. Đường dẫn tương đối tính từ gốc dự án. Key/identifier tiếng Anh, UI và hướng dẫn tiếng Việt. Địa chỉ thanh ghi, pin fixture và linker là ABI phần cứng; đổi cần kiểm thử firmware, không tự đổi mapping bằng một ô GUI.

## Dọn dữ liệu

Các build/log/backup, gói R001/R002 và ảnh của GUI cũ đã được lưu ngoài cây project trong thư mục archive cùng cấp. Không đưa archive đó vào Git. Trong project chỉ giữ nguồn đang dùng, tài liệu hiện tại và capture mẫu nhỏ. build/ được tạo lại khi cần; không xóa source hoặc bằng chứng cần giữ bằng make clean ngoài ý muốn.
