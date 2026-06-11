'use client';

import type { ReactNode, TableHTMLAttributes } from 'react';
import { cn } from '../../../lib/cn';

const TABLE_BASE = 'tbl-light w-full min-w-full text-sm';
const HEAD_ROW =
  '[&_th]:bg-slate-50 [&_th]:text-slate-600 [&_th]:text-xs [&_th]:font-semibold [&_th]:uppercase [&_th]:tracking-wide [&_th]:px-3 [&_th]:py-2.5 [&_th]:text-left [&_th]:border-b [&_th]:border-slate-200/80';
const HEAD_NUM =
  '[&_th.num]:text-right [&_th.text-right]:text-right';
const BODY_ROW =
  '[&_td]:px-3 [&_td]:py-2 [&_td]:align-middle [&_td]:border-b [&_td]:border-slate-100 [&_td]:break-words [&_td]:min-w-0';
const BODY_NUM =
  '[&_td.num]:text-right [&_td.text-right]:text-right [&_td.num]:font-semibold [&_td.num]:tabular-nums';

export type ProposalDataTableProps = TableHTMLAttributes<HTMLTableElement> & {
  wrapClassName?: string;
  compact?: boolean;
  /** 各列等宽 + table-layout: fixed */
  equalCols?: boolean;
  /** 覆盖 .num 右对齐，表头与单元格统一左对齐 */
  leftAlign?: boolean;
};

/**
 * BOQ / 部件 / 风险等表格外壳
 * 数量/金额列请为 th/td 添加 className="num"
 */
export function ProposalDataTable({
  children,
  className,
  wrapClassName,
  compact = false,
  equalCols = false,
  leftAlign = false,
  ...tableProps
}: ProposalDataTableProps) {
  return (
    <div
      className={cn(
        'proposal-data-table-wrap overflow-x-auto rounded-lg border border-slate-200/80 bg-white',
        wrapClassName,
      )}
    >
      <table
        className={cn(
          TABLE_BASE,
          compact && 'text-xs',
          equalCols && 'proposal-table-equal',
          leftAlign && 'proposal-table-left',
          className,
        )}
        {...tableProps}
      >
        {children}
      </table>
    </div>
  );
}

export function ProposalDataTableHead({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <thead className={cn(HEAD_ROW, HEAD_NUM, className)}>
      {children}
    </thead>
  );
}

export function ProposalDataTableBody({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <tbody className={cn(BODY_ROW, BODY_NUM, className)}>
      {children}
    </tbody>
  );
}
