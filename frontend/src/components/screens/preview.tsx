// @ts-nocheck
'use client';

import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { workspaceNavigate } from '@/lib/workspace-nav-link';
import { JOURNEY_STAGES } from '../../data/journey-data';
import {
  PARSED_DEVICES, PARSED_SERVICES,
  SERVICE_CATEGORY_TONE, PART_TONE,
} from '../../data/contract-data';
import VersionBar, { bumpVersion } from '../version-bar';
import { useCurrentProject } from '@/lib/current-project';
import { agentBase } from '@/lib/runtimeBase';

/* 读 URL 参数 — 不用 useSearchParams 避免静态导出后 Suspense fallback=null 空白 */
function readUrlParam(key) {
  if (typeof window === 'undefined') return null;
  return new URLSearchParams(window.location.search).get(key);
}

function derivePreviewProjectCode(proposalId, project) {
  if (project?.projectCode) return project.projectCode;
  if (project?.code && !String(project.code).startsWith('PROP-')) return project.code;
  const tail = String(proposalId || project?.code || '').match(/-([A-Za-z0-9]+)$/);
  if (tail?.[1]) return tail[1];
  return project?.id || DEFAULT_PREVIEW_PROJECT.projectCode;
}

/* BOQ 当前文件清单：预览抽屉只展示用户点击的这一个文件 */
function boqAttachments(b) {
  if (!b) return [];
  const base = b.id.replace('BOQ-', '');
  return [
    { name: b.fileName || `${base}.xlsx`, ext: fileExt(b.fileName || b.name || `${base}.xlsx`) || 'xlsx', size: b.size || '184 KB', updatedAt: b.updatedAt || '2026-05-25', kind: 'BOQ 清单', path: b.sourcePath || '' },
  ];
}

const ATTACH_PREVIEWABLE = ['xlsx', 'xls', 'csv'];
const AGENT_BASE = import.meta.env.VITE_AGENT_BASE || 'http://127.0.0.1:7401';
const DEFAULT_PREVIEW_PROJECT = {
  proposalId: 'PROP-2026-K1903',
  projectName: '京东三期',
  projectCode: 'K1903',
};
const UNLINKED_CONTRACT_NO = '未关联合同';

function fileExt(name) {
  const value = String(name || '');
  if (!value.includes('.')) return '';
  return value.split('.').pop()?.toLowerCase() || '';
}

function previewBoqFileUrl(path) {
  return `${AGENT_BASE}/agent/preview/boq/file?path=${encodeURIComponent(path)}`;
}

