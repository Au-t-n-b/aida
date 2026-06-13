"""
AIDA Agent · FastAPI 入口

端点：
    POST /agent/zhgk/start         启动一次工作流（返回 run_id）
    GET  /agent/zhgk/stream/{run_id}  SSE 流式订阅事件
    POST /agent/zhgk/resume        提交 HITL 用户回复 + 续跑
    POST /agent/zhgk/run-patch     运行时补丁（不重跑图 · file_handler.merge_run_patch）
    POST /agent/zhgk/upload        上传文件到 zhgk Input/
    GET  /agent/zhgk/status/{run_id}  当前状态快照
    GET  /agent/zhgk/artifact?path=... 下载产物（仅限 ProjectData/Output/ 子集）
    GET  /healthz                  健康检查

启动：
    cd D:\\code\\aida\\agent
    uvicorn main:app --host 127.0.0.1 --port 7401 --reload
"""
from __future__ import annotations
import asyncio
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, AsyncIterator

import agent.config  # noqa: F401 - load .env and proposal runtime config at startup

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel, ConfigDict, Field

from .graph import get_graph_async, close_graph_async
from .state import AgentState
from .llm import healthcheck as llm_healthcheck, get_langfuse_callbacks
from .chat_engine import run_chat, run_chat_async, DEFAULT_SYSTEM
from .proposal.errors import ProposalApiError
from .proposal.router import router as proposal_router
from .proposal_routes import router as proposal_chapters_router
from .sog_routes import router as sog_router
from .routers.proposal_mock import router as proposal_mock_router

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DELIVERY_PLAN_PATH = PROJECT_ROOT / "data" / "delivery" / "delivery-plan.xlsx"


def _get_sdui_projector(skill_id: str):
    """按 skill_id 从注册表查 SDUI 投影器。未注册或未设置则返回 None。"""
    try:
        from .skills import registry
        skill = registry.get(skill_id)
        return skill.sdui_projector
    except Exception:
        return None


def _sdui_json_safe(doc: dict) -> dict:
    """SDUI 文档 → 可 JSON 序列化的 dict（剔除投影器偶发混入的运行时对象）。"""
    return json.loads(json.dumps(doc, ensure_ascii=False, default=str))


def _get_skill_or_404(skill_id: str):
    """按 skill_id 取 skill 实例；未注册 → 404。"""
    from .skills import registry
    try:
        return registry.get(skill_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"skill '{skill_id}' 未注册")


# ─── 全局 ───

app = FastAPI(title="AIDA Agent · zhgk pilot", version="0.1.0")
app.include_router(sog_router)
app.include_router(proposal_router)
app.include_router(proposal_chapters_router)
app.include_router(proposal_mock_router)

# 允许前端 (Next.js dev server) 跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*",  # 演示期放开，生产期改具体源
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 内存中的 run registry：run_id → {"queue": asyncio.Queue, "state": AgentState, "task": asyncio.Task}
RUNS: dict[str, dict] = {}

# 工具审批挂起池：approval_id → asyncio.Future[bool]（等待前端 /approve-tool 解锁）
_PENDING_APPROVALS: dict[str, "asyncio.Future[bool]"] = {}


