"""
BaseSkill / BaseStep · 通用 Skill 抽象层（A+B 架构里的 B）

设计原则：
1. **每个 Step 是 LangGraph 一个节点**，输入 state、返回 state diff
2. **LLM 调用走统一客户端**（langchain_openai → 自动被 Langfuse 捕获）
3. **数据落盘走 SkillContext**（隔离原 nanobot path_config，便于本地测试）
4. **前置检查独立函数**（让 graph 决定 HITL 中断）
5. **每个 Skill 自描述**（name / description / steps），用于 Claude Code Skill 表层调用

继承样例（伪代码）：
    class MyStep(BaseStep):
        key = "evaluate"
        name = "评估满足度"
        artifacts = ["机房满足度评估表.xlsx"]
        def check_inputs(self, ctx): ...
        def run(self, ctx, state, emit): ...
        # 用 ctx.llm 直接 invoke

    class MySkill(BaseSkill):
        name = "zhgk"
        description = "智慧工勘 ..."
        steps = [PreflightStep(), SceneFilterStep(), ...]
"""
from __future__ import annotations
import abc
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, ClassVar, Iterable, Literal, TypedDict, Annotated
from operator import add


# ─── 线程安全的 run-level 推送注册表 ────────────────────────────────────────────
# main.py 在 run 启动时注册一个 thread-safe push 回调；
# BaseSkill.make_node 在线程池中执行 _node(state) 时按 run_id 取出回调，
# 注入到 SkillContext.emit_push，供 execute_step 在 step 执行期间实时推送事件。

_RUN_PUSH_FNS: dict[str, "Callable[[dict], None]"] = {}


def register_run_push(run_id: str, fn: "Callable[[dict], None]") -> None:
    """注册 run 的推送回调（由 main.py 在 _run_graph_streaming 启动时调用）。"""
    _RUN_PUSH_FNS[run_id] = fn


def unregister_run_push(run_id: str) -> None:
    """注销推送回调（run 结束后清理）。"""
    _RUN_PUSH_FNS.pop(run_id, None)


def _get_run_push(run_id: str) -> "Callable[[dict], None] | None":
    return _RUN_PUSH_FNS.get(run_id)


# ─── 通用 ───

StepStatus = Literal["pending", "running", "completed", "failed", "hitl"]


def default_checkpoint_db() -> str:
    """LangGraph checkpoint sqlite 默认路径（agent/runtime/checkpoints.db）。
    可用 AIDA_CHECKPOINT_DB 覆盖。"""
    return os.environ.get(
        "AIDA_CHECKPOINT_DB",
        str(Path(__file__).resolve().parents[1] / "runtime" / "checkpoints.db"),
    )


class NeedInputOption(TypedDict, total=False):
    """确认型 HITL 的单个选项（投影成 ChoiceCard 的一项）。

    - label 必填：展示文案。
    - value 必填：用户选定后由 resume 请求以 {"choice": value} 回传，
      apply_resume_payload 据此判定 confirm / redo（见 GuihuaSkill）。
    - id / description 可选。
    ⚠️ 选项统一用 dict（不要用裸 str）；投影器一律经
    agent.sdui.builder.choice_options() 转 SduiChoiceOption。"""
    label: str
    value: str
    id: str
    description: str


class NeedInput(TypedDict, total=False):
    """确认型 HITL 的一个待确认项（投影成一张 ChoiceCard）。

    id 标识该确认门、label 是卡片标题、options 是可选项列表。
    check_inputs 返回 {"ok": False, "missing": [], "need_inputs": [NeedInput, ...]}
    即触发确认型软中断（区别于 missing 非空的文件型）。"""
    id: str
    label: str
    options: list[NeedInputOption]


class CheckResult(TypedDict, total=False):
    """前置检查结果。
    - missing 非空 → 文件型 HITL（need_files → FilePicker）
    - need_inputs 非空 → 确认型 HITL（need_inputs → ChoiceCard/HitlTextInput）
    两者可独立使用：确认门返回 missing=[] + need_inputs=[{...}]。"""
    ok: bool
    missing: list[str]
    found: list[str]
    note: str  # 简短说明
    need_inputs: list[NeedInput]  # 确认型 HITL 的输入项（ChoiceCard 规格）
    need_edit: dict  # 在线编辑型 HITL 规格（→ build_editable_table → 可编辑 DataTable）


