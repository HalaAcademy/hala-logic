#!/usr/bin/env python3
"""Small real-device Tk host. CLI codecs/client are the same backend.

Run with --open <capture.json> for offline raw viewing. No fake telemetry or
protocol PASS inferred merely from a valid decoder result.
"""

import argparse
import hashlib
import json
from pathlib import Path
import queue
import struct
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import webbrowser
from config import settings, PROJECT
from client import Monitor
from serial.tools import list_ports
from session import Capture, Signal, acquire
import measurements

CURSOR_HINT = "Bấm trên sóng để đặt con trỏ 1/2; +/− zoom quanh vùng đang xem."


class App:
    def __init__(self, root, open_path=None):
        self.root = root
        root.title("HALA Logic · HALA Academy")
        root.geometry("1180x800")
        root.minsize(1080, 720)
        self.events = queue.Queue()
        self.busy = False
        self.samples = []
        self.status = {}
        self.decoded = []
        self.saved = None
        self.cursors = []
        self.view = (0, 1)
        self.cancel = threading.Event()
        self.protocol = tk.StringVar(value="GPIO")
        self.baud = tk.StringVar(value="1000")
        self.identifier = tk.StringVar(value="0x123")
        self.payload = tk.StringVar(value="48 45 4C 4C 4F")
        self.fd_brs = tk.BooleanVar(value=True)
        self.fr_channel = tk.StringVar(value="A")
        self.fr_cycle = tk.StringVar(value="0")
        self.can_extended = tk.BooleanVar(value=False)
        self.can_remote = tk.BooleanVar(value=False)
        self.can_dlc = tk.StringVar(value="8")
        self.action_buttons = []
        self.message = tk.StringVar(
            value="Chọn cổng COM/USB, kết nối rồi cấu hình thu hoặc gửi tín hiệu."
        )
        self.device = tk.StringVar(value="Tự động")
        self.usb_info = tk.StringVar(value="Chưa kết nối USB")
        connection = ttk.LabelFrame(root, text="Kết nối thiết bị", padding=7)
        connection.pack(fill="x", padx=10, pady=8)
        ttk.Label(connection, text="COM / USB").pack(side="left")
        self.port_choice = ttk.Combobox(connection, textvariable=self.device, width=31)
        self.port_choice.pack(side="left", padx=6)
        ttk.Button(connection, text="Làm mới", command=self.refresh_devices).pack(
            side="left", padx=3
        )
        button = ttk.Button(connection, text="Kết nối", command=self.connect)
        button.pack(side="left", padx=3)
        self.action_buttons.append(button)
        ttk.Label(connection, textvariable=self.usb_info, wraplength=400).pack(
            side="left", padx=10
        )
        controls = ttk.LabelFrame(root, text="Cấu hình giao tiếp", padding=7)
        controls.pack(fill="x", padx=10)
        ttk.Label(controls, text="Giao thức").grid(row=0, column=0)
        choice = ttk.Combobox(
            controls,
            textvariable=self.protocol,
            values=["GPIO", "UART", "LIN", "CAN", "CAN FD", "FlexRay"],
            state="readonly",
            width=9,
        )
        choice.grid(row=0, column=1, padx=5)
        choice.bind("<<ComboboxSelected>>", self.preset)
        for col, label, var, width in [
            (2, "Baud", self.baud, 7),
            (4, "ID", self.identifier, 12),
            (6, "Data HEX", self.payload, 30),
        ]:
            ttk.Label(controls, text=label).grid(row=0, column=col)
            ttk.Entry(controls, textvariable=var, width=width).grid(
                row=0, column=col + 1, padx=4
            )
        self.extra = ttk.Frame(root, padding=(12, 0))
        self.fd_option = ttk.Checkbutton(
            self.extra, text="BRS (data baud = 2 × nominal)", variable=self.fd_brs
        )
        self.channel_label = ttk.Label(self.extra, text="Kênh")
        self.cycle_label = ttk.Label(self.extra, text="Chu kỳ")
        self.channel_option = ttk.Combobox(
            self.extra,
            textvariable=self.fr_channel,
            values=["A", "B"],
            state="readonly",
            width=3,
        )
        self.cycle_option = ttk.Entry(self.extra, textvariable=self.fr_cycle, width=4)
        self.can_ext_option = ttk.Checkbutton(
            self.extra, text="ID 29-bit", variable=self.can_extended
        )
        self.can_rtr_option = ttk.Checkbutton(
            self.extra,
            text="RTR (Data để trống)",
            variable=self.can_remote,
            command=lambda: self.payload.set("" if self.can_remote.get() else "DE AD"),
        )
        self.can_dlc_label = ttk.Label(self.extra, text="RTR DLC")
        self.can_dlc_option = ttk.Spinbox(
            self.extra, from_=0, to=8, textvariable=self.can_dlc, width=3
        )
        self.header_only = tk.BooleanVar(value=False)
        self.header_option = ttk.Checkbutton(
            self.extra, text="Chỉ gửi LIN header", variable=self.header_only
        )
        self.lin_bytes = tk.StringVar(value="2")
        self.lin_label = ttk.Label(self.extra, text="Số byte LIN để giải mã")
        self.lin_length = ttk.Spinbox(
            self.extra, from_=1, to=8, textvariable=self.lin_bytes, width=3
        )
        self.extra.pack(fill="x")
        cfg = settings()["capture"]
        self.sample_hz = tk.StringVar(value=str(cfg["sample_hz"]))
        self.sample_count = tk.StringVar(value=str(cfg["sample_count"]))
        self.data_baud = tk.StringVar(value="2000")
        self.gpio_port = tk.StringVar(value="B")
        self.mask = tk.StringVar(value="0x501")
        self.decode_pin = tk.StringVar(value="0")
        self.capture_mode = tk.StringVar(value="Streaming")
        acquisition = ttk.LabelFrame(root, text="Cấu hình lấy mẫu", padding=7)
        acquisition.pack(fill="x", padx=10, pady=5)
        for col, label, var, width in [
            (0, "Sample Hz", self.sample_hz, 8),
            (2, "Số mẫu", self.sample_count, 8),
            (4, "Mask", self.mask, 7),
            (6, "Chân decode", self.decode_pin, 3),
            (8, "Data baud", self.data_baud, 7),
        ]:
            ttk.Label(acquisition, text=label).grid(row=0, column=col)
            ttk.Entry(acquisition, textvariable=var, width=width).grid(
                row=0, column=col + 1, padx=4
            )
        ttk.Label(acquisition, text="GPIO").grid(row=0, column=10, padx=2)
        ttk.Combobox(
            acquisition,
            textvariable=self.gpio_port,
            values=["A", "B", "C"],
            state="readonly",
            width=2,
        ).grid(row=0, column=11, padx=3)
        ttk.Combobox(
            acquisition,
            textvariable=self.capture_mode,
            values=["Streaming", "Burst"],
            state="readonly",
            width=9,
        ).grid(row=0, column=12, padx=3)
        actions = ttk.Frame(root, padding=(10, 0))
        actions.pack(fill="x")
        for label, fn in [
            ("Bắt đầu thu", self.capture),
            ("Gửi gói và thu", self.send),
            ("Mở bản thu", self.open),
            ("Lưu bản thu", self.save),
        ]:
            button = ttk.Button(actions, text=label, command=fn)
            button.pack(side="left", padx=4)
            self.action_buttons.append(button)
        ttk.Button(actions, text="Dừng thu/phát", command=self.cancel.set).pack(
            side="left", padx=4
        )
        ttk.Label(
            root,
            text="GPIO số · PB0: tín hiệu thiết bị    PB8: mức bus    PB10: tín hiệu phát từ host",
            padding=10,
        ).pack(anchor="w")
        tabs = ttk.Notebook(root)
        tabs.pack(fill="both", expand=True, padx=10)
        wave = ttk.Frame(tabs)
        packets = ttk.Frame(tabs)
        result = ttk.Frame(tabs)
        tabs.add(wave, text="Sóng")
        tabs.add(packets, text="Gói tin")
        tabs.add(result, text="Kết quả / phép đo")
        menus = tk.Menu(root)
        files = tk.Menu(menus, tearoff=False)
        files.add_command(
            label="Mở bản thu…",
            accelerator=(
                "⌘O" if root.tk.call("tk", "windowingsystem") == "aqua" else "Ctrl+O"
            ),
            command=self.open,
        )
        files.add_command(
            label="Lưu bản thu…",
            accelerator=(
                "⌘S" if root.tk.call("tk", "windowingsystem") == "aqua" else "Ctrl+S"
            ),
            command=self.save,
        )
        files.add_separator()
        files.add_command(label="Đóng cửa sổ", command=root.destroy)
        menus.add_cascade(label="Tệp", menu=files)
        actions_menu = tk.Menu(menus, tearoff=False)
        actions_menu.add_command(label="Kết nối USB", command=self.connect)
        protocols_menu = tk.Menu(actions_menu, tearoff=False)
        for name in ("GPIO", "UART", "LIN", "CAN", "CAN FD", "FlexRay"):
            protocols_menu.add_command(
                label=name, command=lambda p=name: self.choose_protocol(p)
            )
        actions_menu.add_cascade(label="Giao thức", menu=protocols_menu)
        for label, fn in [
            ("Bắt đầu thu", self.capture),
            ("Gửi gói và thu", self.send),
            ("Dừng thu/phát", self.cancel.set),
        ]:
            actions_menu.add_command(label=label, command=fn)
        menus.add_cascade(label="Thao tác", menu=actions_menu)
        views = tk.Menu(menus, tearoff=False)
        for index, label in enumerate(("Sóng", "Gói tin", "Kết quả / phép đo")):
            views.add_command(label=label, command=lambda i=index: tabs.select(i))
        views.add_separator()
        for label, fn in [
            ("Fit toàn bộ", lambda: self.zoom(0)),
            ("Đầu gói", self.first_packet),
            ("Phóng to", lambda: self.zoom(0.5)),
            ("Thu nhỏ", lambda: self.zoom(2)),
        ]:
            views.add_command(label=label, command=fn)
        menus.add_cascade(label="Hiển thị", menu=views)
        help_menu = tk.Menu(menus, tearoff=False)
        help_menu.add_command(
            label="Hướng dẫn từng bước",
            command=lambda: webbrowser.open((PROJECT / "docs/BAT_DAU.md").as_uri()),
        )
        help_menu.add_command(
            label="Giới thiệu / bản quyền",
            command=lambda: messagebox.showinfo(
                "HALA Academy",
                "HALA Logic — USB Logic Analyzer\nCopyright © 2026 HALA Academy\nMIT License · xem LICENSE tại gốc dự án.\nPhiên bản phát triển R002; profile giảng dạy tốc độ thấp.",
            ),
        )
        menus.add_cascade(label="Trợ giúp", menu=help_menu)
        root.config(menu=menus)
        modifier = (
            "Command" if root.tk.call("tk", "windowingsystem") == "aqua" else "Control"
        )
        root.bind(f"<{modifier}-o>", lambda e: self.open())
        root.bind(f"<{modifier}-s>", lambda e: self.save())
        toolbar = ttk.Frame(wave)
        toolbar.pack(fill="x")
        for text, fn in [
            ("Fit", lambda: self.zoom(0)),
            ("Đầu gói", self.first_packet),
            ("+", lambda: self.zoom(0.5)),
            ("−", lambda: self.zoom(2)),
        ]:
            ttk.Button(toolbar, text=text, width=5, command=fn).pack(
                side="left", padx=2, pady=4
            )
        self.cursor_text = tk.StringVar(value=CURSOR_HINT)
        ttk.Label(toolbar, textvariable=self.cursor_text).pack(side="left", padx=12)
        self.canvas = tk.Canvas(wave, bg="#101b29", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.draw())
        self.canvas.bind("<Button-1>", self.cursor)
        self.timeline = ttk.Scrollbar(wave, orient="horizontal", command=self.pan)
        self.timeline.pack(fill="x")
        self.canvas.bind("<Key-plus>", lambda e: self.zoom(0.5))
        self.canvas.bind("<Key-equal>", lambda e: self.zoom(0.5))
        self.canvas.bind("<Key-minus>", lambda e: self.zoom(2))
        self.canvas.bind("<Key-Home>", lambda e: self.zoom(0))
        self.canvas.bind("<Key-Left>", lambda e: self.pan("scroll", -1, "units"))
        self.canvas.bind("<Key-Right>", lambda e: self.pan("scroll", 1, "units"))
        self.packet_table = ttk.Treeview(
            packets,
            columns=("index", "time", "id", "data", "crc", "ack"),
            show="headings",
            height=7,
        )
        for key, title, width in [
            ("index", "STT", 45),
            ("time", "Thời gian (ms)", 130),
            ("id", "ID / loại gói", 160),
            ("data", "Dữ liệu HEX", 420),
            ("crc", "CRC / checksum", 140),
            ("ack", "ACK", 90),
        ]:
            self.packet_table.heading(key, text=title)
            self.packet_table.column(key, width=width, stretch=key == "data")
        self.packet_table.pack(fill="x")
        self.packet_table.bind("<<TreeviewSelect>>", self.packet_selected)
        self.packet_text = self.scrolled_text(packets)
        ttk.Label(
            result, text="Số đo từ mẫu GPIO số; chưa hiệu chuẩn bằng đồng hồ ngoài."
        ).pack(anchor="w", padx=8, pady=6)
        self.measure_table = ttk.Treeview(
            result,
            columns=("pin", "edges", "frequency", "period", "high", "low", "duty"),
            show="headings",
            height=5,
        )
        for key, title in [
            ("pin", "Chân"),
            ("edges", "Số cạnh"),
            ("frequency", "Tần số (Hz)"),
            ("period", "Chu kỳ (µs)"),
            ("high", "Mức cao (µs)"),
            ("low", "Mức thấp (µs)"),
            ("duty", "Duty (%)"),
        ]:
            self.measure_table.heading(key, text=title)
            self.measure_table.column(key, width=130)
        self.measure_table.pack(fill="x")
        self.result_text = self.scrolled_text(result)
        ttk.Label(
            root,
            text="Copyright © 2026 HALA Academy · MIT License · R002 phát triển · GPIO thật, profile giảng dạy",
            padding=(10, 2),
        ).pack(fill="x")
        ttk.Label(root, textvariable=self.message, padding=10, wraplength=1150).pack(
            fill="x"
        )
        self.refresh_devices()
        self.extra_options()
        root.after(50, self.poll)
        if open_path:
            root.after(150, lambda: self.load(open_path))

    def scrolled_text(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, font="TkFixedFont", wrap="word", height=6)
        scroll = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        return text

    def refresh_devices(self):
        self.devices = {p.device: p for p in list_ports.comports()}
        self.port_choice.configure(values=["Tự động", *self.devices])
        self.usb_info.set(f"{len(self.devices)} cổng serial/USB được phát hiện")

    def selected_device(self):
        value = self.device.get().strip()
        return None if not value or value == "Tự động" else value

    def choose_protocol(self, protocol):
        if self.busy:
            return
        self.protocol.set(protocol)
        self.preset()

    def preset(self, event=None):
        p = self.protocol.get()
        self.identifier.set("0x12" if p == "LIN" else "0x123")
        self.payload.set(
            "34 56"
            if p in ("LIN", "FlexRay")
            else "DE AD" if p in ("CAN", "CAN FD") else "48 45 4C 4C 4F"
        )
        self.can_extended.set(False)
        self.can_remote.set(False)
        if p in ("CAN FD", "FlexRay"):
            self.sample_hz.set(str(settings()["capture"]["slow_sample_hz"]))
            self.sample_count.set("98304" if p == "FlexRay" else "32768")
        else:
            cfg = settings()["capture"]
            self.sample_hz.set(str(cfg["sample_hz"]))
            self.sample_count.set(str(cfg["sample_count"]))
        self.extra_options()

    def capture_config(self):
        return Capture(
            protocol=self.protocol.get(),
            port=self.gpio_port.get(),
            mask=int(self.mask.get(), 0),
            bit=int(self.decode_pin.get()),
            hz=int(self.sample_hz.get()),
            count=int(self.sample_count.get()),
            baud=int(self.baud.get()),
            data_baud=int(self.data_baud.get()),
            channel=self.fr_channel.get(),
            lin_bytes=int(self.lin_bytes.get()),
            stream=self.capture_mode.get() == "Streaming",
        )

    def packet_selected(self, event=None):
        selected = self.packet_table.selection()
        if selected:
            frame = self.decoded[int(selected[0])]
            self.packet_text.delete("1.0", "end")
            self.packet_text.insert(
                "end", json.dumps(frame, ensure_ascii=False, indent=2)
            )

    def extra_options(self):
        for widget in self.extra.winfo_children():
            widget.pack_forget()
        self.extra.configure(height=1)
        if self.protocol.get() == "CAN FD":
            self.can_ext_option.pack(side="left")
            self.fd_option.pack(side="left", padx=10)
        elif self.protocol.get() == "CAN":
            for widget in (
                self.can_ext_option,
                self.can_rtr_option,
                self.can_dlc_label,
                self.can_dlc_option,
            ):
                widget.pack(side="left", padx=5)
        elif self.protocol.get() == "LIN":
            for widget in (self.header_option, self.lin_label, self.lin_length):
                widget.pack(side="left", padx=5)
        elif self.protocol.get() == "FlexRay":
            self.channel_label.pack(side="left")
            self.channel_option.pack(side="left")
            self.cycle_label.pack(side="left", padx=8)
            self.cycle_option.pack(side="left")

    def worker(self, label, fn):
        if self.busy:
            self.message.set(
                "Đang chạy một tác vụ; đợi hoàn tất trước tác vụ tiếp theo."
            )
            return
        self.busy = True
        self.cancel.clear()
        self.message.set(label)
        for button in self.action_buttons:
            button.state(["disabled"])
        self.port_choice.configure(state="disabled")

        def run():
            try:
                self.events.put(("ok", fn()))
            except Exception as exc:
                self.events.put(("error", str(exc)))

        threading.Thread(target=run, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                self.busy = False
                for button in self.action_buttons:
                    button.state(["!disabled"])
                self.port_choice.configure(state="normal")
                if kind == "error":
                    self.message.set("Lỗi: " + value)
                    self.usb_info.set("Chưa xác nhận kết nối; kiểm tra COM/USB rồi kết nối lại.")
                elif isinstance(value, Path):
                    self.load(value)
                else:
                    self.message.set(str(value))
                    if str(value).startswith("Đã kết nối"):
                        self.usb_info.set(str(value))
        except queue.Empty:
            pass
        self.root.after(50, self.poll)

    def connect(self):
        device = self.selected_device()

        def action():
            with Monitor(device) as monitor:
                caps = monitor.capabilities()
                port = monitor.port.port
                info = self.devices.get(port)
                description = info.description if info else "USB CDC"
                ids = (
                    f" · VID:PID {info.vid:04X}:{info.pid:04X}"
                    if info and info.vid is not None and info.pid is not None
                    else ""
                )
                return f"Đã kết nối {port} · {description}{ids}"

        self.worker("Đang kết nối USB...", action)

    def send(self):
        try:
            capture = self.capture_config()
            capture.validate()
            device = self.selected_device()
            signal = Signal(
                identifier=int(self.identifier.get(), 0),
                data=bytes.fromhex(self.payload.get()),
                extended=self.can_extended.get(),
                remote=self.can_remote.get(),
                dlc=int(self.can_dlc.get()),
                brs=self.fd_brs.get(),
                cycle=int(self.fr_cycle.get()),
                header_only=self.header_only.get(),
            )
            signal.encode(capture)
        except ValueError as exc:
            self.message.set("Lỗi cấu hình: " + str(exc))
            return
        self.worker(
            "Đang gửi gói và lấy mẫu GPIO...",
            lambda: acquire(capture, device, signal, self.cancel.is_set),
        )

    def capture(self):
        try:
            capture = self.capture_config()
            capture.validate()
            device = self.selected_device()
        except ValueError as exc:
            self.message.set("Lỗi cấu hình: " + str(exc))
            return
        self.worker(
            "Đang thu tín hiệu GPIO bằng Timer/DMA...",
            lambda: acquire(capture, device, cancelled=self.cancel.is_set),
        )

    def open(self):
        name = filedialog.askopenfilename(filetypes=[("Capture JSON", "*.json")])
        if name:
            self.load(Path(name))

    def load(self, path):
        try:
            path = Path(path)
            meta = json.loads(path.read_text(encoding="utf-8"))
            raw = path.with_suffix(".bin").read_bytes()
            samples = list(struct.unpack("<" + "H" * (len(raw) // 2), raw))
            status = meta["capture"]
            if (
                len(samples) != status["count"]
                or status.get("lost", 0)
                or status["state"] != 2
                or status["ticks"] <= 0
                or status["port"] not in (0, 1, 2)
            ):
                raise ValueError("INVALID capture count/state/loss")
            if (
                meta.get("raw_sha256")
                and hashlib.sha256(raw).hexdigest() != meta["raw_sha256"]
            ):
                raise ValueError("INVALID raw SHA256")
            self.samples = samples
            self.status = status
            self.root.title("HALA Logic · HALA Academy — bản thu")
            self.decoded = meta.get("decoded", [])
            self.saved = path
            self.view = (0, len(self.samples))
            self.cursors = []
            self.cursor_text.set(CURSOR_HINT)
            details = meta.get("registers_after_capture") or {}
            self.protocol.set(details.get("protocol", "GPIO"))
            self.gpio_port.set("ABC"[status["port"]])
            self.mask.set(hex(status["mask"]))
            self.sample_hz.set(str(round(72000000 / status["ticks"])))
            self.sample_count.set(str(status["count"]))
            self.capture_mode.set("Streaming" if status.get("stream") else "Burst")
            self.decode_pin.set(str(details.get("decode_bit", self.decode_pin.get())))
            for key in ("baud", "data_baud"):
                if key in details:
                    getattr(self, key).set(str(details[key]))
            if "channel" in details:
                self.fr_channel.set(details["channel"])
            if self.decoded:
                first = self.decoded[0]
                self.protocol.set(
                    "FlexRay"
                    if "frame_crc" in first
                    else (
                        "CAN FD"
                        if "crc_bits" in first
                        else (
                            "LIN"
                            if "pid" in first
                            else "CAN" if "crc" in first else "UART"
                        )
                    )
                )
                if "channel" in first:
                    self.fr_channel.set(first["channel"])
                if "cycle" in first:
                    self.fr_cycle.set(str(first["cycle"]))
                if "brs" in first:
                    self.fd_brs.set(first["brs"])
                if "extended" in first:
                    self.can_extended.set(first["extended"])
                if "remote" in first:
                    self.can_remote.set(first["remote"])
                if "dlc" in first:
                    self.can_dlc.set(str(first["dlc"]))
                if "id" in first:
                    self.identifier.set(hex(first["id"]))
                if "data" in first:
                    self.payload.set(first["data"])
            self.extra_options()
            for row in self.packet_table.get_children():
                self.packet_table.delete(row)
            hz = 72000000 / self.status["ticks"]
            for index, frame in enumerate(self.decoded):
                checks = [
                    v
                    for k, v in frame.items()
                    if k.endswith("_ok") and k not in ("ack_ok",)
                ]
                crc = "Đúng" if checks and all(checks) else "Sai" if checks else "—"
                identifier = hex(frame["id"]) if "id" in frame else self.protocol.get()
                self.packet_table.insert(
                    "",
                    "end",
                    iid=str(index),
                    values=(
                        index + 1,
                        f"{frame.get('time_s',(frame.get('sample',0)+1)/hz)*1000:.3f}",
                        identifier,
                        frame.get("data", frame.get("hex", "")),
                        crc,
                        (
                            "Có"
                            if frame.get("ack")
                            else "Không" if "ack" in frame else "—"
                        ),
                    ),
                )
            self.packet_text.delete("1.0", "end")
            self.packet_text.insert(
                "end", json.dumps(self.decoded, ensure_ascii=False, indent=2)
            )
            hz = 72000000 / self.status["ticks"]
            gpio_label = "ABC"[self.status["port"]]
            stats = {
                f"P{gpio_label}{bit}": measurements.channel(self.samples, hz, bit)
                for bit in range(16)
                if self.status["mask"] & (1 << bit)
            }
            for row in self.measure_table.get_children():
                self.measure_table.delete(row)
            for pin, stat in stats.items():

                def mean(key, scale=1):
                    value = stat[key].get("mean")
                    return "—" if value is None else f"{value*scale:.3f}"

                self.measure_table.insert(
                    "",
                    "end",
                    values=(
                        pin,
                        stat["edges"],
                        (
                            f"{stat['frequency_hz']:.3f}"
                            if "frequency_hz" in stat
                            else "—"
                        ),
                        mean("period", 1e6),
                        mean("high_width", 1e6),
                        mean("low_width", 1e6),
                        mean("duty"),
                    ),
                )
            self.result_text.delete("1.0", "end")
            self.result_text.insert("end", json.dumps(stats, indent=2))
            self.message.set(
                f"Đã mở bản thu: {len(self.samples)} mẫu GPIO, {hz:,.0f} S/s · {len(self.decoded)} gói giải mã. Kết quả CRC chỉ đánh giá dữ liệu trên tín hiệu."
            )
            if self.decoded:
                self.first_packet()
            else:
                self.draw()
        except Exception as exc:
            self.message.set("Không mở được: " + str(exc))

    def save(self):
        if not self.saved:
            self.message.set(
                "Chưa có bản thu. Thu sóng hoặc mở capture JSON trước khi lưu."
            )
            return
        name = filedialog.asksaveasfilename(defaultextension=".json")
        if name:
            import shutil

            for suffix in [".json", ".bin", ".csv", ".vcd", ".png"]:
                source = self.saved.with_suffix(suffix)
                if (
                    source.exists()
                    and source.resolve() != Path(name).with_suffix(suffix).resolve()
                ):
                    shutil.copy2(source, Path(name).with_suffix(suffix))
            self.message.set("Đã lưu raw/metadata/CSV/VCD/PNG.")

    def zoom(self, factor):
        if not self.samples:
            return
        if not factor:
            self.view = (0, len(self.samples))
        else:
            a, b = self.view
            centre = (a + b) / 2
            span = max(16, min(len(self.samples), (b - a) * factor))
            a = max(0, min(len(self.samples) - span, centre - span / 2))
            self.view = (int(a), int(a + span))
        self.draw()

    def first_packet(self):
        if not self.samples:
            return
        hz = 72000000 / self.status["ticks"]
        start = self.decoded[0]["sample"] if self.decoded else 0
        # Keep the whole first frame, including long FD/FlexRay payloads.
        a = max(0, start - round(hz * 0.004))
        frame_end = self.decoded[0].get("end_sample", start) if self.decoded else start
        b = min(len(self.samples), max(a + max(32, round(hz * 0.08)),
                                        frame_end + round(hz * 0.004)))
        self.view = (a, b)
        self.draw()

    def pan(self, operation, value, units=None):
        if not self.samples:
            return
        a, b = self.view
        span = b - a
        offset = (
            float(value) * len(self.samples)
            if operation == "moveto"
            else a + int(value) * span * (0.8 if units == "pages" else 0.1)
        )
        a = max(0, min(len(self.samples) - span, round(offset)))
        self.view = (a, a + span)
        self.draw()

    def cursor(self, event):
        if not self.samples:
            return
        self.canvas.focus_set()
        a, b = self.view
        width = max(1, self.canvas.winfo_width() - 95)
        index = max(a, min(b - 1, round(a + (event.x - 70) / width * (b - a))))
        if len(self.cursors) == 2:
            self.cursors = []
        self.cursors.append(index)
        if len(self.cursors) == 1:
            self.cursor_text.set(f"Con trỏ 1: mẫu {index}; bấm điểm thứ hai để đo Δt.")
        if len(self.cursors) == 2:
            result = measurements.cursors(
                *self.cursors, 72000000 / self.status["ticks"]
            )
            self.cursor_text.set(
                f'Con trỏ 1/2: {self.cursors}, Δt={result["delta_s"]*1e6:.3f} µs '
                f'(độ phân giải {self.status["ticks"]/72:.3f} µs)'
            )
        self.draw()

    def draw(self):
        c = self.canvas
        c.delete("all")
        if not self.samples:
            return
        a, b = self.view
        width = max(1, c.winfo_width() - 95)
        height = max(200, c.winfo_height())
        self.timeline.set(a / len(self.samples), b / len(self.samples))
        channels = [bit for bit in range(16) if self.status["mask"] & (1 << bit)]
        gpio_label = "ABC"[self.status["port"]]
        pitch = (height - 65) / max(1, len(channels))
        colours = ["#53ccf0", "#ffbd69", "#a3e77b"]
        for row, bit in enumerate(channels):
            base = 35 + row * pitch
            high = base + 12
            low = base + pitch * 0.65
            c.create_text(
                30,
                (high + low) / 2,
                text=f"P{gpio_label}{bit}",
                fill="#d5e3ed",
                font="TkFixedFont",
            )
            points = []
            previous = None
            for i in range(a, b):
                level = (self.samples[i] >> bit) & 1
                x = 70 + (i - a) / (b - a) * width
                y = high if level else low
                if previous is None:
                    points.extend([x, y])
                elif level != previous:
                    points.extend([x, low if level else high, x, y])
                previous = level
            points.extend([70 + width, high if previous else low])
            if len(points) >= 4:
                c.create_line(*points, fill=colours[row % 3], width=2)
        hz = 72000000 / self.status["ticks"]
        for i in range(9):
            sample = a + (b - a) * i / 8
            x = 70 + width * i / 8
            c.create_line(x, 20, x, height - 35, fill="#203349")
            c.create_text(
                x,
                height - 20,
                text=f"{(sample+1)/hz*1000:.2f} ms",
                fill="#b0c2d3",
                anchor="w" if i == 0 else "e" if i == 8 else "center",
            )
        for n, index in enumerate(self.cursors):
            x = 70 + (index - a) / (b - a) * width
            c.create_line(x, 10, x, height - 35, fill="#f578a8", dash=(4, 3))
            c.create_text(x + 10, 10, text="12"[n], fill="#f578a8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--open", type=Path)
    args = parser.parse_args()
    root = tk.Tk()
    App(root, args.open)
    root.mainloop()