@app.exception_handler(ProposalApiError)
async def proposal_api_error_handler(_request: Request, exc: ProposalApiError):
    return JSONResponse(
        status_code=exc.status,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.on_event("shutdown")
async def _shutdown():
    """关闭 AsyncSqliteSaver 的 aiosqlite 连接"""
    await close_graph_async()


# ─── 数据模型 ───

class StartReq(BaseModel):
    """通用启动请求体。extra=allow 让各 skill 自带字段（如 zhgk 的 project_code）原样进 project；
    默认值由 skill.initial_project() 补（见 ZhgkSkill）。"""
    model_config = ConfigDict(extra="allow")
    project_code: str | None = None
    project_name: str | None = None
    scenario_run: str | None = None


class ResumeReq(BaseModel):
    run_id: str
    payload: dict = {}   # 用户填的 HITL 数据，由前端构造
    from_step: str | None = None  # 如 report_distribute：仅重试该步，不全量重跑


class RunPatchReq(BaseModel):
    """运行时补丁请求（/run-patch · 不重跑 LangGraph）。

    payload 约定：{"action": "<动作名>", "rows": [{...}, ...], ...}，
    由各 skill 的 file_handler.merge_run_patch 解释（如 action="task_progress"
    把 rows 里的进度合入 tasks_state.json 并更新 step metrics）。"""
    run_id: str
    payload: dict = {}


class GkclawInboundReq(BaseModel):
    """mailgw 收信后 POST · 触发 poll + wait_survey step_retry。"""
    mail_id: int | None = None
    task_id: str | None = None
    subject: str = ""


def _verify_gkclaw_inbound_token(authorization: str | None = None) -> None:
    token = os.environ.get("MAILGW_TOKEN", "").strip()
    if not token:
        raise HTTPException(status_code=503, detail="MAILGW_TOKEN 未配置")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少 Bearer 认证")
    if authorization.removeprefix("Bearer ").strip() != token:
        raise HTTPException(status_code=403, detail="Bearer token 无效")


def _resolve_hitl_step(state: dict, explicit: str | None, skill_obj) -> str:
    """resume / inbound 用：hitl 为空时从 current_step 推断僵死续跑 step。"""
    if explicit and explicit.strip():
        return explicit.strip()
    hitl_step = (state.get("hitl") or {}).get("step") or ""
    if hitl_step:
        return str(hitl_step)
    from .gkclaw_inbound import pipeline_stalled

    step_keys = [s.key for s in skill_obj.steps]
    stalled = pipeline_stalled(state, step_keys)
    return stalled or ""


def _linear_step_keys(skill) -> tuple[str, ...]:
    return tuple(getattr(skill, "LINEAR_STEP_KEYS", ()) or ())


def _next_linear_step(skill, step_key: str) -> str | None:
    linear = _linear_step_keys(skill)
    if step_key not in linear:
        return None
    idx = linear.index(step_key)
    if idx + 1 >= len(linear):
        return None
    return linear[idx + 1]


def _kick_step_retry(run_id: str, step_key: str) -> None:
    """替换 SSE 队列并异步单步重试（与 /resume step_retry 同路径）。"""
    old_task = RUNS[run_id].get("task")
    if old_task and not old_task.done():
        old_task.cancel()
    RUNS[run_id]["queue"] = asyncio.Queue()
    RUNS[run_id]["attempt"] = RUNS[run_id].get("attempt", 0) + 1
    RUNS[run_id]["task"] = asyncio.create_task(_run_single_step_streaming(run_id, step_key))


# ─── 启动钩子 ───

@app.on_event("startup")
def _on_startup() -> None:
    """启动时刷新 skill 实例缓存，确保 .env 中的 SYSTEM_DESIGN_ROOT 等路径生效。"""
    from .skills import registry
    registry._cache.clear()


# ─── 健康检查 ───

@app.get("/healthz")
def healthz():
    out: dict = {"ok": True}
    # 遍历所有注册 skill 报告工作区健康（不再写死 zhgk）
    from .skills import registry
    skills_health: dict = {}
    for name in registry.names():
        try:
            root = registry.get(name).work_root
            pd = root / "ProjectData"
            skills_health[name] = {
                "work_root": str(root),
                "start_files": len(list((pd / "Start").glob("*"))) if (pd / "Start").exists() else 0,
                "input_files": len(list((pd / "Input").glob("*"))) if (pd / "Input").exists() else 0,
                "output_files": len(list((pd / "Output").glob("*"))) if (pd / "Output").exists() else 0,
            }
        except Exception as e:  # noqa: BLE001
            skills_health[name] = {"error": str(e)}
            out["ok"] = False
    out["skills"] = skills_health
    out["llm"] = llm_healthcheck()
    if not out["llm"].get("configured"):
        out["ok"] = False
    code = 200 if out["ok"] else 500
    return JSONResponse(status_code=code, content=out)


# ─── Skill 注册中心（渐进式暴露门面） ───

@app.get("/agent/skills")
def list_skills():
    """
    返回所有已注册 skill 的元数据（仅 name + description，不含 step / 正文）。
    路由层 / 前端 Skill Picker 拿这份做选择。
    """
    from .skills import registry
    return {"skills": registry.list_metadata()}


@app.get("/agent/skills/{skill_name}")
def get_skill(skill_name: str):
    """返回单个 skill 的完整 metadata（含 frontmatter + 正文摘要 + step 列表）"""
    from .skills import registry
    try:
        skill = registry.get(skill_name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' 未注册")
    md = skill.metadata
    return {
        "name": skill.name,
        "description": skill.description,
        "source_path": md.source_path,
        "frontmatter": md.raw_frontmatter,
        "body_excerpt": md.body_excerpt,
        "steps": [{"key": s.key, "name": s.name} for s in skill.steps],
    }


# ─── 工作流启动 ───

async def _run_graph_streaming(run_id: str, init_state: AgentState, thread_id: str | None = None):
    """后台跑 LangGraph，所有 update 推到 run_id 对应 queue。
    thread_id 默认 = run_id；resume 重跑时传新 thread_id，避免命中已 END 的旧 checkpoint。"""
    from .skills.base import register_run_push, unregister_run_push

    queue: asyncio.Queue = RUNS[run_id]["queue"]
    skill_id = init_state.get("skill_id", "zhgk")
    graph = await get_graph_async(skill_id)
    proj = init_state.get("project", {}) or {}
    # 顶层 config：注入 Langfuse callbacks + 整个 run 的元数据
    # → 每个 LangGraph 节点变成 trace 上的 child span，
    #   每个 LLM 调用嵌套在对应 step span 下
    config = {
        "configurable": {"thread_id": thread_id or run_id},
        "callbacks": get_langfuse_callbacks(),
        "metadata": {
            "skill": skill_id,
            "run_id": run_id,
            "project_code": proj.get("project_code", ""),
            "project_name": proj.get("project_name", ""),
            "scenario": proj.get("scenario_run", ""),
        },
        "tags": [f"skill:{skill_id}", f"run:{run_id}"],
        "run_name": f"{skill_id}.run.{run_id}",
    }

    # ── thread-safe 推送机制 ─────────────────────────────────────────────────────
    # LangGraph 在线程池中执行每个节点（同步 _node(state)），无法 await。
    # 用 loop.call_soon_threadsafe + queue.put_nowait 在线程内向 SSE queue 推事件。
    loop = asyncio.get_running_loop()
    RUNS[run_id]["_running_step"] = None   # {key, name, log_tail} | None
    _emit_cnt: dict[str, int] = {}         # step_key → emit 累计次数（节流用）

    def _patched_state_with_running() -> dict:
        """构造带 running 记录的临时 state（不修改原 state）。"""
        cur = RUNS[run_id]["state"]
        running = RUNS[run_id].get("_running_step")
        if not running:
            return cur
        existing = cur.get("steps") or []
        if any(s.get("key") == running["key"] for s in existing):
            return cur  # 该 step 已有完整记录（不应出现，但防御）
        return {
            **cur,
            "steps": existing + [{
                "key":      running["key"],
                "name":     running["name"],
                "status":   "running",
                "log_tail": list(running.get("log_tail") or []),
            }],
        }

    def _push_sdui_overlay() -> None:
        """用带 running 记录的 patched state 生成 SDUI 并推入队列（线程安全）。"""
        try:
            _proj = _get_sdui_projector(skill_id)
            if _proj is None:
                return
            sdui_doc = _sdui_json_safe(_proj(_patched_state_with_running()))
            loop.call_soon_threadsafe(queue.put_nowait, {"event": "sdui", "data": sdui_doc})
        except Exception as e:
            import sys, traceback
            traceback.print_exc(file=sys.stderr)
            sys.stderr.write(f"[sdui] overlay push failed: {e}\n")

    def _thread_push(item: dict) -> None:
        """step_started / step_log 的 thread-safe 分发器（在线程池中被调用）。"""
        ev = item.get("event", "")

        if ev == "step_started":
            d = item["data"]
            RUNS[run_id]["_running_step"] = {
                "key":      d["step"],
                "name":     d["name"],
                "log_tail": [],
            }
            _emit_cnt[d["step"]] = 0
            # 推 SDUI：Stepper 中该节点立即变为蓝色 running 圆点
            _push_sdui_overlay()

        elif ev == "step_log":
            d = item["data"]
            step_key = d["step"]
            running = RUNS[run_id].get("_running_step")
            if running and running.get("key") == step_key:
                tail: list = running.setdefault("log_tail", [])
                tail.append(d["msg"])
                if len(tail) > 8:
                    running["log_tail"] = tail[-8:]
            # 节流：每 5 条 emit 推一次 SDUI（避免高频 LLM step 频繁序列化）
            cnt = _emit_cnt.get(step_key, 0) + 1
            _emit_cnt[step_key] = cnt
            if cnt % 5 == 0:
                _push_sdui_overlay()

    register_run_push(run_id, _thread_push)

    try:
        # LangGraph 0.2+ 提供 .astream() —— yield 每个节点完成后的 state diff
        async for chunk in graph.astream(init_state, config=config):
            # 节点已完成：清除 running_step（completed diff 马上会覆盖 stepper 状态）
            RUNS[run_id]["_running_step"] = None
            # chunk 形如 {"<node_name>": {<state diff>}}
            for node_name, diff in chunk.items():
                await queue.put({
                    "event": "node_update",
                    "data": {"node": node_name, "diff": diff},
                })
                # 把 diff 合到 cached state
                cur = RUNS[run_id]["state"]
                for k, v in diff.items():
                    if k in ("logs", "steps") and isinstance(v, list):
                        cur.setdefault(k, []).extend(v)
                    else:
                        cur[k] = v
                # SDUI 投影：每个节点完成后更新一次 UI 树（用真实 state，无 overlay）
                try:
                    _proj = _get_sdui_projector(skill_id)
                    if _proj is not None:
                        sdui_doc = _sdui_json_safe(_proj(RUNS[run_id]["state"]))
                        await queue.put({"event": "sdui", "data": sdui_doc})
                except Exception as e:
                    import sys, traceback
                    traceback.print_exc(file=sys.stderr)
                    sys.stderr.write(f"[sdui] push failed after {node_name}: {e}\n")

        final_state = RUNS[run_id]["state"]
        hitl = final_state.get("hitl") or {}
        skill_obj = _get_skill_or_404(skill_id)
        step_keys = [s.key for s in skill_obj.steps]
        from .gkclaw_inbound import pipeline_stalled

        stall_step = pipeline_stalled(final_state, step_keys)
        if not hitl.get("step") and stall_step and stall_step in skill_obj.step_retry_keys:
            _kick_step_retry(run_id, stall_step)
            await queue.put({"event": "done", "data": {"run_id": run_id, "auto_recover": stall_step}})
            return

        if not hitl.get("step"):
            asyncio.create_task(_trigger_eval_background(run_id=run_id, skill_id=skill_id))

        await queue.put({"event": "done", "data": {"run_id": run_id}})
    except asyncio.CancelledError:
        return
    except Exception as e:
        await queue.put({"event": "error", "data": {"error": str(e)}})
    finally:
        unregister_run_push(run_id)
        RUNS[run_id].pop("_running_step", None)
        await queue.put(None)  # sentinel


@app.post("/agent/{skill}/start")
async def start_run(skill: str, req: StartReq):
    """启动一次工作流（skill 决定跑哪张图）。"""
    skill_obj = _get_skill_or_404(skill)
    run_id = f"run-{uuid.uuid4().hex[:10]}"
    project = skill_obj.initial_project(req.model_dump(exclude_none=True))

    if str(project.get("entry_mode") or "").strip() == "commission":
        builder = getattr(skill_obj, "build_commission_entry_state", None)
        if callable(builder):
            built = builder(run_id, project)
            if built.get("error"):
                raise HTTPException(400, str(built["error"]))
            queue: asyncio.Queue = asyncio.Queue()
            RUNS[run_id] = {"queue": queue, "state": built, "task": None}
            await _push_sdui_snapshot(run_id)
            return {"run_id": run_id, "status": "commission_ready", "mode": "commission_entry"}

    init_state: AgentState = {
        "run_id": run_id,
        "skill_id": skill,
        "project": project,
        "steps": [],
        "logs": [f"[start] run {run_id} · {skill} · {project.get('project_code', '')}"],
        "overall_progress": 0,
    }
    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(_run_graph_streaming(run_id, init_state))
    RUNS[run_id] = {"queue": queue, "state": init_state, "task": task}
    return {"run_id": run_id, "status": "started"}


# ─── SSE 订阅 ───

async def _sse_generator(run_id: str) -> AsyncIterator[dict]:
    if run_id not in RUNS:
        yield {"event": "error", "data": json.dumps({"error": "run_id not found"})}
        return

    async def _send_snapshot() -> AsyncIterator[dict]:
        """快照辅助：发 snapshot + sdui，供首连和 resume 无缝切换时复用。"""
        yield {"event": "snapshot", "data": json.dumps(RUNS[run_id]["state"], ensure_ascii=False, default=str)}
        try:
            _skill_id = RUNS[run_id]["state"].get("skill_id", "zhgk")
            _proj = _get_sdui_projector(_skill_id)
            if _proj is not None:
                sdui_snap = _proj(RUNS[run_id]["state"])
                yield {"event": "sdui", "data": json.dumps(sdui_snap, ensure_ascii=False, default=str)}
        except Exception as e:
            import sys, traceback
            traceback.print_exc(file=sys.stderr)
            sys.stderr.write(f"[sdui] snapshot push failed for {run_id}: {e}\n")

    # 先把当前 state + SDUI 快照发一份给客户端（避免错过早期 node_update）
    async for ev in _send_snapshot():
        yield ev

    # 捕获当前队列引用；resume 时会替换队列，通过对象比较感知切换
    current_queue: asyncio.Queue = RUNS[run_id]["queue"]

    # ── 快速完成的重连场景 ──────────────────────────────────────────────
    # 若 run 已结束（task.done()）且队列为空（None 哨兵已被首连消费），
    # 再调用 current_queue.get() 会永久阻塞。直接补发 close 即可。
    _task = RUNS[run_id].get("task")
    if _task is not None and _task.done() and current_queue.empty():
        yield {"event": "close", "data": json.dumps({"ok": True})}
        return

    while True:
        item = await current_queue.get()
        if item is None:
            # 旧任务已结束（CancelledError finally 放哨兵）——
            # 判断是 resume（队列已换新）还是真正终止
            new_queue = RUNS[run_id].get("queue")
            if new_queue is not None and new_queue is not current_queue:
                # Resume 场景：无缝切换到新队列，重发快照，前端不断开
                current_queue = new_queue
                async for ev in _send_snapshot():
                    yield ev
                continue
            # 正常结束：持续保持 SSE 连接 5 秒，让浏览器有足够时间处理
            # close 事件后再关闭，避免前端因网络抖动来不及消费就断连重试。
            await asyncio.sleep(5)
            break
        yield {
            "event": item["event"],
            "data": json.dumps(item["data"], ensure_ascii=False, default=str),
        }
    yield {"event": "close", "data": json.dumps({"ok": True})}


@app.get("/agent/{skill}/stream/{run_id}")
async def stream(skill: str, run_id: str):
    return EventSourceResponse(_sse_generator(run_id))


# ─── 通用会话（ReAct · 流式 + 工具）─── 所有页面 ClawRail 共用 ───

class ChatReq(BaseModel):
    message: str
    history: list = []          # 多轮历史（仅未给 conv_id 时生效，向后兼容）
    context: dict = {}          # 跨页面上下文：{"project": "K1903", "page": "cockpit"}
    conv_id: str = ""           # 会话 id（§3.5 多轮记忆；给定则走后端会话历史）


def _chat_system(context: dict) -> str:
    """把「当前项目/页面」注入 system，支持"对当前页面提问"。"""
    base = DEFAULT_SYSTEM
    bits = []
    if context.get("project"):
        bits.append(f"当前项目：{context['project']}")
    if context.get("page"):
        bits.append(f"当前页面：{context['page']}")
    if bits:
        base += "\n\n[上下文] " + " · ".join(bits) + "。用户说的「当前页面 / 这个」即指此。"
    return base


@app.post("/agent/chat/stream")
async def chat_stream_endpoint(req: ChatReq):
    """
    通用会话 SSE：异步流式 token + 工具调用事件。
    前端用 fetch + ReadableStream 读 SSE（POST 带 body）。

    skill-as-tool 检测到 launch_* 时自动启动 LangGraph，
    skill_launch 事件携带 run_id，前端直接订阅 /agent/<skill>/stream/<run_id>。
    """
    ctx = req.context or {}
    conv_id = (req.conv_id or "").strip()

    async def _skill_launch_cb(skill_id: str, project: dict) -> str:
        """chat 触发 skill-as-tool → 自动启动 LangGraph，返回 run_id。"""
        try:
            skill_obj = _get_skill_or_404(skill_id)
            _run_id = f"chat-{uuid.uuid4().hex[:10]}"
            full_project = skill_obj.initial_project(project)
            init_state: AgentState = {
                "run_id": _run_id,
                "skill_id": skill_id,
                "project": full_project,
                "steps": [],
                "logs": [f"[chat] 由会话引擎自动启动 · {project.get('project_code', '')}"],
                "overall_progress": 0,
            }
            RUNS[_run_id] = {"queue": asyncio.Queue(), "state": init_state, "task": None}
            task = asyncio.create_task(_run_graph_streaming(_run_id, init_state))
            RUNS[_run_id]["task"] = task
            return _run_id
        except Exception as e:  # noqa: BLE001
            return f"err-{e}"

    async def _events() -> AsyncIterator[dict]:
        output: asyncio.Queue = asyncio.Queue()
        flags = {"had_tools": False}  # 可变容器，避免 nonlocal 嵌套歧义

        async def _heartbeat() -> None:
            while True:
                await asyncio.sleep(25)
                await output.put({"event": "heartbeat", "data": json.dumps({"type": "heartbeat"})})

        async def _approval_cb(approval_id: str, tool_name: str, args: dict) -> bool:
            """挂起当前工具执行，等待前端 /approve-tool 响应（最长 5 分钟）。"""
            loop = asyncio.get_event_loop()
            future: asyncio.Future[bool] = loop.create_future()
            _PENDING_APPROVALS[approval_id] = future
            try:
                return await asyncio.wait_for(asyncio.shield(future), timeout=300.0)
            except asyncio.TimeoutError:
                return False
            finally:
                _PENDING_APPROVALS.pop(approval_id, None)

        async def _chat_task() -> None:
            try:
                async for ev in run_chat_async(
                    req.message,
                    history=req.history or None,
                    system=_chat_system(ctx),
                    trace_meta={"scope": "chat", "page": ctx.get("page", "")},
                    conv_id=conv_id or None,
                    skill_launch_cb=_skill_launch_cb,
                    approval_cb=_approval_cb,
                ):
                    if ev.get("type") == "tool_call":
                        flags["had_tools"] = True
                    await output.put({"event": ev["type"], "data": json.dumps(ev, ensure_ascii=False, default=str)})
            except Exception as e:  # noqa: BLE001
                await output.put({"event": "error", "data": json.dumps({"type": "error", "message": str(e)})})
            finally:
                await output.put(None)  # sentinel

        hb_task = asyncio.create_task(_heartbeat())
        asyncio.create_task(_chat_task())
        try:
            while True:
                item = await output.get()
                if item is None:
                    break
                yield item
        finally:
            hb_task.cancel()

        if flags["had_tools"] and conv_id:
            asyncio.create_task(_trigger_eval_background(conv_id=conv_id))

    return EventSourceResponse(_events())


# ─── 工具审批（HITL · 敏感工具执行前等待用户确认）───

class ApproveToolReq(BaseModel):
    approval_id: str
    approved: bool


@app.post("/agent/chat/approve-tool")
async def approve_tool(req: ApproveToolReq):
    """前端审批卡片点"批准"或"拒绝"后调此接口，解锁挂起的工具调用。"""
    future = _PENDING_APPROVALS.get(req.approval_id)
    if future is None or future.done():
        raise HTTPException(404, "approval_id 不存在或已超时")
    future.set_result(req.approved)
    return {"ok": True, "approved": req.approved}


# ─── HITL 续跑 ───

async def _run_single_step_streaming(run_id: str, step_key: str, *, _chain: bool = True) -> None:
    """仅重试单个 step（用于 report_distribute / wait_survey 等：前置产物已在磁盘）。"""
    from .skills.base import SkillContext
    from .gkclaw_inbound import should_chain_after_wait_survey

    queue: asyncio.Queue = RUNS[run_id]["queue"]
    skill_id = RUNS[run_id]["state"].get("skill_id", "zhgk")
    skill = _get_skill_or_404(skill_id)
    step = next((s for s in skill.steps if s.key == step_key), None)
    if step is None:
        await queue.put({"event": "error", "data": {"error": f"unknown step: {step_key}"}})
        await queue.put(None)
        return

    state: AgentState = dict(RUNS[run_id]["state"])
    state["hitl"] = {}
    state["error"] = ""
    ctx = SkillContext(
        skill_id=skill.name,
        work_root=skill.work_root,
        run_id=run_id,
        project=state.get("project") or {},
        llm_factory=skill.llm_factory,
        # step_retry 路径在主线程同步执行，emit_push 无法做中途 yield；
        # 但 step_started 信号在 execute_step 进入前手动推（见下方）。
        emit_push=None,
    )
    # 在 execute_step 阻塞之前先推一次 running SDUI，让 Stepper 变蓝
    try:
        RUNS[run_id]["_running_step"] = {"key": step_key, "name": step.name, "log_tail": []}
        _proj_pre = _get_sdui_projector(skill_id)
        if _proj_pre is not None:
            cur_pre = RUNS[run_id]["state"]
            existing_pre = cur_pre.get("steps") or []
            if not any(s.get("key") == step_key for s in existing_pre):
                patched_pre = {
                    **cur_pre,
                    "steps": existing_pre + [{
                        "key": step_key, "name": step.name,
                        "status": "running", "log_tail": [],
                    }],
                }
            else:
                patched_pre = cur_pre
            await queue.put({"event": "sdui", "data": _proj_pre(patched_pre)})
    except Exception:
        pass

    try:
        diff = skill.execute_step(step, state, ctx)
        RUNS[run_id]["_running_step"] = None  # 执行完毕，清除 running 标记
        cur = RUNS[run_id]["state"]
        for k, v in diff.items():
            if k in ("logs", "steps") and isinstance(v, list):
                cur.setdefault(k, []).extend(v)
            else:
                cur[k] = v
        await queue.put({
            "event": "node_update",
            "data": {"node": step_key, "diff": diff},
        })
        # SDUI 投影：step_retry 后也推一棵完整 UI 树（与 _run_graph_streaming 对齐）；
        # 前端 useSduiStream 只订 sdui 事件，缺这步则重试成功后界面停在旧态不刷新。
        try:
            _proj = _get_sdui_projector(skill_id)
            if _proj is not None:
                await queue.put({"event": "sdui", "data": _proj(RUNS[run_id]["state"])})
        except Exception:
            pass
        hitl = (diff.get("hitl") or {}) if isinstance(diff.get("hitl"), dict) else {}
        chain_to = (
            should_chain_after_wait_survey(
                prev_step=step_key,
                state=RUNS[run_id]["state"],
                step_retry_keys=skill.step_retry_keys,
            )
            if _chain and not hitl.get("step") and not diff.get("error")
            else None
        )
        if chain_to:
            await _run_single_step_streaming(run_id, chain_to, _chain=False)
            return
        # system_design：publish_confirm 确认发布后链式执行 publish（step_retry 不重跑前置 LLD/ZTP）
        if (
            step_key == "publish_confirm"
            and not hitl.get("step")
            and not diff.get("error")
            and (RUNS[run_id]["state"].get("project") or {}).get("confirmations", {}).get("publish")
        ):
            await _run_single_step_streaming(run_id, "publish")
            return
        if not hitl.get("step") and not diff.get("error"):
            asyncio.create_task(_trigger_eval_background(run_id=run_id, skill_id=skill_id))
        await queue.put({"event": "done", "data": {"run_id": run_id}})
    except Exception as e:
        RUNS[run_id]["_running_step"] = None
        await queue.put({"event": "error", "data": {"error": str(e)}})
    finally:
        await queue.put(None)


@app.post("/agent/{skill}/resume")
async def resume_run(skill: str, req: ResumeReq):
    if req.run_id not in RUNS:
        raise HTTPException(404, "run_id not found")
    prev = RUNS[req.run_id]["state"]
    skill_id = prev.get("skill_id", skill)
    skill_obj = _get_skill_or_404(skill_id)
    hitl_step = _resolve_hitl_step(prev, req.from_step, skill_obj)

    old_task = RUNS[req.run_id].get("task")
    if old_task and not old_task.done():
        old_task.cancel()
    RUNS[req.run_id]["queue"] = asyncio.Queue()

    # 确认型 HITL 先把用户选择写入 project（step_retry 与 full_restart 均需）
    project = skill_obj.apply_resume_payload(
        prev.get("project", {}) or {}, req.payload or {}, hitl_step
    )
    RUNS[req.run_id]["state"] = {**prev, "project": project}

    # 该 step 声明支持 step_retry：仅重试本步，避免重跑前序 LLM（如 zhgk report_distribute）
    if hitl_step and hitl_step in skill_obj.step_retry_keys:
        RUNS[req.run_id]["attempt"] = RUNS[req.run_id].get("attempt", 0) + 1
        task = asyncio.create_task(_run_single_step_streaming(req.run_id, hitl_step))
        RUNS[req.run_id]["task"] = task
        return {
            "run_id": req.run_id,
            "status": "resumed",
            "mode": "step_retry",
            "from_step": hitl_step,
            "message": f"仅重试「{hitl_step}」，不会重跑前序步骤。",
        }

    # 其余 HITL：全量从预检重跑（缺失文件已补齐后一路跑通）
    RUNS[req.run_id]["attempt"] = RUNS[req.run_id].get("attempt", 0) + 1
    attempt = RUNS[req.run_id]["attempt"]
    init_state: AgentState = {
        "run_id": req.run_id,
        "skill_id": prev.get("skill_id", "zhgk"),
        "project": project,
        "steps": [],
        "logs": [f"[resume] 补齐文件后全量重跑（attempt {attempt}）"],
        "overall_progress": 0,
    }
    RUNS[req.run_id]["state"] = init_state
    new_tid = f"{req.run_id}-r{attempt}"
    task = asyncio.create_task(_run_graph_streaming(req.run_id, init_state, thread_id=new_tid))
    RUNS[req.run_id]["task"] = task
    return {
        "run_id": req.run_id,
        "status": "resumed",
        "thread_id": new_tid,
        "mode": "full_restart",
        "from_step": None,
        "message": "将从环境预检重新执行全流程（含场景筛选、勘测汇总、评估报告等）。",
    }


@app.post("/agent/{skill}/gkclaw/inbound")
async def gkclaw_inbound(
    skill: str,
    req: GkclawInboundReq,
    authorization: str | None = Header(None),
):
    """mailgw 收信回调：poll GKCLAW 包并按 task_id 唤醒 wait_survey（step_retry + SSE）。"""
    _verify_gkclaw_inbound_token(authorization)
    if skill != "zhgk":
        raise HTTPException(404, f"skill '{skill}' 不支持 GKCLAW inbound")

    from .gkclaw_inbound import (
        parse_task_id_from_subject,
        plan_inbound_action,
        poll_gkclaw_inbox,
    )

    skill_obj = _get_skill_or_404(skill)
    task_id = (req.task_id or "").strip() or parse_task_id_from_subject(req.subject) or ""

    try:
        ingest_summary = poll_gkclaw_inbox(work_root=skill_obj.work_root)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"GKCLAW poll 失败: {e}") from e

    step_keys = [s.key for s in skill_obj.steps]
    plan = plan_inbound_action(
        runs=RUNS,
        skill_step_keys=step_keys,
        step_retry_keys=skill_obj.step_retry_keys,
        task_id=task_id or None,
    )

    triggered = False
    if plan.get("trigger") and plan.get("run_id") and plan.get("step"):
        _kick_step_retry(str(plan["run_id"]), str(plan["step"]))
        triggered = True
    elif plan.get("run_id"):
        # 仅刷新 SDUI（如 staged ACK / run 不在 wait_survey）
        run_id = str(plan["run_id"])
        try:
            proj = _get_sdui_projector(skill)
            if proj is not None and run_id in RUNS:
                await RUNS[run_id]["queue"].put({
                    "event": "sdui",
                    "data": proj(RUNS[run_id]["state"]),
                })
        except Exception:
            pass

    return {
        "ok": True,
        "task_id": task_id or None,
        "mail_id": req.mail_id,
        "ingest": ingest_summary,
        "plan": plan,
        "triggered_step_retry": triggered,
    }


# ─── 运行时补丁（run-patch · 与 /resume 同级，不重跑图）───

@app.post("/agent/{skill}/run-patch")
async def run_patch(skill: str, req: RunPatchReq):
    """通用运行时补丁端点。

    与 /resume 的区别：resume 解除 HITL 软中断并重跑 LangGraph（full_restart /
    step_retry）；run-patch **不触发任何图执行**，用于流程完工后的小步数据回写
    （如「任务进展表」改进度百分比），前端 DataTable 声明 submitMode="run-patch"
    时提交走本端点。

    skill 侧约定（鸭子类型 · 与 infer_upload_kind 等同挂在 file_handler 模块上）：
        merge_run_patch(work_root: Path, run_state: dict, payload: dict) -> dict
        - 返回 {"ok": True, ...} 或 {"ok": False, "error": "..."}
        - 负责落盘（如 tasks_state.json）；可就地更新 run_state（如 steps[].metrics），
          供随后的 SDUI 投影反映新值。
    未实现 merge_run_patch → 501（与 /upload 缺 file_handler 同语义）。

    标准行为：补丁成功后立即向该 run 的 SSE 队列推一棵新 SDUI 树 ——
    订阅中的前端大盘即时刷新，无需重连或重跑。
    """
    if req.run_id not in RUNS:
        raise HTTPException(404, "run_id not found")
    state = RUNS[req.run_id]["state"]
    skill_id = state.get("skill_id", skill)
    skill_obj = _get_skill_or_404(skill_id)
    merge = getattr(skill_obj.file_handler, "merge_run_patch", None)
    if merge is None:
        raise HTTPException(
            status_code=501,
            detail=f"skill '{skill_id}' 未实现 file_handler.merge_run_patch（run-patch 不可用）",
        )

    try:
        result = merge(skill_obj.work_root, state, req.payload or {})
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"merge_run_patch 异常：{e}")
    if not isinstance(result, dict):
        result = {"ok": bool(result)}
    if not result.get("ok"):
        return JSONResponse(
            status_code=422,
            content={"ok": False, "error": str(result.get("error", "merge_run_patch 拒绝该补丁"))},
        )

    # 补丁后推送新 SDUI（run 已结束无订阅者时静默丢弃；重连快照走最新 state，同样是新值）
    try:
        proj = _get_sdui_projector(skill_id)
        if proj is not None:
            RUNS[req.run_id]["queue"].put_nowait({"event": "sdui", "data": proj(state)})
    except Exception:
        pass

    extra = {k: v for k, v in result.items() if k != "ok"}
    return {"ok": True, "run_id": req.run_id, **extra}


