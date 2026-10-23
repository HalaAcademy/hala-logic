"""FR21A-TEACH static frame coding/CRC. Not a complete FlexRay cluster stack.

Primary: FlexRay Protocol Specification 2.1 Rev A chapters 3/4, university
hosted copy. TSS=9 bit, FSS=H, BSS=HL, FES=LH; MSB first, channel CRC seeds.
"""


def bits(value, n):
    return [(value >> i) & 1 for i in range(n - 1, -1, -1)]


def division(data, width, poly, seed):
    value = 0
    for b in data:
        value = (value << 1) | b
    value = (value << width) ^ (seed << len(data))
    divisor = (1 << width) | poly
    while value.bit_length() > width:
        value ^= divisor << (value.bit_length() - width - 1)
    return value


def frame(
    identifier,
    data=b"",
    cycle=0,
    channel="A",
    sync=False,
    startup=False,
    pin=10,
    corrupt_header=False,
    corrupt_crc=False,
):
    data = bytes(data)
    if (
        not 1 <= identifier <= 2047
        or len(data) > 254
        or len(data) % 2
        or not 0 <= cycle <= 63
    ):
        raise ValueError("Invalid FlexRay frame ID/even payload length/cycle")
    if channel not in ("A", "B") or pin not in (8, 10) or startup and not sync:
        raise ValueError("Invalid channel/pin/startup without sync")
    words = len(data) // 2
    hinput = [int(sync), int(startup)] + bits(identifier, 11) + bits(words, 7)
    hcrc = division(hinput, 11, 0x385, 0x1A) ^ int(corrupt_header)
    header = (
        [0, 0, 1, int(sync), int(startup)]
        + bits(identifier, 11)
        + bits(words, 7)
        + bits(hcrc, 11)
        + bits(cycle, 6)
    )
    payload = [b for byte in data for b in bits(byte, 8)]
    crc = division(
        header + payload, 24, 0x5D6DCB, 0xFEDCBA if channel == "A" else 0xABCDEF
    ) ^ int(corrupt_crc)
    raw = header + payload + bits(crc, 24)
    physical = [1] * 12 + [0] * 9 + [1]
    for i in range(0, len(raw), 8):
        physical += [1, 0] + raw[i : i + 8]
    physical += [0, 1] + [1] * 12
    return [(1 << pin) if bit else 0 for bit in physical], {
        "profile": "FR21A-TEACH-STATIC-FRAME",
        "id": identifier,
        "data": data.hex(),
        "cycle": cycle,
        "channel": channel,
        "header_crc": hcrc,
        "frame_crc": crc,
        "tss_bits": 9,
    }


def decode(levels, hz, baud=1000, channel="A"):
    if hz / baud < 8 or channel not in ("A", "B"):
        raise ValueError("Invalid sampling/channel")
    spb = hz / baud
    result = []
    i = 1
    idle = 0

    def val(seq):
        v = 0
        for b in seq:
            v = (v << 1) | b
        return v

    def crc_stream(seq, width, poly, seed):
        crc = seed
        for bit in seq:
            feedback = ((crc >> (width - 1)) & 1) ^ bit
            crc = (crc << 1) & ((1 << width) - 1)
            if feedback:
                crc ^= poly
        return crc

    while i < len(levels):
        idle = idle + 1 if levels[i - 1] else 0
        if not (idle >= 10 * spb and levels[i] == 0):
            i += 1
            continue
        start = i
        while i < len(levels) and not levels[i]:
            i += 1
        low_count = (i - start) / spb
        if not 8.5 <= low_count <= 9.5:
            idle = 0
            continue
        # FSS starts at this rising edge; first BSS low centre is +2.5 bit.
        centre = i + 2.5 * spb
        raw = []
        target = 40

        def take():
            nonlocal centre
            if int(centre) >= len(levels):
                raise IndexError("truncated")
            b = levels[int(centre)]
            centre += spb
            return b

        try:
            while len(raw) < target:
                if take() != 0:
                    raise ValueError("BSS low")
                raw.extend(take() for _ in range(8))
                if len(raw) == 40:
                    target = 40 + val(raw[16:23]) * 16 + 24
                if len(raw) < target and take() != 1:
                    raise ValueError("BSS high")
            fes = [take(), take()]
            ident = val(raw[5:16])
            length = val(raw[16:23]) * 2
            hcrc = val(raw[23:34])
            expected_h = crc_stream(raw[3:5] + raw[5:23], 11, 0x385, 0x1A)
            crc = val(raw[-24:])
            expected_c = crc_stream(
                raw[:-24], 24, 0x5D6DCB, 0xFEDCBA if channel == "A" else 0xABCDEF
            )
            payload = bytes(val(raw[40 + n * 8 : 48 + n * 8]) for n in range(length))
            result.append(
                {
                    "sample": start,
                    "time_s": (start + 1) / hz,
                    "id": ident,
                    "cycle": val(raw[34:40]),
                    "length": length,
                    "data": payload.hex(),
                    "channel": channel,
                    "header_crc": hcrc,
                    "header_crc_ok": hcrc == expected_h,
                    "frame_crc": crc,
                    "frame_crc_ok": crc == expected_c,
                    "format_ok": fes == [0, 1] and ident != 0,
                    "tss_bits": low_count,
                }
            )
            i = int(centre)
            idle = 0
        except (ValueError, IndexError):
            i += 1
            idle = 0
    return result
