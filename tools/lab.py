#!/usr/bin/env python3
"""HALA Academy — công cụ phát triển STM32 và khởi động HALA Logic, lệnh và hướng dẫn bằng tiếng Việt."""

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(PROJECT / folder) for folder in ("host", "tools/device", "tests/hardware")
]
from config import catalog, path, settings, tool


def doctor():
    failed = False
    print("HALA Academy · Kiểm tra môi trường (chưa truy cập board)")
    print("Python:", sys.version.split()[0])
    for name in ["gcc", "objcopy", "gdb", "openocd"]:
        exe = tool(name)
        present = shutil.which(exe)
        print(("OK" if present else "THIẾU") + f" · {name}: {exe}")
        failed |= not bool(present)
    for name in ["serial", "elftools", "matplotlib", "tkinter"]:
        try:
            found = importlib.util.find_spec(name) is not None
            if found and name == "tkinter":
                __import__(name)
        except (ImportError, ModuleNotFoundError):
            found = False
        print(("OK" if found else "THIẾU") + f" · Python module: {name}")
        failed |= not found
    print("OpenOCD config:", path("openocd_config"))
    print("Tốc độ SWD:", settings()["swd_khz"], "kHz")
    return int(failed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Kiểm tra công cụ/dependency, không truy cập board")
    sub.add_parser("examples", help="Liệt kê bài mẫu, hướng truyền và file ELF")
    b = sub.add_parser("build", help="Biên dịch monitor và ví dụ; không nạp board")
    b.add_argument(
        "target",
        nargs="?",
        default="all",
        help="all, monitor hoặc key bài trong examples",
    )
    b.add_argument("--output", type=Path, help="Thư mục xuất ELF/BIN")
    a = sub.add_parser("install-monitor", help="Cài monitor bằng OpenOCD qua SWD")
    a.add_argument(
        "--elf", type=Path, help="File monitor.elf; mặc định theo output_dir"
    )
    f = sub.add_parser(
        "flash", help="Nạp ví dụ bằng OpenOCD, xác minh monitor được giữ nguyên"
    )
    f.add_argument("example", help="Key ví dụ hoặc đường dẫn ELF ứng dụng")
    f.add_argument(
        "--stay-safe", action="store_true", help="Giữ ứng dụng dừng sau khi nạp"
    )
    g = sub.add_parser("gui", help="Mở giao diện sóng")
    g.add_argument(
        "--open", type=Path, help="Mở capture JSON ngoại tuyến; cần BIN cùng tên"
    )
    sub.add_parser("info", help="Đọc trạng thái USB của monitor")
    m = sub.add_parser("mode", help="Safe Boot hoặc chạy ứng dụng")
    m.add_argument("value", choices=["safe", "run"])
    sub.add_parser("debug", help="Mở OpenOCD GDB server; Ctrl+C để đóng")
    sub.add_parser("test", help="Chạy unit test host; không truy cập board")
    sub.add_parser("gdb-test", help="Test GDB các ví dụ đã triển khai; tác động board")
    suite = sub.add_parser(
        "hardware-test", help="Chạy tuần tự bộ test phần cứng đã triển khai"
    )
    suite.add_argument(
        "--steps",
        nargs="+",
        help="Tên module trong run_suite.py; bỏ trống để chạy toàn bộ",
    )
    args = parser.parse_args()
    if args.command == "doctor":
        return doctor()
    if args.command == "examples":
        for item in catalog():
            print(
                f"{item['key']:22} {item['direction']:5} {item['baud']:6} bit/s · {item['image']}.elf · {item['title']}"
            )
        return 0
    if args.command == "build":
        from build import build

        print("Đã xuất:", build(args.target, args.output))
        return 0
    if args.command == "test":
        return subprocess.call(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                str(PROJECT / "tests/unit"),
                "-v",
            ],
            cwd=PROJECT,
        )
    if args.command in ("gui", "hardware-test", "gdb-test"):
        module = {
            "gui": "gui",
            "hardware-test": "run_suite",
            "gdb-test": "gdb_examples_acceptance",
        }[args.command]
        folder = "host" if module == "gui" else "tests/hardware"
        command = [sys.executable, str(PROJECT / folder / f"{module}.py")]
        if args.command == "gui" and args.open:
            command += ["--open", str(args.open.resolve())]
        if args.command == "hardware-test" and args.steps:
            command += ["--steps", *args.steps]
        return subprocess.call(command, cwd=PROJECT)
    from swd import openocd, set_mode, tcl_path

    if args.command == "debug":
        return subprocess.call(
            [
                tool("openocd"),
                "-f",
                str(path("openocd_config")),
                "-c",
                f"adapter speed {settings()['swd_khz']}",
                "-c",
                f"gdb_port {settings()['gdb_endpoint'].rsplit(':',1)[1]}",
            ]
        )
    if args.command == "mode":
        print(set_mode(args.value == "safe", settings()["swd_khz"]))
        return 0
    if args.command == "info":
        from client import Monitor

        with Monitor() as monitor:
            print(json.dumps(monitor.info(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "flash":
        from flash import flash_student

        item = next((e for e in catalog() if e["key"] == args.example), None)
        elf = (
            path("output_dir") / (item["image"] + ".elf")
            if item
            else Path(args.example)
        )
        flash_student(elf, settings()["swd_khz"], args.stay_safe)
        return 0
    if args.command == "install-monitor":
        from elftools.elf.elffile import ELFFile

        elf = (args.elf or path("output_dir") / "monitor.elf").resolve()
        # Kiểm vùng nạp trước lệnh SWD đầu tiên; không cho nạp nhầm B thành A.
        with elf.open("rb") as stream:
            image = ELFFile(stream)
            loads = [
                s
                for s in image.iter_segments()
                if s["p_type"] == "PT_LOAD" and s["p_filesz"]
            ]
            if (
                image["e_machine"] != "EM_ARM"
                or not loads
                or not any(s["p_paddr"] == 0x08000000 for s in loads)
                or any(
                    not 0x08000000
                    <= s["p_paddr"]
                    < s["p_paddr"] + s["p_filesz"]
                    <= 0x08006000
                    for s in loads
                )
            ):
                raise ValueError(
                    "ELF monitor phải là ARM, bắt đầu 0x08000000 và nằm trong vùng monitor 24 KiB"
                )
        print(
            "Cài monitor: thay vùng monitor, ứng dụng được nạp riêng ở bước tiếp theo."
        )
        print(openocd([f"program {tcl_path(elf)} verify reset"]))
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(
            f"Lỗi: {exc}\nXem docs/KHAC_PHUC_LOI.md và chạy: python tools/lab.py doctor",
            file=sys.stderr,
        )
        raise SystemExit(1)
