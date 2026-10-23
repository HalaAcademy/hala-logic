# Ma trận ví dụ B — R002-PLAN

> Yêu cầu mới: không nối jumper. Xem [làm rõ kiến trúc không dây](NO_WIRE_ARCHITECTURE.md).
> B vẫn dùng GPIO vật lý. Các cột W1–W4 cần remap sang đường kích thích/relay
> không dây sau khi prototype P01 đạt, không thay thao tác GPIO B bằng RAM.

**96 lesson/test families của thiết kế đích; chưa đóng toàn bộ family.**
Trạng thái từng phần và bằng chứng hiện tại ở
[implementation status](STATUS.md) và [progress.json](progress.json).
Tài liệu đi cùng [master plan](MASTER_EXECUTION_PLAN_R002.md). Một ID có thể
có nhiều build preset và recipe; không yêu cầu sao chép 96 bộ driver.

## 1. Quy ước bắt buộc cho mọi bài

- B là C/ISR thông thường, không gọi API A. TX/RX giao thức dùng GPIO,
  timer/EXTI/software; không bật USART/bxCAN controller để làm thay bài học.
- `TX` trong bảng là **B phát**; `RX` là **B thu**. Host đóng vai peer còn
  lại thông qua generic stimulus/reactive engine của A.
- `W0–W4` theo master plan. Các pin chỉ là preset, phải đối chiếu build B,
  pin lease và fixture trước chạy. W3 cần open-drain/pull-up đúng.
- `O1`: phản hồi ứng dụng B trên chân TX, có sequence/payload transform để
  tránh PASS từ dữ liệu cũ. `O2`: GDB đọc biến ứng dụng sau capture. `O3`:
  ghi nhận hiệu ứng GPIO/counter độc lập của bài. Bài RX cần ít nhất một
  oracle; waveform kích thích đẹp một mình chưa chứng minh B nhận được.
- `Mxx` trỏ sang [ma trận host](HOST_MEASUREMENT_MATRIX_R002.md). M37/M38/M44
  và raw evidence là điều kiện chung của mọi bài, không lặp ở mỗi hàng.
- Một bài negative có thể PASS nếu B nhận ra lỗi, không chấp nhận payload
  lỗi, không treo và tiếp tục nhận gói tốt đúng yêu cầu profile.

Mỗi lesson phải có: `README`, sơ đồ nối dây, `.c/.h`, build preset, memory
report, recipe TX/RX phù hợp, expected waveform/vector, assertions, fault
cases, câu hỏi học tập và GDB checklist. Student có thể thay logic bằng code
riêng mà không sửa A; chỉ cần giữ hợp đồng tài nguyên và update recipe.

## 2. GPIO/timer nền — G01–G08, phase P07

| ID | Bài học/chế độ B | TX: kiểm tra gì | RX: kiểm tra gì/oracle | Biến thể/lỗi | Host đo |
| --- | --- | --- | --- | --- | --- |
| G01 | GPIO toggle bằng polling/delay | W0: chu kỳ, mức idle và số cạnh | — | Busy loop, tối ưu compiler, USB load ảnh hưởng delay | M01–M07, M15 |
| G02 | Timer output compare/PWM làm chuẩn nền | W0: PWM tại các duty/period đặt trước | — | 0/100%, min pulse, timer wrap; đây không phải protocol encoder | M03–M07, M16 |
| G03 | Timer ISR tạo pulse/pattern software | W0: single, burst, periodic, sequence nhiều chân cùng port | — | ISR trễ, priority thấp, cạnh đồng thời, pulse quá hẹp | M01–M07, M15–M17 |
| G04 | Polling input/counter | — | W1: host phát pulse; O2/O3 đếm và phản ứng GPIO | Pulse ngắn bị miss, rate sweep, CPU busy | M06–M09, M15 |
| G05 | EXTI rising/falling/both | W0: B tạo marker phản ứng | W1: đếm đúng cạnh bằng O2/O3 | Bounce, mask, pending, hai pin trùng EXTI line | M08–M09, M16, M30 |
| G06 | Timer input capture/pulse measurement | W0: marker khi xong phép đo | W1: O2 so period/width timer B với capture A | Prescaler, counter overflow, missing edge, timeout | M03–M09, M17 |
| G07 | Nhiều kênh và open-drain | W3: drive/release, mẫu bus dominant/recessive | W3: đọc bus khi tự phát và khi peer giữ thấp; O2 | Pull-up chậm, pin lease sai, contention bị chặn trước arm | M01–M03, M08, M21 |
| G08 | State machine GPIO không blocking | W1/W2: B trả pulse code theo command input | W1: O1/O2 xác nhận input → state → output | Repeated burst, timeout, queue đầy, wrap timer, stress | M08–M09, M15, M34–M35 |

