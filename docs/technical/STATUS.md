# Trạng thái triển khai

HALA Logic đã tách luồng sử dụng khỏi luồng phát triển firmware. Cây nguồn chuẩn ở [CAU_TRUC.md](../CAU_TRUC.md); GUI chỉ COM/USB, cấu hình tín hiệu, thu/phát và xem kết quả. Monitor nằm firmware/monitor, các ví dụ nằm examples; nạp/debug bằng OpenOCD/GDB qua CLI riêng.

## Đã triển khai

- Monitor USB CDC, Timer/DMA lấy GPIO_IDR thật, stimulus và resolver/relay pad; không jumper loopback.
- 19 ví dụ: PWM, UART TX/RX, LIN TX/subscriber/publisher, Classical CAN base/extended DATA/RTR và RX, CAN FD TX/RX, FlexRay static TX/RX từng kênh, fault phục hồi.
- Host codec/export/phép đo, GUI kết nối COM/USB và capture ngoại tuyến.
- Validator ELF, nạp/verify bằng OpenOCD, kiểm monitor readback, GDB main/step/ISR/watchpoint/stack.
- MIT License, HALA Academy, cấu hình tool/USB, CI và tài liệu ba hệ điều hành.

## Bằng chứng và giới hạn

Sau chuyển cây: 20 BIN giống từng byte trước chuyển; 51 unit test host qua. 18 ELF có debug path mới đã qua main/step/ISR/watchpoint/stack, đối chiếu đúng ELF snapshot/hash qua hai lượt; lượt đầu bị lỗi cấu hình host được giữ nguyên log, tám trường hợp còn lại đã chạy lại. Báo cáo tổng hợp ở build/reports/layout-validation-*. Bằng chứng phần cứng cũ đã chuyển ra archive ngoài project; không dùng report cũ để kết luận một ELF mới đã PASS.

Bản firmware vẫn R002-dev9. SHA256 vùng monitor 24 KiB trong qualification trước: d43ae111b05fe1cc9d51c186b2cec88283fa21e5dc61568cb3afe037cbc74a18. Đây là định danh firmware đo được, không phải hash của mã nguồn Python mới.

Kế hoạch đầy đủ 15 phase / 96 nhóm bài / 44 nhóm phép đo **chưa hoàn tất**. UART/LIN chưa đủ format/schedule/diagnostic; CAN/FD chưa đầy đủ arbitration/retry/resync/error-confinement/bus-off; FlexRay chưa có cluster/TDMA/startup/sync/dual-channel đồng thời. Capture vô hạn/pretrigger/reactive peer tổng quát và đo analog chưa có. Cold power/physical Safe strap/external clock calibration còn thiếu bằng chứng.

Windows/Linux có hướng dẫn/CI host, chưa kiểm USB/SWD phần cứng trong phiên này. Không gọi toàn dự án PASS chỉ vì build, decode hoặc GUI hiển thị được.
