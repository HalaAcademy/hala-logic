# Firmware monitor

Source monitor nằm riêng ở monitor/; nền tảng clock/GPIO/USB CDC nằm platform/stm32f103/. Monitor khởi động trước ứng dụng, quản lý USB, Timer/DMA capture và fixture phát mức logic. Giao diện HALA Logic chỉ dùng giao thức USB, không quản lý các file này.

```sh
python tools/lab.py build monitor
python tools/lab.py install-monitor
```

Lệnh cài dùng OpenOCD/ST-Link và verify. Chi tiết [nạp/debug](../docs/NAP_VA_DEBUG.md); thiết kế phân vùng và ISR nằm trong docs/technical. Ví dụ ứng dụng ở examples/, nạp riêng bằng OpenOCD. Giữ clock, USB, SWD, vector và tài nguyên do monitor sở hữu theo hợp đồng phần cứng.
