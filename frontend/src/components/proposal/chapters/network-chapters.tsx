'use client';

import { useState } from 'react';
import {
  ProposalChapterCard,
  ProposalChapterHeader,
  ProposalDataTable,
  ProposalDataTableBody,
  ProposalDataTableHead,
} from '../primitives';
import { COMMON_PLANE_TYPES, NETWORK_PLANES } from '../proposal-data';

const SOURCE_TEXT: Record<string, string> = { BOQ: '自动解析', HLD: '人工录入', 人工: '人工录入' };
const srcLabel = (s: string) => SOURCE_TEXT[s] ?? s;

const INPUT_CLS =
  'w-full rounded border border-transparent bg-transparent px-2 py-1 text-sm text-slate-700 transition-colors hover:border-slate-200 focus:border-blue-400 focus:bg-white focus:outline-none';
const SELECT_CLS = `${INPUT_CLS} cursor-pointer`;
const TH_CLS = 'px-3 py-2.5 font-semibold';
const HEAD_TR_CLS = 'bg-slate-50/90 text-left text-sm text-slate-700';
const DEL_BTN_CLS =
  'rounded p-1 text-slate-300 transition-colors hover:bg-red-50 hover:text-red-500';
const ADD_BTN_CLS =
  'mt-3 rounded-md border border-dashed border-slate-300 px-3 py-1.5 text-xs font-normal text-slate-500 transition-colors hover:border-blue-400 hover:text-blue-600';

/* ── 5.1 网络平面配置（字段：设备角色 / 设备型号 / 设备厂家 / 设备版本 / 数量 / 来源 / 备注）── */
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
            <th>设备角色</th>
            <th>设备型号</th>
            <th>设备厂家</th>
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
              <td>{n.model === '—' ? '' : n.model}</td>
              <td>{n.vendor}</td>
              <td>
                <div className="proposal-clamp-2" title={n.ver}>{n.ver}</div>
              </td>
              <td>{n.qty || ''}</td>
              <td>{n.source !== '—' ? srcLabel(n.source) : ''}</td>
              <td className="text-xs text-slate-500">{n.note}</td>
            </tr>
          ))}
        </ProposalDataTableBody>
      </ProposalDataTable>
    </ProposalChapterCard>
  );
}

/* ── 5.2 网管服务器配置（可编辑：角色下拉 / 型号 / 数量 / 删除 / 新增）── */
const MGMT_SERVERS = [
  { role: 'NCE', model: 'TaiShan 200', qty: 2 },
  { role: 'CCAE', model: 'TaiShan 2280', qty: 1 },
  { role: 'DME', model: 'Kunpeng 920', qty: 1 },
];
const MGMT_ROLES = ['NCE', 'CCAE', 'DME'];

interface MgmtRow {
  id: number;
  role: string;
  model: string;
  qty: string;
}
type MgmtField = 'role' | 'model' | 'qty';

