'use client';

import { useState } from 'react';
import {
  ProposalChapterCard,
  ProposalChapterHeader,
  ProposalDataTable,
  ProposalDataTableBody,
  ProposalDataTableHead,
} from '../primitives';
import { COMMON_PLANE_TYPES, NETWORK_PLANES, SERVER_NETWORK } from '../proposal-data';
import { SourceBadge } from '../proposal-source-badge';

function EllipsisCell({ value, title }: { value: string; title?: string }) {
  const hoverTitle = title ?? value;
  return (
    <td className="proposal-cell-ellipsis font-mono text-xs" title={hoverTitle}>
      {value}
    </td>
  );
}

export function NetworkPlanesChapter() {
  const [selectedPlanes, setSelectedPlanes] = useState(
    () => new Set(['outband', 'inband', 'business', 'sample']),
  );

  const togglePlane = (k: string) => {
    setSelectedPlanes((s) => {
      const ns = new Set(s);
      if (ns.has(k)) ns.delete(k);
      else ns.add(k);
      return ns;
    });
  };

  return (
    <ProposalChapterCard id="sec-ch-5-1" title="5.1 网络平面配置">
      <div className="mb-4 rounded-lg border border-slate-200/80 bg-slate-50/80 px-4 py-3">
        <strong className="mr-3 text-sm text-slate-700">共平面类型</strong>
        {COMMON_PLANE_TYPES.map((p) => (
          <label key={p.key} className="mr-4 cursor-pointer text-sm">
            <input
              type="checkbox"
              className="mr-1"
              checked={selectedPlanes.has(p.key)}
              onChange={() => togglePlane(p.key)}
            />
            {p.label}
          </label>
        ))}
      </div>
      <ProposalDataTable equalCols leftAlign className="proposal-table-ellipsis">
        <ProposalDataTableHead>
          <tr>
            <th>类型</th>
            <th>设备厂家</th>
            <th>设备型号</th>
            <th>设备版本</th>
            <th>数量</th>
            <th>来源</th>
            <th>备注</th>
          </tr>
        </ProposalDataTableHead>
        <ProposalDataTableBody>
          {NETWORK_PLANES.map((n, i) => (
            <tr key={i}>
              <td>{n.type}</td>
              <td>{n.vendor}</td>
              <td>{n.model === '—' ? '' : n.model}</td>
              <EllipsisCell value={n.ver === '—' ? '' : n.ver} title={n.ver === '—' ? undefined : n.ver} />
              <td>{n.qty || ''}</td>
              <td>{n.source !== '—' ? <SourceBadge source={n.source} /> : ''}</td>
              <td className="text-xs text-slate-500">{n.note}</td>
            </tr>
          ))}
        </ProposalDataTableBody>
      </ProposalDataTable>
    </ProposalChapterCard>
  );
}

export function NetworkChapterWrapper() {
  return (
    <section id="sec-ch-5">
      <ProposalChapterHeader title="5. 组网配置信息" />
      <NetworkPlanesChapter />
      <ServerNetworkChapter />
    </section>
  );
}

export function ServerNetworkChapter() {
  return (
    <ProposalChapterCard id="sec-ch-5-2" title="5.2 服务器配置">
      <ProposalDataTable equalCols leftAlign>
        <ProposalDataTableHead>
          <tr>
            <th>服务器角色</th>
            <th>服务器型号</th>
            <th>数量</th>
          </tr>
        </ProposalDataTableHead>
        <ProposalDataTableBody>
          {SERVER_NETWORK.map((s, i) => (
            <tr key={i}>
              <td>{s.planeType}</td>
              <td>{s.serverModel}</td>
              <td>{s.qty}</td>
            </tr>
          ))}
        </ProposalDataTableBody>
      </ProposalDataTable>
    </ProposalChapterCard>
  );
}
