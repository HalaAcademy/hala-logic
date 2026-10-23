"""Export real captured samples; timestamps are nominal timer-derived times."""

import csv
import json
from pathlib import Path
import struct
import hashlib


def export_capture(prefix, status, samples, decoded=None, info=None, registers=None):
    prefix = Path(prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    raw = struct.pack("<" + "H" * len(samples), *samples)
    metadata = {
        "capture": status,
        "monitor": info,
        "registers_after_capture": registers,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "decoded": decoded or [],
        "timing_note": "Relative timestamps use (index+1)*TIM2_ticks/72MHz; "
        "DMA bus latency and oscillator tolerance are not calibrated.",
    }
    Path(str(prefix) + ".json").write_text(json.dumps(metadata, indent=2) + "\n")
    Path(str(prefix) + ".bin").write_bytes(raw)
    channels = [bit for bit in range(16) if status["mask"] & (1 << bit)]
    label = "ABC"[status["port"]]
    with Path(str(prefix) + ".csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            ["sample", "relative_ns", "gpio_hex"] + [f"P{label}{b}" for b in channels]
        )
        for i, value in enumerate(samples):
            writer.writerow(
                [i, round((i + 1) * status["ticks"] * 1e9 / 72000000), f"0x{value:04x}"]
                + [(value >> b) & 1 for b in channels]
            )
    with Path(str(prefix) + ".vcd").open("w") as stream:
        stream.write("$timescale 1ns $end\n$scope module bluepill $end\n")
        for bit in channels:
            stream.write(f"$var wire 1 b{bit} P{label}{bit} $end\n")
        stream.write("$upscope $end\n$enddefinitions $end\n")
        previous = None
        for i, value in enumerate(samples):
            value &= status["mask"]
            if value == previous:
                continue
            stream.write(f'#{round((i+1) * status["ticks"] * 1e9 / 72000000)}\n')
            for bit in channels:
                if previous is None or ((previous ^ value) & (1 << bit)):
                    stream.write(f"{(value >> bit) & 1}b{bit}\n")
            previous = value
    plot_capture(prefix, status, samples, decoded)
    return metadata


def plot_capture(prefix, status, samples, decoded=None, *, sample_window=None):
    """Render raw samples without altering acquisition files or sample indices."""
    prefix = Path(prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    channels = [bit for bit in range(16) if status["mask"] & (1 << bit)]
    label = "ABC"[status["port"]]
    start, stop = sample_window or (0, len(samples))
    if not 0 <= start < stop <= len(samples):
        raise ValueError("Invalid raw sample window")
    # Standalone scientific plot; headless, deterministic, no web server.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(13, max(3, len(channels) * 0.8 + 1.5)))
    times = [(i + 1) * status["ticks"] / 72000 for i in range(start, stop)]
    for row, bit in enumerate(channels):
        values = [((v >> bit) & 1) * 0.7 + row for v in samples[start:stop]]
        ax.step(times, values, where="post", linewidth=1, label=f"P{label}{bit}")
    ax.set_yticks(
        [row + 0.35 for row in range(len(channels))], [f"P{label}{b}" for b in channels]
    )
    ax.set_ylim(-0.1, max(1.1, len(channels)))
    ax.set_xlabel("Relative time (ms), nominal timer clock")
    detail = (
        f"detail samples {start}:{stop} of {len(samples)}"
        if sample_window
        else f"{len(samples)} samples"
    )
    ax.set_title(
        f'Blue Pill DMA capture #{status["id"]} — '
        f'{72000000/status["ticks"]:,.0f} samples/s, {detail}'
    )
    ax.grid(axis="x", alpha=0.25)
    for item in (decoded or [])[:40]:
        if not start <= item["sample"] < stop:
            continue
        if "id" in item:
            protocol = (
                "FR"
                if "frame_crc" in item
                else "FD" if "crc_bits" in item else "LIN" if "pid" in item else "CAN"
            )
            size = item.get("length", len(item.get("data", "")) // 2)
            label_text = f'{protocol} {item["id"]:X}, {size} B'
        else:
            label_text = item.get("hex", item.get("data", ""))[:24]
        ax.annotate(
            label_text,
            (item["time_s"] * 1000, 0.98),
            xycoords=("data", "axes fraction"),
            xytext=(4, -2),
            textcoords="offset points",
            fontsize=8,
            va="top",
            clip_on=True,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.85, "pad": 1},
        )
    fig.tight_layout()
    fig.savefig(str(prefix) + ".png", dpi=130, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    return Path(str(prefix) + ".png")