export function MgmtServerChapter() {
  const [rows, setRows] = useState<MgmtRow[]>(() =>
    MGMT_SERVERS.map((s, i) => ({ id: i + 1, role: s.role, model: s.model, qty: String(s.qty) })),
  );
  const update = (id: number, key: MgmtField, value: string) =>
    setRows((rs) => rs.map((r) => (r.id === id ? { ...r, [key]: value } : r)));
  const addRow = () =>
    setRows((rs) => [...rs, { id: (rs.at(-1)?.id ?? 0) + 1, role: 'NCE', model: '', qty: '1' }]);
  const removeRow = (id: number) => setRows((rs) => rs.filter((r) => r.id !== id));

  return (
    <ProposalChapterCard id="sec-ch-5-2" title="5.2 网管服务器配置">
      <div className="overflow-hidden rounded-md border border-slate-100">
        <table className="w-full table-fixed border-collapse text-sm">
          <thead>
            <tr className={HEAD_TR_CLS}>
              <th className={TH_CLS}>服务器角色</th>
              <th className={TH_CLS}>服务器型号</th>
              <th className={TH_CLS}>数量</th>
              <th className={`w-10 ${TH_CLS}`}></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-slate-100 align-middle">
                <td className="px-2 py-1.5">
                  <select value={r.role} onChange={(e) => update(r.id, 'role', e.target.value)} className={SELECT_CLS}>
                    {(MGMT_ROLES.includes(r.role) ? MGMT_ROLES : [r.role, ...MGMT_ROLES]).map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-2 py-1.5">
                  <input value={r.model} onChange={(e) => update(r.id, 'model', e.target.value)} className={INPUT_CLS} />
                </td>
                <td className="px-2 py-1.5">
                  <input value={r.qty} onChange={(e) => update(r.id, 'qty', e.target.value)} className={INPUT_CLS} />
                </td>
                <td className="px-2 py-1.5 text-center">
                  <button type="button" onClick={() => removeRow(r.id)} title="删除此行" className={DEL_BTN_CLS}>
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button type="button" onClick={addRow} className={ADD_BTN_CLS}>
        ＋ 新增一行
      </button>
    </ProposalChapterCard>
  );
}

/* ── 5.3 集群设备配置（可编辑 + 行展开嵌套设备子表）── */
const CLUSTER_TYPES = ['训练', '训推', '推理'];

interface ClusterDevice {
  id: number;
  devType: string;
  vendor: string;
  model: string;
  usage: string;
  startName: string;
  endName: string;
  qty: string;
}
interface Cluster {
  id: number;
  clusterId: string;
  type: string;
  superNodeId: string;
  storageId: string;
  zoneId: string;
  ccaeId: string;
  dmeId: string;
  devices: ClusterDevice[];
}
type ClusterField = 'clusterId' | 'type' | 'superNodeId' | 'storageId' | 'zoneId' | 'ccaeId' | 'dmeId';
type DeviceField = 'devType' | 'vendor' | 'model' | 'usage' | 'startName' | 'endName' | 'qty';

const SEED_CLUSTERS: Cluster[] = [
  {
    id: 1, clusterId: 'CLU-A001', type: '训练', superNodeId: 'SP-JD3-01', storageId: '', zoneId: 'ZONE-01', ccaeId: '', dmeId: '',
    devices: [
      { id: 1, devType: '计算节点', vendor: '华为', model: 'Atlas 900 A3', usage: '训练', startName: 'AT900A3-0001', endName: 'AT900A3-0384', qty: '384' },
    ],
  },
  {
    id: 2, clusterId: 'CLU-S001', type: '训练', superNodeId: '', storageId: 'STG-S001', zoneId: 'ZONE-01', ccaeId: '', dmeId: '',
    devices: [
      { id: 1, devType: '存储节点', vendor: '华为', model: 'OceanStor Pacific', usage: '训练数据', startName: 'OSP-0001', endName: 'OSP-0009', qty: '9' },
    ],
  },
  {
    id: 3, clusterId: 'CLU-M001', type: '训推', superNodeId: '', storageId: '', zoneId: 'ZONE-02', ccaeId: 'CCAE-A001', dmeId: '',
    devices: [
      { id: 1, devType: '推理节点', vendor: '华为', model: 'Atlas 800I A2', usage: '训推', startName: 'AT800I-0001', endName: 'AT800I-0008', qty: '8' },
    ],
  },
  {
    id: 4, clusterId: 'CLU-D001', type: '推理', superNodeId: '', storageId: '', zoneId: 'ZONE-02', ccaeId: '', dmeId: 'DME-D001',
    devices: [
      { id: 1, devType: '推理节点', vendor: '华为', model: 'Atlas 300I Duo', usage: '推理', startName: 'AT300I-0001', endName: 'AT300I-0004', qty: '4' },
    ],
  },
];

export function ClusterDeviceChapter() {
  const [clusters, setClusters] = useState<Cluster[]>(() => SEED_CLUSTERS);

  const emptyDevice = (): ClusterDevice => ({ id: 1, devType: '', vendor: '', model: '', usage: '', startName: '', endName: '', qty: '' });

  const updateCluster = (cid: number, key: ClusterField, value: string) =>
    setClusters((cs) => cs.map((c) => (c.id === cid ? { ...c, [key]: value } : c)));
  const addCluster = () =>
    setClusters((cs) => [
      ...cs,
      { id: Math.max(0, ...cs.map((c) => c.id)) + 1, clusterId: '', type: '训练', superNodeId: '', storageId: '', zoneId: '', ccaeId: '', dmeId: '', devices: [emptyDevice()] },
    ]);
  /* 单击「＋」复制当前行（同样内容），插入到该行下方 */
  const duplicateCluster = (cid: number) =>
    setClusters((cs) => {
      const idx = cs.findIndex((c) => c.id === cid);
      const src = cs[idx];
      if (idx < 0 || !src) return cs;
      const copy: Cluster = {
        ...src,
        id: Math.max(0, ...cs.map((c) => c.id)) + 1,
        devices: src.devices.map((d, k) => ({ ...d, id: k + 1 })),
      };
      return [...cs.slice(0, idx + 1), copy, ...cs.slice(idx + 1)];
    });
  const removeCluster = (cid: number) => setClusters((cs) => cs.filter((c) => c.id !== cid));

  const updateDevice = (cid: number, did: number, key: DeviceField, value: string) =>
    setClusters((cs) =>
      cs.map((c) =>
        c.id === cid ? { ...c, devices: c.devices.map((d) => (d.id === did ? { ...d, [key]: value } : d)) } : c,
      ),
    );

  const clusterInput = (c: Cluster, key: ClusterField, value: string) => (
    <td className="px-2 py-1.5">
      <input value={value} onChange={(e) => updateCluster(c.id, key, e.target.value)} className={`${INPUT_CLS} font-mono text-xs`} />
    </td>
  );

  return (
    <ProposalChapterCard id="sec-ch-5-3" title="5.3 集群设备配置">
      {/* 集群列 + 设备列同处一张宽表的表头一排（参考图二）·不够宽时左右拖动滚动条 */}
      <div className="overflow-x-auto rounded-md border border-slate-100">
        <table className="w-full min-w-[1560px] table-fixed border-collapse text-sm">
          <colgroup>
            <col style={{ width: 36 }} />
            <col style={{ width: 110 }} />
            <col style={{ width: 84 }} />
            <col style={{ width: 104 }} />
            <col style={{ width: 110 }} />
            <col style={{ width: 96 }} />
            <col style={{ width: 116 }} />
            <col style={{ width: 116 }} />
            <col style={{ width: 100 }} />
            <col style={{ width: 76 }} />
            <col style={{ width: 128 }} />
            <col style={{ width: 104 }} />
            <col style={{ width: 128 }} />
            <col style={{ width: 128 }} />
            <col style={{ width: 68 }} />
            <col style={{ width: 40 }} />
          </colgroup>
          <thead>
            <tr className={HEAD_TR_CLS}>
              <th className="px-2 py-2.5"></th>
              <th className={TH_CLS}>集群ID</th>
              <th className={TH_CLS}>集群类型</th>
              <th className={TH_CLS}>超节点ID</th>
              <th className={TH_CLS}>存储集群ID</th>
              <th className={TH_CLS}>ZONE ID</th>
              <th className={TH_CLS}>CCAE集群ID</th>
              <th className={TH_CLS}>DME集群ID</th>
              <th className={TH_CLS}>设备类型</th>
              <th className={TH_CLS}>厂家</th>
              <th className={TH_CLS}>设备型号</th>
              <th className={TH_CLS}>设备用途</th>
              <th className={TH_CLS}>起始设备命名</th>
              <th className={TH_CLS}>截止设备命名</th>
              <th className={TH_CLS}>数量</th>
              <th className="px-2 py-2.5"></th>
            </tr>
          </thead>
          <tbody>
            {clusters.map((c) => {
              const d = c.devices[0];
              return (
                <tr key={c.id} className="border-t border-slate-100 align-middle">
                  <td className="px-1 py-1.5 text-center">
                    <button type="button" onClick={() => duplicateCluster(c.id)} title="新增同样内容的行" className="grid h-5 w-5 place-items-center rounded text-slate-400 transition-colors hover:bg-blue-50 hover:text-blue-600">＋</button>
                  </td>
                  {clusterInput(c, 'clusterId', c.clusterId)}
                  <td className="px-2 py-1.5">
                    <select value={c.type} onChange={(e) => updateCluster(c.id, 'type', e.target.value)} className={SELECT_CLS}>
                      {CLUSTER_TYPES.map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                  </td>
                  {clusterInput(c, 'superNodeId', c.superNodeId)}
                  {clusterInput(c, 'storageId', c.storageId)}
                  {clusterInput(c, 'zoneId', c.zoneId)}
                  {clusterInput(c, 'ccaeId', c.ccaeId)}
                  {clusterInput(c, 'dmeId', c.dmeId)}
                  {d ? (
                    <>
                      <td className="px-2 py-1.5"><input value={d.devType} onChange={(e) => updateDevice(c.id, d.id, 'devType', e.target.value)} className={INPUT_CLS} /></td>
                      <td className="px-2 py-1.5"><input value={d.vendor} onChange={(e) => updateDevice(c.id, d.id, 'vendor', e.target.value)} className={INPUT_CLS} /></td>
                      <td className="px-2 py-1.5"><input value={d.model} onChange={(e) => updateDevice(c.id, d.id, 'model', e.target.value)} className={INPUT_CLS} /></td>
                      <td className="px-2 py-1.5"><input value={d.usage} onChange={(e) => updateDevice(c.id, d.id, 'usage', e.target.value)} placeholder="TD 录入" className={INPUT_CLS} /></td>
                      <td className="px-2 py-1.5"><input value={d.startName} onChange={(e) => updateDevice(c.id, d.id, 'startName', e.target.value)} placeholder="AT900A3-0001" className={`${INPUT_CLS} font-mono text-xs`} /></td>
                      <td className="px-2 py-1.5"><input value={d.endName} onChange={(e) => updateDevice(c.id, d.id, 'endName', e.target.value)} placeholder="AT900A3-0001" className={`${INPUT_CLS} font-mono text-xs`} /></td>
                      <td className="px-2 py-1.5"><input value={d.qty} onChange={(e) => updateDevice(c.id, d.id, 'qty', e.target.value)} className={INPUT_CLS} /></td>
                    </>
                  ) : (
                    <td colSpan={7} className="px-2 py-2 text-xs text-slate-400">—</td>
                  )}
                  <td className="px-1 py-1.5 text-center">
                    <button type="button" onClick={() => removeCluster(c.id)} title="删除此行" className={DEL_BTN_CLS}>✕</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <button type="button" onClick={addCluster} className={ADD_BTN_CLS}>
        ＋ 新增集群
      </button>
    </ProposalChapterCard>
  );
}

export function NetworkChapterWrapper() {
  return (
    <section id="sec-ch-5">
      <ProposalChapterHeader title="5. 组网配置信息" />
      <NetworkPlanesChapter />
      <MgmtServerChapter />
      <ClusterDeviceChapter />
    </section>
  );
}