# ─── 文件上传 / HITL 齐备检查 ───

def _get_file_handler_or_501(skill_id: str):
    """取 skill 的文件补齐处理器；未配置 → 501。返回 (skill, handler)。"""
    skill = _get_skill_or_404(skill_id)
    fh = skill.file_handler
    if fh is None:
        raise HTTPException(status_code=501, detail=f"skill '{skill_id}' 未配置文件补齐 HITL")
    return skill, fh


@app.get("/agent/{skill}/files/check")
def files_check(skill: str, need: list[str] = Query(default=[])):
    """扫描文件齐备情况。传 need= 多次为当前 HITL 缺失项；否则查该 skill 的默认前置集。"""
    skill_obj, fh = _get_file_handler_or_501(skill)
    root = skill_obj.work_root
    if need:
        return fh.check_need_files(root, need)
    return fh.check_project_files(root)


@app.post("/agent/{skill}/upload")
async def upload(
    skill: str,
    kind: str = Form(..., description="上传类型，由各 skill 的 file_handler.infer_upload_kind 定义"),
    file: UploadFile = File(...),
):
    """上传单个文件到该 skill 工作区"""
    skill_obj, fh = _get_file_handler_or_501(skill)
    return await fh.save_upload(skill_obj.work_root, kind, file)


