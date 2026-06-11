'use client';

import {
  ProposalChapterCard,
  ProposalDataTable,
  ProposalDataTableBody,
  ProposalDataTableHead,
} from '../primitives';
import { INTEL_PARTS } from '../proposal-data';
import { SourceBadge } from '../proposal-source-badge';

export function PartsChapter() {
  return (
    <ProposalChapterCard id="sec-ch-3" title="3. 部件配置信息">
      <ProposalDataTable equalCols leftAlign>
        <ProposalDataTableHead>
          <tr>
            <th>类型</th>
            <th>部件编码</th>
            <th>厂商</th>
            <th>部件名称</th>
            <th>来源</th>
          </tr>
        </ProposalDataTableHead>
        <ProposalDataTableBody>
          {INTEL_PARTS.map((p, i) => (
            <tr key={i}>
              <td>{p.cat}</td>
              <td className="font-mono text-xs">{p.code}</td>
              <td>{p.vendor}</td>
              <td>{p.name}</td>
              <td><SourceBadge source={p.source} /></td>
            </tr>
          ))}
        </ProposalDataTableBody>
      </ProposalDataTable>
    </ProposalChapterCard>
  );
}
