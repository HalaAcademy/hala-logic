# Ví dụ lập trình giao tiếp

Copyright © 2026 HALA Academy · MIT. Mỗi bài có main.c, README.md, Makefile riêng. Các giao thức được xử lý bằng GPIO/timer software, không dùng controller USART/bxCAN/FDCAN/FlexRay để thay thuật toán. GUI HALA Logic chỉ đo/phát tín hiệu và không đọc danh mục ví dụ.

| Bài | Thư mục code | Baud | Key build/nạp |
|---|---|---:|---|
| GPIO · PWM 1 kHz | [gpio/pwm](gpio/pwm/README.md) | 1000 | `pwm` |
| UART · Phát 9600 | [uart/transmit](uart/transmit/README.md) | 9600 | `uart-tx` |
| UART · Nhận và trả lời | [uart/receive](uart/receive/README.md) | 1000 | `uart-rx` |
| LIN · Phát 9600 | [lin/transmit](lin/transmit/README.md) | 9600 | `lin-tx` |
| LIN · subscriber / publisher | [lin/subscriber_publisher](lin/subscriber_publisher/README.md) | 1000 | `lin-rx` |
| CAN · Phát 20 kbit/s (cũ) | [can/transmit_legacy](can/transmit_legacy/README.md) | 20000 | `can-legacy` |
| CAN · Nhận 11/29-bit, DATA/RTR | [can/receive](can/receive/README.md) | 1000 | `can-rx` |
| CAN · Phát DATA 11-bit | [can/transmit](can/transmit/README.md) | 1000 | `can-tx` |
| CAN · Phát DATA 29-bit | [can/transmit_extended](can/transmit_extended/README.md) | 1000 | `can-tx-ext` |
| CAN · Phát RTR 11-bit | [can/remote_request](can/remote_request/README.md) | 1000 | `can-tx-rtr` |
| CAN · Phát RTR 29-bit | [can/remote_request_extended](can/remote_request_extended/README.md) | 1000 | `can-tx-ext-rtr` |
| CAN FD · Nhận 11/29-bit | [canfd/receive](canfd/receive/README.md) | 1000 | `canfd-rx` |
| CAN FD · Phát 11-bit | [canfd/transmit](canfd/transmit/README.md) | 1000 | `canfd-tx` |
| CAN FD · Phát 29-bit | [canfd/transmit_extended](canfd/transmit_extended/README.md) | 1000 | `canfd-tx-ext` |
| FlexRay · Nhận kênh A | [flexray/receive_channel_a](flexray/receive_channel_a/README.md) | 1000 | `flexray-rx-a` |
| FlexRay · Nhận kênh B | [flexray/receive_channel_b](flexray/receive_channel_b/README.md) | 1000 | `flexray-rx-b` |
| FlexRay · Phát kênh A | [flexray/transmit_channel_a](flexray/transmit_channel_a/README.md) | 1000 | `flexray-tx-a` |
| FlexRay · Phát kênh B | [flexray/transmit_channel_b](flexray/transmit_channel_b/README.md) | 1000 | `flexray-tx-b` |
| Chẩn đoán · cố ý tạo fault | [system/fault](system/fault/README.md) | 1000 | `fault` |

## Cách dùng

Build tất cả: `python tools/lab.py build`. Một bài: `python tools/lab.py build uart-rx`; nạp: `python tools/lab.py flash uart-rx`. Nếu dùng Make, mỗi thư mục có target build/flash. Mở tool độc lập bằng `python tools/lab.py gui`.

UART RX 1000 nhận HELLO và phản hồi XOR 0x20 thành hello. LIN subscriber ID 0x12 nhận 2 byte, publisher ID 0x22 trả 34 56. CAN RX hỗ trợ 11/29-bit DATA/RTR DLC 0..8 và ACK; TX mới 1000 bit/s có observer ACK. CAN FD hỗ trợ 11/29-bit, DLC và CRC 17/21, BRS 1000 → 2000. FlexRay static frame A/B thử riêng, payload chẵn ≤ 254 byte.

## Giới hạn

CAN/FD chưa đầy đủ arbitration/retry/resync/error-confinement/bus-off; RTR RX chưa tự trả DATA. FD không có RTR. FlexRay chưa có cluster scheduler/TDMA/startup/sync/clock correction hoặc hai kênh đồng thời. UART/LIN chưa đủ mọi format/schedule/diagnostic. Fault cố ý gây lỗi, không dùng làm bài đầu. Những giới hạn này thuộc ví dụ/code, không phải lựa chọn firmware trong HALA Logic.

Các biến thể extended/RTR/channel dùng shared implementation của bài cơ sở, tránh sao chép thuật toán. Các tên symbol student_* và tên artifact được giữ để tương thích kiểm thử/GDB.
