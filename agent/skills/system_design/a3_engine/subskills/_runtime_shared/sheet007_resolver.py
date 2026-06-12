"""Resolve 007 port-connectivity sheet by plane/intent — never scan unrelated sheets."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional, Sequence, Union

import pandas as pd

SheetSpec = Union[str, int]
AUTO_SHEET_TOKENS = frozenset({"", "0", "auto"})

RESOURCE_SHEET_NAME = "网络资源需求表"

# Sync main_flow.file_configs (address planning): command → 007 connect sheet (tuple[0]).
INTENT_CONNECT_SHEETS: dict[str, str] = {
    "计算样本面地址规划": "存储面端口互联 | 样本面端口互联",
    "计算管理面地址规划": "计算管理面端口互联",
    "计算管存面地址规划": "计算管存面端口互联",
    "计算业务面地址规划": "计算业务面端口互联",
    "存储业务面地址规划": "存储业务面端口互联",
    "计算参数面地址规划": "参数面端口互联",
    "计算超平面地址规划": "超平面端口互联",
    "存储带外管理地址规划": "存储带外管理面端口互联",
    "存储带外管理面地址规划": "存储带外管理面端口互联",
    "计算带外管理地址规划": "计算带外管理面端口互联",
    "计算带外管理面地址规划": "计算带外管理面端口互联",
    "网络带外管理地址规划": "网络带外管理面端口互联",
    "网络带外管理面地址规划": "网络带外管理面端口互联",
    "灵衢带外管理地址规划": "灵衢带外管理面端口互联",
    "灵衢带外管理面地址规划": "灵衢带外管理面端口互联",
    "合一带外管理面地址规划": "带外管理面端口互联",
    "存储样本面地址规划": "样本面端口互联 | 数据面端口互联",
    "存储管理面地址规划": "存储管理面端口互联",
    "网络业务地址规划": "其它",
}

# Alias for orchestrator / dispatch (same mapping as INTENT_CONNECT_SHEETS).
FILE_CONFIGS_CONNECT_SHEET: dict[str, str] = dict(INTENT_CONNECT_SHEETS)

# Align config.FILE_NETWORK_TYPE_CONFIG (resource row 网络平面 column)
FILE_NETWORK_TYPE_BY_CONNECT_SHEET: dict[str, str] = {
    "存储面端口互联 | 样本面端口互联": "计算样本面",
    "计算管理面端口互联": "计算管理面",
    "计算业务面端口互联": "计算业务面",
    "计算管存面端口互联": "计算管存面",
    "参数面端口互联": "计算参数面",
    "超平面端口互联": "超平面",
    "样本面端口互联 | 数据面端口互联": "存储样本面",
    "存储业务面端口互联": "存储业务面",
    "存储管理面端口互联": "存储管理面",
    "计算带外管理面端口互联": "计算带外管理面",
    "网络带外管理面端口互联": "网络带外管理面",
    "存储带外管理面端口互联": "存储带外管理面",
    "灵衢带外管理面端口互联": "灵衢带外管理面",
    "带外管理面端口互联": "合一带外管理面",
}

RESOURCE_PLANE_CONNECT_SHEETS: dict[str, str] = {
    "计算带外管理面": "计算带外管理面端口互联",
    "网络带外管理面": "网络带外管理面端口互联",
    "存储带外管理面": "存储带外管理面端口互联",
    "灵衢带外管理面": "灵衢带外管理面端口互联",
    "计算管理面": "计算管理面端口互联",
    "存储管理面": "存储管理面端口互联",
    "计算管存面": "计算管存面端口互联",
    "计算业务面": "计算业务面端口互联",
    "存储业务面": "存储业务面端口互联",
    "计算参数面": "参数面端口互联",
    "计算样本面": "存储面端口互联 | 样本面端口互联",
    "存储样本面": "样本面端口互联 | 数据面端口互联",
    "超平面": "超平面端口互联",
    "其它": "其它",
}


def _strip_layer_suffix(command: str) -> str:
    cmd = command.strip()
    for suffix in ("_L2", "_L3"):
        if cmd.endswith(suffix):
            return cmd[: -len(suffix)]
    return cmd


def connect_sheet_for_intent(intent: str) -> str:
    key = _strip_layer_suffix(intent)
    if key in INTENT_CONNECT_SHEETS:
        return INTENT_CONNECT_SHEETS[key]
    raise KeyError(f"no connect sheet mapping for intent: {intent!r}")


def connect_sheet_for_command(command: str) -> str:
    """Map L3/L2 command (with optional _L2/_L3 suffix) → 007 sheet per main_flow.file_configs."""
    return connect_sheet_for_intent(command)


def connect_sheet_for_resource_plane(plane: str) -> str:
    key = str(plane).strip()
    if key in RESOURCE_PLANE_CONNECT_SHEETS:
        return RESOURCE_PLANE_CONNECT_SHEETS[key]
    if key.endswith("面") and not key.endswith("端口互联"):
        return f"{key}端口互联"
    return key


def allowed_connect_sheets_for_plane(plane: str) -> tuple[str, ...]:
    """Single-plane allowlist for resolve_connect_sheet (no full-workbook scan)."""
    primary = connect_sheet_for_resource_plane(plane)
    out: List[str] = []
    seen: set[str] = set()
    for item in (primary,) + tuple(split_sheet_alternatives(primary)):
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return tuple(out)


def resource_plane_for_connect_sheet(connect_sheet: str) -> str:
    """Map 007 sheet name → 资源表 网络平面 row (align FILE_NETWORK_TYPE_CONFIG)."""
    key = str(connect_sheet).strip()
    if key in FILE_NETWORK_TYPE_BY_CONNECT_SHEET:
        return FILE_NETWORK_TYPE_BY_CONNECT_SHEET[key]
    if key in RESOURCE_PLANE_CONNECT_SHEETS.values():
        for plane, sheet in RESOURCE_PLANE_CONNECT_SHEETS.items():
            if sheet == key:
                return plane
    return key


def resolve_resource_sheet(path: Path, sheet_spec: object = RESOURCE_SHEET_NAME) -> SheetSpec:
    """Prefer 网络资源需求表 — align utils.get_net_to_gateway_resource_info / cc_glm_io."""
    sn = str(sheet_spec).strip() if sheet_spec is not None else RESOURCE_SHEET_NAME
    names = list(pd.ExcelFile(path).sheet_names)

    if sn.lower() not in AUTO_SHEET_TOKENS and not sn.isdigit():
        if sn in names:
            return sn
        raise ValueError(
            f"resource: sheet {sn!r} not in workbook; available: {names}"
        )

    if RESOURCE_SHEET_NAME in names:
        return RESOURCE_SHEET_NAME

    if sn.isdigit():
        idx = int(sn)
        if 0 <= idx < len(names):
            return idx

    for name in names:
        try:
            df = pd.read_excel(path, sheet_name=name, nrows=2, header=0)
            if "网络平面" in df.columns:
                return name
        except Exception:
            continue

    return 0


def split_sheet_alternatives(spec: str) -> List[str]:
    return [part.strip() for part in str(spec).split("|") if part.strip()]


def expand_allowed_sheets(allowed: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for item in allowed:
        for part in split_sheet_alternatives(str(item)):
            if part not in seen:
                seen.add(part)
                out.append(part)
    return out


def normalize_sheet_spec(sheet_spec: object, *, default_sheet: str) -> str:
    sn = str(sheet_spec).strip() if sheet_spec is not None else ""
    if sn.lower() in AUTO_SHEET_TOKENS:
        return default_sheet
    return sn


def _coerce_candidate(spec: str, workbook_names: Sequence[str]) -> Optional[SheetSpec]:
    if spec.isdigit():
        idx = int(spec)
        if 0 <= idx < len(workbook_names):
            return idx
        return None
    if spec in workbook_names:
        return spec
    return None


def resolve_connect_sheet(
    path: Path,
    sheet_spec: object,
    *,
    allowed_sheets: Sequence[str],
    probe: Optional[Callable[[Path, SheetSpec], bool]] = None,
) -> SheetSpec:
    """Pick one 007 sheet from *allowed_sheets* only (no full-workbook scan)."""
    if not allowed_sheets:
        raise ValueError("allowed_sheets is empty")

    expanded = expand_allowed_sheets(allowed_sheets)
    primary = expanded[0]
    norm = normalize_sheet_spec(sheet_spec, default_sheet=primary)
    workbook_names = list(pd.ExcelFile(path).sheet_names)

    if norm.lower() not in AUTO_SHEET_TOKENS:
        candidates = expand_allowed_sheets((norm,))
    else:
        candidates = expanded

    errors: List[str] = []
    for name in candidates:
        resolved = _coerce_candidate(name, workbook_names)
        if resolved is None:
            parts = split_sheet_alternatives(name)
            if len(parts) > 1:
                for wb_name in workbook_names:
                    if all(p in str(wb_name) for p in parts):
                        resolved = wb_name
                        break
        if resolved is None:
            errors.append(f"{name!r}: not in workbook")
            continue
        if probe is not None and not probe(path, resolved):
            errors.append(f"{resolved!r}: probe failed")
            continue
        return resolved

    raise ValueError(
        "007: 无法在限定平面 sheet 中解析端口互联表。\n"
        f"  - 仅尝试: {candidates}\n"
        f"  - 工作簿 sheet: {workbook_names}\n"
        f"  - 建议: 用 --sheet007 / --sheet-connect 指定上表之一。\n"
        + ("  - 明细: " + "; ".join(errors[-8:]) if errors else "")
    )