G04 polling là bài minh họa giới hạn, không cần “sửa” để nhận mọi xung; phải
đo miền nhận đúng và giải thích vì sao miss. G06 được dùng timer input capture
vì đây là công cụ đo, không phải controller giao thức.

## 3. UART software — U01–U12, phase P07

| ID | Bài học/chế độ B | TX: kiểm tra gì | RX: kiểm tra gì/oracle | Biến thể/lỗi | Host đo |
| --- | --- | --- | --- | --- | --- |
| U01 | TX delay/polling 8N1 | W0: start, LSB-first, payload, stop, idle | — | Chuỗi 00/FF/55/AA; tải USB làm lộ jitter | M10–M12, M15, M22 |
| U02 | TX timer ISR 8N1 | W0: one-shot/burst/periodic, payload dài | — | Phase khởi đầu, inter-byte gap 0/nhiều bit, lateness ISR | M10–M12, M15, M34 |
| U03 | RX polling tốc độ thấp | — | W1: O1 echo/transform hoặc O2 payload | Start giữa polling, CPU busy, framing lỗi; đo rate giới hạn | M10–M12, M15 |
| U04 | RX timer sampling | — | W1: O1/O2 sample tâm bit, nhận chuỗi liên tục | Lệch pha, oversampling, parity/stop sai, timeout | M10–M12, M16 |
| U05 | RX EXTI-start + timer | W1: phản hồi sau nhận | W1: O1/O2 đồng bộ từ start, rearm đúng | False start, noise/glitch, idle dài, break, frame kế tiếp tốt | M09–M12, M16 |
| U06 | Format sweep | W0: 5/6/7/8/9 bit, N/E/O, stop 1/2; stop 1,5 với profile 5-bit | W1: O1/O2 mọi format hợp lệ đã định nghĩa | Mismatch format, parity error, high data bit bị cắt; không dùng serial terminal 8-bit làm oracle 9-bit | M10–M12, M22 |
| U07 | Full duplex đồng thời | W2: B phát sequence độc lập trong lúc thu | W2: O1/O2 host và B cùng phát, không mất byte | Pha đối nghịch, back-to-back, tải CPU/USB, queue overflow | M09–M12, M15, M34 |
| U08 | Half duplex/turnaround | W3 hoặc hai đường theo profile: B nhả rồi chuyển vai | O1: request/response có sequence | Phản hồi quá sớm/muộn, stale reply, line bị giữ thấp | M08–M12, M21, M35 |
| U09 | Byte queue/ring buffer | W2: main xử lý chậm vẫn TX đúng thứ tự | W1/W2: O2 head/tail/count/overflow, O1 payload | Wrap, queue đầy, policy drop/new/old được ghi rõ, không âm thầm mất | M11–M12, M34–M35 |
| U10 | Break, idle và timeout | W0: break dài, idle, chuỗi sau break | W1: O1/O2 phân biệt break/framing/no-data | Stop thiếu, line-low kéo dài, timeout sát ngưỡng, recovery | M06–M07, M11–M12, M29 |
| U11 | Baud/phase tracking và autobaud tùy profile | W0: actual baud/timer rounding | W1: O2 rate estimate và O1 dữ liệu | Training 55, dải lệch baud ±, jitter có seed; autobaud không mặc định cho mọi payload | M10, M15–M16, M22 |
| U12 | Mini application protocol trên UART | W2: length/sequence/CRC ứng dụng, response | W1: O1/O2 parse payload không gọi A | Packet split, bad length/CRC, duplicated sequence, timeout, phục hồi sync | M09, M11–M12, M34–M35 |

U01/U02 kế thừa ý tưởng demo UART R001, nhưng chỉ case 9600 8N1 đã có evidence.
Các biến thể mới và toàn bộ RX vẫn phải được kiểm chứng. U06 stop 1,5 là
format của profile UART-SW-v1, cần bổ sung GUI/codec và không giả định mọi
phần mềm terminal hỗ trợ. Inversion/MSB-first nếu thêm phải ghi là extension.

