"""JSON 落盘的两个必备动作：读得回、写不坏。

写坏的定义是「写到一半断电，留下半个文件」，所以一律先写临时文件再 `os.replace`。
`os.replace` 在 Windows 上是原子的（同一个卷内），不会出现「删了旧的、新的还没到位」。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

BACKUP_SUFFIX = ".bak"


def load_json(path: Path) -> dict | None:
    """读 JSON；文件不存在、读不动、内容不是对象，一律返回 None。

    先读主文件，失败了再读 `.bak`——配置文件被手改坏时，退回上一次的完整内容，
    比直接掉进默认值好：用户改坏了一个逗号，不该连作息一起丢。
    """
    for candidate in (path, path.with_suffix(path.suffix + BACKUP_SUFFIX)):
        try:
            raw = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(data, dict):
            return data
    return None


def save_json(path: Path, data: dict) -> Path:
    """原子写，并把上一版留成 `.bak`。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2)

    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")

    if path.exists():
        backup = path.with_suffix(path.suffix + BACKUP_SUFFIX)
        try:
            os.replace(path, backup)
        except OSError:
            pass  # 备份失败不该拦住保存

    os.replace(tmp, path)
    return path
