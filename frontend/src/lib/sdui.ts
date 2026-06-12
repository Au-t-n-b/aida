/**
 * SDUI（Skill Declarative UI）协议类型 — adapted from nanobot for aida frontend.
 * 后端 Python builder 产出 JSON → 前端 SduiNodeView 递归渲染。
 */

import { scanIllegalPresentationKeysForDev } from './sduiCompliance';

export const SDUI_SCHEMA_VERSION = 1;

export type SpacingToken = 'none' | 'xs' | 'sm' | 'md' | 'lg' | 'xl';
export type SduiSemanticColor = 'success' | 'warning' | 'error' | 'accent' | 'subtle';
export type SduiStepperStatus = 'waiting' | 'running' | 'done' | 'error';
export type SduiArtifactStatus = 'ready' | 'generating' | 'error';
export type SduiArtifactKind = 'docx' | 'xlsx' | 'pdf' | 'html' | 'json' | 'md' | 'png' | 'other';

export type SduiAction =
  | { kind: 'post_user_message'; text: string }
  | { kind: 'open_preview'; path: string }
  | { kind: 'reset_session' };

export interface SduiDataTableColumn {
  key: string;
  label: string;
  type?: 'text' | 'status' | 'progress';
  width?: number;
  editable?: boolean;
  placeholder?: string;
}

export interface SduiCardHeaderAction {
  label: string;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  action: SduiAction;
}

export type SduiDocument = {
  schemaVersion: number;
  type: 'SduiDocument';
  root: SduiNode;
  meta?: Record<string, unknown>;
};

// ── Stepper ───────────────────────────────────────────────────────────────────

export type SduiStepperStep = {
  id: string;
  title: string;
  status: SduiStepperStatus;
  detail?: string[];
};

export type SduiStepperNode = { type: 'Stepper'; id?: string; steps: SduiStepperStep[]; orientation?: 'horizontal' | 'vertical' };

// ── Artifact ──────────────────────────────────────────────────────────────────

export type SduiArtifactItem = {
  id?: string;
  label: string;
  path: string;
  kind?: SduiArtifactKind;
  status?: SduiArtifactStatus;
};

// ── Node types ────────────────────────────────────────────────────────────────

type OptId = { id?: string; flex?: number };

export type SduiStackNode    = OptId & { type: 'Stack';    gap?: SpacingToken; justify?: string; children?: SduiNode[] };
export type SduiCardNode     = OptId & { type: 'Card';     title?: string; density?: 'default' | 'compact'; children?: SduiNode[]; tone?: 'default' | 'warning' | 'danger' | 'info' | 'success'; headerAction?: SduiCardHeaderAction; collapsible?: boolean; defaultCollapsed?: boolean };
export type SduiRowNode      = OptId & { type: 'Row';      gap?: SpacingToken; align?: string; justify?: string; wrap?: boolean; children?: SduiNode[] };
export type SduiDividerNode  = OptId & { type: 'Divider'; orientation?: 'horizontal' | 'vertical'; label?: string };
export type SduiSkeletonNode = OptId & { type: 'Skeleton'; variant?: 'text' | 'rect' | 'card' | 'row'; lines?: number };

export type SduiTextNode     = OptId & { type: 'Text';     content: string; variant?: 'caption' | 'body' | 'heading' | 'mono'; color?: SduiSemanticColor; align?: string };
export type SduiMarkdownNode = OptId & { type: 'Markdown'; content: string };

export type SduiBadgeNode    = OptId & { type: 'Badge';    text: string; tone?: 'default' | 'success' | 'warning' | 'danger'; label?: string };
export type SduiStatisticNode= OptId & { type: 'Statistic'; title: string; value: string | number; color?: SduiSemanticColor };
export type SduiStatisticRowItem = { title: string; value: string | number; color?: SduiSemanticColor };
export type SduiStatisticRowNode = OptId & { type: 'StatisticRow'; items: SduiStatisticRowItem[] };

