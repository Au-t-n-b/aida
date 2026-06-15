'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ProposalChapterCard,
  ProposalDataTable,
  ProposalDataTableBody,
  ProposalDataTableHead,
} from '../primitives';
import {
  deviceRowsNeedEnrichment,
  enrichDeviceInfo,
  fetchDeviceInfo,
  getDefaultProjectId,
  parseDeviceBoq,
  patchDeviceInfoRow,
  ProposalApiError,
  useProposalApiHeaders,
  type DeviceInfoRow,
  type ManifestActivity,
} from '@/lib/proposal-api';

function displayValue(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return 'NA';
  return String(value);
}

function EllipsisCell({ value }: { value: string | number | null | undefined }) {
  const text = displayValue(value);
  return (
    <td className="proposal-cell-ellipsis" title={text}>
      {text}
    </td>
  );
}

export function DeviceChapter({
  proposalVersion = 'draft',
  readOnly = false,
  onDirty,
  onManifestActivity,
}: {
  proposalVersion?: string;
  readOnly?: boolean;
  onDirty?: () => void;
  onManifestActivity?: (activity: ManifestActivity) => void;
}) {
  const headers = useProposalApiHeaders();
  const projectId = getDefaultProjectId();
  const [rows, setRows] = useState<DeviceInfoRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [enriching, setEnriching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enrichNotice, setEnrichNotice] = useState<string | null>(null);
  const [savingRowId, setSavingRowId] = useState<string | null>(null);
  const enrichStartedRef = useRef(false);
  const onDirtyRef = useRef(onDirty);
  onDirtyRef.current = onDirty;

  const runEnrichment = useCallback(
    async (currentRows: DeviceInfoRow[]) => {
      if (proposalVersion !== 'draft' || readOnly || !deviceRowsNeedEnrichment(currentRows)) {
        return;
      }
      setEnriching(true);
      setEnrichNotice('正在补全生命周期与 GA/EOM/EOS…');
      try {
        const data = await enrichDeviceInfo(projectId, headers, proposalVersion);
        setRows(data.rows);
        setEnrichNotice(null);
      } catch (err) {
        const msg =
          err instanceof ProposalApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : '生命周期补全失败';
        setEnrichNotice(msg);
      } finally {
        setEnriching(false);
      }
    },
    [headers, projectId, proposalVersion, readOnly],
  );

  const loadRows = useCallback(async () => {
    setLoading(true);
    setError(null);
    setEnrichNotice(null);
    enrichStartedRef.current = false;
    try {
      let data = await fetchDeviceInfo(projectId, headers, proposalVersion);
      if (proposalVersion === 'draft' && data.rows.length === 0) {
        data = await parseDeviceBoq(projectId, headers);
        onDirtyRef.current?.();
      }
      setRows(data.rows);
      setLoading(false);

      if (proposalVersion === 'draft' && deviceRowsNeedEnrichment(data.rows) && !enrichStartedRef.current) {
        enrichStartedRef.current = true;
        void runEnrichment(data.rows);
      }
    } catch (err) {
      const msg =
        err instanceof ProposalApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : '加载失败';
      setError(msg);
      setLoading(false);
    }
  }, [headers, projectId, proposalVersion, runEnrichment]);

  useEffect(() => {
    void loadRows();
  }, [loadRows]);

  const setQuantity = async (row: DeviceInfoRow, value: string) => {
    const nextQty = Number(value);
    if (readOnly || Number.isNaN(nextQty) || nextQty < 0 || nextQty === row.quantity) return;
    const prev = rows;
    setRows((rs) =>
      rs.map((r) =>
        r.rowId === row.rowId ? { ...r, quantity: nextQty, dataSource: '人工录入' } : r,
      ),
    );
    setSavingRowId(row.rowId);
    setError(null);
    try {
      const { row: updated, manifestActivity } = await patchDeviceInfoRow(
        projectId,
        row.rowId,
        { quantity: nextQty },
        headers,
      );
      setRows((rs) => rs.map((r) => (r.rowId === row.rowId ? updated : r)));
      onDirty?.();
      if (manifestActivity) onManifestActivity?.(manifestActivity);
    } catch (err) {
      setRows(prev);
      const msg =
        err instanceof ProposalApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : '保存失败';
      setError(msg);
    } finally {
      setSavingRowId(null);
    }
  };

  return (
    <ProposalChapterCard id="sec-ch-2" title="2. 设备配置信息">
      {error && (
        <div className="mb-2 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {error}
          <button type="button" className="ml-2 underline" onClick={() => void loadRows()}>
            重试
          </button>
        </div>
      )}
      {enrichNotice && !error && (
        <div className="mb-2 rounded border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
          {enrichNotice}
          {!enriching && (
            <button type="button" className="ml-2 underline" onClick={() => void runEnrichment(rows)}>
              重试补全
            </button>
          )}
        </div>
      )}
      {loading ? (
        <p className="text-sm text-slate-500">加载中…</p>
      ) : (
        <ProposalDataTable leftAlign compact>
          <ProposalDataTableHead>
            <tr>
              <th>设备型号</th>
              <th>产品编码</th>
              <th>版本</th>
              <th className="w-14 max-w-[3.5rem]">数量</th>
              <th className="num">设备U高</th>
              <th>生命周期</th>
              <th>GA实际</th>
              <th>GA计划</th>
              <th>EOM实际</th>
              <th>EOM计划</th>
              <th>EOS实际</th>
              <th>EOS计划</th>
              <th>来源</th>
            </tr>
          </ProposalDataTableHead>
          <ProposalDataTableBody>
            {rows.map((row) => (
              <tr key={row.rowId}>
                <EllipsisCell value={row.deviceModel} />
                <EllipsisCell value={row.productCode} />
                <EllipsisCell value={row.version || (enriching ? '…' : null)} />
                <td className="w-14 max-w-[3.5rem]">
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={row.quantity}
                    disabled={readOnly || savingRowId === row.rowId}
                    onChange={(e) => void setQuantity(row, e.target.value)}
                    className="w-12 max-w-full rounded border border-transparent bg-transparent px-1 py-1 text-left text-sm tabular-nums hover:border-slate-200 focus:border-blue-400 focus:bg-white focus:outline-none disabled:opacity-60"
                    title="数量"
                  />
                </td>
                <td className="num">{displayValue(row.deviceUHeight)}</td>
                <EllipsisCell value={row.lifecycleStatus || (enriching ? '…' : null)} />
                <EllipsisCell value={row.gaActualDate || (enriching ? '…' : null)} />
                <EllipsisCell value={row.gaPlanDate || (enriching ? '…' : null)} />
                <EllipsisCell value={row.eomActualDate || (enriching ? '…' : null)} />
                <EllipsisCell value={row.eomPlanDate || (enriching ? '…' : null)} />
                <EllipsisCell value={row.eosActualDate || (enriching ? '…' : null)} />
                <EllipsisCell value={row.eosPlanDate || (enriching ? '…' : null)} />
                <EllipsisCell value={row.dataSource} />
              </tr>
            ))}
          </ProposalDataTableBody>
        </ProposalDataTable>
      )}
    </ProposalChapterCard>
  );
}
