import sys
from pathlib import Path
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "host"))
import stimulus, decode, measurements
import canfd
import flexray
from client import Monitor


class IndependentVectors(unittest.TestCase):
    def test_long_division_crc_known(self):
        bits = [(b >> i) & 1 for b in b"123456789" for i in range(7, -1, -1)]
        self.assertEqual(stimulus.polynomial_crc(bits, 15, 0x4599), 0x059E)

    def test_can_crc_literal_hardware_baseline(self):
        levels = stimulus.can(0x123, bytes.fromhex("dead"))
        physical = [(x >> 10) & 1 for x in levels for _ in range(16)]
        f = decode.can(physical, 16000, 1000)[0]
        self.assertEqual(
            (f["id"], f["data"], f["crc"], f["ack"]), (0x123, "dead", 0x0B6E, False)
        )

    def test_lin_literal_golden(self):
        levels = stimulus.lin(0x12, bytes.fromhex("3456"))
        physical = [(x >> 10) & 1 for x in levels for _ in range(16)]
        f = decode.lin(physical, 16000, 1000)[0]
        self.assertEqual((f["pid"], f["checksum"], f["data"]), (0x92, 0xE2, "3456"))

    def test_uart_frame_exact_literal(self):
        self.assertEqual(
            stimulus.uart(b"\x55", idle_bits=0)[:10],
            [0, 256, 0, 256, 0, 256, 0, 256, 0, 256],
        )


class Measurements(unittest.TestCase):
    def test_pwm_known_period_duty(self):
        s = ([0] * 7 + [1] * 3) * 10
        r = measurements.channel(s, 1000)
        self.assertAlmostEqual(r["frequency_hz"], 100)
        self.assertAlmostEqual(r["duty"]["mean"], 30)
        self.assertAlmostEqual(r["high_width"]["mean"], 0.003)

    def test_clipped_constant_has_no_frequency_or_pulse(self):
        r = measurements.channel([1] * 20, 1000)
        self.assertNotIn("frequency_hz", r)
        self.assertEqual(r["high_width"]["count"], 0)

    def test_one_sample_glitch_kept(self):
        r = measurements.channel([0, 0, 1, 0, 0], 1000)
        self.assertEqual(r["edges"], 2)
        self.assertAlmostEqual(r["high_width"]["min"], 0.001)

    def test_reverse_cursor(self):
        r = measurements.cursors(10, 0, 1000)
        self.assertAlmostEqual(r["delta_s"], -0.01)


class ClassicalCANModes(unittest.TestCase):
    def test_base_extended_data_remote_all_dlc(self):
        for extended in (False, True):
            for remote in (False, True):
                for dlc in range(9):
                    with self.subTest(extended=extended, remote=remote, dlc=dlc):
                        identifier = 0x12345678 if extended else 0x123
                        payload = b"" if remote else bytes(range(dlc))
                        wire = stimulus.can(
                            identifier,
                            payload,
                            extended=extended,
                            remote=remote,
                            dlc=dlc,
                        )
                        frames = decode.can(
                            [(v >> 10) & 1 for v in wire for _ in range(16)],
                            16000,
                            1000,
                        )
                        self.assertEqual(len(frames), 1)
                        f = frames[0]
                        self.assertEqual(
                            (f["id"], f["extended"], f["remote"], f["dlc"], f["data"]),
                            (identifier, extended, remote, dlc, payload.hex()),
                        )
                        self.assertTrue(f["crc_ok"])
                        self.assertFalse(f["ack"])

    def test_remote_dlc_does_not_generate_data_field(self):
        for extended in (False, True):
            wire = stimulus.can(0x123, extended=extended, remote=True, dlc=8)
            # Destuff exactly SOF/header/CRC: remote payload length is zero.
            expected = 39 if extended else 19
            raw = []
            last = None
            run = 0
            physical = iter((v >> 10) & 1 for v in wire[12:])
            while len(raw) < expected + 15:
                b = next(physical)
                if run == 5:
                    self.assertNotEqual(b, last)
                    last = b
                    run = 1
                    continue
                raw.append(b)
                run = run + 1 if b == last else 1
                last = b
            self.assertEqual(raw[13], int(extended))
            self.assertEqual(raw[32 if extended else 12], 1)
            self.assertEqual(raw[expected - 4 : expected], [1, 0, 0, 0])

    def test_invalid_format_lengths_rejected(self):
        for options in [
            dict(identifier=0x800),
            dict(identifier=0x20000000, extended=True),
            dict(identifier=-1),
            dict(identifier=1, data=b"\x00", remote=True),
            dict(identifier=1, remote=True, dlc=9),
            dict(identifier=1, data=b"\x00", dlc=0),
        ]:
            with self.assertRaises(ValueError):
                stimulus.can(**options)