export type SduiKeyValueItem = { key: string; value: string };
export type SduiKeyValueListNode = OptId & { type: 'KeyValueList'; items: SduiKeyValueItem[] };
export type SduiTableNode    = OptId & { type: 'Table';    headers?: string[]; rows: string[][] };

export type SduiButtonNode   = OptId & { type: 'Button';   label: string; variant?: 'primary' | 'secondary' | 'ghost' | 'outline'; color?: SduiSemanticColor; action: SduiAction };
export type SduiLinkNode     = OptId & { type: 'Link';     label: string; href?: string; action?: SduiAction };

export type SduiDonutSegment = { label: string; value: number; color?: string };
export type SduiDonutChartNode = OptId & { type: 'DonutChart'; segments: SduiDonutSegment[]; centerLabel?: string; centerValue?: string };

export type SduiBarDatum     = { label: string; value: number; color?: string };
export type SduiBarChartNode = OptId & { type: 'BarChart'; data?: SduiBarDatum[] | null; valueUnit?: string };

export type SduiGoldenMetricItem = { id?: string; label?: string; value?: number | string; color?: string };
export type SduiGoldenMetricsNode = OptId & { type: 'GoldenMetrics'; metrics?: SduiGoldenMetricItem[] };

export type SduiArtifactGridNode = OptId & { type: 'ArtifactGrid'; artifacts: SduiArtifactItem[]; mode?: 'input' | 'output'; title?: string };

// ── New display nodes (v1.1) ──────────────────────────────────────────────────

/** Alert — 带 icon + tone 的横幅通知，适合展示 AI 简报、风险提示、系统消息。*/
export type SduiAlertNode = OptId & {
  type: 'Alert';
  /** 通知语义：info（默认）/ success / warning / error */
  tone?: 'info' | 'success' | 'warning' | 'error';
  /** 加粗标题（可选）*/
  title?: string;
  /** 正文内容（必填）*/
  message: string;
};

/** Timeline event item */
export type SduiTimelineEvent = {
  label: string;
  time?: string;
  /** 圆点颜色：default 灰 / success 绿 / warning 黄 / error 红 */
  tone?: 'default' | 'success' | 'warning' | 'error';
};

/** Timeline — 竖向时间轴，适合展示步骤日志、进度历史、事件流。*/
export type SduiTimelineNode = OptId & {
  type: 'Timeline';
  events: SduiTimelineEvent[];
};

/** NumberCard — 突出单个大数字 KPI，可附趋势方向（↑/↓）和辅助标签。*/
export type SduiNumberCardNode = OptId & {
  type: 'NumberCard';
  /** 主数字（字符串可含单位如 "78%"）*/
  value: string | number;
  /** 卡片下方标签 */
  label: string;
  /** 趋势字符串，如 "+12" "+5%" */
  delta?: string;
  /** 趋势方向：up=绿 / down=红 / neutral=灰 */
  deltaDir?: 'up' | 'down' | 'neutral';
  /** 数值语义色 */
  tone?: SduiSemanticColor;
};

/** PlaneMatrix 单元格：一个网络平面 + 其规划状态 */
export type SduiPlaneCell = {
  label: string;
  /** 该平面规划状态：done 绿 / running 蓝脉冲 / pending 灰 / error 红 */
  status?: 'done' | 'running' | 'pending' | 'error';
  /** 分组（如「计算面」「存储面」），同组聚拢展示 */
  group?: string;
  /** 角标说明（产物文件名 / 链路数等）*/
  note?: string;
};

/** PlaneMatrix — a3 系统设计大盘核心：N 个网络平面 × 规划状态的网格，
 * 反映跨命令累积进度（编排器型 skill 专用）。*/
export type SduiPlaneMatrixNode = OptId & {
  type: 'PlaneMatrix';
  cells: SduiPlaneCell[];
  /** 网格列数（缺省前端自适应）*/
  columns?: number;
};

// ── Business nodes ────────────────────────────────────────────────────────────

/** RiskList 一条风险：标题 + 等级 + 可选明细 */
export type SduiRiskItem = {
  title: string;
  /** 等级：high 高(红) / mid 中(琥珀) / low 低(黄) */
  level: 'high' | 'mid' | 'low';
  /** 明细（场景 / 建议 / 编号），可选 */
  detail?: string;
};

