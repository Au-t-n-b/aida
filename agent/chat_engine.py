"""
会话 ReAct 引擎 ·《交付 Claw/Agent 工程范式》§3.5 会话形态

与 zhgk 任务图共享同一底座（同一个 llm.py + DEFAULT_TOOLS + Langfuse）。
流式 ReAct 循环：
  stream LLM → 边出 token 边累积 tool_calls
            → 有工具：执行回灌 → 下一轮 stream
            → 无工具：done
yield 统一事件流（供 SSE / 前端 ClawRail 消费）：
  {"type": "token",        "text": ...}              模型逐字输出
  {"type": "tool_call",    "name", "args"}            模型决定调工具
  {"type": "tool_result",  "name", "result"}          工具返回
  {"type": "skill_launch", "skill", "run_id", "project_code", "scenario_run", "steps"}
                                                        skill-as-tool：后端已自动启动 LangGraph，
                                                        run_id 直接给前端订阅 /agent/<skill>/stream/<run_id>
  {"type": "done"}                                    本轮结束
  {"type": "error",        "message"}                 异常

多轮记忆（§3.5「会话用 thread_id 存多轮记忆」）：
  传 conv_id 时，从 ConversationStore 加载历史 → 喂回模型 → 本轮 user/assistant 存回。

可观测（§3.5「会话也进 trace」）：
  - LLM 调用：get_llm() 已挂 Langfuse callbacks；这里再给会话轮次打 scope/run_name 标签
  - 工具调用：走 execute_traced，与 step 侧的 ctx.call_tool 共用同一 trace helper
"""
from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Awaitable, Callable, Iterator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agent.llm import get_llm
from agent.tools import DEFAULT_TOOLS, ToolRegistry
from agent.tools.trace import execute_traced
from agent.conversation_store import get_conversation_store

# 需要用户确认才执行的工具（会在执行前 yield tool_approval_required 事件）
TOOLS_REQUIRING_APPROVAL: frozenset[str] = frozenset({"send_mail", "send_welink"})

MAX_TOOL_ROUNDS = 6

DEFAULT_SYSTEM = (
    "你是 AIDA 交付助手。可以调用工具完成任务（如读取文件、发邮件、发即时消息、启动智慧工勘）。"
    "回答简洁专业，用中文。需要工具时直接调用，不要编造工具结果。"
    "发邮件或即时消息前，先调 present_choices 向用户确认（收件人/内容摘要/是否发送）。"
    "不要用纯文本问「回复1或2」，必须用 present_choices。"
)

# skill_launch_cb 类型：(skill_id, project) → run_id（后端已启动 LangGraph）
SkillLaunchCb = Callable[[str, dict[str, Any]], Awaitable[str]]
# approval_cb 类型：(approval_id, tool_name, args) → bool（True=允许执行）
ApprovalCb = Callable[[str, str, dict[str, Any]], Awaitable[bool]]


