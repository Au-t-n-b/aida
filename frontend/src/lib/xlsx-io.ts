/**
 * 交付预案 · xlsx 行映射 + 表格 IO
 * 主写入已迁移至 proposal-api saveDraft；writeTableSlot 仅保留兼容导入场景。
 */
import type {
  AcceptanceItem,
  AcceptanceTestCase,
  PlanActivity,
  RaciRow,
  SavedTestCaseRow,
} from '@/types/domain';
import type { ProjectDataContext } from '@/lib/datacenter/client';
import {
  parseTechProposalUpload,
  parseTestcasesUpload,
  readProposalTable,
  writeProposalTable,
} from '@/lib/datacenter/client';

export type { ProjectDataContext };

export function asRaciRows(rows: unknown[]): RaciRow[] {
  return rows.map((r) => {
    const o = r as Record<string, string>;
    return {
      stack: o.stack ?? '',
      cat: o.cat ?? '',
      act: o.act ?? '',
      gts: o.gts ?? '',
      hw: o.hw ?? '',
      partner: o.partner ?? '',
      customer: o.customer ?? '',
    };
  });
}

export function asPlanActivities(rows: unknown[]): PlanActivity[] {
  return rows.map((r) => {
    const o = r as Record<string, unknown>;
    const progress = Number(o.progress ?? 0);
    return {
      name: String(o.name ?? ''),
      start: String(o.start ?? ''),
      end: String(o.end ?? ''),
      actualStart: String(o.actualStart ?? ''),
      actualEnd: String(o.actualEnd ?? ''),
      owner: String(o.owner ?? ''),
      unit: String(o.unit ?? ''),
      status: String(o.status ?? ''),
      progress: Number.isFinite(progress) ? progress : 0,
      progressTone: (o.progressTone as PlanActivity['progressTone']) ?? (progress >= 100 ? 'green' : 'blue'),
    };
  });
}

export function asAcceptanceItems(rows: unknown[]): AcceptanceItem[] {
  return rows.map((r) => {
    const o = r as Record<string, string>;
    return {
      cat: o.cat ?? '',
      scheme: o.scheme ?? '',
      standard: o.standard ?? '',
      milestone: o.milestone ?? '',
      doc: o.doc ?? '',
      payment: o.payment ?? '',
      paymentMilestone: o.paymentMilestone ?? '',
    };
  });
}

export function asTestCases(rows: unknown[]): AcceptanceTestCase[] {
  return rows.map((r) => {
    const o = r as Record<string, unknown>;
    return {
      id: String(o.id ?? ''),
      l1: String(o.l1 ?? ''),
      l2: String(o.l2 ?? ''),
      l3: String(o.l3 ?? ''),
      purpose: String(o.purpose ?? ''),
      topology: String(o.topology ?? ''),
      pre: String(o.pre ?? ''),
      steps: Array.isArray(o.steps) ? (o.steps as string[]) : [],
      expects: Array.isArray(o.expects) ? (o.expects as string[]) : [],
      result: String(o.result ?? ''),
      remark: String(o.remark ?? ''),
    };
  });
}

export async function fetchTableSlot(ctx: ProjectDataContext, slot: Parameters<typeof readProposalTable>[1]) {
  return readProposalTable(ctx, slot);
}

export async function writeTableSlot(
  ctx: ProjectDataContext,
  slot: 'raci_out' | 'acceptance_out' | 'testcases_out',
  kind: 'raci' | 'acceptance' | 'testcases',
  _projectName: string,
  version: number,
  rows: RaciRow[] | AcceptanceItem[] | SavedTestCaseRow[],
) {
  /** @deprecated 请使用 proposal-api saveDraft；兼容旧脚本/导入仍可调 writeProposalTable */
  return writeProposalTable(ctx, slot, kind, rows, version);
}

export { parseTechProposalUpload, parseTestcasesUpload };
