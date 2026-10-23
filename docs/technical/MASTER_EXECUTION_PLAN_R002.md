# Master execution plan — Blue Pill A/B Resident Monitor

> **Cập nhật yêu cầu:** không nối jumper giữa các chân. Xem
> [NO_WIRE_ARCHITECTURE.md](NO_WIRE_ARCHITECTURE.md). Các wiring W1–W4 phía
> dưới là phương án trước khi làm rõ yêu cầu, không phải điều kiện bắt buộc
> của thiết kế đích. B vẫn đọc/ghi GPIO vật lý; RAM chỉ là bộ đệm. P01 phải
> kiểm chứng đường kích thích/relay GPIO không dây và hợp đồng mode/ownership.

**Mã:** BP-AB-MASTER-20261023-R002-PLAN

**Ngày:** 23/10/2026 · **Trạng thái:** kế hoạch đích; triển khai từng phần, chưa đóng toàn bộ gate

**Phần cứng:** một STM32F103C8T6, Flash 64 KiB, SRAM 20 KiB, clock danh định 72 MHz

**Baseline gốc:** R001 release candidate; không thay thế hay sửa bằng chứng R001.
Trạng thái hiện tại: [R002 implementation/evidence](STATUS.md)
và [progress.json](progress.json). Các mốc trong tài liệu này là yêu cầu
nghiệm thu đầy đủ, không phải danh sách mọi tính năng đã PASS.

## 1. Đích hoàn thành

Học viên viết B bằng C, GPIO, timer, EXTI và ISR thông thường để học bản chất
UART, LIN, Classical CAN, CAN FD và FlexRay ở tốc độ đã kiểm chứng. A phục vụ
USB, lấy mẫu GPIO bằng Timer/DMA và phát/kích thích waveform tổng quát.
Python trên Mac cấu hình bài thử, dựng gói kích thích, đọc mẫu, hiển thị sóng,
giải mã và đánh giá kết quả. Giao diện giữ đơn giản, một cửa sổ.

Hai chiều bắt buộc cho từng họ giao thức:

1. **B phát → A lấy mẫu → host đo/giải mã/so sánh.**
2. **Host dựng kích thích → A phát bằng phần cứng định thời → B thu bằng
   software → xác nhận kết quả B bằng phản hồi ứng dụng hoặc đọc biến qua GDB.**

Ngoài ra có bài hỏi–đáp, phát đồng thời nếu giao thức cho phép, tranh chấp bus,
timeout, lỗi bit/CRC/checksum và phục hồi. Không coi khung nhìn đúng trên host
là bằng chứng B đã thu đúng.

### 1.1. Hợp đồng không thay đổi

- Chỉ một MCU. Không thêm MCU thứ hai để thực hiện host peer.
- USB chỉ mang lệnh, dữ liệu đo và mẫu kích thích; B chỉ được nạp qua SWD.
- A dùng ngắt và các tác vụ có giới hạn, không dùng RTOS đầy đủ và không
  phụ thuộc vòng lặp `main()` B. Trong giai đoạn phát triển có thể cập nhật
  A có kiểm soát; khi phát hành, học viên chỉ cần nạp B cho từng bài.
- B không gọi `monitor_init`, API capture, API USB hay callback của A.
- Startup/linker/Makefile B được chuẩn hóa; module C và ISR của học viên vẫn
  là code thông thường. Thư viện giao thức trong ví dụ B là code học tập,
  có thể thay bằng code của học viên, không phải giao diện bắt buộc với A.
- A không chứa parser UART/LIN/CAN/FD/FlexRay. A nhận lịch mức GPIO, mask,
  timestamp/tick và điều kiện tổng quát; Python hiểu giao thức.
- Capture phản ánh tín hiệu thực, kể cả tín hiệu sai; không chỉnh sóng cho đẹp.
- B không dùng USART/bxCAN để thay thế phần software của B. Timer capture,
  compare, DMA GPIO là công cụ định thời được phép; PWM phần cứng chỉ dùng ở
  bài kiểm tra nền, không thay encoder/decoder giao thức.
- Không đổi phân vùng Flash/RAM hoặc lấy timer của B mà không cập nhật ABI,
  kiểm tra ELF, startup, tài liệu và toàn bộ bài kiểm thử liên quan.

### 1.2. “Đủ giao thức” được hiểu thế nào

Mục tiêu là **đủ các chức năng đã liệt kê trong ma trận bài học**, ở tầng logic
và tốc độ được công bố. Không tuyên bố chứng nhận tuân thủ toàn bộ tiêu chuẩn,
bus vật lý ô tô, EMC hay khả năng làm việc với ECU thật.

| Profile của dự án | Nền tham chiếu | Phạm vi cần triển khai |
| --- | --- | --- |
| `UART-SW-v1` | Format UART được mô tả trong profile dự án | 5–9 data bit; none/even/odd parity; stop 1/2 và 1,5 theo profile 5-bit; TX/RX, half/full duplex, lỗi và timeout |
| `LIN22A-LOGIC-v1` | LIN 2.2A | Header/response, publisher/subscriber, schedule, checksum, diagnostic transport, sleep/wake và lỗi |
| `CAN20-LOGIC-v1` | Classical CAN 2.0A/B | 11/29-bit, data/remote, stuffing, CRC, ACK, arbitration, retry, error state và bus-off |
| `CANFD-ISO2015-LOGIC-v1` | ISO CAN FD theo các tài liệu tham chiếu ISO 11898-1:2015 | 11/29-bit, mọi DLC hợp lệ, BRS/ESI, CRC-17/21, dynamic/fixed stuffing, ACK và lỗi |
| `FR21A-TEACH-v1` | FlexRay 2.1 Revision A | Coding, frame, static/dynamic segment, cycle/slot/filter, hai kênh logic, bài wake/startup/sync có giới hạn |

