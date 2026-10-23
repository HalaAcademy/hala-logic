"""Host encoders produce generic physical-pad level schedules, no bit USB loop."""


def uart(data, pin=8, idle_bits=12):
    if pin not in (8, 10) or idle_bits < 0:
        raise ValueError("Unsupported output pin or idle length")
    bits = [1] * idle_bits
    for value in bytes(data):
        bits.extend([0] + [(value >> i) & 1 for i in range(8)] + [1])
    bits.extend([1] * 12)
    return [(1 << pin) if bit else 0 for bit in bits]


def polynomial_crc(bits, width, polynomial):
    """Long division oracle, independent of streaming CRC code in B/decoder."""
    value = 0
    for bit in bits:
        value = (value << 1) | bit
    value <<= width
    divisor = (1 << width) | polynomial
    while value.bit_length() > width:
        value ^= divisor << (value.bit_length() - width - 1)
    return value


def can(
    identifier,
    data=b"",
    pin=10,
    corrupt_crc=False,
    *,
    extended=False,
    remote=False,
    dlc=None
):
    data = bytes(data)
    dlc = len(data) if dlc is None else dlc
    if (
        not 0 <= identifier <= (0x1FFFFFFF if extended else 0x7FF)
        or not 0 <= dlc <= 8
        or pin not in (8, 10)
        or (remote and data)
        or (not remote and dlc != len(data))
    ):
        raise ValueError("Invalid Classical CAN ID/format/data/DLC/pin")

    def msb(v, n):
        return [(v >> i) & 1 for i in range(n - 1, -1, -1)]

    raw = (
        [0]
        + msb(identifier >> 18, 11)
        + [1, 1]
        + msb(identifier & 0x3FFFF, 18)
        + [int(remote), 0, 0]
        if extended
        else [0] + msb(identifier, 11) + [int(remote), 0, 0]
    )
    raw += msb(dlc, 4)
    for byte in data:
        raw += msb(byte, 8)
    crc = polynomial_crc(raw, 15, 0x4599) ^ int(corrupt_crc)
    raw += msb(crc, 15)
    stuffed = []
    previous = None
    run = 0
    for bit in raw:
        stuffed.append(bit)
        run = run + 1 if bit == previous else 1
        previous = bit
        if run == 5:
            stuffed.append(1 - bit)
            previous = 1 - bit
            run = 1
    bits = [1] * 12 + stuffed + [1] * 13 + [1] * 12
    return [(1 << pin) if bit else 0 for bit in bits]


def lin(
    identifier,
    data=b"",
    pin=10,
    header_only=False,
    corrupt_checksum=False,
    corrupt_pid=False,
):
    if not 0 <= identifier <= 63 or len(data) > 8 or pin not in (8, 10):
        raise ValueError("Invalid LIN ID/data/pin")
    b = [(identifier >> i) & 1 for i in range(6)]
    pid = (
        identifier
        | ((b[0] ^ b[1] ^ b[2] ^ b[4]) << 6)
        | ((1 ^ b[1] ^ b[3] ^ b[4] ^ b[5]) << 7)
    )
    wire_pid = pid ^ (64 if corrupt_pid else 0)
    total = sum(data) + (0 if identifier in (60, 61) else pid)
    folded = (total - 1) % 255 + 1 if total else 0
    checksum = (255 - folded) ^ int(corrupt_checksum)
    fields = bytes([0x55, wire_pid]) + (
        b"" if header_only else bytes(data) + bytes([checksum])
    )
    bits = [1] * 12 + [0] * 13 + [1]
    for value in fields:
        bits += [0] + [(value >> i) & 1 for i in range(8)] + [1]
    bits += [1] * (60 if header_only else 12)
    return [(1 << pin) if bit else 0 for bit in bits]
