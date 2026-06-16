/** 部署调测 · 左侧对话自然语言 → 调度意图（/module/deploy） */

import type { SduiDocument, SduiNode } from '@/lib/sdui';
import { findNodeById } from '@/lib/sdui';
import { latestStepRecord, type RunStatusSnapshot } from '@/hooks/useSduiStream';

export type CommissionIntent =
  | { kind: 'start_commission' }
  | { kind: 'run_step'; step: string; rerun?: boolean; scope?: string };

export const COMMISSION_STEP_LABELS: Record<string, string> = {
  connection: '服务器连线检查',
  lq_connection: '灵衢连线检查',
  weak_light: '服务器弱光检查',
  hccs_weak_light: '灵衢光链路检查',
  commission_report: '调测报告汇总',
};

export const SD_LINEAR_STEP_LABELS: Record<string, string> = {
  plan_receive: '接收二级任务',
  plan_split: '拆分调测计划',
  plan_dispatch: '下发设备底表',
  cloudops_init: 'CloudOps 初配',
  cloudops_supplement: 'CloudOps 补充',
  cloudops_full: 'CloudOps 完整配置',
  toolkit_executor: '配置调测设备',
  toolkit_import: '导入 Toolkit',
};

export function commissionStepLabel(step: string): string {
  return COMMISSION_STEP_LABELS[step] ?? step;
}

export function sdStepLabel(step: string): string {
  return SD_LINEAR_STEP_LABELS[step] ?? commissionStepLabel(step);
}

export function formatCommissionScope(scope?: string): string {
  const s = (scope || 'all').trim().toLowerCase();
  if (!s || s === 'all') return '全量（all）';
  return s.toUpperCase();
}

function nowTs(): string {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

/** 左侧会话框进度提示（与 ClawRail aida:progress 对齐） */
export function emitCommissionProgress(body: string): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent('aida:progress', {
    detail: { role: 'ai', body, ts: nowTs() },
  }));
}

function commissionButtonId(stepKey: string): string {
  return stepKey === 'commission_report' ? 'sd-cmd-report' : `sd-cmd-${stepKey}`;
}

function stepOkMetricKey(stepKey: string): string {
  return `${stepKey}_ok`;
}

/** 从 /status 快照判断命令调测单步是否已落地（不依赖 SDUI 按钮投影）。 */
export function isCommissionStepSettledInStatus(
  state: RunStatusSnapshot | null | undefined,
  stepKey: string,
): boolean {
  if (!state) return false;
  const rec = latestStepRecord(state.steps, stepKey);
  if (rec?.status === 'completed' || rec?.status === 'failed') return true;
  const metrics = rec?.metrics;
  if (metrics && metrics[stepOkMetricKey(stepKey)] === true) return true;
  for (const s of state.steps ?? []) {
    const m = s.metrics;
    if (m && m[stepOkMetricKey(stepKey)] === true) return true;
  }
  return false;
}

/** 从 SDUI 判断某调测命令是否已落地（按钮变「重新执行」、任务记录表、或本步 metrics）。 */
export function isCommissionStepSettledInDoc(doc: SduiDocument, stepKey: string): boolean {
  const btn = findNodeById(doc.root, commissionButtonId(stepKey));
  if (btn?.type === 'Button') {
    const label = String(btn.label);
    if (label.startsWith('重新执行') || label.startsWith('重新生成')) return true;
  }
  const md = findNodeById(doc.root, 'sd-step-detail-md');
  if (md?.type === 'Markdown') {
    const content = String(md.content || '');
    if (new RegExp(`\`${stepOkMetricKey(stepKey)}\`:\\s*true`, 'i').test(content)) return true;
    if (
      /\*\*状态\*\*[：:]\s*completed/.test(content)
      && (content.includes(`\`${stepKey}\``) || content.includes(stepKey))
    ) {
      return true;
    }
    if (/\*\*状态\*\*[：:]\s*failed/.test(content) && content.includes(stepKey)) return true;
  }
  const table = findNodeById(doc.root, 'sd-task-log-table');
  if (table?.type === 'DataTable') {
    const label = COMMISSION_STEP_LABELS[stepKey] ?? stepKey;
    const hit = (table.rows as unknown[]).find((r): r is Record<string, unknown> => {
      if (Array.isArray(r) || typeof r !== 'object' || r === null) return false;
      const row = r as Record<string, unknown>;
      return String(row.id) === stepKey || String(row.taskType || '').includes(label);
    });
    if (hit && /已完成|失败/.test(String(hit.status || ''))) return true;
  }
  if (stepKey === 'commission_report' && findNodeById(doc.root, 'sd-report-download')) return true;
  const kpi = findNodeById(doc.root, 'sd-kpis');
  if (kpi?.type === 'StatisticRow') {
    const report = kpi.items.find(i => i.title === '调测报告');
    if (stepKey === 'commission_report' && report && String(report.value).includes('已生成')) return true;
  }
  return false;
}

