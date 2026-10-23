"""Bind tested firmware files to readback from the actual MCU (SWD, read-only)."""

import sys
from pathlib import Path

_PROJECT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(_PROJECT / folder) for folder in ("host", "tools/device", "tests/hardware")
]
import hashlib
import json
from pathlib import Path
from swd import ROOT, openocd, tcl_path
from client import wait_monitor


def bind_firmware(directory, speed=100):
    directory = Path(directory)
    images = {
        "monitor": (0x08000000, ROOT / "build/monitor.bin"),
        "student": (0x08006000, ROOT / "build/student.bin"),
    }
    commands = ["init", "reset halt"]
    for name, (address, path) in images.items():
        commands.append(
            f'dump_image {tcl_path(directory/(name+"-readback.bin"))} '
            f"{address:#x} {len(path.read_bytes()):#x}"
        )
    commands.append("resume")
    openocd(commands, speed, directory / "firmware-binding.log")
    result = {}
    for name, (_, path) in images.items():
        expected = path.read_bytes()
        actual = (directory / (name + "-readback.bin")).read_bytes()
        if actual != expected:
            raise RuntimeError(f"{name} target readback does not match current build")
        result[name] = {
            "bytes": len(actual),
            "bin_sha256": hashlib.sha256(actual).hexdigest(),
            "elf_sha256": hashlib.sha256(
                path.with_suffix(".elf").read_bytes()
            ).hexdigest(),
            "target_readback_matches": True,
        }
    result["monitor_info_after"] = wait_monitor(True)
    (directory / "firmware-binding.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    return result
