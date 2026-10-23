"""Kiểm các ranh giới cấu hình và tính tương thích Windows, không truy cập board."""

import builtins
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "host"))
import client
from config import merge, settings


class ConfigurationChecks(unittest.TestCase):
    def test_nested_override_keeps_other_tools(self):
        value = merge(
            {"tools": {"gcc": "gcc", "gdb": "gdb"}}, {"tools": {"gdb": "gdb-multiarch"}}
        )
        self.assertEqual(value["tools"], {"gcc": "gcc", "gdb": "gdb-multiarch"})

    def test_unknown_override_rejected(self):
        with self.assertRaises(ValueError):
            merge({"swd_khz": 50}, {"swd_speed_typo": 10})

    def test_wrong_pin_mapping_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "local.json"
            config.write_text(json.dumps({"gpio": {"device_tx": 1}}))
            with patch.dict(os.environ, {"HALA_CONFIG": str(config)}):
                with self.assertRaisesRegex(ValueError, "ABI"):
                    settings()

    def test_import_without_termios(self):
        original = builtins.__import__

        def windows_import(name, *args, **kwargs):
            if name == "termios":
                raise ImportError("Windows: no termios")
            return original(name, *args, **kwargs)

        spec = importlib.util.spec_from_file_location(
            "windows_client_probe", ROOT / "host/client.py"
        )
        module = importlib.util.module_from_spec(spec)
        with patch("builtins.__import__", side_effect=windows_import):
            spec.loader.exec_module(module)
        self.assertIsNone(module.termios)
        self.assertIn(OSError, module.TRANSIENT_ERRORS)

    def test_explicit_configured_port_skips_discovery(self):
        config = settings()
        config["serial_port"] = "COM77"
        with patch("client.settings", return_value=config), patch(
            "client.serial.Serial"
        ) as serial, patch("client.find_port") as find, patch("client.time.sleep"):
            monitor = client.Monitor()
            monitor.close()
        self.assertEqual(serial.call_args.args[0], "COM77")
        find.assert_not_called()