@app.post("/agent/{skill}/upload/batch")
async def upload_batch(
    skill: str,
    files: list[UploadFile] = File(..., description="多文件，按文件名自动路由目录"),
    need: list[str] = Form(default=[], description="当前 HITL need_files，用于返回对齐的齐备检查"),
):
    """批量上传；不自动续跑。传 need 时 check 按 HITL 缺失项，否则查该 skill 默认前置集。"""
    skill_obj, fh = _get_file_handler_or_501(skill)
    if not files:
        raise HTTPException(400, "未选择文件")
    root = skill_obj.work_root
    results: list[dict] = []
    for f in files:
        kind = fh.infer_upload_kind(f.filename or "")
        try:
            results.append(await fh.save_upload(root, kind, f))
        except Exception as e:  # noqa: BLE001
            results.append({"ok": False, "filename": f.filename, "error": str(e)})
    check = fh.check_need_files(root, need) if need else fh.check_project_files(root)
    return {"uploaded": results, "check": check}


# ─── 状态快照 ───

@app.get("/agent/{skill}/status/{run_id}")
def status(skill: str, run_id: str):
    if run_id not in RUNS:
        raise HTTPException(404, "run_id not found")
    return RUNS[run_id]["state"]


# ─── 产物下载 ───

@app.get("/agent/{skill}/artifact")
def artifact(skill: str, path: str = Query(..., description="相对 skill 工作区根目录的产物路径")):
    """安全下载产物 · 只允许 ProjectData/ 子树下"""
    skill_obj = _get_skill_or_404(skill)
    root = skill_obj.work_root
    full = (root / path).resolve()
    try:
        full.relative_to((root / "ProjectData").resolve())
    except ValueError:
        raise HTTPException(403, "path outside ProjectData")
    if not full.exists() or not full.is_file():
        raise HTTPException(404, "not found")
    return FileResponse(str(full), filename=full.name)


# ─── 评测看板 ───

