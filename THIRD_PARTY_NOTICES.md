# Thành phần và công cụ bên ngoài

Copyright © 2026 HALA Academy áp dụng phần mã/tài liệu dự án theo LICENSE (MIT). Không thay thế bản quyền/giấy phép của dependency hoặc toolchain.

| Thành phần | Vai trò | Nguồn giấy phép chính thức |
|---|---|---|
| pyserial | USB CDC host | [LICENSE](https://github.com/pyserial/pyserial/blob/master/LICENSE.txt) |
| pyelftools | Đọc/kiểm ELF | [LICENSE](https://github.com/eliben/pyelftools/blob/main/LICENSE) |
| Matplotlib | Xuất hình từ mẫu | [Licensing](https://matplotlib.org/stable/project/license.html) |
| Pillow | Cắt/xuất PNG hướng dẫn (dependency của Matplotlib) | [License](https://pillow.readthedocs.io/en/stable/about.html#license) |
| Python / Tcl/Tk | Runtime và GUI | [Python license](https://docs.python.org/3/license.html), [Tcl/Tk license](https://www.tcl-lang.org/software/tcltk/license.html) |
| GNU Arm GCC/binutils/GDB | Biên dịch/debug | Giấy phép kèm bản toolchain được cài; [Arm GNU](https://learn.arm.com/install-guides/gcc/arm-gnu) |
| OpenOCD | SWD/GDB server | [COPYING](https://github.com/openocd-org/openocd/blob/master/COPYING) |

Không đóng gói executable của các tool trên trong ZIP nguồn. Nếu phân phối dependency/toolchain cùng sản phẩm, phải giữ license/notices đi kèm phiên bản đó. Tên CAN, LIN, FlexRay/STM32 được dùng mô tả tương thích/giảng dạy, không là tuyên bố chứng nhận hay bảo trợ của chủ sở hữu.
