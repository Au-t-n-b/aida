"""
工具评测 v1 ·《团队 Agent 开发范式》规范 3（工具规范）+ 规范 6（评测闭环）

面向「工具大量增长」：工具一多，难用的工具（description/schema 不清）会让模型反复重试，
拖垮整个会话/Skill 的成本与成功率。本评测从工具调用记录算出每个工具的体检指标：

  - 自纠率 ⭐  errors/calls：模型调用后返回 Error（validate 失败/执行异常）的比例。
              高 → description/parameters 需打磨（最高价值优化信号）。
  - 成功率    1 - 自纠率（按工具）。
  - 延迟      p50 / p95（ms）。
  - 调用热度  calls（指导优先优化哪个）。

数据源（与 eval_zhgk 同构：live 优先、fixture 回退）：
  - live：Langfuse 工具 span（metadata.kind=="tool"），见 langfuse_eval.fetch_tool_spans
  - fixture：fixtures/tools-golden.json（CI/离线可跑，证明指标可算）

跑：
    python agent/evals/eval_tools.py             # live（无数据自动回退 fixture）
    python agent/evals/eval_tools.py --fixture   # 强制用 golden fixture（CI）
    python agent/evals/eval_tools.py --days 14   # live 时间窗

指标与基线定义见同目录 METRICS.md。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_FIXTURE = Path(__file__).parent / "fixtures" / "tools-golden.json"

# 工具健康基线（v2 · 区间/阈值而非精确等值，容忍波动只抓塌方）
BASELINE = {
    "retry_rate_max": 0.30,            # 单工具重试率上限（v2 精确自纠率）：超过 → schema/description 该打磨
    "self_correction_rate_max": 0.30,  # 错误率上限（errors/calls，v1 兼容字段）
    "success_rate_min": 0.70,          # 单工具成功率下限
    "p95_ms_max": 5000,                # 单工具 p95 延迟上限
    "min_calls_to_judge": 3,           # 调用数 < 此值不下结论（样本太小）
}


def _pctl(values: list[float], p: float) -> float:
    """线性插值百分位（p ∈ [0,100]）。空 → 0。"""
    if not values:
        return 0.0
    xs = sorted(values)
    if len(xs) == 1:
        return float(xs[0])
    k = (len(xs) - 1) * (p / 100.0)
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return float(xs[lo] + (xs[hi] - xs[lo]) * (k - lo))


def aggregate(records: list[dict]) -> dict:
    """对工具调用记录做纯函数聚合（无 IO，便于单测）。

    v2 自纠率修正：`retry_rate` = 真正的「同工具上次失败→本次重试」序列检测（需 records 保序）；
    `self_correction_rate` 保留为 errors/calls 错误率近似（兼容 v1 前端 deviations）。
    """
    by_tool: dict[str, dict] = {}
    for r in records:
        name = r.get("tool") or "unknown"
        t = by_tool.setdefault(name, {"calls": 0, "errors": 0, "lat": [], "seq": []})
        t["calls"] += 1
        ok = bool(r.get("ok", True))
        if not ok:
            t["errors"] += 1
        t["seq"].append(ok)   # 按出现顺序记 ok/fail，用于 retry 检测
        if r.get("latency_ms") is not None:
            t["lat"].append(float(r["latency_ms"]))

    tools: dict[str, dict] = {}
    total_retries = 0
    for name, t in sorted(by_tool.items()):
        calls = t["calls"]
        errors = t["errors"]
        seq = t["seq"]
        # 自纠/重试：该工具序列中「前一次 fail」之后的那次调用 = 一次重试
        retries = sum(1 for i in range(1, len(seq)) if not seq[i - 1])
        total_retries += retries
        tools[name] = {
            "calls": calls,
            "errors": errors,
            "retry_count": retries,
            "retry_rate": round(retries / calls, 3) if calls else 0.0,            # v2 精确自纠率
            "self_correction_rate": round(errors / calls, 3) if calls else 0.0,   # v1 兼容（错误率近似）
            "success_rate": round((calls - errors) / calls, 3) if calls else 0.0,
            "p50_ms": round(_pctl(t["lat"], 50), 1),
            "p95_ms": round(_pctl(t["lat"], 95), 1),
        }
    overall_calls = sum(t["calls"] for t in tools.values())
    overall_errors = sum(t["errors"] for t in tools.values())
    return {
        "tools": tools,
        "overall": {
            "tool_count": len(tools),
            "calls": overall_calls,
            "retry_count": total_retries,
            "retry_rate": round(total_retries / overall_calls, 3) if overall_calls else 0.0,
            "self_correction_rate": round(overall_errors / overall_calls, 3) if overall_calls else 0.0,
        },
    }


RECORDS_CAP = 200


def evaluate(records: list[dict], *, conv_id: str | None = None, run_id: str | None = None, window: str = "") -> dict:
    """聚合 + 基线断言。返回评测报告（含 checks + records，可进 CI）。"""
    agg = aggregate(records)
    checks: list[dict] = []
    for name, m in agg["tools"].items():
        if m["calls"] < BASELINE["min_calls_to_judge"]:
            checks.append({"tool": name, "name": "样本量", "pass": True,
                           "detail": f"calls={m['calls']} < {BASELINE['min_calls_to_judge']}，不下结论"})
            continue
        checks.append({"tool": name, "name": "重试率 ≤ 基线（v2 自纠率）",
                       "pass": m["retry_rate"] <= BASELINE["retry_rate_max"],
                       "detail": f"retry={m['retry_rate']} ≤ {BASELINE['retry_rate_max']}（{m['retry_count']}/{m['calls']}）"})
        checks.append({"tool": name, "name": "成功率 ≥ 基线",
                       "pass": m["success_rate"] >= BASELINE["success_rate_min"],
                       "detail": f"{m['success_rate']} ≥ {BASELINE['success_rate_min']}"})
        checks.append({"tool": name, "name": "p95 ≤ 基线",
                       "pass": m["p95_ms"] <= BASELINE["p95_ms_max"],
                       "detail": f"{m['p95_ms']}ms ≤ {BASELINE['p95_ms_max']}ms"})

    passed = sum(1 for c in checks if c["pass"])
    capped = records[:RECORDS_CAP]
    return {
        "kind": "tools",
        "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "quality_score": round(passed / len(checks), 3) if checks else 1.0,
        "success": all(c["pass"] for c in checks),
        "overall": agg["overall"],
        "tools": agg["tools"],
        "checks": checks,
        "records": capped,
        "record_count": len(records),
        "conv_id": conv_id or "",
        "run_id": run_id or "",
        "window": window,
    }


def load_records(
    use_fixture: bool,
    days: int,
    *,
    conv_id: str | None = None,
    run_id: str | None = None,
) -> tuple[list[dict], str, str]:
    """取工具调用记录。返回 (records, source, window)。优先本地会话日志，再 Langfuse。"""
    if not use_fixture and (conv_id or run_id):
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
            from agent.evals.session_tool_log import load_session_records
            sess = load_session_records(conv_id=conv_id, run_id=run_id)
            if sess:
                win = f"session:{conv_id or run_id}"
                return sess, win, win
        except Exception:
            pass

    if not use_fixture:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
            from agent.evals.langfuse_eval import fetch_tool_spans
            res = fetch_tool_spans(days=days, conv_id=conv_id, run_id=run_id)
            if res and not res.get("_error") and res.get("records"):
                win = res.get("window", "")
                return res["records"], f"langfuse:{win}", win
            # conv_id 过滤无命中时，再拉全量后按 conv_id/run_id 客户端过滤
            if (conv_id or run_id) and res and not res.get("_error"):
                res2 = fetch_tool_spans(days=days)
                recs = res2.get("records") or []
                if conv_id:
                    recs = [r for r in recs if r.get("conv_id") == conv_id]
                if run_id:
                    recs = [r for r in recs if r.get("run_id") == run_id]
                if recs:
                    win = f"langfuse-filtered:{conv_id or run_id}"
                    return recs, win, win
        except Exception:  # noqa: BLE001 — live 不可用就回退 fixture
            pass
    if _FIXTURE.exists():
        data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        recs = data.get("records", [])
        if conv_id:
            recs = [r for r in recs if r.get("conv_id") == conv_id]
        if run_id:
            recs = [r for r in recs if r.get("run_id") == run_id]
        if not recs and (conv_id or run_id):
            recs = data.get("records", [])
        return recs, "fixture", data.get("window", "fixture")
    return [], "empty", ""


def _arg_value(argv: list[str], flag: str) -> str | None:
    if flag in argv:
        i = argv.index(flag)
        if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            return argv[i + 1]
    return None


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    use_fixture = "--fixture" in sys.argv
    days = 7
    if "--days" in sys.argv:
        i = sys.argv.index("--days")
        if i + 1 < len(sys.argv):
            days = int(sys.argv[i + 1])

    conv_id = _arg_value(sys.argv, "--conv-id")
    run_id = _arg_value(sys.argv, "--run-id")

    records, source, window = load_records(
        use_fixture, days, conv_id=conv_id, run_id=run_id,
    )
    if not records:
        print("[eval tools] 无工具调用记录（live 无数据且无 fixture）")
        return 1

    report = evaluate(records, conv_id=conv_id, run_id=run_id, window=window)
    report["source"] = source

    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"tools-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    o = report["overall"]
    print(f"[eval tools] source={source} · tools={o['tool_count']} · calls={o['calls']} "
          f"· 总重试率={o.get('retry_rate')} · 总错误率={o['self_correction_rate']} "
          f"· quality={report['quality_score']} · success={report['success']}")
    for name, m in report["tools"].items():
        flag = "⚠" if m["retry_rate"] > BASELINE["retry_rate_max"] else " "
        print(f"  {flag} {name:<14} calls={m['calls']:<3} 重试率={m['retry_rate']:<5} "
              f"错误率={m['self_correction_rate']:<5} 成功率={m['success_rate']:<5} "
              f"p50={m['p50_ms']}ms p95={m['p95_ms']}ms")
    for c in report["checks"]:
        if not c["pass"]:
            print(f"  ✗ [{c['tool']}] {c['name']} {c['detail']}")
    print(f"→ {out}")
    return 0 if report["success"] else 1  # 回归闸：有工具跌破基线 → 非零退出


if __name__ == "__main__":
    raise SystemExit(main())
