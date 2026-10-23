# HALA Logic · HALA Academy

Copyright © 2026 HALA Academy · [MIT License](LICENSE).

Tool USB để thu sóng GPIO, đo thời gian và gửi frame logic UART, LIN, Classical CAN, CAN FD, FlexRay ở tốc độ phù hợp học tập. Giao diện chỉ làm việc với **COM/USB, tín hiệu và gói dữ liệu**. Các ví dụ C và công cụ nạp/debug được tổ chức riêng.

## 1. Dùng tool

Cài theo [Windows](docs/CAI_DAT_WINDOWS.md), [macOS](docs/CAI_DAT_MACOS.md) hoặc [Linux](docs/CAI_DAT_LINUX.md). Sau khi kích hoạt môi trường Python:

```sh
python -m pip install -r requirements.txt
python tools/lab.py gui
```

Chọn COM trên Windows hoặc cổng `/dev/cu.usbmodem...` trên macOS, bấm Kết nối, cấu hình giao thức/tần số lấy mẫu rồi **Bắt đầu thu** hoặc **Gửi gói và thu**. Tool không quản lý file firmware, ví dụ hay ST-Link.

- [Hướng dẫn từng bước có ảnh](docs/BAT_DAU.md)
- [Cấu hình thu/phát và phép đo](docs/SU_DUNG_TOOL.md)
- [Khắc phục lỗi](docs/KHAC_PHUC_LOI.md)

Xem dữ liệu thật đã chọn lọc, không cần cắm board:

```sh
python tools/lab.py gui --open examples/captures/pwm.json
```

## 2. Viết và nạp chương trình

- [Ví dụ giao tiếp](examples/README.md): mỗi bài có thư mục, main.c, README.md và Makefile riêng; không cần gọi API monitor.
- [Source monitor](firmware/README.md): mã USB, Timer/DMA, startup và linker riêng.
- [Nạp bằng OpenOCD và debug GDB](docs/NAP_VA_DEBUG.md): luồng dành người phát triển, độc lập với GUI.

```sh
python tools/lab.py doctor
python tools/lab.py build
python tools/lab.py install-monitor
python tools/lab.py flash pwm
```

Cài monitor chỉ khi khởi tạo/cập nhật thiết bị. Nạp các ví dụ tiếp theo bằng OpenOCD qua CLI, không thực hiện trong HALA Logic.

## 3. Cấu trúc chính

```text
firmware/     source monitor và nền tảng STM32
examples/     code từng giao thức, mỗi bài một thư mục
host/         GUI, USB client, thu/phát, codec và phép đo
tools/        build, OpenOCD, validator và đóng gói nguồn
tests/        unit test và kiểm thử phần cứng tách riêng
configs/      cấu hình tool, USB, OpenOCD và danh mục build
docs/         hướng dẫn sử dụng, ảnh và thiết kế kỹ thuật
build/        kết quả sinh tự động; không đưa lên Git
```

[Cây thư mục đầy đủ và quy ước](docs/CAU_TRUC.md).

## 4. Kiểm thử và phát hành nguồn

```sh
python tools/lab.py build
python tools/lab.py test
python tools/check_repo.py
python tools/source_release.py
```

Đóng GUI trước khi chạy `python tools/lab.py hardware-test`. Test phần cứng quản lý OpenOCD tuần tự, giữ log và dừng khi FAIL/INVALID. Không chạy song song trên một board.

Đây là bản phát triển theo profile giảng dạy tốc độ thấp, chưa hoàn tất toàn bộ chuẩn/mode trong kế hoạch. [Trạng thái kỹ thuật](docs/technical/STATUS.md), [giới hạn ví dụ](examples/README.md), [đánh giá UX/UI](docs/DANH_GIA_UX_UI.md). Windows/Linux chưa có kiểm thử USB/SWD thực tế trong phiên này.

[Đánh giá trước khi đưa lên Git](docs/REVIEW_GIT.md): phạm vi, các lỗi đã sửa, kiểm tra nguồn sạch và giới hạn còn mở.

![Sóng PWM trong HALA Logic](docs/images/02-song.png)

## 5. Đóng góp và giấy phép

[CONTRIBUTING.md](CONTRIBUTING.md) · [Changelog](CHANGELOG.md) · [Thành phần bên ngoài](THIRD_PARTY_NOTICES.md). Giữ thông báo bản quyền HALA Academy theo MIT khi phân phối lại. Repository chưa được push trong phiên này.
