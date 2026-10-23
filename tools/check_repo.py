#!/usr/bin/env python3
"""Kiểm cây nguồn, link tài liệu, ví dụ và ranh giới GUI/firmware."""

from pathlib import Path
import ast
import json
import hashlib
import re
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))
from config import catalog, settings


def documentation_errors(root):
    docs = sorted(p for p in root.rglob("*.md") if not set(p.relative_to(root).parts)
                  & {"build", "dist", ".git", ".venv", "venv", "__pycache__"})
    errors = []
    for doc in docs:
        text = re.sub(r"```[^\n]*\n.*?```", "", doc.read_text(encoding="utf-8"), flags=re.S)
        for link in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
            link = unquote(link.split("#")[0].strip("<>"))
            if not link or re.match(r"[A-Za-z][\w+.-]*:", link):
                continue
            if not (doc.parent / link).exists():
                errors.append(f"Link hỏng {doc.relative_to(root).as_posix()}: {link}")
    return errors, len(docs)


def example_errors(root, entries):
    errors = []
    declared = {entry["source"] for entry in entries}
    for main in (root / "examples").rglob("main.c"):
        if main.relative_to(root).as_posix() not in declared:
            errors.append("Ví dụ ngoài danh mục: " + main.relative_to(root).as_posix())
    for entry in entries:
        folder = root / entry["source"]
        for file in (folder, folder.with_name("README.md"), folder.with_name("Makefile")):
            if not file.is_file():
                errors.append("Ví dụ thiếu " + file.relative_to(root).as_posix())
    return errors


def check():
    errors = []
    settings()
    required = [
        "README.md",
        "LICENSE",
        "requirements.txt",
        "firmware/README.md",
        "examples/README.md",
        "docs/CAU_TRUC.md",
        "docs/BAT_DAU.md",
        "docs/NAP_VA_DEBUG.md",
        "docs/images/01-ket-noi.png",
        "docs/images/02-song.png",
        "docs/images/03-phep-do.png",
        "docs/images/04-goi-tin.png",
    ]
    for file in required:
        if not (ROOT / file).is_file():
            errors.append("Thiếu " + file)
    entries = catalog()
    for key in ("key", "image"):
        values = [e[key] for e in entries]
        if len(values) != len(set(values)):
            errors.append("Danh mục trùng " + key)
    errors.extend(example_errors(ROOT, entries))
    doc_errors, doc_count = documentation_errors(ROOT)
    errors.extend(doc_errors)
    provenance = json.loads((ROOT / "docs/images/provenance.json").read_text(encoding="utf-8"))
    if hashlib.sha256((ROOT / "host/gui.py").read_bytes()).hexdigest() != provenance["gui_sha256"]:
        errors.append("GUI đã đổi: kiểm/chụp lại ảnh và cập nhật provenance")
    listed = set()
    for shot in provenance["screenshots"]:
        file = ROOT / "docs/images" / shot["image"]
        listed.add(file.name)
        if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != shot["sha256"]:
            errors.append("Ảnh thiếu/sai SHA256: " + file.name)
        capture = ROOT / shot["capture"]
        if not capture.with_suffix(".bin").is_file() or hashlib.sha256(
            capture.with_suffix(".bin").read_bytes()
        ).hexdigest() != shot["capture_sha256"]:
            errors.append("Capture của ảnh thiếu/sai SHA256: " + shot["capture"])
    published = {p.name for p in (ROOT / "docs/images").iterdir() if p.suffix in (".png", ".jpg", ".svg")}
    if published != listed:
        errors.append("Ảnh công khai và provenance không khớp")
    for name in ["gui.py", "session.py"]:
        tree = ast.parse((ROOT / "host" / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = node.module if isinstance(node, ast.ImportFrom) else None
                if module in ("flash", "swd", "elfcheck", "build") or any(
                    n.name in ("catalog", "flash", "swd", "elfcheck", "build") for n in node.names
                ):
                    errors.append(f"{name} phụ thuộc công cụ nạp/danh mục ví dụ")
    for name in ["ab", "backups", "logs", "work"]:
        if (ROOT / name).exists():
            errors.append("Cây cũ còn sót: " + name)
    for error in errors:
        print("LỖI:", error)
    print(
        f"{'ĐẠT' if not errors else 'CHƯA ĐẠT'}: {len(entries)} ví dụ; {doc_count} tài liệu; GUI tách khỏi công cụ nạp."
    )
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(check())
