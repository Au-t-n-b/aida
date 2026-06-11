'use client';

import type { ReactNode } from 'react';
import { cn } from '../../../lib/cn';

export type ProposalKpiBannerProps = {
  label?: string;
  value: ReactNode;
  hint?: ReactNode;
  className?: string;
  children?: ReactNode;
};

/** 合同金额、节点规模等关键 KPI 高亮条 */
export function ProposalKpiBanner({
  label,
  value,
  hint,
  className,
  children,
}: ProposalKpiBannerProps) {
  return (
    <div
      className={cn(
        'mb-4 rounded-lg border border-blue-100 bg-blue-50/40 px-4 py-3',
        className,
      )}
      role="group"
      aria-label={label}
    >
      {label && (
        <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
          {label}
        </div>
      )}
      <div className="mt-0.5 break-words text-xl font-bold tabular-nums text-blue-600">
        {value}
      </div>
      {hint && (
        <div className="mt-1 break-words text-xs text-slate-500">{hint}</div>
      )}
      {children}
    </div>
  );
}

export function ProposalKpiRow({
  items,
  className,
}: {
  items: { label: string; value: ReactNode; key?: string }[];
  className?: string;
}) {
  return (
    <div
      className={cn(
        'mb-4 flex flex-wrap gap-4 rounded-lg border border-blue-100 bg-blue-50/40 px-4 py-3',
        className,
      )}
    >
      {items.map((item, i) => (
        <div key={item.key ?? item.label ?? String(i)} className="min-w-0">
          <div className="text-xs font-medium text-slate-500">{item.label}</div>
          <div className="break-words text-xl font-bold tabular-nums text-blue-600">
            {item.value}
          </div>
        </div>
      ))}
    </div>
  );
}