export function resolveCommissionButtonStepKey(btnId: string): string | null {
  if (btnId === 'sd-cmd-report') return 'commission_report';
  if (btnId.startsWith('sd-cmd-')) return btnId.slice('sd-cmd-'.length);
  return null;
}

export function readReportArtifactPath(doc: SduiDocument): string | null {
  const grid = findNodeById(doc.root, 'sd-report-artifact');
  if (grid?.type === 'ArtifactGrid' && grid.artifacts?.[0]?.path) {
    return String(grid.artifacts[0].path);
  }
  return null;
}

export function readCommissionKpi(doc: SduiDocument): string | null {
  const kpi = findNodeById(doc.root, 'sd-kpis');
  if (kpi?.type !== 'StatisticRow') return null;
  const item = kpi.items.find(i => i.title === '命令调测');
  return item ? String(item.value) : null;
}

/** 从右侧「当前步骤」卡提取失败原因（后端 rec.error / state.error 已投影到此）。 */
export function readStepDetailError(doc: SduiDocument): string | null {
  const md = findNodeById(doc.root, 'sd-step-detail-md');
  if (md?.type !== 'Markdown') return null;
  const content = String(md.content || '');
  const err = content.match(/\*\*错误\*\*[：:]\s*(.+)/);
  if (err?.[1]?.trim()) return err[1].trim();
  const runErr = content.match(/\*\*运行错误\*\*[：:]\s*(.+)/);
  return runErr?.[1]?.trim() || null;
}

/** Toolkit 导入完成且命令调测工作台已就绪（步骤 8 → 9 衔接信号）。 */
export function isToolkitHubReadyInDoc(doc: SduiDocument): boolean {
  return Boolean(findNodeById(doc.root, 'sd-commission-panel'));
}

/** 从 /status 判断 Toolkit 导入（toolkit_import）是否已落地。 */
export function isToolkitImportSettledInStatus(
  state: RunStatusSnapshot | null | undefined,
): boolean {
  if (!state) return false;
  const rec = latestStepRecord(state.steps, 'toolkit_import');
  if (rec?.status === 'completed' || rec?.status === 'failed') return true;
  const m = rec?.metrics;
  if (m && m.toolkit_imported === true) return true;
  if (m && m.refreshed_devices != null && Number(m.refreshed_devices) > 0) return true;
  for (const s of state.steps ?? []) {
    const sm = s.metrics;
    if (!sm) continue;
    if (sm.toolkit_imported === true) return true;
    if (s.key === 'toolkit_import' && sm.refreshed_devices != null && Number(sm.refreshed_devices) > 0) {
      return true;
    }
  }
  return false;
}

