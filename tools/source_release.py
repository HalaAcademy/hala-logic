#!/usr/bin/env python3
"""Tạo ZIP mã nguồn từ whitelist; không chứa backup/build/evidence máy cá nhân."""

import datetime
import hashlib
from pathlib import Path
import sys
import zipfile
from check_repo import check, ROOT


def source_files():
    files = []
    for name in [
        "README.md",
        "LICENSE",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
        "THIRD_PARTY_NOTICES.md",
        ".gitignore",
        ".gitattributes",
        ".editorconfig",
        "Makefile",
        "requirements.txt",
    ]:
        files.append(ROOT / name)
    for folder in [
        "configs",
        "docs",
        "tools",
        ".github",
        "host",
        "firmware",
        "examples",
        "tests",
        "profiles",
    ]:
        for file in (ROOT / folder).rglob("*"):
            parts = file.relative_to(ROOT).parts
            if not file.is_file() or any(
                p in ("__pycache__", "build", "dist") for p in parts
            ):
                continue
            if (
                file.name in ("local.json", ".DS_Store", "README_TRUOC_CHUAN_HOA.md")
                or file.suffix == ".pyc"
            ):
                continue
            files.append(file)
    return sorted(set(files))


def main():
    if check():
        return 1
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    directory = ROOT / "dist"
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / f"hala-logic-source-{stamp}.zip"
    hashes = {}
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as output:
        for file in source_files():
            name = file.relative_to(ROOT).as_posix()
            data = file.read_bytes()
            output.writestr(name, data)
            hashes[name] = hashlib.sha256(data).hexdigest()
        import json

        output.writestr(
            "SOURCE_MANIFEST.json",
            json.dumps(
                {
                    "license": "MIT",
                    "copyright": "2026 HALA Academy",
                    "hardware_qualified": False,
                    "files": hashes,
                },
                indent=2,
            ),
        )
    with zipfile.ZipFile(archive) as output:
        if output.testzip():
            raise RuntimeError("ZIP không toàn vẹn")
        for name, sha in hashes.items():
            if hashlib.sha256(output.read(name)).hexdigest() != sha:
                raise RuntimeError("ZIP hash sai: " + name)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(digest + "  " + archive.name + "\n")
    print(f"Đã tạo {archive.name}: {len(hashes)} file nguồn, SHA256 {digest}")
    print("Gói nguồn chưa phải bản phát hành đã qualification trên mọi hệ điều hành.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
