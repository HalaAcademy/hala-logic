# Changelog

## 2026-10-23 — Tách HALA Logic khỏi phát triển firmware

- GUI chỉ COM/USB, cấu hình thu/phát, sóng/gói/phép đo và lưu dữ liệu.
- Bỏ chọn ví dụ, ELF và nạp SWD khỏi GUI; USB backend không import công cụ nạp.
- Source monitor tách vào firmware/monitor; ví dụ giao tiếp thành thư mục độc lập theo giao thức.
- Build, OpenOCD, GDB, validator và kiểm thử phần cứng nằm ngoài host GUI.
- Dọn bản build/log/backup/ảnh cũ khỏi cây project; lưu bản gốc bên ngoài để phục hồi.
- MIT License, Copyright © 2026 HALA Academy.

Profile giảng dạy tốc độ thấp, master plan chưa hoàn tất mọi mode/phép đo. Windows/Linux chưa kiểm USB/SWD thực tế ở phiên này.

## 2026-10-23 — Rà soát trước khi công bố nguồn

- Thay ảnh cũ bằng bốn PNG cắt từ GUI hiện tại, có bước tiếng Việt và SHA256/provenance.
- Sửa liên kết trong tài liệu kỹ thuật; ghi rõ baseline R001 là lịch sử.
- Lưu ví dụ blink cũ ngoài cây nguồn vì linker cũ nạp từ đầu Flash.
- Tách luồng cài GUI và toolchain trên Windows/macOS/Linux; bổ sung thứ tự nạp PWM đầu tiên.
- Sửa trạng thái con trỏ và số mẫu khi mở bản thu/đổi giao thức; thêm test hồi quy.
- Checker quét Markdown lồng thư mục, ví dụ ngoài danh mục và hash ảnh.
