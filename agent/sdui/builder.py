"""
SDUI Builder · Pydantic models aligned with frontend/lib/sdui.ts

Extended from nanobot/skills/sdui_builder.py to cover all node types
needed by AIDA skills (including ArtifactGrid, FilePicker, ChoiceCard, etc.).

Usage:
    from agent.sdui.builder import SduiDocument, SduiStackNode, SduiTextNode
    doc = SduiDocument(root=SduiStackNode(children=[SduiTextNode(content="Hello")]))
    json_dict = dump_sdui_json(doc)   # model_dump(mode="json")
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

# ── Actions ──────────────────────────────────────────────────────────────────

class SduiPostUserMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["post_user_message"] = "post_user_message"
    text: str


class SduiOpenPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["open_preview"] = "open_preview"
    path: str


class SduiResetSession(BaseModel):
    """重置会话动作：前端清空当前 run 状态、回到 idle（卡片头部「重置会话」按钮触发）。"""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["reset_session"] = "reset_session"


SduiAction = Annotated[
    Union[SduiPostUserMessage, SduiOpenPreview, SduiResetSession],
    Field(discriminator="kind"),
]


class SduiCardHeaderAction(BaseModel):
    """卡片头部动作按钮（label + variant + action）。"""
    model_config = ConfigDict(extra="ignore")
    label: str
    variant: Literal["primary", "secondary", "ghost", "danger"] | None = None
    action: SduiAction

SpacingToken = Literal["none", "xs", "sm", "md", "lg", "xl"]

# ── Helpers ───────────────────────────────────────────────────────────────────

class KeyValueItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    key: str
    value: str


# ── Layout nodes ─────────────────────────────────────────────────────────────

class SduiDividerNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["Divider"] = "Divider"
    id: str | None = None
    # label：给分隔线挂一个 eyebrow 小标题（大写小字 + 延伸细线），用作分节眉题，
    # 把同区多张卡分组（如「评估结果」「产出与摘要」），告别平铺卡墙。
    label: str | None = None


class SduiSkeletonNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["Skeleton"] = "Skeleton"
    id: str | None = None
    variant: Literal["text", "rect", "card", "row"] | None = None
    lines: int | None = None


class SduiStackNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["Stack"] = "Stack"
    id: str | None = None
    gap: SpacingToken | None = None
    justify: Literal["start", "center", "end", "between"] | None = None
    children: list["SduiNode"] | None = None
    flex: float | None = None


class SduiCardNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["Card"] = "Card"
    id: str | None = None
    title: str | None = None
    density: Literal["default", "compact"] | None = None
    children: list["SduiNode"] | None = None
    tone: Literal["default", "warning", "danger", "info", "success"] | None = None
    headerAction: SduiCardHeaderAction | None = None
    # collapsible=True：卡片头变可点击折叠开关（需 title）；defaultCollapsed 决定初始折叠态。
    # 用于把次要明细（如 micro-step Stepper）收起，减轻信息墙。
    collapsible: bool | None = None
    defaultCollapsed: bool | None = None


class SduiRowNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["Row"] = "Row"
    id: str | None = None
    gap: SpacingToken | None = None
    align: Literal["start", "center", "end", "stretch", "baseline"] | None = None
    justify: Literal["start", "end", "center", "between", "around"] | None = None
    wrap: bool | None = None
    children: list["SduiNode"] | None = None
    flex: float | None = None


# ── Text nodes ────────────────────────────────────────────────────────────────

class SduiTextNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["Text"] = "Text"
    id: str | None = None
    content: str
    variant: Literal["caption", "body", "heading", "mono"] | None = None
    color: Literal["success", "warning", "error", "accent", "subtle"] | None = None


class SduiMarkdownNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["Markdown"] = "Markdown"
    id: str | None = None
    content: str


# ── Data display nodes ────────────────────────────────────────────────────────

class SduiBadgeNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["Badge"] = "Badge"
    id: str | None = None
    text: str
    tone: Literal["default", "success", "warning", "danger"] | None = None
    label: str | None = None


class SduiStatisticNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["Statistic"] = "Statistic"
    id: str | None = None
    title: str
    value: str | int | float
    color: Literal["success", "warning", "error", "accent", "subtle"] | None = None


class SduiStatisticRowItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str
    value: str | int | float
    color: Literal["success", "warning", "error", "accent", "subtle"] | None = None


class SduiStatisticRowNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["StatisticRow"] = "StatisticRow"
    id: str | None = None
    items: list[SduiStatisticRowItem]
    flex: float | None = None


class SduiKeyValueListNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["KeyValueList"] = "KeyValueList"
    id: str | None = None
    items: list[KeyValueItem]


class SduiTableNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["Table"] = "Table"
    id: str | None = None
    headers: list[str] | None = None
    rows: list[list[str]]


class SduiGoldenMetricsNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["GoldenMetrics"] = "GoldenMetrics"
    id: str | None = None
    metrics: list[dict[str, Any]] | None = None


# ── Chart nodes ────────────────────────────────────────────────────────────────

class SduiDonutSegment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label: str
    value: float | int
    color: str | None = None


class SduiDonutChartNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["DonutChart"] = "DonutChart"
    id: str | None = None
    segments: list[SduiDonutSegment]
    centerLabel: str | None = None
    centerValue: str | None = None
    flex: float | None = None


class SduiBarDatum(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label: str
    value: float | int
    color: str | None = None


class SduiBarChartNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["BarChart"] = "BarChart"
    id: str | None = None
    data: list[SduiBarDatum]
    valueUnit: str | None = None
    flex: float | None = None


# ── Action nodes ───────────────────────────────────────────────────────────────

class SduiButtonNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["Button"] = "Button"
    id: str | None = None
    label: str
    variant: Literal["primary", "secondary", "ghost", "outline"] | None = None
    action: SduiPostUserMessage | SduiOpenPreview


class SduiLinkNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["Link"] = "Link"
    id: str | None = None
    label: str
    href: str | None = None
    action: SduiPostUserMessage | SduiOpenPreview | None = None


# ── Stepper ───────────────────────────────────────────────────────────────────

class SduiStepperStep(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    title: str
    status: Literal["waiting", "running", "done", "error"]
    detail: list[str] | None = None


class SduiStepperNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["Stepper"] = "Stepper"
    id: str | None = None
    steps: list[SduiStepperStep]
    orientation: Literal["horizontal", "vertical"] | None = None


# ── Artifact / File nodes ─────────────────────────────────────────────────────

class SduiArtifactItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str | None = None
    label: str
    path: str
    kind: Literal["docx", "xlsx", "pdf", "html", "json", "md", "png", "other"] | None = None
    status: Literal["ready", "generating", "error"] | None = None


class SduiArtifactGridNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["ArtifactGrid"] = "ArtifactGrid"
    id: str | None = None
    artifacts: list[SduiArtifactItem]
    mode: Literal["input", "output"] | None = None
    title: str | None = None
    flex: float | None = None


# ── v1.1 display nodes ────────────────────────────────────────────────────────

class SduiAlertNode(BaseModel):
    """横幅通知。tone: info / success / warning / error"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["Alert"] = "Alert"
    id: str | None = None
    tone: Literal["info", "success", "warning", "error"] | None = None
    title: str | None = None
    message: str


class SduiTimelineEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label: str
    time: str | None = None
    tone: Literal["default", "success", "warning", "error"] | None = None


class SduiTimelineNode(BaseModel):
    """竖向时间轴，适合步骤日志、事件流。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["Timeline"] = "Timeline"
    id: str | None = None
    events: list[SduiTimelineEvent]


class SduiNumberCardNode(BaseModel):
    """突出单个 KPI 大数字，可附趋势方向。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["NumberCard"] = "NumberCard"
    id: str | None = None
    value: str | int | float
    label: str
    delta: str | None = None
    deltaDir: Literal["up", "down", "neutral"] | None = None
    tone: Literal["success", "warning", "error", "accent", "subtle"] | None = None


class SduiPlaneCell(BaseModel):
    """PlaneMatrix 的单元格：一个网络平面 + 其规划状态。"""
    model_config = ConfigDict(extra="ignore")
    label: str
    status: Literal["done", "running", "pending", "error"] | None = None
    group: str | None = None          # 分组（如「计算面」「存储面」），同组聚拢展示
    note: str | None = None           # 角标说明（如产物文件名 / 链路数）


class SduiPlaneMatrixNode(BaseModel):
    """平面矩阵 · a3 系统设计大盘核心节点：N 个网络平面 × 规划状态的网格。
    每格 = 一个平面（计算/存储各面），status 反映该平面是否已出规划产物。
    用于「地址规划」类编排器型 skill 展示跨命令累积进度。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["PlaneMatrix"] = "PlaneMatrix"
    id: str | None = None
    cells: list[SduiPlaneCell]
    columns: int | None = None        # 网格列数（默认前端自适应）
    flex: float | None = None


# ── Business nodes ────────────────────────────────────────────────────────────

class SduiRiskItem(BaseModel):
    """RiskList 的一条风险：标题 + 等级 + 可选明细（场景 / 建议 / 编号）。"""
    model_config = ConfigDict(extra="ignore")
    title: str
    level: Literal["high", "mid", "low"]
    detail: str | None = None


class SduiRiskListNode(BaseModel):
    """风险清单 · 按等级（高/中/低）色带展示。zhgk 风险识别、评估类 skill 通用。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["RiskList"] = "RiskList"
    id: str | None = None
    items: list[SduiRiskItem]
    title: str | None = None
    flex: float | None = None


