"""ISO FD 11/29 data teaching profile, nominal 1k / data 1k or 2k, real pad schedules.

CRC reference: Bosch Mutter/Hartwich iCC 2015 + CAN Newsletter 1/2015.
Uses dynamic stuffed bits + Gray stuff count/parity, high-bit seed, excludes
fixed stuff bits. BRS and delimiter switch at the configured 50% sample point.
No claim of full error-confinement, independent-clock or physical-bus conformance.
"""

import math

LENGTHS = list(range(9)) + [12, 16, 20, 24, 32, 48, 64]


def bits(value, n):
    return [(value >> i) & 1 for i in range(n - 1, -1, -1)]


def crc_division(data, width, poly):
    value = 0
    for bit in data:
        value = (value << 1) | bit
    value = (value << width) ^ ((1 << (width - 1)) << len(data))
    divisor = (1 << width) | poly
    while value.bit_length() > width:
        value ^= divisor << (value.bit_length() - width - 1)
    return value


def frame(
    identifier,
    data=b"",
    brs=True,
    esi=False,
    pin=10,
    corrupt_crc=False,
    corrupt_count=False,
    *,
    extended=False
):
    data = bytes(data)
    if (
        not 0 <= identifier <= (0x1FFFFFFF if extended else 0x7FF)
        or len(data) not in LENGTHS
        or pin not in (8, 10)
    ):
        raise ValueError("ISO FD ID/format/length/pin unsupported")
    raw = (
        [0]
        + bits(identifier >> 18, 11)
        + [1, 1]
        + bits(identifier & 0x3FFFF, 18)
        + [0, 1, 0]
        if extended
        else [0] + bits(identifier, 11) + [0, 0, 1, 0]
    )
    raw += [int(brs), int(esi)] + bits(LENGTHS.index(len(data)), 4)
    brs_index = len(raw) - 6
    for byte in data:
        raw += bits(byte, 8)
    stuffed = []
    durations = []
    run = 0
    last = None
    count = 0
    for i, bit in enumerate(raw):
        stuffed.append(bit)
        durations.append(
            3 if brs and i == brs_index else 2 if brs and i > brs_index else 4
        )
        run = run + 1 if bit == last else 1
        last = bit
        if run == 5 and i != len(raw) - 1:
            stuffed.append(1 - bit)
            durations.append(2 if brs and i >= brs_index else 4)
            last = 1 - bit
            run = 1
            count += 1
    gray = (count & 7) ^ ((count & 7) >> 1)
    if corrupt_count:
        gray ^= 1
    sc = bits(gray, 3) + [(gray ^ (gray >> 1) ^ (gray >> 2)) & 1]
    width = 17 if len(data) <= 16 else 21
    poly = 0x1685B if width == 17 else 0x102899
    crc = crc_division(stuffed + sc, width, poly) ^ int(corrupt_crc)
    field = sc + bits(crc, width)
    physical = list(stuffed)
    ticks = list(durations)
    last = physical[-1]
    for i, bit in enumerate(field):
        if i % 4 == 0:
            physical.append(1 - last)
            ticks.append(2 if brs else 4)
            last = 1 - last
        physical.append(bit)
        ticks.append(2 if brs else 4)
        last = bit
    physical += [1] * 13
    ticks += ([3] if brs else [4]) + [
        4
    ] * 12  # mixed CRC-delimiter, then nominal ACK/EOF/IFS
    levels = [1] * 48
    for bit, n in zip(physical, ticks):
        levels.extend([bit] * n)
    levels += [1] * 48
    return [(1 << pin) if bit else 0 for bit in levels], {
        "profile": (
            "CANFD-ISO2015-EXT-TEACH" if extended else "CANFD-ISO2015-BASE-TEACH"
        ),
        "id": identifier,
        "extended": extended,
        "data": data.hex(),
        "brs": brs,
        "esi": esi,
        "crc": crc,
        "crc_bits": width,
        "stuff_bits": count,
        "crc_input_bits": len(stuffed) + 4,
        "quarter_bit_hz": 4000,
        "ack_quarter_from_sof": sum(ticks[:-12]),
        "active_quarters": sum(ticks),
    }