class StepRecord(TypedDict, total=False):
    """单步执行记录（state.steps 的一项）"""
    key: str
    name: str
    status: StepStatus
    started_at: str
    ended_at: str
    progress: int
    artifacts: list[str]
    log_tail: list[str]
    error: str
    metrics: dict[str, Any]   # 自由字段：LLM token / 行数 / 满足率 等


class HitlRequest(TypedDict, total=False):
    """人在回路请求"""
    step: str
    reason: str
    need_files: list[str]
    need_inputs: list[NeedInput]


class StepResult(TypedDict, total=False):
    """Step.run 的返回 · 也是 LangGraph state diff"""
    steps: list[StepRecord]      # 用 reducer add
    logs: list[str]
    artifacts: list[str]
    current_step: str
    overall_progress: int
    hitl: HitlRequest
    error: str
    # 可选业务字段
    metrics: dict[str, Any]


class SkillState(TypedDict, total=False):
    """LangGraph state · 所有 Skill 共用"""
    run_id: str
    skill_id: str
    started_at: str
    project: dict[str, Any]

    steps: Annotated[list[StepRecord], add]
    logs: Annotated[list[str], add]

    current_step: str
    overall_progress: int

    files: dict[str, Any]
    hitl: HitlRequest
    hitl_resume: dict

    metrics: dict[str, Any]
    error: str


# ─── SkillContext · 业务无关的运行时上下文 ───

