# Rà soát trước khi đưa mã nguồn lên Git

Ngày 2026-10-23 · HALA Academy · MIT.

**Kết luận:** cây nguồn phù hợp công bố như một bản phát triển mã nguồn mở. Không gắn nhãn hoàn thiện toàn bộ kế hoạch hoặc đã chứng nhận mọi mode CAN/LIN/CAN FD/FlexRay. Chưa khởi tạo/push repository trong lượt rà soát này.

## Cách đánh giá

Rà lại từ cây nguồn và package sạch, không chỉ dựa vào kết quả checker cũ. Một script kiểm độc lập không import checker dự án đã quét Markdown lồng thư mục, cú pháp Python 3.10, danh mục ví dụ và đường dẫn cá nhân. Đây là lượt kiểm độc lập với bộ kiểm cũ do cùng tác nhân thực hiện, không phải đánh giá của một người/đơn vị bên ngoài.

Tiêu chí tham khảo: [GitHub về tổ chức repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/best-practices-for-repositories) và [định dạng ảnh GitHub hỗ trợ](https://docs.github.com/en/repositories/working-with-files/using-files/working-with-non-code-files). README, MIT, thông báo HALA Academy, hướng dẫn đóng góp, CI và template issue/PR có trong nguồn.

## Các lỗi tìm được và đã sửa

| Vấn đề | Cách sửa / kiểm lại |
|---|---|
| Link Homebrew OpenOCD trỏ trang không tồn tại | Đổi sang formula chính thức open-ocd; executable vẫn là openocd |
| Bốn liên kết hỏng trong tài liệu kỹ thuật | Sửa đường dẫn progress và trỏ tài liệu kiến trúc/trạng thái hiện hành; quét mọi Markdown |
| Ví dụ blink cũ nằm ngoài danh mục, không có README, linker bắt đầu đầu Flash | Lưu ngoài repository và bỏ khỏi cây phát hành; checker từ chối ví dụ ngoài danh mục |
| Ảnh cũ chụp cả thanh tiêu đề/điều khiển phiên, ảnh sóng lặp cả form | Thay bốn PNG từ GUI mới; chỉ cắt pixel thật và thêm chú thích bên ngoài vùng GUI |
| Mở capture mới giữ nhãn con trỏ cũ | Reset con trỏ và nhãn; test chuyển CAN FD → PWM |
| Đổi giao thức giữ cấu hình lấy mẫu trước đó | Đặt lại mặc định theo giao thức, test FlexRay → GPIO |
| Hàng tùy chọn rỗng và vùng trạng thái chật | Thu gọn hàng rỗng, tăng chiều cao cửa sổ; kiểm trực quan trên macOS |
| Hướng dẫn GUI trộn với bước cài GCC/OpenOCD | Viết lại luồng GUI trước; phần phát triển firmware riêng trên ba OS |
| Kế hoạch vẫn mô tả ab/ là cây đích, số liệu R001 giống trạng thái hiện hành | Thay cây hiện tại và đánh dấu baseline R001 là lịch sử |

## Kết quả kiểm tra

- 19 bài có source, README và Makefile; monitor nằm riêng trong firmware.
- 56 unit test qua, gồm kiểm lỗi cấu hình trước USB, codec, phép đo, trạng thái GUI và lỗi repo từng bị bỏ sót.
- GUI chỉ có COM/USB, cấu hình tín hiệu và xem kết quả; không import công cụ build/nạp hoặc danh mục ví dụ.
- USB thật đã kết nối lại và thu PWM: 8192 mẫu, 32000 S/s, lost = 0; PB0 1000 Hz, 50% duty. Không nạp lại firmware trong lượt rà soát tài liệu/UI này.
- Bốn ảnh được kiểm bằng mắt; SHA256 ảnh gốc, vùng cắt, ảnh PNG, source GUI và BIN capture ở [provenance](images/provenance.json). Ảnh CAN FD là phát lại capture thật lịch sử.
- Hướng dẫn có thứ tự build → cài monitor → nạp PWM → mở tool, tách khỏi hướng dẫn dùng giao diện; file/lệnh liên kết đúng cây hiện tại.

### Xác minh nguồn sạch và danh sách Git

- Build từ thư mục nguồn sạch: 20 BIN, SHA256 giống từng byte với firmware tham chiếu; không thay đổi mã C/linker trong lượt sửa tài liệu/UI.
- Kiểm Git tạm ở thư mục riêng: 171 file nguồn công khai, danh sách khớp whitelist đóng gói. `git diff --cached --check` không báo lỗi sau khi bỏ ba khoảng trắng cuối dòng Markdown.
- Thử đặt file cá nhân giả trong configs/local.json, .env/.env.local, build, dist, .venv và __pycache__: không file nào vào staged. Không khởi tạo Git trong workspace thực.
- Script độc lập ban đầu phát hiện sáu lỗi cấu trúc/link; lượt sau không còn lỗi trong phạm vi kiểm. Quét các mẫu private key/token phổ biến và đường dẫn user không có kết quả; đây không phải chứng nhận bảo mật.
- Rà nguồn chính thức đã sửa link Homebrew OpenOCD và chuyển link xPack sang hướng dẫn hiện hành. Trang package Ubuntu gdb-multiarch bị timeout; chưa kết luận link hỏng hay đã xác minh được nội dung.

[Kết quả máy đọc được](review/20261023.json). Log build/test, bản kiểm trước/sau và inventory đầy đủ giữ ở `build/reports/publication-review-20261023/` trên máy phát triển; không đưa log máy cá nhân vào gói nguồn.

## Còn thiếu trước bản phát hành ổn định

Windows/Linux chưa có kiểm USB/SWD phần cứng; workflow CI đã cấu hình nhưng chưa chạy trên GitHub. Hướng dẫn cài đặt hai OS đã rà câu lệnh/nguồn chính thức, chưa gọi là đã thực thi thành công trên máy thật. Cú pháp Python 3.10 được parse, chưa có lượt chạy đầy đủ bằng mọi phiên bản Python hỗ trợ.

Chưa có nghiên cứu usability với học viên, đánh giá screen reader/bàn phím/HiDPI đủ ba OS. Payload dài xem trong JSON; field một dòng có thể cần cuộn ngang. Chưa đo/hiệu chuẩn clock ngoài. Những điểm này không chặn công bố source phát triển, nhưng chặn tuyên bố sản phẩm đã qualification đầy đủ.

Toàn bộ 15 phase / 96 nhóm bài / 44 nhóm phép đo chưa hoàn thành: xem [STATUS](technical/STATUS.md) và [giới hạn ví dụ](../examples/README.md). Không suy ra GDB/RX/đúng giao thức chỉ từ ảnh sóng hoặc CRC hợp lệ.

## Tái kiểm trước commit

```sh
python tools/lab.py build
python tools/lab.py test
python tools/check_repo.py
python tools/source_release.py
```

Sau khi chủ dự án khởi tạo Git, kiểm `git status --short`, `git diff --cached --check` và danh sách staged trước khi commit. Không đưa build, dist, môi trường Python, configs/local.json, .env hoặc archive phát triển lên Git. Dữ liệu BIN trong examples/captures là mẫu đo công khai có chủ đích, không phải firmware build.