## 4. LIN software — L01–L15, phase P08

| ID | Bài học/chế độ B | TX: kiểm tra gì | RX: kiểm tra gì/oracle | Biến thể/lỗi | Host đo |
| --- | --- | --- | --- | --- | --- |
| L01 | Master header generator | W0/W3: break, delimiter, sync 55, PID | — | ID sweep, header-only, repeated header, idle gap | M10–M14, M18 |
| L02 | Slave header detector | W3: marker/response chỉ với ID được cấp | W3: O1/O2 break/sync/PID nhận đúng | Short break, bad sync, PID parity lỗi, frame ID không đăng ký | M09, M13–M14, M18 |
| L03 | Unconditional master publisher | W3: header + 1–8 data + checksum | W3: host phát response/confirmation khi recipe cần | Payload 00/FF/55/AA, checksum boundary, gap nhỏ/lớn | M13–M14, M18–M19 |
| L04 | Unconditional slave publisher | W3: B chờ header rồi phát response | W3: O1/O2 ID đúng mới phản hồi, đúng payload length theo frame table | Unknown ID, turnaround sớm/muộn, thiếu header, no-response timeout | M09, M13–M14, M18 |
| L05 | Subscriber/master nhận slave response | W3: B master phát header nếu chọn vai master | W3: O1/O2 data từ host publisher, frame counter | 1/2/4/8 byte và các length khác, response thiếu/thừa, timeout | M13–M14, M18–M19 |
| L06 | Classic/enhanced checksum và PID | W3: tạo cả hai checksum mode theo table | W3: O2 accepted/rejected và O1 app effect | Exhaustive 64 ID parity; classic/enhanced mismatch, bad carry/checksum | M13–M14, M19, M22 |
| L07 | Sync/autobaud và clock tolerance | W3: master sync ở actual rate được đo | W3: O2 estimate rate, O1 data sau sync | Rate/phase sweep, jitter sync, header mỗi frame đổi rate trong miền profile | M10, M15–M16, M18 |
| L08 | Schedule table | W3: B master phát nhiều ID theo slot | W3: B subscriber nhận đúng slot; O1/O2 | One-shot/repeat, schedule switch, overrun/late slot, missing response | M09, M18, M28, M34 |
| L09 | Sporadic frame | W3: phát frame có update theo schedule | W3: O2 dữ liệu cập nhật/không cập nhật | Nhiều pending update, không update thì idle, ưu tiên theo table | M13, M18, M28 |
| L10 | Event-triggered frame/collision resolution | W3: B publisher trả event khi có thay đổi | W3: B master phát hiện collision và poll unconditional; O1/O2 | A peer giả lập thêm publisher, collision/missing event, resolution schedule | M08, M13–M14, M18, M28 |
| L11 | Diagnostic master request/slave response | W3: 0x3C request hoặc 0x3D response, đúng PID và classic checksum | W3: O1/O2 NAD/PCI/SID/data theo dịch vụ tối thiểu | Wrong NAD, functional addressing theo profile, timeout, checksum sai | M13–M14, M19, M35 |
| L12 | Diagnostic transport nhiều frame | W3: single/first/consecutive frame ứng dụng mẫu | W3: O1/O2 reassembly và response đầy đủ | Sequence sai, duplicate, thiếu CF, timeout, buffer limit; không tuyên bố đủ UDS | M13, M18–M19, M34–M35 |
| L13 | Sleep/wakeup state machine | W3: sleep command/wakeup pulse theo vai | W3: O1/O2 vào/ra trạng thái logic, nhận lại header | Wake pulse ngắn/dài, retry, bus không hoạt động; không cho MCU STOP làm ngừng A USB | M06–M07, M18, M35 |
| L14 | Fault handling và resynchronization | W3: B từ chối/không phát response trái table | W3: O2 lỗi và frame hợp lệ sau lỗi | Break/sync/PID/stop/checksum sai, stuck-low/high, truncated data, recovery | M07, M13–M14, M18–M19, M35 |
| L15 | Ứng dụng master/slave hoàn chỉnh | W3: B đổi preset master/slave, nhiều ID và schedule | W3: O1/O2 command → state → reply, payload có sequence | Burst/periodic, schedule switch, stress, reset giữa frame, return-to-idle | M09, M13–M14, M18–M19, M34–M35 |

