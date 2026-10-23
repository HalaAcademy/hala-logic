#!/usr/bin/env python3
"""Fail-closed validation/sealing of the standardized B ELF, never a flasher."""

import sys
from pathlib import Path

_PROJECT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(_PROJECT / folder) for folder in ("host", "tools/device", "tests/hardware")
]
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import zlib
from elftools.elf.elffile import ELFFile

FLASH = 0x08006000
FLASH_END = 0x08010000
RAM = 0x20003000
RAM_END = 0x20005000
MANIFEST_OFFSET = 0x200
MAGIC = 0x42414250
VERSION = 1
VECTOR_COUNT = 76


class ELFRejected(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ELFRejected(message)


def inspect(path, sealed=True):
    with open(path, "rb") as stream:
        elf = ELFFile(stream)
        require(
            elf.elfclass == 32 and elf.little_endian and elf["e_machine"] == "EM_ARM",
            "B must be a little-endian ARM ELF32",
        )
        require(elf["e_type"] == "ET_EXEC", "B must be a linked executable")
        vector = elf.get_section_by_name(".isr_vector")
        manifest = elf.get_section_by_name(".manifest")
        require(
            vector is not None
            and vector["sh_addr"] == FLASH
            and vector["sh_size"] == VECTOR_COUNT * 4,
            "incorrect vector table layout",
        )
        require(
            manifest is not None
            and manifest["sh_addr"] == FLASH + MANIFEST_OFFSET
            and manifest["sh_size"] == 64,
            "incorrect manifest layout",
        )
        image = bytearray(b"\xff" * (FLASH_END - FLASH))
        used = bytearray(len(image))
        end = FLASH
        loads = []
        for seg in elf.iter_segments():
            if seg["p_type"] != "PT_LOAD":
                continue
            va, pa, fs, ms = (
                int(seg[k]) for k in ("p_vaddr", "p_paddr", "p_filesz", "p_memsz")
            )
            require(fs <= ms, "segment file size exceeds memory size")
            require(
                (FLASH <= va and va + ms <= FLASH_END)
                or (RAM <= va and va + ms <= RAM_END),
                "load VMA/memory overlaps A or exceeds B",
            )
            require(
                not ((seg["p_flags"] & 1) and va >= RAM),
                "executable RAM segments are unsupported",
            )
            if fs:
                require(
                    FLASH <= pa and pa + fs <= FLASH_END,
                    "load LMA/file payload overlaps A or exceeds B",
                )
                off = pa - FLASH
                require(not any(used[off : off + fs]), "overlapping load segments")
                image[off : off + fs] = seg.data()
                used[off : off + fs] = b"\x01" * fs
                end = max(end, pa + fs)
            loads.append({"vma": va, "lma": pa, "filesz": fs, "memsz": ms})
        image = image[: end - FLASH]
        require(len(image) >= 0x240, "image too small")
        sp, entry = struct.unpack_from("<II", image)
        require(
            RAM < sp <= RAM_END and sp % 8 == 0,
            "B initial PSP is outside B RAM or unaligned",
        )
        require(
            entry & 1 and FLASH + 0x240 <= (entry & ~1) < end,
            "invalid Thumb reset entry",
        )
        require(int(elf["e_entry"]) == entry, "ELF entry differs from reset vector")
        for i in range(2, VECTOR_COUNT):
            (value,) = struct.unpack_from("<I", image, i * 4)
            require(
                not value or (value & 1 and FLASH + 0x240 <= (value & ~1) < end),
                f"vector {i} points outside B executable image",
            )
        # Every allocatable section, including NOLOAD stack/BSS, must be in B.
        for sec in elf.iter_sections():
            if sec["sh_flags"] & 2 and sec["sh_size"]:
                addr, size = sec["sh_addr"], sec["sh_size"]
                require(
                    (FLASH <= addr and addr + size <= FLASH_END)
                    or (RAM <= addr and addr + size <= RAM_END),
                    f"section {sec.name} overlaps A",
                )
        header = bytes(image[0x200:0x240])
        image[0x200:0x240] = bytes(64)
        crc = zlib.crc32(image)
        sha = hashlib.sha256(image).digest()
        expected = struct.pack(
            "<8I32s", MAGIC, VERSION, len(image), crc, FLASH, RAM, RAM_END, entry, sha
        )
        if sealed:
            require(header == expected, "manifest/CRC/SHA mismatch; seal after linking")
        return {
            "path": str(path),
            "image_bytes": len(image),
            "crc32": crc,
            "sha256": sha.hex(),
            "sp": sp,
            "entry": entry,
            "loads": loads,
        }, expected


def seal(source, output, objcopy="arm-none-eabi-objcopy"):
    _, header = inspect(source, sealed=False)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bp-seal-") as temp:
        payload = Path(temp) / "manifest.bin"
        payload.write_bytes(header)
        staging = Path(temp) / "sealed.elf"
        subprocess.run(
            [
                objcopy,
                "--update-section",
                f".manifest={payload}",
                str(source),
                str(staging),
            ],
            check=True,
        )
        inspect(staging)
        shutil.copy2(staging, output)
    return inspect(output)[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("elf", type=Path)
    parser.add_argument("--seal", type=Path, help="write a sealed ELF to this path")
    args = parser.parse_args()
    try:
        result = seal(args.elf, args.seal) if args.seal else inspect(args.elf)[0]
    except (ELFRejected, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"ELF REJECTED: {exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
