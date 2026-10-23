# Tham chiếu lệnh

Chạy tại gốc dự án sau khi kích hoạt .venv. Key chuyên ngành/subcommand dùng tiếng Anh, mô tả/help tiếng Việt.

## Tool người dùng

```sh
python tools/lab.py gui
python tools/lab.py gui --open examples/captures/pwm.json
python host/monitor.py --help
python host/monitor.py info
python host/monitor.py capture --gpio B --hz 32000 --samples 8192 --mask 0x501 --stream --output build/captures/manual
```

CLI monitor.py là giao thức USB kỹ thuật. Gửi frame có thể dùng GUI, không cần chọn/nạp file trong GUI.

## Phát triển firmware

```sh
python tools/lab.py --help
python tools/lab.py doctor
python tools/lab.py examples
python tools/lab.py build
python tools/lab.py build canfd-rx
python tools/lab.py install-monitor
python tools/lab.py flash pwm
python tools/lab.py flash uart-rx
python tools/lab.py flash build/student_can2_tx_ext.elf
python tools/lab.py flash pwm --stay-safe
python tools/lab.py mode safe
python tools/lab.py mode run
python tools/lab.py info
python tools/lab.py debug
```

Install-monitor và flash đều dùng OpenOCD qua SWD. Doctor/build không truy cập board. Flash validator chạy trước SWD, log ở build/reports. Xem [nạp và debug](NAP_VA_DEBUG.md).

## Kiểm thử và đóng gói

```sh
python tools/lab.py test
python tools/lab.py gdb-test
python tools/lab.py hardware-test
python tools/lab.py hardware-test --steps can_rx_acceptance can_modes_tx_acceptance
python tools/lab.py hardware-test --steps lin_rx_acceptance
python tools/lab.py hardware-test --steps canfd_rx_acceptance advanced_tx_acceptance
python tests/hardware/audit_evidence.py
python tools/check_repo.py
python tools/source_release.py
```

Hardware-test cần board và đóng GUI/server khác, chạy tuần tự và dừng khi lỗi. Báo cáo ở build/reports; GDB test dùng đúng ELF mới. Source release tạo ZIP nguồn trong dist/, không chứa build/log/backup máy. CI host không thay thế kiểm USB/SWD thật.

## Make tùy chọn

```sh
make
make test
make gui
make -C examples/uart/receive build
make -C examples/uart/receive flash
```

Windows không có Make dùng Python CLI tương đương. Makefile không tự xóa thư mục chứa bằng chứng.
