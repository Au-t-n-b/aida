'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ProposalChapterCard,
  ProposalChapterHeader,
  ProposalDataTable,
  ProposalDataTableBody,
  ProposalDataTableHead,
} from '../primitives';
import { COMMON_PLANE_TYPES } from '../proposal-data';
import {
  chapterUploadMessage,
  proposalApi,
  type AvailableDeviceItem,
  type ChapterUploadResult,
  type NetMgmtRow,
  type NetPlaneRow,
} from '@/lib/proposal-api';

const INPUT_CLS =
  'w-full rounded border border-transparent bg-transparent px-2 py-1 text-sm text-slate-700 transition-colors hover:border-slate-200 focus:border-blue-400 focus:bg-white focus:outline-none';
const SELECT_CLS = `${INPUT_CLS} cursor-pointer`;
const TH_CLS = 'px-3 py-2.5 font-semibold';
const HEAD_TR_CLS = 'bg-slate-50/90 text-left text-sm text-slate-700';
const DEL_BTN_CLS =
  'rounded p-1 text-slate-300 transition-colors hover:bg-red-50 hover:text-red-500';
const ADD_BTN_CLS =
  'mt-3 rounded-md border border-dashed border-slate-300 px-3 py-1.5 text-xs font-normal text-slate-500 transition-colors hover:border-blue-400 hover:text-blue-600';

function useChapterAutosave(
  save: () => Promise<ChapterUploadResult<unknown>>,
) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saveRef = useRef(save);
  saveRef.current = save;

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  return useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(async () => {
      timerRef.current = null;
      try {
        const result = await saveRef.current();
        if (!result.uploaded || (result.common_plane && !result.common_plane.uploaded)) {
          console.warn('[Proposal chapters] autosave upload warning:', chapterUploadMessage(result));
        }
      } catch (error) {
        console.error('[Proposal chapters] autosave failed:', error);
      }
    }, 1000);
  }, []);
}

const PLANE_LABEL_TO_KEY: Record<string, string> = {
  '网管面': 'outband',
  '业务面': 'business',
  '样本面': 'sample',
  '参数面': 'inband',
  '存储面': 'inband',
};

function matchesFilter(row: NetPlaneRow, selectedPlanes: Set<string>): boolean {
  if (selectedPlanes.size === 0) return true;
  let recognized = false;
  for (const [label, key] of Object.entries(PLANE_LABEL_TO_KEY)) {
    if (row.type.includes(label)) recognized = true;
    if (row.type.includes(label) && selectedPlanes.has(key)) return true;
  }
  return !recognized;
}

