'use client';

import {
  ProposalChapterCard,
  ProposalDataTable,
  ProposalDataTableBody,
  ProposalDataTableHead,
} from '../primitives';
import { ROOMS_RACKS } from '../proposal-data';

export function RoomChapter() {
  return (
    <ProposalChapterCard id="panel-rooms" title="7. 机房信息">
      <ProposalDataTable leftAlign>
        <ProposalDataTableHead>
          <tr>
            <th>机房</th>
            <th>机柜类型</th>
            <th>功率</th>
            <th>数量</th>
            <th>备注</th>
          </tr>
        </ProposalDataTableHead>
        <ProposalDataTableBody>
          {ROOMS_RACKS.map((r, i) => (
            <tr key={i} className={r.qty === 0 ? 'has-conflict' : ''}>
              <td className="font-mono text-xs">{r.room}</td>
              <td>{r.type}</td>
              <td>{r.power}</td>
              <td>
                {r.qty > 0 ? (
                  r.qty
                ) : (
                  <input type="number" className="boq-qty-input" defaultValue={0} placeholder="手填" />
                )}
              </td>
              <td className="text-xs text-slate-500">{r.note}</td>
            </tr>
          ))}
        </ProposalDataTableBody>
      </ProposalDataTable>
    </ProposalChapterCard>
  );
}
