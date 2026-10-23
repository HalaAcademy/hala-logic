"""Thu/phát logic qua USB; độc lập với công cụ nạp và danh mục ví dụ."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from client import Monitor
from config import path
import canfd
import decode
from export import export_capture
import flexray
import stimulus


@dataclass(frozen=True)
class Capture:
    protocol: str = "GPIO"
    port: str = "B"
    mask: int = 0x501
    bit: int = 0
    hz: int = 32000
    count: int = 8192
    baud: int = 1000
    data_baud: int = 2000
    channel: str = "A"
    lin_bytes: int = 2
    stream: bool = True

    def validate(self):
        if (
            self.port not in ("A", "B", "C")
            or not 0 < self.mask <= 0xFFFF
            or not 0 <= self.bit < 16
        ):
            raise ValueError("Port, mask hoặc chân giải mã không hợp lệ.")
        if self.protocol not in ("GPIO", "UART", "LIN", "CAN", "CAN FD", "FlexRay"):
            raise ValueError("Giao thức không được hỗ trợ.")
        if self.protocol != "GPIO" and not self.mask & (1 << self.bit):
            raise ValueError("Mask phải chứa chân cần giải mã.")
        if self.hz <= 0 or self.count <= 0 or self.baud <= 0 or self.data_baud <= 0:
            raise ValueError("Tần số, baud và số mẫu phải lớn hơn 0.")
        if self.stream and (self.count % 1024 or self.count > 1048576):
            raise ValueError("Streaming: số mẫu chia hết 1024, tối đa 1048576.")
        if not self.stream and self.count > 2048:
            raise ValueError("Burst: tối đa 2048 mẫu.")
        required = 8 if self.protocol in ("CAN", "CAN FD", "FlexRay") else 4
        fastest = (
            max(self.baud, self.data_baud) if self.protocol == "CAN FD" else self.baud
        )
        if self.protocol != "GPIO" and self.hz < required * fastest:
            raise ValueError(f"Cần ít nhất {required} mẫu/bit để giải mã cấu hình này.")
        if not 1 <= self.lin_bytes <= 8:
            raise ValueError("Độ dài dữ liệu LIN phải trong 1..8 byte.")

    def decode(self, samples, ticks):
        if self.protocol == "GPIO":
            return []
        hz = 72000000 / ticks
        values = decode.levels(samples, self.bit)
        if self.protocol == "CAN FD":
            return canfd.decode(values, hz, self.baud, self.data_baud)
        if self.protocol == "FlexRay":
            return flexray.decode(values, hz, self.baud, channel=self.channel)
        options = {"data_length": self.lin_bytes} if self.protocol == "LIN" else {}
        return getattr(decode, self.protocol.lower())(values, hz, self.baud, **options)


@dataclass(frozen=True)
class Signal:
    identifier: int = 0x123
    data: bytes = b""
    extended: bool = False
    remote: bool = False
    dlc: int = 0
    brs: bool = True
    cycle: int = 0
    header_only: bool = False

    def encode(self, capture):
        p = capture.protocol
        if p == "UART":
            levels = stimulus.uart(self.data, pin=10)
        elif p == "LIN":
            levels = stimulus.lin(
                self.identifier, self.data, pin=10, header_only=self.header_only
            )
        elif p == "CAN":
            levels = stimulus.can(
                self.identifier,
                self.data,
                extended=self.extended,
                remote=self.remote,
                dlc=self.dlc if self.remote else len(self.data),
            )
        elif p == "CAN FD":
            if self.brs and capture.data_baud != 2 * capture.baud:
                raise ValueError(
                    "Bộ phát CAN FD hiện hỗ trợ BRS với data baud = 2 × nominal baud."
                )
            levels, _ = canfd.frame(
                self.identifier, self.data, brs=self.brs, extended=self.extended
            )
        elif p == "FlexRay":
            levels, _ = flexray.frame(
                self.identifier, self.data, cycle=self.cycle, channel=capture.channel
            )
        else:
            raise ValueError("Chọn UART, LIN, CAN, CAN FD hoặc FlexRay để gửi gói.")
        tick_hz = capture.baud * (64 if p == "CAN FD" else 16)
        bridge = 0x401 if p in ("LIN", "CAN", "CAN FD") else 0x400
        return levels, tick_hz, bridge


def acquire(capture, device=None, signal=None, cancelled=lambda: False):
    capture.validate()
    schedule = signal.encode(capture) if signal else None
    if schedule and (capture.port != "B" or capture.mask & 0x501 != 0x501):
        raise ValueError(
            "Fixture phát hiện tại cần GPIOB và mask chứa PB0/PB8/PB10 (0x501)."
        )
    with Monitor(device) as monitor:
        job = None
        try:
            if schedule:
                levels, tick_hz, bridge = schedule
                job = monitor.stimulus_upload(
                    levels, tick_hz, mask=0x400, idle=0x400, repeat=16
                )
                monitor.bridge(bridge)
                duration = len(levels) * 16 / tick_hz
                if capture.count / capture.hz < duration + 0.01:
                    raise ValueError(
                        f"Cửa sổ thu quá ngắn: cần ít nhất {duration+.01:.3f} giây cho gói và khoảng đệm."
                    )
            options = (
                {"on_start": lambda: monitor.stimulus_start(job["id"])} if job else {}
            )
            if capture.stream:
                status, samples = monitor.capture_stream(
                    capture.port,
                    capture.hz,
                    capture.count,
                    capture.mask,
                    cancelled=cancelled,
                    **options,
                )
            else:
                if job:
                    raise ValueError("Gửi gói kèm thu hiện yêu cầu Streaming.")
                status, samples = monitor.capture(
                    capture.port, capture.hz, capture.count, capture.mask
                )
            tx = monitor.stimulus_status() if job else None
            if tx and (tx["state"] != 3 or tx["underruns"]):
                raise RuntimeError(f"INVALID stimulus: {tx}")
            decoded = capture.decode(samples, status["ticks"])
            prefix = (
                path("output_dir")
                / "captures"
                / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            )
            export_capture(
                prefix,
                status,
                samples,
                decoded,
                None,
                {
                    "stimulus": tx,
                    "decode_bit": capture.bit,
                    "protocol": capture.protocol,
                },
            )
            return Path(str(prefix) + ".json")
        finally:
            if job:
                monitor.stimulus_stop()
