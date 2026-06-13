"""读取 DataGrid.xlsx，返回 432 个有序智算服务器名称列表。

DataGrid.xlsx 列结构：
  ID | 名称 | 型号 | 拓扑层级 | 设备角色 | 机柜名称 | 机房名称 | 坐标 | 起始U位 | 安装方向

排序规则：按名称中的 SP 编号（SP01..SP09）与末尾序号（01..48）双键升序排列，
保证 SP01-AT900A3-01..48 排在最前，SP09-AT900A3-01..48 排在最后，
与 leaf 编号 001..054 的顺序对齐（每个 SP = 48 台 server，对应 6 台 leaf）。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import openpyxl
except ImportError:
    openpyxl = None  # type: ignore[assignment]


def _parse_name_key(name: str) -> tuple[int, int]:
    """从 SPxx-AT900A3-yy 提取 (sp_num, seq_num) 用于排序。未匹配返回 (99999, 99999)。"""
    m = re.match(r"SP(\d+)-.*?-(\d+)$", name.strip())
    if m:
        return int(m.group(1)), int(m.group(2))
    m2 = re.search(r"SP(\d+)", name)
    seq = re.search(r"-(\d+)$", name)
    sp = int(m2.group(1)) if m2 else 99999
    s = int(seq.group(1)) if seq else 99999
    return sp, s


def read_servers(xlsx_path: str | Path) -> list[dict[str, Any]]:
    """读取 DataGrid.xlsx，返回按 SP 编号排序的服务器信息列表。

    每条记录：{"name": str, "model": str, "cabinet": str, "room": str}
    """
    if openpyxl is None:
        raise ImportError("openpyxl not installed; run: pip install openpyxl")

    path = Path(xlsx_path)
    if not path.exists():
        raise FileNotFoundError(f"DataGrid.xlsx 不存在: {path}")

    wb = openpyxl.load_workbook(str(path), data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError("DataGrid.xlsx 为空")

    # 解析表头，兼容列名变体
    header = [str(c).strip() if c is not None else "" for c in rows[0]]

    def col_idx(*keywords: str) -> int:
        for kw in keywords:
            for i, h in enumerate(header):
                if kw in h:
                    return i
        return -1

    idx_name = col_idx("名称", "name")
    idx_model = col_idx("型号", "model")
    idx_role = col_idx("设备角色", "role")
    idx_cabinet = col_idx("机柜", "cabinet")
    idx_room = col_idx("机房", "room")

    if idx_name < 0:
        raise ValueError(f"DataGrid.xlsx 未找到'名称'列，表头={header}")

    servers: list[dict[str, Any]] = []
    for row in rows[1:]:
        if not any(row):
            continue
        name = str(row[idx_name]).strip() if idx_name >= 0 and row[idx_name] is not None else ""
        model = str(row[idx_model]).strip() if idx_model >= 0 and row[idx_model] is not None else ""
        role = str(row[idx_role]).strip() if idx_role >= 0 and row[idx_role] is not None else ""
        cabinet = str(row[idx_cabinet]).strip() if idx_cabinet >= 0 and row[idx_cabinet] is not None else ""
        room = str(row[idx_room]).strip() if idx_room >= 0 and row[idx_room] is not None else ""

        if not name:
            continue
        # 过滤非智算服务器行（如有杂行）
        if role and "服务器" not in role and "server" not in role.lower():
            continue

        servers.append({"name": name, "model": model, "role": role, "cabinet": cabinet, "room": room})

    # 按 SP 编号 + 序号排序
    servers.sort(key=lambda r: _parse_name_key(r["name"]))

    return servers


def server_names(xlsx_path: str | Path) -> list[str]:
    """仅返回有序 server 名称列表。"""
    return [s["name"] for s in read_servers(xlsx_path)]


if __name__ == "__main__":
    import json
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else r"D:\Project\AIDA\相关文件\DataGrid.xlsx"
    names = server_names(path)
    print(f"total servers: {len(names)}")
    print("first 5:", names[:5])
    print("last 5:", names[-5:])
    # 验证 SP 分布
    from collections import Counter
    sp_dist = Counter(re.match(r"SP\d+", n).group() for n in names if re.match(r"SP\d+", n))
    print("SP distribution:", dict(sorted(sp_dist.items())))