function PreviewAssetPane({ asset }) {
  const [status, setStatus] = useState('idle');
  const [sheets, setSheets] = useState([]);
  const [activeSheet, setActiveSheet] = useState(0);
  const [textPreview, setTextPreview] = useState('');
  const [errMsg, setErrMsg] = useState('');

  useEffect(() => {
    if (!asset?.path) {
      setStatus('idle');
      setSheets([]);
      setTextPreview('');
      setErrMsg('');
      return;
    }

    let cancelled = false;
    setStatus('loading');
    setSheets([]);
    setActiveSheet(0);
    setTextPreview('');
    setErrMsg('');

    void (async () => {
      try {
        const resp = await fetch(previewBoqFileUrl(asset.path));
        if (!resp.ok) throw new Error(await errorMessage(resp));

        const ext = fileExt(asset.name);
        if (ext === 'xlsx' || ext === 'xls') {
          const buf = await resp.arrayBuffer();
          const XLSX = await import('xlsx');
          const wb = XLSX.read(buf, { type: 'array' });
          const out = wb.SheetNames.map((name) => ({
            name,
            html: XLSX.utils.sheet_to_html(wb.Sheets[name]),
          }));
          if (!cancelled) {
            setSheets(out);
            setStatus('ready');
          }
        } else if (ext === 'csv') {
          const text = await resp.text();
          if (!cancelled) {
            setTextPreview(text.split(/\r?\n/).slice(0, 80).join('\n'));
            setStatus('ready');
          }
        } else {
          if (!cancelled) setStatus('unsupported');
        }
      } catch (err) {
        if (!cancelled) {
          setStatus('error');
          setErrMsg(err instanceof Error ? err.message : String(err));
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [asset?.path, asset?.name]);

  if (!asset) {
    return (
      <div className="boq-file-preview-empty">
        选择一个 BOQ 文件后，将在这里展示当前文件预览。
      </div>
    );
  }

  if (!asset.path) {
    return (
      <div className="boq-file-preview-empty">
        该附件还没有接入文件源，暂不能在线预览或下载。
      </div>
    );
  }

  return (
    <div className="boq-file-preview">
      {status === 'loading' && <div className="boq-file-preview-empty">正在加载预览…</div>}
      {status === 'error' && <div className="boq-file-preview-empty">预览失败：{errMsg}</div>}
      {status === 'unsupported' && <div className="boq-file-preview-empty">该格式暂不支持在线预览，请直接下载查看。</div>}
      {status === 'ready' && sheets.length > 0 && (
        <>
          {sheets.length > 1 && (
            <div className="boq-sheet-tabs">
              {sheets.map((sheet, i) => (
                <button
                  key={sheet.name}
                  type="button"
                  className={`boq-sheet-tab${activeSheet === i ? ' on' : ''}`}
                  onClick={() => setActiveSheet(i)}
                >
                  {sheet.name}
                </button>
              ))}
            </div>
          )}
          <div className="boq-xlsx-preview" dangerouslySetInnerHTML={{ __html: sheets[activeSheet]?.html || '' }} />
        </>
      )}
      {status === 'ready' && textPreview && (
        <pre className="boq-text-preview">{textPreview}</pre>
      )}
    </div>
  );
}

const CONTRACT_MAP = {
  [DEFAULT_PREVIEW_PROJECT.proposalId]: [
    {
      contract_no: '1Y01012602830P',
      contract_name: '京东26年昇腾液冷超节点框架-宝德',
      order_version: 'V1.0',
      order_status: '已发布',
      created_date: '2026-02-06',
      published_date: '2026-06-12',
      revenue_trigger_ratio: 100,
    },
  ],
};

function revenueRatioLabel(ratio) {
  if (ratio === null || ratio === undefined || ratio === '') return '—';
  const value = Number(ratio);
  if (!Number.isFinite(value)) return String(ratio);
  return `${value}%`;
}

function formatUploadSize(size) {
  if (!Number.isFinite(size)) return '0 B';
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`;
  if (size >= 1024) return `${Math.round(size / 1024)} KB`;
  return `${size} B`;
}

function toPreviewBoq(record, index) {
  const filename = record?.filename || record?.path || `uploaded-${index + 1}.xlsx`;
  const sourceStatus = record?.status || '';
  return {
    id: record?.path || filename,
    name: filename,
    fileName: filename,
    size: formatUploadSize(Number(record?.size ?? 0)),
    updatedAt: record?.uploaded_at ? String(record.uploaded_at).slice(0, 10) : '—',
    boqVersion: record?.version || '手工上传',
    saleType: record?.sales_type || '上传文件',
    version: sourceStatus === '草稿' ? 'draft' : sourceStatus === '已发布' ? 'published' : 'uploaded',
    status: sourceStatus || '已上传',
    contractNo: record?.contract_no || UNLINKED_CONTRACT_NO,
    sourcePath: record?.path || '',
  };
}

async function errorMessage(resp) {
  try {
    const data = await resp.json();
    return data?.detail || `${resp.status} ${resp.statusText}`;
  } catch {
    return `${resp.status} ${resp.statusText}`;
  }
}

/* ── 起手式：合同+预案的"今天到底要做啥" ── */
function PreviewFocus({ tab }) {
  const map = {
    contract: '合同列表已自动按 3 个月内未交付筛选 · 展开关联 BOQ → 默认全选 → 确认后进入 BOQ 解析双表。',
    dtrb: 'DTRB v1.0 已生成（完整度 78%），第 5 章机房物理 2 处缺失等你补完后 → DRB。',
    drb: 'DRB v1.0 已生成（完整度 94%），等下周二客户评审会闭环。',
    lld: '合同已签署（CON-2026-K1903-001）。补充命名/网络/集成测试用例 → 冻结基线进入交付。',
  };
  const tone = tab === 'lld' ? 'green' : tab === 'drb' ? 'amber' : 'blue';
  return (
    <div className={`callout ${tone === 'green' ? 'green' : tone === 'amber' ? '' : 'info'}`} style={{ marginBottom: 14 }}>
      <span style={{ fontWeight: 700 }}>快速开始 · </span>
      {map[tab] || map.contract}
    </div>
  );
}

/* ── 合同 / BOQ tab（5.27 重做：合同列表 + 小三角下拉 + BOQ 默认全选 + 上传按钮） ── */
function ContractTab({ projectInfo }) {
  const proposalId = projectInfo.proposalId || DEFAULT_PREVIEW_PROJECT.proposalId;
  const boqUploadInputRef = useRef(null);
  const [openContracts, setOpenContracts] = useState({});
  /* BOQ 选中状态：默认全选 (AM-27) */
  const [selectedBoqs, setSelectedBoqs] = useState({});
  /* G-B · BOQ 预览抽屉（点行内"预览"按钮打开，不再就地展开子节） */
  const [previewBoq, setPreviewBoq] = useState(null);
  const [previewAsset, setPreviewAsset] = useState(null);
  /* P1 · 上传 BOQ 兜底 */
  const [uploadToast, setUploadToast] = useState(null);
  const [isUploadingBoq, setIsUploadingBoq] = useState(false);
  const [contractRecords, setContractRecords] = useState(() => CONTRACT_MAP[proposalId] || []);
  const [uploadedBoqs, setUploadedBoqs] = useState([]);
  /* BOQ 附件预览 / 下载操作提示 */
  const [attachToast, setAttachToast] = useState(null);
  const fireUploadToast = (msg, delay = 5200) => {
    setUploadToast(msg);
    window.clearTimeout(fireUploadToast._t);
    fireUploadToast._t = window.setTimeout(() => setUploadToast(null), delay);
  };
  const fireAttachToast = (msg) => {
    setAttachToast(msg);
    window.clearTimeout(fireAttachToast._t);
    fireAttachToast._t = window.setTimeout(() => setAttachToast(null), 2400);
  };

  const queriedBoqs = uploadedBoqs.map(toPreviewBoq);
  const usingQueriedBoqs = queriedBoqs.length > 0;
  const activeBoqs = queriedBoqs;
  const activeBoqById = Object.fromEntries(activeBoqs.map(b => [b.id, b]));
  const contractSeeds = contractRecords;
  const contractNos = new Set(contractSeeds.map(c => c.contract_no));
  const orphanBoqs = activeBoqs.filter(b => !contractNos.has(b.contractNo));
  const activeContracts = [
    ...contractSeeds.map(c => ({
      id: c.contract_no,
      name: c.contract_name,
      orderVersion: c.order_version,
      orderStatus: c.order_status,
      createdAt: c.created_date,
      publishedAt: c.published_date,
      revenueTriggerRatio: c.revenue_trigger_ratio,
      boqs: activeBoqs.filter(b => b.contractNo === c.contract_no),
    })),
    ...(orphanBoqs.length ? [{
      id: UNLINKED_CONTRACT_NO,
      name: '手工上传 / 未关联合同 BOQ',
      orderVersion: '—',
      orderStatus: '待关联',
      createdAt: '—',
      publishedAt: '—',
      revenueTriggerRatio: null,
      boqs: orphanBoqs,
    }] : []),
  ].filter(c => c.boqs.length > 0 || c.id !== UNLINKED_CONTRACT_NO);
  const totalContracts = activeContracts.length;
  const totalBoqs = activeBoqs.length;
  const selectedCount = activeBoqs.filter(b => selectedBoqs[b.id]).length;
  const toggleBoq = (id) =>
    setSelectedBoqs(s => ({ ...s, [id]: !s[id] }));
  const toggleContract = (id) =>
    setOpenContracts(s => ({ ...s, [id]: !s[id] }));
  const openBoqPreview = (boq) => {
    const firstAsset = boqAttachments(boq)[0] || null;
    setPreviewBoq(boq);
    setPreviewAsset(firstAsset);
  };
  const closeBoqPreview = () => {
    setPreviewBoq(null);
    setPreviewAsset(null);
  };
  const previewAttachment = (asset) => {
    if (!asset?.path) {
      fireAttachToast('该附件暂无可预览文件源');
      return;
    }
    setPreviewAsset(asset);
  };

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams({ proposal_id: proposalId });
    fetch(`${AGENT_BASE}/agent/preview/contracts?${params}`)
      .then(async (resp) => {
        if (!resp.ok) throw new Error(await errorMessage(resp));
        return resp.json();
      })
      .then((data) => {
        if (!cancelled && Array.isArray(data.contracts)) {
          setContractRecords(data.contracts);
        }
      })
      .catch(() => {
        if (!cancelled) setContractRecords(CONTRACT_MAP[proposalId] || []);
      });
    fetch(`${AGENT_BASE}/agent/preview/boq?${params}`)
      .then(async (resp) => {
        if (!resp.ok) throw new Error(await errorMessage(resp));
        return resp.json();
      })
      .then((data) => {
        if (!cancelled) setUploadedBoqs(Array.isArray(data.boq_files) ? data.boq_files : []);
      })
      .catch(() => {
        if (!cancelled) setUploadedBoqs([]);
      });
    return () => {
      cancelled = true;
    };
  }, [proposalId]);

  useEffect(() => {
    if (!usingQueriedBoqs) return;
    setSelectedBoqs(Object.fromEntries(queriedBoqs.map(b => [b.id, true])));
  }, [usingQueriedBoqs, uploadedBoqs]);

  const uploadBoqFiles = async (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    setIsUploadingBoq(true);
    fireUploadToast(files.length === 1 ? `正在上传 ${files[0].name}…` : `正在上传 ${files.length} 份 BOQ…`, 120000);
    try {
      const form = new FormData();
      form.append('proposal_id', proposalId);
      files.forEach(file => form.append('files', file));
      const resp = await fetch(`${AGENT_BASE}/agent/preview/boq/upload`, {
        method: 'POST',
        body: form,
      });
      if (!resp.ok) {
        throw new Error(await errorMessage(resp));
      }
      const data = await resp.json();
      setUploadedBoqs(Array.isArray(data.boq_files) ? data.boq_files : []);
      const uploadedCount = Array.isArray(data.uploaded) ? data.uploaded.length : files.length;
      fireUploadToast(`已上传 ${uploadedCount} 份 BOQ · ${data.proposal_id} 已关联 ${data.boq_files?.length ?? uploadedCount} 份 BOQ`);
    } catch (err) {
      fireUploadToast(`上传失败：${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsUploadingBoq(false);
      if (boqUploadInputRef.current) {
        boqUploadInputRef.current.value = '';
      }
    }
  };

  return (
    <>
      {/* SVG 校正：顶部项目信息单行表（机会点编码）*/}
      <div className="jn-panel">
        <div className="jn-panel-head" style={{ padding: '10px 0', textAlign: 'left' }}>
          项目信息
        </div>
        {/* 等宽列：▶空列(28) 定宽，其余 5 列在 fixed 布局下均分（不再用像素宽，避免窄屏挤成竖排）*/}
        <table className="vs-table proposal-link-table" style={{ tableLayout: 'fixed', width: '100%' }}>
          <colgroup>
            <col style={{ width: 28 }} />
            <col />
            <col />
            <col />
            <col />
          </colgroup>
          <thead>
            <tr>
              <th></th>
              <th>Proposal ID</th>
              <th>项目名称</th>
              <th>项目编码</th>
              <th>待交付合同</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td></td>
              <td className="num" style={{ fontFamily: 'var(--font-mono)' }} title={proposalId}>{proposalId}</td>
              <td title={projectInfo.projectName}>{projectInfo.projectName}</td>
              <td className="num" style={{ fontFamily: 'var(--font-mono)' }} title={projectInfo.projectCode}>{projectInfo.projectCode}</td>
              <td>{totalContracts}</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* 合同章节：contract-map 驱动合同头，boq-map 驱动关联 BOQ */}
      <div className="jn-panel">
        <div className="jn-panel-head" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
            <span>合同列表</span>
            <span style={{ fontSize: 12, color: 'var(--c-text-muted)' }}>合同 {totalContracts} 个</span>
            <span style={{ fontSize: 12, color: 'var(--c-text-muted)' }}>BOQ {totalBoqs} 份</span>
            <span style={{ fontSize: 12, color: selectedCount ? 'var(--c-brand, #1b84ff)' : 'var(--c-text-muted)' }}>
              已选 {selectedCount} 份
            </span>
          </div>
          <button
            type="button"
            className="inline-flex items-center gap-1.5 bg-blue-600 text-white hover:bg-blue-700 transition-all duration-200 px-5 py-2 rounded-lg text-sm font-normal"
            onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-1px)'; }}
            onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; }}
            title="没有关联合同时手动上传 BOQ（含草稿）"
            disabled={isUploadingBoq}
            onClick={() => boqUploadInputRef.current?.click()}
          >
            {isUploadingBoq ? '上传中…' : '↑ 上传 BOQ'}
          </button>
          <input
            ref={boqUploadInputRef}
            type="file"
            accept=".xlsx,.xls,.csv"
            multiple
            style={{ display: 'none' }}
            onChange={(event) => uploadBoqFiles(event.target.files)}
          />
        </div>

        <table className="vs-table contract-table" style={{ tableLayout: 'fixed', width: '100%' }}>
          <colgroup>
            <col style={{ width: 28 }} />
            <col />
            <col />
            <col style={{ width: 110 }} />
            <col style={{ width: 100 }} />
            <col style={{ width: 110 }} />
            <col style={{ width: 110 }} />
            <col />
            <col style={{ width: 56 }} />
          </colgroup>
          <thead>
            <tr>
              <th></th>
              <th>合同号</th>
              <th>合同名称</th>
              <th>订单版本号</th>
              <th>订单状态</th>
              <th>创建日期</th>
              <th>发布日期</th>
              <th>收入触发比例</th>
              <th>
                <input
                  type="checkbox"
                  checked={totalBoqs > 0 && selectedCount === totalBoqs}
                  disabled={totalBoqs === 0}
                  onChange={() => {
                    const next = !(totalBoqs > 0 && selectedCount === totalBoqs);
                    setSelectedBoqs(Object.fromEntries(activeBoqs.map(b => [b.id, next])));
                  }}
                  title="全选 / 取消全选"
                />
              </th>
            </tr>
          </thead>
          <tbody>
            {activeContracts.length === 0 ? (
              <tr>
                <td colSpan={9} style={{ padding: '18px 12px', color: 'var(--c-text-muted)', textAlign: 'center' }}>
                  暂无合同或 BOQ
                </td>
              </tr>
            ) : activeContracts.flatMap((contract) => {
              const open = !!openContracts[contract.id];
              const selectedHere = contract.boqs.filter(b => selectedBoqs[b.id]).length;
              const allSelected = contract.boqs.length > 0 && selectedHere === contract.boqs.length;
              const rows = [
                <tr key={contract.id} className="contract-row">
                  <td>
                    <button
                      type="button"
                      className={`tri${open ? ' open' : ''}`}
                      onClick={() => toggleContract(contract.id)}
                      title="展开 / 收起关联 BOQ"
                    >
                      ▶
                    </button>
                  </td>
                  <td className="num" style={{ fontFamily: 'var(--font-mono)' }} title={contract.id}>{contract.id}</td>
                  <td title={contract.name}>{contract.name}</td>
                  <td className="num" style={{ fontFamily: 'var(--font-mono)', color: 'var(--c-text-muted)' }} title={contract.orderVersion}>{contract.orderVersion}</td>
                  <td title={contract.orderStatus}>{contract.orderStatus}</td>
                  <td className="num" title={contract.createdAt}>{contract.createdAt}</td>
                  <td className="num" title={contract.publishedAt}>{contract.publishedAt}</td>
                  <td className="num" title={revenueRatioLabel(contract.revenueTriggerRatio)}>{revenueRatioLabel(contract.revenueTriggerRatio)}</td>
                  <td>
                    <input
                      type="checkbox"
                      checked={allSelected}
                      disabled={contract.boqs.length === 0}
                      onChange={() => {
                        const next = !allSelected;
                        setSelectedBoqs(s => {
                          const ns = { ...s };
                          contract.boqs.forEach(b => { ns[b.id] = next; });
                          return ns;
                        });
                      }}
                      title={`合同级选择 · ${selectedHere}/${contract.boqs.length} BOQ 已选`}
                    />
                  </td>
                </tr>,
              ];
              if (open) {
                rows.push(
                  <tr key={`${contract.id}-boqs`} className="contract-expand">
                    <td colSpan={9} style={{ padding: '2px 0 6px 0', borderLeft: '2px solid #e4e4e7' }}>
                      <table className="vs-table boq-hier-table" style={{ background: 'transparent', tableLayout: 'fixed', width: '100%' }}>
                        <colgroup>
                          <col style={{ width: 40 }} />
                          <col />
                          <col style={{ width: 150 }} />
                          <col style={{ width: 110 }} />
                          <col style={{ width: 110 }} />
                          <col style={{ width: 110 }} />
                          <col style={{ width: 100 }} />
                          <col style={{ width: 110 }} />
                        </colgroup>
                        <thead>
                          <tr>
                            <th>选择</th>
                            <th>BOQ 文件</th>
                            <th>合同号</th>
                            <th>版本号</th>
                            <th>销售类型</th>
                            <th>状态</th>
                            <th>大小</th>
                            <th>上传日期</th>
                          </tr>
                        </thead>
                        <tbody>
                          {contract.boqs.map((b) => {
                            const checked = !!selectedBoqs[b.id];
                            const statusText = checked ? b.status || '待解析' : '未选择';
                            const statusColor = checked ? 'var(--c-warning, #d97706)' : 'var(--c-text-muted)';
                            return (
                              <tr key={b.id} className="boq-hier-l1" style={{ background: checked ? 'rgba(27,132,255,.035)' : 'transparent' }}>
                                <td>
                                  <input
                                    type="checkbox"
                                    checked={checked}
                                    onChange={() => toggleBoq(b.id)}
                                  />
                                </td>
                                <td title={b.name}>
                                  <button
                                    type="button"
                                    onClick={() => openBoqPreview(b)}
                                    style={{
                                      padding: 0, border: 'none', background: 'none',
                                      color: '#2563eb', cursor: 'pointer', textAlign: 'left',
                                      font: 'inherit', maxWidth: '100%',
                                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                                    }}
                                    className="boq-name-link"
                                  >
                                    {b.name}
                                  </button>
                                </td>
                                <td className="num" style={{ fontFamily: 'var(--font-mono)' }} title={b.contractNo}>{b.contractNo}</td>
                                <td className="num" style={{ fontFamily: 'var(--font-mono)', color: 'var(--c-text-muted)' }}>{b.boqVersion || '—'}</td>
                                <td title={b.saleType}>{b.saleType}</td>
                                <td style={{ color: statusColor, fontSize: 12 }}>{statusText}</td>
                                <td className="num">{b.size}</td>
                                <td className="num">{b.updatedAt}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </td>
                  </tr>
                );
              }
              return rows;
            })}
          </tbody>
        </table>
      </div>

      {uploadToast && (
        <div className="boq-next-hint" style={{ borderColor: 'var(--c-brand, #1b84ff)' }}>
          <div className="boq-next-hint-ic">↑</div>
          <div className="boq-next-hint-body">
            <strong>BOQ 已上传</strong>
            <span>{uploadToast}</span>
          </div>
        </div>
      )}

      {attachToast && (
        <div className="boq-attach-toast">{attachToast}</div>
      )}

      {/* G-B · BOQ 预览抽屉（点行内"预览"按钮触发，分级展示子项与配套软件） */}
      {previewBoq && (
        <div className="boq-preview-mask" onClick={closeBoqPreview}>
          <aside className="boq-preview-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="boq-preview-head">
              <div>
                <div className="boq-preview-title">{previewBoq.name}</div>
              </div>
              <button className="boq-preview-close" onClick={closeBoqPreview} title="关闭">✕</button>
            </div>
            <div className="boq-preview-body">
              <div className="boq-current-file-card">
                <div className="boq-current-file-head">
                  <div className={`boq-attach-icon ext-${previewAsset?.ext || fileExt(previewBoq.name) || 'file'}`}>
                    {(previewAsset?.ext || fileExt(previewBoq.name) || 'FILE').toUpperCase()}
                  </div>
                  <div className="boq-current-file-meta">
                    <div className="boq-current-file-title" title={previewAsset?.name || previewBoq.name}>
                      {previewAsset?.name || previewBoq.name}
                    </div>
                    <div className="boq-attach-sub">
                      {previewAsset?.kind || 'BOQ 文件'} · {previewAsset?.size || previewBoq.size || '—'} · {previewAsset?.updatedAt || previewBoq.updatedAt || '—'}
                    </div>
                  </div>
                  <div className="boq-current-file-actions">
                    {previewAsset?.path ? (
                      <a
                        className="boq-attach-btn primary"
                        href={previewBoqFileUrl(previewAsset.path)}
                        download={previewAsset.name}
                      >
                        下载
                      </a>
                    ) : (
                      <button type="button" className="boq-attach-btn primary" disabled>
                        下载
                      </button>
                    )}
                  </div>
                </div>
                <PreviewAssetPane asset={previewAsset} />
              </div>

              <div className="boq-attach-listhead">
                <span>BOQ 文件与附件</span>
                <span className="boq-attach-count">{boqAttachments(previewBoq).length} 个文件</span>
              </div>
              <div className="boq-attach-list">
                {boqAttachments(previewBoq).map((att, i) => {
                  const canPreview = ATTACH_PREVIEWABLE.includes(att.ext) && !!att.path;
                  const selected = previewAsset?.name === att.name && previewAsset?.path === att.path;
                  return (
                    <div key={i} className={`boq-attach-row${selected ? ' active' : ''}`}>
                      <div className={`boq-attach-icon ext-${att.ext}`}>{att.ext.toUpperCase()}</div>
                      <div className="boq-attach-meta">
                        <div className="boq-attach-name" title={att.name}>{att.name}</div>
                        <div className="boq-attach-sub">{att.kind} · {att.size} · {att.updatedAt}</div>
                      </div>
                      <div className="boq-attach-actions">
                        <button
                          type="button"
                          className="boq-attach-btn"
                          disabled={!canPreview}
                          title={canPreview ? '在线预览' : '该附件暂无可预览文件源'}
                          onClick={() => previewAttachment(att)}
                        >
                          {selected ? '预览中' : '预览'}
                        </button>
                        {att.path ? (
                          <a
                            className="boq-attach-btn primary"
                            href={previewBoqFileUrl(att.path)}
                            download={att.name}
                            title="下载到本地"
                          >
                            下载
                          </a>
                        ) : (
                          <button type="button" className="boq-attach-btn primary" title="该附件暂无可下载文件源" disabled>
                            下载
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </aside>
        </div>
      )}
    </>
  );
}

/* 数据来源纯文字（去色） */
function DataSourceBadge({ source }) {
  return (
    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--c-text-muted)', fontFamily: 'var(--font-mono)' }}>
      {source || '—'}
    </span>
  );
}

/* G-11 · 厂商下拉候选（PD/TD 在解析后可改）· 选「自定义」后改用 input 手填 */
const VENDOR_OPTIONS = ['华为', 'Mellanox', 'Cisco', 'Intel', 'NVIDIA', '自定义'];


/* VendorChip 已移除（去色改造），仅保留下拉） */

/* 设备 BOQ 解析表 · 7 部件 + 编辑（R-3） + 数据来源徽章（R-8） */
function DeviceTable() {
  const groups = ['CPU', 'NPU', 'Mem', 'PCIe', 'DPU', 'Storage', 'Network'];
  /* 4 子 tab —— 软件配置已去掉（会议决策：干掉） */
  const subTabs = [
    { key: 'compute',  label: '算力底座配置', desc: 'CPU / NPU / Mem' },
    { key: 'intel',    label: '智算部件配置', desc: 'DPU / HBM' },
    { key: 'network',  label: '网络平面配置', desc: '业务 / 网管 / 存储' },
    { key: 'service',  label: '服务配置',     desc: '集成 / 维保（跳到右侧服务表）' },
  ];
  const [subTab, setSubTab] = useState('compute');
  /* R-3 · 表格可编辑：本地维护一份 rows 副本 */
  const [rows, setRows] = useState(PARSED_DEVICES);
  const [customVendorEditing, setCustomVendorEditing] = useState<Record<string, boolean>>({});

  const updateField = (code, key, val) =>
    setRows(rs => rs.map(r => r.code === code ? { ...r, [key]: val } : r));

  const onVendorChange = (code: string, v: string) => {
    if (v === '自定义') {
      setCustomVendorEditing(s => ({ ...s, [code]: true }));
      updateField(code, 'vendor', '');
    } else {
      setCustomVendorEditing(s => ({ ...s, [code]: false }));
      updateField(code, 'vendor', v);
    }
  };

  /* 按 sub tab 过滤显示的部件类型 */
  const visibleGroups = subTab === 'compute'  ? ['CPU', 'NPU', 'Mem']
                      : subTab === 'intel'    ? ['DPU', 'PCIe']
                      : subTab === 'network'  ? ['Network']
                      : ['Storage'];

  const byPart = Object.fromEntries(visibleGroups.map(p => [p, rows.filter(d => d.part === p)]));

  return (
    <>

      <div className="boq-subtabs">
        {subTabs.map(t => (
          <button
            key={t.key}
            className={`boq-subtab${subTab === t.key ? ' on' : ''}`}
            onClick={() => setSubTab(t.key)}
          >
            <span className="boq-subtab-label">{t.label}</span>
            <span className="boq-subtab-desc">{t.desc}</span>
          </button>
        ))}
      </div>


      {groups.map(p => {
        const list = byPart[p];
        if (!list) return null;
        return (
          <div key={p} className="device-part-group">
            <div className="device-part-head">
              <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--c-text-muted)', letterSpacing: '0.05em' }}>{p}</span>
              <span style={{ fontSize: 11, color: 'var(--c-text-faint)', marginLeft: 6 }}>{list.length} 项</span>
            </div>
            {/* 指令4后半：干掉 <table>，改紧凑 Flex 列表；编辑控件全保留 */}
            <div className="flex flex-col">
              {list.map(d => {
                const isHuawei = d.vendor === '华为';
                const noteRequired = !isHuawei;
                const noteEmpty = !d.note || !d.note.trim();
                const editing = customVendorEditing[d.code];
                const vendorIsCustom = d.vendor && !VENDOR_OPTIONS.includes(d.vendor) && d.vendor !== '华为';
                const selectValue = editing || vendorIsCustom ? '自定义' : (VENDOR_OPTIONS.includes(d.vendor) ? d.vendor : (d.vendor ? '自定义' : '华为'));
                const hasConflict = !!d.conflict;
                return (
                  <div
                    key={d.code}
                    className="flex items-center justify-between gap-3 py-2.5"
                    style={{ borderBottom: '1px solid #f4f4f5' }}
                  >
                    {/* 左：名称 + 编码 + 数据来源（+ 冲突附注，红色提示）*/}
                    <div className="min-w-0 flex-1">
                      <div className="text-sm truncate" style={{ color: '#27272a' }}>{d.name}</div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-xs text-zinc-400" style={{ fontFamily: 'var(--font-mono)' }}>{d.code}</span>
                        <DataSourceBadge source={d.dataSource} />
                      </div>
                    </div>
                    {/* 右：厂商 select + 数量 input + 备注 input（onChange/updateField 原样）*/}
                    <div className="flex items-center gap-2 shrink-0">
                      <div className="vendor-edit">
                        <select
                          value={selectValue}
                          onChange={(e) => onVendorChange(d.code, e.target.value)}
                          className="boq-vendor-select"
                          title="点选厂商；选「自定义」后可手填"
                        >
                          {VENDOR_OPTIONS.map(v => <option key={v} value={v}>{v}</option>)}
                        </select>
                        {(editing || vendorIsCustom) && (
                          <input
                            type="text"
                            value={d.vendor}
                            onChange={(e) => updateField(d.code, 'vendor', e.target.value)}
                            className="boq-vendor-input"
                            placeholder="手填厂商名"
                          />
                        )}
                      </div>
                      <input
                        type="number"
                        value={d.qty}
                        onChange={(e) => {
                          const v = parseInt(e.target.value, 10);
                          if (!Number.isNaN(v)) updateField(d.code, 'qty', v);
                        }}
                        className="boq-qty-input"
                        title="可编辑 · 修改后会同步进风险与计划"
                        style={{ width: 64, textAlign: 'right' }}
                      />
                      <input
                        type="text"
                        value={d.note}
                        onChange={(e) => updateField(d.code, 'note', e.target.value)}
                        className={`boq-note-input${noteRequired && noteEmpty ? ' required-empty' : ''}`}
                        placeholder={noteRequired ? '非华为厂商必填' : '—'}
                        required={noteRequired}
                        style={{ width: 150 }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </>
  );
}

/* 服务 BOQ 解析表 · 5 大类（AM-35） */
function ServiceTable() {
  const categories = ['算力集成', '算力使能优化', '智算上路', '维保', '培训'];
  const byCat = Object.fromEntries(categories.map(c => [c, PARSED_SERVICES.filter(s => s.category === c)]));

  return (
    <>

      {/* SVG 校正：服务表列 = 类型 / 服务型号 / 服务版本 / 数量 / 数据来源 */}
      <table className="vs-table service-table">
        <thead>
          <tr>
            <th>类型</th>
            <th>服务型号（编码）</th>
            <th>服务名称</th>
            <th>服务版本</th>
            <th className="num">数量</th>
            <th>数据来源</th>
          </tr>
        </thead>
        <tbody>
          {categories.flatMap(c => byCat[c].map((s, i) => (
            <tr key={s.code}>
              {i === 0 && (
                <td rowSpan={byCat[c].length} className="cat-cell">
                  <span className="inline-flex items-center px-2 py-1 rounded-md text-zinc-600 text-xs font-medium" style={{ background: '#fafafa', border: '1px solid #e4e4e7' }}>{c}</span>
                  <span className="cat-count">{byCat[c].length} 项</span>
                </td>
              )}
              <td className="num" style={{ fontFamily: 'var(--font-mono)' }}>{s.code}</td>
              <td>{s.name}</td>
              <td className="num" style={{ fontFamily: 'var(--font-mono)', color: 'var(--c-text-muted)' }}>V2.0</td>
              <td className="num"><strong>{s.qty}</strong> <span style={{ color: 'var(--c-text-faint)', fontSize: 11 }}>{s.unit}</span></td>
              <td>
                <DataSourceBadge source="人工" />
              </td>
            </tr>
          )))}
        </tbody>
      </table>
    </>
  );
}

/* ── 单个快照详情（DTRB / DRB）—— 接入 VersionBar ── */
function SnapshotDetail({ stageKey }) {
  const stage = JOURNEY_STAGES.find(s => s.key === stageKey);
  if (!stage?.snapshot) return <div className="callout">未找到快照数据</div>;
  const s = stage.snapshot;

  /* 5.27 G-5 版本控制 mock：从 v0.1 ~ 当前版本 */
  const latest = s.version?.replace(/^DTRB-|^DRB-/, '').replace(/^v/, 'v') || 'v1.0';
  const versions = ['v0.1', 'v0.2', 'v0.3', latest];
  const [currentVersion, setCurrentVersion] = useState(latest);
  const [dirty, setDirty] = useState(false);
  const [toast, setToast] = useState(null);
  const isReadonly = currentVersion !== latest;

  const handleSaveDraft = () => {
    setDirty(false);
    setToast('已保存草稿 · 版本号不变');
    setTimeout(() => setToast(null), 2500);
  };
  const handleConfirm = () => {
    const next = bumpVersion(latest);
    setDirty(false);
    setToast(`已确认 · 版本变为 ${next}`);
    setTimeout(() => setToast(null), 3500);
  };

  return (
    <>
      <VersionBar
        versions={versions}
        currentVersion={currentVersion}
        onSelectVersion={setCurrentVersion}
        onSaveDraft={handleSaveDraft}
        onConfirm={handleConfirm}
        dirty={dirty}
      />

      <div className="snap-meta">
        <div className="snap-meta-cell"><div className="k">版本</div><div className="v">{s.version}</div></div>
        <div className="snap-meta-cell"><div className="k">生成时间</div><div className="v">{s.ts}</div></div>
        <div className="snap-meta-cell"><div className="k">完整度</div><div className="v">{s.completeness}%</div></div>
        <div className="snap-meta-cell"><div className="k">章节</div><div className="v">{s.chapters?.length || s.diff?.length}</div></div>
      </div>

      <div className="jn-panel" style={{ marginBottom: 0 }}>
        <div className="jn-panel-head">{s.chapters ? '章节齐备情况' : '相比上一版本的差异'}</div>
        {s.chapters && (
          <div className="jn-chapters">
            {s.chapters.map(c => (
              <div key={c.name} className={`jn-chapter state-${c.state}`}>
                <span className="jn-chapter-name">{c.name}</span>
                {c.note && <span className="jn-chapter-note">{c.note}</span>}
                <span className={`jn-chapter-pill state-${c.state}`}>
                  {c.state === 'ok' ? '齐备' : c.state === 'partial' ? '部分' : '缺失'}
                </span>
                {!isReadonly && c.state !== 'ok' && (
                  <button className="btn-link" onClick={() => setDirty(true)}>编辑</button>
                )}
              </div>
            ))}
          </div>
        )}
        {s.diff && (
          <div className="jn-diff">
            {s.diff.map((d, i) => (
              <div key={i} className="jn-diff-row">
                <span className="jn-diff-ch">{d.ch}</span>
                <span style={{ color: 'var(--c-text-muted)' }}>→</span>
                <span className="jn-diff-change">{d.change}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {toast && <div className="sb-toast">{toast}</div>}
    </>
  );
}

/* ── 合同 LLD tab（合同事件触发后的最终快照）—— 接入 VersionBar ── */
function LLDTab() {
  const stage = JOURNEY_STAGES.find(s => s.key === 'contract');
  if (!stage) return null;
  const c = stage.contractEvent;
  const versions = ['v0.1', 'v0.2', 'v0.3', 'v1.0'];
  const [currentVersion, setCurrentVersion] = useState('v1.0');
  const [dirty, setDirty] = useState(false);

  return (
    <>
      <VersionBar
        versions={versions}
        currentVersion={currentVersion}
        onSelectVersion={setCurrentVersion}
        onSaveDraft={() => setDirty(false)}
        onConfirm={() => setDirty(false)}
        dirty={dirty}
      />

      <div className="snap-meta">
        <div className="snap-meta-cell"><div className="k">合同 ID</div><div className="v">{c.id}</div></div>
        <div className="snap-meta-cell"><div className="k">签署</div><div className="v">{c.signTs}</div></div>
        <div className="snap-meta-cell"><div className="k">合同金额</div><div className="v">{c.amount}</div></div>
        <div className="snap-meta-cell"><div className="k">里程碑</div><div className="v">{c.milestones} 项</div></div>
        {/* NEW-7 · PBI 字段（SVG L175）*/}
        <div className="snap-meta-cell"><div className="k">PBI</div><div className="v">PBI-K1903-{currentVersion.replace('v', '')} · 24 项</div></div>
      </div>

      {/* NEW-7 · PBI 详情面板（Product Backlog Item，TD 手动写）*/}
      <div className="jn-panel">
          <div className="jn-panel-head">PBI · 产品 Backlog（TD 手动维护）</div>
        <table className="vs-table">
          <thead>
            <tr><th>PBI ID</th><th>类型</th><th>标题</th><th>关联 LLD 章节</th><th>状态</th></tr>
          </thead>
          <tbody>
            <tr>
              <td className="num" style={{ fontFamily: 'var(--font-mono)' }}>PBI-001</td>
              <td><span className="status-pill amber">需求</span></td>
              <td>训练集群 384 节点 RDMA 全互联</td>
              <td>§6 网络规划</td>
              <td><span className="status-pill green">已确认</span></td>
            </tr>
            <tr>
              <td className="num" style={{ fontFamily: 'var(--font-mono)' }}>PBI-002</td>
              <td><span className="status-pill">技术</span></td>
              <td>k8s 1.30 LTS + NPU Operator 部署</td>
              <td>§7 平台版本</td>
              <td><span className="status-pill green">已确认</span></td>
            </tr>
            <tr>
              <td className="num" style={{ fontFamily: 'var(--font-mono)' }}>PBI-003</td>
              <td><span className="status-pill red">风险</span></td>
              <td>ConnectX-7 数量与 HLD 冲突</td>
              <td>§3 设备清单</td>
              <td><span className="status-pill amber">待 PD 确认</span></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="jn-panel">
        <div className="jn-panel-head">LLD 必要字段（合同事件后由 TD 补充）</div>
        <div className="jn-lld">
          {stage.lldFields.map(f => (
            <div key={f.k} className="jn-lld-row">
              <span className="k">{f.k}</span>
              <span className="v">{f.v}</span>
              <span className={`pill state-${f.state}`}>{f.state === 'ok' ? '已确认' : '待补'}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="callout green" style={{ marginTop: 14 }}>
        <span style={{ fontWeight: 700 }}>已冻结基线 · </span>
        交付方案（/design）已激活，进入交付作业五段（工勘 → 仿真 → 安装 → 调测 → 验收）。
      </div>
    </>
  );
}

/* SVG 校正：/preview 只承载合同条线；DTRB/DRB/LLD 三快照拆到 /proposal 路由 */
export default function PreviewScreen() {
  const { project } = useCurrentProject();
  const navigate = useNavigate();
  const proposalId =
    readUrlParam('proposal_id') ||
    readUrlParam('proposalId') ||
    readUrlParam('proposal') ||
    project?.proposalId ||
    (project?.code && String(project.code).startsWith('PROP-') ? project.code : null) ||
    DEFAULT_PREVIEW_PROJECT.proposalId;
  const projectName =
    readUrlParam('project_name') ||
    readUrlParam('projectName') ||
    project?.name ||
    DEFAULT_PREVIEW_PROJECT.projectName;
  const projectCode =
    readUrlParam('project_code') ||
    readUrlParam('projectCode') ||
    derivePreviewProjectCode(proposalId, project);

  const goProposal = () => workspaceNavigate(navigate, '/proposal', '/preview');

  return (
    <div className="jn-wrap preview-screen" style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
      <div className="main-inner" style={{ flex: 1 }}>
        <div className="page-head">
          <div>
            <h1>项目合同</h1>
          </div>
        </div>

        <ContractTab
          projectInfo={{ proposalId, projectName, projectCode }}
        />
      </div>

      <div className="action-footer">
        <span className="action-footer-hint">
          项目合同已就绪，可直接进入交付预案
        </span>
        <div className="action-footer-spacer" />
        <button
          type="button"
          className="bg-blue-600 text-white hover:bg-blue-700 transition-all duration-200 px-5 py-2.5 rounded-lg text-sm font-medium"
          onClick={goProposal}
          onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-1px)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; }}
        >
          进入交付预案 →
        </button>
      </div>
    </div>
  );
}
