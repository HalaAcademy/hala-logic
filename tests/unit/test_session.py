"""Các ranh giới thu/phát độc lập với firmware ví dụ, không truy cập board."""

from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "host"))
from session import Capture, Signal, acquire


class SessionChecks(unittest.TestCase):
    def test_low_rate_rejected_before_usb(self):
        with patch("session.Monitor") as usb:
            with self.assertRaises(ValueError):
                acquire(Capture(protocol="UART", baud=9600, hz=32000))
            usb.assert_not_called()

    def test_unknown_gpio_port_rejected(self):
        with self.assertRaises(ValueError):
            Capture(port="").validate()

    def test_gpio_mask_does_not_require_decode_pin(self):
        Capture(protocol="GPIO", mask=2, bit=0).validate()

    def test_lin_accepts_id_outside_example_table(self):
        levels, rate, _ = Signal(identifier=0x31, data=b"\x01\x02\x03").encode(
            Capture(protocol="LIN", baud=500)
        )
        self.assertTrue(levels)
        self.assertEqual(rate, 8000)

    def test_fd_unsupported_brs_ratio_rejected(self):
        with self.assertRaises(ValueError):
            Signal(data=b"", brs=True).encode(
                Capture(protocol="CAN FD", baud=500, data_baud=2000)
            )

    def test_tx_stops_on_stream_failure(self):
        monitor = MagicMock()
        monitor.stimulus_upload.return_value = {"id": 7}
        monitor.capture_stream.side_effect = RuntimeError("USB disconnected")
        with patch("session.Monitor") as cls:
            cls.return_value.__enter__.return_value = monitor
            with self.assertRaisesRegex(RuntimeError, "USB disconnected"):
                acquire(Capture(protocol="UART"), signal=Signal(data=b"A"))
        monitor.stimulus_stop.assert_called_once()
