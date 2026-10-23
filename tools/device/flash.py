#!/usr/bin/env python3
"""Validate B, enter SWD Safe Boot, program B only, and compare all 24 KiB of A."""

import sys
from pathlib import Path

_PROJECT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(_PROJECT / folder) for folder in ("host", "tools/device", "tests/hardware")
]
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import struct
import tempfile
from config import settings
from elfcheck import inspect
from swd import ROOT, openocd, mailbox_commands, set_mode, tcl_path


def flash_student(elf, speed=None, stay_safe=False, report_dir=None):
    speed = settings()["swd_khz"] if speed is None else speed
    elf = Path(elf).resolve()
    # This MUST run before the first device command.
    validation, _ = inspect(elf)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    report_dir = Path(report_dir or ROOT / "build" / "reports" / f"flash-{stamp}")
    report_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bp-flash-") as directory:
        before = Path(directory) / "a-before.bin"
        after = Path(directory) / "a-after.bin"
        openocd(
            [
                "init",
                "reset halt",
                *mailbox_commands(True),
                f"dump_image {tcl_path(before)} 0x08000000 0x6000",
                "resume",
            ],
            speed,
            report_dir / "before.log",
        )
        resident = before.read_bytes()
        sp, reset = struct.unpack_from("<II", resident)
        if sp != 0x20003000 or not reset & 1 or not 0x08000000 <= reset < 0x08006000:
            raise RuntimeError(
                "A resident monitor is not installed; refusing to flash B"
            )
        openocd(
            [
                f"program {tcl_path(elf)} verify",
                f"dump_image {tcl_path(after)} 0x08000000 0x6000",
                *mailbox_commands(True),
                "reset run",
            ],
            speed,
            report_dir / "program.log",
        )
        after_bytes = after.read_bytes()
        a_sha = hashlib.sha256(resident).hexdigest()
        preserved = len(resident) == 24576 and resident == after_bytes
        report = {
            "student": validation,
            "a_bytes_compared": len(resident),
            "a_sha256_before": a_sha,
            "a_sha256_after": hashlib.sha256(after_bytes).hexdigest(),
            "resident_preserved": preserved,
            "speed_khz": speed,
            "released": False,
        }
        (report_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        if not preserved:
            raise RuntimeError(
                f"A FLASH CHANGED; B remains in Safe Boot. See {report_dir}"
            )
    if not stay_safe:
        set_mode(False, speed, report_dir / "release.log")
        report["released"] = True
        (report_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"B programmed and verified; all 24 KiB of A unchanged: {a_sha}", flush=True)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("elf", type=Path)
    parser.add_argument("--speed", type=int, default=None)
    parser.add_argument("--stay-safe", action="store_true")
    args = parser.parse_args()
    print(json.dumps(flash_student(args.elf, args.speed, args.stay_safe), indent=2))
