# Host waveform, phép đo và test modes — R002-PLAN

> Yêu cầu mới: không nối jumper. Xem [làm rõ kiến trúc không dây](NO_WIRE_ARCHITECTURE.md).
> B giữ GPIO vật lý; RAM chỉ là buffer. Host phải nêu mode stimulus/relay,
> ownership và độ trễ đã đo, không lấy waveform mô phỏng thay raw GPIO capture.

**44 nhóm chức năng; đây là yêu cầu nghiệm thu, chưa phải danh sách đã PASS.**
Đi cùng [master plan](MASTER_EXECUTION_PLAN_R002.md) và
[96 nhóm ví dụ B](B_EXAMPLE_MATRIX_R002.md).

## 1. Host phải trả lời được gì

1. B đã tạo ra tín hiệu nào, trên chân nào, tại thời điểm nào?
2. Bit/frame/slot có đúng profile, payload và timing không? Sai tại đâu?
3. Khi host phát kích thích hợp lệ, **B có thực sự nhận/xử lý đúng không**?
4. Lỗi là do B, kích thích A, wiring, capture mất mẫu hay host decoder?
5. Có thể lưu và chạy lại ca đó với cùng cấu hình, seed và firmware không?

Waveform là dữ liệu logic thực; decoder và expected là lớp phủ có thể tắt.
Không sửa waveform khi decoder thấy lỗi. Host đọc được cả dữ liệu thô của
học viên, cho phép họ tự viết script Python đo/giải mã ngoài GUI.

## 2. Một cửa sổ đơn giản

```text
Thiết bị [Connect]  Profile [UART/LIN/CAN/CAN FD/FlexRay]
Test [B phát | Host phát/B thu | Hỏi-đáp | Fault test]
A TX [pin]  B RX [pin]  B TX [pin nếu dùng]  Rate [...]
ID/Slot [...]  Data HEX [...]  [Thiết lập thêm ▾]
[Send] [Capture] [Run test] [Stop] [Save/Open]
Wiring: PB8 → PB9; B cần được build đúng pin/rate này.

[Sóng] [Gói tin] [Kết quả]
  Các kênh logic + time axis + field overlay
  Cursor A/B → Δt; Phép đo [chọn...]
  [Chi tiết đo/trigger ▾]  [Thanh ghi/GDB ▾]
Status: capture quality, PASS/FAIL/INVALID và lý do
```

Không có dashboard nhiều trang, không yêu cầu người học khai báo mọi timer
register trước khi dùng. Các chi tiết kỹ thuật chỉ xuất hiện trong Advanced,
log/debug hoặc khi chúng giúp giải thích lỗi. Default từ preset/recipe.
Worker I/O/analysis gửi kết quả sang UI thread; stop/cancel có state rõ ràng.

### 2.1. Form thay đổi theo giao thức

| Profile | Trường cơ bản | Advanced khi cần |
| --- | --- | --- |
| GPIO | Pins, pattern/pulse, period/width/repeat | Tick, masks, idle, trigger |
| UART | Baud, data bits, parity, stop, payload | TX/RX implementation label, inversion extension, idle, inter-byte gap |
| LIN | Role master/slave, ID, data, rate | PID read-only, frame table/length, checksum, schedule, diagnostic, break/response timing |
| CAN classic | 11/29-bit, ID, data/remote, rate | DLC, sample point/timing, filter, listen-only/single-shot, ACK peer, fault type |
| CAN FD | 11/29-bit, ID, data, nominal/data rate, BRS | ISO profile fixed, ESI/state, DLC read-only/map, timing, peer/error settings |
| FlexRay teaching | Channel, frame ID/slot, cycle, payload, scaled rate | Static/dynamic, flags, slot/minislot/macrotick, payload word count, schedule/profile |

Full duplex chỉ cho UART/fixture phù hợp. CAN/FD là shared bus, LIN là
header/response, FlexRay là schedule; không hiển thị một nút “full duplex”
chung cho mọi giao thức. Remote mode không xuất hiện cho FD. Rate field
không có nghĩa host tự đổi code B; profile/build mismatch phải được báo rõ.

## 3. Ma trận M01–M44

“Pxx” là phase triển khai/hoàn thiện. Có thể có bản tối thiểu trước phase
được ghi; chỉ đóng chức năng sau gate đủ phạm vi. Test tham chiếu là điều
kiện nghiệm thu tương lai, không phải kết quả đã đo.

### 3.1. Waveform và phép đo thời gian

