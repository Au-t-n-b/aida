"""
模板 · 新 Skill 评测。复制为 agent/evals/eval_<name>.py。

读产物 skill_result.json → 质量断言 + 四维 → results/{ts}.json，并写回 Langfuse score。
四维：质量 / 成功率（产物断言）+ 成本 / 延迟（Langfuse 按 run_id 对齐）。指标见 METRICS.md。

跑：
    python agent/evals/eval_xxx.py                 # 评最近一次真实 run
    python agent/evals/eval_xxx.py --run-id run-x  # 精确对齐某次 run 的 trace
    python agent/evals/eval_xxx.py --fixture       # CI 离线（golden fixture）

全局替换：xxx → skill id。
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

# ✏️ 必改：断言用「阈值」不用精确等值，容忍正常波动、只抓塌方
BASELINE = {
    "completion_rate_min": 0.5,
    "required_completed_steps": ["example_step"],
}

_FIXTURE = Path(__file__).parent / "fixtures" / "xxx-golden.json"


def load_skill_result(use_fixture: bool = False) -> dict | None:
    if use_fixture:
        return json.loads(_FIXTURE.read_text("utf-8")) if _FIXTURE.exists() else None
    from agent.tools.zhgk_bridge import get_zhgk_root   # ✏️ 改成你模块的 work_root 解析
    live = Path(get_zhgk_root()) / "ProjectData" / "Output" / "skill_result.json"
    if live.exists():
        return json.loads(live.read_text("utf-8"))
    return json.loads(_FIXTURE.read_text("utf-8")) if _FIXTURE.exists() else None   # CI 回退


def evaluate(result: dict) -> dict:
    steps = result.get("execution", {}).get("steps", []) or []
    completed = [s.get("name") or s.get("step") for s in steps if s.get("status") == "completed"]

    # ✏️ 必改：你的业务指标
    metrics = {
        "completion_rate": (result.get("survey") or {}).get("completion_rate"),
        "steps_completed": len(completed),
        "steps_total": len(steps),
    }

    checks: list[dict] = []
    cr = metrics["completion_rate"] or 0
    checks.append({"name": "completion_rate ≥ 基线",
                   "pass": cr >= BASELINE["completion_rate_min"],
                   "detail": f"{cr} ≥ {BASELINE['completion_rate_min']}"})
    for rs in BASELINE["required_completed_steps"]:
        checks.append({"name": f"step[{rs}] = completed", "pass": rs in completed, "detail": ""})

    passed = sum(1 for c in checks if c["pass"])
    return {
        "skill": "xxx",
        "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "quality_score": round(passed / len(checks), 3) if checks else 0.0,
        "success": all(c["pass"] for c in checks),
        "run_id": result.get("run_id"),
        "cost_cny": None, "latency_ms": None,
        "metrics": metrics, "checks": checks,
    }


def main() -> int:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # aida 进 path
    result = load_skill_result(use_fixture="--fixture" in sys.argv)
    if not result:
        print("[eval xxx] 未找到 skill_result.json（先跑一次 xxx 产出产物）")
        return 1

    report = evaluate(result)
    run_id = (sys.argv[sys.argv.index("--run-id") + 1]
              if "--run-id" in sys.argv else result.get("run_id"))
    report["run_id"] = run_id

    # 四维补全：Langfuse 按 run_id 拉成本/延迟 + 写回质量/成功率 score
    try:
        from agent.evals.langfuse_eval import fetch_run_metrics, write_scores
        lf = fetch_run_metrics(run_id=run_id)
        if lf and not lf.get("_error"):
            report["cost_cny"] = lf.get("cost_cny")
            report["latency_ms"] = lf.get("latency_ms")
            if lf.get("trace_id"):
                write_scores(lf["trace_id"], {
                    "eval.quality": report["quality_score"],
                    "eval.success": 1.0 if report["success"] else 0.0,
                })
    except Exception as e:  # noqa: BLE001
        report["langfuse_error"] = str(e)

    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"xxx-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[eval xxx] quality={report['quality_score']} · success={report['success']} "
          f"· cost=¥{report.get('cost_cny')} · latency={report.get('latency_ms')}ms")
    for c in report["checks"]:
        print(f"  {'✓' if c['pass'] else '✗'} {c['name']} {c['detail']}")
    return 0 if report["success"] else 1  # 回归闸：质量断言不全过 → 非零退出


if __name__ == "__main__":
    raise SystemExit(main())