LIN frame table phải khai báo publisher/subscriber, length, checksum,
schedule và response space. Diagnostic transport L12 không kéo theo yêu cầu
triển khai toàn bộ danh mục dịch vụ chẩn đoán xe. Sleep ở L13 là trạng thái
node logic; mọi power mode thực tế cần kiểm tra rằng A/USB không bị phá.

## 5. Classical CAN software — C01–C18, phase P09

| ID | Bài học/chế độ B | TX: kiểm tra gì | RX: kiểm tra gì/oracle | Biến thể/lỗi | Host đo |
| --- | --- | --- | --- | --- | --- |
| C01 | Base data frame 11-bit TX | W0 trước, W3 khi có peer: SOF→EOF, CRC/stuffing | W3: B đọc ACK/bit monitor khi peer có mặt | DLC 0–8, min/max ID, payload cực trị, ACK missing | M20–M24 |
| C02 | Base data frame 11-bit RX | W3: B ACK khung hợp lệ, reply ứng dụng | W3: O1/O2 ID/DLC/data/sequence đúng | Bad CRC/stuff/format không được giao payload, frame tiếp theo tốt | M20–M24, M35 |
| C03 | Extended data frame 29-bit TX | W3: SRR/IDE, arbitration field và CRC đúng | W3: B kiểm ACK | Boundary ID, high/low ID portions, đối chiếu base frame | M20–M24 |
| C04 | Extended data frame 29-bit RX | W3: ACK/response | W3: O1/O2 phân biệt 11/29-bit, không cắt ID | Same low bits khác extended ID, filter hit/miss, invalid field | M20–M24, M35 |
| C05 | Remote request/response | W3: B requester hoặc data responder | W3: O1/O2 RTR không bị hiểu là payload data | 11/29-bit, DLC request, data và remote cạnh tranh cùng ID | M20–M24, M35 |
| C06 | Acceptance filtering | W3: ACK valid frame độc lập với quyết định app filter theo profile | W3: O2 whitelist/mask/range và queue | Adjacent IDs, same ID khác format, remote filter, filter switch | M20, M23–M24, M34 |
| C07 | Bit stuffing/destuffing/CRC-15 | W3: worst-case runs và random seed | W3: O2 payload/error position từ vector độc lập | Stuff bit missing/inverted, CRC bit lỗi, EOF/delimiter sai | M20, M22–M23 |
| C08 | ACK, no-ACK và retry | W3: B phát, peer A ACK hoặc cố ý không ACK | W3: B nhận rồi ACK, app delivery không lặp sai | Delayed/wrong ACK, retry bound/single-shot, bus silent | M21–M24, M34–M35 |
| C09 | Arbitration 11-bit | W3: B và peer bắt đầu cùng SOF; thắng/thua theo ID | W3: B thua chuyển sang nhận, O2 không tự báo TX success | ID khác tại bit đầu/cuối, tie prefix, data/remote | M20–M21, M24 |
| C10 | Arbitration 11/29-bit và 29/29-bit | W3: SRR/IDE/RTR và thứ tự ưu tiên đúng | W3: O2 arbitration-lost bit và khung thắng | Same base ID, extended suffix khác, role đảo | M20–M21, M24 |
| C11 | Bit monitoring và active error flag | W3: B detect mức bus trái expected theo luật bit monitoring | W3: O2 vị trí lỗi và behavior error flag | Inject dominant/recessive ở bit data, CRC, delimiter; không đánh lỗi arbitration/ACK hợp lệ | M20–M24, M35 |
| C12 | Error classification/counters | W3: phát/nhận error flag theo nguyên nhân | W3: O2 TEC/REC đúng chuyển trạng thái | Bit/stuff/CRC/form/ACK error, ca tăng/giảm counter và ngoại lệ theo spec | M23–M24, M35 |
| C13 | Error-passive và suspend transmission | W3: passive error flag, hạn chế phát theo profile | W3: O2 active→passive→active và ESI không áp dụng CAN classic | Counter boundary, valid recovery traffic, cạnh tranh khi passive | M21, M24, M35 |
| C14 | Bus-off/recovery | W3: bus-off phải nhả bus, không tiếp tục spam | W3: O2 state/counter và rejoin đúng điều kiện | Forced errors, manual/auto recovery policy, idle recovery, restart request | M07, M21, M24, M35 |
| C15 | Overload/intermission/bus busy | W3: overload sequence khi case được profile cho phép | W3: O2 không nhầm overload với SOF/data | Earliest next frame, overload boundary, stuck dominant, timeout | M07, M20–M24 |
| C16 | Normal/listen-only/single-shot/self-test logic | W3: TX/ACK policy theo mode, self-test có ghi nhãn | W3: O2 listen-only không drive ACK/error, app RX đúng | Switch chỉ khi idle, no peer, self reception không thay thế peer RX test | M20–M24, M35 |
| C17 | Bit timing, hard sync, resync | W3: sample point/timing segment đúng profile | W3: O1/O2 chịu phase step/drift trong bound | SJW/phase limits, injected rate lệch/jitter, bus idle acquisition | M10, M15–M16, M20, M22 |
| C18 | Queues, traffic và ứng dụng CAN | W3: periodic/event-driven, nhiều ID, request/reply | W3: O1/O2 ordering/sequence/latency/drop policy | Max DLC/stuffing, long run, queue full, simultaneous peer, reset mid-frame | M09, M20, M24, M34–M35 |

