"""Simulate LangGraph resume → lld_integrate for 生成完整 LLD 设计."""
from __future__ import annotations

import sys
from pathlib import Path

_AIDA_ROOT = Path(__file__).resolve().parents[2]
if str(_AIDA_ROOT) not in sys.path:
    sys.path.insert(0, str(_AIDA_ROOT))

from agent.skills.system_design.skill import get_system_design_skill
from agent.skills.system_design.pipelines.path_manifest import reload_manifest
from agent.sdui.projector_base import collect_metrics


def _run_graph(skill, init: dict, thread_id: str) -> dict:
    graph = skill.build_graph()
    config = {"configurable": {"thread_id": thread_id}}
    return graph.invoke(init, config)


def test_resume_lld_route() -> None:
    reload_manifest()
    skill = get_system_design_skill()
    prev = {
        "run_id": "verify-lld",
        "skill_id": "system_design",
        "project": {"confirmations": {"exec": True}, "text": ""},
        "hitl": {"step": "plane_planning", "need_inputs": []},
        "steps": [{
            "key": "plane_planning",
            "status": "completed",
            "metrics": {
                "sd_mode": "single",
                "plane_done": 1,
                "plan_commands": [{"command": "t", "status": "ok", "files": ["A3带外管理地址规划.xlsx"]}],
            },
        }],
        "files": {},
        "logs": [],
    }
    payload = {"choice": "生成完整LLD设计", "text": "生成完整LLD设计"}
    project = skill.apply_resume_payload(dict(prev["project"]), payload, "plane_planning")
    extras, project = skill.build_resume_init_state(prev, project, "plane_planning", payload)
    init = {
        "run_id": "verify-lld-r1",
        "skill_id": "system_design",
        "project": project,
        "steps": list(extras.get("steps") or []),
        "logs": list(extras.get("logs") or []),
        "overall_progress": 0,
        "route_to": extras.get("route_to"),
        "metrics": extras.get("metrics"),
        "files": extras.get("files"),
    }
    print("init route_to:", init.get("route_to"))
    state = _run_graph(skill, init, "verify-lld-thread")
    m = collect_metrics(state)
    steps = {s.get("key"): s.get("status") for s in state.get("steps") or []}
    print("steps:", steps)
    print("lld_status:", m.get("lld_status"), "lld_file:", m.get("lld_file"))
    print("error:", state.get("error"))
    print("hitl:", state.get("hitl"))
    assert m.get("lld_status") == "ok", f"expected lld ok, got {m.get('lld_status')}"
    assert m.get("lld_file"), "missing lld_file in metrics"


def test_full_intent_lld() -> None:
    """Fresh run with intent 生成完整LLD设计 (needs inputs on disk)."""
    reload_manifest()
    skill = get_system_design_skill()
    init = {
        "run_id": "verify-full",
        "skill_id": "system_design",
        "project": skill.initial_project({
            "text": "生成完整LLD设计",
            "confirmations": {"exec": True},
        }),
        "steps": [],
        "logs": [],
        "overall_progress": 0,
    }
    state = _run_graph(skill, init, "verify-full-thread")
    m = collect_metrics(state)
    print("full run lld_status:", m.get("lld_status"), "lld_file:", m.get("lld_file"))
    print("sd_mode:", m.get("sd_mode"))
    print("error:", state.get("error"))
    if state.get("hitl"):
        print("hitl step:", state["hitl"].get("step"))


def test_resume_lld_no_hitl_step() -> None:
    """hitl 已清空但 Output 有平面表 → 仍应 route_to=lld_integrate。"""
    reload_manifest()
    skill = get_system_design_skill()
    from agent.skills.system_design.pipelines.delivery import resolve_resume_route_to

    prev = {
        "hitl": {},
        "steps": [{
            "key": "plane_planning",
            "status": "completed",
            "metrics": {"sd_mode": "single", "plane_done": 1},
        }],
    }
    payload = {"text": "生成完整 LLD 设计"}
    project = skill.apply_resume_payload({}, payload, "")
    route = resolve_resume_route_to(
        hitl_step="",
        project=project,
        payload=payload,
        prev_state=prev,
        work_root=skill.work_root,
    )
    print("no-hitl route:", route)
    assert route == "lld_integrate", route


if __name__ == "__main__":
    print("=== resume lld route ===")
    test_resume_lld_route()
    print("=== resume lld without hitl step ===")
    test_resume_lld_no_hitl_step()
    print("=== full intent (may hitl if no exec confirm) ===")
    test_full_intent_lld()
