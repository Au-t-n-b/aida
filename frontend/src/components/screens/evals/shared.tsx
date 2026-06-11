/* 评测中心 · 三 tab 共享层：类型 / 颜色 token / 格式化 helper / 偏离导出 */
import type { ReactNode } from 'react';

// 与 useSduiStream 同源：服务器部署时通过 VITE_AGENT_BASE 注入
export const API_BASE = import.meta.env.VITE_AGENT_BASE || 'http://127.0.0.1:7401';
// 混合模式：trace 明细深链接跳 Langfuse 原生（host 后续从后端 report 返回，这里先占位）
export const LANGFUSE_HOST = 'https://cloud.langfuse.com';

// ─── 颜色 token（取自 globals.css）───
export const C = {
  brand:   '#3551d8',
  success: '#0f9d58',
  warning: '#d97706',
  danger:  '#dc2626',
  info:    '#2563eb',
  violet:  '#8b5cf6',
  border:  '#e3e8ef',
  muted:   '#64748b',
} as const;

export const PALETTE = [C.brand, C.success, C.warning, C.violet, C.info, C.danger];

// zhgk 4 step（真实 key + 中文名 + 配色）
export const STEP_META = [
  { key: 'scene_filter', label: '场景选择', color: C.brand },
  { key: 'survey_build', label: '勘测汇总', color: C.success },
  { key: 'report_gen',   label: '评估报告', color: C.warning },
  { key: 'distribute',   label: '审批分发', color: C.violet },
] as const;

// Recharts 通用样式
export const tickStyle = { fontSize: 10, fill: C.muted, fontFamily: 'var(--font-mono)' };
export const tooltipStyle = { fontSize: 11, borderRadius: 6, borderColor: C.border } as const;

// ─── 类型 ───

export interface EvalCheck { name: string; pass: boolean; detail: string; }

export interface EvalRun {
  skill: string;
  evaluated_at: string;
  quality_score: number;
  success: boolean;
  cost_cny: number | null;
  latency_ms: number | null;
  metrics: Record<string, number | null>;
  checks: EvalCheck[];
  run_id?: string;
  trace_id?: string;
  metrics_source?: string;
  step_durations?: Record<string, number>;  // step→ms（v1.5 从 Langfuse span 拉）
  step_status?: Record<string, string>;      // 漏斗图用
  empty_by_type?: Record<string, number>;    // 完成度构成环图用
}

export interface EvalSummary {
  quality_avg: number | null;
  success_rate: number;
  success_count: number;
  total: number;
  latest_quality: number | null;
  latest_success: boolean | null;
  latest_cost_cny: number | null;
  latest_latency_ms: number | null;
  latency_p50: number | null;
}

export interface EvalReport {
  skill: string;
  total: number;
  summary: EvalSummary;
  runs: EvalRun[];
  run?: EvalRun | null;
  mode?: 'latest' | 'overview';
  summary_latest?: Partial<EvalRun> & { metrics_source?: string };
  source?: 'live' | 'mock';
}

export type EvalViewMode = 'latest' | 'overview';

// 工具测评
export interface ToolRecord {
  tool: string;
  ok: boolean;
  latency_ms: number;
  scope: string;
  step?: string;
  run_id?: string;
  conv_id?: string;
  ts?: string;
  error?: string;
}

export interface ToolCheck {
  tool?: string;
  name: string;
  pass: boolean;
  detail: string;
}

export interface ToolsReport {
  mode?: EvalViewMode;
  total: number;
  evaluated_at?: string;
  source: string;
  conv_id?: string;
  run_id?: string;
  window?: string;
  record_count?: number;
  summary: {
    tool_count?: number;
    calls?: number;
    self_correction_rate_avg?: number;
    flagged_count?: number;
    quality_score?: number;
    success?: boolean;
  };
  tools: ToolMetric[];
  records?: ToolRecord[];
  checks?: ToolCheck[];
  history?: Array<{
    evaluated_at?: string;
    source?: string;
    quality_score?: number;
    success?: boolean;
    calls?: number;
  }>;
}

export interface ToolMetric {
  name: string;
  type: string;            // 会话 / 副作用·外发 / 控制·HITL / skill-as-tool
  scope: string;           // default / skill:zhgk
  calls: number;
  self_correct_rate: number;  // 自纠率（核心体检项）
  success_rate: number;
  latency_p50: number;
  latency_p95: number;
}