/* ── 5.1 网络平面配置（字段：设备角色 / 设备型号 / 设备厂家 / 设备版本 / 数量 / 来源 / 备注）── */
export function NetworkPlanesChapter() {
  const [rows, setRows] = useState<NetPlaneRow[]>([]);
  const [availableDevices, setAvailableDevices] = useState<AvailableDeviceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [selectedPlanes, setSelectedPlanes] = useState(
    () => new Set(['outband', 'inband', 'business', 'sample']),
  );
  const fileInputRef = useRef<HTMLInputElement>(null);
  const debounceTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const pendingPatches = useRef<Map<string, Record<string, unknown>>>(new Map());
  const scheduleAutosave = useChapterAutosave(
    () => proposalApi.autosaveNetPlanes(
      rows,
      COMMON_PLANE_TYPES.filter((plane) => selectedPlanes.has(plane.key)).map((plane) => plane.label),
    ),
  );

  useEffect(() => {
    return () => { debounceTimers.current.forEach((t) => clearTimeout(t)); };
  }, []);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const [data, devicesData] = await Promise.all([
        proposalApi.listNetPlanes(),
        proposalApi.listAvailableDevices(),
      ]);
      setRows(data.rows);
      setAvailableDevices(devicesData.devices);
    } catch (e) {
      console.error('[Network planes] load failed:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const togglePlane = (k: string) => {
    setSelectedPlanes((s) => {
      const ns = new Set(s);
      if (ns.has(k)) ns.delete(k);
      else ns.add(k);
      return ns;
    });
    scheduleAutosave();
  };

  const filteredRows = rows.filter((r) => matchesFilter(r, selectedPlanes));

  const handleAdd = async (sourceRowId: string) => {
    try {
      const data = await proposalApi.createNetPlane(sourceRowId);
      setRows((rs) => {
        const sourceIndex = rs.findIndex((row) => row.row_id === sourceRowId);
        if (sourceIndex < 0) return [...rs, data.row];
        return [...rs.slice(0, sourceIndex + 1), data.row, ...rs.slice(sourceIndex + 1)];
      });
      window.dispatchEvent(new CustomEvent('net-plane-updated', { detail: { rowId: data.row.row_id } }));
      scheduleAutosave();
    } catch (e) {
      console.error('[Network planes] create failed:', e);
    }
  };

  const handleUpdate = (
    rowId: string,
    patch: {
      type?: string;
      vendor?: string;
      model?: string;
      ver?: string;
      qty?: number;
      source?: string;
      note?: string | null;
    },
  ) => {
    setRows((rs) => rs.map((r) => (r.row_id === rowId ? { ...r, ...patch } : r)));

    const existing = pendingPatches.current.get(rowId) || {};
    pendingPatches.current.set(rowId, { ...existing, ...patch });

    const existingTimer = debounceTimers.current.get(rowId);
    if (existingTimer) clearTimeout(existingTimer);

    const timer = setTimeout(async () => {
      const accumulated = pendingPatches.current.get(rowId);
      pendingPatches.current.delete(rowId);
      debounceTimers.current.delete(rowId);
      if (!accumulated) return;

      try {
        const data = await proposalApi.updateNetPlane(rowId, accumulated as Parameters<typeof proposalApi.updateNetPlane>[1]);
        setRows((rs) => rs.map((r) => (r.row_id === rowId ? data.row : r)));
        if (data.warnings.length > 0) {
          console.warn('[Network planes] update warnings:', data.warnings);
        }
        if ('qty' in accumulated || 'vendor' in accumulated || 'model' in accumulated) {
          window.dispatchEvent(new CustomEvent('net-plane-updated', { detail: { rowId } }));
        }
        scheduleAutosave();
      } catch (e) {
        console.error('[Network planes] update failed:', e);
        load();
      }
    }, 500);

    debounceTimers.current.set(rowId, timer);
  };

  const handleDelete = async (rowId: string) => {
    const prev = rows;
    setRows((rs) => rs.filter((r) => r.row_id !== rowId));
    try {
      await proposalApi.deleteNetPlane(rowId);
      scheduleAutosave();
    } catch (e) {
      setRows(prev);
      console.error('[Network planes] delete failed:', e);
    }
  };

  const handleUpload = async (file: File) => {
    if (exporting) return;
    setExporting(true);
    try {
      const data = await proposalApi.importNetPlanes(file);
      setRows(data.rows);
      window.dispatchEvent(new CustomEvent('net-plane-updated'));
      scheduleAutosave();
    } catch (e) {
      console.error('[Network planes] import failed:', e);
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return (
      <ProposalChapterCard id="sec-ch-5-1" title="5.1 网络平面配置">
        <div className="p-8 text-center text-sm text-slate-400">加载中…</div>
      </ProposalChapterCard>
    );
  }

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
      <ProposalDataTable leftAlign className="proposal-table-ellipsis">
        <ProposalDataTableHead>
          <tr>
            <th className="w-8 px-1"></th>
            <th>设备角色</th>
            <th>设备型号</th>
            <th>设备厂家</th>
            <th>设备版本</th>
            <th className="w-20">数量</th>
            <th className="w-24">来源</th>
            <th>备注</th>
            <th className="w-8 px-1"></th>
          </tr>
        </ProposalDataTableHead>
        <ProposalDataTableBody>
          {filteredRows.map((row) => (
            <tr key={row.row_id}>
              <td className="w-8 px-1 text-center align-middle">
                <button
                  type="button"
                  title="复制本行并新增"
                  onClick={() => handleAdd(row.row_id)}
                  className="inline-flex h-5 w-5 items-center justify-center rounded border border-slate-200 text-xs text-slate-500 transition-colors hover:border-blue-400 hover:bg-blue-50 hover:text-blue-600"
                >＋</button>
              </td>
              <td>
                <input
                  type="text"
                  value={row.type}
                  onChange={(e) => handleUpdate(row.row_id, { type: e.target.value })}
                  placeholder="手工填写设备角色"
                  className={INPUT_CLS}
                />
              </td>
              <td>
                <select
                  value={row.model}
                  onChange={(e) => {
                    const device = availableDevices.find((item) => item.device_model === e.target.value);
                    handleUpdate(row.row_id, {
                      model: e.target.value,
                      ver: device?.device_version || '',
                    });
                  }}
                  className={`${SELECT_CLS} font-mono text-xs`}
                >
                  <option value="">请选择设备型号</option>
                  {availableDevices.map((device) => (
                    <option key={`${device.device_model}-${device.device_version}`} value={device.device_model}>
                      {device.device_model}
                    </option>
                  ))}
                </select>
              </td>
              <td>
                <input
                  type="text"
                  value={row.vendor}
                  onChange={(e) => handleUpdate(row.row_id, { vendor: e.target.value })}
                  readOnly={row.vendor === '华为'}
                  placeholder="手工填写设备厂家"
                  className={`${INPUT_CLS} ${row.vendor === '华为' ? 'cursor-not-allowed bg-slate-50 text-slate-400' : ''}`}
                />
              </td>
              <td>
                <span className="block truncate px-2 py-1 text-sm font-mono text-slate-600" title={row.ver}>
                  {row.ver || '—'}
                </span>
              </td>
              <td>
                <input
                  type="number"
                  value={row.qty}
                  min={0}
                  onChange={(e) => {
                    const v = e.target.value;
                    handleUpdate(row.row_id, { qty: v === '' ? 0 : parseInt(v, 10) });
                  }}
                  className={`${INPUT_CLS} tabular-nums`}
                />
              </td>
              <td>
                <input
                  type="text"
                  value={row.source}
                  onChange={(e) => handleUpdate(row.row_id, { source: e.target.value })}
                  placeholder="来源"
                  className={INPUT_CLS}
                />
              </td>
              <td>
                <input
                  type="text"
                  value={row.note ?? ''}
                  onChange={(e) => handleUpdate(row.row_id, { note: e.target.value || null })}
                  placeholder="备注"
                  className={`${INPUT_CLS} text-xs text-slate-500`}
                />
              </td>
              <td className="w-8 px-1 text-center align-middle">
                <button
                  type="button"
                  title="删除本行"
                  onClick={() => handleDelete(row.row_id)}
                  className={DEL_BTN_CLS}
                >✕</button>
              </td>
            </tr>
          ))}
        </ProposalDataTableBody>
      </ProposalDataTable>
      <div className="mt-3 flex justify-end">
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = '';
            if (file) void handleUpload(file);
          }}
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={exporting}
          className={`rounded-md border px-3 py-1.5 text-xs font-normal transition-colors ${
            exporting
              ? 'cursor-not-allowed border-slate-200 text-slate-300'
              : 'border-green-300 text-green-600 hover:border-green-400 hover:bg-green-50'
          }`}
        >
          {exporting ? '上传中…' : '上传'}
        </button>
      </div>
    </ProposalChapterCard>
  );
}