/** 从 SDUI 判断 Toolkit 导入是否已完成（含命令调测调度区出现）。 */
export function isToolkitImportSettledInDoc(doc: SduiDocument): boolean {
  if (isToolkitHubReadyInDoc(doc)) return true;
  const md = findNodeById(doc.root, 'sd-step-detail-md');
  if (md?.type === 'Markdown') {
    const content = String(md.content || '');
    if (content.includes('`toolkit_import`') && /\*\*状态\*\*[：:]\s*completed/.test(content)) {
      return true;
    }
    if (/`toolkit_imported`:\s*true/i.test(content)) return true;
  }
  const kpi = findNodeById(doc.root, 'sd-kpis');
  if (kpi?.type === 'StatisticRow') {
    const tk = kpi.items.find(i => i.title === 'Toolkit');
    const val = tk ? String(tk.value) : '';
    if (val && val !== '—' && val !== '0') return true;
  }
  return false;
}

export function isStepFailedInDoc(doc: SduiDocument): boolean {
  if (findNodeById(doc.root, 'sd-error-banner')) return true;
  const md = findNodeById(doc.root, 'sd-step-detail-md');
  if (md?.type !== 'Markdown') return false;
  const content = String(md.content || '');
  return /\*\*状态\*\*[：:]\s*failed/.test(content) || /\*\*错误\*\*/.test(content);
}

export interface CommissionRecordView {
  stepKey?: string;
  taskType?: string;
  taskName?: string;
  deviceCount?: string;
  status?: string;
  resultDir?: string;
  errorMessage?: string;
  summaryRows?: string[][];
}

function asRecord(raw: unknown): CommissionRecordView | null {
  if (!raw || typeof raw !== 'object') return null;
  const r = raw as Record<string, unknown>;
  const rows = r.summaryRows;
  return {
    stepKey: String(r.stepKey ?? ''),
    taskType: String(r.taskType ?? ''),
    taskName: String(r.taskName ?? ''),
    deviceCount: String(r.deviceCount ?? ''),
    status: String(r.status ?? ''),
    resultDir: String(r.resultDir ?? ''),
    errorMessage: String(r.errorMessage ?? ''),
    summaryRows: Array.isArray(rows)
      ? rows.filter(Array.isArray).map(row => row.map(cell => String(cell ?? '')))
      : [],
  };
}

/** 从 /status 读取 pending_command 与范围摘要。 */
export function readCommissionProject(
  st: RunStatusSnapshot | null | undefined,
): { pendingCommand: string; summary: string; phase: string } {
  const project = (st?.project ?? {}) as Record<string, unknown>;
  const comm = (project.commission ?? {}) as Record<string, unknown>;
  return {
    pendingCommand: String(comm.pending_command ?? '').trim(),
    summary: String(comm.summary ?? '').trim(),
    phase: String(comm.phase ?? '').trim(),
  };
}

export function readCommissionRecordFromStatus(
  st: RunStatusSnapshot | null | undefined,
  stepKey: string,
): CommissionRecordView | null {
  if (!st) return null;
  const rec = latestStepRecord(st.steps, stepKey);
  const fromRec = asRecord(rec?.metrics?.commission_record);
  if (fromRec) return fromRec;
  for (const s of st.steps ?? []) {
    const m = s.metrics;
    if (m && String(m.command ?? '') === stepKey) {
      const hit = asRecord(m.commission_record);
      if (hit) return hit;
    }
    if (s.key === stepKey && m?.commission_record) {
      return asRecord(m.commission_record);
    }
  }
  return null;
}

/** SDUI 任务记录表行 → 简要记录视图。 */
export function readCommissionRecordFromDoc(
  doc: SduiDocument | null,
  stepKey: string,
): CommissionRecordView | null {
  if (!doc) return null;
  const table = findNodeById(doc.root, 'sd-task-log-table');
  if (table?.type !== 'DataTable') return null;
  const label = COMMISSION_STEP_LABELS[stepKey] ?? stepKey;
  const hit = (table.rows as unknown[]).find((r): r is Record<string, unknown> => {
    if (!r || typeof r !== 'object') return false;
    const row = r as Record<string, unknown>;
    return String(row.id) === stepKey || String(row.taskType || '').includes(label);
  });
  if (!hit) return null;
  return {
    stepKey,
    taskType: String(hit.taskType ?? label),
    taskName: String(hit.taskName ?? hit.id ?? stepKey),
    deviceCount: String(hit.deviceCount ?? '—'),
    status: String(hit.status ?? ''),
    resultDir: String(hit.resultDir ?? ''),
    errorMessage: String(hit.errorMessage ?? ''),
  };
}

