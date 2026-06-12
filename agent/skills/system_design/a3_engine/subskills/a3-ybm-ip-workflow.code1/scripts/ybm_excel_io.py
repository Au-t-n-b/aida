"""YBM 离线 Excel IO。

- 自动探测输入 Excel（007 / 资源表）
- 读取 007：解析「接入交换机 → 服务器列表」
- 读取资源表：按网络平面匹配一行规划参数
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is required. Install: pip install pandas openpyxl", file=sys.stderr)
    raise SystemExit(2)

# Align main_flow.file_configs「计算样本面地址规划」→ 存储面端口互联 | 样本面端口互联
SHEET_007_DEFAULT = "存储面端口互联 | 样本面端口互联"
SHEET_RES_DEFAULT = "网络资源需求表"
SHEET_RES_DEFAULT_INDEX = SHEET_RES_DEFAULT


def resolve_local_only(p: Path) -> Path:
    if p.is_absolute():
        return p
    return (Path.cwd() / p).resolve()


def require_under_cwd(file_path: Path, label: str) -> Path:
    cwd = Path.cwd().resolve()
    resolved = resolve_local_only(file_path)
    try:
        resolved.relative_to(cwd)
    except Exception:
        raise SystemExit(
            f"ERROR: {label} must be located under current working directory.\n"
            f"  resolved: {resolved}\n"
            f"  cwd:      {cwd}"
        )
    return resolved


def list_excel_files_in_cwd() -> List[Path]:
    cwd = Path.cwd().resolve()
    files: List[Path] = []
    for ext in (".xlsx", ".xls", ".XLSX", ".XLS"):
        files.extend([p for p in cwd.rglob(f"*{ext}") if p.is_file()])
    uniq: List[Path] = []
    seen = set()
    for p in files:
        if p.name.startswith("~$"):
            continue
        rp = str(p.resolve())
        if rp in seen:
            continue
        seen.add(rp)
        uniq.append(p)
    return uniq


def autodetect_007_in_cwd() -> Path:
    for p in list_excel_files_in_cwd():
        n = p.name
        if ("007" in n) or ("端口连线" in n) or ("端口互联" in n):
            return p
    raise SystemExit("ERROR: cannot autodetect 007 excel in current working directory.")


def autodetect_resource_in_cwd() -> Path:
    for p in list_excel_files_in_cwd():
        n = p.name
        if ("项目信息收集" in n) or ("资源" in n) or ("信息收集表" in n):
            return p
    raise SystemExit("ERROR: cannot autodetect resource excel in current working directory.")


def find_header_row(df: "pd.DataFrame", needle: str = "设备命名") -> int:
    for i in range(len(df.index)):
        row = df.iloc[i].astype(str).tolist()
        if any(needle in (c or "") for c in row):
            return i
    raise ValueError(f"cannot locate header row by {needle!r}")


def fuzzy_get(row: "pd.Series", needle: str) -> Optional[object]:
    for k in row.index:
        if needle in str(k):
            return row.get(k)
    return None


def _subskills_root() -> Path:
    return Path(__file__).resolve().parents[2]


def read_resource_row_for_plane(
    path_resource: Path,
    sheet_spec: object,
    network_plane: str,
) -> "pd.Series":
    root = _subskills_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from _runtime_shared.sheet007_resolver import resolve_resource_sheet

    resolved = resolve_resource_sheet(path_resource, sheet_spec)
    df = pd.read_excel(path_resource, sheet_name=resolved, header=0)
    if "网络平面" not in df.columns:
        cols = [str(c) for c in df.columns.tolist()]
        raise ValueError(
            "resource: 缺少列「网络平面」。\n"
            f"  - 请在资源表中补齐该列，或确认读取的是正确的 sheet (sheet={resolved!r})。\n"
            f"  - 当前列名: {cols}"
        )
    rows = df[df["网络平面"].astype(str) == str(network_plane)]
    if rows.empty:
        planes = (
            df["网络平面"].astype(str).dropna().map(lambda x: x.strip()).replace("", pd.NA).dropna().unique().tolist()
            if "网络平面" in df.columns
            else []
        )
        preview = planes[:20]
        raise ValueError(
            "resource: 找不到匹配的网络平面行。\n"
            f"  - 期望: 网络平面 == {network_plane!r} (sheet={resolved!r})\n"
            f"  - 建议: 修改参数 --network-plane 为资源表中真实的取值，或切换 --sheet-res-index。\n"
            f"  - 资源表中可见网络平面(前{len(preview)}项): {preview}"
        )
    return rows.iloc[0]


def read_007_leaf_to_servers(
    path_007: Path,
    sheet_name: str,
    *,
    server_substring: str = "",
    network_plane: str = "计算样本面",
) -> Dict[str, List[str]]:
    """首列服务器、末列接入交换机；去掉服务器列含 LEAF/SPINE 的行；可选仅保留服务器名含 server_substring 的行。"""

    def _read_one(sheet: object) -> Dict[str, List[str]]:
        raw = pd.read_excel(path_007, sheet_name=sheet, header=None, dtype=str).fillna("")
        try:
            header_idx = find_header_row(raw, "设备命名")
        except Exception as e:
            raise ValueError(
                "007: 未找到包含「设备命名」的表头行。\n" "  - 请确认 007 表该 sheet 中存在「设备命名」字样，且其下方为数据区。"
            ) from e
        data = raw.iloc[header_idx + 1 :].copy()
        if data.shape[1] < 2:
            raise ValueError("007 sheet: expected at least 2 columns (server, access switch)")

        server_col = data.columns[0]
        leaf_col = data.columns[data.shape[1] - 1]
        data = data[[server_col, leaf_col]]
        data.columns = ["计算服务器", "接入交换机"]
        data["计算服务器"] = data["计算服务器"].astype(str).str.strip()
        data["接入交换机"] = data["接入交换机"].astype(str).str.strip()
        data = data[(data["计算服务器"] != "") & (data["接入交换机"] != "")]
        data = data[~data["计算服务器"].str.contains(r"LEAF|SPINE", case=False, regex=True)]
        if server_substring:
            before = len(data)
            data = data[data["计算服务器"].str.contains(re.escape(server_substring), regex=True, na=False)]
            if data.empty and before > 0:
                samples = (
                    raw.iloc[header_idx + 1 :, 0]
                    .astype(str)
                    .str.strip()
                    .replace("", pd.NA)
                    .dropna()
                    .head(15)
                    .tolist()
                )
                raise ValueError(
                    "007: 服务器名过滤后无可用数据。\n"
                    f"  - 当前 --server-substring={server_substring!r} 未命中首列服务器名\n"
                    "  - 建议: 将 --server-substring 改为能命中的子串，或不传该参数（不过滤）。\n"
                    f"  - 首列服务器名示例(前{len(samples)}条): {samples}"
                )

        out: Dict[str, List[str]] = {}
        for leaf, g in data.groupby("接入交换机", sort=False):
            servers = [s for s in g["计算服务器"].tolist() if s]
            if servers:
                out[str(leaf)] = servers
        if not out:
            raise ValueError(
                "007: 无法得到「接入交换机 → 服务器」映射。\n"
                "  - 规则: 首列=服务器名，末列=接入交换机名；会剔除服务器名包含 LEAF/SPINE 的行；可选再按 --server-substring 过滤。\n"
                "  - 建议: 检查该 sheet 是否为业务面/计算服务器连线页；或用 --sheet007 指定正确 sheet。"
            )
        return out

    root = _subskills_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from _runtime_shared.sheet007_resolver import (
        allowed_connect_sheets_for_plane,
        resolve_connect_sheet,
    )

    resolved = resolve_connect_sheet(
        path_007,
        sheet_name,
        allowed_sheets=allowed_connect_sheets_for_plane(network_plane),
    )
    return _read_one(resolved)


def excel_sheet_title(name: str, max_len: int = 31) -> str:
    s = str(name).strip() or "Sheet1"
    return s[:max_len]

