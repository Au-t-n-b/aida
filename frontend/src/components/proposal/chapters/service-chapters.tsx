'use client';

import { Fragment, useCallback, useEffect, useState, type ReactNode } from 'react';
import {
  ProposalChapterCard,
  ProposalChapterHeader,
  ProposalDataTable,
  ProposalDataTableBody,
  ProposalDataTableHead,
} from '../primitives';
import {
  fetchMaintenanceSla,
  fetchMaintenanceStrategy,
  fetchServiceContent,
  fetchServiceDeliveryUi,
  getDefaultProjectId,
  initializeServiceDeliveryUi,
  parseMaintenanceBoq,
  parseMaintenanceProposalDoc,
  parseServiceBoq,
  patchMaintenanceSlaRow,
  patchMaintenanceStrategyRow,
  patchServiceDeliveryUiRow,
  ProposalApiError,
  shouldSilenceNoDataError,
  useProposalApiHeaders,
  type DeliveryChannel,
  type MaintenanceSlaRow,
  type MaintenanceStrategyRow,
  type ManifestActivity,
  type ServiceContentRow,
  type ServiceDeliveryUiRow,
} from '@/lib/proposal-api';

function EllipsisCell({ value, title }: { value: ReactNode; title?: string }) {
  const hoverTitle =
    title ??
    (typeof value === 'string' || typeof value === 'number' ? String(value) : undefined);
  return (
    <td className="proposal-cell-ellipsis" title={hoverTitle}>
      {value}
    </td>
  );
}

/* ── 8.1 服务交付界面（交付界面可选 华为/客户 · 接后端 API）── */
const DELIVERY_OPTIONS: DeliveryChannel[] = ['华为', '客户'];

