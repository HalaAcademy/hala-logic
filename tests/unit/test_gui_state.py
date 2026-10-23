"""Kiểm trạng thái hiển thị không cần Tk window hay USB."""
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'host'))
from gui import App, CURSOR_HINT
from config import settings
ROOT=Path(__file__).resolve().parents[2]


class Value:
    def __init__(self, value=None):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class GUIStateChecks(unittest.TestCase):
    def app(self):
        app = App.__new__(App)
        for key in ('protocol', 'identifier', 'payload', 'can_extended', 'can_remote',
                    'sample_hz', 'sample_count', 'cursor_text', 'gpio_port', 'mask',
                    'decode_pin', 'message', 'capture_mode', 'baud', 'data_baud', 'fr_channel'):
            setattr(app, key, Value('0'))
        for key in ('root', 'packet_table', 'packet_text', 'measure_table',
                    'result_text', 'draw', 'extra_options'):
            setattr(app, key, MagicMock())
        app.baud.set('1000')
        return app

    def test_switch_from_flexray_to_gpio_restores_capture_defaults(self):
        app = self.app()
        app.protocol.set('FlexRay')
        app.preset()
        self.assertEqual(app.sample_count.get(), '98304')
        app.protocol.set('GPIO')
        app.preset()
        cfg = settings()['capture']
        self.assertEqual(app.sample_hz.get(), str(cfg['sample_hz']))
        self.assertEqual(app.sample_count.get(), str(cfg['sample_count']))

    def test_open_new_gpio_capture_clears_previous_protocol_and_cursor(self):
        app = self.app()
        app.protocol.set('CAN FD')
        app.cursors = [1, 50]
        app.cursor_text.set('Δt cũ')
        capture = Path(__file__).resolve().parents[2] / 'examples/captures/pwm.json'
        app.load(capture)
        self.assertEqual(app.protocol.get(), 'GPIO')
        self.assertEqual(app.cursors, [])
        self.assertEqual(app.cursor_text.get(), CURSOR_HINT)
        self.assertEqual(app.sample_hz.get(), '32000')
        self.assertEqual(app.sample_count.get(), '8192')
        self.assertEqual(app.saved, capture)
        app.draw.assert_called_once()

    def test_third_cursor_click_starts_new_measurement_without_old_delta(self):
        app = self.app()
        app.samples = [0] * 100
        app.view = (0, 100)
        app.cursors = [10, 20]
        app.cursor_text.set('Δt cũ')
        app.canvas = MagicMock()
        app.canvas.winfo_width.return_value = 1095
        app.cursor(SimpleNamespace(x=570))
        self.assertEqual(app.cursors, [50])
        self.assertIn('mẫu 50', app.cursor_text.get())
        self.assertNotIn('cũ', app.cursor_text.get())

    def test_first_packet_keeps_full_long_frame_in_view(self):
        app = self.app()
        app.samples = [0] * 98304
        app.status = {'ticks': 4500}
        app.decoded = [{'sample': 2000, 'end_sample': 44000}]
        app.first_packet()
        self.assertLessEqual(app.view[0], 2000)
        self.assertGreater(app.view[1], 44000)

    def test_load_restores_baud_and_burst_mode_from_metadata(self):
        import json
        import tempfile
        app = self.app()
        capture = ROOT / 'examples/captures/pwm.json'
        metadata = json.loads(capture.read_text())
        metadata['registers_after_capture']['baud'] = 9600
        metadata['capture']['stream'] = 0
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'capture.json'
            path.write_text(json.dumps(metadata))
            path.with_suffix('.bin').write_bytes(capture.with_suffix('.bin').read_bytes())
            app.load(path)
            self.assertEqual(app.baud.get(), '9600')
            self.assertEqual(app.capture_mode.get(), 'Burst')