/* ── 5.2 网管服务器配置（文件名识别角色，型号和数量手工维护）── */
export function MgmtServerChapter() {
  const [rows, setRows] = useState<NetMgmtRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const debounceTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const pendingPatches = useRef<Map<string, { server_model?: string; quantity?: number }>>(new Map());
  const scheduleAutosave = useChapterAutosave(
    () => proposalApi.autosaveNetMgmt(rows),
  );

  const load = async () => {
    setLoading(true);
    try {
      const data = await proposalApi.initializeNetMgmt();
      setRows(data.rows);
    } catch (e) {
      console.error('[Network management servers] load failed:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    return () => debounceTimers.current.forEach((timer) => clearTimeout(timer));
  }, []);

  const update = (rowId: string, patch: { server_model?: string; quantity?: number }) => {
    setRows((current) => current.map((row) => (row.row_id === rowId ? { ...row, ...patch } : row)));
    pendingPatches.current.set(rowId, { ...pendingPatches.current.get(rowId), ...patch });
    const timer = debounceTimers.current.get(rowId);
    if (timer) clearTimeout(timer);
    debounceTimers.current.set(rowId, setTimeout(async () => {
      debounceTimers.current.delete(rowId);
      const accumulated = pendingPatches.current.get(rowId);
      pendingPatches.current.delete(rowId);
      if (!accumulated) return;
      try {
        const updated = await proposalApi.updateNetMgmt(rowId, accumulated);
        setRows((current) => current.map((row) => (row.row_id === rowId ? updated : row)));
        scheduleAutosave();
      } catch (e) {
        console.error('[Network management servers] update failed:', e);
        load();
      }
    }, 500));
  };

  const removeRow = async (rowId: string) => {
    const previous = rows;
    setRows((current) => current.filter((row) => row.row_id !== rowId));
    try {
      await proposalApi.deleteNetMgmt(rowId);
      scheduleAutosave();
    } catch (e) {
      setRows(previous);
      console.error('[Network management servers] delete failed:', e);
    }
  };

  const handleUpload = async (file: File) => {
    if (exporting) return;
    setExporting(true);
    try {
      const data = await proposalApi.importNetMgmt(file);
      setRows(data.rows);
      scheduleAutosave();
    } catch (e) {
      console.error('[Network management servers] import failed:', e);
    } finally {
      setExporting(false);
    }
  };

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
              <tr key={r.row_id} className="border-t border-slate-100 align-middle">
                <td className="px-2 py-1.5">
                  <div className="px-2 py-1 text-xs text-slate-500">{r.server_role}</div>
                </td>
                <td className="px-2 py-1.5">
                  <input value={r.server_model} onChange={(e) => update(r.row_id, { server_model: e.target.value })} className={INPUT_CLS} placeholder="手工填写" />
                </td>
                <td className="px-2 py-1.5">
                  <input type="number" min={1} value={r.quantity} onChange={(e) => update(r.row_id, { quantity: Math.max(1, Number(e.target.value) || 1) })} className={INPUT_CLS} />
                </td>
                <td className="px-2 py-1.5 text-center">
                  <button type="button" onClick={() => removeRow(r.row_id)} title="删除此行" className={DEL_BTN_CLS}>
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && rows.length === 0 && (
          <div className="border-t border-slate-100 px-4 py-8 text-center text-sm text-slate-400">
            未识别到网管服务器，请将文件放入 data/delivery/net-mgmt/，文件名需包含 NCE、CCAE 或 DME。
          </div>
        )}
      </div>
      <div className="mt-3 flex items-center justify-between">
        <div className="text-xs text-slate-500">{loading ? '正在读取目录…' : `共识别 ${rows.length} 类网管服务器`}</div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className={`rounded-md border px-3 py-1.5 text-xs font-normal transition-colors ${
              loading
                ? 'cursor-not-allowed border-slate-200 text-slate-300'
                : 'border-blue-300 text-blue-600 hover:border-blue-400 hover:bg-blue-50'
            }`}
          >
            {loading ? '扫描中…' : '重新扫描'}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              event.target.value = '';
              if (file) void handleUpload(file);
            }}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={exporting}
            className={`rounded-md border px-3 py-1.5 text-xs font-normal transition-colors ${
              exporting
                ? 'cursor-not-allowed border-slate-200 text-slate-300'
                : 'border-green-300 text-green-600 hover:border-green-400 hover:bg-green-50'
            }`}
          >
            {exporting ? '上传中…' : '上传'}
          </button>
        </div>
      </div>
    </ProposalChapterCard>
  );
}

