# Cài đặt Linux — Ubuntu/Debian

Copyright © 2026 HALA Academy · MIT. Yêu cầu Python 3.10 trở lên và phiên desktop có Tk. Distro khác dùng trình quản lý gói tương ứng. Chưa kiểm thử USB/SWD trên máy Linux thực tế trong phiên này; CI host chưa thay thế kiểm thử phần cứng.

## 1. Cài Python và Tk

```sh
sudo apt update
sudo apt install python3 python3-venv python3-pip python3-tk
python3 --version
```

## 2. Tạo môi trường và chạy tool

Giải nén mã nguồn, mở Terminal tại thư mục có README.md. Thay đường dẫn ví dụ bằng thư mục thực tế:

```sh
cd /duong/dan/toi/hala-logic
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m tkinter
```

Đóng cửa sổ thử Tk, rồi xem dữ liệu mẫu không cần board:

```sh
python tools/lab.py gui --open examples/captures/pwm.json
```

Với thiết bị đã cài monitor, chọn `/dev/ttyACM...` và **Kết nối**. Xem [bài bắt đầu có ảnh](BAT_DAU.md). Mỗi Terminal mới cần vào thư mục dự án và kích hoạt lại `.venv`.

## 3. Quyền cổng serial

```sh
python -m serial.tools.list_ports -v
```

Nếu CDC báo `Permission denied` trên Ubuntu/Debian:

```sh
sudo usermod -aG dialout "$USER"
```

Đăng xuất/đăng nhập lại để áp dụng nhóm, sau đó rút/cắm USB. Không chạy GUI bằng sudo. Nếu cổng bị chiếm, kiểm tra ứng dụng serial/ModemManager qua log trước khi đổi dịch vụ.

## 4. Tùy chọn — phát triển firmware

```sh
sudo apt install git gcc-arm-none-eabi binutils-arm-none-eabi gdb-multiarch openocd
arm-none-eabi-gcc --version
gdb-multiarch --version
openocd --version
```

Đặt GDB trong `configs/local.json` (không đưa file này lên Git):

```json
{"tools":{"gdb":"gdb-multiarch"}}
```

Sau khi kích hoạt `.venv`:

```sh
python tools/lab.py doctor
python tools/lab.py build
python tools/lab.py test
python tools/check_repo.py
```

Nếu gói hệ thống không phù hợp, dùng [Arm GNU Toolchain](https://learn.arm.com/install-guides/gcc/arm-gnu), chọn host Linux theo kiến trúc máy và target **arm-none-eabi**. [gdb-multiarch](https://packages.ubuntu.com/noble/gdb-multiarch) hỗ trợ debug Cortex-M3.

OpenOCD thường kèm udev rules. Dùng `dpkg -L openocd` để tìm `60-openocd.rules`; nếu chưa cài vào `/etc/udev/rules.d/`, chép file do package cung cấp rồi reload:

```sh
sudo cp /usr/share/openocd/contrib/60-openocd.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Chỉ chạy lệnh `cp` khi đường dẫn nguồn đúng với package của máy; rút/cắm lại ST-Link. CDC và ST-Link có quyền truy cập khác nhau.

## 5. Nạp lần đầu và debug

Theo [thứ tự nạp monitor → ví dụ → mở tool](NAP_VA_DEBUG.md). Khi chạy GDB thủ công, thay `arm-none-eabi-gdb` bằng `gdb-multiarch`. Không chạy hai OpenOCD hoặc hai tác vụ USB cùng lúc. CDC có thể chưa xuất hiện trước khi cài monitor.
