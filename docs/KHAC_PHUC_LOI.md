# Khắc phục lỗi

| Hiện tượng | Cách kiểm tra và xử lý |
|---|---|
| Không thấy COM/USB | Kiểm cáp dữ liệu, nguồn và firmware USB; Làm mới danh sách. Người phát triển xem NAP_VA_DEBUG.md nếu chưa cài thiết bị |
| Có nhiều cổng | Chọn COM hoặc /dev/cu.usbmodem cụ thể, không dùng Tự động |
| Cổng đang bận | Đóng serial terminal hoặc tool khác; mỗi lần chỉ một tác vụ board |
| Permission denied trên Linux | Kiểm udev rules và nhóm dialout theo hướng dẫn Linux |
| Tkinter không mở | Cài Tk đúng phiên bản Python; thử python -m tkinter |
| Không có gói giải mã | Kiểm protocol/baud, chân decode, mask và cửa sổ; xem sóng raw trước |
| Rate không đủ | UART/LIN cần≥4mẫu/bit; CAN/FD/FlexRay cần≥8mẫu/bit |
| FD BRS ratio không hỗ trợ | Bộ phát hiện chỉ data=2×nominal khi BRS; không suy diễn tỷ lệ khác |
| Cửa sổ quá ngắn | Tăng số mẫu hoặc giảm baud; gói dài cần cửa sổ dài hơn |
| INVALID/lost/underrun | Giữ log lỗi, giảm sample rate; không đổi lỗi thành PASS |
| JSON không mở được | Giữ BIN cùng stem, kiểm count/state/lost/SHA256 |
| USB mất sau reset/debug | Làm mới danh sách; nếu chỉ còn ST-Link thì rút/cắm riêng USB dữ liệu Blue Pill, giữ nguyên dây SWD. Không coi verify Flash là bằng chứng USB đã hoạt động lại |
| USB timeout lúc debug | MCU đang halt; resume/detach, đóng OpenOCD rồi mở tool |
| CRC đúng nhưng chương trình không nhận | Kiểm parser/app state bằng oracle/GDB; CRC chỉ nói về waveform |

Phần nạp/debug nằm ngoài GUI: [NAP_VA_DEBUG.md](NAP_VA_DEBUG.md). Không mass erase như bước xử lý đầu tiên. Không cần sửa code host để chọn đường dẫn tool hay cổng: dùng configs/local.json hoặc chọn cổng trực tiếp trong GUI.
