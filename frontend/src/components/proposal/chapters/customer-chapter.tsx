'use client';

import { useEffect, useState } from 'react';
import { ProposalChapterCard } from '../primitives';
import { PROJECT_BACKGROUND } from '../proposal-data';

const BACKGROUND_ROWS = (b: typeof PROJECT_BACKGROUND) => [
  { key: 'background', label: '客户项目背景', value: b.background },
  { key: 'goal', label: '客户项目目标', value: b.goal },
  { key: 'scope', label: '客户项目范围', value: b.scope },
  { key: 'plan', label: '客户项目计划', value: b.planSummary },
];

interface CustomerChapterProps {
  initialRows?: unknown;
  readOnly?: boolean;
  onRowsChange?: (rows: Array<Record<string, string>>) => void;
}

function _normalizeRows(input: unknown) {
  if (!Array.isArray(input) || input.length === 0) {
    return BACKGROUND_ROWS(PROJECT_BACKGROUND);
  }
  const rows = input
    .filter((row) => typeof row === 'object' && row !== null)
    .map((row) => {
      const item = row as Record<string, unknown>;
      return {
        key: String(item.key ?? ''),
        label: String(item.label ?? ''),
        value: String(item.value ?? ''),
      };
    })
    .filter((row) => row.key);
  return rows.length ? rows : BACKGROUND_ROWS(PROJECT_BACKGROUND);
}

export function CustomerProjectChapter({
  initialRows,
  readOnly = false,
  onRowsChange,
}: CustomerChapterProps) {
  const [rows, setRows] = useState(() => _normalizeRows(initialRows));

  useEffect(() => {
    setRows(_normalizeRows(initialRows));
  }, [initialRows]);

  useEffect(() => {
    onRowsChange?.(rows.map((row) => ({ ...row })));
  }, [onRowsChange, rows]);

  const update = (key: string, value: string) =>
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, value } : r)));

  return (
    <ProposalChapterCard id="sec-1-1" title="1. 项目背景">
      <div className="overflow-hidden rounded-lg border border-slate-200/80 bg-white">
        {rows.map((row, i) => (
          <div
            key={row.key}
            className={`flex items-start gap-4 px-4 py-3 ${i > 0 ? 'border-t border-slate-100' : ''}`}
          >
            <div className="w-32 flex-shrink-0 pt-2 text-sm font-semibold text-slate-700">
              {row.label}
            </div>
            <textarea
              value={row.value}
              rows={2}
              onChange={(e) => update(row.key, e.target.value)}
              disabled={readOnly}
              placeholder="填写内容"
              className="w-full resize-y rounded-md border border-transparent bg-transparent px-2 py-1.5 text-sm leading-relaxed text-slate-700 transition-colors hover:border-slate-200 focus:border-blue-400 focus:bg-white focus:outline-none"
            />
          </div>
        ))}
      </div>
    </ProposalChapterCard>
  );
}

export function CustomerChapterWrapper(props: CustomerChapterProps) {
  return <CustomerProjectChapter {...props} />;
}
