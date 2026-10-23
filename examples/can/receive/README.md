# CAN · Nhận 11/29-bit, DATA/RTR

Copyright © 2026 HALA Academy · MIT.

Source: main.c. Tốc độ ví dụ: 1000 bit/s. Giao thức CAN, hướng rx. Đọc GPIO_IDR/ghi GPIO và timer trực tiếp; không gọi API monitor để truyền giao thức.

Chạy từ gốc repository:

```sh
python tools/lab.py build can-rx
python tools/lab.py flash can-rx
```

File tạo ra: build/student_can_rx.elf và .bin. Nạp dùng OpenOCD/ST-Link qua SWD. Tài nguyên được cấp và startup/linker chung ở examples/common; không thay clock/USB/vector hoặc timer/DMA của monitor.

Để xem/gửi dữ liệu, mở HALA Logic, chọn COM/USB rồi cấu hình đúng protocol/baud/chân. Tool không tự chọn hay nạp ví dụ này. Chi tiết mode/giới hạn tại [danh mục ví dụ](../../README.md) và [hướng dẫn nạp/debug](../../../docs/NAP_VA_DEBUG.md).
