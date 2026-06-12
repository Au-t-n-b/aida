'use client';

import {
  ProposalChapterCard,
  ProposalDataTable,
  ProposalDataTableBody,
  ProposalDataTableHead,
} from '../primitives';
import { useProposalData } from '@/hooks/useProposalData';
import type { RaciRow } from '@/types/domain';

type RoleField = 'gts' | 'hw' | 'partner' | 'customer';

const ROLE_INPUT =
  'w-full cursor-pointer rounded border border-transparent bg-transparent px-1 py-0.5 text-sm text-slate-700 transition-colors hover:border-slate-200 focus:border-blue-400 focus:bg-white focus:outline-none';
const ROLE_OPTIONS = ['', 'R', 'A', 'S', 'C', 'I', 'R/A'];

function spans(rows: readonly RaciRow[], keyFn: (r: RaciRow) => string): number[] {
  return rows.map((row, i) => {
    const prev = rows[i - 1];
    if (i > 0 && prev && keyFn(prev) === keyFn(row)) return 0;
    let span = 1;
    let next = rows[i + span];
    while (next && keyFn(next) === keyFn(row)) {
      span += 1;
      next = rows[i + span];
    }
    return span;
  });
}

export function RaciChapter() {
  const { raciRows, updateRaci, loading } = useProposalData();
  const rows = raciRows;

  const update = (i: number, key: RoleField, value: string) =>
    updateRaci(rows.map((r, idx) => (idx === i ? { ...r, [key]: value } : r)));

  const stackSpans = spans(rows, (r) => r.stack);
  const catSpans = spans(rows, (r) => `${r.stack}||${r.cat}`);

  const roleCell = (i: number, key: RoleField, value: string) => (
    <td className="px-1 py-1">
      <select value={value} onChange={(e) => update(i, key, e.target.value)} className={ROLE_INPUT}>
        {(ROLE_OPTIONS.includes(value) ? ROLE_OPTIONS : [value, ...ROLE_OPTIONS]).map((o) => (
          <option key={o} value={o}>{o || '—'}</option>
        ))}
      </select>
    </td>
  );

  return (
    <ProposalChapterCard id="panel-raci" title="9. 责任矩阵信息">
      {loading && <p className="mb-2 text-xs text-slate-400">正在加载责任矩阵…</p>}
      <div className="overflow-x-auto">
        <ProposalDataTable leftAlign className="min-w-[920px] table-fixed proposal-table-aligned">
          <colgroup>
            <col style={{ width: 86 }} />
            <col style={{ width: 156 }} />
            <col />
            <col style={{ width: 80 }} />
            <col style={{ width: 80 }} />
            <col style={{ width: 78 }} />
            <col style={{ width: 78 }} />
          </colgroup>
          <ProposalDataTableHead>
            <tr>
              <th>技术栈</th>
              <th className="raci-cat-col text-left">活动分类（一级）</th>
              <th>活动（二级）</th>
              <th>GTS</th>
              <th>华为云</th>
              <th>伙伴</th>
              <th>客户</th>
            </tr>
          </ProposalDataTableHead>
          <ProposalDataTableBody>
            {rows.map((r, i) => (
              <tr key={i}>
                {(stackSpans[i] ?? 0) > 0 && (
                  <td rowSpan={stackSpans[i] ?? 1} className="align-middle font-semibold text-slate-800">
                    {r.stack}
                  </td>
                )}
                {(catSpans[i] ?? 0) > 0 && (
                  <td rowSpan={catSpans[i] ?? 1} className="raci-cat-col align-middle text-left font-medium text-slate-700">
                    {r.cat}
                  </td>
                )}
                <td>{r.act}</td>
                {roleCell(i, 'gts', r.gts)}
                {roleCell(i, 'hw', r.hw)}
                {roleCell(i, 'partner', r.partner)}
                {roleCell(i, 'customer', r.customer)}
              </tr>
            ))}
          </ProposalDataTableBody>
        </ProposalDataTable>
      </div>
    </ProposalChapterCard>
  );
}