Không coi W0 waveform đơn tuyến là đã kiểm C08–C17. ACK/arbitration/error cần
W3 và reactive peer đã qua gate P04. A có thể đóng nhiều vai **node ảo** trong
lịch thử, nhưng không phải các ECU có oscillator/fault domain độc lập.
Vector cho error counters và arbitration phải có tham chiếu chính xác, không
chỉ so sánh hai bản implementation cùng suy luận.

## 6. ISO CAN FD software — F01–F16, phase P10

| ID | Bài học/chế độ B | TX: kiểm tra gì | RX: kiểm tra gì/oracle | Biến thể/lỗi | Host đo |
| --- | --- | --- | --- | --- | --- |
| F01 | FD 11-bit, BRS off, TX | W3: FDF/control/data/CRC/ACK đúng ISO profile | W3: B bit monitor/ACK handling | DLC ngắn, min/max ID, ESI theo trạng thái | M20–M25 |
| F02 | FD 11-bit, BRS off, RX | W3: B ACK/reply | W3: O1/O2 payload và FD metadata | Classic/FD format xen kẽ trong mode được cấp, bad control/reserved bits | M20–M25, M35 |
| F03 | FD 29-bit hai chiều | W3: extended arbitration và data | W3: O1/O2 đủ ID 29-bit | Base/extended same prefix, filter, ID boundaries | M20–M25 |
| F04 | BRS on, RX 64 byte | W3: B ACK/response sau data phase nhanh | W3: O1/O2 đủ 64 byte, không mất đuôi frame | Ratio 1:2/1:4, payload sequence, phase sampling, capture dài | M10, M22–M25, M34 |
| F05 | BRS on, TX | W3: nominal→data→nominal đúng bit boundary | W3: B monitor bus và ACK ở phase đúng | Ratio 1:1/1:2/1:4, rate rounding, switch boundary, ISR lateness | M10, M15, M22–M25 |
| F06 | DLC map exhaustive | W3: mọi length 0–8/12/16/20/24/32/48/64 | W3: O1/O2 length/payload đúng | Invalid app length 9/10/11 phải reject hoặc pad khai báo trước, không đổi DLC ngầm | M20, M23, M25, M34 |
| F07 | CRC-17 boundary | W3: payload 0/8/12/16 byte, golden CRC đúng | W3: O2 chấp nhận/từ chối CRC độc lập | Một bit lỗi header/data/CRC, seed vector, frame sau tốt | M22–M23, M25, M35 |
| F08 | CRC-21 boundary | W3: 20/24/32/48/64 byte | W3: O1/O2 chuyển CRC tại 16→20, đủ payload | CRC17 bị dùng nhầm, long all-zero/all-one, lỗi cuối frame | M22–M23, M25, M34 |
| F09 | Dynamic/fixed stuffing và stuff count | W3: vị trí stuff bit, count/parity đúng | W3: O2 phát hiện count/parity/fixed-stuff lỗi | Pattern cực trị, flip/delete stuff, checksum đúng nhưng count sai | M22–M23, M25 |
| F10 | ESI và FD error state | W3: ESI đúng active/passive state B | W3: O2 phân biệt peer ESI với local error state | State transition, counter boundary, peer passive vẫn nhận được | M24–M25, M35 |
| F11 | Arbitration/ACK/retry FD | W3: arbitration ở nominal rate, ACK và retry | W3: O2 lose arbitration→RX, ACK missing path | 11/29-bit FD, classic arbitration prefix theo profile; không phát FD cho classic-only B | M20–M25, M35 |
| F12 | FD error handling/bus-off | W3: error flag và return-to-nominal theo loại lỗi | W3: O2 counters, passive/bus-off và recovery | Lỗi ở nominal/data/CRC/ACK, đúng thời điểm báo lỗi theo ISO profile | M23–M25, M35 |
| F13 | Filter, queues, mixed traffic | W3: FD và Classical frame ở B có hỗ trợ cả hai | W3: O1/O2 metadata, ordering, filter | Full queues, same ID khác format, back-to-back 64 byte, load stress | M20, M24–M25, M34–M35 |
| F14 | FD fault/compatibility rejection | W3: host cố tình tạo invalid frame | W3: O2 không giao app payload sai, phục hồi đúng | FD remote không hợp lệ, wrong DLC semantics, non-ISO CRC, reserved bits sai | M20, M23–M25, M35 |
| F15 | Data phase tolerance/resync | W3: rate/phase/jitter sweep hai phase | W3: O1/O2 rate pair đạt và giới hạn fail | BRS transition offset, edge density thấp/cao, injected drift, CPU/USB load | M10, M15–M16, M22, M25 |
| F16 | Ứng dụng FD request/response | W3: sequence + payload transform 0..64 byte, cyclic/event mode | W3: O1/O2 input thật → output thật | Timeout, duplicated command, retry, error burst, reset, long capture | M09, M20, M25, M34–M35 |

