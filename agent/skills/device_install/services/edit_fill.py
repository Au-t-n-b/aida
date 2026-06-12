"""
edit_fill · EditableTable「一键填写」预填值生成（device_install 三处编辑门）。

由 step 的 need_edit.fillRows 下发给前端；用户点「一键填写」后合并到可编辑列。

⚠️ 仅为本地/演示快速跑通流程用的占位值（责任人姓名 / 责任主体 / ESN）。
正式使用时应由用户填写真实数据，或由数据中心《责任人信息表》合并真实责任人。
"""
from __future__ import annotations

from ._common import as_str

_DEMO_PRINCIPALS = ("张三", "李四", "王五", "赵六", "孙七", "周八")
_DEMO_ORGS = ("华为", "分包商")


def fill_principal_rows(rows: list[dict]) -> list[dict]:
    """责任人填报：为每行生成责任人姓名 + 责任主体（占位，演示用）。"""
    out: list[dict] = []
    for i, r in enumerate(rows):
        row = dict(r)
        row["principal"] = as_str(r.get("principal")) or _DEMO_PRINCIPALS[i % len(_DEMO_PRINCIPALS)]
        row["principal_org"] = as_str(r.get("principal_org")) or _DEMO_ORGS[i % len(_DEMO_ORGS)]
        out.append(row)
    return out


def fill_tasks_rows(rows: list[dict]) -> list[dict]:
    """全量任务复核：保留已有值，空的可编辑列用责任人/主体兜底（占位，演示用）。"""
    out: list[dict] = []
    for i, r in enumerate(rows):
        row = dict(r)
        if not as_str(row.get("principal")):
            row["principal"] = _DEMO_PRINCIPALS[i % len(_DEMO_PRINCIPALS)]
        if not as_str(row.get("principal_org")):
            row["principal_org"] = _DEMO_ORGS[i % len(_DEMO_ORGS)]
        out.append(row)
    return out


def fill_dispatch_select_all(rows: list[dict]) -> list[dict]:
    """计划下发：一键全选待下发条目（保留行内其它列，仅改 selected）。"""
    out: list[dict] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        row = dict(r)
        row["selected"] = True
        out.append(row)
    return out


def fill_dispatch_deselect_all(rows: list[dict]) -> list[dict]:
    """计划下发：一键取消全部勾选（保留行内其它列）。"""
    out: list[dict] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        row = dict(r)
        row["selected"] = False
        out.append(row)
    return out


def fill_esn_rows(rows: list[dict]) -> list[dict]:
    """ESN 录入：按设备信息生成唯一 ESN（占位，演示用，格式 HW-型号-机柜U位）。"""
    out: list[dict] = []
    seen: set[str] = set()
    for i, r in enumerate(rows):
        row = dict(r)
        existing = as_str(row.get("ESN"))
        if existing:
            seen.add(existing)
            out.append(row)
            continue
        model = as_str(row.get("设备型号")).replace(" ", "")[:12] or "DEV"
        col = as_str(row.get("所属机柜")) or "C00"
        u = as_str(row.get("安装起始U位")) or str(i + 1)
        base = f"HW-{model}-{col}U{u}"
        esn = base
        n = 0
        while esn in seen:
            n += 1
            esn = f"{base}-{n}"
        seen.add(esn)
        row["ESN"] = esn
        out.append(row)
    return out