def _skill_eval_summary(runs: list[dict]) -> dict:
    if not runs:
        return {}
    quality_scores = [r["quality_score"] for r in runs if r.get("quality_score") is not None]
    success_count = sum(1 for r in runs if r.get("success"))
    latencies = [r["latency_ms"] for r in runs if r.get("latency_ms")]
    return {
        "quality_avg": round(sum(quality_scores) / len(quality_scores), 3) if quality_scores else None,
        "success_rate": round(success_count / len(runs), 3),
        "success_count": success_count,
        "total": len(runs),
        "latest_quality": runs[0].get("quality_score"),
        "latest_success": runs[0].get("success"),
        "latest_cost_cny": runs[0].get("cost_cny"),
        "latest_latency_ms": runs[0].get("latency_ms"),
        "latency_p50": sorted(latencies)[len(latencies) // 2] if latencies else None,
    }


@app.get("/agent/evals/report")
def evals_report(
    skill: str = Query("zhgk"),
    limit: int = Query(30),
    mode: str = Query("overview"),
):
    """
    读 evals/results/{skill}-*.json。
    mode=latest：仅最近一次 run 详情；mode=overview：历次汇总 + 趋势数据。
    """
    runs = _load_eval_runs(skill, limit)
    if not runs:
        empty = {"skill": skill, "total": 0, "summary": {}, "runs": [], "mode": mode}
        if mode == "latest":
            empty["run"] = None
        return empty

    summary = _skill_eval_summary(runs)
    if mode == "latest":
        return {
            "skill": skill,
            "mode": "latest",
            "total": len(runs),
            "run": runs[0],
            "summary": summary,
            "summary_latest": {
                "quality_score": runs[0].get("quality_score"),
                "success": runs[0].get("success"),
                "cost_cny": runs[0].get("cost_cny"),
                "latency_ms": runs[0].get("latency_ms"),
                "run_id": runs[0].get("run_id"),
                "trace_id": runs[0].get("trace_id"),
                "metrics_source": runs[0].get("metrics_source"),
            },
        }
    return {"skill": skill, "mode": "overview", "total": len(runs), "summary": summary, "runs": runs}


def _evals_results_dir() -> Path:
    return Path(__file__).parent / "evals" / "results"


def _agent_python() -> str:
    """agent/.venv python（与 scripts/agent-python.mjs 同逻辑）。"""
    root = Path(__file__).parent
    for rel in (".venv/Scripts/python.exe", ".venv/bin/python"):
        p = root / rel
        if p.exists():
            return str(p)
    return "python"


def _load_eval_runs(prefix: str, limit: int = 30) -> list[dict]:
    files = sorted(_evals_results_dir().glob(f"{prefix}-*.json"), reverse=True)[:limit]
    runs: list[dict] = []
    for f in files:
        try:
            runs.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return runs


def _tools_report_payload(latest: dict, file_count: int) -> dict:
    from .evals.deviations import tool_metric_row

    raw = latest.get("tools") or {}
    tools = [tool_metric_row(name, m) for name, m in raw.items()]
    overall = latest.get("overall") or {}
    flagged = sum(1 for t in tools if t["self_correct_rate"] > 0.15)
    return {
        "total": file_count,
        "evaluated_at": latest.get("evaluated_at"),
        "source": latest.get("source", "live"),
        "conv_id": latest.get("conv_id", ""),
        "run_id": latest.get("run_id", ""),
        "window": latest.get("window", ""),
        "record_count": latest.get("record_count", len(latest.get("records") or [])),
        "summary": {
            "tool_count": overall.get("tool_count", len(tools)),
            "calls": overall.get("calls", 0),
            "self_correction_rate_avg": overall.get("self_correction_rate"),
            "flagged_count": flagged,
            "quality_score": latest.get("quality_score"),
            "success": latest.get("success"),
        },
        "tools": tools,
        "records": latest.get("records") or [],
        "checks": latest.get("checks") or [],
    }


@app.get("/agent/evals/tools/report")
def evals_tools_report(limit: int = Query(10), mode: str = Query("overview")):
    """读 evals/results/tools-*.json。mode=latest 含调用明细 records。"""
    files = sorted(_evals_results_dir().glob("tools-*.json"), reverse=True)
    latest = None
    for f in files[: max(limit, 1)]:
        try:
            latest = json.loads(f.read_text(encoding="utf-8"))
            break
        except Exception:
            pass

    if not latest:
        empty = {"mode": mode, "total": 0, "summary": {}, "tools": [], "source": "empty"}
        if mode == "latest":
            empty["records"] = []
            empty["checks"] = []
        return empty

    payload = _tools_report_payload(latest, len(files))
    payload["mode"] = mode

    if mode == "latest":
        return payload

    history = []
    for f in files[:limit]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            history.append({
                "evaluated_at": data.get("evaluated_at"),
                "source": data.get("source"),
                "quality_score": data.get("quality_score"),
                "success": data.get("success"),
                "calls": (data.get("overall") or {}).get("calls"),
                "conv_id": data.get("conv_id", ""),
                "run_id": data.get("run_id", ""),
            })
        except Exception:
            pass
    payload["history"] = history
    payload.pop("records", None)
    payload.pop("checks", None)
    return payload


@app.get("/agent/evals/deviations/skill")
def evals_deviations_skill(skill: str = Query("zhgk"), limit: int = Query(30)):
    """SKILL 偏离 JSON（METRICS §7 · 喂 Cursor）。"""
    from .evals.deviations import build_skill_deviations

    runs = _load_eval_runs(skill, limit)
    return build_skill_deviations(runs)


@app.get("/agent/evals/deviations/tools")
def evals_deviations_tools(threshold: float = Query(0.15)):
    """工具偏离 JSON（自纠率超阈值）。"""
    from .evals.deviations import build_tool_deviations

    files = sorted(_evals_results_dir().glob("tools-*.json"), reverse=True)
    if not files:
        return {"prompt": "", "threshold": threshold, "flagged": [], "note": "无 tools 评测结果"}
    try:
        latest = json.loads(files[0].read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(500, str(e)) from e
    return build_tool_deviations(latest.get("tools") or {}, threshold=threshold)


def _eval_subprocess_run(
    script: str,
    extra: list[str] | None = None,
    *,
    fixture: bool = False,
) -> dict:
    import subprocess

    py = _agent_python()
    project = Path(__file__).resolve().parents[1]
    evals = Path(__file__).parent / "evals"
    cmd = [py, str(evals / script)] + (extra or [])
    if fixture:
        cmd.append("--fixture")
    proc = subprocess.run(
        cmd,
        cwd=str(project),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-800:],
        "stderr_tail": (proc.stderr or "")[-400:],
    }


class PreviewBoqUploadResp(BaseModel):
    ok: bool
    proposal_id: str
    filename: str | None = None
    path: str | None = None
    size: int = 0
    uploaded: list[dict[str, Any]] = Field(default_factory=list)
    boq_files: list[dict[str, Any]]


class PreviewBoqListResp(BaseModel):
    ok: bool
    proposal_id: str
    boq_files: list[dict[str, Any]]


class PreviewContractListResp(BaseModel):
    ok: bool
    proposal_id: str
    contracts: list[dict[str, Any]]


# ─── 健康检查 ───

@app.get("/healthz")
def healthz():
    out: dict = {"ok": True}
    # 遍历所有注册 skill 报告工作区健康（不再写死 zhgk）
    from .skills import registry
    skills_health: dict = {}
    for name in registry.names():
        try:
            root = registry.get(name).work_root
            pd = root / "ProjectData"
            skills_health[name] = {
                "work_root": str(root),
                "start_files": len(list((pd / "Start").glob("*"))) if (pd / "Start").exists() else 0,
                "input_files": len(list((pd / "Input").glob("*"))) if (pd / "Input").exists() else 0,
                "output_files": len(list((pd / "Output").glob("*"))) if (pd / "Output").exists() else 0,
            }
        except Exception as e:  # noqa: BLE001
            skills_health[name] = {"error": str(e)}
            out["ok"] = False
    out["skills"] = skills_health
    out["llm"] = llm_healthcheck()
    if not out["llm"].get("configured"):
        out["ok"] = False
    code = 200 if out["ok"] else 500
    return JSONResponse(status_code=code, content=out)


# ─── Skill 注册中心（渐进式暴露门面） ───

@app.get("/agent/skills")
def list_skills():
    """
    返回所有已注册 skill 的元数据（仅 name + description，不含 step / 正文）。
    路由层 / 前端 Skill Picker 拿这份做选择。
    """
    from .skills import registry
    return {"skills": registry.list_metadata()}


@app.get("/agent/skills/{skill_name}")
def get_skill(skill_name: str):
    """返回单个 skill 的完整 metadata（含 frontmatter + 正文摘要 + step 列表）"""
    from .skills import registry
    try:
        skill = registry.get(skill_name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' 未注册")
    md = skill.metadata
    return {
        "name": skill.name,
        "description": skill.description,
        "source_path": md.source_path,
        "frontmatter": md.raw_frontmatter,
        "body_excerpt": md.body_excerpt,
        "steps": [{"key": s.key, "name": s.name} for s in skill.steps],
    }


# ─── 工作流启动 ───

async def _run_graph_streaming(run_id: str, init_state: AgentState, thread_id: str | None = None):
    """后台跑 LangGraph，所有 update 推到 run_id 对应 queue。
    thread_id 默认 = run_id；resume 重跑时传新 thread_id，避免命中已 END 的旧 checkpoint。"""
    from .skills.base import register_run_push, unregister_run_push

    queue: asyncio.Queue = RUNS[run_id]["queue"]
    skill_id = init_state.get("skill_id", "zhgk")
    graph = await get_graph_async(skill_id)
    proj = init_state.get("project", {}) or {}
    # 顶层 config：注入 Langfuse callbacks + 整个 run 的元数据
    # → 每个 LangGraph 节点变成 trace 上的 child span，
    #   每个 LLM 调用嵌套在对应 step span 下
    config = {
        "configurable": {"thread_id": thread_id or run_id},
        "callbacks": get_langfuse_callbacks(),
        "metadata": {
            "skill": skill_id,
            "run_id": run_id,
            "project_code": proj.get("project_code", ""),
            "project_name": proj.get("project_name", ""),
            "scenario": proj.get("scenario_run", ""),
        },
        "tags": [f"skill:{skill_id}", f"run:{run_id}"],
        "run_name": f"{skill_id}.run.{run_id}",
    }

    # ── thread-safe 推送机制 ─────────────────────────────────────────────────────
    # LangGraph 在线程池中执行每个节点（同步 _node(state)），无法 await。
    # 用 loop.call_soon_threadsafe + queue.put_nowait 在线程内向 SSE queue 推事件。
    loop = asyncio.get_running_loop()
    RUNS[run_id]["_running_step"] = None   # {key, name, log_tail} | None
    _emit_cnt: dict[str, int] = {}         # step_key → emit 累计次数（节流用）

    def _patched_state_with_running() -> dict:
        """构造带 running 记录的临时 state（不修改原 state）。"""
        cur = RUNS[run_id]["state"]
        running = RUNS[run_id].get("_running_step")
        if not running:
            return cur
        existing = cur.get("steps") or []
        if any(s.get("key") == running["key"] for s in existing):
            return cur  # 该 step 已有完整记录（不应出现，但防御）
        return {
            **cur,
            "steps": existing + [{
                "key":      running["key"],
                "name":     running["name"],
                "status":   "running",
                "log_tail": list(running.get("log_tail") or []),
            }],
        }

    def _push_sdui_overlay() -> None:
        """用带 running 记录的 patched state 生成 SDUI 并推入队列（线程安全）。"""
        try:
            _proj = _get_sdui_projector(skill_id)
            if _proj is None:
                return
            sdui_doc = _proj(_patched_state_with_running())
            loop.call_soon_threadsafe(queue.put_nowait, {"event": "sdui", "data": sdui_doc})
        except Exception:
            pass

    def _thread_push(item: dict) -> None:
        """step_started / step_log 的 thread-safe 分发器（在线程池中被调用）。"""
        ev = item.get("event", "")

        if ev == "step_started":
            d = item["data"]
            RUNS[run_id]["_running_step"] = {
                "key":      d["step"],
                "name":     d["name"],
                "log_tail": [],
            }
            _emit_cnt[d["step"]] = 0
            # 推 SDUI：Stepper 中该节点立即变为蓝色 running 圆点
            _push_sdui_overlay()

        elif ev == "step_log":
            d = item["data"]
            step_key = d["step"]
            running = RUNS[run_id].get("_running_step")
            if running and running.get("key") == step_key:
                tail: list = running.setdefault("log_tail", [])
                tail.append(d["msg"])
                if len(tail) > 8:
                    running["log_tail"] = tail[-8:]
            # 节流：每 5 条 emit 推一次 SDUI（避免高频 LLM step 频繁序列化）
            cnt = _emit_cnt.get(step_key, 0) + 1
            _emit_cnt[step_key] = cnt
            if cnt % 5 == 0:
                _push_sdui_overlay()

    register_run_push(run_id, _thread_push)

    try:
        # LangGraph 0.2+ 提供 .astream() —— yield 每个节点完成后的 state diff
        async for chunk in graph.astream(init_state, config=config):
            # 节点已完成：清除 running_step（completed diff 马上会覆盖 stepper 状态）
            RUNS[run_id]["_running_step"] = None
            # chunk 形如 {"<node_name>": {<state diff>}}
            for node_name, diff in chunk.items():
                await queue.put({
                    "event": "node_update",
                    "data": {"node": node_name, "diff": diff},
                })
                # 把 diff 合到 cached state
                cur = RUNS[run_id]["state"]
                for k, v in diff.items():
                    if k in ("logs", "steps") and isinstance(v, list):
                        cur.setdefault(k, []).extend(v)
                    else:
                        cur[k] = v
                # SDUI 投影：每个节点完成后更新一次 UI 树（用真实 state，无 overlay）
                try:
                    _proj = _get_sdui_projector(skill_id)
                    if _proj is not None:
                        sdui_doc = _proj(RUNS[run_id]["state"])
                        await queue.put({"event": "sdui", "data": sdui_doc})
                except Exception:
                    pass

        final_state = RUNS[run_id]["state"]
        hitl = final_state.get("hitl") or {}
        if not hitl.get("step"):
            asyncio.create_task(_trigger_eval_background(run_id=run_id, skill_id=skill_id))

        await queue.put({"event": "done", "data": {"run_id": run_id}})
    except asyncio.CancelledError:
        return
    except Exception as e:
        await queue.put({"event": "error", "data": {"error": str(e)}})
    finally:
        unregister_run_push(run_id)
        RUNS[run_id].pop("_running_step", None)
        await queue.put(None)  # sentinel



async def _push_sdui_snapshot(run_id: str) -> None:
    """仅推送 SDUI + done（commission 直达等无图场景）。"""
    queue: asyncio.Queue = RUNS[run_id]["queue"]
    try:
        skill_id = RUNS[run_id]["state"].get("skill_id", "zhgk")
        _proj = _get_sdui_projector(skill_id)
        if _proj is not None:
            await queue.put({"event": "sdui", "data": _proj(RUNS[run_id]["state"])})
    except Exception:
        pass
    await queue.put({"event": "done", "data": {"run_id": run_id}})
    await queue.put(None)

@app.post("/agent/{skill}/start")
async def start_run(skill: str, req: StartReq):
    """启动一次工作流（skill 决定跑哪张图）。"""
    skill_obj = _get_skill_or_404(skill)
    run_id = f"run-{uuid.uuid4().hex[:10]}"
    project = skill_obj.initial_project(req.model_dump(exclude_none=True))

    if str(project.get("entry_mode") or "").strip() == "commission":
        builder = getattr(skill_obj, "build_commission_entry_state", None)
        if callable(builder):
            built = builder(run_id, project)
            if built.get("error"):
                raise HTTPException(400, str(built["error"]))
            queue: asyncio.Queue = asyncio.Queue()
            RUNS[run_id] = {"queue": queue, "state": built, "task": None}
            await _push_sdui_snapshot(run_id)
            return {"run_id": run_id, "status": "commission_ready", "mode": "commission_entry"}

    init_state: AgentState = {
        "run_id": run_id,
        "skill_id": skill,
        "project": project,
        "steps": [],
        "logs": [f"[start] run {run_id} · {skill} · {project.get('project_code', '')}"],
        "overall_progress": 0,
    }
    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(_run_graph_streaming(run_id, init_state))
    RUNS[run_id] = {"queue": queue, "state": init_state, "task": task}
    return {"run_id": run_id, "status": "started"}



@app.post("/agent/{skill}/reset-workspace")
async def reset_workspace_endpoint(skill: str):
    """重置 skill 工作区：清空 ProjectData 运行态与产物，保留 Input（重置会话时调用）。"""
    skill_obj = _get_skill_or_404(skill)
    handler = getattr(skill_obj, "file_handler", None)
    reset_fn = getattr(handler, "reset_workspace", None) if handler else None
    if not callable(reset_fn):
        raise HTTPException(404, f"skill {skill} 不支持工作区重置")
    summary = reset_fn(skill_obj.work_root)
    return summary

# ─── SSE 订阅 ───

async def _sse_generator(run_id: str) -> AsyncIterator[dict]:
    if run_id not in RUNS:
        yield {"event": "error", "data": json.dumps({"error": "run_id not found"})}
        return

    async def _send_snapshot() -> AsyncIterator[dict]:
        """快照辅助：发 snapshot + sdui，供首连和 resume 无缝切换时复用。"""
        yield {"event": "snapshot", "data": json.dumps(RUNS[run_id]["state"], ensure_ascii=False, default=str)}
        try:
            _skill_id = RUNS[run_id]["state"].get("skill_id", "zhgk")
            _proj = _get_sdui_projector(_skill_id)
            if _proj is not None:
                sdui_snap = _proj(RUNS[run_id]["state"])
                yield {"event": "sdui", "data": json.dumps(sdui_snap, ensure_ascii=False, default=str)}
        except Exception:
            pass

    # 先把当前 state + SDUI 快照发一份给客户端（避免错过早期 node_update）
    async for ev in _send_snapshot():
        yield ev

    # 捕获当前队列引用；resume 时会替换队列，通过对象比较感知切换
    current_queue: asyncio.Queue = RUNS[run_id]["queue"]

    # ── 快速完成的重连场景 ──────────────────────────────────────────────
    # 若 run 已结束（task.done()）且队列为空（None 哨兵已被首连消费），
    # 再调用 current_queue.get() 会永久阻塞。直接补发 close 即可。
    _task = RUNS[run_id].get("task")
    if _task is not None and _task.done() and current_queue.empty():
        yield {"event": "close", "data": json.dumps({"ok": True})}
        return

    while True:
        item = await current_queue.get()
        if item is None:
            # 旧任务已结束（CancelledError finally 放哨兵）——
            # 判断是 resume（队列已换新）还是真正终止
            new_queue = RUNS[run_id].get("queue")
            if new_queue is not None and new_queue is not current_queue:
                # Resume 场景：无缝切换到新队列，重发快照，前端不断开
                current_queue = new_queue
                async for ev in _send_snapshot():
                    yield ev
                continue
            # 正常结束：持续保持 SSE 连接 5 秒，让浏览器有足够时间处理
            # close 事件后再关闭，避免前端因网络抖动来不及消费就断连重试。
            await asyncio.sleep(5)
            break
        yield {
            "event": item["event"],
            "data": json.dumps(item["data"], ensure_ascii=False, default=str),
        }
    yield {"event": "close", "data": json.dumps({"ok": True})}


@app.get("/agent/{skill}/stream/{run_id}")
async def stream(skill: str, run_id: str):
    return EventSourceResponse(_sse_generator(run_id))


# ─── 通用会话（ReAct · 流式 + 工具）─── 所有页面 ClawRail 共用 ───

class ChatReq(BaseModel):
    message: str
    history: list = []          # 多轮历史（仅未给 conv_id 时生效，向后兼容）
    context: dict = {}          # 跨页面上下文：{"project": "K1903", "page": "cockpit"}
    conv_id: str = ""           # 会话 id（§3.5 多轮记忆；给定则走后端会话历史）


def _chat_system(context: dict) -> str:
    """把「当前项目/页面」注入 system，支持"对当前页面提问"。"""
    base = DEFAULT_SYSTEM
    bits = []
    if context.get("project"):
        bits.append(f"当前项目：{context['project']}")
    if context.get("page"):
        bits.append(f"当前页面：{context['page']}")
    if bits:
        base += "\n\n[上下文] " + " · ".join(bits) + "。用户说的「当前页面 / 这个」即指此。"
    return base


@app.post("/agent/chat/stream")
async def chat_stream_endpoint(req: ChatReq):
    """
    通用会话 SSE：异步流式 token + 工具调用事件。
    前端用 fetch + ReadableStream 读 SSE（POST 带 body）。

    skill-as-tool 检测到 launch_* 时自动启动 LangGraph，
    skill_launch 事件携带 run_id，前端直接订阅 /agent/<skill>/stream/<run_id>。
    """
    ctx = req.context or {}
    conv_id = (req.conv_id or "").strip()

    async def _skill_launch_cb(skill_id: str, project: dict) -> str:
        """chat 触发 skill-as-tool → 自动启动 LangGraph，返回 run_id。"""
        try:
            skill_obj = _get_skill_or_404(skill_id)
            _run_id = f"chat-{uuid.uuid4().hex[:10]}"
            full_project = skill_obj.initial_project(project)
            init_state: AgentState = {
                "run_id": _run_id,
                "skill_id": skill_id,
                "project": full_project,
                "steps": [],
                "logs": [f"[chat] 由会话引擎自动启动 · {project.get('project_code', '')}"],
                "overall_progress": 0,
            }
            RUNS[_run_id] = {"queue": asyncio.Queue(), "state": init_state, "task": None}
            task = asyncio.create_task(_run_graph_streaming(_run_id, init_state))
            RUNS[_run_id]["task"] = task
            return _run_id
        except Exception as e:  # noqa: BLE001
            return f"err-{e}"

    async def _events() -> AsyncIterator[dict]:
        output: asyncio.Queue = asyncio.Queue()
        flags = {"had_tools": False}  # 可变容器，避免 nonlocal 嵌套歧义

        async def _heartbeat() -> None:
            while True:
                await asyncio.sleep(25)
                await output.put({"event": "heartbeat", "data": json.dumps({"type": "heartbeat"})})

        async def _approval_cb(approval_id: str, tool_name: str, args: dict) -> bool:
            """挂起当前工具执行，等待前端 /approve-tool 响应（最长 5 分钟）。"""
            loop = asyncio.get_event_loop()
            future: asyncio.Future[bool] = loop.create_future()
            _PENDING_APPROVALS[approval_id] = future
            try:
                return await asyncio.wait_for(asyncio.shield(future), timeout=300.0)
            except asyncio.TimeoutError:
                return False
            finally:
                _PENDING_APPROVALS.pop(approval_id, None)

        async def _chat_task() -> None:
            try:
                async for ev in run_chat_async(
                    req.message,
                    history=req.history or None,
                    system=_chat_system(ctx),
                    trace_meta={"scope": "chat", "page": ctx.get("page", "")},
                    conv_id=conv_id or None,
                    skill_launch_cb=_skill_launch_cb,
                    approval_cb=_approval_cb,
                ):
                    if ev.get("type") == "tool_call":
                        flags["had_tools"] = True
                    await output.put({"event": ev["type"], "data": json.dumps(ev, ensure_ascii=False, default=str)})
            except Exception as e:  # noqa: BLE001
                await output.put({"event": "error", "data": json.dumps({"type": "error", "message": str(e)})})
            finally:
                await output.put(None)  # sentinel

        hb_task = asyncio.create_task(_heartbeat())
        asyncio.create_task(_chat_task())
        try:
            while True:
                item = await output.get()
                if item is None:
                    break
                yield item
        finally:
            hb_task.cancel()

        if flags["had_tools"] and conv_id:
            asyncio.create_task(_trigger_eval_background(conv_id=conv_id))

    return EventSourceResponse(_events())


# ─── 工具审批（HITL · 敏感工具执行前等待用户确认）───

class ApproveToolReq(BaseModel):
    approval_id: str
    approved: bool


@app.post("/agent/chat/approve-tool")
async def approve_tool(req: ApproveToolReq):
    """前端审批卡片点"批准"或"拒绝"后调此接口，解锁挂起的工具调用。"""
    future = _PENDING_APPROVALS.get(req.approval_id)
    if future is None or future.done():
        raise HTTPException(404, "approval_id 不存在或已超时")
    future.set_result(req.approved)
    return {"ok": True, "approved": req.approved}


# ─── HITL 续跑 ───

async def _run_single_step_streaming(run_id: str, step_key: str, *, _chain: bool = True, chain_linear: bool = False) -> None:
    """仅重试单个 step（用于 report_distribute 等：前置产物已在磁盘）。"""
    from .skills.base import SkillContext

    queue: asyncio.Queue = RUNS[run_id]["queue"]
    skill_id = RUNS[run_id]["state"].get("skill_id", "zhgk")
    skill = _get_skill_or_404(skill_id)
    step = next((s for s in skill.steps if s.key == step_key), None)
    if step is None:
        await queue.put({"event": "error", "data": {"error": f"unknown step: {step_key}"}})
        await queue.put(None)
        return

    state: AgentState = dict(RUNS[run_id]["state"])
    state["hitl"] = {}
    state["error"] = ""
    ctx = SkillContext(
        skill_id=skill.name,
        work_root=skill.work_root,
        run_id=run_id,
        project=state.get("project") or {},
        llm_factory=skill.llm_factory,
        # step_retry 路径在主线程同步执行，emit_push 无法做中途 yield；
        # 但 step_started 信号在 execute_step 进入前手动推（见下方）。
        emit_push=None,
    )
    # 在 execute_step 阻塞之前先推一次 running SDUI，让 Stepper 变蓝
    try:
        RUNS[run_id]["_running_step"] = {"key": step_key, "name": step.name, "log_tail": []}
        _proj_pre = _get_sdui_projector(skill_id)
        if _proj_pre is not None:
            cur_pre = RUNS[run_id]["state"]
            existing_pre = cur_pre.get("steps") or []
            if not any(s.get("key") == step_key for s in existing_pre):
                patched_pre = {
                    **cur_pre,
                    "steps": existing_pre + [{
                        "key": step_key, "name": step.name,
                        "status": "running", "log_tail": [],
                    }],
                }
            else:
                patched_pre = cur_pre
            await queue.put({"event": "sdui", "data": _proj_pre(patched_pre)})
    except Exception:
        pass

    try:
        diff = skill.execute_step(step, state, ctx)
        RUNS[run_id]["_running_step"] = None  # 执行完毕，清除 running 标记
        cur = RUNS[run_id]["state"]
        for k, v in diff.items():
            if k in ("logs", "steps") and isinstance(v, list):
                cur.setdefault(k, []).extend(v)
            else:
                cur[k] = v
        await queue.put({
            "event": "node_update",
            "data": {"node": step_key, "diff": diff},
        })
        # SDUI 投影：step_retry 后也推一棵完整 UI 树（与 _run_graph_streaming 对齐）；
        # 前端 useSduiStream 只订 sdui 事件，缺这步则重试成功后界面停在旧态不刷新。
        try:
            _proj = _get_sdui_projector(skill_id)
            if _proj is not None:
                await queue.put({"event": "sdui", "data": _proj(RUNS[run_id]["state"])})
        except Exception:
            pass
        hitl = (diff.get("hitl") or {}) if isinstance(diff.get("hitl"), dict) else {}
        if not hitl.get("step") and not diff.get("error"):
            asyncio.create_task(_trigger_eval_background(run_id=run_id, skill_id=skill_id))
        await queue.put({"event": "done", "data": {"run_id": run_id}})
    except Exception as e:
        RUNS[run_id]["_running_step"] = None
        await queue.put({"event": "error", "data": {"error": str(e)}})
    finally:
        await queue.put(None)


@app.post("/agent/{skill}/resume")
async def resume_run(skill: str, req: ResumeReq):
    if req.run_id not in RUNS:
        raise HTTPException(404, "run_id not found")
    prev = RUNS[req.run_id]["state"]
    skill_id = prev.get("skill_id", skill)
    skill_obj = _get_skill_or_404(skill_id)
    hitl_step = _resolve_hitl_step(prev, req.from_step, skill_obj)
    target_step = (req.from_step or "").strip() or hitl_step
    dispatch_keys = list(getattr(skill_obj, "dispatch_step_keys", []) or [])
    retry_keys = set(skill_obj.step_retry_keys or []) | set(dispatch_keys)

    old_task = RUNS[req.run_id].get("task")
    if old_task and not old_task.done():
        old_task.cancel()
    RUNS[req.run_id]["queue"] = asyncio.Queue()

    if target_step and target_step in retry_keys:
        project = skill_obj.apply_resume_payload(
            prev.get("project", {}) or {}, req.payload or {}, target_step
        )
        RUNS[req.run_id]["state"] = {**prev, "project": project}
        if target_step in dispatch_keys and not hitl_step:
            RUNS[req.run_id]["state"]["hitl"] = {}
            RUNS[req.run_id]["state"]["error"] = ""
        RUNS[req.run_id]["attempt"] = RUNS[req.run_id].get("attempt", 0) + 1
        payload = req.payload or {}
        linear_keys = _linear_step_keys(skill_obj)
        chain_linear = (
            target_step in linear_keys
            and target_step not in dispatch_keys
            and payload.get("choice") == "confirm"
            and not payload.get("rerun")
        )
        task = asyncio.create_task(
            _run_single_step_streaming(req.run_id, target_step, chain_linear=chain_linear)
        )
        RUNS[req.run_id]["task"] = task
        mode = "dispatch" if target_step in dispatch_keys else "step_retry"
        msg = f"仅执行「{target_step}」，不会重跑前序步骤。"
        if chain_linear:
            msg = f"从「{target_step}」起沿主线自动推进，遇确认点或缺料时暂停。"
        return {
            "run_id": req.run_id,
            "status": "resumed",
            "mode": mode,
            "from_step": target_step,
            "chain_linear": chain_linear,
            "message": msg,
        }

    project = skill_obj.apply_resume_payload(
        prev.get("project", {}) or {}, req.payload or {}, hitl_step
    )
    RUNS[req.run_id]["state"] = {**prev, "project": project}
    RUNS[req.run_id]["attempt"] = RUNS[req.run_id].get("attempt", 0) + 1
    attempt = RUNS[req.run_id]["attempt"]
    init_state: AgentState = {
        "run_id": req.run_id,
        "skill_id": prev.get("skill_id", "zhgk"),
        "project": project,
        "steps": [],
        "logs": [f"[resume] 补齐文件后全量重跑（attempt {attempt}）"],
        "overall_progress": 0,
    }
    RUNS[req.run_id]["state"] = init_state
    new_tid = f"{req.run_id}-r{attempt}"
    task = asyncio.create_task(_run_graph_streaming(req.run_id, init_state, thread_id=new_tid))
    RUNS[req.run_id]["task"] = task
    return {
        "run_id": req.run_id,
        "status": "resumed",
        "thread_id": new_tid,
        "mode": "full_restart",
        "from_step": None,
        "message": "将从环境预检重新执行全流程（含场景筛选、勘测汇总、评估报告等）。",
    }


# ─── 文件上传 / HITL 齐备检查 ───

def _get_file_handler_or_501(skill_id: str):
    """取 skill 的文件补齐处理器；未配置 → 501。返回 (skill, handler)。"""
    skill = _get_skill_or_404(skill_id)
    fh = skill.file_handler
    if fh is None:
        raise HTTPException(status_code=501, detail=f"skill '{skill_id}' 未配置文件补齐 HITL")
    return skill, fh


@app.get("/agent/{skill}/files/check")
def files_check(skill: str, need: list[str] = Query(default=[])):
    """扫描文件齐备情况。传 need= 多次为当前 HITL 缺失项；否则查该 skill 的默认前置集。"""
    skill_obj, fh = _get_file_handler_or_501(skill)
    root = skill_obj.work_root
    if need:
        return fh.check_need_files(root, need)
    return fh.check_project_files(root)


@app.post("/agent/{skill}/upload")
async def upload(
    skill: str,
    kind: str = Form(..., description="上传类型，由各 skill 的 file_handler.infer_upload_kind 定义"),
    file: UploadFile = File(...),
):
    """上传单个文件到该 skill 工作区"""
    skill_obj, fh = _get_file_handler_or_501(skill)
    return await fh.save_upload(skill_obj.work_root, kind, file)


@app.post("/agent/{skill}/upload/batch")
async def upload_batch(
    skill: str,
    files: list[UploadFile] = File(..., description="多文件，按文件名自动路由目录"),
    need: list[str] = Form(default=[], description="当前 HITL need_files，用于返回对齐的齐备检查"),
):
    """批量上传；不自动续跑。传 need 时 check 按 HITL 缺失项，否则查该 skill 默认前置集。"""
    skill_obj, fh = _get_file_handler_or_501(skill)
    if not files:
        raise HTTPException(400, "未选择文件")
    root = skill_obj.work_root
    results: list[dict] = []
    for f in files:
        kind = fh.infer_upload_kind(f.filename or "")
        try:
            results.append(await fh.save_upload(root, kind, f))
        except Exception as e:  # noqa: BLE001
            results.append({"ok": False, "filename": f.filename, "error": str(e)})
    check = fh.check_need_files(root, need) if need else fh.check_project_files(root)
    return {"uploaded": results, "check": check}


# ─── Preview 页面 · BOQ 上传 ───

ASSETS_ROOT = Path(__file__).resolve().parent / "assets"
PREVIEW_BOQ_DIR = ASSETS_ROOT / "boq"
PREVIEW_BOQ_MAP = ASSETS_ROOT / "boq-map.json"
PREVIEW_CONTRACT_MAP = ASSETS_ROOT / "contract-map.json"
ALLOWED_PREVIEW_BOQ_EXTS = {".xlsx", ".xls", ".csv"}


def _safe_upload_filename(raw_name: str | None, fallback: str) -> str:
    """清洗上传文件名，确保只落到 assets 子目录内。"""
    basename = Path(raw_name or fallback).name
    cleaned = re.sub(r"[^0-9A-Za-z.\-_()\u4e00-\u9fff]+", "_", basename).strip("._")
    return cleaned or fallback


def _unique_asset_path(dest_dir: Path, filename: str) -> Path:
    candidate = dest_dir / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    return dest_dir / f"{stem}-{uuid.uuid4().hex[:8]}{suffix}"


def _read_preview_boq_map() -> dict[str, list[dict[str, Any]]]:
    if not PREVIEW_BOQ_MAP.is_file():
        return {}
    try:
        data = json.loads(PREVIEW_BOQ_MAP.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for key, value in data.items():
        if isinstance(key, str) and isinstance(value, list):
            out[key] = [item for item in value if isinstance(item, dict)]
    return out


def _read_preview_contract_map() -> dict[str, list[dict[str, Any]]]:
    if not PREVIEW_CONTRACT_MAP.is_file():
        return {}
    try:
        data = json.loads(PREVIEW_CONTRACT_MAP.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for key, value in data.items():
        if isinstance(key, str) and isinstance(value, list):
            out[key] = [item for item in value if isinstance(item, dict)]
    return out


def _write_preview_boq_map(data: dict[str, list[dict[str, Any]]]) -> None:
    PREVIEW_BOQ_MAP.parent.mkdir(parents=True, exist_ok=True)
    PREVIEW_BOQ_MAP.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _preview_boq_asset_path(path: str) -> Path:
    """Resolve a preview BOQ asset path recorded relative to agent/assets/boq/."""
    raw = (path or "").strip().replace("\\", "/")
    if not raw:
        raise HTTPException(status_code=400, detail="path 不能为空")
    full = (ASSETS_ROOT / raw).resolve()
    try:
        full.relative_to(PREVIEW_BOQ_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="path outside preview BOQ assets")
    if not full.exists() or not full.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return full


async def _save_preview_boq_file(file: UploadFile) -> dict[str, Any]:
    filename = _safe_upload_filename(file.filename, "uploaded_BOQ.xlsx")
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_PREVIEW_BOQ_EXTS:
        raise HTTPException(status_code=400, detail=f"{filename} 不是支持的 BOQ 格式（仅支持 .xlsx / .xls / .csv）")

    PREVIEW_BOQ_DIR.mkdir(parents=True, exist_ok=True)
    dest = _unique_asset_path(PREVIEW_BOQ_DIR, filename)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail=f"{filename} 为空文件")
    dest.write_bytes(content)
    return {
        "filename": dest.name,
        "path": dest.relative_to(ASSETS_ROOT).as_posix(),
        "size": len(content),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/agent/preview/boq/upload", response_model=PreviewBoqUploadResp)
async def upload_preview_boq(
    request: Request,
    proposal_id: str = Form(..., description="项目 Proposal ID"),
):
    """Preview 页面上传 BOQ，保存到 agent/assets/boq/。支持 files 多文件，兼容 file 单文件。"""
    normalized_proposal_id = proposal_id.strip()
    if not normalized_proposal_id:
        raise HTTPException(status_code=400, detail="proposal_id 不能为空")

    form = await request.form()
    upload_items = [item for item in [*form.getlist("files"), *form.getlist("file")] if hasattr(item, "filename")]
    if not upload_items:
        raise HTTPException(status_code=400, detail="未选择 BOQ 文件")

    uploaded = [await _save_preview_boq_file(file) for file in upload_items]
    boq_map = _read_preview_boq_map()
    files = boq_map.setdefault(normalized_proposal_id, [])
    files.extend(uploaded)
    _write_preview_boq_map(boq_map)
    first = uploaded[0]
    return {
        "ok": True,
        "proposal_id": normalized_proposal_id,
        "filename": first["filename"],
        "path": first["path"],
        "size": first["size"],
        "uploaded": uploaded,
        "boq_files": files,
    }


@app.get("/agent/preview/contracts", response_model=PreviewContractListResp)
async def list_preview_contracts(proposal_id: str = Query(..., description="项目 Proposal ID")):
    """按 Proposal ID 查询 Preview 页面合同列表（读取 agent/assets/contract-map.json）。"""
    normalized_proposal_id = proposal_id.strip()
    if not normalized_proposal_id:
        raise HTTPException(status_code=400, detail="proposal_id 不能为空")

    contract_map = _read_preview_contract_map()
    return {
        "ok": True,
        "proposal_id": normalized_proposal_id,
        "contracts": contract_map.get(normalized_proposal_id, []),
    }


@app.get("/agent/preview/boq", response_model=PreviewBoqListResp)
async def list_preview_boq(proposal_id: str = Query(..., description="项目 Proposal ID")):
    """按 Proposal ID 查询 Preview 页面已上传 BOQ 列表。"""
    normalized_proposal_id = proposal_id.strip()
    if not normalized_proposal_id:
        raise HTTPException(status_code=400, detail="proposal_id 不能为空")

    boq_map = _read_preview_boq_map()
    return {
        "ok": True,
        "proposal_id": normalized_proposal_id,
        "boq_files": boq_map.get(normalized_proposal_id, []),
    }


@app.get("/agent/preview/boq/file")
async def preview_boq_file(path: str = Query(..., description="agent/assets/boq 下的 BOQ 相对路径")):
    """Preview 页面 BOQ 文件预览/下载流，仅允许读取已上传 BOQ 目录。"""
    full = _preview_boq_asset_path(path)
    return FileResponse(str(full), filename=full.name)


# ─── 状态快照 ───

@app.get("/agent/{skill}/status/{run_id}")
def status(skill: str, run_id: str):
    if run_id not in RUNS:
        raise HTTPException(404, "run_id not found")
    return RUNS[run_id]["state"]


# ─── 产物下载 ───

@app.get("/agent/{skill}/artifact")
def artifact(skill: str, path: str = Query(..., description="相对 skill 工作区根目录的产物路径")):
    """安全下载产物 · 只允许 ProjectData/ 子树下"""
    skill_obj = _get_skill_or_404(skill)
    root = skill_obj.work_root
    full = (root / path).resolve()
    try:
        full.relative_to((root / "ProjectData").resolve())
    except ValueError:
        raise HTTPException(403, "path outside ProjectData")
    if not full.exists() or not full.is_file():
        raise HTTPException(404, "not found")
    return FileResponse(str(full), filename=full.name)


# ─── 评测看板 ───

def _skill_eval_summary(runs: list[dict]) -> dict:
    if not runs:
        return {}
    quality_scores = [r["quality_score"] for r in runs if r.get("quality_score") is not None]
    success_count = sum(1 for r in runs if r.get("success"))
    latencies = [r["latency_ms"] for r in runs if r.get("latency_ms")]
    return {
        "quality_avg": round(sum(quality_scores) / len(quality_scores), 3) if quality_scores else None,
        "success_rate": round(success_count / len(runs), 3),
        "success_count": success_count,
        "total": len(runs),
        "latest_quality": runs[0].get("quality_score"),
        "latest_success": runs[0].get("success"),
        "latest_cost_cny": runs[0].get("cost_cny"),
        "latest_latency_ms": runs[0].get("latency_ms"),
        "latency_p50": sorted(latencies)[len(latencies) // 2] if latencies else None,
    }


@app.get("/agent/evals/report")
def evals_report(
    skill: str = Query("zhgk"),
    limit: int = Query(30),
    mode: str = Query("overview"),
):
    """
    读 evals/results/{skill}-*.json。
    mode=latest：仅最近一次 run 详情；mode=overview：历次汇总 + 趋势数据。
    """
    runs = _load_eval_runs(skill, limit)
    if not runs:
        empty = {"skill": skill, "total": 0, "summary": {}, "runs": [], "mode": mode}
        if mode == "latest":
            empty["run"] = None
        return empty

    summary = _skill_eval_summary(runs)
    if mode == "latest":
        return {
            "skill": skill,
            "mode": "latest",
            "total": len(runs),
            "run": runs[0],
            "summary": summary,
            "summary_latest": {
                "quality_score": runs[0].get("quality_score"),
                "success": runs[0].get("success"),
                "cost_cny": runs[0].get("cost_cny"),
                "latency_ms": runs[0].get("latency_ms"),
                "run_id": runs[0].get("run_id"),
                "trace_id": runs[0].get("trace_id"),
                "metrics_source": runs[0].get("metrics_source"),
            },
        }
    return {"skill": skill, "mode": "overview", "total": len(runs), "summary": summary, "runs": runs}


def _evals_results_dir() -> Path:
    return Path(__file__).parent / "evals" / "results"


def _agent_python() -> str:
    """agent/.venv python（与 scripts/agent-python.mjs 同逻辑）。"""
    root = Path(__file__).parent
    for rel in (".venv/Scripts/python.exe", ".venv/bin/python"):
        p = root / rel
        if p.exists():
            return str(p)
    return "python"


def _load_eval_runs(prefix: str, limit: int = 30) -> list[dict]:
    files = sorted(_evals_results_dir().glob(f"{prefix}-*.json"), reverse=True)[:limit]
    runs: list[dict] = []
    for f in files:
        try:
            runs.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return runs


def _tools_report_payload(latest: dict, file_count: int) -> dict:
    from .evals.deviations import tool_metric_row

    raw = latest.get("tools") or {}
    tools = [tool_metric_row(name, m) for name, m in raw.items()]
    overall = latest.get("overall") or {}
    flagged = sum(1 for t in tools if t["self_correct_rate"] > 0.15)
    return {
        "total": file_count,
        "evaluated_at": latest.get("evaluated_at"),
        "source": latest.get("source", "live"),
        "conv_id": latest.get("conv_id", ""),
        "run_id": latest.get("run_id", ""),
        "window": latest.get("window", ""),
        "record_count": latest.get("record_count", len(latest.get("records") or [])),
        "summary": {
            "tool_count": overall.get("tool_count", len(tools)),
            "calls": overall.get("calls", 0),
            "self_correction_rate_avg": overall.get("self_correction_rate"),
            "flagged_count": flagged,
            "quality_score": latest.get("quality_score"),
            "success": latest.get("success"),
        },
        "tools": tools,
        "records": latest.get("records") or [],
        "checks": latest.get("checks") or [],
    }


@app.get("/agent/evals/tools/report")
def evals_tools_report(limit: int = Query(10), mode: str = Query("overview")):
    """读 evals/results/tools-*.json。mode=latest 含调用明细 records。"""
    files = sorted(_evals_results_dir().glob("tools-*.json"), reverse=True)
    latest = None
    for f in files[: max(limit, 1)]:
        try:
            latest = json.loads(f.read_text(encoding="utf-8"))
            break
        except Exception:
            pass

    if not latest:
        empty = {"mode": mode, "total": 0, "summary": {}, "tools": [], "source": "empty"}
        if mode == "latest":
            empty["records"] = []
            empty["checks"] = []
        return empty

    payload = _tools_report_payload(latest, len(files))
    payload["mode"] = mode

    if mode == "latest":
        return payload

    history = []
    for f in files[:limit]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            history.append({
                "evaluated_at": data.get("evaluated_at"),
                "source": data.get("source"),
                "quality_score": data.get("quality_score"),
                "success": data.get("success"),
                "calls": (data.get("overall") or {}).get("calls"),
                "conv_id": data.get("conv_id", ""),
                "run_id": data.get("run_id", ""),
            })
        except Exception:
            pass
    payload["history"] = history
    payload.pop("records", None)
    payload.pop("checks", None)
    return payload


@app.get("/agent/evals/deviations/skill")
def evals_deviations_skill(skill: str = Query("zhgk"), limit: int = Query(30)):
    """SKILL 偏离 JSON（METRICS §7 · 喂 Cursor）。"""
    from .evals.deviations import build_skill_deviations

    runs = _load_eval_runs(skill, limit)
    return build_skill_deviations(runs)


@app.get("/agent/evals/deviations/tools")
def evals_deviations_tools(threshold: float = Query(0.15)):
    """工具偏离 JSON（自纠率超阈值）。"""
    from .evals.deviations import build_tool_deviations

    files = sorted(_evals_results_dir().glob("tools-*.json"), reverse=True)
    if not files:
        return {"prompt": "", "threshold": threshold, "flagged": [], "note": "无 tools 评测结果"}
    try:
        latest = json.loads(files[0].read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(500, str(e)) from e
    return build_tool_deviations(latest.get("tools") or {}, threshold=threshold)


def _eval_subprocess_run(
    script: str,
    extra: list[str] | None = None,
    *,
    fixture: bool = False,
) -> dict:
    import subprocess

    py = _agent_python()
    project = Path(__file__).resolve().parents[1]
    evals = Path(__file__).parent / "evals"
    cmd = [py, str(evals / script)] + (extra or [])
    if fixture:
        cmd.append("--fixture")
    proc = subprocess.run(
        cmd,
        cwd=str(project),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-800:],
        "stderr_tail": (proc.stderr or "")[-400:],
    }


def _excel_date(value) -> str:
    if not value:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10]


def _delivery_plan_snapshot(project_id: str) -> dict:
    from openpyxl import load_workbook

    if not DELIVERY_PLAN_PATH.is_file():
        raise HTTPException(status_code=404, detail="delivery plan workbook not found")

    sheet = load_workbook(DELIVERY_PLAN_PATH, data_only=True, read_only=True).active
    rows = list(sheet.iter_rows(values_only=True))
    headers = {name: index for index, name in enumerate(rows[0])}
    records = [{name: row[index] for name, index in headers.items()} for row in rows[1:]]
    pods = sorted({
        unit.strip()
        for record in records
        for unit in str(record.get("MANAGEMENT_UNIT") or "").split(",")
        if unit.strip().upper().endswith(tuple(f"POD{i:02d}" for i in range(1, 100)))
    })
    matchers = {
        "roomReady": lambda name: "机房改造实施" in name,
        "arrival": lambda name: "设备到货静置" in name or "设备静置" in name,
        "cabling": lambda name: "综合布线与成端" in name,
        "powerOn": lambda name: "设备上电" in name,
        "online": lambda name: "集群性能调优" in name,
        "handover": lambda name: name == "移交",
    }
    pod_items = []
    for pod in pods:
        stages = {}
        for key, matcher in matchers.items():
            candidates = []
            for record in records:
                if not matcher(str(record.get("ACTIVITY_NAME") or "").strip()):
                    continue
                units = [unit.strip() for unit in str(record.get("MANAGEMENT_UNIT") or "").split(",") if unit.strip()]
                if not units or pod in units:
                    candidates.append(record)
            if not candidates:
                continue
            completed = all(
                "已完成" in str(record.get("STATUS") or "")
                or float(str(record.get("PROCESS") or "0").replace("%", "") or 0) >= 100
                for record in candidates
            )
            expected_ends = sorted(filter(None, (_excel_date(record.get("END_DATE")) for record in candidates)))
            actual_ends = sorted(filter(None, (_excel_date(record.get("ACTUAL_END_DATE")) for record in candidates)))
            progress = min(
                100 if "已完成" in str(record.get("STATUS") or "") else
                max(0, min(99, float(str(record.get("PROCESS") or "0").replace("%", "") or 0)))
                for record in candidates
            )
            stages[key] = {
                "expectedEnd": expected_ends[-1] if expected_ends else "",
                "actualEnd": actual_ends[-1] if completed and actual_ends else "",
                "progress": progress,
                "owner": next((str(record.get("PRINCIPAL")) for record in candidates if record.get("PRINCIPAL")), ""),
                "common": any(not str(record.get("MANAGEMENT_UNIT") or "").strip() for record in candidates),
            }
        if all(key in stages and stages[key]["expectedEnd"] for key in matchers):
            pod_items.append({"pod": pod, "batch": pod.split("-")[0], "stages": stages})
    return {"projectId": project_id, "sourceLabel": "data/delivery/delivery-plan.xlsx", "pods": pod_items}


@app.get("/api/v1/projects/{project_id}/delivery-plan/milestones")
def get_delivery_plan_milestones(project_id: str):
    return JSONResponse(
        content=_delivery_plan_snapshot(project_id),
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/v1/projects/{project_id}/delivery-plan.xlsx")
def get_delivery_plan_excel(project_id: str):
    """Return the project-local delivery plan workbook used by the dashboard."""
    if not DELIVERY_PLAN_PATH.is_file():
        raise HTTPException(status_code=404, detail="delivery plan workbook not found")
    return FileResponse(
        DELIVERY_PLAN_PATH,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="delivery-plan.xlsx",
        headers={"Cache-Control": "no-store"},
    )


async def _trigger_eval_background(*, run_id: str = "", conv_id: str = "", skill_id: str = "zhgk") -> None:
    """skill run 完成 / 会话工具结束后后台跑评测（不阻塞 SSE）。
    当前评测脚本（eval_zhgk.py）仅对 zhgk；其他 skill 暂跳过自动评测，
    待各自 eval_<skill>.py 落地后再放开（见 evals/eval_skill.template.py）。"""
    if skill_id != "zhgk":
        return
    try:
        await asyncio.to_thread(
            _run_evals_bundle,
            live=True,
            fixture=False,
            run_id=run_id,
            conv_id=conv_id,
        )
    except Exception:
        pass


def _run_evals_bundle(
    *,
    live: bool = True,
    fixture: bool = False,
    run_id: str = "",
    conv_id: str = "",
) -> dict:
    """跑评测脚本组合。仅 conv_id 时只跑 tools；有 run_id 时 zhgk 带 --run-id。"""
    tools_extra: list[str] = []
    if live and not fixture:
        tools_extra = ["--days", "7"]
    if conv_id:
        tools_extra.extend(["--conv-id", conv_id])
    if run_id:
        tools_extra.extend(["--run-id", run_id])

    out: dict = {"live": live, "fixture": fixture, "run_id": run_id or None, "conv_id": conv_id or None}

    run_zhgk = not conv_id or bool(run_id)
    if run_zhgk:
        zhgk_extra: list[str] = []
        if run_id:
            zhgk_extra.extend(["--run-id", run_id])
        out["zhgk"] = _eval_subprocess_run("eval_zhgk.py", zhgk_extra or None, fixture=fixture)
    else:
        out["zhgk"] = {"ok": True, "skipped": True, "reason": "conv_id only"}

    out["tools"] = _eval_subprocess_run("eval_tools.py", tools_extra or None, fixture=fixture)
    if not fixture:
        out["export"] = _eval_subprocess_run("export_deviations.py", fixture=fixture)
    return out


async def _trigger_eval_background(*, run_id: str = "", conv_id: str = "", skill_id: str = "zhgk") -> None:
    """skill run 完成 / 会话工具结束后后台跑评测（不阻塞 SSE）。
    当前评测脚本（eval_zhgk.py）仅对 zhgk；其他 skill 暂跳过自动评测，
    待各自 eval_<skill>.py 落地后再放开（见 evals/eval_skill.template.py）。"""
    if skill_id != "zhgk":
        return
    try:
        await asyncio.to_thread(
            _run_evals_bundle,
            live=True,
            fixture=False,
            run_id=run_id,
            conv_id=conv_id,
        )
    except Exception:
        pass


@app.post("/agent/evals/refresh")
async def evals_refresh(
    live: bool = Query(True),
    fixture: bool = Query(False),
    run_id: str = Query(""),
    conv_id: str = Query(""),
):
    """
    一键跑评测脚本并写 results/。
    run_id：对齐 zhgk trace + skill 侧工具 span；conv_id：对齐会话工具 span。
    """
    return _run_evals_bundle(
        live=live,
        fixture=fixture,
        run_id=run_id.strip(),
        conv_id=conv_id.strip(),
    )


# ─── SDUI 快照（前端首屏或断线重连时拉取完整 UI 树） ───

@app.get("/agent/{skill}/ui/{run_id}")
def get_ui_snapshot(skill: str, run_id: str):
    """返回指定 run 的当前 SDUI 文档（JSON）。前端断线重连或初始化时调用。"""
    if run_id not in RUNS:
        raise HTTPException(404, "run_id not found")
    entry = RUNS[run_id]
    task = entry.get("task")
    if entry.get("display_state") and task is not None and not task.done():
        state = entry["display_state"]
    else:
        state = entry["state"]
    skill_id = state.get("skill_id", skill)
    proj_fn = _get_sdui_projector(skill_id)
    if proj_fn is None:
        raise HTTPException(501, f"skill '{skill_id}' has no SDUI projector")
    try:
        return JSONResponse(_sdui_json_safe(proj_fn(state)))
    except Exception as e:
        import sys, traceback
        traceback.print_exc(file=sys.stderr)
        sys.stderr.write(f"[sdui] get_ui_snapshot failed for {run_id}: {e}\n")
        raise


# ─── 列出所有 run（调试用） ───

@app.get("/agent/{skill}/runs")
def list_runs(skill: str):
    return [
        {
            "run_id": k,
            "current_step": v["state"].get("current_step"),
            "overall_progress": v["state"].get("overall_progress", 0),
        }
        for k, v in RUNS.items()
    ]
