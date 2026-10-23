# Đóng góp cho HALA Academy HALA Logic

Dự án dùng [MIT](LICENSE). Đóng góp cần giữ bản quyền/tác giả và giấy phép của thành phần được sử dụng lại. Chưa có repository URL được cấu hình; không gửi issue tới một địa chỉ giả định.

## Quy ước

- UTF-8, LF, tiếng Việt có dấu cho tài liệu/UI/help; identifier, JSON key và thuật ngữ chuyên ngành bằng tiếng Anh.
- Python 4 space, C 4 space, không nhồi logic mới vào một dòng. Function nhỏ, ISR có giới hạn thời gian; tránh blocking trong ISR.
- Dùng Path và subprocess argv, không ghép shell command với đầu vào người dùng. Không ghi đường dẫn user/toolchain/cổng serial cụ thể vào source mặc định.
- Cấu hình host ở configs/lab.json; bài mới thêm configs/examples.json và tài liệu/test tương ứng. Pin/layout là firmware ABI, đổi cần qualification.
- Không sửa/xóa bằng chứng R001 hoặc report lỗi cũ để tạo PASS.

## Trước pull request

```sh
python tools/lab.py doctor
python tools/lab.py build
python tools/lab.py test
python tools/check_repo.py
```

Nếu đổi firmware, codec hoặc đường truyền: chạy test hardware liên quan, GDB đúng ELF mới, lưu SHA256 và kết quả PASS/FAIL/INVALID. Không chạy song song tool trên một board. Phân biệt Windows/Linux CI host với test USB/SWD thực tế.

PR nêu vấn đề, hành vi sau sửa, cách kiểm, kết quả và giới hạn. Ảnh GUI phải từ tool thật; giữ ảnh gốc và provenance. Không đưa backup Flash/log cá nhân lên Git.

## Cập nhật ảnh hướng dẫn

Chụp cửa sổ HALA Logic thật, giữ ảnh gốc trong archive phát triển ngoài cây public.
Cập nhật vùng cắt/chú thích trong `docs/images/crops.json`, rồi chạy:

```sh
python tools/render_guide.py --raw-dir /duong/dan/anh-goc
python tools/check_repo.py
```

Không chụp cả desktop, thanh điều khiển phiên, nội dung riêng tư hoặc tạo sóng giả.
Ảnh PNG chỉ cắt pixel và thêm chú thích bên ngoài vùng GUI; kiểm lại bằng mắt.
Giữ `provenance.json` cùng ảnh để đối chiếu hash và bản thu gốc. Nếu source GUI đổi,
kiểm và chụp lại những vùng bị ảnh hưởng trước khi cập nhật provenance.
