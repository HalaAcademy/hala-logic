# Cài đặt Windows 10/11

Copyright © 2026 HALA Academy · MIT. Dùng PowerShell native; không cần WSL, Make hoặc bash. Yêu cầu Python 3.10 trở lên. Cấu hình CI dùng Python 3.12; chưa kiểm thử USB/SWD trên Windows thực tế.

## 1. Cài Python và mở mã nguồn

Cài Python 64-bit từ [python.org](https://www.python.org/downloads/windows/), giữ thành phần Tcl/Tk theo [hướng dẫn chính thức](https://docs.python.org/3/using/windows.html). Git là tùy chọn nếu bạn tải ZIP; nếu clone, cài từ [git-scm.com](https://git-scm.com/downloads/win).

Giải nén nguồn vào thư mục bạn chọn. Mở PowerShell tại thư mục chứa README.md, hoặc thay đường dẫn ví dụ dưới đây bằng đường dẫn thực tế:

```powershell
cd C:\Projects\hala-logic
py --version
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m tkinter
```

Đóng cửa sổ thử Tk trước khi tiếp tục. Nếu Activate.ps1 bị chặn, không cần đổi policy: thay `python` bằng `.\.venv\Scripts\python.exe` trong mọi lệnh. Ví dụ:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools/lab.py gui
```

## 2. Chạy HALA Logic

```powershell
python tools/lab.py gui --open examples/captures/pwm.json
```

Lệnh trên xem dữ liệu mẫu, không cần board. Khi thiết bị đã được cài monitor, cắm USB Blue Pill bằng cáp dữ liệu, mở GUI rồi chọn COM và **Kết nối**. Kiểm tra Device Manager → Ports (COM & LPT) nếu chưa thấy COM. USB CDC và ST-Link là hai thiết bị khác nhau. Xem [bài bắt đầu có ảnh](BAT_DAU.md).

Mỗi PowerShell mới cần vào thư mục dự án và kích hoạt lại `.venv`, hoặc gọi Python môi trường trực tiếp.

## 3. Tùy chọn — phát triển firmware

Phần này dành cho người build/nạp/debug; không cần để xem sóng trong GUI.

Cài [Arm GNU Toolchain](https://learn.arm.com/install-guides/gcc/arm-gnu): host Windows x86_64, target **arm-none-eabi**. Thêm thư mục `bin` vào PATH. Cài [xPack OpenOCD](https://xpack-dev-tools.github.io/openocd-xpack/docs/install/) và thêm `bin` của OpenOCD vào PATH. Mở PowerShell mới, kích hoạt `.venv`, rồi kiểm tra:

```powershell
arm-none-eabi-gcc --version
arm-none-eabi-objcopy --version
arm-none-eabi-gdb --version
openocd --version
python tools/lab.py doctor
python tools/lab.py build
python tools/lab.py test
python tools/check_repo.py
```

Có thể đặt đường dẫn executable trong `configs/local.json` thay vì sửa PATH; xem [cấu hình](CAU_TRUC.md). OpenOCD cần driver libusb cho ST-Link, xem [README.Windows chính thức](https://github.com/openocd-org/openocd/blob/master/README.Windows.md). Nếu gặp `LIBUSB_ERROR_NOT_SUPPORTED`, làm theo hướng dẫn xPack/Zadig và chọn đúng **ST-Link**; không thay driver CDC Blue Pill hay hub. Thay driver có thể ảnh hưởng công cụ ST khác.

## 4. Nạp lần đầu và debug

Làm theo [thứ tự nạp monitor → ví dụ → mở tool](NAP_VA_DEBUG.md). Các bước này dùng OpenOCD qua ST-Link bên ngoài GUI. CDC có thể chưa xuất hiện trước khi monitor được cài. Không mở hai tác vụ cùng COM hoặc hai OpenOCD cùng lúc.