class SkillContext:
    """
    运行时上下文：路径 + LLM 客户端 + 当前 run 元信息。
    每个 Step.run() 拿到的 ctx 都包含完整运行环境。
    """

    def __init__(
        self,
        skill_id: str,
        work_root: Path,
        run_id: str,
        project: dict[str, Any] | None = None,
        llm_factory: Callable[[], Any] | None = None,
        emit_push: "Callable[[dict], None] | None" = None,
    ):
        self.skill_id = skill_id
        self.work_root = Path(work_root)
        self.run_id = run_id
        self.project = project or {}
        self._llm_factory = llm_factory
        self._llm = None
        # thread-safe 推送回调：由 make_node 从 _RUN_PUSH_FNS 注入。
        # 非 None 时 execute_step 会在 step 开始和每次 emit() 时调用它。
        self.emit_push: Callable[[dict], None] | None = emit_push

    # ── 路径工具 ──

    @property
    def start_dir(self) -> Path:
        return self.work_root / "ProjectData" / "Start"

    @property
    def input_dir(self) -> Path:
        return self.work_root / "ProjectData" / "Input"

    @property
    def runtime_dir(self) -> Path:
        return self.work_root / "ProjectData" / "RunTime"

    @property
    def output_dir(self) -> Path:
        return self.work_root / "ProjectData" / "Output"

    @property
    def images_dir(self) -> Path:
        return self.work_root / "ProjectData" / "Images"

    def ensure_dirs(self) -> None:
        for d in [self.start_dir, self.input_dir, self.runtime_dir, self.output_dir, self.images_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def rel(self, p: Path | str) -> str:
        """绝对路径 → 相对 work_root 的字符串"""
        return str(Path(p).resolve().relative_to(self.work_root.resolve()))

    # ── LLM ──

    @property
    def llm(self):
        """懒加载 LLM client（避免 import 时拉起网络）"""
        if self._llm is None:
            if self._llm_factory is None:
                raise RuntimeError("SkillContext 没有 llm_factory，无法调用 LLM")
            self._llm = self._llm_factory()
        return self._llm

    def invoke_llm(
        self,
        messages,
        *,
        step_key: str = "",
        run_name: str | None = None,
        extra_metadata: dict | None = None,
        extra_tags: list[str] | None = None,
    ):
        """
        统一 LLM 入口（推荐使用）。

        自动给每次调用打：
          metadata = {skill, step, run_id, ...extra_metadata}
          tags     = ["skill:zhgk", "step:report_gen", ...extra_tags]
          run_name = "zhgk.report_gen" (或自定义)

        Langfuse / LangSmith 据此聚合：可按 skill 看总成本，按 step 看延迟分布，
        按 run_id 反查单次 run 的所有 LLM 调用链。
        """
        meta: dict = {
            "skill": self.skill_id,
            "step": step_key or "unknown",
            "run_id": self.run_id,
        }
        if extra_metadata:
            meta.update(extra_metadata)

        tags = [f"skill:{self.skill_id}"]
        if step_key:
            tags.append(f"step:{step_key}")
        if extra_tags:
            tags.extend(extra_tags)

        config = {
            "metadata": meta,
            "tags": tags,
            "run_name": run_name or f"{self.skill_id}.{step_key or 'llm'}",
        }
        return self.llm.invoke(messages, config=config)

    def call_tool(
        self,
        name: str,
        params: dict | None = None,
        *,
        step_key: str = "",
        emit: Callable[[str], None] | None = None,
    ):
        """
        统一工具入口（《交付 Claw/Agent 工程范式》§4.2 / 铁律⑤）。

        所有 step / 受控子任务调工具都走这里：
          - 受控执行：cast → validate → run（由 ToolRegistry 保证），出错回提示不抛栈
          - 可观测：尽力创建 Langfuse span（tool/params/result/latency）；未配置则静默跳过
          - 日志：可选 emit 一行到 step 日志（state.logs 可见）

        用法（在 step.run 内）：
            text = ctx.call_tool("read_file", {"path": p}, step_key=self.key, emit=emit)
        """
        from agent.tools import DEFAULT_TOOLS
        from agent.tools.trace import execute_traced

        return execute_traced(
            DEFAULT_TOOLS,
            name,
            params,
            scope=self.skill_id,
            step=step_key or "",
            run_id=self.run_id,
            emit=emit,
        )


# ─── BaseStep ───

# 流式日志回调签名：emit("xxx") · 由 Skill.run_step 注入
Emit = Callable[[str], None]


class BaseStep(abc.ABC):
    """
    一个 Skill 节点的抽象基类。

    子类必须设置：
        key: str        — 节点 ID（小写下划线）
        name: str       — 中文显示名
    子类必须实现：
        check_inputs(ctx) -> CheckResult
        run(ctx, state, emit) -> StepResult
    """

    key: str = ""
    name: str = ""
    artifacts_pattern: list[str] = []  # 相对 work_root 的产物路径
    internal: bool = False             # True = 基础设施步骤（如 preflight 环境预检），
                                       # 豁免 SKILL.md 业务流程表契约校验（lint_skill_contract）

    def check_inputs(self, ctx: SkillContext) -> CheckResult:
        """默认：不需要检查任何前置文件"""
        return {"ok": True, "missing": [], "found": [], "note": ""}

    @abc.abstractmethod
    def run(self, ctx: SkillContext, state: SkillState, emit: Emit) -> StepResult:
        """
        执行步骤。可在内部调用 ctx.llm.invoke(...)、读写文件、subprocess 等。
        使用 emit("xxx") 推送实时日志（FastAPI SSE 层订阅）。
        返回 StepResult（LangGraph state diff）。
        """

    # ── 工具方法 ──

    def collect_existing_artifacts(self, ctx: SkillContext) -> list[str]:
        """扫 artifacts_pattern 取实际存在的产物相对路径"""
        out = []
        for pat in self.artifacts_pattern:
            full = (ctx.work_root / pat).resolve()
            if full.exists() and full.is_file():
                out.append(pat)
        return out

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def make_record(self, status: StepStatus, **extra: Any) -> StepRecord:
        rec: StepRecord = {
            "key": self.key,
            "name": self.name,
            "status": status,
            "started_at": self._now(),
            "log_tail": [],
            "artifacts": [],
            "progress": 0,
        }
        rec.update(extra)
        return rec


# ─── BaseSkill ───

class BaseSkill(abc.ABC):
    """
    一组 BaseStep 的编排。
    子类必须实现 / 设置：
        name        : str
        description : str
        steps       : list[BaseStep]    # 顺序
    可选：
        sdui_projector: ClassVar[Callable[[dict], dict] | None]
            SkillState → SduiDocument JSON dict 的纯函数投影器。
            设置后 SSE 层自动按 skill_id 路由，新 skill 只需绑定自己的 sdui.py::project，
            不再需要改 main.py。
            示例（ZhgkSkill）：
                from .sdui import project as _sdui_project
                sdui_projector = staticmethod(_sdui_project)
    """

    name: str = ""
    description: str = ""
    steps: list[BaseStep] = []

    # SDUI 投影器：SkillState → SduiDocument dict（纯函数，用 staticmethod 防止 Python 绑定）
    sdui_projector: ClassVar[Callable[[dict[str, Any]], dict[str, Any]] | None] = None

    # ── 运行时分派钩子（让 main.py 按 skill 通用化，新模块无需改 HTTP 层）──

    # 支持「仅重试该步」(step_retry) 的 step.key 列表；不在表内的 step HITL 走 full_restart。
    # 例：zhgk 的 report_distribute（避免补料后重跑 report_gen 的 LLM）。
    step_retry_keys: ClassVar[list[str]] = []

    # 编排形态：False = 线性 DAG（默认 · zhgk/guihua）；True = 命令分发图（菜单式 · a3 系统设计）。
    # dispatch 模式下 build_graph 生成：START → _dispatch →（按 project["command"] 选中的 handler）→ END，
    # 每个 handler 即 steps[] 里的一个 step（key = 命令 id），用户可任意顺序触发命令（每个 run 跑一条）。
    # 见 agent/docs/A3-MIGRATION-PLAN.md。向后兼容：线性 skill 不设此属性即沿用原行为。
    dispatch_mode: ClassVar[bool] = False
    # dispatch 模式下 project 未带 command 时的兜底命令（默认用 steps[0].key）。
    default_command: ClassVar[str] = ""

    # 文件补齐（HITL）处理器。鸭子类型，需提供模块级函数：
    #   infer_upload_kind(filename)->str · save_upload(root, kind, file)
    #   check_need_files(root, need)->dict · check_project_files(root)->dict
    # None = 该 skill 无文件补齐 HITL（/upload·/files/check 返回 501）。
    # 例：zhgk 挂模块内 agent.skills.zhgk.files 模块（自包含）。
    file_handler: ClassVar[Any] = None

    # SKILL.md 在 Claude Code skills 目录下的路径（可被子类覆盖）。
    # 默认走 ~/.claude/skills/<name>/SKILL.md 约定。
    skill_md_path: Path | None = None

    def initial_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        """把客户端 start 请求体映射为 state['project']。
        默认原样透传；子类可覆盖以填默认值（见 ZhgkSkill）。"""
        return dict(payload or {})

    def apply_resume_payload(
        self, project: dict[str, Any], payload: dict[str, Any], hitl_step: str
    ) -> dict[str, Any]:
        """resume 时把用户 HITL 回复并入 project。

        默认 no-op。子类可覆盖以支持「确认型 HITL」：把用户在 ChoiceCard 的选择
        写进 project（如 project['confirmations'][gate]=True），因 full_restart 重跑
        保留 project，确认状态得以跨重跑存活、对应 step 的 check_inputs 据此放行。
        见 GuihuaSkill。"""
        return project

    def __init__(self, work_root: Path, llm_factory: Callable[[], Any] | None = None):
        self.work_root = Path(work_root)
        self.llm_factory = llm_factory

        # ── SKILL.md 是 source of truth：启动时读 frontmatter 同步到 self ──
        from ._loader import load_skill_md, default_skill_md_path
        md_path = self.skill_md_path or default_skill_md_path(self.name)
        self.metadata = load_skill_md(md_path)
        # 若 SKILL.md 给了 description，覆盖类属性（保持 A 层唯一真相）
        if self.metadata.description:
            self.description = self.metadata.description
        if self.metadata.name and self.metadata.name != self.name:
            # 名字不一致：警告但不阻断（保留代码侧的 name 作为运行时 ID）
            import warnings
            warnings.warn(
                f"BaseSkill: class name='{self.name}' 与 SKILL.md name='{self.metadata.name}' 不一致",
                stacklevel=2,
            )

    # ── 单 Step 执行（被 LangGraph 节点函数调用）──

    def execute_step(self, step: BaseStep, state: SkillState, ctx: SkillContext) -> StepResult:
        """
        统一的 step 执行模板：前置检查 → 检查通过则 run → 收产物 → 返回 diff。
        失败 / HITL 时返回相应的 state diff，由 graph 决定流向。
        """
        logs: list[str] = [f"[{step.key}] ▶ 开始 {step.name}"]
        _push = ctx.emit_push  # thread-safe 推送回调（可能为 None）

        def emit(msg: str) -> None:
            logs.append(msg)
            # 实时推送日志到 SSE（main.py 的 _thread_push 会节流）
            if _push is not None:
                try:
                    _push({"event": "step_log", "data": {"step": step.key, "msg": msg}})
                except Exception:
                    pass

        # 前置检查
        check = step.check_inputs(ctx)
        if not check["ok"]:
            missing = check.get("missing") or []
            need_inputs = check.get("need_inputs") or []
            if need_inputs:
                logs.append(f"[{step.key}] ⏸ HITL · 等待确认 {len(need_inputs)} 项")
                default_reason = f"{step.name} 需要确认"
            else:
                logs.append(f"[{step.key}] ⏸ HITL · 缺 {len(missing)} 项前置文件")
                for f in missing:
                    logs.append(f"  · 缺：{f}")
                default_reason = f"{step.name} 前置文件未就绪"
            rec = step.make_record(
                "hitl",
                ended_at=step._now(),
                log_tail=logs[-8:],
            )
            note = check.get("note", "")
            return {
                "steps": [rec],
                "current_step": step.key,
                "logs": logs,
                "hitl": {
                    "step": step.key,
                    "reason": f"{note}" if note else default_reason,
                    "need_files": missing,
                    "need_inputs": need_inputs,
                    "need_edit": check.get("need_edit"),
                },
            }

        # 通知前端：step 真正开始执行（Stepper 节点变蓝 / 进入 running 态）
        if _push is not None:
            try:
                _push({"event": "step_started", "data": {"step": step.key, "name": step.name}})
            except Exception:
                pass

        # 真实执行
        try:
            result = step.run(ctx, state, emit)
        except Exception as e:
            rec = step.make_record(
                "failed",
                ended_at=step._now(),
                error=f"{type(e).__name__}: {e}",
                log_tail=logs[-8:],
            )
            return {
                "steps": [rec],
                "current_step": step.key,
                "logs": logs + [f"[{step.key}] ❌ 异常 {e}"],
                "error": str(e),
            }

        # 合并 step 自己返回的 diff
        # result 已经是 StepResult，但我们补充 step 记录 / artifacts / progress
        artifacts = result.get("artifacts") or step.collect_existing_artifacts(ctx)
        result_logs = result.get("logs") or []
        all_logs = logs + result_logs

        # step.run() 主动返回 HITL（如 determine_gen 解析 BOQ 后才发现推不出代际制冷
        # → 手选 ChoiceCard）：与 check_inputs 的 HITL 同等对待——记 hitl 状态、保留
        # hitl 字段、不推进 current_step，由 router 据 state["hitl"].step 路由到 END。
        run_hitl = result.get("hitl")
        if run_hitl and run_hitl.get("step"):
            if not result.get("steps"):
                result["steps"] = [step.make_record(
                    "hitl", ended_at=step._now(), log_tail=all_logs[-8:],
                )]
            result["current_step"] = step.key
            result["logs"] = all_logs
            return result  # 保留 result["hitl"]，不清空

        # 如果 result 已经写了 steps，就用 result 的；否则补一个 completed 记录
        if not result.get("steps"):
            rec = step.make_record(
                "completed",
                ended_at=step._now(),
                progress=100,
                artifacts=artifacts,
                log_tail=all_logs[-8:],
                metrics=result.get("metrics", {}),
            )
            result["steps"] = [rec]

        # 默认推进 current_step + overall_progress
        result.setdefault("current_step", self._next_step_key(step.key))
        result.setdefault("overall_progress", self._step_progress_pct(step.key))
        result["logs"] = all_logs
        result["hitl"] = {}  # 清空
        return result

    # ── LangGraph 编排 ──

    def build_graph(self, checkpointer=None):
        """
        生成 compiled LangGraph。

        checkpointer 选择优先级：
          1. 传入的 checkpointer（推荐 · FastAPI 走 AsyncSqliteSaver，见 graph.py）
          2. AIDA_CHECKPOINT=memory → MemorySaver（测试 / CLI 同步场景）
          3. 默认同步 SqliteSaver（agent/runtime/checkpoints.db）
             ⚠️ 同步 SqliteSaver 不支持 graph.astream() 的异步路径，
                FastAPI 异步场景必须传 AsyncSqliteSaver，否则会 NotImplementedError。
          - AIDA_CHECKPOINT_DB=/some/path.db → 覆盖默认路径
        """
        import os
        from langgraph.graph import StateGraph, START, END

        g = StateGraph(SkillState)
        ctx = SkillContext(
            skill_id=self.name,
            work_root=self.work_root,
            run_id="<init>",
            llm_factory=self.llm_factory,
        )
        ctx.ensure_dirs()

        # 注册每个 step 为一个节点（闭包绑定）
        def make_node(s: BaseStep):
            def _node(state: SkillState) -> dict:
                # 每次 invoke 时构造新 ctx（带最新 run_id 和 project）
                run_id = str(state.get("run_id", "<no-run>"))
                local_ctx = SkillContext(
                    skill_id=self.name,
                    work_root=self.work_root,
                    run_id=run_id,
                    project=state.get("project") or {},
                    llm_factory=self.llm_factory,
                    emit_push=_get_run_push(run_id),  # 注入 thread-safe 推送回调
                )
                return self.execute_step(s, state, local_ctx)
            return _node

        for step in self.steps:
            g.add_node(step.key, make_node(step))

        if self.dispatch_mode:
            # 分发图（菜单式）：START → _dispatch →（按 command 选中的 handler）→ END。
            # 每个 handler 跑完即结束（一个 run 跑一条命令）；HITL / error 同样 → END。
            g.add_node("_dispatch", lambda state: {})
            g.add_edge(START, "_dispatch")
            dispatch_route: dict[str, str] = {s.key: s.key for s in self.steps}
            dispatch_route["__end__"] = END
            g.add_conditional_edges("_dispatch", self._dispatch_router, dispatch_route)
            for step in self.steps:
                g.add_conditional_edges(
                    step.key,
                    self._make_router(step.key, None),
                    self._route_map(None),
                )
        else:
            # 线性串行边 · 用 conditional_edges 处理 HITL / error 中断
            g.add_edge(START, self.steps[0].key)
            for i, step in enumerate(self.steps):
                next_key = self.steps[i + 1].key if i + 1 < len(self.steps) else None
                g.add_conditional_edges(
                    step.key,
                    self._make_router(step.key, next_key),
                    self._route_map(next_key),
                )

        # 选 checkpointer
        if checkpointer is None:
            ckpt_mode = os.environ.get("AIDA_CHECKPOINT", "sqlite").strip().lower()
            if ckpt_mode == "memory":
                from langgraph.checkpoint.memory import MemorySaver
                checkpointer = MemorySaver()
            else:
                from langgraph.checkpoint.sqlite import SqliteSaver
                import sqlite3
                db_path = default_checkpoint_db()
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
                # check_same_thread=False · LangGraph 在 asyncio worker 里跑，会跨线程
                conn = sqlite3.connect(db_path, check_same_thread=False)
                checkpointer = SqliteSaver(conn)

        return g.compile(checkpointer=checkpointer)

    def _make_router(self, this_key: str, next_key: str | None):
        """生成 step 出口路由"""
        def _route(state: SkillState) -> str:
            if state.get("error"):
                return "__end__"
            if state.get("hitl") and state["hitl"].get("step"):
                return "__end__"
            return next_key or "__end__"
        return _route

    def _dispatch_router(self, state: SkillState) -> str:
        """dispatch 模式入口路由：按 project["command"] 选中对应 handler step。
        无 command → default_command → 兜底 steps[0]。未知命令也兜底首个 step。"""
        if state.get("error"):
            return "__end__"
        keys = {s.key for s in self.steps}
        cmd = str((state.get("project") or {}).get("command") or self.default_command or "")
        if cmd in keys:
            return cmd
        return self.steps[0].key if self.steps else "__end__"

    def _route_map(self, next_key: str | None) -> dict[str, str]:
        from langgraph.graph import END
        m = {"__end__": END}
        if next_key:
            m[next_key] = next_key
        return m

    # ── 工具 ──

    def _next_step_key(self, current: str) -> str:
        keys = [s.key for s in self.steps]
        try:
            idx = keys.index(current)
        except ValueError:
            return current
        return keys[idx + 1] if idx + 1 < len(keys) else current

    def _step_progress_pct(self, step_key: str) -> int:
        keys = [s.key for s in self.steps]
        try:
            idx = keys.index(step_key)
        except ValueError:
            return 0
        return int(100 * (idx + 1) / len(keys))