F06 quy định policy payload ứng dụng không thuộc length hợp lệ trước khi
encode; trên wire DLC chỉ có những length đã định nghĩa. F14 “FD remote” là
negative test, không phải một mode FD hợp lệ. F04/F08/F13 không được bỏ max
payload để làm vừa buffer rồi vẫn đánh dấu cả family đã hoàn thành.

## 7. FlexRay teaching profile — R01–R19, phase P11

Tất cả ghi nhãn `FR21A-TEACH-v1`. Phải đọc profile/deviations cùng kết quả,
đặc biệt các bài startup/sync. Channel A/B là hai kênh logic FlexRay, khác
chương trình A/B của nền tảng.

| ID | Bài học/chế độ B | TX: kiểm tra gì | RX: kiểm tra gì/oracle | Biến thể/lỗi | Host đo |
| --- | --- | --- | --- | --- | --- |
| R01 | Bit/byte coding | W0/W4: TSS/FSS/BSS/FES và ký hiệu kết thúc theo profile | W1/W4: O2 byte stream đã đồng bộ | Start giữa stream, polarity/edge lỗi, delimiter sai | M10, M16, M26–M27 |
| R02 | Frame TX một kênh | W0/W4: header, flags, payload, trailer CRC | W4: B quan sát input/marker cần thiết | Frame ID boundary, null/startup/sync flags có ràng buộc | M26–M27, M31 |
| R03 | Frame RX một kênh | W4: B application reply trong slot được cấp | W4: O1/O2 header/payload/cycle/channel đúng | Bad header CRC/frame CRC, truncated frame, wrong coding | M26–M27, M31, M35 |
| R04 | Header CRC/frame CRC | W4: golden vector và flag/length combinations | W4: O2 chấp nhận/từ chối đúng lớp lỗi | Flip header/data/trailer, channel-specific CRC context theo spec | M23, M26–M27 |
| R05 | Payload length range | W4: 0/2/4/…/254 byte theo word length | W4: O1/O2 min/max và boundary, đủ toàn bộ payload | Odd app length reject/pad có khai báo; zero/static padding, buffer boundary | M26–M27, M34 |
| R06 | Static slot TX | W4: B chỉ phát tại action point/slot được cấp | W4: nhận peer slot khác, O2 cycle state | Early/late TX, missing slot, slot duration/guard, no data/null policy | M26, M28, M31 |
| R07 | Static slot RX/filter | W4: B phản hồi ở slot sau nếu recipe yêu cầu | W4: O1/O2 frame ID/slot/cycle/channel filters | Wrong slot, duplicate frame, late arrival, filter miss không cập nhật app | M26, M28, M31, M35 |
| R08 | Nhiều static slot/cycle | W4: schedule nhiều slot, action point chính xác | W4: O1/O2 ordering và per-slot buffer | Full/empty slots, payload worst-case, cycle wrap, schedule update boundary | M26, M28, M31, M34 |
| R09 | Dynamic segment/minislot TX | W4: phát theo minislot/frame ID và deadline profile | W4: O2 bus activity ảnh hưởng minislot advance | Slot idle/busy, payload dài, cutoff cuối dynamic segment | M26, M28, M31 |
| R10 | Dynamic segment RX | W4: app response ở slot/cycle hợp lệ | W4: O1/O2 nhận dynamic frame đúng filter | Variable length, no frame, duplicate, late frame, minislot drift | M26, M28, M31, M35 |
| R11 | Symbol window và NIT | W4: symbols được chọn và nhả bus trong NIT | W4: O2 cycle progress, symbol recognition theo profile | Symbol sai/cắt ngắn, unexpected activity trong NIT, timeout | M07, M26, M28, M31 |
| R12 | Cycle counter/multiplex/filter | W4: frame phát theo cycle mask/base/repetition | W4: O1/O2 đúng cycle, counter wrap | Adjacent cycle, wrong cycle field, missed cycle, stale payload | M26, M28, M31, M35 |
| R13 | Channel A và B riêng lẻ | W4: cùng test lần lượt channel A rồi B | W4: O1/O2 channel metadata/filter/CRC đúng | Đảo route, một kênh im lặng, cấu hình pin không hỗ trợ | M01, M08, M26–M27, M31 |
| R14 | Hai kênh đồng thời/redundancy | W4: hai channel output cùng cycle, pin role rõ | W4: O1/O2 chọn/so sánh hai bản theo policy ứng dụng | Một kênh lỗi/mất, lệch arrival, hai payload khác; không test lần lượt giả đồng thời | M08, M26–M28, M31, M34 |
| R15 | Wakeup state machine | W4: wake pattern đúng vai trò/mode | W4: O2 trạng thái và hoạt động sau wake | Short/long pattern, collision/wake retry có bound, no peer | M06–M07, M26, M28, M35 |
| R16 | Startup/coldstart teaching scenario | W4: startup frames và state transitions có profile | W4: O2 startup→normal với peer ảo | Missing/invalid peer, timeout, restart, số node ảo công bố rõ | M26, M28, M31, M35 |
| R17 | Sync/clock correction teaching scenario | W4: sync flag/frame đúng slot | W4: O2 correction/phase tracking dưới offset/drift được inject | Correction limit, missing sync, jitter, loss-of-sync/recovery; clock cùng MCU phải ghi rõ | M15–M16, M26, M28, M31 |
| R18 | Error/isolation/recovery | W4: stop/release theo error policy profile | W4: O2 no invalid delivery và trở lại nhận frame tốt | Coding/CRC/slot/cycle/channel lỗi, stuck level, buffer overflow, reset mid-cycle | M23, M26–M28, M31, M35 |
| R19 | Ứng dụng cyclic/event hai chiều | W4: static periodic + dynamic event, sequence/payload transform | W4: O1/O2 command ở slot X → response slot Y/cycle sau | Long payload, two-channel load, queue full, latency bound, run dài | M09, M26–M28, M31, M34–M35 |