def run_chat(
    user_text: str,
    *,
    history: list | None = None,
    system: str | None = None,
    tools: ToolRegistry | None = None,
    allowed: list[str] | None = None,
    trace_meta: dict | None = None,
    conv_id: str | None = None,
) -> Iterator[dict[str, Any]]:
    """跑一轮会话（含多步工具调用），流式 yield 事件。

    conv_id:    给定则启用后端多轮记忆（加载历史 + 存回本轮）。
    history:    显式历史（仅在未给 conv_id 时生效，向后兼容）。
    trace_meta: 可选会话元数据（如 {"scope":"chat","page":"cockpit"}）打到 Langfuse。
    """
    tools = tools or DEFAULT_TOOLS
    defs = tools.get_definitions(allowed=allowed)
    llm = get_llm()
    bound = llm.bind_tools(defs) if defs else llm

    scope = (trace_meta or {}).get("scope", "chat")
    stream_config = {
        "metadata": {**(trace_meta or {}), "kind": "chat"},
        "tags": [f"scope:{scope}"],
        "run_name": f"{scope}.turn",
    }

    messages: list = [SystemMessage(system or DEFAULT_SYSTEM)]
    # 多轮记忆：优先 conv_id 后端历史，否则用显式 history（兼容）
    store = get_conversation_store() if conv_id else None
    if store is not None:
        for h in store.load(conv_id or ""):
            if h["role"] == "user":
                messages.append(HumanMessage(h["content"]))
            elif h["role"] == "assistant" and h["content"]:
                messages.append(AIMessage(h["content"]))
    elif history:
        messages.extend(history)
    messages.append(HumanMessage(user_text))

    ai_text_parts: list[str] = []

    def _persist() -> None:
        """把本轮 user + assistant 最终文本存回会话记忆。"""
        if store is not None:
            store.append(conv_id or "", "user", user_text)
            store.append(conv_id or "", "assistant", "".join(ai_text_parts))

    try:
        for _ in range(MAX_TOOL_ROUNDS):
            # ── 流式生成本轮（边出 token 边累积 tool_calls）──
            gathered = None
            for chunk in bound.stream(messages, config=stream_config):
                gathered = chunk if gathered is None else gathered + chunk
                if chunk.content:
                    text = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                    if text:
                        ai_text_parts.append(text)
                        yield {"type": "token", "text": text}

            tcs = getattr(gathered, "tool_calls", None) or []
            if not tcs:
                _persist()
                yield {"type": "done"}
                return

            # ── present_choices：本轮立即结束，把选项推给前端 ──
            pc = next((tc for tc in tcs if tc["name"] == "present_choices"), None)
            if pc is not None:
                args = pc.get("args", {})
                yield {
                    "type": "choices",
                    "question": args.get("question", ""),
                    "options": args.get("options", []),
                }
                _persist()
                yield {"type": "done"}
                return

            # ── 有工具调用：执行并回灌，进入下一轮 ──
            messages.append(gathered)  # AIMessage(含 tool_calls)
            for tc in tcs:
                yield {"type": "tool_call", "name": tc["name"], "args": tc.get("args", {})}
                result = execute_traced(
                    tools,
                    tc["name"],
                    tc.get("args", {}),
                    scope=scope,
                    conv_id=conv_id or "",
                )
                yield {"type": "tool_result", "name": tc["name"], "result": str(result)[:800]}

                # skill-as-tool：工具返回 {action:"launch_<skill>", skill, ...} → 通知前端启动
                # 对应任务图并订阅进度（§3.5）。通用化：识别任意 launch_<skill>（不再写死 zhgk），
                # skill 取自 result["skill"]，回退 action 的 launch_ 后缀。
                action = result.get("action", "") if isinstance(result, dict) else ""
                if action.startswith("launch_"):
                    yield {
                        "type": "skill_launch",
                        "skill": result.get("skill") or action[len("launch_"):],
                        "project_code": result.get("project_code", ""),
                        "scenario_run": result.get("scenario_run", ""),
                        "project_name": result.get("project_name", ""),
                        "steps": result.get("steps", []),
                    }

                messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

        _persist()
        yield {"type": "done", "note": f"达到工具轮次上限 {MAX_TOOL_ROUNDS}"}
    except Exception as e:  # noqa: BLE001
        yield {"type": "error", "message": str(e)}


