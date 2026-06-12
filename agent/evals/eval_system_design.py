"""
system_design 评测回归 · 读 Output/skill_result.json → 阈值断言 → results/{ts}.json。

断言用「阈值」不用精确等值（容忍正常波动、只抓塌方）：
  1. completion_rate           ≥ 0.5     流程跑通过半
  2. plane_coverage            ≥ 0.25    规划覆盖率（plane_done/plane_total）
  3. artifact_count            ≥ 3       至少产出若干产物
  + 必过步骤 publish == completed（发布完成）

跑：
    agent\.venv\Scripts\python agent/evals/eval_system_design.py            # 评最近一次真实 run
    agent\.venv\Scripts\python agent/evals/eval_system_design.py --fixture  # CI 离线（golden fixture）
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# 阈值基线（只抓塌方，不做精确等值）
BASELINE = {
    "completion_rate_min": 0.5,
    "plane_coverage_min": 0.25,
    "artifact_count_min": 3,
    "required_completed_steps": ["publish"],
}

_FIXTURE = Path(__file__).parent / "fixtures" / "system_design-golden.json"


def _live_result_path() -> Path | None:
    """系统设计 work_root 的 Output/skill_result.json（与 skill.py 同源解析 root）。"""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # aida 进 path
        from agent.skills.system_design.skill import _get_system_design_root
        p = _get_system_design_root() / "ProjectData" / "Output" / "skill_result.json"
        return p if p.exists() else None
    except Exception:
        return None


def load_skill_result(use_fixture: bool = False) -> dict | None:
    if not use_fixture:
        live = _live_result_path()
        if live:
            return json.loads(live.read_text("utf-8"))
    return json.loads(_FIXTURE.read_text("utf-8")) if _FIXTURE.exists() else None


def evaluate(result: dict) -> dict:
    steps = (result.get("execution") or {}).get("steps", []) or []
    completed = [s.get("step") for s in steps if s.get("status") == "completed"]
    m = result.get("metrics") or {}

    completion_rate = result.get("completion_rate")
    if completion_rate is None:
        completion_rate = (len(completed) / len(steps)) if steps else 0.0

    metrics = {
        "completion_rate": round(completion_rate, 4),
        "plane_coverage": m.get("plane_coverage"),
        "plane_done": m.get("plane_done"),
        "plane_total": m.get("plane_total"),
        "artifact_count": m.get("artifact_count"),
        "lld_planes_merged": m.get("lld_planes_merged"),
        "steps_completed": len(completed),
        "steps_total": len(steps),
    }

    checks: list[dict] = []
    checks.append({
        "name": "completion_rate ≥ 基线",
        "pass": (completion_rate or 0) >= BASELINE["completion_rate_min"],
        "detail": f"{completion_rate} ≥ {BASELINE['completion_rate_min']}",
    })
    pc = m.get("plane_coverage") or 0
    checks.append({
        "name": "plane_coverage ≥ 基线",
        "pass": pc >= BASELINE["plane_coverage_min"],
        "detail": f"{pc} ≥ {BASELINE['plane_coverage_min']}",
    })
    ac = m.get("artifact_count") or 0
    checks.append({
        "name": "artifact_count ≥ 基线",
        "pass": ac >= BASELINE["artifact_count_min"],
        "detail": f"{ac} ≥ {BASELINE['artifact_count_min']}",
    })
    for rs in BASELINE["required_completed_steps"]:
        checks.append({"name": f"step[{rs}] = completed", "pass": rs in completed, "detail": ""})

    passed = sum(1 for c in checks if c["pass"])
    return {
        "skill": "system_design",
        "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "quality_score": round(passed / len(checks), 3) if checks else 0.0,
        "success": all(c["pass"] for c in checks),
        "run_id": result.get("run_id"),
        "metrics": metrics,
        "checks": checks,
    }


def main() -> int:
    use_fixture = "--fixture" in sys.argv
    result = load_skill_result(use_fixture=use_fixture)
    if not result:
        print("[eval system_design] 未找到 skill_result.json（先跑一次 system_design 产出产物，或用 --fixture）")
        return 1

    report = evaluate(result)
    report["source"] = "fixture" if use_fixture else "live"

    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"system_design-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[eval system_design] source={report['source']} · quality={report['quality_score']} · success={report['success']}")
    for c in report["checks"]:
        print(f"  {'PASS' if c['pass'] else 'FAIL'} · {c['name']} {c['detail']}")
    return 0 if report["success"] else 1  # 回归闸：阈值断言不全过 → 非零退出


if __name__ == "__main__":
    raise SystemExit(main())