export function formatCommissionResultChat(
  label: string,
  opts: {
    scopeSummary?: string;
    record?: CommissionRecordView | null;
    isError?: boolean;
    errorMessage?: string;
    kpi?: string | null;
  },
): string {
  const lines: string[] = [];
  const status = opts.isError
    ? '失败'
    : (opts.record?.status || '已完成');
  lines.push(`「${label}」${opts.isError ? '执行失败' : '执行完成'}`);
  if (opts.scopeSummary) lines.push(`· 范围：${opts.scopeSummary}`);
  if (opts.record?.deviceCount && opts.record.deviceCount !== '—') {
    lines.push(`· 设备：${opts.record.deviceCount} 台`);
  }
  if (opts.record?.taskName && opts.record.taskName !== '—') {
    lines.push(`· 任务：${opts.record.taskName}`);
  }
  lines.push(`· 状态：${status}`);
  if (opts.record?.resultDir) {
    const dir = opts.record.resultDir.replace(/\\/g, '/');
    lines.push(`· 结果目录：${dir}`);
  }
  if (opts.record?.summaryRows?.length) {
    const row = opts.record.summaryRows[0];
    if (row && row.length >= 3) {
      lines.push(`· 抽检：${row[0]} / 光口 ${row[1]} / 设备 ${row[2]}`);
    }
  }
  if (opts.kpi) lines.push(`· 进度：命令调测 ${opts.kpi}`);
  const err = opts.errorMessage || opts.record?.errorMessage;
  if (err) lines.push(`· 原因：${err}`);
  return lines.join('\n');
}

export function isScopeConfirmInDoc(doc: SduiDocument): boolean {
  let found = false;
  const walk = (node: SduiNode): void => {
    if (found || !node) return;
    if (node.type === 'ChoiceCard') {
      const raw = node as { stepId?: string; hitlRequestId?: string };
      const sid = String(raw.stepId || raw.hitlRequestId || '');
      if (sid === 'commission_scope') found = true;
      return;
    }
    const children = (node as { children?: SduiNode[] }).children;
    children?.forEach(walk);
  };
  walk(doc.root);
  return found;
}

const RULES: Array<{
  re: RegExp;
  step?: string;
  start?: boolean;
}> = [
  { re: /直接进入命令调测|直达.*调测|进入命令调测/, start: true },
  { re: /(?:重新)?(?:执行|跑|做).*(?:服务器连线|连线检查)(?!.*灵衢)/, step: 'connection' },
  { re: /(?:重新)?(?:执行|跑|做).*灵衢连线/, step: 'lq_connection' },
  { re: /(?:重新)?(?:执行|跑|做).*(?:服务器弱光|弱光检查)/, step: 'weak_light' },
  { re: /(?:重新)?(?:执行|跑|做).*(?:灵衢光链|光链路)/, step: 'hccs_weak_light' },
  { re: /生成.*调测报告|调测报告汇总/, step: 'commission_report' },
];

function extractScope(text: string): string | undefined {
  const m = text.match(/pod\s*([0-9A-Za-z_-]+)/i);
  if (m?.[1]) return `pod${m[1]}`.toLowerCase();
  return undefined;
}

export function parseCommissionIntent(text: string): CommissionIntent | null {
  const t = text.trim();
  if (!t) return null;
  for (const rule of RULES) {
    if (!rule.re.test(t)) continue;
    if (rule.start) return { kind: 'start_commission' };
    if (rule.step) {
      return {
        kind: 'run_step',
        step: rule.step,
        rerun: /重新|再测|再执行|反复/.test(t),
        scope: extractScope(t),
      };
    }
  }
  return null;
}
