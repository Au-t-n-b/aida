'use client';

import {
  ProposalChapterCard,
  ProposalDataTable,
  ProposalDataTableBody,
  ProposalDataTableHead,
} from '../primitives';
import { RACI_ROWS } from '../proposal-data';

function RaciLabel({ v }: { v: string }) {
  if (!v) return <span className="text-slate-400">—</span>;
  return <span className="status-pill gray">{v}</span>;
}

function stackRowSpans(rows: typeof RACI_ROWS): number[] {
  return rows.map((row, i) => {
    if (i > 0 && row.stack === rows[i - 1]?.stack) return 0;
    let span = 1;
    while (i + span < rows.length && rows[i + span]?.stack === row.stack) span += 1;
    return span;
  });
}

export function RaciChapter() {
  const rowSpans = stackRowSpans(RACI_ROWS);

  return (
    <ProposalChapterCard id="panel-raci" title="9. 责任矩阵信息">
      <ProposalDataTable leftAlign>
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
          {RACI_ROWS.map((r, i) => (
            <tr key={i}>
              {(rowSpans[i] ?? 0) > 0 && (
                <td
                  rowSpan={rowSpans[i] ?? 1}
                  className="align-middle text-xs font-bold text-slate-900"
                >
                  {r.stack}
                </td>
              )}
              <td className="raci-cat-col text-left text-xs">{r.cat}</td>
              <td className="text-xs">{r.act}</td>
              <td><RaciLabel v={r.gts} /></td>
              <td><RaciLabel v={r.hw} /></td>
              <td><RaciLabel v={r.partner} /></td>
              <td><RaciLabel v={r.customer} /></td>
            </tr>
          ))}
        </ProposalDataTableBody>
      </ProposalDataTable>
    </ProposalChapterCard>
  );
}