async def run_chat_async(
    user_text: str,
    *,
    history: list | None = None,
    system: str | None = None,
    tools: ToolRegistry | None = None,
    allowed: list[str] | None = None,
    trace_meta: dict | None = None,
    conv_id: str | None = None,
    skill_launch_cb: SkillLaunchCb | None = None,
    approval_cb: ApprovalCb | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """异步 ReAct 会话引擎：astream LLM + asyncio.to_thread 工具执行。

    skill_launch_cb(skill_id, project) → run_id：
        当工具返回 launch_* action 时调用，由 main.py 端点实现（自动启动 LangGraph）。
    事件类型与同步版 run_chat 完全兼容，skill_launch 事件额外携带 run_id。
    """
    tools = tools or DEFAULT_TOOLS
    defs = tools.get_definitions(allowed=allowed)
    llm = get_llm()
    bound = llm.bind_tools(defs) if defs else llm

    scope = (trace_meta or {}).get("scope", "chat")
    stream_config = {
        "metadata": {**(trace_meta or {}), "kind": "chat"},
        "tags": [f"scope:{scope}"],
        "run_name": f"{scope}.turn",
    }

    messages: list = [SystemMessage(system or DEFAULT_SYSTEM)]
    store = get_conversation_store() if conv_id else None
    if store is not None:
        for h in store.load(conv_id or ""):
            if h["role"] == "user":
                messages.append(HumanMessage(h["content"]))
            elif h["role"] == "assistant" and h["content"]:
                messages.append(AIMessage(h["content"]))
    elif history:
        messages.extend(history)
    messages.append(HumanMessage(user_text))

    ai_text_parts: list[str] = []

    def _persist() -> None:
        if store is not None:
            store.append(conv_id or "", "user", user_text)
            store.append(conv_id or "", "assistant", "".join(ai_text_parts))

    try:
        for _ in range(MAX_TOOL_ROUNDS):
            # ── 异步流式生成 ──
            gathered = None
            async for chunk in bound.astream(messages, config=stream_config):
                gathered = chunk if gathered is None else gathered + chunk
                if chunk.content:
                    text = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                    if text:
                        ai_text_parts.append(text)
                        yield {"type": "token", "text": text}

            if gathered is None:
                break
            tcs = getattr(gathered, "tool_calls", None) or []
            if not tcs:
                _persist()
                yield {"type": "done"}
                return

            # ── present_choices 拦截 ──
            pc = next((tc for tc in tcs if tc["name"] == "present_choices"), None)
            if pc is not None:
                args = pc.get("args", {})
                yield {
                    "type": "choices",
                    "question": args.get("question", ""),
                    "options": args.get("options", []),
                }
                _persist()
                yield {"type": "done"}
                return

            # ── 工具执行（asyncio.to_thread 包裹同步工具，不阻塞事件循环）──
            messages.append(gathered)
            for tc in tcs:
                tool_name = tc["name"]
                tool_args = tc.get("args", {})
                yield {"type": "tool_call", "name": tool_name, "args": tool_args}

                # 敏感工具：发信前先请求用户确认
                if tool_name in TOOLS_REQUIRING_APPROVAL and approval_cb is not None:
                    approval_id = f"{conv_id or 'anon'}-{tc['id']}"
                    yield {
                        "type": "tool_approval_required",
                        "approval_id": approval_id,
                        "name": tool_name,
                        "args": tool_args,
                    }
                    try:
                        approved = await approval_cb(approval_id, tool_name, tool_args)
                    except asyncio.TimeoutError:
                        approved = False
                    if not approved:
                        result: Any = f"用户拒绝了工具 '{tool_name}' 的执行请求。"
                        yield {"type": "tool_result", "name": tool_name, "result": result}
                        messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
                        continue

                result = await asyncio.to_thread(
                    execute_traced,
                    tools,
                    tool_name,
                    tool_args,
                    scope=scope,
                    conv_id=conv_id or "",
                )
                yield {"type": "tool_result", "name": tool_name, "result": str(result)[:800]}

                action = result.get("action", "") if isinstance(result, dict) else ""
                if action.startswith("launch_"):
                    skill_id = result.get("skill") or action[len("launch_"):]
                    project = {
                        k: result.get(k, "")
                        for k in ("project_code", "project_name", "scenario_run")
                    }
                    steps = result.get("steps", [])
                    run_id = ""
                    if skill_launch_cb is not None:
                        try:
                            run_id = await skill_launch_cb(skill_id, project)
                        except Exception as cb_err:  # noqa: BLE001
                            run_id = f"err-{cb_err}"
                    yield {
                        "type": "skill_launch",
                        "skill": skill_id,
                        "run_id": run_id,
                        "project_code": project.get("project_code", ""),
                        "scenario_run": project.get("scenario_run", ""),
                        "project_name": project.get("project_name", ""),
                        "steps": steps,
                    }

                messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

        _persist()
        yield {"type": "done", "note": f"达到工具轮次上限 {MAX_TOOL_ROUNDS}"}
    except Exception as e:  # noqa: BLE001
        yield {"type": "error", "message": str(e)}