# ── Tier B nodes (v4 通用扩展) ─────────────────────────────────────────────────

class SduiEmptyStateNode(BaseModel):
    """空状态 · 无数据 / 待启动时的占位（图标 + 标题 + 副标题）。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["EmptyState"] = "EmptyState"
    id: str | None = None
    title: str
    subtitle: str | None = None
    icon: str | None = None


class SduiSpinnerNode(BaseModel):
    """加载 / 执行中转圈（可附说明文字）。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["Spinner"] = "Spinner"
    id: str | None = None
    label: str | None = None
    tone: Literal["default", "brand"] | None = None


class SduiProgressBarNode(BaseModel):
    """进度条 · value 0–100，tone 决定填充色。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["ProgressBar"] = "ProgressBar"
    id: str | None = None
    value: float | int
    label: str | None = None
    tone: Literal["success", "warning", "danger"] | None = None
    flex: float | None = None


class SduiBannerNode(BaseModel):
    """通栏横幅 · 比 Alert 更轻量的单行提示。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["Banner"] = "Banner"
    id: str | None = None
    message: str
    title: str | None = None
    tone: Literal["brand", "warning"] | None = None


class SduiCodeBlockNode(BaseModel):
    """代码 / 命令块（可附文件名）。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["CodeBlock"] = "CodeBlock"
    id: str | None = None
    code: str
    filename: str | None = None
    language: str | None = None


class SduiLogLine(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str
    time: str | None = None
    level: Literal["ok", "warn", "error", "info"] | None = None


class SduiLogStreamNode(BaseModel):
    """执行日志流 · 语义色日志行（时间 + 文本 + 级别）。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["LogStream"] = "LogStream"
    id: str | None = None
    lines: list[SduiLogLine]


class SduiChecklistItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label: str
    done: bool | None = None


class SduiChecklistNode(BaseModel):
    """勾选清单 · 完成项打勾 + 删除线。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["Checklist"] = "Checklist"
    id: str | None = None
    items: list[SduiChecklistItem]


class SduiFileTreeItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    type: Literal["file", "dir"] | None = None
    depth: int | None = None
    tag: str | None = None


class SduiFileTreeNode(BaseModel):
    """文件树 · 目录/文件层级（depth 缩进，dir 加粗）。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["FileTree"] = "FileTree"
    id: str | None = None
    items: list[SduiFileTreeItem]


class SduiTabItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label: str
    content: str | None = None