export function ServiceDeliveryChapter({
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
  const [rows, setRows] = useState<ServiceDeliveryUiRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingRowId, setSavingRowId] = useState<string | null>(null);

  const loadRows = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let data = await fetchServiceDeliveryUi(projectId, headers, proposalVersion);
      if (proposalVersion === 'draft' && data.length === 0) {
        data = await initializeServiceDeliveryUi(projectId, headers);
      }
      setRows(data);
    } catch (err) {
      if (shouldSilenceNoDataError(err)) {
        setRows([]);
        setError(null);
        return;
      }
      const msg =
        err instanceof ProposalApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : '加载失败';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [headers, projectId, proposalVersion]);

  useEffect(() => {
    void loadRows();
  }, [loadRows]);

  const setChannel = async (row: ServiceDeliveryUiRow, value: DeliveryChannel) => {
    if (readOnly || row.deliveryChannel === value) return;
    const prev = rows;
    setRows((rs) =>
      rs.map((r) =>
        r.rowId === row.rowId
          ? { ...r, deliveryChannel: value, dataSource: '人工录入' as const }
          : r,
      ),
    );
    setSavingRowId(row.rowId);
    setError(null);
    try {
      const { row: updated, manifestActivity } = await patchServiceDeliveryUiRow(
        projectId,
        row.rowId,
        value,
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
    <ProposalChapterCard id="sec-7-1" title="8.1 服务交付界面">
      {error && (
        <div className="mb-2 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {error}
          <button
            type="button"
            className="ml-2 underline"
            onClick={() => void loadRows()}
          >
            重试
          </button>
        </div>
      )}
      {loading ? (
        <p className="text-sm text-slate-500">加载中…</p>
      ) : (
        <ProposalDataTable leftAlign>
          <ProposalDataTableHead>
            <tr>
              <th>服务大类</th>
              <th>服务细项</th>
              <th>交付界面</th>
            </tr>
          </ProposalDataTableHead>
          <ProposalDataTableBody>
            {rows.map((row) => (
              <tr key={row.rowId}>
                <td>{row.serviceMajor}</td>
                <td>{row.serviceItem}</td>
                <td className="px-2 py-1">
                  <select
                    value={row.deliveryChannel}
                    disabled={readOnly || savingRowId === row.rowId}
                    onChange={(e) => void setChannel(row, e.target.value as DeliveryChannel)}
                    title="选择交付界面"
                    className="cursor-pointer rounded border border-transparent bg-transparent px-2 py-1 text-sm text-slate-700 transition-colors hover:border-slate-200 focus:border-blue-400 focus:bg-white focus:outline-none disabled:opacity-60"
                  >
                    {DELIVERY_OPTIONS.map((o) => (
                      <option key={o} value={o}>{o}</option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </ProposalDataTableBody>
        </ProposalDataTable>
      )}
    </ProposalChapterCard>
  );
}

/* ── 8.2 服务配置（分组树，默认折叠 · 接后端 API）── */
export function ServiceContentChapter({
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
  const [l1Rows, setL1Rows] = useState<ServiceContentRow[]>([]);
  const [childrenByParent, setChildrenByParent] = useState<Record<string, ServiceContentRow[]>>({});
  const [open, setOpen] = useState<Set<string>>(() => new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadL1 = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let { rows } = await fetchServiceContent(projectId, headers, {
        collapse: true,
        version: proposalVersion,
      });
      if (proposalVersion === 'draft' && rows.length === 0) {
        const parsed = await parseServiceBoq(projectId, headers);
        rows = parsed.rows.filter((r) => r.rowLevel === 'L1');
      }
      setL1Rows(rows);
    } catch (err) {
      if (shouldSilenceNoDataError(err)) {
        setL1Rows([]);
        setError(null);
        return;
      }
      const msg =
        err instanceof ProposalApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : '加载失败';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [headers, projectId, proposalVersion]);

  useEffect(() => {
    void loadL1();
  }, [loadL1]);

  const toggle = async (row: ServiceContentRow) => {
    const rowId = row.rowId;
    if (open.has(rowId)) {
      setOpen((s) => {
        const n = new Set(s);
        n.delete(rowId);
        return n;
      });
      return;
    }
    if (!childrenByParent[rowId]) {
      try {
        const { rows } = await fetchServiceContent(projectId, headers, {
          collapse: false,
          expandOfferingId: rowId,
          version: proposalVersion,
        });
        const children = rows.filter((r) => r.rowLevel === 'L2');
        setChildrenByParent((prev) => ({ ...prev, [rowId]: children }));
      } catch (err) {
        if (shouldSilenceNoDataError(err)) {
          setChildrenByParent((prev) => ({ ...prev, [rowId]: [] }));
          setError(null);
          return;
        }
        const msg =
          err instanceof ProposalApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : '展开失败';
        setError(msg);
        return;
      }
    }
    setOpen((s) => new Set(s).add(rowId));
  };

  return (
    <ProposalChapterCard id="sec-7-2" title="8.2 服务配置">
      {error && (
        <div className="mb-2 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {error}
          <button type="button" className="ml-2 underline" onClick={() => void loadL1()}>
            重试
          </button>
        </div>
      )}
      {loading ? (
        <p className="text-sm text-slate-500">加载中…</p>
      ) : (
        <div className="overflow-hidden rounded-md border border-slate-100">
          <table className="w-full border-collapse text-sm">
            <colgroup>
              <col />
              <col style={{ width: 90 }} />
              <col style={{ width: 70 }} />
            </colgroup>
            <thead>
              <tr className="bg-slate-50/90 text-left text-sm text-slate-700">
                <th className="px-3 py-2.5 font-semibold">服务内容</th>
                <th className="px-3 py-2.5 font-semibold">数量</th>
                <th className="px-3 py-2.5 font-semibold">单位</th>
              </tr>
            </thead>
            <tbody>
              {l1Rows.map((g) => (
                <Fragment key={g.rowId}>
                  <tr
                    className="cursor-pointer border-t border-slate-100 bg-slate-50/40 hover:bg-slate-100/60"
                    onClick={() => void toggle(g)}
                  >
                    <td className="px-3 py-2.5 font-medium text-slate-700">
                      <span
                        className="mr-1.5 inline-block text-slate-400"
                        style={{
                          transform: open.has(g.rowId) ? 'rotate(0deg)' : 'rotate(-90deg)',
                          transition: 'transform .15s',
                        }}
                      >
                        ▼
                      </span>
                      {g.serviceContent}
                    </td>
                    <td className="px-3 py-2.5">{g.quantity}</td>
                    <td className="px-3 py-2.5">{g.unit || '—'}</td>
                  </tr>
                  {open.has(g.rowId) &&
                    (childrenByParent[g.rowId] ?? []).map((ch) => (
                      <tr key={ch.rowId} className="border-t border-slate-100">
                        <td className="py-2 pl-9 pr-3 text-slate-600">{ch.serviceContent}</td>
                        <td className="px-3 py-2">{ch.quantity}</td>
                        <td className="px-3 py-2">{ch.unit || '—'}</td>
                      </tr>
                    ))}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </ProposalChapterCard>
  );
}

/* ── 8.3 维保策略（接后端 API）── */
export function MaintStrategyChapter({
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
  const [rows, setRows] = useState<MaintenanceStrategyRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingRowId, setSavingRowId] = useState<string | null>(null);

  const loadRows = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let data = await fetchMaintenanceStrategy(projectId, headers, proposalVersion);
      if (proposalVersion === 'draft' && data.length === 0) {
        data = await parseMaintenanceBoq(projectId, headers);
      }
      setRows(data);
    } catch (err) {
      if (shouldSilenceNoDataError(err)) {
        setRows([]);
        setError(null);
        return;
      }
      const msg =
        err instanceof ProposalApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : '加载失败';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [headers, projectId, proposalVersion]);

  useEffect(() => {
    void loadRows();
  }, [loadRows]);

  const patchField = async (
    row: MaintenanceStrategyRow,
    body: Parameters<typeof patchMaintenanceStrategyRow>[2],
  ) => {
    if (readOnly) return;
    const prev = rows;
    setRows((rs) =>
      rs.map((r) => (r.rowId === row.rowId ? { ...r, ...body } as MaintenanceStrategyRow : r)),
    );
    setSavingRowId(row.rowId);
    setError(null);
    try {
      const { row: updated, manifestActivity } = await patchMaintenanceStrategyRow(
        projectId,
        row.rowId,
        body,
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
    <ProposalChapterCard id="sec-7-3" title="8.3 维保策略">
      {error && (
        <div className="mb-2 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {error}
          <button type="button" className="ml-2 underline" onClick={() => void loadRows()}>
            重试
          </button>
        </div>
      )}
      {loading ? (
        <p className="text-sm text-slate-500">加载中…</p>
      ) : (
        <ProposalDataTable equalCols leftAlign className="proposal-table-ellipsis">
          <ProposalDataTableHead>
            <tr>
              <th>产品型号</th>
              <th>保修策略</th>
              <th>维保策略</th>
              <th>开始时间</th>
              <th>结束时间</th>
              <th>EOS时间</th>
              <th>是否超EOS服务</th>
              <th>超EOS审批结论</th>
            </tr>
          </ProposalDataTableHead>
          <ProposalDataTableBody>
            {rows.map((m) => (
              <tr
                key={m.rowId}
                className={m.overEos === '是' ? 'bg-amber-50/50' : undefined}
              >
                <EllipsisCell value={m.productModel} />
                <EllipsisCell value={m.warrantyPolicy} />
                <EllipsisCell value={m.maintenancePolicy} />
                <td className="px-2 py-1">
                  <input
                    type="date"
                    value={m.maintStartDate}
                    disabled={readOnly || savingRowId === m.rowId}
                    onChange={(e) =>
                      void patchField(m, {
                        maintStartDate: e.target.value,
                        recalculateEnd: true,
                      })
                    }
                    className="w-full rounded border border-transparent bg-transparent px-1 py-1 text-sm disabled:opacity-60"
                  />
                </td>
                <EllipsisCell value={m.maintEndDate} />
                <td className="px-2 py-1">
                  <input
                    type="date"
                    value={m.productEosDate ?? ''}
                    disabled={readOnly || savingRowId === m.rowId}
                    onChange={(e) =>
                      void patchField(m, {
                        productEosDate: e.target.value || null,
                      })
                    }
                    className="w-full rounded border border-transparent bg-transparent px-1 py-1 text-sm disabled:opacity-60"
                  />
                </td>
                <EllipsisCell value={m.overEos} />
                <td className="px-2 py-1">
                  <input
                    type="text"
                    value={m.overEosApproval === '—' ? '' : m.overEosApproval}
                    disabled={readOnly || savingRowId === m.rowId}
                    placeholder="—"
                    onBlur={(e) => {
                      const v = e.target.value.trim() || '—';
                      if (v !== m.overEosApproval) {
                        void patchField(m, { overEosApproval: v });
                      }
                    }}
                    className="w-full rounded border border-transparent bg-transparent px-1 py-1 text-sm disabled:opacity-60"
                  />
                </td>
              </tr>
            ))}
          </ProposalDataTableBody>
        </ProposalDataTable>
      )}
    </ProposalChapterCard>
  );
}

export function ServiceChapterWrapper({
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
  return (
    <section id="sec-7">
      <ProposalChapterHeader title="8. 服务&维保信息" />
      <ServiceDeliveryChapter
        proposalVersion={proposalVersion}
        readOnly={readOnly}
        onDirty={onDirty}
        onManifestActivity={onManifestActivity}
      />
      <ServiceContentChapter
        proposalVersion={proposalVersion}
        readOnly={readOnly}
        onDirty={onDirty}
        onManifestActivity={onManifestActivity}
      />
      <MaintStrategyChapter
        proposalVersion={proposalVersion}
        readOnly={readOnly}
        onDirty={onDirty}
        onManifestActivity={onManifestActivity}
      />
      <SlaChapter
        proposalVersion={proposalVersion}
        readOnly={readOnly}
        onDirty={onDirty}
        onManifestActivity={onManifestActivity}
      />
    </section>
  );
}

interface SlaServiceGroup {
  seq: string;
  serviceItem: string;
  rows: MaintenanceSlaRow[];
}

function groupSlaRowsByService(rows: MaintenanceSlaRow[]): SlaServiceGroup[] {
  const groups: SlaServiceGroup[] = [];
  for (const row of rows) {
    const serviceItem = row.serviceItem?.trim() || '—';
    const parsedSeq = row.seq?.trim();
    const last = groups[groups.length - 1];
    const sameGroup =
      last &&
      last.serviceItem === serviceItem &&
      (parsedSeq ? last.seq === parsedSeq : true);
    if (sameGroup) {
      last.rows.push(row);
    } else {
      groups.push({
        seq: parsedSeq || String(groups.length + 1),
        serviceItem,
        rows: [row],
      });
    }
  }
  return groups;
}

export function SlaChapter({
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
  const [rows, setRows] = useState<MaintenanceSlaRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingRowId, setSavingRowId] = useState<string | null>(null);
  const slaGroups = groupSlaRowsByService(rows);

  const loadSla = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let data = await fetchMaintenanceSla(projectId, headers, proposalVersion);
      if (proposalVersion === 'draft' && data.rows.length === 0) {
        data = await parseMaintenanceProposalDoc(projectId, headers);
      }
      setRows(data.rows);
    } catch (err) {
      if (shouldSilenceNoDataError(err)) {
        setRows([]);
        setError(null);
        return;
      }
      const msg =
        err instanceof ProposalApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : '加载失败';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [headers, projectId, proposalVersion]);

  useEffect(() => {
    void loadSla();
  }, [loadSla]);

  const patchField = async (
    row: MaintenanceSlaRow,
    body: Parameters<typeof patchMaintenanceSlaRow>[2],
  ) => {
    if (readOnly) return;
    const prev = rows;
    setRows((rs) =>
      rs.map((r) => (r.rowId === row.rowId ? { ...r, ...body } as MaintenanceSlaRow : r)),
    );
    setSavingRowId(row.rowId);
    setError(null);
    try {
      const { row: updated, manifestActivity } = await patchMaintenanceSlaRow(
        projectId,
        row.rowId,
        body,
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
    <ProposalChapterCard id="sec-7-4" title="8.4 维保SLA">
      {error && (
        <div className="mb-2 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {error}
          <button type="button" className="ml-2 underline" onClick={() => void loadSla()}>
            重试
          </button>
        </div>
      )}
      {loading ? (
        <p className="text-sm text-slate-500">加载中…</p>
      ) : (
        <ProposalDataTable
          leftAlign
          className="proposal-table-sla proposal-table-aligned min-w-[1080px] table-fixed"
        >
          <ProposalDataTableHead className="[&_th]:whitespace-nowrap">
            <tr>
              <th className="w-12">序号</th>
              <th className="w-[140px]">服务项目</th>
              <th>问题级别</th>
              <th>服务时段</th>
              <th>响应时间</th>
              <th>恢复时间</th>
              <th>解决时间</th>
            </tr>
          </ProposalDataTableHead>
          <ProposalDataTableBody>
            {slaGroups.flatMap((g) =>
              g.rows.map((s, ri) => (
                <tr key={s.rowId}>
                  {ri === 0 && (
                    <>
                      <td
                        rowSpan={g.rows.length}
                        className="whitespace-nowrap text-center text-slate-700"
                      >
                        {g.seq}
                      </td>
                      <td rowSpan={g.rows.length} className="font-medium text-slate-700">
                        {g.serviceItem}
                      </td>
                    </>
                  )}
                  <td className="text-slate-800">
                    {s.severityLevel?.trim() || 'NA'}
                  </td>
                  <td>
                    <input
                      type="text"
                      value={s.coveragePeriod}
                      disabled={readOnly || savingRowId === s.rowId}
                      onBlur={(e) => {
                        const v = e.target.value.trim();
                        if (v !== s.coveragePeriod) {
                          void patchField(s, { coveragePeriod: v });
                        }
                      }}
                      className="w-full rounded border border-transparent bg-transparent px-0 py-0 text-sm disabled:opacity-60"
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={s.responseTime}
                      disabled={readOnly || savingRowId === s.rowId}
                      onBlur={(e) => {
                        const v = e.target.value.trim();
                        if (v !== s.responseTime) {
                          void patchField(s, { responseTime: v });
                        }
                      }}
                      className="w-full rounded border border-transparent bg-transparent px-0 py-0 font-mono text-xs disabled:opacity-60"
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={s.restoreTime}
                      disabled={readOnly || savingRowId === s.rowId}
                      onBlur={(e) => {
                        const v = e.target.value.trim();
                        if (v !== s.restoreTime) {
                          void patchField(s, { restoreTime: v });
                        }
                      }}
                      className="w-full rounded border border-transparent bg-transparent px-0 py-0 font-mono text-xs disabled:opacity-60"
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={s.resolveTime}
                      disabled={readOnly || savingRowId === s.rowId}
                      onBlur={(e) => {
                        const v = e.target.value.trim();
                        if (v !== s.resolveTime) {
                          void patchField(s, { resolveTime: v });
                        }
                      }}
                      className="w-full rounded border border-transparent bg-transparent px-0 py-0 font-mono text-xs disabled:opacity-60"
                    />
                  </td>
                </tr>
              )),
            )}
          </ProposalDataTableBody>
        </ProposalDataTable>
      )}
    </ProposalChapterCard>
  );
}
