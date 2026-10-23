#!/usr/bin/env python3
"""USB logic analyzer CLI. Firmware programming is exclusively tools/device/flash.py + SWD."""

import argparse
import json
from client import Monitor
import decode
import canfd, flexray
from export import export_capture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", help="serial device; defaults to USB autodetection")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("info")
    mode = sub.add_parser("mode")
    mode.add_argument("value", choices=["SAFE", "RUN"])
    reg = sub.add_parser("regs")
    reg.add_argument("address", type=lambda s: int(s, 0))
    reg.add_argument("count", nargs="?", type=int, default=1)
    cap = sub.add_parser("capture")
    cap.add_argument("--gpio", choices=["A", "B", "C"], default="B")
    cap.add_argument("--hz", type=int, default=100000)
    cap.add_argument("--samples", type=int, default=2048)
    cap.add_argument("--mask", type=lambda s: int(s, 0), default=1)
    cap.add_argument("--bit", type=int, default=0)
    cap.add_argument("--decode", choices=["uart", "lin", "can", "canfd", "flexray"])
    cap.add_argument("--baud", type=int, default=9600)
    cap.add_argument("--data-baud", type=int, default=2000)
    cap.add_argument("--channel", choices=["A", "B"], default="A")
    cap.add_argument("--stream", action="store_true")
    cap.add_argument("--lin-bytes", type=int, default=2)
    cap.add_argument(
        "--uart-unsynced",
        action="store_true",
        help="allow UART phase guesses before a 10-bit idle gap",
    )
    cap.add_argument("--output", default="build/capture")
    args = parser.parse_args()
    with Monitor(args.device) as monitor:
        if args.action == "info":
            result = monitor.info()
        elif args.action == "mode":
            result = monitor.command("MODE " + args.value)
        elif args.action == "regs":
            result = monitor.registers(args.address, args.count)
        else:
            info = monitor.info()
            method = monitor.capture_stream if args.stream else monitor.capture
            status, samples = method(args.gpio, args.hz, args.samples, args.mask)
            registers = {
                "RCC_CFGR": monitor.registers(0x40021004)[0],
                "GPIO": monitor.registers(0x40010800 + 0x400 * status["port"], 4),
                "DMA_CPAR_CMAR": monitor.registers(0x40020024, 2),
            }
            decoded = []
            if args.decode:
                decoder = (
                    canfd.decode
                    if args.decode == "canfd"
                    else (
                        flexray.decode
                        if args.decode == "flexray"
                        else getattr(decode, args.decode)
                    )
                )
                options = (
                    {"data_length": args.lin_bytes} if args.decode == "lin" else {}
                )
                if args.decode == "uart":
                    options["require_idle"] = not args.uart_unsynced
                if args.decode == "canfd":
                    options["data_rate"] = args.data_baud
                if args.decode == "flexray":
                    options["channel"] = args.channel
                decoded = decoder(
                    decode.levels(samples, args.bit),
                    72000000 / status["ticks"],
                    args.baud,
                    **options
                )
            result = export_capture(
                args.output, status, samples, decoded, info, registers
            )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