R15–R17 phải triển khai state machine B ở phạm vi đã mô tả, không chỉ host
vẽ hình mô phỏng. Không tuyên bố đủ thuật toán cluster startup/clock voting
trong mọi cấu hình từ một vài teaching scenario. Full interoperability với
FlexRay bus vật lý và clock các node độc lập cần chiến dịch kiểm thử khác.

## 8. Bài tích hợp, debug và giới hạn — X01–X08, phase P13

| ID | Bài học/chế độ B | TX: kiểm tra gì | RX: kiểm tra gì/oracle | Biến thể/lỗi | Host đo |
| --- | --- | --- | --- | --- | --- |
| X01 | B busy loop không phục vụ A | B phát signal timer trong khi main busy | RX ISR vẫn nhận trong envelope; O1/O2 | 1000+ control requests theo recipe, capture+TX đồng thời | M15, M34, M37–M38 |
| X02 | IRQ priority/deadline budget | Cùng vector ở priority được phép, B đo lateness | RX dưới USB/DMA IRQ load, O2 counters | Mức gây fail phải có trace; không nâng priority vô hạn để che lỗi | M15–M17, M34, M40 |
| X03 | GDB main/ISR/watchpoint | Dừng/step xác nhận code TX B và tài nguyên | Đọc RX app variables sau capture, O2 | Halt giữa run bị đánh INVALID; vector/CONTROL/MSP/PSP đúng | M17, M38, M40–M41 |
| X04 | Fault/Safe Boot/reflash | B lỗi không làm pattern A treo drive ngoài bound | Sau reset B RX mẫu chạy lại, O1/O2 | UDF/HardFault, invalid manifest/CRC, A hash trước/sau, SWD thấp tốc | M35, M38, M40–M41 |
| X05 | Data integrity/backpressure | B pattern có counter dễ phát hiện gap | O1/O2 packet sequence khi host chậm | USB stall, lost block, capture overrun, stimulus underflow, disconnect | M32, M34–M39 |
| X06 | Timer wrap/long run | TX chu kỳ qua counter/DWT/sample-index wrap | RX vẫn giữ ordering/timeout, O1/O2 | DWT wrap thực, simulated index wrap, soak duration ghi trong recipe | M03, M07, M17, M34–M35 |
| X07 | Resource/stack contract | B hợp lệ với stack/ISR tải cao vẫn không phá A | RX + nested IRQ, O2 và canary | Shared MSP high-water; unsafe pin/clock/VTOR request bị phát hiện hoặc Safe recovery | M15, M17, M38, M40 |
| X08 | Rate/phase/load qualification | Sweep từng mode TX, payload min/max/worst stuffing | Sweep RX cùng observable và negative recovery | Tối thiểu min/typ/max qualified rate, seed cố định, margin, evidence fail biên | M10, M15–M16, M22, M34–M38, M44 |

