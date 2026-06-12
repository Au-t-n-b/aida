/** 部署调测 · 左侧对话自然语言 → 调度意图（/module/deploy） */

import type { SduiDocument } from '@/lib/sdui';
import { findNodeById } from '@/lib/sdui';

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

export function commissionStepLabel(step: string): string {
  return COMMISSION_STEP_LABELS[step] ?? step;
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

/** 从 SDUI 判断某调测命令是否已落地（按钮变「重新执行」或出现错误条） */
export function isCommissionStepSettledInDoc(doc: SduiDocument, stepKey: string): boolean {
  if (findNodeById(doc.root, 'sd-error-banner')) return true;
  const btn = findNodeById(doc.root, commissionButtonId(stepKey));
  if (btn?.type === 'Button') {
    const label = String(btn.label);
    if (label.startsWith('重新执行') || label.startsWith('重新生成')) return true;
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