def decode(samples, hz, nominal=1000, data_rate=2000):
    """Independent sampled parser, streaming LFSR CRC (encoder uses division)."""
    if min(hz / nominal, hz / data_rate) < 8:
        raise ValueError("FD requires >=8 samples/fast bit")
    result = []
    i = 1
    idle = 0
    while i < len(samples):
        idle = idle + 1 if samples[i - 1] else 0
        if not (idle >= 11 * hz / nominal and not samples[i]):
            i += 1
            continue
        start = i
        period = hz / nominal
        centre = i + period / 2
        raw = []
        stuffed = []
        last = None
        run = 0
        count = 0
        target = header = 22
        crc_field = []

        def take():
            nonlocal centre
            if int(centre) >= len(samples):
                raise IndexError("truncated")
            bit = samples[int(centre)]
            centre += period
            return bit

        def value(seq):
            v = 0
            for b in seq:
                v = (v << 1) | b
            return v

        try:
            while len(raw) < target:
                if run == 5:
                    b = take()
                    if b == last:
                        raise ValueError("dynamic stuff error")
                    stuffed.append(b)
                    count += 1
                    last = b
                    run = 1
                b = take()
                stuffed.append(b)
                raw.append(b)
                run = run + 1 if b == last else 1
                last = b
                if len(raw) == 14 and raw[13]:
                    header = target = 41
                if len(raw) == header - 5 and b:
                    centre += hz / data_rate - period
                    period = hz / data_rate
                if len(raw) == header:
                    if raw[32 if header == 41 else 12] or raw[
                        header - 8 : header - 6
                    ] != [1, 0]:
                        raise ValueError("FD format")
                    length = LENGTHS[value(raw[header - 4 : header])]
                    target = header + length * 8
            width = 17 if length <= 16 else 21
            pos = 0
            while len(crc_field) < width + 4:
                if len(crc_field) % 4 == 0:
                    b = take()
                    if b == last:
                        raise ValueError("fixed stuff error")
                    last = b
                b = take()
                crc_field.append(b)
                last = b
            crc = 1 << (width - 1)
            poly = 0x1685B if width == 17 else 0x102899
            for b in stuffed + crc_field[:4]:
                feedback = ((crc >> (width - 1)) & 1) ^ b
                crc = (crc << 1) & ((1 << width) - 1)
                if feedback:
                    crc ^= poly
            delimiter = take()
            if raw[header - 6]:
                centre += hz / nominal - period
                period = hz / nominal
            ack, ack_del = take(), take()
            eof = [take() for _ in range(7)]
            gray = (count & 7) ^ ((count & 7) >> 1)
            count_ok = crc_field[:3] == bits(gray, 3) and (sum(crc_field[:4]) & 1) == 0
            received = value(crc_field[4:])
            payload = bytes(
                value(raw[header + n * 8 : header + 8 + n * 8]) for n in range(length)
            )
            result.append(
                {
                    "sample": start,
                    "time_s": (start + 1) / hz,
                    "end_sample": int(centre - period / 2),
                    "id": (
                        (value(raw[1:12]) << 18) | value(raw[14:32])
                        if header == 41
                        else value(raw[1:12])
                    ),
                    "extended": header == 41,
                    "data": payload.hex(),
                    "dlc": LENGTHS.index(length),
                    "length": length,
                    "brs": bool(raw[header - 6]),
                    "esi": bool(raw[header - 5]),
                    "crc_bits": width,
                    "crc": received,
                    "computed_crc": crc,
                    "crc_ok": received == crc,
                    "stuff_count_ok": count_ok,
                    "stuff_bits": count,
                    "ack": not ack,
                    "format_ok": delimiter == ack_del == 1 and eof == [1] * 7,
                }
            )
            i = int(centre - period / 2)
            idle = 0
        except (ValueError, IndexError):
            i += 1
            idle = 0
    return result