class SduiTabsNode(BaseModel):
    """页签 · 多视图切换（content 为文本/markdown）。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["Tabs"] = "Tabs"
    id: str | None = None
    tabs: list[SduiTabItem]


class SduiAccordionItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str
    body: str


class SduiAccordionNode(BaseModel):
    """手风琴 · 可展开/折叠的分节内容。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["Accordion"] = "Accordion"
    id: str | None = None
    items: list[SduiAccordionItem]


class SduiDataTableColumn(BaseModel):
    """类型化列：key 取行 dict 字段，type 决定单元格渲染（文本 / 状态徽标 / 进度条）。

    editable=True 的列在可编辑表里渲染为输入框（如 ESN 列）；其余列只读。"""
    model_config = ConfigDict(extra="ignore")
    key: str
    label: str
    type: Literal["text", "status", "progress"] = "text"
    width: int | None = None
    editable: bool = False
    placeholder: str | None = None


class SduiDataTableNode(BaseModel):
    """数据表格 · 列 + 行（带标题 / 计数栏）。

    两种形态向后兼容：
      ① 旧只读位置型：columns=list[str]、rows=list[list]（zhgk 等沿用）；
      ② 新类型化 / 可编辑：columns=list[SduiDataTableColumn]、rows=list[dict]，
         editable=True 时前端按列 type 渲染输入框 + 底部「填充 / 提交」按钮。
    """
    model_config = ConfigDict(extra="ignore")
    type: Literal["DataTable"] = "DataTable"
    id: str | None = None
    columns: list[str] | list[SduiDataTableColumn]
    rows: list[list[str | int | float]] | list[dict[str, Any]]
    title: str | None = None
    subtitle: str | None = None
    flex: float | None = None
    # ── 可编辑 / 提交（新形态）──
    editable: bool = False
    submitMode: Literal["resume", "run-patch"] | None = None
    submitLabel: str | None = None
    stepId: str | None = None
    rowKey: str | None = None
    checkKey: str | None = None          # 勾选列字段名（task_dispatch）
    fillLabel: str | None = None         # 「一键填充」按钮文案
    fillRows: list[dict[str, Any]] | None = None  # 一键填充后的整组行
    groupKey: str | None = None          # 分组列（esn 按设备大类）
    pageSize: int | None = None
    requiredKeys: list[str] | None = None  # 提交前必填校验


