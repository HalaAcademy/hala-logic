"""Bounded teaching decoders: UART 8N1, LIN, Classical CAN 11/29 data/RTR.

Input is a sampled digital logic level, not CANH/CANL or LIN bus voltage.
UART/LIN require >=4 samples/bit; CAN uses >=8 and caller-supplied bit rate.
No auto-baud, CAN error-state decoder or clock-resynchronization claim.
FD and FlexRay static-frame decoders are separate modules.
"""

import math


def levels(samples, bit=0):
    if not 0 <= bit <= 15:
        raise ValueError("bit must be 0..15")
    return [(s >> bit) & 1 for s in samples]


def uart(bits, sample_hz, baud=9600, require_idle=True):
    spb = sample_hz / baud
    if spb < 4:
        raise ValueError("UART needs at least 4 samples/bit")
    frames = []
    i, idle, synchronized = 1, 0, False
    while i + 10 * spb < len(bits):
        idle = idle + 1 if bits[i - 1] else 0
        if bits[i - 1] and not bits[i]:
            if idle >= 10 * spb:
                synchronized = True
            if require_idle and not synchronized:
                i += 1
                continue
            at = lambda position: bits[int(i + position * spb)]
            if at(0.5) == 0 and at(9.5) == 1:
                value = sum(at(1.5 + k) << k for k in range(8))
                frames.append(
                    {
                        "sample": i,
                        "time_s": (i + 1) / sample_hz,
                        "value": value,
                        "hex": f"{value:02X}",
                        "synchronized": synchronized,
                    }
                )
                i = math.ceil(i + 9.75 * spb)
                idle = 0
                continue
            synchronized = False
        i += 1
    return frames


def lin_pid(identifier):
    b = [(identifier >> k) & 1 for k in range(6)]
    p0 = b[0] ^ b[1] ^ b[2] ^ b[4]
    p1 = 1 ^ b[1] ^ b[3] ^ b[4] ^ b[5]
    return (identifier & 63) | (p0 << 6) | (p1 << 7)


def lin_checksum(data, pid=None):
    value = sum(data) + (pid if pid is not None else 0)
    while value > 255:
        value = (value & 255) + (value >> 8)
    return (~value) & 255


def lin(bits, sample_hz, baud=9600, data_length=2):
    if not 1 <= data_length <= 8:
        raise ValueError("LIN data_length must be 1..8")
    spb = sample_hz / baud
    decoded = uart(bits, sample_hz, baud, require_idle=False)
    breaks = []
    start = None
    for i, bit in enumerate(bits):
        if not bit and start is None:
            start = i
        if bit and start is not None:
            if i - start >= 11 * spb and start > 0:
                breaks.append((start, i))
            start = None
    frames = []
    for start, end in breaks:
        candidates = [f for f in decoded if f["sample"] >= end]
        needed = data_length + 3  # sync, PID, data, checksum
        if len(candidates) < needed:
            continue
        fields = candidates[:needed]
        if fields[0]["value"] != 0x55:
            continue
        pid = fields[1]["value"]
        data = [f["value"] for f in fields[2:-1]]
        identifier = pid & 63
        expected = lin_checksum(data, None if identifier in (60, 61) else pid)
        frames.append(
            {
                "sample": start,
                "time_s": (start + 1) / sample_hz,
                "id": identifier,
                "pid": pid,
                "parity_ok": lin_pid(identifier) == pid,
                "data": bytes(data).hex(),
                "checksum": fields[-1]["value"],
                "checksum_ok": expected == fields[-1]["value"],
                "break_bits": (end - start) / spb,
            }
        )
    return frames


def can_crc(bits):
    crc = 0
    for bit in bits:
        feedback = ((crc >> 14) & 1) ^ bit
        crc = (crc << 1) & 0x7FFF
        if feedback:
            crc ^= 0x4599
    return crc


def can(bits, sample_hz, baud=20000):
    spb = sample_hz / baud
    if spb < 8:
        raise ValueError("CAN teaching decoder needs at least 8 samples/bit")
    frames = []
    i, idle = 1, 0
    while i < len(bits):
        if bits[i - 1]:
            idle += 1
        else:
            idle = 0
        if not (idle >= 11 * spb and bits[i] == 0):
            i += 1
            continue
        # Fixed nominal bit centres; suitable for short, low-rate local stimuli.
        start, physical, raw, run, previous, stuff = i, 0, [], 0, None, 0
        target = 19
        header = 19

        def take():
            nonlocal physical
            index = int(start + (physical + 0.5) * spb)
            if index >= len(bits):
                raise IndexError
            physical += 1
            return bits[index]

        def value(seq):
            result = 0
            for b in seq:
                result = (result << 1) | b
            return result

        try:
            while len(raw) < target:
                if run == 5:
                    b = take()
                    if b == previous:
                        raise ValueError("stuff error")
                    previous, run, stuff = b, 1, stuff + 1
                b = take()
                raw.append(b)
                run = run + 1 if b == previous else 1
                previous = b
                if len(raw) == 14 and raw[13]:
                    header = target = 39
                if len(raw) == header:
                    dlc = value(raw[header - 4 : header])
                    remote = bool(raw[32 if header == 39 else 12])
                    if dlc > 8:
                        raise ValueError("DLC outside teaching profile 0..8")
                    target = header + (0 if remote else 8 * dlc) + 15
            if run == 5:
                if take() == previous:
                    raise ValueError("final stuff error")
                stuff += 1
            crc_delimiter, ack, ack_delimiter = take(), take(), take()
            eof = [take() for _ in range(7)]
            if crc_delimiter != 1 or ack_delimiter != 1 or eof != [1] * 7:
                raise ValueError("delimiter/EOF error")
            received_crc = value(raw[-15:])
            payload = bytes(
                value(raw[header + k * 8 : header + 8 + k * 8])
                for k in range(0 if remote else dlc)
            )
            frames.append(
                {
                    "sample": start,
                    "time_s": (start + 1) / sample_hz,
                    "end_sample": int(start + physical * spb),
                    "id": (
                        (value(raw[1:12]) << 18) | value(raw[14:32])
                        if header == 39
                        else value(raw[1:12])
                    ),
                    "extended": header == 39,
                    "remote": remote,
                    "dlc": dlc,
                    "data": payload.hex(),
                    "crc": received_crc,
                    "crc_ok": received_crc == can_crc(raw[:-15]),
                    "ack": ack == 0,
                    "stuff_bits": stuff,
                }
            )
            i = int(start + physical * spb)
            idle = 0
        except (IndexError, ValueError):
            i += 1
            idle = 0
    return frames