CAN FD của dự án ghim **ISO FD**, không trộn CRC với Bosch FD đời đầu/non-ISO;
không tự nhận bao phủ toàn bộ thay đổi của ISO 11898-1:2024. LIN dùng ID 6 bit
và PID riêng. FlexRay dùng frame ID/slot, payload length theo word, cycle,
không tái sử dụng form “CAN ID + DLC” một cách sai nghĩa.

Mỗi profile phải có `deviations.md`: tham số tốc độ đã thu nhỏ, giới hạn số
node ảo, deadline, cách mô phỏng clock lệch, tính năng chưa đủ chuẩn và phạm vi
đã kiểm chứng. Một tính năng chỉ được mô phỏng trên host không được ghi là B
đã triển khai. Tính năng trong ma trận bắt buộc còn thiếu giữ trạng thái
`PLANNED/BLOCKED`, không âm thầm bỏ khỏi định nghĩa hoàn thành.

## 2. Điểm xuất phát R001 — tư liệu lịch sử

Bảng dưới ghi baseline lúc lập kế hoạch, không phải trạng thái hiện tại.
Log `acceptance-20261023-151127` và tài liệu R001 được giữ trong archive phát triển ngoài repository.
Xem [kiến trúc hiện hành](NO_WIRE_ARCHITECTURE.md), [trạng thái triển khai](STATUS.md)
và [nạp/debug](../NAP_VA_DEBUG.md) để sử dụng cây nguồn hiện tại:

| Thành phần | Bằng chứng hiện có | Còn phải làm |
| --- | --- | --- |
| A/B, Safe, SWD, GDB | 18 kiểm tra phần cứng, 16 host checks; B busy không chặn USB trong ca đã đo | Physical Safe strap, cold boot, stack/IRQ stress khi thêm TX và streaming |
| Capture | Single-shot 2048 mẫu, 16 bit, một GPIO port; 10k/100k/500k/1M sample/s trên PWM nội bộ | Ring, dài hơn RAM, trigger, pretrigger, mất dữ liệu và đồng bộ TX/RX |
| B TX software | UART 9600 8N1, LIN 9600, CAN 11-bit 20k có raw capture | RX, 29-bit, CAN FD, FlexRay, peer behavior và lỗi theo ma trận |
| Host | CLI, decoder UART/LIN/CAN cơ bản, PNG/CSV/VCD/bin/JSON | Encoder, test runner hai chiều, decoder nâng cao và GUI thật |
| A stimulus | Chưa có | Pattern DMA, drive/release, kích thích phản ứng cục bộ, abort an toàn |
| GUI setup | Mockup lịch sử, không phát hành trong repository | Kết nối backend thật, capability và hiển thị phép đo |

Baseline CAN đang phát không có peer ACK và chưa có arbitration/error
confinement. Không dùng kết quả đó để nghiệm thu stack CAN hai chiều.

## 3. Các quyết định kỹ thuật phải giải quyết sớm

### 3.1. Bộ nhớ là gate đầu tiên

Giữ mặc định A Flash 24 KiB/RAM 12 KiB và B Flash 40 KiB/RAM 8 KiB.
Kết quả `size` của baseline R001 lúc lập kế hoạch: text 8916, data 12,
BSS 11140 byte; BSS đã gồm một số vùng được reserve bởi linker. So với vùng
A 12288 byte, khoảng trống thô còn **1136 byte**, chưa phải ngân sách có thể
tiêu hết mà không đo stack.

Các số trên chỉ mô tả R001. Với cây hiện tại, chạy
`arm-none-eabi-size build/monitor.elf` sau build; định danh firmware đã đo nằm trong [STATUS.md](STATUS.md).

| Hạng mục | R001 | Hướng khảo sát R002 |
| --- | --- | --- |
| Capture buffer | 4096 byte | Tái sử dụng thành hai nửa DMA; không cộng thêm một buffer 4096 byte |
| USB queues | 2048 byte mỗi chiều | Đo high-water; chỉ giảm khi backpressure và stress test vẫn đạt |
| Pattern output | Chưa có | Thử tổng 128 word BSRR = 512 byte, hai nửa 64 word; đo deadline refill |
| Mẫu kích thích nén/VM | Chưa có | Arena có giới hạn, overlay theo mode; compiler phải kiểm tra đủ dữ liệu trước arm |
| Exception MSP | 2048 byte | Dùng chung cho mọi ISR kể cả B; canary/high-water khi IRQ lồng nhau |
| B | 8 KiB kể cả PSP | Giữ nguyên mặc định; mỗi example phải báo Flash/RAM/stack |

Đây là phương án khảo sát, **chưa phải layout đã chứng minh vừa**. Không đưa
thêm mọi buffer/decoder vào A. Parser giao thức, tài liệu sóng, golden vector
và lịch dài nằm trên host. Không ghi pattern tạm vào Flash A trong mỗi test.
P01 phải xuất map file và ngân sách worst-case cho từng mode hoạt động.

Nếu không đủ bộ nhớ: tối ưu queues/representation, overlay phần không hoạt
động đồng thời, chia test có đánh dấu ranh giới hoặc dùng streaming ở tốc độ
đã đo. Không nối các capture rời rồi giả làm một waveform liên tục. Nếu vẫn
không đáp ứng mode bắt buộc, đánh dấu gate bị chặn và công bố tradeoff; không
âm thầm mượn RAM B hay dựa vào Flash 128 KiB không được công bố.

### 3.2. Tài nguyên dự kiến

