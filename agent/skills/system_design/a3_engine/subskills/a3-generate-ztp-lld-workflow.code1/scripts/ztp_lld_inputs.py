"""ZTP LLD 输入件扫描规则。"""

from __future__ import annotations

from pathlib import Path

SCAN_RULES = {
    "cpm": (["超平面", "规划"], ["网关"]),
    "manage": (["灵衢", "带外", "地址", "规划"], ["网关"]),
    "location": (["004", "设备位置"], []),
}

LABELS = {
    "cpm": "A3超平面网络规划",
    "manage": "A3灵衢带外管理地址规划",
    "location": "建模仿真输出文档004-设备位置表",
}


def find_excel(rule_key: str, scan_dir: Path) -> Path | None:
    must, exclude = SCAN_RULES[rule_key]
    candidates: list[Path] = []
    for path in sorted(scan_dir.rglob("*.xlsx")):
        if path.name.startswith("~$"):
            continue
        name = path.name
        if not all(k in name for k in must):
            continue
        if any(k in name for k in exclude):
            continue
        candidates.append(path)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)
