"""
Langfuse 集成 · 补全评测四维的「成本 / 延迟」+ 把「质量 / 成功率」写回 score。

数据流（《团队 Agent 开发范式》规范 6）：
  评测脚本算质量/成功率 → fetch_run_metrics() 拉成本/延迟 → write_scores() 写回 trace
  → Langfuse 里每个 run 既有自动指标(cost/latency/token)、又有业务指标(eval.quality/success)
  → 呈现界面 / AI 分析 从同一个源拿。

依赖 llm.py 已初始化的 Langfuse 客户端（v4，get_client）。
"""
from __future__ import annotations

from typing import Optional

from agent.tools.base import is_tool_error


def _client():
    """复用 llm.py 初始化的 Langfuse 单例（确保已 init）。"""
    from agent.llm import get_langfuse_callbacks
    get_langfuse_callbacks()  # 触发 _init_langfuse_once
    from langfuse import get_client
    return get_client()


def fetch_run_metrics(run_id: Optional[str] = None, skill: str = "zhgk") -> dict:
    """
    拉某个 run 的成本/延迟（Langfuse 自动采集）。
    run_id 为空时取该 skill 最近一条 run。

    返回：{trace_id, run_id, cost_cny, latency_ms} 或 {"_error": ...} / {}。
    注：trace.name 形如 "<skill>.run.<run_id>"，据此回解析 run_id。
    """
    c = _client()
    tags = [f"skill:{skill}"]
    if run_id:
        tags.append(f"run:{run_id}")
    try:
        tr = c.api.trace.list(tags=tags, limit=1)
        data = getattr(tr, "data", tr) or []
        if not data:
            return {}
        t = data[0]
        name = getattr(t, "name", "") or ""
        rid = run_id or (name.split(f"{skill}.run.")[-1] if f"{skill}.run." in name else "")
        latency_s = getattr(t, "latency", 0) or 0
        return {
            "trace_id": t.id,
            "run_id": rid,
            "cost_cny": getattr(t, "total_cost", None),
            "latency_ms": int(latency_s * 1000),
        }
    except Exception as e:  # noqa: BLE001
        return {"_error": str(e)}


def fetch_tool_spans(
    days: int = 7,
    limit: int = 500,
    skill: Optional[str] = None,
    conv_id: Optional[str] = None,
    run_id: Optional[str] = None,
    since_iso: Optional[str] = None,
) -> dict:
    """
    拉最近 N 天的工具调用 span（metadata.kind == "tool"），归一为评测记录。

    工具 span 由 execute_traced / SkillContext.call_tool 创建，
    metadata 形如 {tool, kind, scope, step, run_id, conv_id}。

    返回：{"window", "records": [{tool, ok, latency_ms, scope, step, run_id, conv_id, ts, error}, ...]}
          或 {"_error": ...}。ok=False：output 以 "Error" 开头。
    """
    import datetime as _dt

    c = _client()
    if since_iso:
        try:
            from_start = _dt.datetime.fromisoformat(since_iso.replace("Z", "+00:00"))
        except ValueError:
            from_start = _dt.datetime.now() - _dt.timedelta(days=days)
    else:
        from_start = _dt.datetime.now() - _dt.timedelta(days=days)

    try:
        resp = c.api.observations.get_many(
            type="SPAN",
            limit=limit,
            from_start_time=from_start,
        )
        data = getattr(resp, "data", resp) or []
    except Exception as e:  # noqa: BLE001
        return {"_error": str(e)}

    records: list[dict] = []
    for o in data:
        meta = getattr(o, "metadata", None) or {}
        if not isinstance(meta, dict):
            meta = {}
        if meta.get("kind") != "tool":
            continue
        scope = meta.get("scope") or meta.get("skill") or ""
        if skill and scope not in (skill, None, ""):
            continue
        rid = meta.get("run_id") or ""
        cid = meta.get("conv_id") or ""
        if run_id and rid != run_id:
            continue
        if conv_id and cid != conv_id:
            continue
        out = getattr(o, "output", None)
        # 统一成败判定（dict 工具看 ok/error，str 工具看 Error 前缀），与 tools.trace 一致
        ok = not is_tool_error(out if isinstance(out, (str, dict)) else str(out))
        latency_s = getattr(o, "latency", None) or 0
        start = getattr(o, "start_time", None)
        ts = start.isoformat() if hasattr(start, "isoformat") else (str(start) if start else "")
        records.append({
            "tool": meta.get("tool") or getattr(o, "name", "") or "unknown",
            "ok": ok,
            "latency_ms": int(latency_s * 1000),
            "scope": scope,
            "step": meta.get("step") or "",
            "run_id": rid,
            "conv_id": cid,
            "ts": ts,
            "error": "" if ok else out_text[:200],
        })

    window = f"conv:{conv_id}" if conv_id else (f"run:{run_id}" if run_id else f"last-{days}d")
    return {"window": window, "records": records, "conv_id": conv_id, "run_id": run_id}


def write_scores(trace_id: str, scores: dict[str, float]) -> bool:
    """把评测分数写回 Langfuse（关联 trace_id）。score 名建议带 eval. 前缀。"""
    c = _client()
    try:
        for name, value in scores.items():
            c.create_score(name=name, value=float(value), trace_id=trace_id, data_type="NUMERIC")
        c.flush()
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[langfuse] write_scores failed: {e}")
        return False
