"""sentinel · run_id 绑定的磁盘留痕（防跨 run 假跳过）

副作用步（combo_create / cabinet_move / handoff）写 RunTime/*.json 时带上 run_id；
full_restart 同 run 内可跳过重复 API，新 /start（新 run_id）或旧文件无 run_id 则必真跑。
"""
from __future__ import annotations

import json
from pathlib import Path


def read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except Exception:
        return {}


def is_same_run(record: dict, run_id: str) -> bool:
    """sentinel 是否属于当前 run（无 run_id 的旧文件视为不匹配）。"""
    rid = record.get("run_id")
    return bool(rid) and rid == run_id
