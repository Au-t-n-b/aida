# -*- coding: utf-8 -*-
"""调测报告汇总（对标 CPCIA Agent ``report_handler.export_word_report``）。

遍历 task_catalog 登记的**全部命令**，每个命令找它在 ``results/index.json`` 的
**最新一次** run：测过的填摘要+设备级明细，未测的标「未测试」（内容留空）。
输出一份多 sheet xlsx：

    总览 sheet「调测总览」：每命令一行（命令/模块/是否测过/通过/失败/最近任务/时间/报告）
    明细 sheet（每个测过的命令一个）：设备级 IP × 结果

与 Agent 对应：Agent 用 docx 模板预置全部章节、只填有结果的、最后 clear_empty_placeholder
清空占位；这里改 xlsx 形态——总览行天然覆盖全部命令，未测行留空即等价「占位」。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

_HERE = Path(__file__).resolve()
_SHARED = _HERE.parent
for _p in (str(_SHARED / "task_catalog" / "scripts"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from task_catalog import MODULE_TITLES, TASKS  # noqa: E402

OVERVIEW_SHEET = "调测总览"
AGGREGATE_NAME = "调测报告汇总_{0}.xlsx"
AGGREGATE_LATEST = "调测报告汇总_latest.xlsx"


def _skill_root(skill_dir: str | Path) -> Path:
    return Path(skill_dir).resolve()


def _results_root(skill_dir: str | Path) -> Path:
    return _skill_root(skill_dir) / "ProjectData" / "results"


def _load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _latest_run_by_type(skill_dir: str | Path) -> dict[str, dict[str, Any]]:
    """task_type → 最新一次 run（按 index.json 顺序，后出现的覆盖）。"""
    idx = _load_json(_results_root(skill_dir) / "index.json")
    runs = idx.get("runs") if isinstance(idx, dict) else None
    out: dict[str, dict[str, Any]] = {}
    if isinstance(runs, list):
        for entry in runs:
            if isinstance(entry, dict) and entry.get("taskType"):
                out[str(entry["taskType"])] = entry  # 后者覆盖前者=最新
    return out


def _safe_sheet_name(name: str) -> str:
    bad = '[]:*?/\\'
    s = "".join("_" if ch in bad else ch for ch in str(name or ""))
    return s[:31] or "sheet"


def _device_rows_from_receipt(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    """从 receipt 提取设备级明细（best-effort）：优先 listData，退化为下发设备列表。"""
    last = receipt.get("lastQuery") if isinstance(receipt, dict) else {}
    data = last.get("data") if isinstance(last, dict) else {}
    rows: list[dict[str, Any]] = []
    list_data = data.get("listData") if isinstance(data, dict) else None
    if isinstance(list_data, list) and list_data:
        for node in list_data:
            if not isinstance(node, dict):
                continue
            ip = node.get("deviceId") or node.get("deviceIp") or node.get("nodeIp") or node.get("ip") or ""
            res = node.get("optResult")
            check = node.get("checkResult")
            if res is not None:
                status = "通过" if str(res) == "1" else "失败"
            elif check is not None:
                status = "失败" if str(check).strip() == "检查失败" else "通过"
            else:
                status = str(node.get("taskStatus") or node.get("status") or "")
            rows.append({"设备IP": str(ip), "结果": status})
        return rows
    # 退化：只知道下发了哪些设备，没有逐台明细
    body = receipt.get("executeBody") if isinstance(receipt, dict) else {}
    if isinstance(body, dict):
        for fld in ("serviceDeviceIds", "switchesDeviceIds", "deviceIds", "nodeList"):
            val = body.get(fld)
            if isinstance(val, list) and val:
                for x in val:
                    ip = x.get("deviceIp") if isinstance(x, dict) else x
                    rows.append({"设备IP": str(ip), "结果": "（无逐台明细）"})
                break
    return rows


def build_aggregate(skill_dir: str | Path, *, task_types: list[str] | None = None) -> dict[str, Any]:
    """生成汇总 xlsx，返回路径与统计。

    task_types: 若指定，仅汇总这些命令（AIDA 接入的四条 init_install）；
                默认遍历 TASKS 全表（与 nanobot driver report_aggregate 一致）。
    """
    latest = _latest_run_by_type(skill_dir)
    overview_rows: list[dict[str, Any]] = []
    detail_sheets: list[tuple[str, list[dict[str, Any]]]] = []
    tested = 0

    if task_types:
        pairs = [(t, TASKS[t]) for t in task_types if t in TASKS]
    else:
        pairs = list(TASKS.items())

    for task_type, spec in pairs:
        label = spec.labels[0] if spec.labels else task_type
        module_title = MODULE_TITLES.get(spec.module, spec.module)
        run = latest.get(task_type)
        if not run:
            overview_rows.append({
                "模块": module_title,
                "命令": label,
                "命令名": task_type,
                "是否测过": "未测试",
                "通过": "",
                "失败": "",
                "最近任务": "",
                "完成时间": "",
                "报告路径": "",
            })
            continue

        tested += 1
        receipt = _load_json(Path(str(run.get("receiptPath") or ""))) or {}
        data = (receipt.get("lastQuery") or {}).get("data") or {}
        succ = data.get("successNum")
        fail = data.get("failNum")
        overview_rows.append({
            "模块": module_title,
            "命令": label,
            "命令名": task_type,
            "是否测过": "已测试",
            "通过": succ if succ is not None else "",
            "失败": fail if fail is not None else "",
            "最近任务": run.get("taskName") or "",
            "完成时间": run.get("finishedAt") or "",
            "报告路径": run.get("reportPath") or "",
        })
        dev_rows = _device_rows_from_receipt(receipt)
        if dev_rows:
            detail_sheets.append((task_type, dev_rows))

    out_dir = _results_root(skill_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / AGGREGATE_NAME.format(stamp)
    latest_path = out_dir / AGGREGATE_LATEST

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        cols = ["模块", "命令", "命令名", "是否测过", "通过", "失败", "最近任务", "完成时间", "报告路径"]
        pd.DataFrame(overview_rows, columns=cols).to_excel(writer, sheet_name=OVERVIEW_SHEET, index=False)
        used_names: set[str] = {OVERVIEW_SHEET}
        for task_type, rows in detail_sheets:
            name = _safe_sheet_name(task_type)
            base = name
            i = 1
            while name in used_names:
                name = f"{base[:28]}_{i}"
                i += 1
            used_names.add(name)
            pd.DataFrame(rows, columns=["设备IP", "结果"]).to_excel(writer, sheet_name=name, index=False)

    import shutil

    shutil.copy2(out_path, latest_path)

    return {
        "path": str(out_path.resolve()),
        "latestPath": str(latest_path.resolve()),
        "fileName": out_path.name,
        "latestName": AGGREGATE_LATEST,
        "totalCommands": len(pairs),
        "testedCommands": tested,
        "untestedCommands": len(pairs) - tested,
        "detailSheets": len(detail_sheets),
    }