/** RiskList — 风险清单，按等级色带展示。zhgk 风险识别、评估类 skill 通用。*/
export type SduiRiskListNode = OptId & {
  type: 'RiskList';
  items: SduiRiskItem[];
  title?: string;
};

// ── Tier B nodes (v4 通用扩展) ─────────────────────────────────────────────────

/** EmptyState — 空状态占位（图标 + 标题 + 副标题）。*/
export type SduiEmptyStateNode = OptId & { type: 'EmptyState'; title: string; subtitle?: string; icon?: string };

/** Spinner — 加载 / 执行中转圈。*/
export type SduiSpinnerNode = OptId & { type: 'Spinner'; label?: string; tone?: 'default' | 'brand' };

/** ProgressBar — 进度条，value 0–100。*/
export type SduiProgressBarNode = OptId & { type: 'ProgressBar'; value: number; label?: string; tone?: 'success' | 'warning' | 'danger' };

/** Banner — 通栏横幅，比 Alert 更轻量的单行提示。*/
export type SduiBannerNode = OptId & { type: 'Banner'; message: string; title?: string; tone?: 'brand' | 'warning' };

/** CodeBlock — 代码 / 命令块（可附文件名）。*/
export type SduiCodeBlockNode = OptId & { type: 'CodeBlock'; code: string; filename?: string; language?: string };

/** LogStream — 执行日志流，语义色日志行。*/
export type SduiLogLine = { text: string; time?: string; level?: 'ok' | 'warn' | 'error' | 'info' };
export type SduiLogStreamNode = OptId & { type: 'LogStream'; lines: SduiLogLine[] };

/** Checklist — 勾选清单，完成项打勾 + 删除线。*/
export type SduiChecklistItem = { label: string; done?: boolean };
export type SduiChecklistNode = OptId & { type: 'Checklist'; items: SduiChecklistItem[] };

/** FileTree — 文件树，目录/文件层级（depth 缩进）。*/
export type SduiFileTreeItem = { name: string; type?: 'file' | 'dir'; depth?: number; tag?: string };
export type SduiFileTreeNode = OptId & { type: 'FileTree'; items: SduiFileTreeItem[] };

/** Tabs — 页签，多视图切换（content 为文本/markdown）。*/
export type SduiTabItem = { label: string; content?: string };
export type SduiTabsNode = OptId & { type: 'Tabs'; tabs: SduiTabItem[] };

/** Accordion — 手风琴，可展开/折叠的分节内容。*/
export type SduiAccordionItem = { title: string; body: string };
export type SduiAccordionNode = OptId & { type: 'Accordion'; items: SduiAccordionItem[] };

/** DataTable — 数据表格。两种形态：① 旧只读位置型（columns=string[]、rows=矩阵）；
 *  ② 新类型化/可编辑（columns=SduiDataTableColumn[]、rows=dict[]，editable 时按列 type 渲染 + 提交）。*/
export type SduiDataTableNode = OptId & {
  type: 'DataTable';
  columns: string[] | SduiDataTableColumn[];
  rows: (string | number)[][] | Record<string, unknown>[];
  title?: string;
  subtitle?: string;
  editable?: boolean;
  submitMode?: 'resume' | 'run-patch';
  submitLabel?: string;
  stepId?: string;
  rowKey?: string;
  checkKey?: string;
  fillLabel?: string;
  deselectLabel?: string;
  fillRows?: Record<string, unknown>[];
  backLabel?: string;
  backStepId?: string;
  groupKey?: string;
  groupAsTabs?: boolean;
  pageSize?: number;
  requiredKeys?: string[];
  /** Tier B 展示/编辑双模式（组件库 DataTable · 编辑/保存/取消） */
  dualMode?: boolean;
  /** dualMode 保存时 run-patch 的 action，默认 task_progress */
  patchAction?: string;
};

