"""Biên dịch bằng subprocess, không cần Make/bash trên Windows."""

import sys
from pathlib import Path

_PROJECT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(_PROJECT / folder) for folder in ("host", "tools/device", "tests/hardware")
]
from pathlib import Path
import subprocess
import sys
from config import PROJECT, catalog, path, tool
from elfcheck import inspect

COMMON = [
    "-mcpu=cortex-m3",
    "-mthumb",
    "-Og",
    "-g3",
    "-Wall",
    "-Wextra",
    "-Werror",
    "-ffreestanding",
    "-fno-builtin",
    "-ffunction-sections",
    "-fdata-sections",
]
LINK = ["-nostdlib", "-Wl,--gc-sections,-z,max-page-size=0x400"]


def build(target="all", output=None):
    output = Path(output or path("output_dir")).resolve()
    output.mkdir(parents=True, exist_ok=True)
    project = PROJECT
    entries = catalog()
    targets = (
        ["monitor"] + [item["image"] for item in entries]
        if target == "all"
        else [target]
    )
    for image in targets:
        entry = next(
            (
                item
                for item in entries
                if item["image"] == image or item["key"] == image
            ),
            None,
        )
        if image != "monitor" and entry is None:
            raise ValueError(f"Không có bài mẫu: {image}")
        if entry:
            image = entry["image"]
        raw = output / (image + (".elf" if image == "monitor" else ".raw.elf"))
        if image == "monitor":
            sources = [
                "firmware/monitor/startup.c",
                "firmware/monitor/runtime.c",
                "firmware/monitor/protocol.c",
                "firmware/monitor/capture.c",
                "firmware/monitor/stimulus.c",
                "firmware/platform/stm32f103/board.c",
                "firmware/platform/stm32f103/usb_cdc.c",
            ]
            extra = [
                "-DRESIDENT_MONITOR",
                "-Ifirmware/platform/stm32f103",
                "-Ifirmware/monitor",
            ]
            linker = "firmware/monitor/linker.ld"
        else:
            sources = ["examples/common/startup.c", entry["source"]]
            extra = ["-Iexamples/common"]
            linker = "examples/common/linker.ld"
        command = [
            tool("gcc"),
            *COMMON,
            *extra,
            *LINK,
            "-T",
            linker,
            *sources,
            "-o",
            str(raw),
        ]
        print("Biên dịch:", image, flush=True)
        subprocess.run(command, cwd=project, check=True)
        sealed = output / (image + ".elf")
        if image != "monitor":
            subprocess.run(
                [
                    sys.executable,
                    str(project / "tools/device/elfcheck.py"),
                    str(raw),
                    "--seal",
                    str(sealed),
                ],
                check=True,
            )
            inspect(sealed)
        subprocess.run(
            [
                tool("objcopy"),
                "-O",
                "binary",
                str(sealed),
                str(output / (image + ".bin")),
            ],
            check=True,
        )
        if image != "monitor":
            raw.unlink()
    return output