| ID | Chức năng | Hiển thị/kết quả bắt buộc | Ca kiểm chứng và giới hạn | Phase |
| --- | --- | --- | --- | --- |
| M01 | Digital waveform nhiều kênh | Mức 0/1, tên pin/role, time axis, raw sample index, idle và gap | Pattern known 00/FF/55/AA; mask không thay raw capture; one-port đồng bộ | P06 |
| M02 | Zoom/pan/channel selection | Fit capture/selection, rename/hide, track height, raw/decoded toggle | Zoom xa vẫn giữ min/max transitions; rendering decimation không ảnh hưởng phân tích | P06 |
| M03 | Cursor A/B | tA/tB, Δt, sample/tick counts, 1/Δt có nhãn phù hợp | Snap sample/edge, wrap và gap; không báo độ chính xác cao hơn acquisition | P06 |
| M04 | Period/frequency | Min/max/mean period, frequency, edge count trên region | PWM known, ít hơn hai cạnh, non-periodic và missing pulse không cho frequency giả | P06 |
| M05 | Duty cycle | High/low duration, duty per-cycle và statistics | 0/100%, pulse bị cắt đầu/cuối phải báo incomplete, threshold logic cố định | P06 |
| M06 | Pulse width/run length | High/low width, histogram, longest run, pulse count | Pulse sát 1–2 samples, counter wrap; xung nhỏ hơn sample interval có thể bị miss | P06 |
| M07 | Idle, inter-edge gap, missing pulse | Gap duration, timeout marker, stuck-high/low | Timeout boundary, acquisition ending trước deadline là inconclusive, không tự kết luận missing | P06/P12 |
| M08 | Delay/skew giữa kênh | Δt từ edge/pattern A tới B, polarity, match rule | Same-port simultaneous pattern, W1 wire, two-channel; cross-port cần skew calibration riêng | P06/P12 |
| M09 | Response latency | Request end/field marker → response start/end; timeout, sequence match | UART/LIN/CAN/FD/FR app reply; không ghép response cũ vào request mới | P07–P12 |
| M10 | Bit width/baud/rate estimation | Nominal, actual divider, estimate từ cạnh/sync, error %, rate phase | UART training, CAN stuffing, FD hai phase; thiếu edge thì confidence thấp | P07–P12 |
| M15 | Jitter/timing statistics | Min/max/mean/stddev/percentiles, histogram, sample count và reference period | Known dither/injected jitter; tách deterministic drift và random spread, ghi quantization | P06/P13 |
| M16 | Glitch/false edge detection | Width filter, suspect pulse marker, raw event vẫn truy cập được | Pulse dưới/ngang/trên ngưỡng; không lọc âm thầm trước decoder, không hứa phát hiện sub-sample glitch | P06/P12 |
| M17 | Timestamp/timer integrity | 64-bit sample index, epoch, actual ticks, wrap/gap và nguồn clock | Qua DMA block/DWT/timer wrap; reset tạo epoch mới, không nối timestamp xuyên reset giả liên tục | P03/P12 |

### 3.2. Gói tin và đo theo giao thức

