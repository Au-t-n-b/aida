'use client';

import type { ReactNode } from 'react';
import { cn } from '../../../lib/cn';

export type ProposalFieldRow = {
  label: string;
  value: ReactNode;
  /** 占满整行（长文本描述） */
  fullWidth?: boolean;
};

export type ProposalFieldGridProps = {
  rows: ProposalFieldRow[];
  columns?: 1 | 2;
  className?: string;
  /** 弱化样式：字段值改为浅灰、不加粗（用于客户背景等弱化场景）*/
  muted?: boolean;
};

const SHELL = 'overflow-hidden rounded-md border border-slate-100';
const LABEL_CELL = 'bg-slate-50 px-4 py-2.5 text-sm font-medium text-slate-500';
const VALUE_CELL =
  'bg-white px-4 py-2.5 text-sm font-semibold text-slate-900 break-words min-w-0';
const LABEL_CELL_MUTED = 'bg-slate-50 px-4 py-2.5 text-sm font-normal text-slate-400';
const VALUE_CELL_MUTED =
  'bg-white px-4 py-2.5 text-sm font-normal text-slate-400 break-words min-w-0';

/**
 * 键值对网格 · 标签列 / 数据列
 * 以左右底色区分，无内部分割线，避免 Excel 表格感
 */
export function ProposalFieldGrid({
  rows,
  columns = 2,
  className,
  muted = false,
}: ProposalFieldGridProps) {
  if (!rows.length) return null;

  const labelCls = muted ? LABEL_CELL_MUTED : LABEL_CELL;
  const valueCls = muted ? VALUE_CELL_MUTED : VALUE_CELL;

  if (columns === 1) {
    return (
      <div className={cn(SHELL, className)}>
        {rows.map((row) => (
          <div
            key={row.label}
            className="grid min-w-0 grid-cols-1 sm:grid-cols-[minmax(7rem,auto)_1fr]"
          >
            <div className={labelCls}>{row.label}</div>
            <div className={valueCls}>{row.value}</div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className={cn(SHELL, className)}>
      <div className="grid grid-cols-1 sm:grid-cols-2">
        {rows.map((row) => {
          if (row.fullWidth) {
            return (
              <div
                key={row.label}
                className="col-span-full grid min-w-0 grid-cols-1 sm:grid-cols-[minmax(7rem,auto)_1fr]"
              >
                <div className={labelCls}>{row.label}</div>
                <div className={valueCls}>{row.value}</div>
              </div>
            );
          }
          return (
            <div
              key={row.label}
              className="col-span-1 grid min-w-0 grid-cols-1 sm:grid-cols-[minmax(7rem,auto)_1fr]"
            >
              <div className={labelCls}>{row.label}</div>
              <div className={valueCls}>{row.value}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function ProposalFieldBlock({
  label,
  value,
  className,
}: {
  label: string;
  value: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn(SHELL, className)}>
      <div className="grid min-w-0 grid-cols-1 sm:grid-cols-[minmax(7rem,auto)_1fr]">
        <div className={LABEL_CELL}>{label}</div>
        <div className={VALUE_CELL}>{value}</div>
      </div>
    </div>
  );
}
