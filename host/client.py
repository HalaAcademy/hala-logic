"""USB monitor protocol client. USB has no firmware upload operation."""

import json
from pathlib import Path
import struct
import time

try:
    import termios
except ImportError:  # Windows không có termios.
    termios = None
from config import settings
import zlib
import serial
from serial.tools import list_ports

TRANSIENT_ERRORS = (
    RuntimeError,
    serial.SerialException,
    OSError,
    json.JSONDecodeError,
    KeyError,
) + ((termios.error,) if termios else ())


def find_port():
    usb = settings()["usb"]
    found = [
        p.device
        for p in list_ports.comports()
        if (p.vid, p.pid) == (usb["vid"], usb["pid"]) and p.product == usb["product"]
    ]
    if len(found) != 1:
        raise RuntimeError(f"Expected one BluePill, found {len(found)}; specify a port")
    return found[0]


class Monitor:
    def __init__(self, port=None):
        self.port = serial.Serial(
            port or settings()["serial_port"] or find_port(),
            115200,
            timeout=2,
            write_timeout=3,
        )
        self._rx = bytearray()
        try:
            time.sleep(0.04)
            self.port.reset_input_buffer()
        except Exception:
            self.port.close()
            raise

    def close(self):
        self.port.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def command(self, text):
        self.port.write(text.encode("ascii") + b"\n")
        raw = self._readline()
        if not raw.endswith(b"\n"):
            raise RuntimeError(f"Timeout/truncated response to {text!r}: {raw!r}")
        result = raw.decode("ascii").strip()
        if result.startswith("ERR "):
            raise RuntimeError(result)
        return result

    def _readline(self):
        """Read available USB batches; retain binary bytes coalesced with a header."""
        deadline = time.monotonic() + (self.port.timeout or 2)
        while True:
            end = self._rx.find(b"\n")
            if end >= 0:
                result = bytes(self._rx[: end + 1])
                del self._rx[: end + 1]
                return result
            if len(self._rx) > 4096:
                raise RuntimeError("INVALID overlong monitor response")
            if time.monotonic() >= deadline:
                result = bytes(self._rx)
                self._rx.clear()
                return result
            chunk = self.port.read(max(1, min(4096, self.port.in_waiting)))
            if not chunk:
                result = bytes(self._rx)
                self._rx.clear()
                return result
            self._rx.extend(chunk)

    def _read_exact(self, count):
        take = min(count, len(self._rx))
        result = bytes(self._rx[:take])
        del self._rx[:take]
        if take < count:
            result += self.port.read(count - take)
        return result

    def info(self):
        return json.loads(self.command("INFO"))

    def capabilities(self):
        return json.loads(self.command("CAPS"))

    def stimulus_upload(self, levels, hz, mask=0x100, idle=0x100, mode=0, repeat=1):
        caps = self.capabilities()
        values = list(levels)
        if not values or len(values) > caps["tx_steps_max"]:
            raise ValueError("Pattern length exceeds firmware capability")
        if not 1 <= hz <= caps["tx_hz_max"] or mask <= 0 or mask & ~caps["tx_mask"]:
            raise ValueError("Unsupported rate or mask")
        if idle & ~mask or mode not in (0, 1) or not 1 <= repeat <= 64:
            raise ValueError("Invalid idle level or electrical mode")
        if any(not isinstance(v, int) or v < 0 or v & ~mask for v in values):
            raise ValueError("Pattern writes pins outside selected mask")
        if values[-1] != idle:
            raise ValueError("Final pattern entry must be idle")
        status = json.loads(
            self.command(f"TXCONFIG {hz} {mask} {idle} {mode} {repeat}")
        )
        for offset in range(0, len(values), 16):
            chunk = "".join(f"{v:04x}" for v in values[offset : offset + 16])
            status = json.loads(self.command(f"TXDATA {offset} {chunk}"))
            if status["loaded"] != min(offset + 16, len(values)):
                raise RuntimeError("Firmware did not accept complete stimulus chunk")
        return status

    def stimulus_start(self, job_id):
        return json.loads(self.command(f"TXSTART {job_id}"))

    def stimulus_arm(self, job_id, source=1, idle_ticks=1):
        return json.loads(self.command(f"TXARM {job_id} {source} {idle_ticks}"))

    def stimulus_status(self):
        return json.loads(self.command("TXSTATUS"))

    def stimulus_stop(self):
        return json.loads(self.command("TXSTOP"))

    def bridge(self, sources=0x401):
        return json.loads(self.command(f"BRIDGE {sources}"))

    def registers(self, addr, count=1):
        return json.loads(self.command(f"REG {addr:#x} {count}"))

    def capture_start(self, port="B", hz=100000, count=2048, mask=1):
        return json.loads(self.command(f"CAPTURE {port} {hz} {count} {mask}"))

    def capture_status(self):
        return json.loads(self.command("CAPSTATUS"))

    def capture_stream(
        self,
        port="B",
        hz=16000,
        count=16384,
        mask=1,
        on_start=None,
        timeout=None,
        cancelled=None,
    ):
        if count <= 0 or count > 1048576 or count % 1024:
            raise ValueError("Stream sample count must be 1024-aligned, <=1048576")
        initial = json.loads(self.command(f"CAPSTREAM {port} {hz} {count} {mask}"))
        acquisition = initial["id"]
        deadline = time.monotonic() + (
            timeout or count * initial["ticks"] / 72000000 + 4
        )
        data = bytearray()
        next_seq = 1
        last_poll = time.monotonic()
        max_poll_gap = max_service = 0.0
        try:
            if on_start:
                on_start()
            while time.monotonic() < deadline:
                now = time.monotonic()
                max_poll_gap = max(max_poll_gap, now - last_poll)
                last_poll = now
                if cancelled and cancelled():
                    raise InterruptedError(
                        "Đã dừng acquisition; GPIO stimulus được trả idle."
                    )
                status = self.capture_status()
                max_poll_gap = max(max_poll_gap, time.monotonic() - last_poll)
                if status["id"] != acquisition or status["lost"] or status["state"] > 2:
                    raise RuntimeError(
                        f"INVALID stream: {status}; host_max_poll_gap_ms={max_poll_gap*1000:.3f}; host_max_block_service_ms={max_service*1000:.3f}"
                    )
                ready = {status["ready0"], status["ready1"]} - {0}
                if next_seq in ready:
                    service_started = time.monotonic()
                    for offset in range(0, 1024, 512):
                        try:
                            header = self.command(
                                f"BLOCK {next_seq} {offset} 512"
                            ).split()
                        except RuntimeError as exc:
                            raise RuntimeError(
                                f"INVALID block transfer: {exc}; {self.capture_status()}"
                            ) from exc
                        if (
                            len(header) != 6
                            or header[0] != "BLOCK"
                            or list(map(int, header[1:5]))
                            != [acquisition, next_seq, offset, 512]
                        ):
                            raise RuntimeError(f"INVALID stream header: {header}")
                        raw = self._read_exact(1024)
                        if len(raw) != 1024 or zlib.crc32(raw) != int(header[5]):
                            raise RuntimeError("INVALID stream block length/CRC")
                        data.extend(raw)
                    ack = json.loads(self.command(f"ACKBLOCK {next_seq}"))
                    if ack["id"] != acquisition or ack["lost"] or ack["state"] > 2:
                        raise RuntimeError(f"INVALID stream after ACK: {ack}")
                    next_seq += 1
                    max_service = max(max_service, time.monotonic() - service_started)
                    continue
                if ready and min(ready) > next_seq:
                    raise RuntimeError("INVALID missing stream sequence")
                if status["state"] == 2:
                    if len(data) != count * 2 or status["produced"] != count:
                        raise RuntimeError("INVALID truncated stream")
                    status["host_stream"] = {
                        "max_poll_gap_ms": max_poll_gap * 1000,
                        "max_block_service_ms": max_service * 1000,
                        "half_buffer_budget_ms": 1024 * initial["ticks"] / 72000,
                    }
                    return status, list(struct.unpack("<" + "H" * count, data))
                time.sleep(0.001)
            raise RuntimeError("INVALID stream completion timeout")
        except Exception:
            try:
                self.command("STOP")
                self.stimulus_stop()
            except Exception:
                pass
            raise

    def capture_fetch(self, status):
        if status["state"] != 2:
            raise RuntimeError(f"Capture not completed: {status}")
        data = bytearray()
        for offset in range(0, status["count"], 512):
            count = min(512, status["count"] - offset)
            header = self.command(f"READ {offset} {count}").split()
            if (
                len(header) != 5
                or header[0] != "DATA"
                or list(map(int, header[1:4])) != [status["id"], offset, count]
            ):
                raise RuntimeError(f"Invalid data header: {header}")
            raw = self._read_exact(2 * count)
            if len(raw) != 2 * count or zlib.crc32(raw) != int(header[4]):
                raise RuntimeError("Capture truncated or CRC32 mismatch")
            data.extend(raw)
        return list(struct.unpack("<" + "H" * status["count"], data))

    def capture(self, port="B", hz=100000, count=2048, mask=1, timeout=None):
        initial = self.capture_start(port, hz, count, mask)
        deadline = time.monotonic() + (
            timeout or count * initial["ticks"] / 72000000 + 3
        )
        while time.monotonic() < deadline:
            status = self.capture_status()
            if status["state"] == 2:
                return status, self.capture_fetch(status)
            if status["state"] == 3:
                raise RuntimeError(f"DMA error: {status}")
            time.sleep(0.01)
        raise RuntimeError("Capture completion timeout")


def wait_monitor(running=None, timeout=8):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            with Monitor() as monitor:
                result = monitor.info()
                if running is None or result["running"] == int(running):
                    return result
        except TRANSIENT_ERRORS as exc:
            last = exc
        time.sleep(0.15)
    raise RuntimeError(f"Monitor not ready (running={running}): {last}")
