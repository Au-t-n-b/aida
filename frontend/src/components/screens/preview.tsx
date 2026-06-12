// @ts-nocheck
'use client';

import { useState, useEffect } from 'react';
import { JOURNEY_STAGES } from '../../data/journey-data';
import {
  CONTRACTS, BOQS, PARSED_DEVICES, PARSED_SERVICES,
  SERVICE_CATEGORY_TONE, PART_TONE,
} from '../../data/contract-data';
import VersionBar, { bumpVersion } from '../version-bar';

/* 读 URL 参数 — 不用 useSearchParams 避免静态导出后 Suspense fallback=null 空白 */
function readUrlParam(key) {
  if (typeof window === 'undefined') return null;
  return new URLSearchParams(window.location.search).get(key);
}

/* BOQ 关联附件清单（mock）：主清单 + 技术/报价/配置/拓扑等支撑文件，支持预览与下载 */
function boqAttachments(b) {
  if (!b) return [];
  const base = b.id.replace('BOQ-', '');
  return [
    { name: b.fileName || `${base}.xlsx`, ext: 'xlsx', size: b.size || '184 KB', updatedAt: b.updatedAt || '2026-05-25', kind: 'BOQ 清单' },
    { name: `${base} · 技术规格清单.xlsx`, ext: 'xlsx', size: '420 KB', updatedAt: '2026-05-20', kind: '技术清单' },
    { name: `${base} · 商务报价单.xlsx`, ext: 'xlsx', size: '96 KB', updatedAt: '2026-05-18', kind: '商务' },
    { name: `${base} · 配置明细.xlsx`, ext: 'xlsx', size: '312 KB', updatedAt: '2026-05-16', kind: '配置' },
    { name: `${base} · 组网清单.xlsx`, ext: 'xlsx', size: '188 KB', updatedAt: '2026-05-14', kind: '拓扑' },
  ];
}