| ID | Chức năng | Hiển thị/kết quả bắt buộc | Ca kiểm chứng và giới hạn | Phase |
| --- | --- | --- | --- | --- |
| M11 | UART decoder | Start/data/parity/stop spans, byte/word HEX/ASCII, format/baud | 5–9 bits, N/E/O, stop 1/2 và 1,5 theo profile; bắt đầu giữa frame gắn UNSYNC | P07 |
| M12 | UART errors/timing | Parity/framing/break/false-start, inter-byte gap và byte index | Vectors mỗi lỗi, wrong baud, truncated byte; không vứt byte lỗi khỏi packet log | P07 |
| M13 | LIN decoder | Break/sync/ID/PID/data/checksum, role và schedule context | Payload length từ frame table; unknown length không đoán rồi PASS checksum | P08 |
| M14 | LIN validation | Break/delimiter/sync, PID parity, checksum mode, data length, stop | ID↔PID, bad parity, diagnostic classic checksum, truncated response | P08 |
| M18 | LIN timing/schedule | Header duration, response space, inter-byte/frame, slot/lateness, sleep/wake pulse | Master/slave, event collision/schedule resolution, timeout boundaries | P08/P12 |
| M19 | LIN diagnostic/checksum detail | Calculated/observed checksum, NAD/PCI/sequence, transport reassembly status | Classic/enhanced vectors, FF/CF order/timeout, no full UDS conformance claim | P08 |
| M20 | Classical CAN decoder | SOF/arbitration/control/data/CRC/ACK/EOF; 11/29-bit, RTR/DLC | Valid data/remote and invalid frame, actual bit/field spans và stuffed/raw index | P09 |
| M21 | CAN bus interaction | Dominant/recessive, ACK slot, arbitration-lost bit, release/drive context | Two logical transmitters W3; bus level một mình không cho biết ai drive nếu thiếu pin/recipe context | P09 |
| M22 | Bit/sample annotations | Sample points, bit boundaries, dynamic/fixed stuff bits, logical↔raw mapping | Classical/FD boundary patterns, B timing config so expected; không suy sample point B chỉ từ waveform | P09/P10 |
| M23 | CRC/checksum/error localization | Observed vs computed, CRC model/version, failing span và loại lỗi | Golden vectors độc lập, bit error trước CRC; CRC mismatch không chứng minh chính xác bit vật lý gây lỗi | P08–P12 |
| M24 | CAN states/error behavior | Error/overload/intermission/retry markers; TEC/REC/state nếu có oracle | Counter/state từ B vars hoặc known peer, không tự suy counter chính xác chỉ bằng bus trace | P09/P10 |
| M25 | ISO FD decoder/timing | FDF/BRS/ESI, 11/29-bit, DLC/length, CRC17/21, count/parity, nominal/data phase | Mọi DLC, BRS off/on, 16→20 boundary, 64-byte frames, ISO/non-ISO mismatch | P10 |
| M26 | FlexRay frame view | Channel, frame ID/slot, flags, word/byte length, cycle, payload, CRCs, coding spans | FR21A-TEACH label, null/sync/startup constraints, truncated/invalid frame vẫn nhìn thấy | P11 |
| M27 | FlexRay coding/CRC errors | TSS/FSS/BSS/FES/end sequence, header/frame CRC và error region | Vectors từ nguồn độc lập, sai coding/length/channel context; mode đo logic theo profile | P11 |
| M28 | FlexRay schedule/timing | Static slot/action point, dynamic minislot, symbol window, NIT, cycle timing và lateness | Complete/partial cycle, slot miss, overrun, startup/sync teaching scenarios, explicit scaled timebase | P11/P12 |
| M31 | FlexRay cycle/channel comparison | Channel A/B aligned view, duplicate/different payload, cycle filter, skew/redundancy decision | Simultaneous two-channel evidence; single-port sample constraint và application policy được công bố | P11/P12 |

### 3.3. Acquisition, trigger, stimulus và test

| ID | Chức năng | Hiển thị/kết quả bắt buộc | Ca kiểm chứng và giới hạn | Phase |
| --- | --- | --- | --- | --- |
| M29 | Trigger cơ bản/time trigger | Auto/manual, rising/falling/both, level, width/runt, missing pulse/timeout, holdoff/rearm | Phân biệt sample/software/EXTI hỗ trợ; pre/posttrigger thực có giới hạn, trigger timeout rõ | P03/P12 |
| M30 | Mask/pattern/protocol trigger | GPIO mask/value/sequence; UART byte, LIN ID, CAN/FD ID/error, FR slot/cycle | Chỉ rõ on-device generic vs host postprocess; protocol trigger trên host không hứa pretrigger vô hạn | P12 |
| M32 | Capture modes | Finite single-shot, rolling view, ring pretrigger, finite-long, continuous, segmented/repeated | Actual duration/count/gaps; continuous chỉ trong qualified bandwidth; segmented không giả liên tục | P03/P12 |
| M33 | Stimulus modes | One-shot, finite burst, periodic, timed sequence, bounded reactive peer, raw replay | TX status, actual ticks/output readback, pin lease/idle; unsupported mode bị disable | P04/P12 |
| M34 | Traffic/throughput/quality stats | Frames/bytes/bits per second, occupancy, queue/drop/overrun/underrun counters, latency percentiles | Cửa sổ thống kê có sample count và gap; bus-load có định nghĩa overhead theo profile | P05/P12/P13 |
| M35 | B RX/app oracle và assertions | Expected/observed sequence/data/state, observable kind, timeout, comparator result | O1/O2/O3; GDB sau capture, no stale response, invalid stimulus không chấm B fail | P05–P12 |
| M36 | Expected/actual overlay và replay | Hai trace tách, align bằng run start/edge/frame; diff field/bit/timing, error markers | Expected không thay raw; replay khác rate/clock phải có resampling/quantization report và electrical policy | P05/P12 |
| M37 | Quality/uncertainty | Actual sample rate/tick, calibration status, resolution, edge quantization, gap/UNSYNC flags | No PASS timing vượt resolution, no absolute-clock claim từ cùng HSE; quality truyền vào report | P03–P14 |
| M38 | Test runner/report | PASS/FAIL/INVALID/SKIP/UNSUPPORTED/MANUAL_PENDING, reason, coverage và evidence links | Negative test expected error có thể PASS; bỏ evidence hay mất mẫu không tự PASS | P05–P14 |

