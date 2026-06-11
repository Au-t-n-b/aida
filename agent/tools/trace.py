"""
工具受控执行 + 尽力进 Langfuse span（《交付 Claw/Agent 工程范式》§4.2 / 铁律⑤）。

抽出独立 helper，让「会话 ReAct（chat_engine）」与「任务 step（SkillContext.call_tool）」
共用同一套「执行 + trace」逻辑 —— 这正是 §3.5「两形态一底座」在可观测性上的对齐：
无论工具被会话调用还是被 step 调用，都经 ToolRegistry 受控执行，并尽力进同一 Langfuse trace。
"""
from __future__ import annotations

import time
from typing import Any, Callable

from .base import is_tool_error
from .registry import ToolRegistry


def execute_traced(
    registry: ToolRegistry,
    name: str,
    params: dict | None = None,
    *,
    scope: str = "chat",
    step: str = "",
    run_id: str = "",
    conv_id: str = "",
    emit: Callable[[str], None] | None = None,
) -> Any:
    """
    cast → validate → run（由 ToolRegistry 保证），并尽力创建 Langfuse span。

    Args:
        scope: 调用来源（"chat" 或 skill_id），用于 trace 归类。
        step:  step_key（step 调用时给）；会话调用留空。
        run_id: 工勘 run_id（step/skill 调用时给）。
        conv_id: 会话 id（chat 调用时给，供评测按次过滤）。
        emit:  可选日志回调，写一行 "[tool] <name> ok/fail · <ms>ms"。
    """
    params = params or {}
    t0 = time.time()

    # ── 尽力进 Langfuse trace（tool / params / result / latency）；未配置则静默跳过 ──
    span_cm = None
    try:
        from langfuse import get_client  # type: ignore
        span_cm = get_client().start_as_current_span(
            name=f"{scope}.{step or 'tool'}.{name}",
            input=params,
            metadata={
                "scope": scope,
                "step": step,
                "run_id": run_id,
                "conv_id": conv_id,
                "tool": name,
                "kind": "tool",
            },
        )
    except Exception:
        span_cm = None

    if span_cm is not None:
        with span_cm as span:
            result = registry.execute(name, params)
            try:
                span.update(output=result)
            except Exception:
                pass
    else:
        result = registry.execute(name, params)

    ms = int((time.time() - t0) * 1000)
    ok = not is_tool_error(result)
    err_text = "" if ok else (result if isinstance(result, str) else str(result.get("error") or result))
    if conv_id or run_id:
        try:
            from agent.evals.session_tool_log import append_tool_record
            append_tool_record(
                tool=name,
                ok=ok,
                latency_ms=ms,
                scope=scope,
                step=step,
                run_id=run_id,
                conv_id=conv_id,
                error=err_text,
            )
        except Exception:
            pass
    if emit:
        emit(f"[tool] {name} {'ok' if ok else 'fail'} · {ms}ms")
    return result