/** TabbedTable — 页签表格，多组表格按页签切换。*/
export type SduiTabbedTableTab = { label: string; headers?: string[]; rows: string[][] };
export type SduiTabbedTableNode = OptId & { type: 'TabbedTable'; tabs: SduiTabbedTableTab[] };

/** MultiSelect — 多选 pill（本地状态展示）。*/
export type SduiMultiSelectOption = { label: string; value?: string };
export type SduiMultiSelectNode = OptId & { type: 'MultiSelect'; options: SduiMultiSelectOption[]; title?: string };

/** Slider — 滑块，value + min/max（本地状态展示）。*/
export type SduiSliderNode = OptId & { type: 'Slider'; value: number; label?: string; min?: number; max?: number; unit?: string };

/** ConfirmDialog — 确认对话，标题 + 消息 + 确认/取消。*/
export type SduiConfirmDialogNode = OptId & { type: 'ConfirmDialog'; title: string; message?: string; confirmLabel?: string; cancelLabel?: string };

/** FormGroup — 表单组，多个 label + 输入框。*/
export type SduiFormField = { label: string; placeholder?: string; value?: string };
export type SduiFormGroupNode = OptId & { type: 'FormGroup'; fields: SduiFormField[] };

// ── Tier C nodes (v4 业务扩展) ─────────────────────────────────────────────────

/** StatusBanner — 运行态通栏，状态点 + 文本。*/
export type SduiStatusItem = { status: 'run' | 'pause' | 'fail' | 'done'; text: string };
export type SduiStatusBannerNode = OptId & { type: 'StatusBanner'; items: SduiStatusItem[] };

/** SegmentedControl — 轻量视图切换（本地状态）。*/
export type SduiSegmentedControlNode = OptId & { type: 'SegmentedControl'; segments: string[]; caption?: string };

/** VerticalStepper — 竖向步骤条，轻量。*/
export type SduiVStepItem = { label: string; status?: 'done' | 'running' | 'pending' };
export type SduiVerticalStepperNode = OptId & { type: 'VerticalStepper'; items: SduiVStepItem[] };

/** AssessmentBar — 五值评估堆叠条。*/
export type SduiAssessSegment = { label: string; value: number; color?: string };
export type SduiAssessmentBarNode = OptId & { type: 'AssessmentBar'; segments: SduiAssessSegment[]; title?: string };

/** RecipientList — 分发对象/审批链。*/
export type SduiRecipient = { name: string; role?: string; status?: string };
export type SduiRecipientListNode = OptId & { type: 'RecipientList'; items: SduiRecipient[] };

/** DiffView — 左右对比（增/删/改）。*/
export type SduiDiffRow = { left: string; right: string; change?: 'add' | 'del' | 'chg' };
export type SduiDiffViewNode = OptId & { type: 'DiffView'; rows: SduiDiffRow[]; leftTitle?: string; rightTitle?: string };

/** InlinePreview — 内嵌产物预览。*/
export type SduiInlinePreviewNode = OptId & { type: 'InlinePreview'; filename: string; placeholder?: string };

/** ImageGrid — 现场照片网格（src 有值渲染真图，否则场景占位）。*/
export type SduiImageItem = { caption: string; label?: string; src?: string };
export type SduiImageGridNode = OptId & { type: 'ImageGrid'; images: SduiImageItem[] };

/** Toast — 浮层通知（状态点 + 主文案 + 副文案）。*/
export type SduiToastNode = OptId & { type: 'Toast'; message: string; detail?: string; tone?: 'success' | 'info' | 'warning' | 'error' };

/** Sparkline — 指标迷你趋势。*/
export type SduiSparklineNode = OptId & { type: 'Sparkline'; points: number[]; label?: string; value?: string | number; delta?: string };

/** DashboardLayout — 双栏仪表盘（递归子节点）。*/
export type SduiDashboardLayoutNode = OptId & { type: 'DashboardLayout'; main: SduiNode[]; side: SduiNode[] };

/** Drawer — 侧滑详情面板（递归子节点）。*/
export type SduiDrawerNode = OptId & { type: 'Drawer'; title: string; children?: SduiNode[] };

