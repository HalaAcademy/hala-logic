# Làm rõ yêu cầu không nối dây — 23/10/2026

Yêu cầu mới nhất: chỉ một STM32F103, không nối jumper giữa các chân và **B
vẫn đọc/ghi GPIO vật lý**. RAM là bộ đệm capture/lịch kích thích, không thay
GPIO_IDR/BSRR bằng biến RAM. UART/LIN/CAN/CAN FD/FlexRay của B vẫn là
software, không dùng controller giao thức phần cứng. Lựa chọn bus RAM trước
đó đã được người dùng làm rõ lại bằng yêu cầu giữ GPIO vật lý; không dùng nó
để thay đổi interface B. Các wiring W1–W4 trong R002 là phương án cũ.

## Những việc khác nhau cần tách rõ

| Việc | Không dây làm được thế nào | Ý nghĩa kiểm thử |
| --- | --- | --- |
| Quan sát GPIO do B phát | Timer kích DMA đọc GPIO_IDR vào RAM, USB chuyển về host | Waveform GPIO thực; không cần jumper để đọc chính port đó |
| Một bên tạo mức, B đọc lại cùng pad | A cấu hình/drive pad, B đọc IDR cùng pad; cần hợp đồng mode/ownership | Self-test một pad; chưa chứng minh bus hai transmitter độc lập |
| Host gửi dữ liệu vào B dùng GPIO thật tùy ý | Buffer RAM/DMA đơn thuần không tạo kết nối giữa hai pad khác nhau | Không thể hứa RX GPIO tùy ý mà không có đường tín hiệu |
| Hai bên truyền/nhận hoàn toàn trong RAM | B đọc/ghi các vị trí RAM quy ước | Không phải phương án người dùng yêu cầu; loại khỏi interface B |

GPIO_IDR là thanh ghi chỉ đọc; DMA không biến nó thành RAM có thể ghi và không
tạo kết nối nội bộ PB8→PB9. Tham chiếu:
[ST RM0008](https://www.st.com/resource/en/reference_manual/rm0008-stm32f103xx-advanced-armbased-32bit-mcus-stmicroelectronics.pdf).

## Đường GPIO vật lý không dây đã chạy trên board

Capture B TX đã có đường thực: `B → GPIO_BSRR → pad → GPIO_IDR → DMA → RAM`.
Không cần jumper để A quan sát chính pad B đã điều khiển.

Host TX dùng A drive chính pad B đọc IDR. Input buffer vẫn quan
sát pad trong output mode theo RM0008, nhưng phải công bố rằng **A giữ quyền
cấu hình/drive pad kích thích**, B đọc IDR và không đổi mode của pad đó trong
test. Đây chưa phải khả năng giữ mọi cấu hình input tùy ý của B nguyên trạng.

Đối với B_TX và B_RX khác pad, cầu tín hiệu tổng quát đang được dùng:

```text
B ghi BSRR_TX → pad TX → IDR_TX → A relay/resolve → BSRR_RX → pad RX → IDR_RX → B
                                 ↑
                       lịch kích thích từ host
```

Không có dây nối TX–RX; phần chuyển tiếp là công việc của A, không phải
kết nối điện có sẵn trong F103. B vẫn dùng thanh ghi GPIO thật. Với bài
dominant/recessive, resolver có thể tổng hợp mức theo rule AND tổng quát,
không parse CAN frame. Phải thiết kế đúng mode điện của pad TX để đọc mức
nhả có nghĩa, và ownership pad RX do A drive.

**Đường này đã qua các bài thử UART/LIN/CAN/FD/FR cụ thể**, không có nghĩa
mọi tốc độ và mode đều đạt. DMA không tự tính AND và không tự nối
hai GPIO. Nếu B liên tục cấu hình RX thành input hoặc khóa cấu hình GPIO,
A không thể drive pad RX bằng output stage theo cách trên; đây là giới hạn
hợp đồng cần công bố, không che bằng API giả hoặc biến RAM thay IDR.

CAN ACK/arbitration và các phản hồi theo bit cần generic engine cục bộ có
deadline đã đo. USB/Python không nằm trong vòng phản hồi bit. Dù pad thật,
relay nội bộ vẫn không phải bus CAN điện nhiều node/transceiver độc lập;
evidence phải phân biệt rõ phạm vi này.

## Trạng thái quyết định

- Không nối dây: đã xác nhận theo yêu cầu người dùng.
- Interface B: GPIO vật lý; không chuyển sang RAM virtual GPIO.
- Không đổi ABI/RAM layout chỉ để tạo thanh ghi GPIO ảo.
- `monitor/stimulus.c/.h` đã tích hợp vào A R002-dev9 và nạp/verify qua SWD.
- PB0 là B_TX, PB10 là host peer, PB8 là pad mức bus do A drive.
- TIM1_UP/DMA1 CH5 phát lịch mức; TIM1_CC IRQ đọc IDR PB0/PB10 và drive PB8.
  Unary relay dùng mask `0x400`; AND resolver dùng `0x401`.
- TIM2_UP/DMA1 CH2 vẫn lấy mẫu GPIOB_IDR vào RAM độc lập vòng main B.
- UART có app phản hồi XOR, LIN có subscriber/publisher, CAN/FD có ACK từ
  PB0 của B và biến nhận được đối chiếu GDB. FlexRay có app counter/data/CRC
  đối chiếu GDB. Host giải mã thành công một mình không đủ làm oracle RX.
- Relay UART đã đo lệch tối đa 2 mẫu ở 32 kS/s trong bài thử. Với FD tải đầy
  đủ (B ISR 32 kHz, relay 64 kHz), capture được nghiệm thu ở 16 kS/s;
  không suy rộng lượt stream 50 kS/s tải nhẹ sang mọi workload.
- Physical Safe strap, cold power và external timing vẫn pending.

Phạm vi và đường dẫn bằng chứng mới nhất được giữ trong
[STATUS.md](STATUS.md).
Nếu một mode không đạt thì giữ trạng thái chưa đạt, không thay GPIO vật lý
bằng biến RAM rồi báo PASS. Pad relay có trễ và dùng cùng clock MCU;
nó không tạo một bus điện nhiều transceiver hoặc hai clock độc lập.
