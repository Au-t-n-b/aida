'use client';

import {
  ProposalChapterCard,
  ProposalDataTable,
  ProposalDataTableBody,
  ProposalDataTableHead,
} from '../primitives';
import { COMPUTE_DEVICES } from '../proposal-data';
import { SourceBadge } from '../proposal-source-badge';

export function DeviceChapter() {
  return (
    <ProposalChapterCard id="sec-ch-2" title="2. 设备配置信息">
      <ProposalDataTable leftAlign>
        <ProposalDataTableHead>
          <tr>
            <th>设备类型</th>
            <th>型号</th>
            <th>产品编码</th>
            <th>版本</th>
            <th>生命周期</th>
            <th>数量</th>
            <th>单空间</th>
            <th>总空间</th>
            <th>单功耗</th>
            <th>总功耗</th>
            <th>来源</th>
          </tr>
        </ProposalDataTableHead>
        <ProposalDataTableBody>
          {COMPUTE_DEVICES.map((d, i) => (
            <tr key={i}>
              <td>{d.cat}</td>
              <td>{d.model}</td>
              <td className="font-mono text-xs">{d.code}</td>
              <td className="font-mono text-xs">{d.ver}</td>
              <td><span className="status-pill green">{d.lifecycle}</span></td>
              <td>{d.qty}</td>
              <td>{d.unitSpace}</td>
              <td>{d.totalSpace}</td>
              <td>{d.unitPower}</td>
              <td>{d.totalPower}</td>
              <td><SourceBadge source={d.source} /></td>
            </tr>
          ))}
        </ProposalDataTableBody>
      </ProposalDataTable>
    </ProposalChapterCard>
  );
}
