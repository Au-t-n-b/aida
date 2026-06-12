'use client';

import {
  ProposalChapterCard,
  ProposalDataTable,
  ProposalDataTableBody,
  ProposalDataTableHead,
} from '../primitives';
import { ACCEPTANCE_ITEMS } from '../proposal-data';

export function AcceptanceChapter() {
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
          {ACCEPTANCE_ITEMS.map((a, i) => (
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