### 3.4. Dữ liệu, debug và trải nghiệm dùng

| ID | Chức năng | Hiển thị/kết quả bắt buộc | Ca kiểm chứng và giới hạn | Phase |
| --- | --- | --- | --- | --- |
| M39 | Save/export/import | Raw bin, metadata/session JSON, CSV, VCD, PNG; packet/measurements/report, hashes | Round-trip giữ index/epoch/gap/profile; VCD timescale/rounding khai báo, PNG không thay raw evidence | P06/P12/P14 |
| M40 | Register/app snapshot | GPIO/RCC/TIM/DMA/SCB allowlist, B variable symbols; source/time/halted/running labels | MMIO read không clear flag ngoài ý muốn; nhiều word đang chạy không atomic, B state có thể đã thay đổi | P05/P12 |
| M41 | GDB/SWD integration | ELF check, safe B flash, attach/debug instructions/actions, halt status, A hash before/after | Main/ISR/step/watchpoint thực; halt làm USB ngừng CPU, không giả acquisition realtime còn hợp lệ | P01/P12/P14 |
| M42 | Profile/capability/session config | Pin roles, wiring, available modes/rates, host/A version, B build preset/hash, deviations | Invalid HEX/ID/DLC/pin/resource conflict reject trước arm; B code khác preset phải cảnh báo | P02/P06/P12 |
| M43 | Simple UI/control behavior | Connect/reconnect, Send/Capture/Run/Stop, tabs gọn, progress và lỗi cụ thể | No freeze khi USB chậm, disconnect/reset, cancel có cleanup; preset cơ bản không cần Advanced | P06/P12 |
| M44 | Reproducibility/Python access | CLI và Python API, session recipe/seed, build/tool versions, case-to-evidence traceability | Cùng raw input cho cùng kết quả decoder/measurement version; hardware rerun báo tolerance, không buộc timestamp tuyệt đối trùng | P05/P14 |

## 4. Chế độ test người dùng được chọn

| Test mode | A/host làm gì | B cần làm gì | Kết luận hợp lệ |
| --- | --- | --- | --- |
| Monitor only | A capture, Python hiển thị/đo/giải mã | Tự chạy bài TX | Đúng/sai waveform trong cửa sổ; không kết luận B RX |
| Host TX → B RX | Host encode, A drive, capture stimulus thật | Software RX, app effect/response/variables | PASS RX khi stimulus/capture hợp lệ và oracle B đúng |
| B TX → host peer | A capture và ACK/response nếu protocol cần | Software TX và đọc bus khi cần | PASS TX/peer behavior, không chỉ frame CRC |
| Request–response | Compile stimulus + phản ứng cục bộ có bound | RX → xử lý app → TX | Payload/sequence/latency/timeout và role turnaround đúng |
| Duplex/concurrent | Hai đường UART hoặc lịch nhiều node/kênh hợp lệ | TX/RX đồng thời theo fixture/profile | Ordering, no-loss, deadline và rate envelope |
| Fault injection | Flip/drop/insert bit, CRC sai, delay/jitter, no-ACK, stuck level | Detect/reject/error/recover theo yêu cầu | Negative assertions + frame tốt tiếp theo; hạ tầng lỗi là INVALID |
| Sweep/qualification | Lặp có seed qua rate/phase/payload/load | Implementation được chọn | Bảng miền đạt/thất bại với raw evidence, không hứa mọi setting |
| Replay | Phát waveform ghi trước ở tick được khai báo, capture lại | Thu/xử lý hoặc so TX | Chỉ hợp lệ khi pin mode và protocol turnaround phù hợp |
| Offline analysis | Mở session/raw đã lưu | Không cần board | Kết quả phân tích, không được ghi thành hardware test mới |

Interactive protocol test phải preload/compile trước. Không có deadline
CAN ACK/LIN response/FlexRay slot phụ thuộc Python/UI event loop.

## 5. Hợp đồng tính toán phép đo

### 5.1. Timestamp và độ không chắc chắn

- Mốc dữ liệu chính là sample index 64 bit và timer divider, không phải thời
  điểm Python nhận USB. Wall-clock Mac dùng cho metadata phiên.
- Tính thời gian từ clock/tick thực cấu hình; lưu cả nominal clock và trạng
  thái calibration. Thời điểm bắt đầu có start/trigger skew đã đo hoặc bound.
