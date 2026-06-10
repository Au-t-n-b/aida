"""
评测偏离构建 · METRICS.md §7 + AI 分析闭环

纯函数，无 IO。供 export_deviations.py 与 FastAPI /agent/evals/deviations/* 共用。
"""
from __future__ import annotations

from typing import Any

SKILL_PROMPT = (
    "以下是该 skill 的评测偏离项，结合 skills/<skill> 源码，"
    "指出每个偏离的根因与具体改法（改 prompt / 改 schema / 拆 step / 加缓存），按 ROI 排序。"
)

TOOLS_PROMPT = (
    "以下工具的自纠率超阈值，说明模型常因 description/parameters 不清而调用失败重试。"
    "结合 agent/tools/<name>.py，给出每个工具 description 与 JSON Schema 的具体改法，"
    "按调用热度×自纠率（影响面）排序。"
)

TOOL_TYPE_MAP: dict[str, str] = {
    "read_file": "会话",
    "run_survey": "skill-as-tool",
    "send_mail": "副作用·外发",
    "send_welink": "副作用·外发",
    "present_choices": "控制·HITL",
}


def build_skill_deviations(runs: list[dict]) -> dict[str, Any]:
    """基线 = 最早一条，当前 = 最新一条（runs 按时间倒序：runs[0] 最新）。"""
    if len(runs) < 2:
        return {
            "skill": runs[0].get("skill", "zhgk") if runs else "zhgk",
            "note": "需要至少 2 次评测才能计算偏离",
            "runs": len(runs),
            "prompt": SKILL_PROMPT,
        }
    latest, baseline = runs[0], runs[-1]
    deviations: list[dict] = []

    bq, lq = baseline.get("quality_score"), latest.get("quality_score")
    if bq is not None and lq is not None and lq < bq:
        deviations.append({
            "target": "skill:overall",
            "metric": "quality_score",
            "baseline": bq,
            "current": lq,
            "delta": f"{(lq - bq) * 100:.1f}%",
        })
    bl, ll = baseline.get("latency_ms"), latest.get("latency_ms")
    if bl and ll and ll > bl * 1.2:
        deviations.append({
            "target": "skill:overall",
            "metric": "latency_ms",
            "baseline": bl,
            "current": ll,
            "delta": f"+{((ll - bl) / bl) * 100:.0f}%",
        })
    for c in latest.get("checks") or []:
        if not c.get("pass"):
            deviations.append({
                "target": f"check:{c.get('name', '')}",
                "metric": "pass",
                "value": False,
                "detail": c.get("detail", ""),
            })

    trend_slice = runs[:10][::-1]
    return {
        "skill": latest.get("skill", "zhgk"),
        "prompt": SKILL_PROMPT,
        "baseline_run_id": baseline.get("run_id"),
        "current_run_id": latest.get("run_id"),
        "trend": {
            "quality_score": [r.get("quality_score") for r in trend_slice],
            "latency_ms": [r.get("latency_ms") for r in trend_slice],
            "cost_cny": [r.get("cost_cny") for r in trend_slice],
        },
        "deviations": deviations,
    }


def build_tool_deviations(
    tools: dict[str, dict],
    *,
    threshold: float = 0.15,
) -> dict[str, Any]:
    """tools: eval_tools aggregate 的 tools 字典。"""
    flagged = []
    for name, m in sorted(tools.items(), key=lambda x: x[1].get("self_correction_rate", 0), reverse=True):
        scr = m.get("self_correction_rate", 0) or 0
        if scr > threshold:
            flagged.append({
                "target": f"tool:{name}",
                "scope": "default",
                "metric": "自纠率",
                "value": scr,
                "threshold": threshold,
                "calls": m.get("calls", 0),
                "source_file": f"agent/tools/{name.replace('-', '_')}.py",
            })
    return {
        "prompt": TOOLS_PROMPT,
        "threshold": threshold,
        "flagged": flagged,
    }


def tool_metric_row(name: str, m: dict) -> dict[str, Any]:
    """eval_tools 结果 → 前端 ToolMetric 形态。"""
    return {
        "name": name,
        "type": TOOL_TYPE_MAP.get(name, "会话"),
        "scope": "default",
        "calls": m.get("calls", 0),
        "self_correct_rate": m.get("self_correction_rate", 0),
        "success_rate": m.get("success_rate", 0),
        "latency_p50": m.get("p50_ms", 0),
        "latency_p95": m.get("p95_ms", 0),
    }
