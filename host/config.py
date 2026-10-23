"""Cấu hình host; key tiếng Anh, đường dẫn tương đối tính từ gốc dự án.

HALA_CONFIG chọn một JSON thay thế; configs/local.json ghi đè cấu hình chuẩn.
Địa chỉ thanh ghi/layout firmware là ABI, không phải tùy chọn người dùng.
"""

import copy
import json
import os
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def merge(base, override):
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key not in result:
            raise ValueError(f"Key cấu hình không được hỗ trợ: {key}")
        if isinstance(result[key], dict):
            if not isinstance(value, dict):
                raise ValueError(f"Cấu hình {key} phải là object")
            result[key] = merge(result[key], value)
        else:
            result[key] = value
    return result


def settings():
    value = json.loads((PROJECT / "configs/lab.json").read_text(encoding="utf-8"))
    custom = os.environ.get("HALA_CONFIG")
    local = Path(custom).expanduser() if custom else PROJECT / "configs/local.json"
    if custom or local.exists():
        value = merge(value, json.loads(local.read_text(encoding="utf-8")))
    if not isinstance(value["swd_khz"], int) or not 1 <= value["swd_khz"] <= 1000:
        raise ValueError("swd_khz phải trong khoảng 1..1000 kHz")
    if value["gpio"] != {"port": "B", "device_tx": 0, "bus_rx": 8, "host_peer": 10}:
        raise ValueError(
            "Pin hiện là ABI fixture PB0/PB8/PB10; đổi pin cần sửa và kiểm thử firmware monitor/ứng dụng"
        )
    endpoint = value["gdb_endpoint"].rsplit(":", 1)
    if (
        len(endpoint) != 2
        or endpoint[0] not in ("127.0.0.1", "localhost")
        or not endpoint[1].isdigit()
        or not 1024 <= int(endpoint[1]) <= 65535
    ):
        raise ValueError(
            "gdb_endpoint phải là localhost:port hoặc 127.0.0.1:port, port 1024..65535"
        )
    return value


def path(key):
    value = Path(settings()[key]).expanduser()
    return value if value.is_absolute() else PROJECT / value


def tool(key):
    return settings()["tools"][key]


def catalog():
    return json.loads((PROJECT / "configs/examples.json").read_text(encoding="utf-8"))[
        "examples"
    ]
