'use client';

import { useEffect, useMemo } from 'react';
import {
  ProposalChapterCard,
  ProposalDataTable,
  ProposalDataTableBody,
  ProposalDataTableHead,
} from '../primitives';
import { ACCEPTANCE_ITEMS } from '../proposal-data';

interface AcceptanceChapterProps {
  initialRows?: unknown;
  onRowsChange?: (rows: Array<Record<string, unknown>>) => void;
}

function _normalizeRows(input: unknown) {
  if (!Array.isArray(input) || input.length === 0) {
    return ACCEPTANCE_ITEMS;
  }
  const rows = input
    .filter((row) => typeof row === 'object' && row !== null)
    .map((row) => {
      const item = row as Record<string, unknown>;
      return {
        cat: String(item.cat ?? ''),
        scheme: String(item.scheme ?? ''),
        standard: String(item.standard ?? ''),
        milestone: String(item.milestone ?? ''),
        doc: String(item.doc ?? ''),
        payment: String(item.payment ?? ''),
        paymentMilestone: String(item.paymentMilestone ?? ''),
      };
    });
  return rows.length ? rows : ACCEPTANCE_ITEMS;
}

export function AcceptanceChapter({ initialRows, onRowsChange }: AcceptanceChapterProps) {
  const rows = useMemo(() => _normalizeRows(initialRows), [initialRows]);

  useEffect(() => {
    onRowsChange?.(rows.map((row) => ({ ...row })));
  }, [onRowsChange, rows]);

  return (
    <ProposalChapterCard id="panel-accept" title="11. 验收策略">
      <ProposalDataTable equalCols leftAlign>
        <ProposalDataTableHead>
          <tr>
            <th>分类</th>
            <th>验收方案</th>
            <th>验收标准</th>
            <th>验收里程碑</th>
            <th>验收文档</th>
            <th>回款条款</th>
            <th>回款里程碑</th>
          </tr>
        </ProposalDataTableHead>
        <ProposalDataTableBody>
          {rows.map((a, i) => (
            <tr key={i}>
              <td>{a.cat}</td>
              <td className="text-xs">{a.scheme}</td>
              <td className="text-xs">{a.standard}</td>
              <td className="text-xs">{a.milestone}</td>
              <td className="text-xs">{a.doc}</td>
              <td className="font-mono text-xs">{a.payment}</td>
              <td className="text-xs text-slate-500">{a.paymentMilestone}</td>
            </tr>
          ))}
        </ProposalDataTableBody>
      </ProposalDataTable>
    </ProposalChapterCard>
  );
}