X07 không biến privileged B thành sandbox: code B tùy ý vẫn có thể phá clock,
VTOR hay PRIMASK. Gate là phát hiện/khôi phục các lỗi đã nêu, không bảo đảm
ngăn mọi thao tác xấu bằng phần cứng.

## 9. Bao phủ biến thể theo lớp

| Chiều kiểm thử | Miền bắt buộc |
| --- | --- |
| Direction | B TX, B RX, request/response; full duplex chỉ khi giao thức/fixture cho phép |
| Run mode | Manual one-shot, finite burst, periodic, repeat/cyclic, replay captured pattern phù hợp |
| RX implementation | Polling cho bài nền; timer sampling; EXTI/edge + timer khi mapping cho phép |
| Data | Empty nếu giao thức cho phép, min/max length, 00/FF/55/AA, ascending, seeded random, stuffing worst case |
| Timing | Qualified min/typ/max rate, phase offset, clock/rate rounding, injected jitter/drift, response timeout boundaries |
| Error | Bad coding/format/parity/CRC/checksum, missing bit/frame/ACK, stuck level, invalid length/ID, recovery frame |
| Traffic | Single frame, back-to-back, mixed IDs, filter hit/miss, simultaneous peer nếu hợp lệ, queue full |
| System | USB active, capture+TX active, B busy/ISR load, reset/fault, SWD debug after run |

Không lấy tích Descartes toàn bộ setting làm lời hứa “đã test mọi tổ hợp”.
Registry recipe ghi rõ coverage: exhaustive với miền nhỏ, boundary với miền
lớn và pairwise có chủ đích; các tương tác quan trọng phải có case riêng.

## 10. Checklist đóng một lesson

1. Build ELF trong B Flash/RAM; manifest/checker đạt, A hash không đổi khi nạp.
2. Học viên chỉ cần code B và build preset, không cần liên kết API monitor.
3. Chứng minh peripheral protocol hardware không được dùng cho lesson đó.
4. Có recipe và wiring tái lập; host GUI lẫn CLI chạy cùng backend.
5. TX có raw capture và field/timing assertions; RX có thêm O1/O2/O3 phù hợp.
6. Có ca lỗi và recovery đúng cho chức năng đã cam kết.
7. Có rate/tolerance/CPU/stack limits, không suy luận từ một ca chạy đẹp.
8. Evidence đủ để phân biệt FAIL B với INVALID hạ tầng; tài liệu kỳ vọng khớp.

Tổng: **8 GPIO + 12 UART + 15 LIN + 18 Classical CAN + 16 CAN FD +
19 FlexRay + 8 tích hợp = 96 families**. Các family TX/RX cơ bản kế thừa
R001 vẫn phải chạy regression trong A phiên bản mới; không tự gắn PASS toàn
bộ family vì một ví dụ con cũ từng đạt.
