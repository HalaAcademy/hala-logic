# Nạp firmware bằng OpenOCD và debug bằng GDB

Phần này dành người phát triển. GUI HALA Logic không nạp chương trình và không biết danh mục ví dụ.

## 1. Build

```sh
python tools/lab.py doctor
python tools/lab.py build monitor
python tools/lab.py build pwm
```

File monitor: build/monitor.elf; PWM: build/student.elf. Tên artifact student_* được giữ để tương thích các script kiểm thử, không xuất hiện trong GUI.

## 2. Cài monitor lần đầu

```sh
python tools/lab.py install-monitor
```

Lệnh dùng OpenOCD qua ST-Link, verify vùng monitor. Cách gọi OpenOCD trực tiếp tương đương cho monitor:

```sh
openocd -f configs/openocd/stlink.cfg -c "adapter speed 50" -c "program build/monitor.elf verify reset exit"
```

SWD mặc định 50 kHz, có thể hạ 25/10 kHz trong configs/local.json. Đây là tốc độ debug, không phải baud UART/CAN.

## 3. Nạp PWM đầu tiên và mở tool

```sh
python tools/lab.py flash pwm
python tools/lab.py gui
```

Thứ tự lần đầu: build `monitor.elf` và `student.elf` → cài monitor → nạp PWM → mở GUI.
Trong GUI làm theo [sáu bước có ảnh](BAT_DAU.md); PB0 kỳ vọng 1 kHz, duty 50%.
Đóng GUI trước khi đổi chương trình hoặc debug.

## 4. Nạp ví dụ tiếp theo

```sh
python tools/lab.py build uart-rx
python tools/lab.py flash uart-rx
```

Helper kiểm ELF trước khi kết nối, dùng OpenOCD nạp/verify, so sánh đủ 24 KiB monitor trước/sau. Không cần nạp lại monitor mỗi lần đổi code ví dụ. Linker/startup chuẩn và validator bảo vệ quy ước phân vùng, không phải sandbox bảo mật.

Để xem lệnh OpenOCD trực tiếp cho ELF ứng dụng sau khi đã kiểm bằng validator:

```sh
python tools/device/elfcheck.py build/student_uart_rx.elf
openocd -f configs/openocd/stlink.cfg -c "adapter speed 50" -c "program build/student_uart_rx.elf verify reset exit"
```

Cách trực tiếp không có bước so sánh monitor trước/sau của helper. Không mass erase, không nạp raw.elf, không dùng USB để nạp chương trình.

## 5. Debug

Đóng HALA Logic. Terminal thứ nhất:

```sh
python tools/lab.py flash pwm
python tools/lab.py debug
```

Terminal thứ hai:

```sh
arm-none-eabi-gdb build/student.elf
```

Linux apt có thể dùng gdb-multiarch. Trong GDB:

```gdb
set pagination off
target extended-remote 127.0.0.1:3333
monitor reset halt
hbreak main
continue
stepi
delete breakpoints
hbreak TIM4_IRQHandler
continue
delete breakpoints
watch -location student_loop_count
continue
print student_loop_count
x/wx 0x40010c08
delete breakpoints
monitor reset run
detach
quit
```

GDB phải báo Old value/New value cho watchpoint. Khi MCU halt, USB cũng có thể timeout; resume/detach và đóng OpenOCD trước khi mở HALA Logic. Tên ELF phải khớp chương trình đang debug.

## 6. Safe Boot và kiểm thử

```sh
python tools/lab.py mode safe
python tools/lab.py flash pwm
python tools/lab.py mode run
python tools/lab.py gdb-test
```

GDB test tự quản lý server; không chạy cùng server thủ công. Physical Safe strap và cold power vẫn là gate chưa đóng. Kết quả cũ chỉ áp dụng đúng firmware/profile đã đo; sau thay source cần giữ ELF mới và bằng chứng mới.
