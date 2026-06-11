/**
 * ZhgkState · 智慧工勘读契约 v1（FROZEN · 2026-06-02）
 * ────────────────────────────────────────────────────────
 * 右侧面板 = render(ZhgkState) 的纯函数。
 * 数据来源：数据中心 runs/{runId}/state.json（首屏读）+ 运行中 SSE 推增量（同一形状）。
 * 后端由 SkillState 投影而来 —— 投影规则见 aida-datacenter/skills/zhgk/CONTRACT.md。
 *
 * ⚠ 两处语义为「提案·待业务确认」，已用 @confirm 标注（metrics.dataIntegrity / openIssues）。
 */

export type ZhgkStatus = 'idle' | 'running' | 'paused' | 'done' | 'failed';
export type ZhgkStepStatus = 'pending' | 'running' | 'completed' | 'failed' | 'hitl';
export type ZhgkStepKey = 'scene_filter' | 'survey_build' | 'report_gen' | 'report_distribute';
export type ZhgkAlertLevel = 'high' | 'medium' | 'low';

export interface ZhgkStep {
  key: ZhgkStepKey;
  name: string;
  status: ZhgkStepStatus;
  /** 0–100 */
  progress: number;
}

export interface ZhgkMetrics {
  /** 勘测完成度 = filled_items / total_items × 100。整体勘测项填充率。 */
  surveyCompletion: number;
  /**
   * 数据完整率 = mandatory_filled / mandatory_total × 100。强制项完成率。
   * @confirm 提案：仅统计「强制项」，以区别于 surveyCompletion 的全项口径。待业务确认。
   */
  dataIntegrity: number;
  /**
   * 遗留问题数 = Σ empty_by_type（待客户确认 + 待拍摄图片 + 待补充勘测）。
   * @confirm 提案：三类待办总数。若「待拍摄」不算问题，可改为仅前两类。待业务确认。
   */
  openIssues: number;
}

/** 结构化风险 —— 需 report_gen 补吐（审计 B2）。当前后端只产 xlsx，无此 JSON。 */
export interface ZhgkAlert {
  id: string;
  level: ZhgkAlertLevel;
  /** 风险描述（标题） */
  title: string;
  /** 类别：供电 / 承重 / 制冷 / 网络 / … */
  category?: string;
  /** 关联机房或 PoD */
  room?: string;
  detail?: string;
  /** 建议措施 */
  recommendation?: string;
  source: 'report_gen' | 'survey_build';
}

export interface ZhgkArtifact {
  name: string;
  /** 相对 run 根目录，如 output/工勘报告.docx */
  path: string;
  step?: ZhgkStepKey;
  /** boq / presets / survey / report / … */
  kind?: string;
}

export interface ZhgkHitl {
  step: ZhgkStepKey;
  reason: string;
  /** 缺失文件名清单 */
  needFiles: string[];
  /** 需用户决策的输入 */
  needInputs?: { key: string; label: string; options?: string[] }[];
}

export interface ZhgkChartSegment {
  label: string;
  value: number;
  color?: string;
}

/** 图表区 —— 派生自 metrics + steps，可由后端投影层或前端计算。 */
export interface ZhgkCharts {
  donut: { centerLabel: string; centerValue: string; segments: ZhgkChartSegment[] };
  bar: ZhgkChartSegment[];
}

/** 智慧工勘读契约 · 右侧面板唯一数据源。 */
export interface ZhgkState {
  schemaVersion: 'v1';
  skill: 'zhgk';
  projectId: string;
  runId: string;

  status: ZhgkStatus;
  currentStep: ZhgkStepKey | null;

  steps: ZhgkStep[];
  metrics: ZhgkMetrics;
  charts: ZhgkCharts;
  alerts: ZhgkAlert[];
  inputs: ZhgkArtifact[];
  /** 产物清单以本数组为准，不扫 output/ 目录（目录有跨 run 残留）。 */
  outputs: ZhgkArtifact[];
  summary: string;
  /** 非 null 时面板弹出上传/选择卡（HITL）。 */
  hitl: ZhgkHitl | null;
}