| Tài nguyên | R001 | Phương án R002 cần kiểm chứng |
| --- | --- | --- |
| TIM2 + DMA1 CH2 | Capture A | Giữ |
| TIM1_UP + DMA1 CH5 | Đang được cấp cho B theo quy ước cũ | Thu hồi cho stimulus A trong ABI/resource contract mới |
| TIM3/TIM4, EXTI được cấp | B | Giữ cho software TX/RX; lập lịch để một timer phục vụ nhiều deadline nếu cần |
| GPIO A_TX | Chưa có | Chỉ pin allowlist được A quản lý theo session; ví dụ PB8/PB10 |
| RAM vector, USB, SysTick, DWT, PA11/12, PA13/14, PC13, PB12 | A/SWD | Giữ; thêm IRQ DMA1 CH5 vào vector A khi được thông qua |

Mapping TIM2_UP/CH2 và TIM1_UP/CH5 theo
[ST RM0008](https://www.st.com/resource/en/reference_manual/rm0008-stm32f103xx-advanced-armbased-32bit-mcus-stmicroelectronics.pdf).
Request timer dùng để kích DMA ghi GPIO_BSRR vẫn phải được chứng minh bằng
CPAR/CMAR/CNDTR và tín hiệu thật. CH5 còn dùng chung request với ngoại vi
khác; B không được bật một nguồn DMA trùng channel khi A đang giữ channel.

Một lệnh BSRR 32 bit chỉ thay bit pin thuộc mask A, không ghi đè ODR cả port.
Open-drain: ghi 0 để kéo thấp, ghi 1 để nhả; không dùng push-pull đối đầu.
Mode/config pin phải được kiểm tra trước khi arm. B thay mode pin A giữa test
là vi phạm resource contract và kết quả test không hợp lệ.

### 3.3. Độ dài bản tin và băng thông

2048 mẫu chỉ chứa tối đa 256 bit ở 8 sample/bit, chưa tính pre/posttrigger.
Riêng payload CAN FD 64 byte đã là 512 bit, cần 4096 mẫu ở tỷ lệ đó, chưa có
header/stuffing/CRC. Hạ bit rate đồng thời hạ sample rate để giữ cùng tỷ lệ
không làm khung dài vừa buffer hơn.

Raw 16 bit tại 1 MS/s tạo **2 MB/s trước overhead**, không được hứa streaming
USB FS liên tục ở tốc độ này. Cần đo ngân sách USB của **A/B thật khi vừa TX,
vừa capture, vừa chạy B**, không lấy benchmark CDC standalone thay thế.

P03/P04 phải chọn và kiểm chứng: raw sample ring, pack kênh được chọn sau
DMA, RLE cho dữ liệu phù hợp, hoặc edge records trong mode được mô tả riêng.
DMA vẫn lấy IDR vào SRAM; việc pack/nén có CPU budget và worst-case riêng.
Không gọi RLE là bảo đảm nén được tín hiệu xen kẽ 0101. Edge-only không được
quảng cáo có chất lượng glitch giống sample mode nếu không có bằng chứng.

### 3.4. Timing và tín hiệu tương tác

- Không phát từng bit bằng USB round-trip hoặc `time.sleep()` Python.
- One-shot phải preload đủ dữ liệu. Lịch dài phải có prefill/refill và kiểm
  tra deadline; underflow dừng test, nhả đường dây, báo `INVALID`.
- DMA BSRR fixed-tick là phiên bản đầu. Descriptor duration/RLE phải được
  giải nén kịp vào DMA ring; một channel DMA không tự ghi cả ARR lẫn BSRR.
  Nếu cần thay ARR bằng phần cứng, phải thiết kế thêm tài nguyên cụ thể.
- ACK, arbitration, LIN response và FlexRay slot cần phản ứng cục bộ.
  A cung cấp thao tác tổng quát `drive/release`, `wait level/edge`, `sample`,
  `match`, `branch bounded`, `timeout`; host compile thành lịch/bytecode.
  Không chạy Python trong deadline bit. Engine phản ứng là **gate khả thi**,
  không suy ra từ việc phát được một pattern cố định.
- B vòng polling có thể miss bit khi bị USB preempt; polling là bài học có
  miền tốc độ riêng. Không tắt ngắt toàn cục lâu để làm bài bit-bang “đúng”.
- Capture, A stimulus và B cùng clock HSE: so sánh tương đối tốt nhưng không
  chứng minh sai số tuyệt đối/khả năng chịu lệch clock độc lập. Phải inject
  lệch pha/jitter có kiểm soát và đánh dấu chưa hiệu chuẩn ngoài.

## 4. Wiring chuẩn cho các test

Tên “A_TX”, “B_RX” là vai trò logic trên **cùng một MCU**. Host chọn chân B
chỉ mô tả cấu hình bài thử, không tự sửa chân/tốc độ trong code B.

| Wiring | Nối thực tế dự kiến | Dùng cho |
| --- | --- | --- |
| `W0` | B_TX PB0; A đọc GPIOB IDR trực tiếp | B phát, không cần jumper |
| `W1` | PB8 A_TX → PB9 B_RX; quan sát thêm PB0 B_TX nếu B phản hồi | Host phát/B thu, request–response |
| `W2` | PB8 A_TX → PB9 B_RX; PB0 B_TX được A đọc; hai đường độc lập | UART full duplex |
| `W3` | PB8 A_OD, PB0 B_OD và PB9 B_RX nối chung, có pull-up 3,3 V | CAN/LIN shared logic, ACK/arbitration/turnaround |
| `W4` | Hai đường logic/kênh; ví dụ A_TX PB8/PB10 → B_RX PB9/PB11; B_TX PB0/PB1 | FlexRay hai kênh logic; route/ownership theo từng bài |

W4 chỉ là sơ đồ phân vai, không tự biến thành bus FlexRay hai chiều. Bài có
bus turnaround phải chỉ rõ mạch nhả/drive và các jumper trong recipe riêng.
P01 chốt pin thực sự khả dụng, EXTI line và timer capture mapping; không mặc
định mọi pin dùng được cho mọi mode. Capture đồng thời mặc định trong **một
GPIO port**, nhờ đó các kênh có chung sample index. Cross-port là mode riêng
có skew được đo; không hứa capture đồng thời nhiều port bằng engine R001.

Đây là tín hiệu logic 3,3 V. CANH/CANL, LIN 12 V và điện vi sai FlexRay cần
transceiver phù hợp nếu mở rộng sau này; không phải hai chân GPIO “a/b”.
Pull-up và điện dung dây của W3 phải được ghi trong fixture manifest; cạnh
nhả quá chậm có thể giới hạn tốc độ và phải được quan sát ngoài khi cần.

## 5. Roadmap theo phase

Mỗi phase tạo artifact có thể review, test tự động khi hợp lý, raw evidence
và gate rõ ràng. Không cần hoàn thành tất cả GUI rồi mới chạy thử RX đầu tiên.

| Phase | Kết quả chính | Phụ thuộc | Nhóm bài liên quan |
| --- | --- | --- | --- |
| P00 | Ghim baseline, scope/profile, traceability | — | Toàn bộ |
| P01 | ABI, RAM/Flash, resource/pin/IRQ và recovery | P00 | GPIO, X |
| P02 | USB/API có phiên, capability và flow control | P01 | Host nền |
| P03 | Capture dài/ring/trigger cơ bản, integrity | P02 | GPIO, UART; nền FD/FR |
| P04 | Stimulus DMA và reactive engine tổng quát | P01–P03 | Mọi bài host → B |
| P05 | Python encoder/decoder, runner và oracle độc lập | P02; tích hợp P03/P04 | Mọi protocol |
| P06 | GUI đơn giản và đo waveform nền | P03–P05 | GPIO/UART view nền; các đo protocol hoàn thiện ở phase tương ứng |
| P07 | Bộ GPIO/UART hai chiều hoàn chỉnh | P04–P06 | G01–G08, U01–U12 |
| P08 | LIN software master/slave | P07 | L01–L15 |
| P09 | Classical CAN software | P07, reactive P04 | C01–C18 |
| P10 | ISO CAN FD software | P09, capture dài P03 | F01–F16 |
| P11 | FlexRay teaching profile software | P07, P04/P05; tài nguyên đã duyệt | R01–R19 |
| P12 | Hoàn thiện mọi phép đo/protocol view/test mode | P08–P11 | M01–M44 |
| P13 | Stress, lỗi, giới hạn tốc độ và phục hồi | P07–P12 | X01–X08; toàn bộ |
| P14 | Đóng gói, tái lập và phát hành | Tất cả gate bắt buộc | Toàn bộ |

### P00 — Ghim phạm vi và baseline

**Làm:** lưu nguyên release candidate/evidence R001; ghi toolchain, board ID,
USB identity, hash A/B, cấu hình OpenOCD/GDB. Tạo registry yêu cầu `REQ-*`,
profile và liên kết phase → example → measurement → test → evidence. Đánh dấu
những chức năng chưa có; ghim tài liệu chuẩn và SHA của bản tham chiếu có
quyền sử dụng. Chốt chính sách không dùng phần cứng UART/CAN cho protocol B.

**Bàn giao:** `scope.md`, `profiles/*`, inventory baseline, backlog có trạng
thái. Các file này là đầu việc tương lai, trừ bộ kế hoạch đang đọc.

**Gate:** mọi yêu cầu người dùng được map vào backlog; không có mục “đủ
FlexRay” chung chung không định nghĩa. Baseline vẫn tái lập được từ package.

### P01 — Khả thi bộ nhớ, tài nguyên và recovery

**Làm:** prototype tối thiểu capture+TX+USB đồng thời; đo RAM/Flash, queue,
canary MSP/PSP, nested ISR, worst-case critical section. Chốt TIM1/CH5 và cập
nhật vector/resource contract; B dùng TIM3/4/EXTI theo bài. Thiết kế pin lease,
BSRR mask, timeout/abort, trạng thái idle khi reset, Safe và mất USB. Thử ưu
tiên/độ dài ISR, không suy luận từ priority number. Kiểm tra EXTI line conflict.

Kiểm tra physical PB12 strap và cold-power cycle đang pending; phục hồi SWD
ở 100/50 kHz, hạ thêm nếu thực tế cần. Bắt đầu từ lỗi khôi phục được; bài đổi
SWD cần quy trình BOOT0/NRST và fixture rõ ràng, không mass erase mặc định.

**Bàn giao:** resource contract/ABI mới nếu cần, map files từng mode, memory
worksheet, timing budget, pin fixtures và recovery checklist có log.

**Gate:** workload tối thiểu đồng thời vừa 64K/20K, B giữ 40K/8K; không tràn
stack/queue; xác nhận A không bị nạp đè; phục hồi về A Safe sau lỗi được thử.
Nếu engine tương tác không có budget thực hiện ở tốc độ đề xuất, hạ rate và
ghi giới hạn trước khi mở phase CAN/FR. Không bỏ qua gate này bằng mockup.

### P02 — Transport và API host có khả năng mở rộng

**Làm:** giữ discovery/INFO tương thích; bổ sung protocol version, session,
request/response ID, capabilities, ownership, limits. Chốt frame nhị phân có
length, type, sequence, payload CRC và resync; tách control/data để không xen
ASCII vào raw stream. Chọn timeout, giới hạn payload và chunk/window sau khi
đo. Retry không được vô tình phát cùng gói hai lần: command arm/start/abort
có token và semantics idempotent. Ghi rõ ACK lệnh khác ACK trên bus CAN.

Capability trả mode thật đang có: sample rate, port/mask, buffer, trigger,
TX tick, reactive ops, profile host tương thích và mode đồng thời được phép.
API dự kiến `capabilities`, `capture.arm/read/stop`, `stimulus.upload/arm`,
`run.start/abort/status`; không phải các lệnh firmware đã tồn tại.

**Test/gate:** packet split/coalesce, CRC/length sai, duplicate, stale session,
sequence wrap, unplug/replug, reset giữa chunk, host chậm và timeout. Không
treo parser/đọc ngoài buffer; error recovery không làm GPIO phát ngoài ý muốn.
Host cũ hoặc bị từ chối có thông báo version rõ, hoặc tiếp tục lệnh cũ hợp lệ.

### P03 — Capture V2 và trigger

**Làm:** giữ single-shot; thêm circular DMA half/full block, finite long
capture và continuous có rate limit; mỗi block có acquisition ID, first
sample index 64 bit, actual divider, count, sequence, CRC và loss flags.
Chốt ownership giữa DMA/packer/USB, không gửi buffer đang bị DMA ghi lại.
Detect overrun trước khi kết luận protocol; không suy ra “lossless” từ CRC.

Thêm trigger auto/manual, rising/falling/both, level/mask pattern, pre/post
trigger, repeated acquisition. Pulse-width/timeout/protocol trigger triển
khai sau ở P12, trả rõ hardware/software/postprocess và độ trễ tương ứng.
Protocol trigger host không thể phục hồi pretrigger đã bị board ghi đè khi
host phát hiện trễ. Định nghĩa giới hạn cửa sổ, holdoff, rearm và timeout.

**Bàn giao:** data format v2; renderer giữ gap; capability rate table;
golden pattern và metadata test. Chọn representation để chụp được khung
CAN FD 64 byte và FlexRay profile payload tối đa đã cam kết một cách liên tục.

**Gate:** đo thực chuỗi qua nhiều DMA wrap, sample index đúng, không nối mất
dữ liệu; khi cố tình host chậm phải có cờ lỗi. Rate được công bố chỉ trong
envelope đã thử, có USB/TX/B load. Mọi đoạn bị mất dữ liệu đánh dấu `INVALID`.

### P04 — Bộ phát waveform và peer phản ứng cục bộ

**Làm theo bậc:** (a) pattern fixed-tick preload, one-shot; (b) burst/repeat
và pattern dài refill; (c) đồng bộ capture+stimulus; (d) generic reactive
engine có execution bound, input mask, branch/timeout và drive/release.
Host encoder tạo pattern/bytecode; không thêm opcode tên CAN/LIN vào A.

Mỗi job khai báo pins, mode điện, idle, tick, duration, masks, expected input,
deadline và maximum duration. Validate toàn bộ trước arm; không được ghi pin
USB/SWD/Safe/B_TX ngoài lease. Start có run ID chung với capture; đo start skew,
DMA bus contention và phản ứng xấu nhất dưới tải. Không chỉ đo khi B đứng yên.

**Gate DMA:** GDB xác nhận TIM1/DMA request, CPAR là BSRR đúng port, CMAR
trong A, width32, mask đúng; capture/thiết bị ngoài xác nhận output. Underflow,
abort, disconnect theo policy, reset và lỗi VM đều trả idle/release trong bound.

**Gate reactive:** measured worst-case reaction đáp ứng ACK/arbitration/slot
của profile ở rate được cấp phép. Fixed-pattern playback đơn thuần chưa đạt
gate này. Capture actual output/readback cho từng fault injection; nếu peer
không phát đúng kích thích thì không chấm B FAIL.

### P05 — Python SDK, codec và test runner

**Làm:** API không phụ thuộc GUI; session schema chứa wiring, profile, B ELF
hash/build config, nominal/actual rates, masks, trigger, stimulus, expected
response và tolerance. Encoder → waveform segments; decoder raw → fields
với span sample/time và error flags; comparator không che lỗi decoder.

Golden vectors phải có nguồn tham chiếu độc lập hoặc tính tay cho ca ngắn;
round-trip encoder của mình ↔ decoder của mình không đủ chứng minh CRC hay
stuffing đúng. Có vector tại biên độ dài, bit pattern cực trị và dữ liệu seed
cố định, negative vector với expected error vị trí rõ ràng.

**B RX oracle:** ưu tiên B trả phản hồi ứng dụng có sequence/payload transform
(ví dụ XOR dữ liệu + counter). Với bài không phản hồi, GDB đọc biến ứng dụng
B sau khi dừng acquisition; cấu hình test chỉ định symbol, không ép mọi B
có một struct monitor. Đọc SRAM qua REG là lựa chọn cho vùng được phép,
không nguyên tử; multiword phải có snapshot/seqlock do bài B tự thiết kế hoặc
đọc khi halt. GDB halt trong khi test realtime làm run đó không còn hợp lệ.

**Gate:** phân biệt lỗi kích thích, lỗi capture và lỗi B; test bị thiếu evidence
không PASS. Có CLI chạy cùng test recipe GUI dùng và xuất report tái lập được.

### P06 — GUI nhỏ và waveform nền

**Làm:** một cửa sổ Python; khảo sát Tkinter + Matplotlib để tái dùng stack
hiện tại, chốt backend sau khi kiểm tra macOS. Phần trên: kết nối, protocol,
vai trò/test mode, pin, rate, ID, data HEX, Send/Capture/Run/Stop. Trường chỉ
hiện khi có nghĩa: CAN FD data rate, LIN checksum/length, FlexRay slot/cycle.

Phần dưới có ba tab gọn: **Sóng**, **Gói tin**, **Kết quả**; Measurements và
Advanced thu gọn. Chọn preset là đủ dùng cho bài cơ bản. I/O và decode chạy
worker, GUI không block; Stop vẫn phản hồi. Lệnh chưa được firmware hỗ trợ
phải disable kèm lý do capability, không làm nút bấm giả thành công.

**Gate:** chạy thật W1 UART RX, xem waveform nhiều kênh, cursor và bảng packet;
lưu/mở lại session. Sai pin/rate/HEX/ID có lỗi cụ thể trước arm. Đổi B không
khớp recipe được báo rõ; chọn pin host không tự cấu hình firmware học viên.

### P07 — GPIO và UART software

**Làm:** G01–G08 và U01–U12 trong
[B_EXAMPLE_MATRIX_R002.md](B_EXAMPLE_MATRIX_R002.md). Đi từ polling có giới
hạn sang timer sampling và EXTI-start + timer; TX dùng delay để minh họa rồi
timer state machine để ổn định. Đủ RX/TX, bit width/parity/stop, simultaneous
full duplex, turnaround, timeout, lỗi framing, jitter và tải ngắt.

**Gate:** mỗi example có ELF riêng hoặc build preset rõ, không gọi A API;
USART clock vẫn tắt; raw evidence hai chiều và B RX oracle. Đo miền baud cho
từng implementation, không gán một max baud chung cho toàn bộ UART software.

### P08 — LIN software

**Làm:** L01–L15; header/response, master/slave, unconditional, event-triggered
và collision resolution, sporadic, diagnostic transport, sleep/wakeup,
checksum classic/enhanced, timeout và recovery. Host làm peer với schedule
được compile trước hoặc reactive tại A; không quyết định response deadline
bằng USB round-trip. LIN profile định nghĩa frame table vì ID không mã hóa
trực tiếp payload length. Có mapping ID↔PID, không nhập PID nhầm vào ID.

**Gate:** B cả publisher và subscriber; chuyển quyền drive đúng ở W3; diagnostic
0x3C/0x3D kiểm tra classic checksum. Bỏ frame lỗi, nhận lại frame hợp lệ tiếp
theo. Schedule có timestamp/slot/lateness evidence, không chỉ checksum PASS.

### P09 — Classical CAN software

**Làm:** C01–C18; bit timing/resync, frame 11/29-bit, data/remote, stuffing,
CRC-15, filter, ACK, non-destructive arbitration, retry, error flags, overload,
TEC/REC, error active/passive, bus-off và recovery. B vừa drive vừa đọc bus;
host peer A được compile có nhánh phản ứng bounded. Ghim quy tắc counter và
recovery theo profile, không thay bằng counter tăng tùy ý.

**Gate:** B thắng/thua arbitration vẫn bảo toàn phần khung hợp lệ; dominant
ACK của peer được thấy thật; ACK missing dẫn đến behavior đúng. Error state
được kiểm cả waveform lẫn B variable; mỗi loại lỗi có recovery test.
Điện logic wired-AND W3 phải đúng, không dùng hai push-pull output đối đầu.

### P10 — ISO CAN FD software

**Làm:** F01–F16 trên nền CAN; 11/29-bit, DLC 0–8/12/16/20/24/32/48/64 byte,
BRS off/on, nominal/data phase, ESI, CRC-17/21, stuff-count/parity và fixed
stuffing. Không có FD remote frame. Phân biệt Classical frame với FD format,
không dùng chung decoder CRC-15 cho FD. Rate ratio khởi đầu 1:2, sau đó 1:4
nếu đo đạt; mọi chuyển pha theo bit timing profile.

**Gate:** max payload và boundary 16→20 byte qua capture liên tục; sample
rate/representation đủ cho data phase; lỗi stuff-count/CRC/phase được chỉ ra.
RX B phải nhận đúng payload 64 byte có sequence, không chỉ header/ID. Kiểm
ACK/error/retry/error-state theo FD profile; không dựa vào GUI decode để PASS.

### P11 — FlexRay teaching profile software

**Làm:** R01–R19; bit/byte coding, header CRC/frame CRC, static slots, dynamic
minislots, symbol window/NIT, cycle/filter, null/sync/startup flags, hai kênh
logic và bài wake/startup/synchronization có bound. Profile định nghĩa micro/
macrotick và mọi tham số phụ thuộc tốc độ; không chỉ kéo dài waveform tùy ý.

Triển khai theo tầng: frame → một slot → nhiều slot/cycle → dynamic segment
→ RX filter → channel A/B → fault/startup/sync. Decoder và GUI luôn ghi
`FR21A-TEACH-v1`; không gọi một stream frame định kỳ đơn giản là toàn bộ stack
FlexRay. Payload dài kiểm đến 254 byte nếu cam kết profile đầy đủ dải frame;
length tính word nên payload lẻ phải bị từ chối hoặc pad có khai báo.

**Gate:** TX/RX và scheduler đều có waveform/variable evidence; miss slot,
wrong cycle/CRC và channel lỗi được xử lý. Startup/sync test với peer ảo có
offset/drift đã inject không được coi là cluster thật với oscillator độc lập.
Hai kênh phải chạy đồng thời trong bài redundancy nếu feature được đánh dấu
đã hoàn thành; chạy lần lượt hai trace chưa đạt. Nếu RAM/timer không đủ, giữ
gate bị chặn kèm số đo và thiết kế lại trong giới hạn một MCU.

### P12 — Đo và đánh giá đầy đủ trên host

**Làm:** hoàn tất M01–M44 trong
[HOST_MEASUREMENT_MATRIX_R002.md](HOST_MEASUREMENT_MATRIX_R002.md): pulse,
frequency/duty, jitter, baud, latency, frame/slot, triggers, statistics, decode
và expected/actual overlay. Cùng một capture phải có kết quả CLI và GUI giống
nhau. Mọi số có unit, sample/time range, method và uncertainty/quality.

**Gate:** known waveform, boundary sample, glitch, mất block, lệch clock,
capture bắt đầu giữa frame, thiếu ACK và stale register snapshot đều cho
trạng thái đúng. Trigger hậu xử lý không bị ghi nhãn hardware trigger. Export
rồi import giữ sample index, gap, config, lỗi và kết quả đo; downsample chỉ
phục vụ vẽ, không được làm biến mất xung trong phân tích raw.

### P13 — Stress, fault injection và qualification tốc độ

**Làm:** X01–X08, đồng thời capture+stimulus+USB+B TX/RX; CPU busy, ISR tải,
queue gần đầy, unplug, reset, overflow/underflow, stale session. Test seeded
payload và sweep rate/phase/error có giới hạn, báo cả dữ liệu thất bại. Tách
qualification từng mode, một/two channel, length và workload.

**Định lượng:** đo latency/jitter max và percentile; RAM/stack high-water;
CPU worst-case deadline; USB useful throughput, gap/drop/underrun; thời gian
abort/release; max valid rate có margin. Đặt margin tối thiểu đề xuất 20% cho
ngân sách tải/refill; chỉ dùng sau khi số đo worst-case xác nhận phù hợp.

**Gate:** công bố capability theo configuration đã đạt, không hứa mọi baud
và mọi kết hợp setting. Warm/cold/reset/strap recovery đã có log. Không tạo
PASS bằng việc chạy lại nhiều lần rồi chỉ giữ lượt đẹp; lưu FAIL trước sửa,
nguyên nhân, thay đổi và lượt regression sau sửa.

### P14 — Release và tài liệu học tập

**Làm:** package nguồn, tool versions, A/B ELF/BIN, manifests/hashes, profiles,
recipes, golden vectors, raw evidence, decoder/measurement version và report.
Mỗi bài có mục tiêu, sơ đồ nối dây, build/run/debug, waveform kỳ vọng, lỗi hay
gặp, câu hỏi tự kiểm và cách quay về B mẫu an toàn. Tài liệu rời không chứa
dump firmware gốc của board nếu chưa được phép phát hành.

**Gate cuối:** build sạch trên Mac từ package; ELF checker từ chối ảnh sai;
nạp B giữ đủ Flash A; GDB thật kiểm main/ISR/stack/vector; USB thực, capture
thực; toàn bộ example bắt buộc ở ít nhất một tốc độ có bằng chứng TX/RX tương
ứng; mọi phép đo bắt buộc đã verified; manual gate hoàn tất hoặc release vẫn
là candidate và nêu rõ thiếu gì. Chỉ khi mọi gate bắt buộc đạt mới gọi project
hoàn thành theo profile R002. Publish ra ngoài là bước riêng sau package review.

## 6. Tổ chức code hiện hành

```text
firmware/monitor/       # resident monitor: USB, capture, stimulus, safety
firmware/platform/      # thanh ghi STM32F103, USB CDC
examples/               # bài học C theo giao thức; startup/linker dùng chung
host/                   # GUI, transport, codec, phép đo, export
tools/device/           # build, ELF validator, OpenOCD, GDB helper
tests/unit/             # kiểm tra host không truy cập board
tests/hardware/         # test tích hợp USB/SWD trên board
profiles/               # profile và giới hạn giao thức
docs/                   # hướng dẫn và tài liệu thiết kế
build/                  # artifact/evidence cục bộ, không đưa lên Git
```

Cây nguồn đã chuyển sang bố cục này. Xem [quy ước thư mục](../CAU_TRUC.md).
Các recipe/VM và phép đo chưa triển khai bên dưới vẫn là mục tiêu kế hoạch;
không suy ra đã có tính năng chỉ từ bố cục thư mục.

### 6.1. Một recipe minh họa, chưa phải lệnh hiện có

```yaml
id: F04-rx-64-brs
profile: CANFD-ISO2015-LOGIC-v1
example: F04
build_preset: canfd_rx_timer
wiring: W3
pins: {a_drive: PB8, b_rx: PB9, b_drive: PB0}
rates: {nominal: 2000, data: 8000}
frame: {id: 0x123, extended: false, brs: true, esi: false,
        data_pattern: incrementing_64_bytes}
capture: {port: B, pins: [PB8, PB9, PB0], samples_per_fast_bit: 16,
          mode: finite_long, pretrigger_bits: 20}
oracle: {kind: gdb_after_capture, symbols: [rx_count, rx_data, rx_errors]}
expected: {rx_count_delta: 1, rx_errors_delta: 0, payload_equals_stimulus: true}
```

Mức 2k/8k ở đây là **giá trị đề xuất để triển khai**, chưa được đo/PASS.
Compiler phải đổi recipe thành capture/sample count và schedule đủ dài, từ
chối nếu capability không đáp ứng. Không gửi literal `incrementing_64_bytes`
đến B; host sinh dữ liệu xác định được.

## 7. Quy tắc nghiệm thu và tốc độ

### 7.1. Miền tốc độ khởi đầu để khảo sát

| Họ | Preset đầu đề xuất | Sau đó |
| --- | --- | --- |
| GPIO | Pulse 10 Hz–1 kHz | Sweep đến giới hạn mode được đo |
| UART | 1200/2400/9600 baud | 19200/38400/115200 chỉ sau qualification từng RX/TX implementation |
| LIN | 2400/9600 bit/s | 19200 nếu ISR/response timing đạt |
| Classical CAN | 1k/5k/10k/20k bit/s | Bit timing/sample point và load sweep |
| CAN FD | Nominal 1k/2k/5k, data ×1/×2/×4 | Chỉ quảng cáo cặp rate đã kiểm chứng |
| FlexRay teaching | Bit rate 1k/5k/10k, cùng timing profile thu nhỏ | Tăng sau khi static/dynamic/two-channel scheduling đạt |

Capture giải mã ưu tiên 16 sample/fastest-bit nếu budget cho phép; tối thiểu
8 chỉ là điểm khởi đầu kỹ thuật, không bảo đảm mọi trường hợp jitter/decode.
UART baseline từng chạy 5 sample/bit là bằng chứng riêng, không làm chuẩn
chung cho CAN FD. Với mỗi rate, lưu actual timer divider và actual sample rate.
Scale LIN wake/sleep/startup hoặc FlexRay clock correction phải nêu tham số
nào được scale, tham số nào giữ thời gian thực; không tự scale mọi timeout.

### 7.2. Kết quả có nghĩa cụ thể

| Trạng thái | Nghĩa |
| --- | --- |
| `PASS` | Đúng assertions và có đủ evidence chất lượng; input lỗi có thể PASS nếu B xử lý lỗi đúng |
| `FAIL` | Hạ tầng/kích thích hợp lệ nhưng behavior B/host trái expected |
| `INVALID` | Capture mất mẫu, stimulus underrun/sai, debug halt, wiring chưa xác nhận hoặc clock config sai |
| `SKIP` | Có lý do không chạy lượt này; không tính là đã nghiệm thu |
| `UNSUPPORTED` | Capability hiện tại không hỗ trợ setting; không đồng nghĩa feature đã hoàn thành |
| `MANUAL_PENDING` | Cần thao tác/thiết bị ngoài chưa có bằng chứng |

Mỗi ca cần: run/session ID; profile/recipe/seed; source/build/ELF hash; A hash;
tool version; board/fixture/pins; USB/SWD settings; raw samples + metadata +
gap flags; stimulus actual readback; decoded field spans; expected vs actual;
measurement uncertainty; GDB/reg snapshot nếu dùng; kết quả và lý do.

### 7.3. Cách bao phủ nhiều chế độ mà không nhân bản code vô hạn

- Mỗi ID trong ma trận là một lesson/test family, không nhất thiết một file C.
- Bắt buộc mỗi family TX/RX có case đúng, lỗi, timeout/recovery nếu áp dụng.
- Exhaustive cho miền nhỏ: toàn bộ LIN ID/parity, CAN FD DLC, UART parity mode;
  boundary cho ID/payload/timing; seeded/pairwise cho tổ hợp lớn.
- Test tối thiểu min/typical/max qualified rate, min/max payload, 00/FF/55/AA,
  long runs và seeded random; phải có worst-case stuffing/capture length.
- Không lấy pairwise thay trường hợp tương tác quan trọng: FD BRS+64 byte,
  CAN arbitration+extended ID, LIN event collision, FR two-channel+slot load.
- Nguồn pattern/decoder khác nhau và B RX oracle giúp tránh lỗi chung của
  encoder/decoder tự kiểm lẫn nhau; vẫn công bố giới hạn clock cùng MCU.

## 8. Các mốc dùng được và điều kiện hoàn thành

1. **Mốc hai chiều cơ bản:** P00–P07; host gửi UART thật tới B, B trả lời,
   waveform/cursor/report chạy trong GUI đơn giản.
2. **Mốc LIN + CAN:** P08/P09; peer phản ứng, schedule/arbitration/error được đo.
3. **Mốc CAN FD + FlexRay:** P10/P11; khung dài, hai phase/two-channel theo profile.
4. **Mốc hoàn chỉnh:** P12–P14; mọi lesson và phép đo bắt buộc có evidence,
   giới hạn tốc độ rõ, recovery và build/package tái lập.

Không đặt lịch ngày cố định trước P01/P04 vì RAM, reactive deadline và USB
throughput là rủi ro thực cần số đo. Khi có số đo, tách mỗi phase thành task
build → unit/golden test → bench/GDB → evidence → gate review.

Hai phụ lục là phần bắt buộc của kế hoạch:

- [Ma trận 96 nhóm ví dụ B](B_EXAMPLE_MATRIX_R002.md).
- [Ma trận 44 nhóm chức năng hiển thị/đo host](HOST_MEASUREMENT_MATRIX_R002.md).

## 9. Tài liệu kỹ thuật tham chiếu

- [ST RM0008](https://www.st.com/resource/en/reference_manual/rm0008-stm32f103xx-advanced-armbased-32bit-mcus-stmicroelectronics.pdf): timer, DMA, GPIO, USB và mapping request.
- [ST PM0056](https://www.st.com/resource/en/programming_manual/cd00228163.pdf): Cortex-M3 exception, stack, debug.
- [LIN Specification Package 2.2A](https://www.lin-cia.org/fileadmin/microsites/lin-cia.org/resources/documents/LIN_2.2A.pdf): nền profile LIN.
- [ST AN5348 — CAN FD protocol overview](https://www.st.com/content/st_com/en/technical-documents/an5348-introduction-to-fdcan-peripherals-for-stm32-mcus-stmicroelectronics_asset/chunk-001-topic-an5348-can-fd-protocol-overview.html): cấu trúc và hai bit-rate phase.
- [Microchip — ISO vs non-ISO CRC](https://onlinedocs.microchip.com/oxy/GUID-BA964748-63AC-4D4B-AD5F-E96EAA995DF8-en-US-22/GUID-B450C10C-7D95-44C5-BB33-51988FC0E978.html): tách CRC mode, CRC-17 tới 16 byte và CRC-21 từ 20 byte.
- [Bosch — CAN FD and the CRC issue](https://www.bosch-semiconductors.com/media/ip_modules/pdf_2/papers/icc_2015_mutter_1.pdf): lý do stuff count và xử lý lỗi.
- [NXP — FlexRay Communication Controllers](https://www.nxp.com/products/nxp-product-information/ip-block-licensing/flexray-communication-controllers:FLEXRAY-COMMUNICATION-CONTROLLERS): tham chiếu 2.1 Revision A, frame/buffer/channel.
- [Infineon — FlexRay training](https://www.infineon.com/assets/row/public/documents/10/56/infineon-traveo-ii-flexray-training-en.pdf): static/dynamic/symbol/NIT, microtick/macrotick.

Tài liệu ngoại vi phần cứng được dùng làm tham chiếu hành vi/frame, không
phải yêu cầu dùng controller phần cứng đó trong B. Tài liệu overview không
thay thế specification ở bước viết bit-level state machine; P00 phải chốt
nguồn chuẩn đầy đủ cho từng feature trước khi gọi nó đã tương thích profile.
