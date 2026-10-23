# Đánh giá UX/UI HALA Logic

Ngày 2026-10-23 · Copyright © 2026 HALA Academy · MIT.

Giao diện hiện đi theo luồng của một công cụ đo: chọn COM/USB → kết nối → cấu hình giao thức/lấy mẫu → thu hoặc gửi → xem sóng/gói/phép đo → lưu. Source monitor, code ví dụ, OpenOCD và GDB được tách khỏi GUI.

## Tiêu chí thiết kế đã áp dụng

- Không cần biết cấu trúc firmware để dùng tool; không có file firmware hay chọn ví dụ trong GUI.
- Baud và Sample Hz hiện riêng; số mẫu, mask, chân decode và Streaming/Burst được cấu hình trực tiếp.
- Windows chọn COM; macOS hiện cổng USB serial, mô tả và VID/PID. Tự động là lựa chọn bổ sung khi chỉ có một thiết bị phù hợp.
- Gửi frame lấy ID/data/baud người dùng nhập, không khóa vào bảng ID của một ví dụ nhận.
- Kết quả gói/phép đo có bảng tiếng Việt, JSON field kỹ thuật giữ tiếng Anh.
- Thu/phát chạy ở worker; lỗi/cancel trả stimulus idle; mỗi lần một tác vụ USB.

## Xác minh

Code được build lại theo cây mới, đủ 20 BIN giống từng byte bản trước. Bộ 51 unit test đã qua, gồm rate validation trước USB, GPIO config, LIN ID độc lập ví dụ, FD BRS ratio và stop stimulus khi lỗi USB. 18 ELF hiện tại đã được đối chiếu snapshot/hash và log GDB main/step/ISR/watchpoint/stack qua hai lượt. Lượt đầu bị ngắt do đổi schema cấu hình host; lỗi gốc được giữ, tám trường hợp còn lại đã kiểm lại với cấu hình đã chốt.

GUI đã thực hiện kết nối và thu PWM thật bằng USB, không chọn chương trình trong tool. Backend mới gửi HELLO và đọc lại hello; GDB xác nhận đúng buffer 5 byte, không lỗi. Sau lượt test, USB mất enumerate; đã phục hồi bằng rút/cắm USB, PING=PONG, thu lại PWM 1000 Hz / duty 50%, bộ đếm USB lỗi không tăng trong phép thử. Flash PWM đã verify ở SWD 25 kHz, monitor giữ nguyên. Ảnh hiện tại nằm trong [bài bắt đầu](BAT_DAU.md). Các ảnh của giao diện lập trình cũ đã bỏ khỏi tài liệu hiện hành.

## Rà soát lại sau thay đổi giao diện

Đã đi lại luồng kết nối USB → thu GPIO → phóng sóng → xem phép đo trên GUI mới.
Lần thu ngày 2026-10-23 có 8192 mẫu ở 32000 S/s, không mất mẫu; PB0 1000 Hz,
chu kỳ 1000 µs, duty 50%. Bốn ảnh trong bài bắt đầu đã chụp lại và cắt riêng vùng
cấu hình/sóng/phép đo/gói tin; không còn thanh điều khiển môi trường chụp.
Ảnh gói tin là mở lại capture CAN FD thật lịch sử, không phải test CAN FD mới.

Sửa nhãn con trỏ còn sót khi mở bản thu, khôi phục mặc định lấy mẫu khi đổi từ
CAN FD/FlexRay sang GPIO/UART, thu gọn hàng tùy chọn rỗng và tăng chiều cao cửa sổ.
56 test hiện qua, gồm năm test hồi quy cho trạng thái GUI và checker tài liệu/ví dụ.
[Đánh giá công bố nguồn](REVIEW_GIT.md) ghi phạm vi kiểm tra và các điểm chưa đủ bằng chứng.

## Giới hạn đánh giá

Đây là walkthrough kỹ thuật trên macOS, chưa là nghiên cứu usability với học viên mới; không có điểm SUS hay kết quả Windows/Linux phần cứng được tạo giả. CI được cấu hình nhưng chưa chạy trên GitHub trong phiên này.

Chưa có analog measurement, auto baud, continuous/pretrigger hay reactive scheduler tổng quát. Bảng payload dài dùng JSON chi tiết để đọc đủ. Kiểm bàn phím/screen reader/HiDPI trên cả ba OS vẫn cần tiếp tục. Không kết luận chương trình nhận đúng chỉ từ CRC hợp lệ.
