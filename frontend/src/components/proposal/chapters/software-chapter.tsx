'use client';

import {
  ProposalChapterCard,
  ProposalDataTable,
  ProposalDataTableBody,
  ProposalDataTableHead,
} from '../primitives';
import { SOFTWARE_STACK } from '../proposal-data';
import { HwBadge, SourceBadge } from '../proposal-source-badge';

export function SoftwareChapter() {
  return (
    <ProposalChapterCard id="sec-ch-4" title="4. 软件配置信息">
      <ProposalDataTable equalCols leftAlign>
        <ProposalDataTableHead>
          <tr>
            <th>类型</th>
            <th>华为软件</th>
            <th>软件型号</th>
            <th>版本</th>
            <th>来源</th>
            <th>备注</th>
          </tr>
        </ProposalDataTableHead>
        <ProposalDataTableBody>
          {SOFTWARE_STACK.map((s, i) => (
            <tr key={i}>
              <td>{s.type}</td>
              <td><HwBadge isHW={s.isHW} /></td>
              <td>{s.software}</td>
              <td className="font-mono text-xs">{s.ver}</td>
              <td><SourceBadge source={s.source} /></td>
              <td className="text-xs">{s.remark}</td>
            </tr>
          ))}
        </ProposalDataTableBody>
      </ProposalDataTable>
    </ProposalChapterCard>
  );
}
