"""
AIDA Agent · LangGraph State Schema
─────────────────────────────────────────
智慧工勘（zhgk）pilot Agent 的共享状态。
按 LangGraph 推荐模式用 TypedDict + reducer。

后续其它模块（规划设计 / 设备安装 / 部署调测）可继承 BaseAgentState
扩展 module_specific 字段。
"""
from __future__ import annotations
from typing import TypedDict, Annotated, Literal, Any
from operator import add


# ─── 通用 ───

StepKey = Literal[
    "preflight",
    "scene_filter",
    "survey_build",
    "report_gen",
    "report_distribute",
]

StepStatus = Literal["pending", "running", "completed", "failed", "hitl"]


class StepRecord(TypedDict, total=False):
    """单个 step 的执行记录"""
    key: StepKey
    name: str
    status: StepStatus
    started_at: str    # ISO ts
    ended_at: str      # ISO ts
    progress: int      # 0-100
    log_tail: list[str]
    artifacts: list[str]   # 产物文件相对路径
    error: str             # 失败时的报错


class ProjectMeta(TypedDict, total=False):
    """项目元数据 · 跨 step 共享"""
    project_code: str          # 如 K1903
    project_name: str          # 智算 Q3 · 客户甲一期
    scenario_new: str          # 新增 / 节点扩容
    scenario_run: str          # 推理 / 训练 / 训推一体 / 大EP
    room_count: int            # 机房数
    pod_count: int             # PoD 数


class FilePaths(TypedDict, total=False):
    """各阶段产物路径（相对 zhgk skill 根目录）"""
    boq_xlsx: str
    presets_docx: str
    images_dir: str
    runtime: dict[str, str]    # RunTime/ 下产物
    output: dict[str, str]     # Output/ 下产物


# ─── HITL 中断信息 ───

class HitlRequest(TypedDict, total=False):
    """LangGraph interrupt 携带的人工干预请求"""
    step: StepKey
    reason: str                # 文字说明
    need_files: list[str]      # 缺失文件清单
    need_inputs: list[dict]    # 需要用户决策的输入（{key, label, options}）


# ─── 顶层 Agent State ───

class AgentState(TypedDict, total=False):
    """智慧工勘 Agent 的完整状态"""
    # 元数据
    run_id: str
    skill_id: str              # 默认 "zhgk"
    started_at: str
    project: ProjectMeta

    # 各 step 状态（用 reducer 累加更新）
    steps: Annotated[list[StepRecord], add]

    # 当前 step + 整体进度
    current_step: StepKey
    overall_progress: int      # 0-100，自动计算

    # 文件与产物
    files: FilePaths

    # HITL（人在回路）
    hitl: HitlRequest          # 当前是否在等用户输入；非空表示等待
    hitl_resume: dict          # 用户提交回来的数据

    # 流式日志（节点内追加）
    logs: Annotated[list[str], add]

    # 最终错误（若有）
    error: str
