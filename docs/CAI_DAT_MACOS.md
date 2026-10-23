# Cài đặt macOS

Copyright © 2026 HALA Academy · MIT. GUI và USB/SWD đã được kiểm trên Apple Silicon trong phiên phát triển. Máy Intel chưa có kiểm thử phần cứng tương ứng. Yêu cầu Python 3.10 trở lên; hướng dẫn dưới dùng Homebrew Python 3.14 và Tk cùng phiên bản.

## 1. Cài Python và Tk

Cài Homebrew theo [brew.sh](https://brew.sh/), mở Terminal mới:

```sh
brew install python@3.14 python-tk@3.14
python3.14 --version
```

[Python và Tk](https://formulae.brew.sh/formula/python-tk@3.14) phải cùng phiên bản. Có thể dùng bộ cài Python có Tk từ python.org thay thế; dùng đúng Python đó để tạo môi trường.

## 2. Tạo môi trường và chạy tool

Tải/giải nén nguồn, mở Terminal tại thư mục chứa README.md. Thay đường dẫn ví dụ bằng thư mục thực tế:

```sh
cd /duong/dan/toi/hala-logic
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m tkinter
```

Đóng cửa sổ thử Tk, rồi chạy bản thu mẫu không cần board:

```sh
python tools/lab.py gui --open examples/captures/pwm.json
```

Khi thiết bị đã cài monitor, cắm USB Blue Pill bằng cáp dữ liệu, chọn `/dev/cu.usbmodem...` và **Kết nối**. Theo [bài bắt đầu có ảnh](BAT_DAU.md). Mỗi Terminal mới cần vào thư mục dự án và `source .venv/bin/activate`.

Liệt kê USB và serial khi cần chẩn đoán:

```sh
system_profiler SPUSBDataType
python -m serial.tools.list_ports -v
```

## 3. Tùy chọn — phát triển firmware

Cài thêm công cụ nếu cần build/nạp/debug:

```sh
brew install git open-ocd arm-none-eabi-gcc arm-none-eabi-gdb
arm-none-eabi-gcc --version
arm-none-eabi-gdb --version
openocd --version
python tools/lab.py doctor
python tools/lab.py build
python tools/lab.py test
python tools/check_repo.py
```

Nguồn package: [GCC](https://formulae.brew.sh/formula/arm-none-eabi-gcc), [GDB](https://formulae.brew.sh/formula/arm-none-eabi-gdb), [OpenOCD](https://formulae.brew.sh/formula/open-ocd). Có thể dùng [Arm GNU Toolchain](https://learn.arm.com/install-guides/gcc/arm-gnu), target **arm-none-eabi**, host darwin-arm64 cho Apple Silicon hoặc darwin-x86_64 cho Intel. Thêm `bin` vào PATH hoặc dùng `configs/local.json` theo [quy ước cấu hình](CAU_TRUC.md).

## 4. Nạp lần đầu và debug

Theo [thứ tự nạp monitor → ví dụ → mở tool](NAP_VA_DEBUG.md). ST-Link nối SWDIO/SWCLK/GND, USB Blue Pill truyền dữ liệu; không cần jumper nối bus PB0/PB8/PB10. CDC có thể chưa xuất hiện trước lần cài monitor đầu tiên. Nếu SWD không ổn định, đặt `{"swd_khz":25}` trong `configs/local.json` rồi thử lại. Nạp và debug nằm ngoài GUI.