// ── Tier D nodes (v5 业务扩展 · 交付台 / 系统设计) ──────────────────────────────

/** TabGroup 的一个页签：id + label + 可选 badge 角标 + 递归子节点。*/
export type SduiTabPanel = { id: string; label: string; badge?: string | number; children?: SduiNode[] };
/** TabGroup — 页签容器，子节点按页签分组切换（区别于只放文本的 Tabs / 只放表格的 TabbedTable）。
 *  badge 显示计数/未读角标；activeTab 给定页签 id 作为初始选中，后端可借此引导（如执行中切「进度」页）。*/
export type SduiTabGroupNode = OptId & { type: 'TabGroup'; tabs: SduiTabPanel[]; activeTab?: string };

/** InputSlotList 的一行输入件槽位。source=auto 仿真产出 / manual 人工上传。*/
export type SduiInputSlot = { label: string; source: 'auto' | 'manual'; required?: boolean; ready?: boolean; fileName?: string; previewPath?: string };
/** InputSlotList — 输入件槽位清单：必需/可选 × 自动/手动 × 就绪/缺失；缺件行高亮 + 上传 CTA，就绪行可预览，自动件未就绪显示「检查中」。*/
export type SduiInputSlotListNode = OptId & { type: 'InputSlotList'; slots: SduiInputSlot[]; title?: string };

/** TaskTimelineStrip — 任务时间规划条/迷你甘特：计划 vs 实际双轨 + 剩余天数 + 进度填充（remainingDays 逾期为负，progressPct 0–100）。*/
export type SduiTaskTimelineStripNode = OptId & { type: 'TaskTimelineStrip'; plannedStart: string; plannedEnd: string; actualStart?: string; actualEnd?: string; remainingDays?: number; progressPct?: number };

/** MacroStepRail 的一个宏观阶段：id + 标题 + 可选 hint + optional 标记 + 状态。*/
export type SduiMacroStep = { id: string; title: string; hint?: string; optional?: boolean; status?: 'done' | 'running' | 'pending' };
/** MacroStepRail — 宏观交付蓝图条（如六步 s1–s6），区别于 micro 的 Stepper：optional 阶段灰显，hint 给副提示，currentId 高亮当前。*/
export type SduiMacroStepRailNode = OptId & { type: 'MacroStepRail'; steps: SduiMacroStep[]; currentId?: string };

/** EmbeddedWeb — 内嵌网页（iframe 承载外部 Web UI，如 nVisual 仿真软件访问页）。
 *  url 必填；title 作页眉、note 作离线/加载提示；height 像素高（默认 520）；openInNewTab 给「新页打开」兜底链接。*/
export type SduiEmbeddedWebNode = OptId & { type: 'EmbeddedWeb'; url: string; title?: string; note?: string; height?: number; openInNewTab?: boolean; offline?: boolean };

// ── HITL nodes ────────────────────────────────────────────────────────────────

export type SduiFilePickerNode = OptId & {
  type: 'FilePicker';
  purpose: string;
  label?: string;
  helpText?: string;
  accept?: string;
  multiple?: boolean;
  hitlRequestId?: string;
  stepId?: string;
};

export type SduiChoiceOption = { id?: string; value?: string; label: string; description?: string };
export type SduiChoiceCardNode = OptId & {
  type: 'ChoiceCard';
  title: string;
  options: SduiChoiceOption[];
  hitlRequestId?: string;
  stepId?: string;
};

export type SduiHitlTextInputNode = OptId & {
  type: 'HitlTextInput';
  purpose?: string;
  title?: string;
  label?: string;
  placeholder?: string;
  rows?: number;
  defaultValue?: string;
  submitLabel?: string;
  helpText?: string;
  hitlRequestId?: string;
  stepId?: string;
};

export type SduiHitlFormField = {
  key: string;
  label: string;
  placeholder?: string;
  required?: boolean;
  defaultValue?: string;
};

export type SduiHitlFormNode = OptId & {
  type: 'HitlForm';
  title: string;
  fields: SduiHitlFormField[];
  payloadKey?: string;
  repeatable?: boolean;
  submitLabel?: string;
  helpText?: string;
  hitlRequestId?: string;
  stepId?: string;
};

