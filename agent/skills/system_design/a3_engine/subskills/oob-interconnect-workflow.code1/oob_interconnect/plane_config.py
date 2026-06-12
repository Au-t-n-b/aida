"""平面配置加载：可由 JSON 文件覆盖默认值。"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from oob_interconnect.constants import DEFAULT_PLANE_CONFIG


def load_plane_config(path: str | Path | None = None) -> dict[str, dict[str, str]]:
    """读取平面配置。若 ``path`` 为空则返回默认配置的深拷贝。

    JSON 格式：
    ``{ "<plan_name>": {"sheet_name": "...", "keyword": "...", "network_type": "..."}, ... }``

    兼容旧格式：若未提供 ``sheet_name``，则使用 JSON key 作为端口连线表 sheet 名。
    """
    if not path:
        return copy.deepcopy(DEFAULT_PLANE_CONFIG)
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"平面配置文件不存在: {p}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not raw:
        raise ValueError("平面配置文件需为非空 JSON 对象")
    cfg: dict[str, dict[str, str]] = {}
    for plan_name, val in raw.items():
        if not isinstance(val, dict):
            raise ValueError(f"平面 '{plan_name}' 配置需为对象")
        kw = val.get("keyword")
        nt = val.get("network_type")
        if not kw or not nt:
            raise ValueError(f"平面 '{plan_name}' 必须含 keyword 与 network_type")
        cfg[str(plan_name)] = {
            "sheet_name": str(val.get("sheet_name") or plan_name),
            "keyword": str(kw),
            "network_type": str(nt),
        }
        peer_keyword = val.get("peer_keyword")
        if peer_keyword:
            cfg[str(plan_name)]["peer_keyword"] = str(peer_keyword)
    return cfg