/* ── 5.3 集群设备配置（继承 5.1 厂家/型号/数量 + 子行拆分）── */
const CLUSTER_TYPES = ['训练', '训推', '推理'];

type ClusterField =
  | 'cluster_id'
  | 'cluster_type'
  | 'super_pod_id'
  | 'storage_cluster_id'
  | 'zone_id'
  | 'ccae_cluster_id'
  | 'dme_cluster_id';
type ClusterEditableField =
  | ClusterField
  | 'device_type'
  | 'device_purpose'
  | 'start_device_name'
  | 'end_device_name'
  | 'quantity';

const FIELD_TO_API: Record<ClusterEditableField, string> = {
  cluster_id: 'cluster_id',
  cluster_type: 'cluster_type',
  super_pod_id: 'super_pod_id',
  storage_cluster_id: 'storage_cluster_id',
  zone_id: 'zone_id',
  ccae_cluster_id: 'ccae_cluster_id',
  dme_cluster_id: 'dme_cluster_id',
  device_type: 'device_type',
  device_purpose: 'device_purpose',
  start_device_name: 'start_device_name',
  end_device_name: 'end_device_name',
  quantity: 'quantity',
};

const READONLY_CELL = 'px-2 py-1 text-xs text-slate-500 truncate';

export function ClusterDeviceChapter() {
  const [rows, setRows] = useState<import('@/lib/proposal-api').ClusterDeviceRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const debounceTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const pendingPatches = useRef<Map<string, Record<string, unknown>>>(new Map());
  const scheduleAutosave = useChapterAutosave(
    () => proposalApi.autosaveClusterDevices(rows),
  );

  useEffect(() => {
    return () => { debounceTimers.current.forEach((t) => clearTimeout(t)); };
  }, []);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const devicesData = await proposalApi.listClusterDevices();
      setRows(devicesData.rows);
    } catch (e) {
      console.error('[Cluster devices] load failed:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const handler = () => { load(); };
    window.addEventListener('net-plane-updated', handler);
    return () => window.removeEventListener('net-plane-updated', handler);
  }, [load]);

  const handleAdd = async (sourceNetPlaneId: string) => {
    try {
      const newRow = await proposalApi.createClusterDevice(sourceNetPlaneId);
      setRows((rs) => {
        const idx = rs.findIndex((r) => r.source_net_plane_id === sourceNetPlaneId);
        if (idx >= 0) {
          let insertPos = idx + 1;
          while (insertPos < rs.length && rs[insertPos]?.source_net_plane_id === sourceNetPlaneId) {
            insertPos++;
          }
          return [...rs.slice(0, insertPos), newRow, ...rs.slice(insertPos)];
        }
        return [...rs, newRow];
      });
      scheduleAutosave();
    } catch (e) {
      console.error('[Cluster devices] create failed:', e);
    }
  };

  const handleUpload = async (file: File) => {
    if (exporting) return;
    setExporting(true);
    try {
      const data = await proposalApi.importClusterDevices(file);
      setRows(data.rows);
      scheduleAutosave();
    } catch (e) {
      console.error('[Cluster devices] import failed:', e);
    } finally {
      setExporting(false);
    }
  };

  const handleUpdate = (rowId: string, field: ClusterEditableField, value: string | number | null) => {
    const apiField = FIELD_TO_API[field];
    const patch: Record<string, unknown> = { [apiField]: value };

    setRows((rs) => rs.map((r) => (r.row_id === rowId ? { ...r, [field]: value } : r)));

    const existing = pendingPatches.current.get(rowId) || {};
    pendingPatches.current.set(rowId, { ...existing, ...patch });

    const existingTimer = debounceTimers.current.get(rowId);
    if (existingTimer) clearTimeout(existingTimer);

    const timer = setTimeout(async () => {
      const accumulated = pendingPatches.current.get(rowId);
      pendingPatches.current.delete(rowId);
      debounceTimers.current.delete(rowId);
      if (!accumulated) return;

      try {
        const updated = await proposalApi.updateClusterDevice(
          rowId,
          accumulated as Parameters<typeof proposalApi.updateClusterDevice>[1],
        );
        setRows((rs) => rs.map((r) => (r.row_id === rowId ? updated : r)));
        scheduleAutosave();
      } catch (e) {
        console.error('[Cluster devices] update failed:', e);
        load();
      }
    }, 500);

    debounceTimers.current.set(rowId, timer);
  };

  const handleDelete = async (rowId: string) => {
    const prev = rows;
    setRows((rs) => rs.filter((r) => r.row_id !== rowId));
    try {
      await proposalApi.deleteClusterDevice(rowId);
      scheduleAutosave();
    } catch (e) {
      setRows(prev);
      console.error('[Cluster devices] delete failed:', e);
    }
  };

  const isFirstOfGroup = (row: import('@/lib/proposal-api').ClusterDeviceRow, index: number) => {
    if (index === 0) return true;
    return rows[index - 1]?.source_net_plane_id !== row.source_net_plane_id;
  };

  const isSubRow = (row: import('@/lib/proposal-api').ClusterDeviceRow, index: number) => {
    return !isFirstOfGroup(row, index);
  };

  if (loading) {
    return (
      <ProposalChapterCard id="sec-ch-5-3" title="5.3 集群设备配置">
        <div className="p-8 text-center text-sm text-slate-400">加载中…</div>
      </ProposalChapterCard>
    );
  }

  return (
    <ProposalChapterCard id="sec-ch-5-3" title="5.3 集群设备配置">
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
            {rows.map((row, index) => {
              const sub = isSubRow(row, index);
              const parentRow = sub
                ? rows.find((r, i) => r.source_net_plane_id === row.source_net_plane_id && !isSubRow(r, i))
                : null;
              const parentQty = parentRow ? parentRow.quantity : row.quantity;
              const subRows = sub && parentRow
                ? rows.filter((r) => r.source_net_plane_id === row.source_net_plane_id && r.row_id !== parentRow.row_id)
                : [];
              const subTotal = subRows.reduce((s, r) => s + r.quantity, 0);
              const overAlloc = sub && subTotal > parentQty;
              return (
                <tr
                  key={row.row_id}
                  className="border-t border-slate-100 align-middle"
                >
                  <td className="px-1 py-1.5 text-center">
                    {!sub && (
                      <button
                        type="button"
                        onClick={() => row.source_net_plane_id && handleAdd(row.source_net_plane_id)}
                        disabled={!row.source_net_plane_id}
                        title="新增子行（拆分数量）"
                        className="grid h-5 w-5 place-items-center rounded text-xs text-slate-400 transition-colors hover:bg-blue-50 hover:text-blue-600"
                      >＋</button>
                    )}
                  </td>
                  <td className="px-2 py-1.5">
                    <input
                      value={row.cluster_id ?? ''}
                      onChange={(e) => handleUpdate(row.row_id, 'cluster_id', e.target.value)}
                      className={`${INPUT_CLS} font-mono text-xs`}
                      placeholder="必填"
                    />
                  </td>
                  <td className="px-2 py-1.5">
                    <select
                      value={row.cluster_type}
                      onChange={(e) => handleUpdate(row.row_id, 'cluster_type', e.target.value)}
                      className={SELECT_CLS}
                    >
                      {CLUSTER_TYPES.map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                  </td>
                  <td className="px-2 py-1.5">
                    <input value={row.super_pod_id ?? ''} onChange={(e) => handleUpdate(row.row_id, 'super_pod_id', e.target.value)} className={`${INPUT_CLS} font-mono text-xs`} />
                  </td>
                  <td className="px-2 py-1.5">
                    <input value={row.storage_cluster_id ?? ''} onChange={(e) => handleUpdate(row.row_id, 'storage_cluster_id', e.target.value)} className={`${INPUT_CLS} font-mono text-xs`} />
                  </td>
                  <td className="px-2 py-1.5">
                    <input value={row.zone_id ?? ''} onChange={(e) => handleUpdate(row.row_id, 'zone_id', e.target.value)} className={`${INPUT_CLS} font-mono text-xs`} />
                  </td>
                  <td className="px-2 py-1.5">
                    <input value={row.ccae_cluster_id ?? ''} onChange={(e) => handleUpdate(row.row_id, 'ccae_cluster_id', e.target.value)} className={`${INPUT_CLS} font-mono text-xs`} />
                  </td>
                  <td className="px-2 py-1.5">
                    <input value={row.dme_cluster_id ?? ''} onChange={(e) => handleUpdate(row.row_id, 'dme_cluster_id', e.target.value)} className={`${INPUT_CLS} font-mono text-xs`} />
                  </td>
                  <td className="px-2 py-1.5">
                    <input value={row.device_type} onChange={(e) => handleUpdate(row.row_id, 'device_type', e.target.value)} className={INPUT_CLS} placeholder="设备类型" />
                  </td>
                  <td className="px-2 py-1.5">
                    <div className={READONLY_CELL} title={row.vendor}>{row.vendor || '—'}</div>
                  </td>
                  <td className="px-2 py-1.5">
                    <div className={`${READONLY_CELL} font-mono`} title={row.device_model}>{row.device_model || '—'}</div>
                  </td>
                  <td className="px-2 py-1.5">
                    <input value={row.device_purpose ?? ''} onChange={(e) => handleUpdate(row.row_id, 'device_purpose', e.target.value)} className={INPUT_CLS} placeholder="TD 录入" />
                  </td>
                  <td className="px-2 py-1.5">
                    <input value={row.start_device_name ?? ''} onChange={(e) => handleUpdate(row.row_id, 'start_device_name', e.target.value)} placeholder="AT900A3-0001" className={`${INPUT_CLS} font-mono text-xs`} />
                  </td>
                  <td className="px-2 py-1.5">
                    <input value={row.end_device_name ?? ''} onChange={(e) => handleUpdate(row.row_id, 'end_device_name', e.target.value)} placeholder="AT900A3-0384" className={`${INPUT_CLS} font-mono text-xs`} />
                  </td>
                  <td className="px-2 py-1.5">
                    <input
                      type="number"
                      value={row.quantity}
                      min={0}
                      max={sub ? parentQty : undefined}
                      onChange={(e) => {
                        const v = e.target.value;
                        handleUpdate(row.row_id, 'quantity', v === '' ? 0 : parseInt(v, 10));
                      }}
                      className={`${INPUT_CLS} tabular-nums ${overAlloc ? 'border-red-300 bg-red-50' : ''}`}
                    />
                  </td>
                  <td className="px-1 py-1.5 text-center">
                    <button type="button" onClick={() => handleDelete(row.row_id)} title="删除此行" className={DEL_BTN_CLS}>✕</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex items-center justify-between">
        <div className="text-xs text-slate-500">
          共 {rows.length} 行 · 自动继承自 5.1 网络平面
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = '';
            if (file) void handleUpload(file);
          }}
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={exporting}
          className={`rounded-md border px-3 py-1.5 text-xs font-normal transition-colors ${
            exporting
              ? 'border-slate-200 text-slate-300 cursor-not-allowed'
              : 'border-green-300 text-green-600 hover:border-green-400 hover:bg-green-50'
          }`}
        >
          {exporting ? '上传中…' : '上传'}
        </button>
      </div>
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