// ── Union ─────────────────────────────────────────────────────────────────────

// MachineRoom3D — 3D 机房俯视总览（等距体素 + 机房卡片 + 多入口）
export interface SduiRoom3DEntry { key: string; label: string; icon?: string; primary?: boolean; action?: SduiAction }
export interface SduiRoom3DItemStats { surveyed: number; pending: number; unknown: number; na: number }
export interface SduiMachineRoom {
  id: string; label: string; code?: string; status?: string; progress?: number;
  rows?: number; cols?: number; racks?: number; cdu?: number;
  itemStats: SduiRoom3DItemStats;
  rackStatuses?: string[];
  statKey?: string[];
  entries?: SduiRoom3DEntry[];
}
export type SduiMachineRoom3DNode = OptId & {
  type: 'MachineRoom3D';
  eyebrow?: string; title?: string; subtitle?: string;
  headStats?: { value: string; label: string; tone?: string }[];
  rooms: SduiMachineRoom[]; refreshNote?: string;
};


export type SduiNode =
  | SduiStackNode | SduiCardNode | SduiRowNode | SduiDividerNode | SduiSkeletonNode
  | SduiStepperNode
  | SduiTextNode | SduiMarkdownNode
  | SduiBadgeNode | SduiStatisticNode | SduiStatisticRowNode
  | SduiKeyValueListNode | SduiTableNode
  | SduiButtonNode | SduiLinkNode
  | SduiDonutChartNode | SduiBarChartNode | SduiGoldenMetricsNode
  | SduiArtifactGridNode
  // v1.1 display nodes
  | SduiAlertNode | SduiTimelineNode | SduiNumberCardNode | SduiPlaneMatrixNode
  // business nodes
  | SduiRiskListNode | SduiMachineRoom3DNode
  // tier B (v4)
  | SduiEmptyStateNode | SduiSpinnerNode | SduiProgressBarNode | SduiBannerNode
  | SduiCodeBlockNode | SduiLogStreamNode | SduiChecklistNode | SduiFileTreeNode
  | SduiTabsNode | SduiAccordionNode | SduiDataTableNode | SduiTabbedTableNode
  | SduiMultiSelectNode | SduiSliderNode | SduiConfirmDialogNode | SduiFormGroupNode
  // tier C (v4 业务扩展)
  | SduiStatusBannerNode | SduiSegmentedControlNode | SduiVerticalStepperNode | SduiAssessmentBarNode
  | SduiRecipientListNode | SduiDiffViewNode | SduiInlinePreviewNode | SduiImageGridNode | SduiToastNode | SduiSparklineNode
  | SduiDashboardLayoutNode | SduiDrawerNode
  // tier D (v5 业务扩展)
  | SduiTabGroupNode | SduiInputSlotListNode | SduiTaskTimelineStripNode | SduiMacroStepRailNode
  | SduiEmbeddedWebNode
  | SduiFilePickerNode | SduiChoiceCardNode | SduiHitlTextInputNode | SduiHitlFormNode;

// ── Parsing ───────────────────────────────────────────────────────────────────

function isRecord(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === 'object' && !Array.isArray(v);
}

export function parseSduiDocument(data: unknown): { ok: true; doc: SduiDocument } | { ok: false; error: string } {
  scanIllegalPresentationKeysForDev(data);
  if (!isRecord(data)) return { ok: false, error: 'root is not an object' };
  const schemaVersion = data.schemaVersion;
  if (typeof schemaVersion !== 'number') return { ok: false, error: 'missing schemaVersion' };
  const root = data.root;
  if (!isRecord(root) || typeof (root as { type?: unknown }).type !== 'string') {
    return { ok: false, error: 'missing or invalid root node' };
  }
  return {
    ok: true,
    doc: {
      schemaVersion,
      type: 'SduiDocument',
      root: root as SduiNode,
      meta: isRecord(data.meta) ? (data.meta as Record<string, unknown>) : undefined,
    },
  };
}