// Langfuse 大盘
export interface ObsCostRow { date: string; [model: string]: number | string; }
export interface ObsModelShare { name: string; cost: number; calls: number; }
export interface ObsTokenRow { date: string; input: number; output: number; }
export interface ObsLatencyBin { range: string; count: number; }
export interface ObsTrace {
  trace_id: string; name: string; cost_cny: number;
  latency_ms: number; model: string; ts: string;
}
export interface ObsData {
  kpi: { cost_cny: number; tokens: number; runs: number; avg_latency_ms: number };
  models: string[];           // cost_by_day 里的模型 key
  cost_by_day: ObsCostRow[];
  model_share: ObsModelShare[];
  token_trend: ObsTokenRow[];
  latency_hist: ObsLatencyBin[];
  traces: ObsTrace[];
}

// ─── 格式化 ───

export function fmtTs(iso: string): string {
  try {
    const d = new Date(iso);
    const p = (n: number) => String(n).padStart(2, '0');
    return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
  } catch {
    return iso.slice(0, 16);
  }
}

export function fmtLatency(ms: number | null): string {
  if (ms == null) return '—';
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}

export function fmtCost(cny: number | null): string {
  if (cny == null) return '—';
  return `¥${cny.toFixed(4)}`;
}

/** Recharts 3.x Tooltip formatter 类型适配：业务侧只写 (v:number)=>…，吃下 ValueType 兼容性 */
export function fmt(fn: (v: number, n?: string) => ReactNode) {
  return (v: unknown, n?: unknown): ReactNode =>
    fn(typeof v === 'number' ? v : Number(v), typeof n === 'string' ? n : undefined);
}

export function qualityTone(q: number | null): string {
  if (q == null) return '';
  if (q >= 0.9) return 'green';
  if (q >= 0.6) return 'amber';
  return 'red';
}

export function pickColor(i: number): string {
  return PALETTE[i % PALETTE.length] ?? C.brand;
}

// ─── 偏离导出（METRICS.md §7 · 喂 CC/Cursor）───

export function buildDeviations(runs: EvalRun[]): object {
  if (runs.length < 2) {
    return { skill: runs[0]?.skill ?? 'zhgk', note: '需要至少 2 次评测才能计算偏离', runs: runs.length };
  }
  const latest = runs[0]!;
  const baseline = runs[runs.length - 1]!;
  const deviations: object[] = [];

  if (baseline.quality_score != null && latest.quality_score != null
      && latest.quality_score < baseline.quality_score) {
    deviations.push({
      target: 'skill:overall', metric: 'quality_score',
      baseline: baseline.quality_score, current: latest.quality_score,
      delta: `${((latest.quality_score - baseline.quality_score) * 100).toFixed(1)}%`,
    });
  }
  if (baseline.latency_ms && latest.latency_ms && latest.latency_ms > baseline.latency_ms * 1.2) {
    deviations.push({
      target: 'skill:overall', metric: 'latency_ms',
      baseline: baseline.latency_ms, current: latest.latency_ms,
      delta: `+${(((latest.latency_ms - baseline.latency_ms) / baseline.latency_ms) * 100).toFixed(0)}%`,
    });
  }
  for (const c of latest.checks ?? []) {
    if (!c.pass) deviations.push({ target: `check:${c.name}`, metric: 'pass', value: false, detail: c.detail });
  }

  return {
    skill: latest.skill,
    prompt: '以下是该 skill 的评测偏离项，结合 skills/<skill> 源码，指出每个偏离的根因与具体改法（改 prompt / 改 schema / 拆 step / 加缓存），按 ROI 排序。',
    trend: {
      quality_score: runs.slice(0, 10).reverse().map(r => r.quality_score),
      latency_ms:    runs.slice(0, 10).reverse().map(r => r.latency_ms),
    },
    deviations,
  };
}

// 工具偏离导出（自纠率超阈值的工具 → 喂 AI 改 description/schema）
export function buildToolDeviations(tools: ToolMetric[], threshold = 0.15): object {
  const flagged = tools
    .filter(t => t.self_correct_rate > threshold)
    .sort((a, b) => b.self_correct_rate - a.self_correct_rate)
    .map(t => ({
      target: `tool:${t.name}`, scope: t.scope,
      metric: '自纠率', value: t.self_correct_rate, threshold,
      calls: t.calls,
    }));
  return {
    prompt: '以下工具的自纠率超阈值，说明模型常因 description/parameters 不清而调用失败重试。结合 agent/tools/<name>.py，给出每个工具 description 与 JSON Schema 的具体改法，按调用热度×自纠率（影响面）排序。',
    threshold,
    flagged,
  };
}
