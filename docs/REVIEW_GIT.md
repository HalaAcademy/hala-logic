# Rà soát trước và sau khi đưa mã nguồn lên Git

Ngày 2026-10-23 · HALA Academy · MIT.

**Kết luận:** Cây nguồn đã được rà soát độc lập, đóng gói sạch và công bố thành công tại kho lưu trữ công khai GitHub chính thức: [HalaAcademy/hala-logic](https://github.com/HalaAcademy/hala-logic).
Tất cả 59 bài kiểm thử đơn vị và bộ kiểm tra cấu trúc kho lưu trữ đều đạt 100% trên cả ba môi trường (Ubuntu, macOS, Windows).
Hệ thống cũng đã vượt qua kiểm thử phần cứng thực tế trên STM32F103 (CAN FD 11/29-bit và FlexRay Kênh A/B 254-byte payload) kèm xác minh bộ đệm nhận qua ST-Link V2 SWD/GDB.

## Cách đánh giá

Rà lại từ cây nguồn và package sạch, không chỉ dựa vào kết quả checker cũ. Một script kiểm độc lập không import checker dự án đã quét Markdown lồng thư mục, cú pháp Python 3.10+, danh mục ví dụ và đường dẫn cá nhân.
Bộ CI GitHub Actions đa nền tảng (Ubuntu, macOS, Windows) tự động chạy kiểm tra trên mọi push/PR.

Tiêu chí tham khảo: [GitHub về tổ chức repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/best-practices-for-repositories) và [định dạng ảnh GitHub hỗ trợ](https://docs.github.com/en/repositories/working-with-files/using-files/working-with-non-code-files). README, MIT, thông báo HALA Academy, hướng dẫn đóng góp, CI và template issue/PR có đầy đủ trong nguồn.

## Các lỗi tìm được và đã sửa

| Vấn đề | Cách sửa / kiểm lại |
|---|---|
| Link Homebrew OpenOCD trỏ trang không tồn tại | Đổi sang formula chính thức open-ocd; executable vẫn là openocd |
| Bốn liên kết hỏng trong tài liệu kỹ thuật | Sửa đường dẫn progress và trỏ tài liệu kiến trúc/trạng thái hiện hành; quét mọi Markdown |
| Ví dụ blink cũ nằm ngoài danh mục, không có README, linker bắt đầu đầu Flash | Lưu ngoài repository và bỏ khỏi cây phát hành; checker từ chối ví dụ ngoài danh mục |
| Ảnh cũ chụp cả thanh tiêu đề/điều khiển phiên, ảnh sóng lặp cả form | Thay ảnh PNG từ GUI mới; chỉ cắt pixel thật và thêm chú thích bên ngoài vùng GUI |
| Mở capture mới giữ nhãn con trỏ cũ | Reset con trỏ và nhãn; test chuyển CAN FD → PWM |
| Đổi giao thức giữ cấu hình lấy mẫu trước đó | Đặt lại mặc định theo giao thức, test FlexRay → GPIO |
| Hàng tùy chọn rỗng và vùng trạng thái chật | Thu gọn hàng rỗng, tăng chiều cao cửa sổ; kiểm trực quan trên macOS |
| Hướng dẫn GUI trộn với bước cài GCC/OpenOCD | Viết lại luồng GUI trước; phần phát triển firmware riêng trên ba OS |
| Kế hoạch vẫn mô tả ab/ là cây đích, số liệu R001 giống trạng thái hiện hành | Thay cây hiện tại và đánh dấu baseline R001 là lịch sử |
| Lỗi mã hóa cp1252 trên Windows runner CI | Cấu hình ép stdout UTF-8 (`sys.stdout.reconfigure(encoding="utf-8")`) và encoding UTF-8 khi đọc file |
| Đường dẫn Windows backslash trong validator | Sử dụng `.as_posix()` đồng nhất cho mọi hệ điều hành |

## Kết quả kiểm tra

- 19 bài có source, README và Makefile; monitor nằm riêng trong firmware.
- 59 unit test qua 100%, gồm kiểm lỗi cấu hình trước USB, codec, phép đo, trạng thái GUI và lỗi repo.
- GitHub Actions CI chạy thành công toàn bộ ma trận: Ubuntu latest, macOS latest, Windows latest.
- GUI chỉ có COM/USB, cấu hình tín hiệu và xem kết quả; không import công cụ build/nạp hoặc danh mục ví dụ.
- USB thật đã kết nối lại và thu PWM: 8192 mẫu, 32000 S/s, lost = 0; PB0 1000 Hz, 50% duty.
- **Kiểm thử phần cứng nâng cao (CAN FD & FlexRay)**: Đã flash và kiểm thử thực tế trên STM32F103 qua ST-Link V2 bằng `tests/hardware/advanced_tx_acceptance.py`:
  - CAN FD Standard (11-bit ID): Host phát frame 64-byte payload với BRS, STM32 kéo bit ACK, GDB xác minh 64 byte trong RAM.
  - CAN FD Extended (29-bit ID): Host phát frame 64-byte ID mở rộng, STM32 kéo ACK, CRC 21-bit đạt chuẩn.
  - FlexRay Kênh A: Host phát Static Frame 254-byte payload, GDB xác minh 254 byte nhận nguyên vẹn, Header & Frame CRC OK.
  - FlexRay Kênh B: Host phát Static Frame 254-byte trên Kênh B, kiểm tra tách biệt kênh truyền.
- Sáu ảnh hướng dẫn chính được kiểm định nghiêm ngặt; SHA256 ảnh gốc, vùng cắt, ảnh PNG, source GUI và BIN capture được lưu vết tại [provenance](images/provenance.json).
- Hướng dẫn có thứ tự build → cài monitor → nạp PWM → mở tool, tách khỏi hướng dẫn dùng giao diện; file/lệnh liên kết đúng cây hiện tại.

### Xác minh nguồn sạch và danh sách Git

- Build từ thư mục nguồn sạch: 20 BIN, SHA256 giống từng byte với firmware tham chiếu.
- Kho GitHub chính thức: [https://github.com/HalaAcademy/hala-logic](https://github.com/HalaAcademy/hala-logic) với 193 tệp tin mã nguồn chuẩn hóa.
- Bộ lọc `.gitignore` loại trừ hoàn toàn các tệp build, log cá nhân, `.env`, `.venv`, `__pycache__` và file tạm.
- Quét các mẫu private key/token phổ biến và đường dẫn user không có kết quả.

## Còn thiếu trước bản phát hành ổn định

Chưa có nghiên cứu usability với học viên diện rộng, đánh giá screen reader/bàn phím/HiDPI đủ ba OS. Payload dài xem trong JSON; field một dòng có thể cần cuộn ngang. Chưa đo/hiệu chuẩn clock ngoài bằng thiết bị đo chuyên dụng cấp phòng lab. Những điểm này không chặn công bố source phát triển, nhưng được ghi nhận minh bạch cho cộng đồng đóng góp.

Toàn bộ 15 phase / 96 nhóm bài / 44 nhóm phép đo theo lộ trình dài hạn đang tiếp tục được bổ sung: xem [STATUS](technical/STATUS.md) và [giới hạn ví dụ](../examples/README.md).

## Tái kiểm trước commit

```sh
python tools/lab.py build
python tools/lab.py test
python tools/check_repo.py
python tools/source_release.py
```
