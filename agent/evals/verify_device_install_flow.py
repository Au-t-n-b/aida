"""设备安装全流程自验证（可用 env 覆盖三个上游目录或统一 DEVICE_INSTALL_SOURCE_ROOT）。

用法（PowerShell）:
  $env:PYTHONPATH = "d:\\aida-feature_new\\aida"
  $env:DEVICE_INSTALL_SOURCE_ROOT = "C:\\Users\\...\\ProjectData\\Input"  # 交付计划表目录
  $env:DEVICE_INSTALL_ROOT = "C:\\Users\\...\\device_install"
  python agent/evals/verify_device_install_flow.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_AGENT = Path(__file__).resolve().parents[1]
_ROOT = _AGENT.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
os.chdir(_AGENT)

from agent.skills.base import SkillContext
from agent.skills.device_install import dc_paths
from agent.skills.device_install.pipeline import DI_STEP_NAMES
from agent.skills.device_install.sdui import project as sdui_project
from agent.skills.device_install.skill import get_device_install_skill
from agent.skills.device_install.steps._io import (
    find_arrival_table,
    find_delivery_plan,
    find_position_table,
)
from agent.skills.device_install.steps.preflight import PreflightStep
from agent.sdui.projector_base import backend_status_to_sdui


def _stepper_map(doc: dict) -> dict[str, str]:
    out: dict[str, str] = {}

    def walk(node: dict) -> None:
        if not isinstance(node, dict):
            return
        if node.get("type") == "Stepper":
            for s in node.get("steps") or []:
                if isinstance(s, dict) and s.get("id"):
                    out[s["id"]] = s.get("status", "?")
        for c in node.get("children") or []:
            walk(c)

    walk(doc.get("root") or {})
    return out


def _backend_step_map(state: dict) -> dict[str, str]:
    return {s.get("key", ""): s.get("status", "?") for s in state.get("steps") or []}


def _fill_principal_rows(need_edit: dict) -> list[dict]:
    rows = need_edit.get("fillRows") or need_edit.get("rows") or []
    filled: list[dict] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        item = dict(r)
        item.setdefault("principal", item.get("principal") or "测试责任人")
        item.setdefault("principal_org", item.get("principal_org") or "华为")
        filled.append(item)
    return filled


def _find_nodes(doc: dict, node_type: str) -> list[dict]:
    found: list[dict] = []

    def walk(node: dict) -> None:
        if not isinstance(node, dict):
            return
        if node.get("type") == node_type:
            found.append(node)
        for c in node.get("children") or []:
            walk(c)
        for t in node.get("tabs") or []:
            if isinstance(t, dict):
                for c in t.get("children") or []:
                    walk(c)

    walk(doc.get("root") or {})
    return found


def _stepper_details_empty(doc: dict) -> bool:
    for st in _find_nodes(doc, "Stepper"):
        for s in st.get("steps") or []:
            if isinstance(s, dict) and s.get("detail"):
                return False
    return True


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    # 数据中心 API 化：业务数据走 DATA_CENTER_BASE_URL；本地验证可用挂载盘降级
    # （AIDA_BUSINESS_ROOT/project/... 放入上游三表）。需任一可达。
    dc = os.environ.get("DATA_CENTER_BASE_URL", "").strip()
    biz = os.environ.get("AIDA_BUSINESS_ROOT", "").strip()
    if not dc and not biz:
        print("FAIL: set DATA_CENTER_BASE_URL（推荐 mock）或 AIDA_BUSINESS_ROOT（挂载盘降级）")
        return 1

    loc = dc_paths.delivery_plan_loc()
    print(f"[OK] 上游交付计划表语义位置: {loc.describe()}（挂载盘降级: {loc.disk_dir()}）")

    skill = get_device_install_skill()
    project = skill.initial_project(
        {"command": "build", "project_name": "flow-verify", "reset_workspace": True}
    )
    ctx = SkillContext(
        skill_id="device_install",
        work_root=skill.work_root,
        run_id="verify-flow",
        project=project,
        llm_factory=skill.llm_factory,
    )

    for label, finder in (
        ("delivery", find_delivery_plan),
        ("position", find_position_table),
        ("arrival", find_arrival_table),
    ):
        p = finder(ctx)
        _assert(bool(p and Path(p).exists()), f"missing input {label}: {p}")
        print(f"[OK] input {label}: {Path(p).name}")

    logs: list[str] = []
    PreflightStep().run(ctx, {}, logs.append)
    for token in (
        "正在扫描设备安装环境",
        "正在校验三个上游输入文件",
        "交付计划表",
        "设备位置表",
        "到货信息表",
        "LLM 摘要跳过",
    ):
        _assert(any(token in ln for ln in logs), f"preflight log missing {token}: {logs}")
    print(f"[OK] preflight logs ({len(logs)} lines)")

    graph = skill.build_graph(checkpointer=__import__(
        "langgraph.checkpoint.memory", fromlist=["MemorySaver"]
    ).MemorySaver())
    init = {
        "run_id": "verify-flow",
        "skill_id": "device_install",
        "project": project,
        "steps": [],
        "logs": [],
        "overall_progress": 0,
    }
    state = graph.invoke(init, {"configurable": {"thread_id": "verify-flow-1"}})
    hitl = state.get("hitl") or {}
    _assert(hitl.get("step") == "principal_fill", f"expected principal_fill HITL, got {hitl}")
    print("[OK] graph paused at principal_fill")

    doc_hitl = sdui_project(state)
    stepper_hitl = _stepper_map(doc_hitl)
    _assert("principal_fill" in stepper_hitl, f"stepper missing principal_fill: {stepper_hitl}")
    _assert(_stepper_details_empty(doc_hitl), "stepper should not embed log_tail detail")
    print(f"[OK] SDUI at principal_fill HITL: {stepper_hitl}")

    # 模拟「保存并继续」
    rows = _fill_principal_rows(hitl.get("need_edit") or {})
    _assert(rows, "principal_fill rows empty")
    project = skill.apply_resume_payload(state["project"], {"rows": rows}, "principal_fill")
    state2 = graph.invoke(
        {"project": project, "logs": ["[resume] verify principal_fill"]},
        {"configurable": {"thread_id": "verify-flow-2"}},
    )
    hitl2 = state2.get("hitl") or {}
    _assert(hitl2.get("step") == "tasks_generate", f"expected tasks_generate HITL, got {hitl2}")
    backend2 = _backend_step_map(state2)
    _assert(backend2.get("principal_fill") == "completed", backend2)
    doc2 = sdui_project(state2)
    stepper2 = _stepper_map(doc2)
    _assert(stepper2.get("principal_fill") == "done", stepper2)
    _assert("tasks_generate" in stepper2, stepper2)
    need2 = hitl2.get("need_edit") or {}
    _assert(need2.get("fillLabel") == "一键同步", need2)
    _assert(need2.get("submitLabel") == "确认并生成", need2)
    tabs2 = [t for t in _find_nodes(doc2, "TabGroup") if t.get("id") == "view-tabs-tasks_generate"]
    _assert(tabs2 and tabs2[0].get("keepAlive") is True, f"tasks_generate TabGroup keepAlive: {tabs2}")
    print(f"[OK] after 保存并继续: backend={backend2}, stepper={stepper2}")

    # 模拟「确认并生成」
    rows2 = need2.get("rows") or []
    _assert(rows2, "tasks_generate rows empty")
    project2 = skill.apply_resume_payload(state2["project"], {"rows": rows2}, "tasks_generate")
    state3 = graph.invoke(
        {"project": project2, "logs": ["[resume] verify tasks_generate"]},
        {"configurable": {"thread_id": "verify-flow-3"}},
    )
    hitl3 = state3.get("hitl") or {}
    _assert(hitl3.get("step") == "task_dispatch", f"expected task_dispatch HITL, got {hitl3}")
    backend3 = _backend_step_map(state3)
    _assert(backend3.get("tasks_generate") == "completed", backend3)
    doc3 = sdui_project(state3)
    stepper3 = _stepper_map(doc3)
    _assert(stepper3.get("tasks_generate") in ("running", "done"), stepper3)
    tabs3 = [t for t in _find_nodes(doc3, "TabGroup") if t.get("id") == "view-tabs-task_dispatch"]
    _assert(tabs3 and tabs3[0].get("keepAlive") is True, f"task_dispatch TabGroup keepAlive: {tabs3}")
    need3 = hitl3.get("need_edit") or {}
    _assert(need3.get("submitLabel") == "确认下发", need3)
    _assert(need3.get("fillLabel") == "一键全选", need3)
    print(f"[OK] after 确认并生成: backend={backend3}, stepper={stepper3}")

    # 模拟「确认下发」→ sn_generate → esn_fill HITL
    rows3 = need3.get("rows") or []
    _assert(rows3, "task_dispatch rows empty")
    for r in rows3:
        if isinstance(r, dict):
            r["selected"] = True
    project3 = skill.apply_resume_payload(state3["project"], {"rows": rows3}, "task_dispatch")
    state4 = graph.invoke(
        {"project": project3, "logs": ["[resume] verify task_dispatch"]},
        {"configurable": {"thread_id": "verify-flow-4"}},
    )
    hitl4 = state4.get("hitl") or {}
    _assert(hitl4.get("step") == "esn_fill", f"expected esn_fill HITL, got {hitl4}")
    need4 = hitl4.get("need_edit") or {}
    _assert(need4.get("submitLabel") == "生成完工报告", need4)
    _assert(need4.get("fillLabel") == "一键同步", need4)
    doc4 = sdui_project(state4)
    _assert(_stepper_details_empty(doc4), "stepper detail should stay empty at esn_fill")
    print(f"[OK] after 确认下发 → esn_fill HITL: submitLabel={need4.get('submitLabel')}")

    # 步骤条 running 语义：backend running → SDUI running（琥珀转圈）
    for rec in state3.get("steps") or []:
        if rec.get("key") == "task_dispatch" and rec.get("status") == "hitl":
            sdui_status = backend_status_to_sdui("hitl")
            _assert(sdui_status == "running", f"hitl should map to running, got {sdui_status}")
            print("[OK] stepper running mapping: hitl -> running (yellow spinner)")

    all_logs = "\n".join(state3.get("logs") or [])
    _assert("已保存责任人信息" in all_logs or "principal_fill" in all_logs, "missing principal log")
    print("[OK] pipeline logs include principal_fill result")

    print("\n=== ALL CHECKS PASSED ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
