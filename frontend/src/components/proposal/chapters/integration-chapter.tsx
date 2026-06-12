'use client';

import {
  ProposalChapterCard,
  ProposalDataTable,
  ProposalDataTableBody,
  ProposalDataTableHead,
} from '../primitives';
import { PRE_INTEGRATION } from '../proposal-data';

export function IntegrationChapter() {
  return (
    <ProposalChapterCard id="panel-pre" title="6. 集成验证需求信息">
      <ProposalDataTable equalCols leftAlign>
        <ProposalDataTableHead>
          <tr>
            <th>分类</th>
            <th>预集成验证需求</th>
            <th>硬件需求</th>
            <th>软件需求</th>
            <th>责任人</th>
            <th>完成状态</th>
            <th>完成时间</th>
          </tr>
        </ProposalDataTableHead>
        <ProposalDataTableBody>
          {PRE_INTEGRATION.map((p, i) => (
            <tr key={i}>
              <td>{p.cat}</td>
              <td><div className="proposal-clamp-2" title={p.desc}>{p.desc}</div></td>
              <td className="text-xs">{p.hw}</td>
              <td className="text-xs">{p.sw}</td>
              <td>{p.owner}</td>
              <td>{p.state}</td>
              <td>{p.date}</td>
            </tr>
          ))}
        </ProposalDataTableBody>
      </ProposalDataTable>
    </ProposalChapterCard>
  );
}