class ISOFDVectors(unittest.TestCase):
    def test_extended_all_dlc_and_brs(self):
        for brs in (False, True):
            for length in canfd.LENGTHS:
                with self.subTest(brs=brs, length=length):
                    payload = bytes(range(length))
                    wire, meta = canfd.frame(
                        0x12345678, payload, extended=True, brs=brs, esi=True
                    )
                    frames = canfd.decode(
                        [(v >> 10) & 1 for v in wire for _ in range(4)], 16000
                    )
                    self.assertEqual(len(frames), 1)
                    f = frames[0]
                    self.assertEqual(
                        (f["id"], f["extended"], f["data"], f["esi"], f["brs"]),
                        (0x12345678, True, payload.hex(), True, brs),
                    )
                    self.assertTrue(
                        f["crc_ok"] and f["stuff_count_ok"] and f["format_ok"]
                    )

    def test_extended_identifier_bounds(self):
        for ident in (0, 0x1FFFFFFF):
            wire, _ = canfd.frame(ident, b"", extended=True)
            f = canfd.decode([(v >> 10) & 1 for v in wire for _ in range(4)], 16000)[0]
            self.assertEqual(f["id"], ident)
        for ident in (-1, 0x20000000):
            with self.assertRaises(ValueError):
                canfd.frame(ident, extended=True)

    def test_all_dlc_brs_crc_models(self):
        for brs in (False, True):
            for length in canfd.LENGTHS:
                with self.subTest(brs=brs, length=length):
                    payload = bytes(range(length))
                    schedule, expected = canfd.frame(0x123, payload, brs=brs)
                    raw = [(v >> 10) & 1 for v in schedule for _ in range(8)]
                    frames = canfd.decode(raw, 32000)
                    self.assertEqual(len(frames), 1)
                    frame = frames[0]
                    self.assertEqual(frame["data"], payload.hex())
                    self.assertEqual(frame["crc_bits"], 17 if length <= 16 else 21)
                    self.assertTrue(
                        frame["crc_ok"]
                        and frame["stuff_count_ok"]
                        and frame["format_ok"]
                    )

    def test_corrupt_crc_and_count_are_distinct(self):
        for option, flag in [
            ("corrupt_crc", "crc_ok"),
            ("corrupt_count", "stuff_count_ok"),
        ]:
            schedule, _ = canfd.frame(0x5AA, b"\xff" * 8, **{option: True})
            frame = canfd.decode(
                [(v >> 10) & 1 for v in schedule for _ in range(8)], 32000
            )[0]
            self.assertFalse(frame[flag])

    def test_invalid_lengths_and_id(self):
        for length in [9, 10, 11, 15, 17, 63, 65]:
            with self.assertRaises(ValueError):
                canfd.frame(0x123, bytes(length))
        with self.assertRaises(ValueError):
            canfd.frame(0x800, b"")


class StimulusValidation(unittest.TestCase):
    def setUp(self):
        self.m = Monitor.__new__(Monitor)
        self.m.capabilities = Mock(
            return_value={"tx_steps_max": 2048, "tx_hz_max": 100000, "tx_mask": 0x500}
        )
        self.m.command = Mock()

    def test_mask_and_final_idle_validate_before_mutating_firmware(self):
        for values in ([512, 256], [256, 0], [-1, 256]):
            with self.assertRaises(ValueError):
                self.m.stimulus_upload(values, 1000)
        self.m.command.assert_not_called()

    def test_repeat_and_length_limits(self):
        with self.assertRaises(ValueError):
            self.m.stimulus_upload([256], 1000, repeat=0)
        with self.assertRaises(ValueError):
            self.m.stimulus_upload([256] * 2049, 1000)
        self.m.command.assert_not_called()


class USBBufferedFraming(unittest.TestCase):
    class Port:
        timeout = 0.1

        def __init__(self, chunks):
            self.chunks = list(chunks)
            self.writes = []

        @property
        def in_waiting(self):
            return len(self.chunks[0]) if self.chunks else 0

        def read(self, n):
            if not self.chunks:
                return b""
            chunk = self.chunks[0][:n]
            self.chunks[0] = self.chunks[0][n:]
            if not self.chunks[0]:
                self.chunks.pop(0)
            return chunk

        def write(self, data):
            self.writes.append(data)

    def monitor(self, chunks):
        m = Monitor.__new__(Monitor)
        m.port = self.Port(chunks)
        m._rx = bytearray()
        return m

    def test_split_line_and_coalesced_binary_payload(self):
        m = self.monitor([b"DA", b"TA 1 0 4 123\r", b"\n\x00\x0a\xff\x01"])
        self.assertEqual(m.command("READ 0 4"), "DATA 1 0 4 123")
        self.assertEqual(m._read_exact(4), b"\x00\x0a\xff\x01")
        self.assertEqual(m.port.writes, [b"READ 0 4\n"])

    def test_read_exact_preserves_following_reply(self):
        m = self.monitor([])
        m._rx.extend(b"\x01\x02PONG\r\n")
        self.assertEqual(m._read_exact(2), b"\x01\x02")
        self.assertEqual(m.command("PING"), "PONG")

    def test_truncated_line_is_rejected(self):
        m = self.monitor([b"PONG"])
        with self.assertRaisesRegex(RuntimeError, "truncated"):
            m.command("PING")


class FlexRayFrames(unittest.TestCase):
    def test_static_frame_lengths_and_channels(self):
        for ch in ("A", "B"):
            for length in (0, 2, 16, 254):
                schedule, expected = flexray.frame(
                    0x123, bytes(range(length)), cycle=63, channel=ch
                )
                raw = [(v >> 10) & 1 for v in schedule for _ in range(16)]
                frame = flexray.decode(raw, 16000, channel=ch)[0]
                self.assertEqual(frame["data"], bytes(range(length)).hex())
                self.assertEqual(frame["cycle"], 63)
                self.assertTrue(
                    frame["header_crc_ok"]
                    and frame["frame_crc_ok"]
                    and frame["format_ok"]
                )

    def test_channel_seed_mismatch(self):
        schedule, _ = flexray.frame(1, b"\x00\xff", channel="B")
        frame = flexray.decode(
            [(v >> 10) & 1 for v in schedule for _ in range(16)], 16000, channel="A"
        )[0]
        self.assertTrue(frame["header_crc_ok"])
        self.assertFalse(frame["frame_crc_ok"])

    def test_invalid_payload_and_id(self):
        with self.assertRaises(ValueError):
            flexray.frame(0, b"")
        with self.assertRaises(ValueError):
            flexray.frame(1, b"\x00")
        with self.assertRaises(ValueError):
            flexray.frame(1, bytes(256))


if __name__ == "__main__":
    unittest.main()
