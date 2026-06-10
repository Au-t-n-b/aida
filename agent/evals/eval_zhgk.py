"""
zhgk Skill 评测 v1 ·《团队 Agent 开发范式》规范 6（可观测 → 评测闭环）

读产物 skill_result.json → 质量断言 + 四维指标 → evals/results/{ts}.json。
四维：质量 / 成功率（产物断言）+ 成本 / 延迟（Langfuse，按 run_id 精确对齐）。
指标与基线定义见同目录 METRICS.md。

跑：
    python agent/evals/eval_zhgk.py                 # 评最近一次真实 run
    python agent/evals/eval_zhgk.py --run-id run-x  # 精确对齐某次 run 的 trace
    python agent/evals/eval_zhgk.py --fixture       # CI：用 golden fixture，离线可跑

run_id 解析优先级：--run-id > 产物里的 run_id 字段 > 无（回退 Langfuse 最近 trace，标 approx）。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

# golden 基线（来自 CONTRACT.md 真实样例 run-demo-0001：completion 53.9 / mandatory 23-46 / open 59）
BASELINE = {
    "completion_rate_min": 45.0,
    "mandatory_fill_rate_min": 0.40,
    "open_issues_max": 80,
    "required_completed_steps": ["scene_filter", "survey_build", "report_gen", "report_distribute"],
    "unrecognized_ratio_max": 0.20,   # 防 stub：无法识别占比上限（抓 MAX_LLM_CALLS 阉割）
}

# 业务 step（非 internal）· EVAL-STANDARDS 原则1 覆盖完整性
BUSINESS_STEPS = ["scene_filter", "survey_build", "report_gen", "report_distribute"]
# execution.steps.name 命名兼容（writer 历史遗留 distribute ↔ step.key report_distribute）
STEP_NAME_ALIAS = {"report_distribute": "distribute", "distribute": "report_distribute"}


def _completed_step_names(steps: list) -> set:
    """completed 的 step 名集合，做命名归一（report_distribute ≡ distribute）。"""
    names: set = set()
    for s in steps:
        if s.get("status") == "completed":
            n = s.get("name") or s.get("step") or ""
            if n:
                names.add(n)
                if n in STEP_NAME_ALIAS:
                    names.add(STEP_NAME_ALIAS[n])
    return names


_FIXTURE = Path(__file__).parent / "fixtures" / "zhgk-golden-run-demo-0001.json"


def _arg_value(argv: list[str], flag: str) -> str | None:
    """取 `--flag value` 形式的参数值（无则 None）。"""
    if flag in argv:
        i = argv.index(flag)
        if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            return argv[i + 1]
    return None


def _zhgk_root() -> Path:
    from agent.tools.zhgk_bridge import get_zhgk_root
    return get_zhgk_root()


def load_skill_result(use_fixture: bool = False) -> dict | None:
    if use_fixture:
        return json.loads(_FIXTURE.read_text(encoding="utf-8")) if _FIXTURE.exists() else None
    live = _zhgk_root() / "ProjectData" / "Output" / "skill_result.json"
    if live.exists():
        return json.loads(live.read_text(encoding="utf-8"))
    # CI 环境无真实 run，回退到 golden fixture
    return json.loads(_FIXTURE.read_text(encoding="utf-8")) if _FIXTURE.exists() else None


def evaluate(result: dict) -> dict:
    survey = result.get("survey", {}) or {}
    assessment = result.get("assessment", {}) or {}
    risk = result.get("risk", {}) or {}
    distribute = result.get("distribute", {}) or {}
    steps = result.get("execution", {}).get("steps", []) or []
    completed = _completed_step_names(steps)

    mand_total = survey.get("mandatory_total", 0) or 0
    mand_filled = survey.get("mandatory_filled", 0) or 0
    # 防 stub：无法识别占比（asm_decided = 满足+不满足+无法识别，不含不涉及）
    asm_unrec = assessment.get("unrecognized", 0) or 0
    asm_decided = (assessment.get("satisfied", 0) or 0) + (assessment.get("unsatisfied", 0) or 0) + asm_unrec
    unrec_ratio = round(asm_unrec / asm_decided, 3) if asm_decided else None

    metrics = {
        "completion_rate": survey.get("completion_rate"),
        "mandatory_fill_rate": round(mand_filled / mand_total, 3) if mand_total else None,
        "open_issues": sum((survey.get("empty_by_type") or {}).values()),
        "steps_completed": len(completed & set(BUSINESS_STEPS)),
        "steps_total": len(BUSINESS_STEPS),
        "assessment_total": assessment.get("total"),
        "assessment_unrecognized": asm_unrec,
        "unrecognized_ratio": unrec_ratio,
        "risk_total": risk.get("total"),
        "recipients": len(distribute.get("recipients") or []),
    }

    checks: list[dict] = []

    # ── survey 维（v1 保留）──
    cr = metrics["completion_rate"] or 0
    checks.append({"name": "completion_rate ≥ 基线", "pass": cr >= BASELINE["completion_rate_min"],
                   "detail": f"{cr} ≥ {BASELINE['completion_rate_min']}"})
    mfr = metrics["mandatory_fill_rate"] or 0
    checks.append({"name": "mandatory_fill_rate ≥ 基线", "pass": mfr >= BASELINE["mandatory_fill_rate_min"],
                   "detail": f"{mfr} ≥ {BASELINE['mandatory_fill_rate_min']}"})
    oi = metrics["open_issues"]
    checks.append({"name": "open_issues ≤ 基线", "pass": oi <= BASELINE["open_issues_max"],
                   "detail": f"{oi} ≤ {BASELINE['open_issues_max']}"})

    # ── 原则1+2：覆盖完整性 + step 自证（每个业务 step 必须 completed）──
    for rs in BASELINE["required_completed_steps"]:
        ok = rs in completed
        checks.append({"name": f"step[{rs}] = completed", "pass": ok,
                       "detail": "" if ok else "未完成或未自证（step 没写 skill_result）"})

    # ── L2 完整度：report_gen / report_distribute 产出非空 ──
    checks.append({"name": "assessment.total > 0（评估非空）", "pass": bool(metrics["assessment_total"]),
                   "detail": f"total={metrics['assessment_total']}"})
    checks.append({"name": "recipients > 0（有分发对象）", "pass": metrics["recipients"] > 0,
                   "detail": f"recipients={metrics['recipients']}"})

    # ── 原则4 防 stub：无法识别占比 ≤ 上限（抓 MAX_LLM_CALLS 阉割）──
    if unrec_ratio is not None:
        checks.append({"name": "unrecognized 占比 ≤ 基线（防评估阉割）",
                       "pass": unrec_ratio <= BASELINE["unrecognized_ratio_max"],
                       "detail": f"{unrec_ratio} ≤ {BASELINE['unrecognized_ratio_max']}（{asm_unrec}/{asm_decided}）"})
    else:
        checks.append({"name": "unrecognized 占比 ≤ 基线（防评估阉割）", "pass": False,
                       "detail": "assessment 段缺失，report_gen 未自证"})

    # ── L3-a 规则校验：assessment 统计自洽（Σ结论 == total）──
    asm_sum = ((assessment.get("satisfied", 0) or 0) + (assessment.get("unsatisfied", 0) or 0)
               + asm_unrec + (assessment.get("not_applicable", 0) or 0))
    asm_total = assessment.get("total") or 0
    checks.append({"name": "assessment 统计自洽（Σ结论 == total）",
                   "pass": bool(asm_total) and asm_sum == asm_total,
                   "detail": f"Σ={asm_sum} vs total={asm_total}"})

    passed = sum(1 for c in checks if c["pass"])
    quality_score = round(passed / len(checks), 3)

    step_status: dict[str, str] = {}
    step_durations: dict[str, int] = {}
    for s in steps:
        key = s.get("name") or s.get("step") or ""
        if not key:
            continue
        step_status[key] = s.get("status", "pending")
        if s.get("duration_s") is not None:
            step_durations[key] = int(float(s["duration_s"]) * 1000)

    return {
        "skill": "zhgk",
        "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "quality_score": quality_score,
        "success": all(c["pass"] for c in checks),
        "run_id": result.get("run_id"),
        "cost_cny": None,
        "latency_ms": None,
        "metrics": metrics,
        "checks": checks,
        "step_status": step_status,
        "step_durations": step_durations,
        "empty_by_type": survey.get("empty_by_type") or {},
    }


def main() -> int:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # aida 进 path
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    use_fixture = "--fixture" in sys.argv
    cli_run_id = _arg_value(sys.argv, "--run-id")
    result = load_skill_result(use_fixture=use_fixture)
    if not result:
        print("[eval zhgk] 未找到 skill_result.json（先跑一次 zhgk 产出产物）")
        return 1

    report = evaluate(result)

    # run_id 解析：CLI > 产物字段 > 无（回退最近 trace · 标 approx）
    run_id = cli_run_id or result.get("run_id")
    report["run_id"] = run_id
    report["metrics_source"] = "run-id" if run_id else "approx-latest"

    # 补全四维：Langfuse 按 run_id 精确拉成本/延迟 + 质量/成功率写回 score
    try:
        from agent.evals.langfuse_eval import fetch_run_metrics, write_scores
        lf = fetch_run_metrics(run_id=run_id)
        if lf and not lf.get("_error"):
            # 无 run_id 回退最近 trace：把解析到的 run_id 回填，但保留 approx 标记以示不确定
            report["run_id"] = run_id or lf.get("run_id")
            report["trace_id"] = lf.get("trace_id")
            report["cost_cny"] = lf.get("cost_cny")
            report["latency_ms"] = lf.get("latency_ms")
            if not run_id:
                print("[eval zhgk] ⚠ 未提供 run_id，成本/延迟取『最近一条 zhgk trace』（可能与本产物不是同一次 run）。"
                      "\n  建议：跑 zhgk 后产物会自带 run_id；或显式传 --run-id。")
            if lf.get("trace_id"):
                report["scores_written"] = write_scores(lf["trace_id"], {
                    "eval.quality": report["quality_score"],
                    "eval.success": 1.0 if report["success"] else 0.0,
                })
        elif lf and lf.get("_error"):
            report["langfuse_error"] = lf["_error"]
        elif not lf:
            report["langfuse_note"] = f"未找到匹配 trace（run_id={run_id}）"
    except Exception as e:  # noqa: BLE001
        report["langfuse_error"] = str(e)

    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"zhgk-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[eval zhgk] quality={report['quality_score']} · success={report['success']} "
          f"· cost=¥{report.get('cost_cny')} · latency={report.get('latency_ms')}ms")
    for c in report["checks"]:
        print(f"  {'✓' if c['pass'] else '✗'} {c['name']} {c['detail']}")
    print(f"  run_id={report.get('run_id')} ({report.get('metrics_source')}) · "
          f"trace={report.get('trace_id')} · scores_written={report.get('scores_written')}")
    print(f"→ {out}")
    return 0 if report["success"] else 1  # 回归闸：质量断言不全过 → 非零退出


if __name__ == "__main__":
    raise SystemExit(main())
