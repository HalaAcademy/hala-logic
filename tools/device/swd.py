"""Bounded OpenOCD operations. Uses SYSRESETREQ; never mass erase or option bytes."""

import sys
from pathlib import Path

_PROJECT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(_PROJECT / folder) for folder in ("host", "tools/device", "tests/hardware")
]
import argparse
from pathlib import Path
import subprocess
import tempfile
from config import PROJECT, path, tool, settings

ROOT = PROJECT
CONFIG = path("openocd_config")
MAILBOX = 0x20000200
MAGIC = 0x53414645
GUARD = 0xACBEB9BA


def tcl_path(path):
    value = Path(path).resolve().as_posix()
    if any(c in value for c in "{}\r\n"):
        raise ValueError("unsupported characters in OpenOCD file path")
    return "{" + value + "}"


def openocd(commands, speed=None, log=None):
    speed = settings()["swd_khz"] if speed is None else speed
    if not 1 <= speed <= 1000:
        raise ValueError("SWD speed must be 1..1000 kHz")
    with tempfile.TemporaryDirectory(prefix="bp-openocd-") as directory:
        script = Path(directory) / "run.cfg"
        script.write_text("\n".join(commands + ["shutdown"]) + "\n")
        result = subprocess.run(
            [
                tool("openocd"),
                "-f",
                str(CONFIG),
                "-c",
                f"adapter speed {speed}",
                "-f",
                str(script),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    output = result.stdout + result.stderr
    if log:
        Path(log).parent.mkdir(parents=True, exist_ok=True)
        Path(log).write_text(output)
    if result.returncode:
        raise RuntimeError(f"OpenOCD failed ({result.returncode}):\n{output}")
    return output


def mailbox_commands(safe):
    return [
        f"mww {MAILBOX:#x} {MAGIC:#x}",
        f"mww {MAILBOX+4:#x} {int(safe)}",
        f"mww {MAILBOX+8:#x} {GUARD:#x}",
    ]


def set_mode(safe, speed=None, log=None):
    return openocd(
        ["init", "reset halt", *mailbox_commands(safe), "resume"], speed, log
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["safe", "run"])
    parser.add_argument("--speed", type=int, default=None)
    args = parser.parse_args()
    print(set_mode(args.mode == "safe", args.speed))