- Với sample interval `Ts`, mỗi cạnh số hóa có quantization cỡ một khoảng
  lấy mẫu. Báo bound bảo thủ cho phép đo hai cạnh, cộng sai số clock/start
  tương ứng; không hiển thị nhiều chữ số rồi coi đó là độ chính xác thật.
- Có ít hơn số cạnh/frame yêu cầu thì trả `insufficient data`; frame bị cắt,
  gap hoặc UNSYNC phải được giữ cờ. Gap cắt region đo, không tính period
  xuyên gap như thể tín hiệu liên tục.
- Với B/a stimulus cùng HSE, kết quả tương đối không thay thế chuẩn clock
  ngoài. Không có scope/nguồn độc lập thì absolute accuracy để pending.

### 5.2. Định nghĩa thống kê

- Mọi thống kê có region `[first_sample, last_sample]`, channel, edge rule,
  count, unit, estimator và các sample/frame bị loại kèm lý do.
- Jitter ghi rõ tham chiếu: period-to-period, deviation từ nominal, hoặc
  time-interval error sau alignment. Không trộn ba đại lượng thành một số.
- Latency phải định nghĩa mốc request và response; FD phase switch/FR action
  point là mốc protocol có rule cụ thể, không suy ra bằng cạnh bất kỳ.
- Bus utilization nêu mẫu số/cửa sổ và overhead tính vào: arbitration,
  stuffing, intermission, idle hoặc slot reservations tùy profile.
- Bit error của negative injection chỉ có vị trí “đã inject” khi recipe và
  output capture xác nhận; CRC mismatch đơn lẻ không định vị được bit gốc.

### 5.3. Hiển thị đúng dữ liệu

Khi zoom xa, renderer có thể tổng hợp transitions/min-max để vẽ nhanh. Mọi
đo/decoder chạy trên raw hoặc representation đã chứng minh không mất thông
tin cần dùng. Nếu chuyển từ raw samples sang RLE/edges, metadata ghi phương
pháp, resolution, overflow và khả năng phát hiện pulse. Không nội suy analog
rise/fall từ mức GPIO 0/1.

## 6. Kiểm chứng host độc lập firmware

1. **Golden input:** synthetic raw capture có waveform/timestamp biết trước;
   so field, CRC, spans và phép đo ở boundary/phase khác nhau.
2. **Independent vectors:** nguồn/implementation tham chiếu độc lập hoặc
   tính tay, lưu provenance. Encoder và decoder cùng code không đủ oracle.
3. **Corruption tests:** truncate chunk, duplicate/drop/reorder block, wrong
   CRC/length/session, timer wrap/reset, capture bắt đầu giữa frame.
4. **Rendering checks:** zoom giữ xung ngắn, error/gap marker, channel/time
   alignment, export/import và snapshot PNG ở case tiêu biểu.
5. **GUI checks:** validation, conditional fields, capability-disabled modes,
   reconnect/cancel; backend không chạy nhiều job tranh pin ngoài ý muốn.
6. **Hardware integration:** case TX/RX thực, raw output readback, O1/O2/O3,
   GDB registers và performance envelope; giữ cả failed trace để điều tra.

Không cần unit test phản chiếu từng dòng UI; tập trung vào parser, tính toán,
data integrity và các workflow có nguy cơ chấm sai kết quả.

## 7. Phạm vi không thể suy ra từ digital capture này

- Không đo điện áp analog, rise/fall time, overshoot, differential/common-mode,
  eye diagram hay chất lượng transceiver từ GPIO IDR.
- Không bảo đảm thấy pulse ngắn hơn interval lấy mẫu; không tự nhận phân giải
  nanosecond chỉ vì Cortex-M3 chạy 72 MHz.
- Không suy full ISO/automotive conformance từ CRC đúng và packet decode đúng.
- Không có independent-node clock test chỉ bằng hai timer cùng một oscillator.
- Không có unlimited capture hoặc mọi sample rate khi USB/TX/B cùng tải.

Đây là giới hạn đo cần hiện khi liên quan, không phải các pop-up cản học viên
ở mọi thao tác. GUI cơ bản vẫn chỉ có setup → run → xem sóng/kết quả.

## 8. Definition of done cho host

M01–M44 có implementation, test/vector và status cụ thể; các chức năng cũ
chỉ được tính trong phạm vi đã test lại trên A mới. Host xử lý được mọi
lesson G/U/L/C/F/R/X tương ứng capability; raw capture dài không bị cắt âm
thầm; decode error không làm mất waveform. CLI/Python/GUI cùng backend,
session lưu đủ để tái lập, report không PASS khi hạ tầng INVALID. Giao diện
vẫn dùng được cho bài cơ bản mà không mở Advanced.
