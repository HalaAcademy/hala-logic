import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

try:
    import termios
except ImportError:
    termios = None
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / folder) for folder in ("host", "tools/device")]
from elfcheck import inspect, ELFRejected
import decode
from client import wait_monitor


class ELFChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        target = ROOT / "build/student.elf"
        if not target.exists():
            try:
                from build import build
                build("student")
            except Exception as e:
                raise unittest.SkipTest(f"student.elf not found and cannot build: {e}")

    def setUp(self):
        self.path = ROOT / "build/student.elf"
        self.data = bytearray(self.path.read_bytes())
        with self.path.open("rb") as stream:
            elf = ELFFile(stream)
            self.vector = elf.get_section_by_name(".isr_vector")["sh_offset"]
            self.text = elf.get_section_by_name(".text")["sh_offset"]
            self.manifest = elf.get_section_by_name(".manifest")["sh_offset"]
            self.phoff = elf["e_phoff"]

    def rejected(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.elf"
            path.write_bytes(data)
            with self.assertRaises(ELFRejected):
                inspect(path)

    def test_valid_sealed_image(self):
        report, _ = inspect(self.path)
        self.assertEqual(report["sp"], 0x20005000)

    def test_corrupt_code_crc(self):
        self.data[self.text] ^= 1
        self.rejected(self.data)

    def test_forged_manifest(self):
        self.data[self.manifest + 32] ^= 1
        self.rejected(self.data)

    def test_load_lma_overlaps_monitor(self):
        struct.pack_into("<I", self.data, self.phoff + 12, 0x08000000)
        self.rejected(self.data)

    def test_load_vma_overlaps_monitor(self):
        struct.pack_into("<I", self.data, self.phoff + 8, 0x08000000)
        self.rejected(self.data)

    def test_initial_stack_overlaps_monitor(self):
        struct.pack_into("<I", self.data, self.vector, 0x20001000)
        self.rejected(self.data)

    def test_non_thumb_reset(self):
        (value,) = struct.unpack_from("<I", self.data, self.vector + 4)
        struct.pack_into("<I", self.data, self.vector + 4, value & ~1)
        self.rejected(self.data)

    def test_interrupt_vector_overlaps_monitor(self):
        struct.pack_into("<I", self.data, self.vector + 46 * 4, 0x08000101)
        self.rejected(self.data)

    def test_unsealed_manifest_rejected(self):
        self.data[self.manifest : self.manifest + 64] = bytes(64)
        self.rejected(self.data)


class Decoders(unittest.TestCase):
    def test_crc15_can_known_check(self):
        bits = [(b >> bit) & 1 for b in b"123456789" for bit in range(7, -1, -1)]
        self.assertEqual(decode.can_crc(bits), 0x059E)

    def test_lin_known_pid_checksum(self):
        self.assertEqual(decode.lin_pid(0x12), 0x92)
        self.assertEqual(decode.lin_checksum([0x34, 0x56], 0x92), 0xE2)

    def test_uart_literal_waveform(self):
        # Idle, start, LSB-first 0x55, stop, idle, all oversampled 10x.
        bits = [1] * 120 + [
            v for b in [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 1, 1] for v in [b] * 10
        ]
        self.assertEqual([f["value"] for f in decode.uart(bits, 96000, 9600)], [0x55])

    def test_uart_invalid_stop_rejected(self):
        bits = [1] * 20 + [0] * 120 + [1] * 20
        self.assertEqual(decode.uart(bits, 96000, 9600), [])

    def test_uart_partial_window_requires_sync(self):
        bits = [1] * 20 + [
            v for b in [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 1, 1] for v in [b] * 10
        ]
        self.assertEqual(decode.uart(bits, 96000, 9600), [])
        self.assertFalse(
            decode.uart(bits, 96000, 9600, require_idle=False)[0]["synchronized"]
        )

    def test_low_sample_rate_rejected(self):
        with self.assertRaises(ValueError):
            decode.can([1] * 100, 1000, 20000)
        with self.assertRaises(ValueError):
            decode.uart([1] * 100, 1000, 9600)


class HostReconnect(unittest.TestCase):
    @unittest.skipIf(termios is None, "termios chỉ có trên POSIX")
    def test_termios_hot_unplug_retries(self):
        monitor = MagicMock()
        monitor.__enter__.return_value.info.return_value = {"running": 1}
        with patch(
            "client.Monitor",
            side_effect=[termios.error(6, "Device not configured"), monitor],
        ), patch("client.time.sleep"):
            self.assertEqual(wait_monitor(True), {"running": 1})


if __name__ == "__main__":
    unittest.main()