class SduiTabbedTableTab(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label: str
    headers: list[str] | None = None
    rows: list[list[str]]


class SduiTabbedTableNode(BaseModel):
    """页签表格 · 多组表格按页签切换（device_install ESN 表）。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["TabbedTable"] = "TabbedTable"
    id: str | None = None
    tabs: list[SduiTabbedTableTab]


class SduiMultiSelectOption(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label: str
    value: str | None = None


class SduiMultiSelectNode(BaseModel):
    """多选 · pill 形式可多选（本地状态展示）。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["MultiSelect"] = "MultiSelect"
    id: str | None = None
    options: list[SduiMultiSelectOption]
    title: str | None = None


class SduiSliderNode(BaseModel):
    """滑块 · value + min/max（本地状态展示）。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["Slider"] = "Slider"
    id: str | None = None
    value: float | int
    label: str | None = None
    min: float | int | None = None
    max: float | int | None = None
    unit: str | None = None


class SduiConfirmDialogNode(BaseModel):
    """确认对话 · 标题 + 消息 + 确认/取消按钮。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["ConfirmDialog"] = "ConfirmDialog"
    id: str | None = None
    title: str
    message: str | None = None
    confirmLabel: str | None = None
    cancelLabel: str | None = None


class SduiFormField(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label: str
    placeholder: str | None = None
    value: str | None = None


class SduiFormGroupNode(BaseModel):
    """表单组 · 多个 label + 输入框。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["FormGroup"] = "FormGroup"
    id: str | None = None
    fields: list[SduiFormField]


# ── Tier C nodes (v4 业务扩展) ─────────────────────────────────────────────────

class SduiStatusItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: Literal["run", "pause", "fail", "done"]
    text: str


class SduiStatusBannerNode(BaseModel):
    """运行态通栏 · 状态点 + 文本（执行中/待补充/失败）。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["StatusBanner"] = "StatusBanner"
    id: str | None = None
    items: list[SduiStatusItem]


class SduiSegmentedControlNode(BaseModel):
    """轻量视图切换（本地状态）。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["SegmentedControl"] = "SegmentedControl"
    id: str | None = None
    segments: list[str]
    caption: str | None = None


class SduiVStepItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label: str
    status: Literal["done", "running", "pending"] | None = None


class SduiVerticalStepperNode(BaseModel):
    """竖向步骤条 · 轻量（纯标签，无日志）。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["VerticalStepper"] = "VerticalStepper"
    id: str | None = None
    items: list[SduiVStepItem]


class SduiAssessSegment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label: str
    value: float | int
    color: str | None = None


class SduiAssessmentBarNode(BaseModel):
    """五值评估堆叠条 · 满足/不满足/不涉及/无法识别。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["AssessmentBar"] = "AssessmentBar"
    id: str | None = None
    segments: list[SduiAssessSegment]
    title: str | None = None


class SduiRecipient(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    role: str | None = None
    status: str | None = None


class SduiRecipientListNode(BaseModel):
    """分发对象 / 审批链 · 头像 + 姓名 + 角色 + 状态。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["RecipientList"] = "RecipientList"
    id: str | None = None
    items: list[SduiRecipient]


class SduiDiffRow(BaseModel):
    model_config = ConfigDict(extra="ignore")
    left: str
    right: str
    change: Literal["add", "del", "chg"] | None = None


class SduiDiffViewNode(BaseModel):
    """左右对比 · BOQ vs HLD（增/删/改色标）。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["DiffView"] = "DiffView"
    id: str | None = None
    rows: list[SduiDiffRow]
    leftTitle: str | None = None
    rightTitle: str | None = None


class SduiInlinePreviewNode(BaseModel):
    """内嵌产物预览 · 文件名 + 预览占位。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["InlinePreview"] = "InlinePreview"
    id: str | None = None
    filename: str
    placeholder: str | None = None


class SduiImageItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    caption: str                       # 底部浮层文件名（如 PDU-01.jpg）
    label: str | None = None           # 无图时居中的场景占位标签（如「配电」）
    src: str | None = None             # 真实图片路径 / URL；给定则渲染缩略图，否则回退占位


class SduiImageGridNode(BaseModel):
    """现场照片网格 · 缩略图 + 文件名（src 有值渲染真图，否则场景占位）。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["ImageGrid"] = "ImageGrid"
    id: str | None = None
    images: list[SduiImageItem]


class SduiToastNode(BaseModel):
    """浮层通知 · 单行轻提示（状态点 + 主文案 + 副文案）。
    SDUI 静态投影里作为「已完成/已保存」类即时反馈展示，无自动消失计时。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["Toast"] = "Toast"
    id: str | None = None
    message: str
    detail: str | None = None
    tone: Literal["success", "info", "warning", "error"] | None = None


class SduiSparklineNode(BaseModel):
    """指标迷你趋势 · 折线 + 当前值 + 变化。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["Sparkline"] = "Sparkline"
    id: str | None = None
    points: list[float | int]
    label: str | None = None
    value: str | int | float | None = None
    delta: str | None = None


class SduiDashboardLayoutNode(BaseModel):
    """双栏仪表盘 · 主区 + 右侧栏（递归子节点）。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["DashboardLayout"] = "DashboardLayout"
    id: str | None = None
    main: list["SduiNode"]
    side: list["SduiNode"]


class SduiDrawerNode(BaseModel):
    """侧滑详情面板 · 标题 + 递归子节点（此处内嵌展示）。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["Drawer"] = "Drawer"
    id: str | None = None
    title: str
    children: list["SduiNode"] | None = None


# ── Tier D nodes (v5 业务扩展 · 交付台 / 系统设计) ──────────────────────────────

class SduiTabPanel(BaseModel):
    """TabGroup 的一个页签：id + label + 可选 badge 角标 + 递归子节点。"""
    model_config = ConfigDict(extra="ignore")
    id: str
    label: str
    badge: str | int | None = None
    children: list["SduiNode"] | None = None


class SduiTabGroupNode(BaseModel):
    """页签容器 · 子节点按页签分组切换（区别于只放文本的 Tabs / 只放表格的 TabbedTable）。
    badge 显示计数/未读角标；activeTab 给定页签 id 作为初始选中，后端可借此引导
    （如执行中切「进度」页）。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["TabGroup"] = "TabGroup"
    id: str | None = None
    tabs: list[SduiTabPanel]
    activeTab: str | None = None


class SduiInputSlot(BaseModel):
    """InputSlotList 的一行输入件槽位。source=auto 仿真产出 / manual 人工上传；
    ready 表就绪（有文件）；缺失的 manual 件给上传 CTA，缺失的 auto 件显示「检查中」。"""
    model_config = ConfigDict(extra="ignore")
    label: str
    source: Literal["auto", "manual"]
    required: bool | None = None
    ready: bool | None = None
    fileName: str | None = None
    previewPath: str | None = None


class SduiInputSlotListNode(BaseModel):
    """输入件槽位清单 · 每行一个输入件，区分必需/可选 × 自动/手动 × 就绪/缺失。
    缺件行高亮并给行内上传 CTA，就绪行可预览，自动件未就绪显示「检查中」标签。
    （ArtifactGrid 只能列已存在产物，无法表达缺失槽位 + 行内上传 + 必需/自动语义。）"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["InputSlotList"] = "InputSlotList"
    id: str | None = None
    slots: list[SduiInputSlot]
    title: str | None = None


class SduiTaskTimelineStripNode(BaseModel):
    """任务时间规划条 / 迷你甘特 · 计划 vs 实际双轨 + 剩余天数 + 进度填充。
    plannedStart/End 必填；actualStart/End 可选；remainingDays 逾期为负；progressPct 0–100。
    （Timeline 是事件流、KeyValueList 只能列日期，均无双轨甘特 + 剩余天数提醒。）"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["TaskTimelineStrip"] = "TaskTimelineStrip"
    id: str | None = None
    plannedStart: str
    plannedEnd: str
    actualStart: str | None = None
    actualEnd: str | None = None
    remainingDays: int | None = None
    progressPct: float | int | None = None


class SduiMacroStep(BaseModel):
    """MacroStepRail 的一个宏观阶段：id + 标题 + 可选 hint + optional 标记 + 状态。"""
    model_config = ConfigDict(extra="ignore")
    id: str
    title: str
    hint: str | None = None
    optional: bool | None = None
    status: Literal["done", "running", "pending"] | None = None


class SduiMacroStepRailNode(BaseModel):
    """宏观交付蓝图条 · 顶层阶段（如六步 s1–s6），区别于 micro 的 Stepper 步骤日志。
    optional 阶段灰显并标「可选」，hint 给每步副提示，currentId 高亮当前阶段。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["MacroStepRail"] = "MacroStepRail"
    id: str | None = None
    steps: list[SduiMacroStep]
    currentId: str | None = None


class SduiEmbeddedWebNode(BaseModel):
    """内嵌网页 · iframe 承载外部 Web UI（如 nVisual 仿真软件访问页）。

    url 必填；title 作页眉、note 作离线/加载提示；height 像素高（默认前端给 520）。
    openInNewTab=True 时页眉给「新页打开」链接（内网 iframe 不可达时的兜底）。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["EmbeddedWeb"] = "EmbeddedWeb"
    id: str | None = None
    url: str
    title: str | None = None
    note: str | None = None
    height: int | None = None
    openInNewTab: bool | None = None
    # offline=True：内网不可达时不渲染空白 iframe，改用骨架占位 + 说明 + 「新页打开」兜底。
    offline: bool | None = None


# ── HITL nodes ────────────────────────────────────────────────────────────────

class SduiFilePickerNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["FilePicker"] = "FilePicker"
    id: str | None = None
    purpose: str
    label: str | None = None
    helpText: str | None = None
    accept: str | None = None
    multiple: bool | None = None
    hitlRequestId: str | None = None
    stepId: str | None = None


class SduiChoiceOption(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str | None = None
    value: str | None = None
    label: str
    description: str | None = None


class SduiChoiceCardNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["ChoiceCard"] = "ChoiceCard"
    id: str | None = None
    title: str
    options: list[SduiChoiceOption]
    hitlRequestId: str | None = None
    stepId: str | None = None


class SduiHitlTextInputNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["HitlTextInput"] = "HitlTextInput"
    id: str | None = None
    purpose: str | None = None
    title: str | None = None
    label: str | None = None
    placeholder: str | None = None
    rows: int | None = None
    defaultValue: str | None = None
    submitLabel: str | None = None
    helpText: str | None = None
    hitlRequestId: str | None = None
    stepId: str | None = None


# ── MachineRoom3D：3D 机房俯视总览（等距体素 + 机房卡片 + 多入口）─────────────────

class SduiRoom3DEntry(BaseModel):
    """机房卡片底部的作业入口（勘测主线 / 通液电子流 / 液冷湿材质 AI 审核）。"""
    model_config = ConfigDict(extra="ignore")
    key: str
    label: str
    icon: str | None = None            # cube | sync | sparkles
    primary: bool = False
    action: SduiAction | None = None


class SduiRoom3DItemStats(BaseModel):
    """机房勘测条目四值分布（已勘测 / 未勘测 / 无法识别 / 不涉及）。"""
    model_config = ConfigDict(extra="ignore")
    surveyed: int = 0
    pending: int = 0
    unknown: int = 0
    na: int = 0


class SduiMachineRoom(BaseModel):
    """单个机房：grid/racks/cdu 决定 3D 体素体量；itemStats/progress 为状态。"""
    model_config = ConfigDict(extra="ignore")
    id: str
    label: str
    code: str | None = None
    status: str = "active"             # active | pending
    progress: int = 0
    rows: int = 3
    cols: int = 4
    racks: int = 0
    cdu: int = 0
    itemStats: SduiRoom3DItemStats
    # 每个机柜的状态着色（done 完成/绿 · active 进行/蓝 · pending 未始/灰 · risk 不满足/红）；
    # 空则统一品牌色。长度≈racks，由投影器按真实五值比例分配。
    rackStatuses: list[str] = Field(default_factory=list)
    # 机房卡紧凑扫读行（如 ["124 条目", "7 问题", "R3 轮"]）；空则不渲染。
    statKey: list[str] = Field(default_factory=list)
    entries: list[SduiRoom3DEntry] = Field(default_factory=list)


class SduiMachineRoom3DNode(BaseModel):
    """3D 机房俯视总览 · 等距体素场景 + 机房卡片网格 + 多业务入口 + 图例。

    给「以机房为单位的勘测态势」一个立体俯视入口（CSS 3D，前端零依赖）。
    DataTable/PlaneMatrix 只能平铺，无法表达机柜级体量与多入口下钻。"""
    model_config = ConfigDict(extra="ignore")
    type: Literal["MachineRoom3D"] = "MachineRoom3D"
    id: str | None = None
    eyebrow: str | None = None
    title: str | None = None
    subtitle: str | None = None
    headStats: list[dict[str, Any]] = Field(default_factory=list)   # {value,label,tone}
    rooms: list[SduiMachineRoom] = Field(default_factory=list)
    refreshNote: str | None = None


# ── SduiNode union ────────────────────────────────────────────────────────────

SduiNode = Annotated[
    Union[
        SduiStackNode,
        SduiCardNode,
        SduiRowNode,
        SduiDividerNode,
        SduiSkeletonNode,
        SduiStepperNode,
        SduiTextNode,
        SduiMarkdownNode,
        SduiBadgeNode,
        SduiStatisticNode,
        SduiStatisticRowNode,
        SduiKeyValueListNode,
        SduiTableNode,
        SduiButtonNode,
        SduiLinkNode,
        SduiDonutChartNode,
        SduiBarChartNode,
        SduiGoldenMetricsNode,
        SduiArtifactGridNode,
        # v1.1 display nodes
        SduiAlertNode,
        SduiTimelineNode,
        SduiNumberCardNode,
        SduiPlaneMatrixNode,
        # Business
        SduiRiskListNode,
        SduiMachineRoom3DNode,
        # Tier B (v4)
        SduiEmptyStateNode,
        SduiSpinnerNode,
        SduiProgressBarNode,
        SduiBannerNode,
        SduiCodeBlockNode,
        SduiLogStreamNode,
        SduiChecklistNode,
        SduiFileTreeNode,
        SduiTabsNode,
        SduiAccordionNode,
        SduiDataTableNode,
        SduiTabbedTableNode,
        SduiMultiSelectNode,
        SduiSliderNode,
        SduiConfirmDialogNode,
        SduiFormGroupNode,
        # Tier C (v4 业务扩展)
        SduiStatusBannerNode,
        SduiSegmentedControlNode,
        SduiVerticalStepperNode,
        SduiAssessmentBarNode,
        SduiRecipientListNode,
        SduiDiffViewNode,
        SduiInlinePreviewNode,
        SduiImageGridNode,
        SduiToastNode,
        SduiSparklineNode,
        SduiDashboardLayoutNode,
        SduiDrawerNode,
        # Tier D (v5 业务扩展 · 交付台 / 系统设计)
        SduiTabGroupNode,
        SduiInputSlotListNode,
        SduiTaskTimelineStripNode,
        SduiMacroStepRailNode,
        SduiEmbeddedWebNode,
        # HITL
        SduiFilePickerNode,
        SduiChoiceCardNode,
        SduiHitlTextInputNode,
    ],
    Field(discriminator="type"),
]

# ── Document ──────────────────────────────────────────────────────────────────

class SduiDocument(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schemaVersion: int = 1
    type: Literal["SduiDocument"] = "SduiDocument"
    root: "SduiNode"
    meta: dict[str, Any] | None = None


# Resolve forward references for recursive children
_ns: dict[str, Any] = {"SduiNode": SduiNode}
for _m in (SduiStackNode, SduiCardNode, SduiRowNode, SduiDashboardLayoutNode, SduiDrawerNode,
           SduiTabPanel, SduiTabGroupNode, SduiDocument):
    _m.model_rebuild(_types_namespace=_ns)


def dump_sdui_json(doc: SduiDocument) -> dict[str, Any]:
    """Serialize to JSON-compatible dict (camelCase keys preserved)."""
    return doc.model_dump(mode="json")


def choice_options(raw: list[Any] | None) -> list[SduiChoiceOption]:
    """把 CheckResult.need_inputs[i]['options'] 容错转成 SduiChoiceOption 列表。

    统一确认型 HITL 的 options 契约：**所有 skill 投影器都用本函数**构造 ChoiceCard
    选项，避免各投影器各自假设 str / dict 而漂移（历史上 zhgk 投影器按 str 读、guihua
    按 dict 读，撞在一起会把整个 dict 字符串化当 label）。

    每个选项可为：
      - dict（推荐 · 对齐 NeedInputOption）：{"label", "value", "id"?, "description"?}
      - str（兼容）：label = value = 该字符串
    前端 SduiChoiceCard 以 `value`（回退 id）作为提交值，故 value 必须有意义。"""
    out: list[SduiChoiceOption] = []
    for i, o in enumerate(raw or []):
        if isinstance(o, dict):
            value = str(o.get("value", o.get("label", i)))
            out.append(SduiChoiceOption(
                id=str(o.get("id", value)),
                label=str(o.get("label", o.get("value", f"选项 {i + 1}"))),
                value=value,
                description=o.get("description"),
            ))
        else:
            out.append(SduiChoiceOption(id=str(i), label=str(o), value=str(o)))
    return out
