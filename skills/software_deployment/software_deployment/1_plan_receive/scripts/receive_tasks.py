# -*- coding: utf-8 -*-
"""
步骤 ①：接收作业管理二级任务（对齐 zhgk scene-filter/scripts 用法）。

```bash
python software_deployment/1_plan_receive/scripts/receive_tasks.py
```
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def _plan_dir(skill_root: Path) -> Path:
    return skill_root / "ProjectData" / "plan"


def _text(v: Any) -> str:
    return str(v or "").strip()


def _find_col(header: list[str], *candidates: str) -> int | None:
    norm = [h.replace(" ", "").replace("_", "").lower() for h in header]
    for cand in candidates:
        c = cand.replace(" ", "").replace("_", "").lower()
        for i, h in enumerate(norm):
            if h == c:
                return i
    return None


def load_second_tasks_from_json(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    tasks = raw.get("tasks") if isinstance(raw, dict) else raw
    if isinstance(tasks, list):
        return [t for t in tasks if isinstance(t, dict)]
    return []


def load_second_tasks_from_xlsx(path: Path) -> list[dict[str, Any]]:
    try:
        from openpyxl import load_workbook  # type: ignore
    except Exception as e:
        raise RuntimeError(f"解析 Excel 失败：未安装 openpyxl（{e}）") from e

    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.active
        rows = ws.iter_rows(values_only=True)
        first = next(rows, None)
        if not first:
            return []
        header = [_text(v) for v in list(first)]
        idx_id = _find_col(header, "serial_number", "序列号", "任务编号", "id")
        idx_activity = _find_col(header, "二级活动", "活动名称", "activity_name", "activityName")
        idx_mu = _find_col(header, "管理单元", "POD", "management_unit", "managementUnit", "机房")
        idx_principal = _find_col(header, "责任人", "负责人", "principal")
        idx_status = _find_col(header, "任务状态", "status", "task_status")
        idx_start = _find_col(header, "计划开始日期", "开始日期", "开始时间", "start_date", "startDate")
        idx_end = _find_col(header, "计划结束日期", "结束日期", "结束时间", "end_date", "endDate")
        idx_device = _find_col(
            header,
            "设备清单",
            "设备型号&数量的列表",
            "device_list",
            "deviceList",
            "device_type_quantity_list",
            "raw_equipment_list",
        )
        if idx_activity is None:
            return []

        out: list[dict[str, Any]] = []
        for r in rows:
            row = list(r or [])
            activity = _text(row[idx_activity]) if idx_activity < len(row) else ""
            if not activity:
                continue
            mu = _text(row[idx_mu]) if idx_mu is not None and idx_mu < len(row) else ""
            rid = _text(row[idx_id]) if idx_id is not None and idx_id < len(row) else ""
            if not rid:
                rid = f"L2-{len(out) + 1:04d}"
            item: dict[str, Any] = {
                "id": rid,
                "activityName": activity,
                "managementUnit": mu,
                "principal": _text(row[idx_principal]) if idx_principal is not None and idx_principal < len(row) else "",
                "status": _text(row[idx_status]) if idx_status is not None and idx_status < len(row) else "待接收",
                "targetAgent": "software_deployment",
            }
            if idx_start is not None and idx_start < len(row):
                item["startDate"] = _text(row[idx_start])
            if idx_end is not None and idx_end < len(row):
                item["endDate"] = _text(row[idx_end])
            if idx_device is not None and idx_device < len(row):
                device_val = _text(row[idx_device])
                if device_val:
                    item["deviceList"] = device_val
                    item["device_type_quantity_list"] = device_val
            out.append(item)
        return assign_second_task_ids(out)
    finally:
        wb.close()


def assign_second_task_ids(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """为二级任务生成稳定 serial_number（对齐 Agent：每条二级独立 SN，供三级绑定）。"""
    out: list[dict[str, Any]] = []
    for i, raw in enumerate(tasks):
        item = dict(raw)
        existing = str(item.get("id") or item.get("serial_number") or "").strip()
        if existing and not existing.startswith("L2-"):
            item["id"] = existing
            item["serial_number"] = existing
            out.append(item)
            continue
        activity = str(item.get("activityName") or "").strip()
        start = str(item.get("startDate") or item.get("start_date") or "").strip()
        end = str(item.get("endDate") or item.get("end_date") or "").strip()
        device = str(item.get("deviceList") or item.get("device_type_quantity_list") or "").strip()
        mu = str(item.get("managementUnit") or item.get("management_unit") or "").strip()
        principal = str(item.get("principal") or "").strip()
        key = f"{activity}|{start}|{end}|{device}|{mu}|{principal}|{i}"
        sn = hashlib.md5(key.encode("utf-8")).hexdigest()
        item["id"] = sn
        item["serial_number"] = sn
        out.append(item)
    return out


def _load_from_slot(skill_root: Path) -> tuple[list[dict[str, Any]], Path | None]:
    rt = skill_root / "runtime"
    if str(rt) not in sys.path:
        sys.path.insert(0, str(rt))
    from paths import resolve_slot  # noqa: WPS433

    slot = resolve_slot("second_level_tasks", skill_root=skill_root)
    primary = str(slot.get("primary") or "").strip()
    if not primary:
        return [], None
    p = Path(primary)
    if not p.is_file():
        return [], p
    if p.suffix.lower() == ".xlsx":
        return load_second_tasks_from_xlsx(p), p
    tasks = load_second_tasks_from_json(p)
    return assign_second_task_ids(tasks), p


def load_second_tasks(skill_root: Path, *, prefer_inbox: bool = False) -> list[dict[str, Any]]:
    """加载二级任务。临时阶段优先 ``plan_receive/部署调测任务列表.xlsx``（约 333 条）。"""
    root = skill_root.resolve()
    slot_tasks, slot_path = _load_from_slot(root)

    if prefer_inbox and slot_tasks:
        return slot_tasks

    # MVP：收件箱 xlsx 为二级真值（覆盖旧的 2 条 json 快照）
    if slot_path and slot_path.suffix.lower() == ".xlsx" and slot_tasks:
        return slot_tasks

    for name in ("second_level_tasks.json", "second_level_tasks.sample.json"):
        p = _plan_dir(root) / "Input" / name
        if p.is_file():
            return assign_second_task_ids(load_second_tasks_from_json(p))

    return slot_tasks


def persist_received_tasks(skill_root: Path, second_tasks: list[dict[str, Any]]) -> int:
    """写入规范化 JSON；进度由 deploy_chain.step1_* 记录（mark_step1_complete）。"""
    received: list[dict[str, Any]] = []
    for t in second_tasks:
        item = dict(t)
        item["status"] = "已接收"
        received.append(item)

    plan = _plan_dir(skill_root)
    inp = plan / "Input" / "second_level_tasks.json"
    inp.parent.mkdir(parents=True, exist_ok=True)
    inp.write_text(
        json.dumps({"schemaVersion": 1, "tasks": received}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return len(received)


def run_receive(skill_root: Path, *, prefer_inbox: bool = False) -> dict[str, Any]:
    tasks = load_second_tasks(skill_root, prefer_inbox=prefer_inbox)
    if not tasks:
        return {"ok": False, "count": 0, "tasks": []}
    n = persist_received_tasks(skill_root, tasks)
    rt = skill_root / "runtime"
    if str(rt) not in sys.path:
        sys.path.insert(0, str(rt))
    from plan_chain import mark_step1_complete  # noqa: WPS433

    mark_step1_complete(
        skill_root,
        second_tasks_path=skill_root / "ProjectData" / "plan" / "Input" / "second_level_tasks.json",
        task_count=n,
    )
    return {"ok": True, "count": n, "tasks": tasks}


def main() -> int:
    skill_root = Path.cwd().resolve()
    if len(sys.argv) > 1 and sys.argv[1] == "--prefer-inbox":
        result = run_receive(skill_root, prefer_inbox=True)
    else:
        result = run_receive(skill_root)
    if not result.get("ok"):
        print("ERROR: 未找到二级任务文件（plan_receive 或 plan/Input）")
        return 1
    print(f"OK: 已接收 {result['count']} 条二级任务 → plan/Input/second_level_tasks.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