const ATTACH_PREVIEWABLE = ['pdf', 'png', 'jpg', 'jpeg', 'xlsx', 'docx'];

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
function ContractTab({ onStateChange }) {
  /* 折叠状态：默认所有合同展开 */
  /* 默认全部收缩，点击三角才展开 BOQ 列表 */
  const [openContracts, setOpenContracts] = useState(() =>
    Object.fromEntries(CONTRACTS.map(c => [c.id, false]))
  );
  /* BOQ 选中状态：默认全选 (AM-27) */
  const [selectedBoqs, setSelectedBoqs] = useState(() =>
    Object.fromEntries(Object.keys(BOQS).map(id => [id, true]))
  );
  /* 切换确认后展示 BOQ 解析结果 */
  const [confirmed, setConfirmed] = useState(false);
  /* G-B · BOQ 预览抽屉（点行内"预览"按钮打开，不再就地展开子节） */
  const [previewBoq, setPreviewBoq] = useState(null);
  /* 解析结果双表当前 tab */
  const [resultTab, setResultTab] = useState('device'); // device | service
  /* NEW-4 · 解析进度条（进度 0→100，同步 ClawRail 4 拍消息） */
  const [parseProgress, setParseProgress] = useState(0); // 0-100
  const [parseStage, setParseStage] = useState('');      // 当前阶段名
  /* P2 · 收入触发比例列排序 */
  const [revSort, setRevSort] = useState('desc'); // desc | asc | none
  /* P1 · 上传 BOQ 兜底 */
  const [uploadToast, setUploadToast] = useState(null);
  /* BOQ 附件预览 / 下载操作提示 */
  const [attachToast, setAttachToast] = useState(null);
  const fireAttachToast = (msg) => {
    setAttachToast(msg);
    window.clearTimeout(fireAttachToast._t);
    fireAttachToast._t = window.setTimeout(() => setAttachToast(null), 2400);
  };

  const selectedCount = Object.values(selectedBoqs).filter(Boolean).length;
  const parseDone = confirmed && parseProgress === 100;  // 派生：解析完成后悬浮条让位给「进入交付预案」

  /* 把解析状态提升给父组件，驱动底部悬浮条 */
  useEffect(() => {
    onStateChange?.({ confirmed, parseProgress, selectedCount });
  }, [confirmed, parseProgress, selectedCount]);

  const toggleContract = (id) =>
    setOpenContracts(s => ({ ...s, [id]: !s[id] }));
  const toggleBoq = (id) =>
    setSelectedBoqs(s => ({ ...s, [id]: !s[id] }));

  const totalBoqs = Object.keys(BOQS).length;

  const sortedContracts = [...CONTRACTS].sort((a, b) => {
    if (revSort === 'none') return 0;
    const diff = (a.revenueTriggerPct ?? 0) - (b.revenueTriggerPct ?? 0);
    return revSort === 'desc' ? -diff : diff;
  });

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
            <col />
          </colgroup>
          <thead>
            <tr>
              <th></th>
              <th>Proposal ID</th>
              <th>项目名称</th>
              <th>项目编码</th>
              <th>客户</th>
              <th>待交付合同</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td></td>
              <td className="num" style={{ fontFamily: 'var(--font-mono)' }} title="PROP-2026-K1903">PROP-2026-K1903</td>
              <td title="京东三期">京东三期</td>
              <td className="num" style={{ fontFamily: 'var(--font-mono)' }} title="K1903">K1903</td>
              <td
                title="客户甲（华东）"
                style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
              >
                客户甲（华东）
              </td>
              <td>{CONTRACTS.length}</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* 合同列表卡（SVG 校正：列加项目编码 / 中标日期 / 合同状态 / 备注；BOQ 列改成 checkbox 选择）*/}
      <div className="jn-panel">
        <div className="jn-panel-head" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <span>合同列表</span>
          </div>
          <button
            className="inline-flex items-center gap-1.5 bg-blue-600 text-white hover:bg-blue-700 transition-all duration-200 px-5 py-2 rounded-lg text-sm font-normal"
            onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-1px)'; }}
            onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; }}
            title="没有关联合同时手动上传 BOQ（含草稿）"
            onClick={() => {
              const name = `BOQ-K1903-手工-${Date.now().toString(36).slice(-4)}.xlsx`;
              setUploadToast(`已上传 ${name} · 解析任务已挂起`);
              setTimeout(() => setUploadToast(null), 3200);
            }}
          >
            ↑ 上传 BOQ
          </button>
        </div>

        <table className="vs-table contract-table" style={{ tableLayout: 'fixed', width: '100%' }}>
          {/* ▶ 与「选择」列定宽，中间 7 个业务列等宽（table-layout:fixed 平分剩余空间）*/}
          <colgroup>
            <col style={{ width: 28 }} />
            <col />
            <col />
            <col />
            <col />
            <col />
            <col />
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
              <th>
                <button
                  type="button"
                  className="th-sort-btn"
                  style={{ fontWeight: 400 }}
                  onClick={() => setRevSort(s => (s === 'desc' ? 'asc' : s === 'asc' ? 'none' : 'desc'))}
                  title="按收入触发比例排序"
                >
                  收入触发比例
                </button>
              </th>
              <th>选择</th>
            </tr>
          </thead>
          <tbody>
            {sortedContracts.flatMap(c => {
              const open = !!openContracts[c.id];
              const boqs = c.boqs.map(id => BOQS[id]).filter(Boolean);
              const selectedHere = boqs.filter(b => selectedBoqs[b.id]).length;
              const allSelected = selectedHere === boqs.length;
              const out = [
                <tr key={c.id} className="contract-row">
                  <td>
                    <button
                      type="button"
                      className={`tri${open ? ' open' : ''}`}
                      onClick={() => toggleContract(c.id)}
                      title="展开 / 收起关联 BOQ"
                    >
                      ▶
                    </button>
                  </td>
                  <td className="num" style={{ fontFamily: 'var(--font-mono)' }} title={c.id}>{c.id}</td>
                  <td title={c.name}>{c.name}</td>
                  <td className="num" style={{ fontFamily: 'var(--font-mono)', color: 'var(--c-text-muted)' }} title={c.orderVersion}>{c.orderVersion}</td>
                  <td title={c.orderStatus}>{c.orderStatus}</td>
                  <td className="num" title={c.createdAt}>{c.createdAt}</td>
                  <td className="num" title={c.publishedAt}>{c.publishedAt}</td>
                  <td className="num" style={{ fontVariantNumeric: 'tabular-nums' }} title={`${c.revenueTriggerPct}%`}>{c.revenueTriggerPct}%</td>
                  <td>
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={() => {
                        const next = !allSelected;
                        setSelectedBoqs(s => {
                          const ns = { ...s };
                          boqs.forEach(b => { ns[b.id] = next; });
                          return ns;
                        });
                      }}
                      title={`合同级选择 · ${selectedHere}/${boqs.length} BOQ 已选`}
                    />
                  </td>
                </tr>
              ];
              if (open) {
                /* BOQ 展开行：colSpan=8 从第一列起，与父表 colgroup 完全对齐 */
                out.push(
                  <tr key={c.id + '-expand'} className="contract-expand">
                    <td colSpan={9} style={{ padding: '2px 0 6px 0', borderLeft: '2px solid #e4e4e7' }}>
                      <table className="vs-table boq-hier-table" style={{ background: 'transparent', tableLayout: 'fixed', width: '100%' }}>
                        {/* colgroup：选列定宽，名称 / 版本号 / 销售类型 / 状态 4 列等宽 */}
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
                            <th>名称</th>
                            <th>版本号</th>
                            <th>销售类型</th>
                            <th>状态</th>
                          </tr>
                        </thead>
                        <tbody>
                          {boqs.map((b) => {
                            const checked = !!selectedBoqs[b.id];
                            return (
                              <tr key={b.id} className="boq-hier-l1" style={{ background: 'transparent' }}>
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
                                    onClick={() => setPreviewBoq(b)}
                                    style={{
                                      padding: 0, border: 'none', background: 'none',
                                      color: '#60a5fa', cursor: 'pointer', textAlign: 'left',
                                      font: 'inherit', maxWidth: '100%',
                                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                                    }}
                                    className="boq-name-link"
                                  >
                                    {b.name}
                                  </button>
                                </td>
                                <td className="num" style={{ fontFamily: 'var(--font-mono)', color: 'var(--c-text-muted)' }} title={b.boqVersion || '—'}>
                                  {b.boqVersion || '—'}
                                </td>
                                <td style={{ fontSize: 12, color: 'var(--c-text-muted)' }} title={b.saleType}>{b.saleType}</td>
                                <td style={{ fontSize: 12, color: 'var(--c-text-muted)' }} title={b.version === 'draft' ? '草稿' : '已发布'}>
                                  {b.version === 'draft' ? '草稿' : '已发布'}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </td>
                  </tr>
                );
              }
              return out;
            })}
          </tbody>
        </table>

        {!parseDone && (
        <div style={{ display: 'none' }}>
          {/* 按钮已移至 PreviewScreen 底部 action-footer，保留 onClick 逻辑 */}
          <button
            id="boq-confirm-trigger"
            disabled={selectedCount === 0 || confirmed}
            onClick={() => {
              setConfirmed(true);
              setParseProgress(0);
              setParseStage('准备解析任务…');
              /* NEW-4 · 同步进度条（与下面 fire(...) 节拍对齐）*/
              const tick = (delay, pct, stage) => setTimeout(() => {
                setParseProgress(pct);
                setParseStage(stage);
              }, delay);
              tick(100,  10, '拉取 BOQ 文件…');
              tick(700,  25, '设备类解析中…');
              tick(1500, 55, '检测数据冲突…');
              tick(2600, 80, '服务类分类中…');
              tick(3700, 95, '写入风险列表…');
              tick(4700, 100, '解析完成');
              /* 解析完成后底部悬浮按钮自动出现，不弹窗打断用户 */
              /* G-9 · 异步进度推 ClawRail
               * 模拟 BOQ 解析流：清空 → 收到任务 → 拉取 → 解析 → 完成 */
              if (typeof window === 'undefined') return;
              const fire = (delay, detail) => setTimeout(() => {
                window.dispatchEvent(new CustomEvent('aida:progress', { detail }));
              }, delay);
              const selectedNames = Object.entries(selectedBoqs)
                .filter(([, v]) => v)
                .map(([id]) => BOQS[id]?.name)
                .filter(Boolean);
              fire(0, {
                role: 'user',
                body: `开始解析 ${selectedCount} 份 BOQ`,
              });
              fire(450, {
                role: 'ai',
                body: `收到 · 已挂起解析任务，依次拉取${selectedCount > 4 ? ` ${selectedCount} 份` : ''} BOQ 文件…`,
                reasoning: selectedNames.slice(0, 5).map((n, i) => ({
                  ix: String(i + 1), text: `Fetch · ${n}`,
                })),
              });
              fire(1500, {
                role: 'ai',
                body: '设备类 BOQ 已解析完毕，识别到 4 部件 8 项；其中 ConnectX-7 数量与 HLD 冲突，已挂"待确认"。',
                chips: ['CPU/NPU/Mem/PCIe', 'BOQ vs HLD 冲突'],
                actions: [
                  { label: '查看冲突项', kind: 'primary', icon: 'Eye' },
                ],
              });
              fire(2600, {
                role: 'ai',
                body: '服务类 BOQ 已分到 5 大类 · 共 9 行（算力集成 / 算力使能优化 / 智算上路 / 维保 / 培训）。解析完成。',
                chips: ['服务 5 大类'],
                actions: [
                  { label: '导出 BOM', kind: 'ghost', icon: 'Doc' },
                  { label: '推到 LLD', kind: 'primary' },
                ],
              });
              /* M-112 · 冲突项自动入 cockpit 风险列表 */
              fire(3700, {
                role: 'ai',
                body: '已把 ConnectX-7 数量冲突自动登记为「设计来源」风险，在 /cockpit 的风险预警面板可见。OCC 跨境数据出境项也已挂到「合规来源」。',
                chips: ['设计来源 +1', '合规来源 +1'],
                actions: [
                  { label: '去看风险预警', kind: 'primary', icon: 'Eye' },
                ],
              });
              /* R-10 · 解析全流程完成 → 提醒刷新页面 */
              fire(4700, {
                role: 'ai',
                body: '⚡ 全部解析任务已完成。请刷新本页面查看 7 部件最新数据；下方表格已支持数量与备注就地编辑。',
                chips: ['解析完成', 'HITL 可编辑'],
                actions: [
                  { label: '刷新页面看结果', kind: 'primary', icon: 'Eye' },
                  { label: '推到 LLD 出图', kind: 'ghost' },
                ],
              });
            }}
          >
            {confirmed ? '已确认' : '确认并解析 BOQ →'}
          </button>
        </div>
        )}
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

      {/* BOQ 双表：设备 / 服务 卡片切换（AM-30） */}
      {confirmed && (
        <div className="jn-panel">
          <div className="jn-panel-head" style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <span>BOQ 解析结果</span>
            <div className="flex items-center gap-6">
              <button
                onClick={() => setResultTab('device')}
                className={`pb-1 text-sm font-medium transition-colors ${resultTab === 'device' ? 'text-zinc-900' : 'text-zinc-500 hover:text-zinc-700'}`}
                style={{ background: 'none', border: 'none', borderBottom: resultTab === 'device' ? '2px solid #18181b' : '2px solid transparent', cursor: 'pointer' }}
              >
                设备 BOQ · {PARSED_DEVICES.length} 项
              </button>
              <button
                onClick={() => setResultTab('service')}
                className={`pb-1 text-sm font-medium transition-colors ${resultTab === 'service' ? 'text-zinc-900' : 'text-zinc-500 hover:text-zinc-700'}`}
                style={{ background: 'none', border: 'none', borderBottom: resultTab === 'service' ? '2px solid #18181b' : '2px solid transparent', cursor: 'pointer' }}
              >
                服务 BOQ · {PARSED_SERVICES.length} 项 · 5 大类
              </button>
            </div>
            <span style={{ flex: 1 }} />
            {/* 产品概览（5.30 减法：只保留 NPU 总数，删型号/散热/规模/设备类型识别）*/}
            <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 6, fontSize: 12, color: 'var(--c-text-muted)' }}>
              NPU 总数
              <strong style={{ fontFamily: 'var(--font-mono)', fontSize: 15, color: 'var(--c-text)' }}>
                {PARSED_DEVICES.filter(d => d.part === 'NPU').reduce((s, d) => s + d.qty, 0).toLocaleString()}
              </strong>
            </span>
          </div>

          {resultTab === 'device' && <DeviceTable />}
          {resultTab === 'service' && <ServiceTable />}
        </div>
      )}

      {/* G-B · BOQ 预览抽屉（点行内"预览"按钮触发，分级展示子项与配套软件） */}
      {previewBoq && (
        <div className="boq-preview-mask" onClick={() => setPreviewBoq(null)}>
          <aside className="boq-preview-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="boq-preview-head">
              <div>
                <div className="boq-preview-title">{previewBoq.name}</div>
                <div className="boq-preview-sub">
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{previewBoq.id}</span>
                  <span className={`status-pill ${previewBoq.version === 'draft' ? 'amber' : 'green'}`}>
                    {previewBoq.version === 'draft' ? '草稿' : '已发布'}
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--c-brand-text)' }}>
                    {previewBoq.boqVersion || '—'}
                  </span>
                </div>
              </div>
              <button className="boq-preview-close" onClick={() => setPreviewBoq(null)} title="关闭">✕</button>
            </div>
            <div className="boq-preview-body">
              <div className="boq-attach-listhead">
                <span>BOQ 附件清单</span>
                <span className="boq-attach-count">{boqAttachments(previewBoq).length} 个文件</span>
              </div>
              <div className="boq-attach-list">
                {boqAttachments(previewBoq).map((att, i) => {
                  const canPreview = ATTACH_PREVIEWABLE.includes(att.ext);
                  return (
                    <div key={i} className="boq-attach-row">
                      <div className={`boq-attach-icon ext-${att.ext}`}>{att.ext.toUpperCase()}</div>
                      <div className="boq-attach-meta">
                        <div className="boq-attach-name" title={att.name}>{att.name}</div>
                      </div>
                      <div className="boq-attach-actions">
                        <button
                          type="button"
                          className="boq-attach-btn"
                          disabled={!canPreview}
                          title={canPreview ? '在线预览' : '该格式暂不支持预览'}
                          onClick={() => fireAttachToast(`正在预览：${att.name}`)}
                        >
                          预览
                        </button>
                        <button
                          type="button"
                          className="boq-attach-btn primary"
                          title="下载到本地"
                          onClick={() => fireAttachToast(`开始下载：${att.name}`)}
                        >
                          下载
                        </button>
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
  const [boqState, setBoqState] = useState({ confirmed: false, parseProgress: 0, selectedCount: 0 });
  const parseDone = boqState.confirmed && boqState.parseProgress === 100;

  return (
    <div className="jn-wrap preview-screen" style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
      <div className="main-inner" style={{ flex: 1 }}>
        <div className="page-head">
          <div>
            <h1>项目合同</h1>
          </div>
        </div>

        <ContractTab onStateChange={setBoqState} />
      </div>

      {/* 确认前底部操作栏：居中显示「已选 N / M BOQ」+ 「确认并解析 BOQ →」*/}
      {!boqState.confirmed && boqState.selectedCount > 0 && (
        <div className="action-footer">
          <span className="action-footer-hint">
            已选 <strong style={{ color: 'var(--c-text)' }}>{boqState.selectedCount}</strong> / {Object.keys(BOQS).length} BOQ
          </span>
          <div className="action-footer-spacer" />
          <button
            type="button"
            className="bg-blue-600 text-white hover:bg-blue-700 transition-all duration-200 px-5 py-2.5 rounded-lg text-sm font-medium"
            onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-1px)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; }}
            onClick={() => { if (typeof window !== 'undefined') window.location.href = '/proposal'; }}
          >
            进入交付预案 →
          </button>
        </div>
      )}

      {/* 解析完成后底部悬浮条，取代原 ActionFooter */}
      {parseDone && (
        <div className="action-footer">
          <span className="action-footer-hint">
            已解析 <strong style={{ color: 'var(--c-text)' }}>{boqState.selectedCount}</strong> 份 BOQ，审视结果后可进入交付预案
          </span>
          <div className="action-footer-spacer" />
          <button
            type="button"
            className="bg-blue-600 text-white hover:bg-blue-700 transition-all duration-200 px-5 py-2.5 rounded-lg text-sm font-medium"
            onClick={() => { if (typeof window !== 'undefined') window.location.href = '/proposal'; }}
            onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-1px)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; }}
          >
            进入交付预案 →
          </button>
        </div>
      )}
    </div>
  );
}
