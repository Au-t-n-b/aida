// @ts-nocheck
/* 从 DS-1 / twin-world-export 整体移植，与项目里既有 screens/*.tsx 同等做法 — 保留 @ts-nocheck */
import React from 'react';
import { buildFirstLevelGantt, severityClass } from '@/lib/contingency-view';
import { getOntologyObjectEditableKeyField, isOntologyObjectFieldEditable, updateOntologyObjectField } from '@/lib/ontology-api';
/* AIDA · 数字孪生 — 本体决策报告内容 (信息栏)
   移植自 ontology-decision-brain 升级版：综合判定 + KPI + 拓扑/机柜图 +
   参数表 / QoS 表 / 验收表 + 容量条 + 行动工单 + 孪生入口
   决策态: decision = 'risk' | 'success'
*/
import { useState as useStateOR, useRef as useRefOR } from 'react';

/* ── 两张 SVG 图（原样保留，dangerouslySetInnerHTML 注入，避免 JSX 属性转换风险） ── */
const ONT_SVG_TOPO = `
<svg viewBox="0 0 900 312" role="img" aria-label="智算中心 Spine-Leaf 组网拓扑">
  <defs>
    <linearGradient id="gSpine" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3b82f6"/><stop offset="1" stop-color="#2563eb"/></linearGradient>
    <linearGradient id="gLeaf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#22b8d8"/><stop offset="1" stop-color="#0e9bbb"/></linearGradient>
    <linearGradient id="gPod" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#eef4ff"/></linearGradient>
  </defs>
  <rect x="372" y="8" width="156" height="30" rx="8" fill="#f1f5fb" stroke="#cbd8ea"/>
  <text x="450" y="27" text-anchor="middle" font-size="12" font-weight="700" fill="#475569">省际骨干网 / WAN 出口</text>
  <line x1="300" y1="62" x2="430" y2="38" stroke="#94a3b8" stroke-width="1.4" stroke-dasharray="4 4"/>
  <line x1="600" y1="62" x2="470" y2="38" stroke="#94a3b8" stroke-width="1.4" stroke-dasharray="4 4"/>
  <g font-size="12" font-weight="700" fill="#fff" text-anchor="middle">
    <rect x="225" y="62" width="150" height="40" rx="9" fill="url(#gSpine)"/>
    <text x="300" y="80">Spine-01</text><text x="300" y="95" font-size="9.5" font-weight="500" fill="#dbeafe">CE16800 · 400GE</text>
    <rect x="525" y="62" width="150" height="40" rx="9" fill="url(#gSpine)"/>
    <text x="600" y="80">Spine-02</text><text x="600" y="95" font-size="9.5" font-weight="500" fill="#dbeafe">CE16800 · 400GE</text>
  </g>
  <g stroke="#2f7df6" stroke-width="1.5" opacity="0.55">
    <line x1="300" y1="102" x2="150" y2="150"/><line x1="300" y1="102" x2="350" y2="150"/><line x1="300" y1="102" x2="550" y2="150"/><line x1="300" y1="102" x2="750" y2="150"/>
    <line x1="600" y1="102" x2="150" y2="150"/><line x1="600" y1="102" x2="350" y2="150"/><line x1="600" y1="102" x2="550" y2="150"/><line x1="600" y1="102" x2="750" y2="150"/>
  </g>
  <text x="218" y="132" font-size="9.5" font-weight="700" fill="#2563eb">200GE ×8</text>
  <g font-size="11.5" font-weight="700" fill="#fff" text-anchor="middle">
    <rect x="92" y="150" width="116" height="36" rx="8" fill="url(#gLeaf)"/><text x="150" y="167">Leaf-01</text><text x="150" y="180" font-size="9" font-weight="500" fill="#e0f7fc">CE8850</text>
    <rect x="292" y="150" width="116" height="36" rx="8" fill="url(#gLeaf)"/><text x="350" y="167">Leaf-02</text><text x="350" y="180" font-size="9" font-weight="500" fill="#e0f7fc">CE8850</text>
    <rect x="492" y="150" width="116" height="36" rx="8" fill="url(#gLeaf)"/><text x="550" y="167">Leaf-03</text><text x="550" y="180" font-size="9" font-weight="500" fill="#e0f7fc">CE8850</text>
    <rect x="692" y="150" width="116" height="36" rx="8" fill="url(#gLeaf)"/><text x="750" y="167">Leaf-04</text><text x="750" y="180" font-size="9" font-weight="500" fill="#e0f7fc">CE8850</text>
  </g>
  <g stroke="#19b8d8" stroke-width="1.8" opacity="0.6">
    <line x1="150" y1="186" x2="150" y2="234"/><line x1="350" y1="186" x2="350" y2="234"/><line x1="550" y1="186" x2="550" y2="234"/><line x1="750" y1="186" x2="750" y2="234"/>
  </g>
  <text x="160" y="214" font-size="9.5" font-weight="700" fill="#0e9bbb">100GE</text>
  <g text-anchor="middle">
    <g><rect x="78" y="234" width="144" height="62" rx="10" fill="url(#gPod)" stroke="#c3d4ee"/><rect x="78" y="234" width="144" height="18" rx="10" fill="#eef4ff"/><text x="150" y="247" font-size="10.5" font-weight="800" fill="#1e3a8a">智算 Pod-A</text><text x="150" y="270" font-size="10" font-weight="700" fill="#334155">Atlas 800 训练服务器</text><text x="150" y="285" font-size="9" fill="#64748b">昇腾 910B ×64</text></g>
    <g><rect x="278" y="234" width="144" height="62" rx="10" fill="url(#gPod)" stroke="#c3d4ee"/><rect x="278" y="234" width="144" height="18" rx="10" fill="#eef4ff"/><text x="350" y="247" font-size="10.5" font-weight="800" fill="#1e3a8a">智算 Pod-B</text><text x="350" y="270" font-size="10" font-weight="700" fill="#334155">Atlas 800 训练服务器</text><text x="350" y="285" font-size="9" fill="#64748b">昇腾 910B ×64</text></g>
    <g><rect x="478" y="234" width="144" height="62" rx="10" fill="url(#gPod)" stroke="#c3d4ee"/><rect x="478" y="234" width="144" height="18" rx="10" fill="#eef4ff"/><text x="550" y="247" font-size="10.5" font-weight="800" fill="#1e3a8a">智算 Pod-C</text><text x="550" y="270" font-size="10" font-weight="700" fill="#334155">Atlas 800 训练服务器</text><text x="550" y="285" font-size="9" fill="#64748b">昇腾 910B ×64</text></g>
    <g><rect x="678" y="234" width="144" height="62" rx="10" fill="url(#gPod)" stroke="#c3d4ee"/><rect x="678" y="234" width="144" height="18" rx="10" fill="#eef4ff"/><text x="750" y="247" font-size="10.5" font-weight="800" fill="#1e3a8a">存储/管理 Pod</text><text x="750" y="270" font-size="10" font-weight="700" fill="#334155">分布式存储 + 管理面</text><text x="750" y="285" font-size="9" fill="#64748b">OceanStor · OM</text></g>
  </g>
</svg>`;

const ONT_SVG_RACK = `
<svg viewBox="0 0 900 270" role="img" aria-label="机房机柜与设备分布">
  <defs><linearGradient id="gRack" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f7faff"/><stop offset="1" stop-color="#eaf1fb"/></linearGradient></defs>
  <g font-family="monospace">
    <rect x="40" y="20" width="180" height="230" rx="10" fill="url(#gRack)" stroke="#c3d4ee"/>
    <text x="130" y="38" text-anchor="middle" font-size="11" font-weight="800" fill="#1e3a8a">机柜 A · BJ-IDC-R12</text>
    <rect x="56" y="50" width="148" height="26" rx="5" fill="#3b82f6"/><text x="130" y="67" text-anchor="middle" font-size="10" font-weight="700" fill="#fff">Spine-01 CE16800</text>
    <rect x="56" y="82" width="148" height="26" rx="5" fill="#22b8d8"/><text x="130" y="99" text-anchor="middle" font-size="10" font-weight="700" fill="#fff">Leaf-01/02 CE8850</text>
    <rect x="56" y="114" width="148" height="58" rx="5" fill="#ede9fe" stroke="#c4b5fd"/><text x="130" y="138" text-anchor="middle" font-size="10" font-weight="800" fill="#5b21b6">Atlas 800 ×4</text><text x="130" y="154" text-anchor="middle" font-size="9" fill="#7c3aed">昇腾910B · 256卡</text>
    <rect x="56" y="178" width="148" height="26" rx="5" fill="#e2e8f0"/><text x="130" y="195" text-anchor="middle" font-size="9.5" font-weight="700" fill="#475569">存储/管理 2U</text>
    <text x="130" y="222" text-anchor="middle" font-size="9" fill="#64748b">功率 12.4kW / 16kW · 液冷</text>
    <text x="130" y="238" text-anchor="middle" font-size="9" fill="#16a34a" font-weight="700">容量充足</text>
    <rect x="240" y="20" width="180" height="230" rx="10" fill="url(#gRack)" stroke="#fcd9a6"/>
    <text x="330" y="38" text-anchor="middle" font-size="11" font-weight="800" fill="#92400e">机柜 B · BJ-IDC-R13</text>
    <rect x="256" y="50" width="148" height="26" rx="5" fill="#f59e0b"/><text x="330" y="67" text-anchor="middle" font-size="10" font-weight="700" fill="#fff">SW-Core-BJ-02 ⚠</text>
    <rect x="256" y="82" width="148" height="26" rx="5" fill="#22b8d8"/><text x="330" y="99" text-anchor="middle" font-size="10" font-weight="700" fill="#fff">Leaf-03/04 CE8850</text>
    <rect x="256" y="114" width="148" height="58" rx="5" fill="#ede9fe" stroke="#c4b5fd"/><text x="330" y="138" text-anchor="middle" font-size="10" font-weight="800" fill="#5b21b6">Atlas 800 ×4</text><text x="330" y="154" text-anchor="middle" font-size="9" fill="#7c3aed">昇腾910B · 256卡</text>
    <rect x="256" y="178" width="148" height="26" rx="5" fill="#e2e8f0"/><text x="330" y="195" text-anchor="middle" font-size="9.5" font-weight="700" fill="#475569">存储/管理 2U</text>
    <text x="330" y="222" text-anchor="middle" font-size="9" fill="#64748b">功率 13.1kW / 16kW · 液冷</text>
    <text x="330" y="238" text-anchor="middle" font-size="9" fill="#d97706" font-weight="700">100G 光口缺口</text>
    <rect x="452" y="28" width="408" height="214" rx="10" fill="#fbfdff" stroke="#e6edf6"/>
    <text x="470" y="50" font-size="11" font-weight="800" fill="#1e293b" font-family="inherit">端口与算力容量比对</text>
    <g font-family="inherit" font-size="9.5">
      <text x="470" y="78" fill="#475569" font-weight="700">SW-Core-BJ-02 · 100GE 光口</text>
      <rect x="470" y="84" width="300" height="9" rx="5" fill="#eef2f8"/><rect x="470" y="84" width="300" height="9" rx="5" fill="#f59e0b"/><rect x="710" y="84" width="60" height="9" rx="5" fill="#ef4444"/>
      <text x="790" y="92" fill="#d97706" font-weight="800">需8/余4</text>
      <text x="470" y="118" fill="#475569" font-weight="700">Leaf 集群 · 100GE 接入口</text>
      <rect x="470" y="124" width="300" height="9" rx="5" fill="#eef2f8"/><rect x="470" y="124" width="186" height="9" rx="5" fill="#10b981"/>
      <text x="790" y="132" fill="#059669" font-weight="800">62%</text>
      <text x="470" y="158" fill="#475569" font-weight="700">昇腾 910B 算力 (256卡)</text>
      <rect x="470" y="164" width="300" height="9" rx="5" fill="#eef2f8"/><rect x="470" y="164" width="300" height="9" rx="5" fill="#10b981"/>
      <text x="790" y="172" fill="#059669" font-weight="800">100%</text>
      <text x="470" y="198" fill="#475569" font-weight="700">机柜电力 / 散热预算</text>
      <rect x="470" y="204" width="300" height="9" rx="5" fill="#eef2f8"/><rect x="470" y="204" width="246" height="9" rx="5" fill="#10b981"/>
      <text x="790" y="212" fill="#059669" font-weight="800">82%</text>
      <text x="470" y="234" fill="#94a3b8">注：红色区段为本次组网策略产生的额外占用需求</text>
    </g>
  </g>
</svg>`;

/* ── 小图标 ── */
const IcWarnTri = ({ s = 19  }: any) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>);
const IcCheck = ({ s = 19  }: any) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>);
const IcUser = () => (<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>);
const IcSend = () => (<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg>);
const IcTrace = ({ s = 13  }: any) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><circle cx="6" cy="6" r="3" /><circle cx="18" cy="18" r="3" /><path d="M6 9v3a6 6 0 0 0 6 6h3" /></svg>);
/* ── 每章工具条图标：编辑（铅笔） ── */
const IcEdit = ({ s = 13  }: any) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9" /><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" /></svg>);

const Pill = ({ kind, children  }: any) => <span className={`ont-pill ${kind}`}>{children}</span>;
const Ubar = ({ fill, pct, label  }: any) => (
  <div className="ont-ubar"><span className="ont-track"><span className={`ont-fill ${fill}`} style={{ width: pct }} /></span><span className="ont-uv">{label}</span></div>
);

/* ── 章节/区块可编辑能力（编辑），与预制演示 digital-twin.html 的 .sec-tools 对齐 ──
   编辑：把正文切到 contentEditable，可直接改文字（演示态，不写回本体）。
   图片 / 附件按钮已移除：资料类输入统一走上游预案提取（文件上传 → 解析进本体），不再旁路挂前端临时态。
   抽成 hook + 子组件，供编号章节(DocSec) 与 综合判定 / 处置工单等已生成区块(EditableSection) 复用。 */
function useSectionTools(onToast: any) {
  const [editing, setEditing] = useStateOR<boolean>(false);
  const contentRef = useRefOR<any>(null);

  const toggleEdit = () => {
    const el = contentRef.current;
    const on = !editing;
    setEditing(on);
    if (el) {
      el.contentEditable = on ? 'true' : 'false';
      if (on) el.focus();
    }
    if (onToast) onToast(on ? '已进入编辑模式，可直接修改本节文字内容' : '本节修改已保存');
  };

  return { editing, toggleEdit, contentRef };
}

function SectionTools({ editing, onEdit }: any) {
  return (
    <div className="ont-sec-tools">
      <button type="button" className={'ont-sec-tool' + (editing ? ' on' : '')} onClick={onEdit} title="编辑本节内容"><IcEdit /><span>{editing ? '完成' : '编辑'}</span></button>
    </div>
  );
}

/* 编号章节包装：标题(不可编辑) + 正文(可编辑) + 工具条。 */
function DocSec({ id, idx, title, sub, st, active, children, onToast  }: any) {
  const t = useSectionTools(onToast);
  return (
    <div id={id} className={`ont-doc-sec${active ? ' active' : ''}${t.editing ? ' editing' : ''}`}>
      <SectionTools editing={t.editing} onEdit={t.toggleEdit} />
      <div className="ont-sec-title"><span className={`ont-idx${/^\d+$/.test(String(idx)) ? '' : ' ont-idx--label'}`}>{idx}</span>{title}{st && <span className={`ont-st ${st.cls}`}>{st.text}</span>}</div>
      {sub && <div className="ont-sec-sub">{sub}</div>}
      <div className="ont-sec-content" ref={t.contentRef} suppressContentEditableWarning>{children}</div>
    </div>
  );
}

/* 已生成区块包装（综合判定 / 处置任务工单 等非编号区块）：整块内容可编辑 + 工具条。
   保留各区块原 className（.ont-verdict / .ont-dispatch）与 id（doc-overall / doc-dispatch），
   不影响目录跳转 / active 高亮 / 导出。 */
function EditableSection({ id, className, active, onToast, children }: any) {
  const t = useSectionTools(onToast);
  return (
    <div id={id} className={className + (active ? ' active' : '') + (t.editing ? ' editing' : '')}>
      <SectionTools editing={t.editing} onEdit={t.toggleEdit} />
      <div className="ont-sec-editable" ref={t.contentRef} suppressContentEditableWarning>{children}</div>
    </div>
  );
}
const SubH = ({ children  }: any) => <div className="ont-subh">{children}</div>;
const Diagram = ({ svg, legend, cap  }: any) => (
  <div className="ont-diagram">
    <div className="ont-diagram-svg" dangerouslySetInnerHTML={{ __html: svg }} />
    {legend && <div className="ont-dleg">{legend.map((l: any, i: any) => <span key={i}><i style={{ background: l.c }} />{l.t}</span>)}</div>}
    <div className="ont-cap" dangerouslySetInnerHTML={{ __html: cap }} />
  </div>
);
const Alert = ({ title, children  }: any) => (
  <div className="ont-alert"><div className="ont-alert-title"><IcWarnTri s={15} />{title}</div><div className="ont-alert-desc">{children}</div></div>
);

/* ── 溯源跳章/跳行：滚动到源数据章节（或具体表行/风险卡）并闪烁高亮（复用 .ont-highlight 动画；
   scrollIntoView 滚动最近的可滚动祖先 .ont-drawer-body，与 TOC 跳章观感一致）。
   返回是否命中目标元素，调用方可用章节 id 兜底（行锚点在离线/裁剪时可能不存在）。 ── */
function jumpToReportSection(id: any): boolean {
  const el = document.getElementById(id);
  if (!el) return false;
  el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  el.classList.add('ont-highlight');
  setTimeout(() => el.classList.remove('ont-highlight'), 1600);
  return true;
}

/* 章节表行锚点 id：溯源主体 keyValue ↔ 行主键值（chapter.rowKeyField）一致，双方可互算。 */
const chapterRowAnchor = (chapterId: any, rowKey: any) => `${chapterId}-row-${rowKey}`;

/* ── 风险清单卡 ── */
function RiskCard({ rid, sev, av, title, domain, desc, owner, onDispatch, dispatched, provenance, chapterFor, anchorId  }: any) {
  const sevLabel = sev === 'high' ? '高危' : (sev === 'mid' ? '中危' : '低危');
  const adopted = dispatched === 'done';
  const adopting = dispatched === 'sending';
  // 推导溯源（规则 × 触发主体 × 证据）：后端 provenance 缺省（旧服务/预制演示）时不渲染入口。
  const [provOpen, setProvOpen] = useStateOR<boolean>(false);
  const prov = provenance && Array.isArray(provenance.subjects) && provenance.subjects.length ? provenance : null;
  const srcChapters: any[] = [];
  if (prov && chapterFor) {
    const seenType: any = {};
    for (const s of prov.subjects) {
      if (!s || !s.objectType || seenType[s.objectType]) continue;
      seenType[s.objectType] = 1;
      const ch = chapterFor(s.objectType);
      if (ch) srcChapters.push(ch);
    }
  }
  return (
    <div className="ont-act-card risk" id={anchorId || undefined}>
      <div className="ont-avatar risk">{av}</div>
      <div className="ont-act-main">
        <div className="ont-act-head">
          <div className="ont-act-title">{rid} · {title}</div>
          <span className={'ont-sev ' + sev}>{sevLabel}</span>
          <span className="ont-act-tag risk">{domain}</span>
        </div>
        <div className="ont-act-desc">{desc}</div>
        <div className="ont-act-meta"><IcUser />处置责任人：{owner}</div>
        {prov && (
          <div className="ont-prov">
            <button type="button" className={'ont-prov-toggle' + (provOpen ? ' on' : '')} onClick={() => setProvOpen(!provOpen)}>
              <IcTrace />推导溯源 · 规则 {prov.rule && (prov.rule.ruleId || prov.rule.riskPoint)} × {prov.subjects.length} 行事实
              <i className="ont-prov-caret">{provOpen ? '▲' : '▼'}</i>
            </button>
            {provOpen && (
              <div className="ont-prov-body">
                <div className="ont-prov-row">
                  <span className="ont-prov-chip">规则</span>
                  <b>{prov.rule.ruleName}</b>
                  <span className="ont-prov-dim">{prov.rule.riskPoint}{prov.rule.ruleId ? ' · ' + prov.rule.ruleId : ''} · {prov.rule.source}</span>
                </div>
                <div className="ont-prov-link">↓ 基准日 {prov.referenceDate} 在事实底座上命中 {prov.subjects.length} 行</div>
                {prov.subjects.map((s: any, i: number) => {
                  // 溯源跳行：主体 keyValue ↔ 章节表行锚点；行不存在（离线/被裁剪）退回跳章。
                  const srcCh = chapterFor && s.objectType ? chapterFor(s.objectType) : null;
                  const jump = srcCh
                    ? () => {
                        const hitRow = s.keyValue && jumpToReportSection(chapterRowAnchor(srcCh.id, s.keyValue));
                        if (!hitRow) jumpToReportSection(srcCh.id);
                      }
                    : undefined;
                  return (
                    <div key={i} className={'ont-prov-row' + (jump ? ' jump' : '')}
                      title={jump ? `定位到 §${srcCh.no} ${srcCh.title} 的源数据行` : undefined}
                      onClick={jump}>
                      <span className="ont-prov-chip fact">{s.objectTypeLabel || s.objectType}</span>
                      <b>{s.label}</b>
                      {s.keyValue && <span className="ont-prov-key">{s.keyValue}</span>}
                      <span className="ont-prov-reason">{s.reason}</span>
                    </div>
                  );
                })}
                {srcChapters.length > 0 && (
                  <div className="ont-prov-srcs">源数据：
                    {srcChapters.map((c: any) => (
                      <button key={c.id} type="button" className="ont-prov-srcbtn" onClick={() => jumpToReportSection(c.id)}>§{c.no} {c.title}</button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
      <div className="ont-act-btns">
        <button type="button" className={`ont-btn-dispatch${adopted ? ' done' : ' go'}`}
          onClick={(adopting || adopted) ? undefined : onDispatch}>
          {adopted ? <><IcCheck s={15} />已派发</> : adopting ? '派发中…' : <><IcSend />下发处理</>}
        </button>
      </div>
    </div>
  );
}

/* ── 行动工单卡 ── */
function ActCard({ type, av, title, tag, desc, owner, dispatched, onDispatch  }: any) {
  const avCls = type === 'risk' ? 'risk' : 'task';
  const cardCls = type === 'hold' ? 'task' : type;
  const tagCls = type === 'risk' ? 'risk' : 'task';
  return (
    <div className={`ont-act-card ${cardCls}`}>
      <div className={`ont-avatar ${avCls}`}>{av}</div>
      <div className="ont-act-main">
        <div className="ont-act-head"><div className="ont-act-title">{title}</div><span className={`ont-act-tag ${tagCls}`}>{tag}</span></div>
        <div className="ont-act-desc">{desc}</div>
        <div className="ont-act-meta"><IcUser />责任人：{owner}</div>
      </div>
      {type === 'hold'
        ? <button type="button" className="ont-btn-dispatch lock">系统管控</button>
        : <button type="button" className={`ont-btn-dispatch${dispatched === 'done' ? ' done' : ' go'}`} onClick={dispatched ? undefined : onDispatch}>
            {dispatched === 'done' ? <><IcCheck s={15} />已派发</> : dispatched === 'sending' ? '派发中…' : <><IcSend />一键派发</>}
          </button>}
    </div>
  );
}

/* ── 章节正文（ChapterNarrative）：AI 生成 + 人工可改 + 智能融合 + 版本历史 ──
   正文落 ChapterNarrative run-record overlay。人工改过的章重生成不覆盖（新稿入 pendingGenerated，
   由对比抽屉合并）。所有写操作经回调 onNarrative(action, chapterId, payload) 上交父组件真实写回；
   onNarrative 缺省（预制演示）时只读展示既有正文。 */
const _NARR_STATUS: any = {
  ai_draft: { t: 'AI 草稿', c: '#2f7df6', b: '#e8f1ff' },
  human_edited: { t: '人工修改', c: '#0a8a5f', b: '#e3f7ee' },
  merged: { t: '已融合', c: '#7a5af0', b: '#efeaff' },
  regen_pending: { t: '待合并', c: '#c2410c', b: '#fff0e6' },
};
const _NARR_SRC: any = { ai: 'AI', human: '人工', merge: '融合', restore: '回滚', milestone: '里程碑' };
const _narrBtn = (kind?: string): any => ({
  display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, fontWeight: 600,
  padding: '5px 11px', borderRadius: 7, cursor: 'pointer', lineHeight: 1.4, border: '1px solid',
  ...(kind === 'primary'
    ? { background: '#2f7df6', color: '#fff', borderColor: '#2f7df6' }
    : kind === 'warn'
      ? { background: '#ff8f1f', color: '#fff', borderColor: '#ff8f1f' }
      : { background: '#fff', color: '#3a4a63', borderColor: '#d4ddec' }),
});
const _narrPill = (info: any): any => ({
  fontSize: 10.5, fontWeight: 700, padding: '1px 7px', borderRadius: 999, color: info.c, background: info.b,
});
const _narrColTtl: any = { fontSize: 11, fontWeight: 700, color: '#64748b', marginBottom: 4 };
const _narrColBox: any = {
  fontSize: 12.5, lineHeight: 1.7, color: '#23344d', whiteSpace: 'pre-wrap', maxHeight: 160,
  overflow: 'auto', background: '#fff', border: '1px solid #eef2f8', borderRadius: 6, padding: 8,
};

function ChapterNarrative({ c, busy, onNarrative }: any) {
  const [editing, setEditing] = useStateOR<boolean>(false);
  const [draft, setDraft] = useStateOR<string>('');
  const [compareOpen, setCompareOpen] = useStateOR<boolean>(false);
  const [histOpen, setHistOpen] = useStateOR<boolean>(false);

  // 预制演示（无回调）：仅只读展示既有正文，不渲染编辑/生成控件。
  if (!onNarrative) {
    return c.narrative
      ? <p style={{ margin: '4px 0 8px', fontSize: 13, lineHeight: 1.8, color: '#23344d', whiteSpace: 'pre-wrap' }}>{c.narrative}</p>
      : null;
  }

  const status = c.narrativeStatus || (c.narrative ? 'ai_draft' : '');
  const statusInfo = _NARR_STATUS[status];
  const hasPending = !!(c.pendingGenerated || c.mergeCandidate || status === 'regen_pending');
  const versions: any[] = Array.isArray(c.versions) ? c.versions : [];
  const busyTxt = busy
    ? ({ generate: '生成中…', regenerate: '重生成中…', smartmerge: '融合中…', edit: '保存中…', accept: '采纳中…', restore: '回滚中…' } as any)[busy] || '处理中…'
    : '';

  const startEdit = () => { setDraft(c.narrative || ''); setEditing(true); };
  const saveEdit = () => { onNarrative('edit', c.id, { text: draft }); setEditing(false); };

  return (
    <div className="ont-narr" style={{ margin: '6px 0 12px', borderLeft: '3px solid #cfe0f6', paddingLeft: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
        <span style={{ fontSize: 11, fontWeight: 800, color: '#2f7df6', letterSpacing: '.05em' }}>章节正文</span>
        {statusInfo ? <span style={_narrPill(statusInfo)}>{statusInfo.t}</span> : null}
        {c.narrativeModel ? <span style={{ fontSize: 10, color: '#94a3b8' }}>· {c.narrativeModel}</span> : null}
        {hasPending ? <span style={{ ..._narrPill(_NARR_STATUS.regen_pending), cursor: 'pointer' }} onClick={() => setCompareOpen(true)}>● 有新版本待合并</span> : null}
        <span style={{ flex: 1 }} />
        {busyTxt ? <span style={{ fontSize: 11, color: '#64748b' }}>{busyTxt}</span> : null}
      </div>

      {editing ? (
        <div>
          <textarea value={draft} onChange={(e: any) => setDraft(e.target.value)} rows={6}
            style={{ width: '100%', boxSizing: 'border-box', fontSize: 13, lineHeight: 1.7, padding: 10, border: '1px solid #cfe0f6', borderRadius: 8, resize: 'vertical', fontFamily: 'inherit', color: '#23344d' }} />
          <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
            <button type="button" style={_narrBtn('primary')} onClick={saveEdit}>保存修改</button>
            <button type="button" style={_narrBtn()} onClick={() => setEditing(false)}>取消</button>
          </div>
        </div>
      ) : c.narrative ? (
        <p style={{ margin: 0, fontSize: 13, lineHeight: 1.8, color: '#23344d', whiteSpace: 'pre-wrap' }}>{c.narrative}</p>
      ) : (
        <p style={{ margin: 0, fontSize: 12.5, color: '#94a3b8', fontStyle: 'italic' }}>本章尚未生成文字描述。</p>
      )}

      {!editing ? (
        <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
          {c.narrative
            ? <button type="button" style={_narrBtn()} disabled={!!busy} onClick={startEdit}><IcEdit />编辑</button>
            : <button type="button" style={_narrBtn('primary')} disabled={!!busy} onClick={() => onNarrative('generate', c.id)}>生成本章正文</button>}
          {c.narrative ? <button type="button" style={_narrBtn()} disabled={!!busy} onClick={() => onNarrative('regenerate', c.id)}>重新生成</button> : null}
          {hasPending ? <button type="button" style={_narrBtn('warn')} disabled={!!busy} onClick={() => setCompareOpen(true)}>对比 / 合并</button> : null}
          {versions.length ? <button type="button" style={_narrBtn()} onClick={() => setHistOpen((v: boolean) => !v)}>历史 · {versions.length}</button> : null}
        </div>
      ) : null}

      {compareOpen ? (
        <div style={{ marginTop: 10, border: '1px solid #ffe0b2', background: '#fff9f0', borderRadius: 10, padding: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#b26a00', marginBottom: 8 }}>融合 · 保留人工改动并融入最新生成（人工稿在采纳前不会丢失）</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div>
              <div style={_narrColTtl}>我的（人工稿）</div>
              <div style={_narrColBox}>{c.narrativeEdited || c.narrative || '—'}</div>
            </div>
            <div>
              <div style={_narrColTtl}>{c.mergeCandidate ? '智能融合候选稿' : 'AI 新生成稿'}</div>
              <div style={_narrColBox}>{c.mergeCandidate || c.pendingGenerated || '—'}</div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
            <button type="button" style={_narrBtn('primary')} disabled={!!busy} onClick={() => onNarrative('smartmerge', c.id)}>智能融合</button>
            <button type="button" style={_narrBtn()} disabled={!!busy} onClick={() => { onNarrative('accept', c.id, { choice: 'mine' }); setCompareOpen(false); }}>保留我的</button>
            {c.pendingGenerated ? <button type="button" style={_narrBtn()} disabled={!!busy} onClick={() => { onNarrative('accept', c.id, { choice: 'new' }); setCompareOpen(false); }}>采纳新稿</button> : null}
            {c.mergeCandidate ? <button type="button" style={_narrBtn('warn')} disabled={!!busy} onClick={() => { onNarrative('accept', c.id, { choice: 'candidate' }); setCompareOpen(false); }}>采纳融合稿</button> : null}
            <span style={{ flex: 1 }} />
            <button type="button" style={_narrBtn()} onClick={() => setCompareOpen(false)}>关闭</button>
          </div>
        </div>
      ) : null}

      {histOpen && versions.length ? (
        <div style={{ marginTop: 8, border: '1px solid #e6edf6', borderRadius: 8, padding: '6px 10px' }}>
          {versions.slice().reverse().map((v: any) => (
            <div key={v.seq} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0', borderBottom: '1px dashed #eef2f8', fontSize: 12 }}>
              <span style={{ color: '#94a3b8', minWidth: 24 }}>#{v.seq}</span>
              <span style={_narrPill({ c: '#475569', b: '#eef2f8' })}>{_NARR_SRC[v.source] || v.source}</span>
              {v.versionLabel ? <span style={{ color: '#2f7df6', fontWeight: 600 }}>{v.versionLabel}</span> : null}
              <span style={{ color: '#94a3b8', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{(v.text || '').slice(0, 36)}</span>
              <button type="button" style={_narrBtn()} disabled={!!busy} onClick={() => onNarrative('restore', c.id, { seq: v.seq })}>回滚</button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/* =========================================================
   ContingencyReport — 后端真实「预案本体生成」报告
   章节由本体服务按《预案章节目录》生成（result.chapters），派生风险/任务按章绑定
   ========================================================= */

/* 章节数据表：把后端投影进 chapter.rows 的事实底座行（多台设备/部件…）按 chapter.columns 渲染。
   columns 缺省时回退用行自身的键当表头；空单元显示「—」。rows 为空则不渲染（交回字段标签兜底）。
   默认精简 + 命中追加：derived 列（风险证据字段，后端追加）表头带「命中」标识；riskCells 命中的
   单元格红色着色 + ⚠，title 显示溯源 reason，点击回跳对应风险卡；行锚点承接溯源跳行。
   预制演示/无风险时 riskCells 缺省，整表保持原精简渲染。 */
function ChapterRows({ chapter, onToast }: any) {
  const sourceRows: any[] = Array.isArray(chapter.rows) ? chapter.rows : [];
  const [editing, setEditing] = useStateOR<any>(null);
  const [savingKey, setSavingKey] = useStateOR('');
  const [rowOverrides, setRowOverrides] = useStateOR<Record<string, Record<string, any>>>({});
  const keyField: string = chapter.rowKeyField || getOntologyObjectEditableKeyField(chapter.objectType) || '';
  const rows: any[] = sourceRows.map((row: any) => {
    const rowKey = keyField ? String(row[keyField] ?? '') : '';
    return rowKey && rowOverrides[rowKey] ? { ...row, ...rowOverrides[rowKey] } : row;
  });

  if (!rows.length) return null;
  const cols: any[] = chapter.columns && chapter.columns.length
    ? chapter.columns
    : Object.keys(rows[0] || {}).map((k) => ({ key: k, label: k }));
  const hitByRow: Record<string, Record<string, any>> = {};
  (Array.isArray(chapter.riskCells) ? chapter.riskCells : []).forEach((c: any) => {
    if (!c || !c.rowKey || !c.field) return;
    (hitByRow[c.rowKey] = hitByRow[c.rowKey] || {})[c.field] = c;
  });
  const startEdit = (rowKey: string, col: any, value: any) => {
    setEditing({
      rowKey,
      field: String(col.key || ''),
      label: String(col.label || col.key || ''),
      value: value === null || value === undefined ? '' : String(value),
    });
  };
  const cancelEdit = () => setEditing(null);
  const saveEdit = () => {
    if (!editing || savingKey) return;
    const objectType = String(chapter.objectType || '');
    const current = { ...editing };
    const cellKey = `${current.rowKey}:${current.field}`;
    setSavingKey(cellKey);
    updateOntologyObjectField({
      objectType,
      objectKey: current.rowKey,
      field: current.field,
      value: current.value,
    })
      .then((result: any) => {
        const returned = result && result.data && typeof result.data === 'object'
          ? result.data[current.field]
          : undefined;
        const nextValue = returned === undefined || returned === null ? current.value : returned;
        setRowOverrides((prev: any) => ({
          ...prev,
          [current.rowKey]: {
            ...(prev[current.rowKey] || {}),
            [current.field]: nextValue,
          },
        }));
        setEditing(null);
        if (onToast) onToast(`已写回本体：${current.label}`);
      })
      .catch((err: any) => {
        if (onToast) onToast('写回失败：' + (err && err.message ? err.message : '本体服务未响应'));
      })
      .finally(() => setSavingKey(''));
  };

  return (
    <React.Fragment>
      <div className="ont-rows-cap">本章数据 · {rows.length} 条{chapter.objectType ? `（Dolt · ${chapter.objectType}）` : ''}</div>
      <div className="ont-rows-wrap">
        <table className="ont-ptable ont-rows">
          <thead>
            <tr>{cols.map((col: any, ci: number) => (
              <th key={ci} title={col.note || ''} className={col.derived ? 'ont-th-derived' : undefined}>
                {col.label}{col.derived ? <span className="ont-th-hit">命中</span> : null}
              </th>
            ))}</tr>
          </thead>
          <tbody>
            {rows.map((row: any, ri: number) => {
              const rowKey = keyField ? String(row[keyField] ?? '') : '';
              const hits = rowKey ? hitByRow[rowKey] : undefined;
              return (
                <tr key={ri} id={rowKey ? chapterRowAnchor(chapter.id, rowKey) : undefined}>
                  {cols.map((col: any, ci: number) => {
                    const v = row[col.key];
                    const cell = v === null || v === undefined || v === '' ? '—' : String(v);
                    const hit = hits ? hits[col.key] : undefined;
                    const editable = !!rowKey
                      && !hit
                      && !col.derived
                      && isOntologyObjectFieldEditable(chapter.objectType, String(col.key || ''));
                    const editKey = `${rowKey}:${col.key}`;
                    const isEditing = editing && editing.rowKey === rowKey && editing.field === col.key;
                    if (isEditing) {
                      const saving = savingKey === editKey;
                      return (
                        <td key={ci} className="ont-cell-editing">
                          <div className="ont-cell-editor">
                            <input
                              value={editing.value}
                              disabled={saving}
                              autoFocus
                              onChange={(e) => setEditing({ ...editing, value: e.target.value })}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') saveEdit();
                                if (e.key === 'Escape') cancelEdit();
                              }}
                            />
                            <button type="button" title="确认写回本体" disabled={saving} onClick={saveEdit}>
                              {saving ? '…' : <IcCheck s={13} />}
                            </button>
                            <button type="button" title="取消" disabled={saving} onClick={cancelEdit}>×</button>
                          </div>
                        </td>
                      );
                    }
                    if (!hit) return (
                      <td
                        key={ci}
                        title={editable ? `${cell}（点击编辑本体字段）` : cell}
                        className={editable ? 'ont-cell-editable' : undefined}
                        onClick={editable ? () => startEdit(rowKey, col, v) : undefined}
                      >
                        {cell}
                      </td>
                    );
                    return (
                      <td key={ci} className="ont-cell-risk" title={`${hit.reason || cell}（点击查看风险卡）`}
                        onClick={() => jumpToReportSection('ont-risk-' + hit.riskId)}>
                        <IcWarnTri s={12} />{cell}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </React.Fragment>
  );
}

/* 单对象叙述章节（如 项目背景）：后端按 layout:"detail" 把单条对象的 curated 字段投影成
   label→value 明细（chapter.detailRows）；竖排成「标签 · 值」两列，长文本自然换行（参考 proposal）。 */
function ChapterDetail({ chapter }: any) {
  const rows: any[] = Array.isArray(chapter.detailRows) ? chapter.detailRows : [];
  if (!rows.length) return null;
  return (
    <div className="ont-rows-wrap">
      <table className="ont-ptable ont-detail">
        <tbody>
          {rows.map((r: any, i: number) => {
            const v = r.value === null || r.value === undefined || r.value === '' ? '—' : String(r.value);
            return (
              <tr key={i}>
                <th title={r.note || ''}>{r.label}</th>
                <td>{v}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* 计划章（doc-ch-12，绑定 DeliveryPlanRow）：把投影行（delivery_plan_row）聚合成「一级活动」甘特图——
   一级活动 = activityId 不含小数点；同一活动跨多 PoD 多行按 activityId 聚合（min 起 / max 止 / 覆盖 PoD 数 /
   是否命中工期风险）。月份轴按天精度定位 bar，并附一级活动计划/责任汇总表。无一级活动行时回退占位字段
   chips + 未就绪提示（:8011 离线或数据为空时优雅降级，不白屏）。聚合逻辑在 contingency-view.buildFirstLevelGantt（可单测）。 */
function ChapterGantt({ chapter }: any) {
  const rows: any[] = Array.isArray(chapter.rows) ? chapter.rows : [];
  const model = buildFirstLevelGantt(rows);
  if (!model.activities.length) {
    return (
      <React.Fragment>
        <div className="ont-gantt-note">计划模块排期输出未就绪，暂无一级活动可展示。</div>
        {chapter.fields && chapter.fields.length ? (
          <div className="ont-fields">
            {chapter.fields.map((f: any, fi: number) => (
              <span key={fi} className="ont-field" title={f.note || ''}>{f.name}</span>
            ))}
          </div>
        ) : null}
      </React.Fragment>
    );
  }
  return (
    <React.Fragment>
      <SubH>关键一级活动甘特图 · {model.activities.length} 项（{model.minDate} ~ {model.maxDate}）</SubH>
      <div className="ont-gantt">
        <div className="ont-gantt-head">
          <span className="ont-gl">一级活动 / 月份</span>
          <div className="ont-gtrack ont-gmonths">
            {model.months.map((m: any) => (
              <i key={m.key} style={{ width: m.widthPct + '%' }}>{m.label}</i>
            ))}
          </div>
        </div>
        {model.activities.map((a: any) => (
          <div className="ont-gantt-row" key={a.activityId}>
            <span className="ont-gl">{a.name}<em>{a.owner || '未指派'}{a.podCount > 0 ? ` · ×${a.podCount} PoD` : ' · 项目级'}</em></span>
            <div className="ont-gtrack">
              <span
                className={'ont-gbar' + (a.hasRisk ? ' risk' : '')}
                style={{ left: a.leftPct + '%', width: a.widthPct + '%' }}
                title={`${a.name}：${a.start} ~ ${a.end} · ${a.durationDays} 天 · ${a.podCount} PoD${a.hasRisk ? ' · 命中工期风险' : ''}`}
              >
                {a.durationDays}d
              </span>
            </div>
          </div>
        ))}
      </div>
      <div className="ont-glegend">
        <span><i className="ont-lg plan" />一级活动（计划工期）</span>
        <span><i className="ont-lg risk" />命中低于标准工期风险</span>
      </div>
      <SubH>一级活动计划与责任 · {model.activities.length} 项</SubH>
      <div className="ont-rows-wrap">
        <table className="ont-ptable">
          <thead>
            <tr><th>一级活动</th><th>计划窗口</th><th>工期(天)</th><th>覆盖 PoD</th><th>责任人</th></tr>
          </thead>
          <tbody>
            {model.activities.map((a: any) => (
              <tr key={a.activityId}>
                <td>{a.name}{a.hasRisk ? <span className="ont-pill warn" style={{ marginLeft: 6 }}>工期风险</span> : null}</td>
                <td className="mono">{a.start} ~ {a.end}</td>
                <td>{a.durationDays}</td>
                <td>{a.podCount > 0 ? a.podCount : '—'}</td>
                <td>{a.owner || '未指派'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </React.Fragment>
  );
}

/* 章节数据体（按类型分派）：DeliveryPlanRow→甘特 / detail→明细 / rows→数据表 / 仅 fields→字段 chips。
   抽出来既给独立章用，也给融合组章的每个成员子区块复用（保留成员原始表单/数据表）。 */
function ChapterTable({ chapter, onToast }: any) {
  if (chapter.objectType === 'DeliveryPlanRow') return <ChapterGantt chapter={chapter} />;
  if (chapter.detailRows && chapter.detailRows.length) return <ChapterDetail chapter={chapter} />;
  if (chapter.rows && chapter.rows.length) return <ChapterRows chapter={chapter} onToast={onToast} />;
  if (chapter.fields && chapter.fields.length) {
    return (
      <div className="ont-fields">
        {chapter.fields.map((f: any, fi: number) => (
          <span key={fi} className="ont-field" title={f.note || ''}>{f.name}</span>
        ))}
      </div>
    );
  }
  return null;
}

/* ── 章节裁剪（ContingencyOutline）：assemblyNote 展示 + 逐章人工固定/排除 + 已排除恢复 ──
   写操作经 onAssembly('pin', chapterId, { action }) 上交父组件（pinContingencyChapter → reload）；
   onAssembly 缺省（预制演示）时全部不渲染，保持只读。 */
const _asmNote: any = {
  margin: '2px 0 8px', fontSize: 12.5, lineHeight: 1.7, color: '#0a6b4f',
  background: '#e9f8f1', border: '1px solid #c7ecdd', borderRadius: 7, padding: '6px 10px',
};
const _pinBadge: any = { fontSize: 10.5, fontWeight: 700, padding: '1px 8px', borderRadius: 999, color: '#7a5af0', background: '#efeaff' };
// 融合组章的成员子区块：左侧淡紫描边 + 缩进，视觉上把「原始表单」归到组章下。
const _grpMember: any = { margin: '12px 0 4px', paddingLeft: 12, borderLeft: '3px solid #e0d6fb' };
const _pinBtn = (kind?: string): any => ({
  display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11.5, fontWeight: 600,
  padding: '4px 10px', borderRadius: 7, cursor: 'pointer', lineHeight: 1.4, border: '1px solid',
  ...(kind === 'warn'
    ? { background: '#fff', color: '#c2410c', borderColor: '#f3c79b' }
    : kind === 'pin'
      ? { background: '#f4f0ff', color: '#6b46e0', borderColor: '#d9cdfb' }
      : { background: '#fff', color: '#3a4a63', borderColor: '#d4ddec' }),
});

function ChapterPinControls({ c, outline, busy, onAssembly }: any) {
  if (!onAssembly) return null; // 预制演示：只读
  const pinnedIn: string[] = (outline && outline.pinnedInclude) || [];
  const isPinnedIn = pinnedIn.indexOf(c.id) !== -1;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', margin: '0 0 8px' }}>
      <span style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8' }}>本项目裁剪</span>
      {isPinnedIn ? <span style={_pinBadge}>📌 已固定保留</span> : null}
      {busy ? (
        <span style={{ fontSize: 11, color: '#64748b' }}>处理中…</span>
      ) : (
        <React.Fragment>
          {isPinnedIn
            ? <button type="button" style={_pinBtn()} onClick={() => onAssembly('pin', c.id, { action: 'auto' })}>取消固定</button>
            : <button type="button" style={_pinBtn('pin')} onClick={() => onAssembly('pin', c.id, { action: 'include' })}>固定保留</button>}
          <button type="button" style={_pinBtn('warn')} onClick={() => onAssembly('pin', c.id, { action: 'exclude' })}>排除本章</button>
        </React.Fragment>
      )}
    </div>
  );
}

function ExcludedChaptersStrip({ outline, titleMap, busy = {}, onAssembly }: any) {
  if (!onAssembly || !outline) return null;
  const excluded: string[] = outline.pinnedExclude || [];
  if (!excluded.length) return null;
  return (
    <div style={{ margin: '0 0 14px', border: '1px dashed #f3c79b', background: '#fff8f0', borderRadius: 10, padding: '10px 12px' }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: '#b26a00', marginBottom: 6 }}>已排除章节 · {excluded.length}（人工固定排除，不计入本预案）</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {excluded.map((id: string) => (
          <span key={id} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#7a5a3a', background: '#fff', border: '1px solid #f0d6b8', borderRadius: 999, padding: '3px 6px 3px 11px' }}>
            {(titleMap && titleMap[id]) || id}
            <button type="button" disabled={!!busy[id]} style={{ ..._pinBtn(), padding: '2px 9px', fontSize: 11 }} onClick={() => onAssembly('pin', id, { action: 'auto' })}>{busy[id] ? '…' : '恢复'}</button>
          </span>
        ))}
      </div>
    </div>
  );
}

/* 真实生成中只有 项目背景 一章保留 AI 文字总结（章节正文）；其余章去除（风险&假设章已从后端目录删除）。
   与后端 contingency_narrative/graph.py 的 NARRATIVE_CHAPTERS 保持一致。 */
const NARRATIVE_CHAPTER_IDS = new Set(['doc-ch-1']);

function ContingencyReport({ risks, chapters, summary, activeSection, dispatched = {}, onDispatch, onToast, narrBusy = {}, onNarrative, onAssembly, asmBusy = {}, outline = null, chapterTitleMap = {} }: any) {
  const list: any[] = Array.isArray(risks) ? risks : [];
  const chapterList: any[] = Array.isArray(chapters) ? chapters : [];
  const count = summary ? summary.riskCount : list.length;
  const high = summary ? summary.high : list.filter((r: any) => severityClass(r.severity) === 'high').length;
  const risk = count > 0;

  // 风险按 riskId 建索引；章节携带后端绑定的 riskIds，按 id 取回风险对象渲染（后端驱动）。
  const byId: Record<string, any> = {};
  list.forEach((r: any, i: number) => { byId[r.riskId || String(i)] = r; });
  const resolveRisks = (ids: any): any[] => (Array.isArray(ids) ? ids.map((id: string) => byId[id]).filter(Boolean) : []);

  // 溯源「源数据」跳章：触发主体的 objectType → 投影该事实底座的章节（首个命中）。
  const chapterByObjectType: Record<string, any> = {};
  chapterList.forEach((c: any) => { if (c.objectType && !chapterByObjectType[c.objectType]) chapterByObjectType[c.objectType] = c; });
  const chapterFor = (objectType: string) => chapterByObjectType[objectType] || null;

  const refDate = list.length ? (list[0].identifiedAt || '') : '';
  const projectKey = list.length ? (list[0].projectKey || '') : '';
  const riskDesc = (r: any) => `${r.description || ''}${r.mitigationPlan ? '；处置建议：' + r.mitigationPlan : ''}${r.impact ? '；影响：' + r.impact : ''}`;
  const riskKey = (r: any, i: number) => r.riskId || String(i);
  const gapChapters = chapterList.filter((c: any) => c.lane && c.state === 'gap').length;
  const chapterCount = chapterList.length || 13;

  return (
    <React.Fragment>
      <div className="ont-doc-meta">
        <span>ENGINE · deriveContingencyRisks</span>
        <span>ONTOLOGY · default</span>
        <span>DOC · 交付预案 · {chapterList.length ? chapterList.length + ' 章（本体生成）' : '12 章目录'}</span>
        {projectKey ? <span>PROJECT · {projectKey}</span> : null}
        <span>SCALE · {count} 项风险</span>
        {refDate ? <span>AS OF · {refDate}</span> : null}
      </div>

      <EditableSection id="doc-overall" className={`ont-verdict ${risk ? 'risk' : 'success'}`} active={activeSection === 'doc-overall'} onToast={onToast}>
        <div className="ont-vhead">{risk ? <IcWarnTri /> : <IcCheck />}预案本体生成综合判定：{risk ? `识别到 ${count} 项预案风险` : '未识别到阻断性风险'}</div>
        <div className="ont-vbody">
          {risk
            ? <>本体引擎已按《交付预案》<b>章节目录</b>生成 <b>{chapterCount} 个章节</b>，并在维保 / 设备 / 部件 / 验收等事实底座上按售前风险规则库派生出 <b className="r">{count} 项预案风险</b>（建议值，未写回），绑定到对应可交付章节。下方逐章查阅，可逐项下发责任人处置。</>
            : <>本体引擎已按《交付预案》<b>章节目录</b>生成 <b>{chapterCount} 个章节</b>，<b className="g">四个子决策点章节均未命中风险规则</b>，当前事实与规则库比对未发现阻断性预案风险。</>}
        </div>
        <div className="ont-kpis">
          <div className="ont-kpi"><div className="ont-kv">{chapterCount}</div><div className="ont-kl">预案章节</div></div>
          <div className="ont-kpi"><div className={`ont-kv ${gapChapters ? 'r' : 'g'}`}>{gapChapters}</div><div className="ont-kl">命中风险章节</div></div>
          <div className="ont-kpi"><div className="ont-kv">{count}</div><div className="ont-kl">派生风险</div></div>
          <div className="ont-kpi"><div className={`ont-kv ${high ? 'r' : ''}`}>{high}</div><div className="ont-kl">高危</div></div>
        </div>
      </EditableSection>

      <ExcludedChaptersStrip outline={outline} titleMap={chapterTitleMap} busy={asmBusy} onAssembly={onAssembly} />

      {chapterList.map((c: any) => {
        // 融合组章（isGroup）：渲染单段融合正文（无独立数据表）；有绑定风险则照常列风险卡。
        const isGroup = !!c.isGroup;
        const showNarrative = NARRATIVE_CHAPTER_IDS.has(c.id) || isGroup;
        const hasRiskSlot = !!(c.lane || c.consolidatesRisks || (isGroup && c.riskIds && c.riskIds.length));
        const bound = resolveRisks(c.riskIds);
        const st = hasRiskSlot
          ? (bound.length
              ? { cls: 'warn', text: `${bound.length} 项${c.consolidatesRisks ? '' : '风险'}` }
              : { cls: 'ok', text: c.consolidatesRisks ? '0 项' : '可交付' })
          : { cls: 'ok', text: isGroup ? '融合章' : '已生成' };
        return (
          <DocSec key={c.id} id={c.id} idx={c.no} title={c.title} st={st} active={activeSection === c.id} sub={c.decisionLabel} onToast={onToast}>
            {showNarrative ? null : <p>{c.desc}</p>}
            {c.assemblyNote ? <div style={_asmNote}>📌 本项目说明 · {c.assemblyNote}</div> : null}
            <ChapterPinControls c={c} outline={outline} busy={asmBusy[c.id]} onAssembly={onAssembly} />
            {/* 组章：顶部 AI 融合概述（导语）；普通章：自身正文（仅 doc-ch-1） */}
            {showNarrative ? <ChapterNarrative c={c} busy={narrBusy[c.id]} onNarrative={onNarrative} /> : null}
            {c.source && !isGroup ? <div className="ont-ch-src">数据来源 · {c.source}</div> : null}
            {isGroup ? (
              /* 融合组章：每个成员一个带小标题的子区块，保留各自原始表单/数据表；
                 子区块 id=成员原 id（doc-device 等）→ 承接脑图子决策点跳转 / 溯源跳行，落点更精准。 */
              (c.members || []).map((m: any) => (
                <div key={m.id} id={m.id} className="ont-grp-member" style={_grpMember}>
                  <SubH>{m.title}</SubH>
                  {m.source ? <div className="ont-ch-src">数据来源 · {m.source}</div> : null}
                  <ChapterTable chapter={m} onToast={onToast} />
                </div>
              ))
            ) : (
              <ChapterTable chapter={c} onToast={onToast} />
            )}
            {hasRiskSlot ? (
              bound.length ? (
                <React.Fragment>
                  <SubH>{c.consolidatesRisks ? `统一风险清单 · ${bound.length} 项（可下发责任人）` : `本章命中预案风险 · ${bound.length} 项`}</SubH>
                  {bound.map((r: any, i: number) => (
                    <RiskCard key={riskKey(r, i)} rid={r.riskId} sev={severityClass(r.severity)} av={(r.owner || '险').slice(0, 1)}
                      title={r.riskName} domain={r.riskType || r.riskPoint} desc={riskDesc(r)}
                      owner={r.owner || '未指派'} dispatched={dispatched[riskKey(r, i)]}
                      provenance={r.provenance} chapterFor={chapterFor}
                      anchorId={!c.consolidatesRisks && r.riskId ? 'ont-risk-' + r.riskId : undefined}
                      onDispatch={() => onDispatch && onDispatch(riskKey(r, i), r, 'risk')} />
                  ))}
                </React.Fragment>
              ) : (
                <div className="ont-ch-concl ok"><IcCheck s={15} />{c.consolidatesRisks ? '四条生命周期通道均未命中风险规则，无阻断性风险。' : '本章对应生命周期事实未命中风险规则，可交付。'}</div>
              )
            ) : null}
          </DocSec>
        );
      })}

      {chapterList.length === 0 ? (
        <EditableSection id="doc-risks" className="ont-dispatch" active={activeSection === 'doc-risks'} onToast={onToast}>
          <div className="ont-dispatch-h"><IcWarnTri s={19} />{risk ? `已派生预案风险清单 · ${count} 项（可下发责任人）` : '已派生预案风险清单 · 0 项'}</div>
          {risk
            ? list.map((r: any, i: number) => (
                <RiskCard key={riskKey(r, i)} rid={r.riskId} sev={severityClass(r.severity)} av={(r.owner || '险').slice(0, 1)}
                  title={r.riskName} domain={r.riskType || r.riskPoint} desc={riskDesc(r)}
                  owner={r.owner || '未指派'} dispatched={dispatched[riskKey(r, i)]}
                  provenance={r.provenance} chapterFor={chapterFor}
                  anchorId={r.riskId ? 'ont-risk-' + r.riskId : undefined}
                  onDispatch={() => onDispatch && onDispatch(riskKey(r, i), r, 'risk')} />
              ))
            : <div className="ont-empty-risk"><IcCheck s={20} />四条生命周期通道均未命中风险规则，预案本体无阻断性风险。</div>}
        </EditableSection>
      ) : null}

      <EditableSection id="doc-dispatch" className="ont-dispatch" active={activeSection === 'doc-dispatch'} onToast={onToast}>
        <div className="ont-dispatch-h">
          <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /></svg>
          {risk ? `处置任务工单 · ${count} 项（每项风险派生一项处置任务）` : '处置任务工单 · 0 项'}
        </div>
        {risk
          ? list.map((r: any, i: number) => (
              <ActCard key={'t' + riskKey(r, i)} type="risk" av={(r.owner || '务').slice(0, 1)}
                title={`处置：${r.riskName}`} tag="RISK ACTION" desc={r.mitigationPlan || r.description || '按规则库建议处置'}
                owner={r.owner || '未指派'} dispatched={dispatched['t-' + riskKey(r, i)]} onDispatch={() => onDispatch && onDispatch('t-' + riskKey(r, i), r, 'task')} />
            ))
          : <div className="ont-empty-risk"><IcCheck s={20} />预案无阻断性风险，暂无处置任务工单。</div>}
      </EditableSection>
    </React.Fragment>
  );
}

/* =========================================================
   OntologyReport — 报告主体（注入到 .ont-drawer-body 内）
   ========================================================= */
function OntologyReport({ decision = 'risk', risks = null, chapters = null, summary = null, activeSection, dispatched = {} as Record<string|number, any>, onDispatch, onToast, narrBusy = {}, onNarrative, onAssembly, asmBusy = {}, outline = null, chapterTitleMap = {} }: any) {
  const risk = decision === 'risk';

  if (Array.isArray(risks)) {
    return <ContingencyReport risks={risks} chapters={chapters} summary={summary} activeSection={activeSection} dispatched={dispatched} onDispatch={onDispatch} onToast={onToast} narrBusy={narrBusy} onNarrative={onNarrative} onAssembly={onAssembly} asmBusy={asmBusy} outline={outline} chapterTitleMap={chapterTitleMap} />;
  }

  return (
    <React.Fragment>
      <div className="ont-doc-meta">
        <span>REPORT REF · ONT-DLV-20260530-017</span>
        <span>ENGINE · ONTOLOGY DECISION v3.2</span>
        <span>SCENE · 智算中心专线交付</span>
        <span>SCALE · 256×昇腾910B</span>
        <span>SLA · 99.999%</span>
        <span>MODE · SECURE</span>
      </div>

      {/* 综合判定 */}
      <EditableSection id="doc-overall" className={`ont-verdict ${risk ? 'risk' : 'success'}`} active={activeSection === 'doc-overall'} onToast={onToast}>
        <div className="ont-vhead">{risk ? <IcWarnTri /> : <IcCheck />}总体方案综合判定：{risk ? '交付存在风险' : '项目可交付'}</div>
        {risk ? (
          <div className="ont-vbody">全域数字孪生模型匹配完成，当前拓扑计算结果为 <b className="r">交付具备较高风险 (Blocked)</b>。业务引擎检测到核心路径设备端口资源不足，且 QA 自动化测试资产库脱节。为保障 <b className="r">99.999% SLA</b>，已拦截直接下发指令。该总体结论由下方四个章节（组网 / 设备 / 服务 / 验收）组合而成，请查阅并派发干预工单后再行交付。</div>
        ) : (
          <div className="ont-vbody">全域数字孪生模型匹配完成，当前拓扑计算结果为 <b className="g">项目可交付 (Deliverable)</b>。组网、设备、服务与验收四个子决策点全部通过校验，资源与质量卡点满足 <b className="g">99.999% SLA</b> 要求。该总体结论由下方四个章节组合而成，可一键下发交付实施指令。</div>
        )}
        <div className="ont-kpis">
          <div className="ont-kpi"><div className="ont-kv">4/4</div><div className="ont-kl">子决策完成</div></div>
          <div className="ont-kpi"><div className="ont-kv g">{risk ? '2' : '4'}</div><div className="ont-kl">通过章节</div></div>
          <div className="ont-kpi"><div className={`ont-kv ${risk ? 'r' : 'g'}`}>{risk ? '2' : '0'}</div><div className="ont-kl">风险项</div></div>
          <div className="ont-kpi"><div className={`ont-kv ${risk ? 'r' : 'g'}`}>{risk ? '2' : '99.999%'}</div><div className="ont-kl">{risk ? '待派发工单' : '交付 SLA'}</div></div>
        </div>
      </EditableSection>

      {/* 1. 组网 */}
      <DocSec id="doc-network" idx="1" title="组网拓扑规划与无损网络验证" st={{ cls: 'ok', text: 'VALIDATED' }} active={activeSection === 'doc-network'} onToast={onToast}
        sub="Spine-Leaf 架构 · RoCEv2 无损以太 · 昇腾智算集群东西向互联">
        <p>本体引擎依据项目业务意图，自动推导出面向 <b>256 卡昇腾 910B 训练集群</b> 的两层 <code>Spine-Leaf</code> 无阻塞 CLOS 组网，并完成跨省骨干网 OSPF/BGP 路由重分布演算。参数面采用 <code>RoCEv2</code> 无损以太承载，业务面 Active-Active 双归冗余，整网无逻辑环路与死锁，组网约束条件全部满足。</p>
        <Diagram svg={ONT_SVG_TOPO}
          legend={[{ c: '#2f7df6', t: 'Spine↔Leaf 200GE 上行' }, { c: '#19b8d8', t: 'Leaf↔Pod 100GE 接入' }, { c: '#94a3b8', t: 'WAN 出口（OSPF/BGP）' }]}
          cap="图 1 · <b>智算中心两层 Spine-Leaf 无阻塞组网拓扑</b>（自动生成，已通过环路与带宽收敛校验）" />
        <SubH>关键组网参数</SubH>
        <table className="ont-ptable">
          <tbody>
            <tr><th>项目</th><th>规划值</th><th>校验结果</th></tr>
            <tr><td>网络架构</td><td className="mono">两层 Spine-Leaf / CLOS</td><td><Pill kind="ok">无阻塞</Pill></td></tr>
            <tr><td>收敛比</td><td className="mono">1 : 1（无收敛）</td><td><Pill kind="ok">达标</Pill></td></tr>
            <tr><td>上行带宽</td><td className="mono">Spine↔Leaf 200GE ×8</td><td><Pill kind="ok">满足</Pill></td></tr>
            <tr><td>参数面协议</td><td className="mono">RoCEv2 + PFC + ECN</td><td><Pill kind="ok">无损</Pill></td></tr>
            <tr><td>路由协议</td><td className="mono">EBGP（Underlay）/ VXLAN（Overlay）</td><td><Pill kind="ok">收敛正常</Pill></td></tr>
            <tr><td>冗余方案</td><td className="mono">M-LAG Active-Active 双归</td><td><Pill kind="ok">高可用</Pill></td></tr>
          </tbody>
        </table>
        <p style={{ marginTop: 6 }}>无损网络已完成 PFC 死锁预防与 ECN 门限演算，Headroom Buffer 满足 256 卡 All-Reduce 突发；整网逻辑校验未发现环路、黑洞路由或 MTU 不一致问题。</p>
      </DocSec>

      {/* 2. 设备 */}
      <DocSec id="doc-device" idx="2" title="设备层资源锁定与容量探测" onToast={onToast}
        st={risk ? { cls: 'warn', text: 'RESOURCE GAP' } : { cls: 'ok', text: 'MATCHED' }} active={activeSection === 'doc-device'}
        sub="物理设备清单 · 端口/算力容量比对 · 库存预留锁态">
        <p>引擎将组网方案下推为物理设备需求，并与资产/库存系统实时比对，对交换机端口、智算服务器算力与机柜电力/散热进行容量探测与预留锁定。</p>
        <Diagram svg={ONT_SVG_RACK} cap="图 2 · <b>机柜设备分布与端口/算力容量比对</b>（橙色标注为待补充资源）" />
        <SubH>核心设备资源清单</SubH>
        <table className="ont-ptable">
          <tbody>
            <tr><th>设备</th><th>型号</th><th>关键资源</th><th>占用 / 容量</th><th>状态</th></tr>
            <tr><td>核心交换</td><td className="mono">SW-Core-BJ-02</td><td>100GE 光口</td>
              <td><Ubar fill={risk ? 'r' : 'g'} pct="100%" label={risk ? '8 / 4' : '8 / 8'} /></td>
              <td>{risk ? <Pill kind="warn">缺口</Pill> : <Pill kind="ok">充足</Pill>}</td></tr>
            <tr><td>接入交换</td><td className="mono">Leaf-01~04 CE8850</td><td>100GE 接入口</td>
              <td><Ubar fill="g" pct="62%" label="62%" /></td><td><Pill kind="ok">充足</Pill></td></tr>
            <tr><td>训练服务器</td><td className="mono">Atlas 800 ×8</td><td>昇腾 910B 算力卡</td>
              <td><Ubar fill="b" pct="100%" label="256/256" /></td><td><Pill kind="ok">已锁定</Pill></td></tr>
            <tr><td>电力散热</td><td className="mono">机柜 R12/R13</td><td>液冷 16kW/柜</td>
              <td><Ubar fill="g" pct="82%" label="82%" /></td><td><Pill kind="ok">达标</Pill></td></tr>
          </tbody>
        </table>
        {risk ? (
          <React.Fragment>
            <SubH>资源比对结论</SubH>
            <p>【探测失败】硬件库与存量库实时比对发现严重差值，核心交换设备端口预留动作未能闭合，已阻断本设备域的自动锁定。</p>
            <Alert title="端口物理容量枯竭">北京二区核心网元 <code>SW-Core-BJ-02</code> 可用 100G 光口仅余 4 个，而当前组网策略拟占用 8 个。硬件预留动作宣告失败（Error Code: <code>ERR_CAPACITY_LIMIT</code>）。建议补充端口或重规划链路绕行，详见下方派发工单。</Alert>
          </React.Fragment>
        ) : (
          <React.Fragment>
            <SubH>资源比对结论</SubH>
            <p>【匹配通过】硬件库与存量库实时比对一致。核心网元 <code>SW-Core-BJ-02</code> 100G 光口资源充足，已完成 8 端口预留锁定，昇腾算力、机柜电力与散热预算均满足组网策略需求。</p>
          </React.Fragment>
        )}
      </DocSec>

      {/* 3. 服务 */}
      <DocSec id="doc-service" idx="3" title="业务服务编排与 QoS 策略" st={{ cls: 'ok', text: 'GENERATED' }} active={activeSection === 'doc-service'} onToast={onToast}
        sub="服务目录解析 · 能力开通 · DSCP/队列/限速参数生成">
        <p>引擎将业务意图转换为可执行服务指令集，已自动匹配「金牌 QoS」策略模版，针对智算训练 RDMA 大象流与管理流进行差异化保障，配置项已就绪可一键开通。</p>
        <SubH>服务目录与开通能力</SubH>
        <table className="ont-ptable">
          <tbody>
            <tr><th>服务</th><th>能力</th><th>参数</th><th>状态</th></tr>
            <tr><td>RDMA 无损承载</td><td>RoCEv2 / PFC 优先级</td><td className="mono">CoS 3，无丢包</td><td><Pill kind="ok">已生成</Pill></td></tr>
            <tr><td>跨域专线</td><td>VXLAN EVPN 互联</td><td className="mono">VNI 100256，MTU 9000</td><td><Pill kind="ok">已生成</Pill></td></tr>
            <tr><td>管理面</td><td>带外管理 + 监控采集</td><td className="mono">Telemetry 1s 粒度</td><td><Pill kind="ok">已生成</Pill></td></tr>
            <tr><td>安全策略</td><td>微分段 ACL</td><td className="mono">东西向白名单</td><td><Pill kind="ok">已生成</Pill></td></tr>
          </tbody>
        </table>
        <SubH>QoS 队列与调度策略</SubH>
        <table className="ont-ptable">
          <tbody>
            <tr><th>流量类型</th><th>DSCP</th><th>队列</th><th>调度 / 限速</th></tr>
            <tr><td>训练 RDMA（大象流）</td><td className="mono">EF / 46</td><td className="mono">Q6 无损</td><td>PFC + ECN，优先调度</td></tr>
            <tr><td>参数同步 All-Reduce</td><td className="mono">AF41 / 34</td><td className="mono">Q5</td><td>WFQ 权重 40%</td></tr>
            <tr><td>存储 IO</td><td className="mono">AF31 / 26</td><td className="mono">Q4</td><td>WFQ 权重 30%</td></tr>
            <tr><td>管理 / 监控</td><td className="mono">CS6 / 48</td><td className="mono">Q7</td><td>限速 2Gbps</td></tr>
          </tbody>
        </table>
        <p style={{ marginTop: 6 }}>指令集已通过语法与策略冲突预检，<code>0</code> 条冲突；下发后预计 1 个变更窗口内完成全网能力开通。</p>
      </DocSec>

      {/* 4. 验收 */}
      <DocSec id="doc-acceptance" idx="4" title="自动化验收沙盘推演" onToast={onToast}
        st={risk ? { cls: 'warn', text: 'SCRIPT MISSING' } : { cls: 'ok', text: 'READY' }} active={activeSection === 'doc-acceptance'}
        sub="验收规则提取 · 测试用例编排 · 交付质量卡点校验">
        <p>引擎依据交付标准与本体验收规则库，自动编排端到端验收用例，并在数字孪生沙盘中预演，输出可交付质量卡点结论。</p>
        <SubH>关键验收测试项</SubH>
        <table className="ont-ptable">
          <tbody>
            <tr><th>用例</th><th>类型</th><th>判据</th><th>结果</th></tr>
            <tr><td>链路连通性 / MTU 一致性</td><td>组网</td><td className="mono">丢包 0，MTU 9000</td><td><Pill kind="ok">通过</Pill></td></tr>
            <tr><td>RoCE 无损（PFC/ECN）压测</td><td>性能</td><td className="mono">零丢包 @ 线速</td><td><Pill kind="ok">通过</Pill></td></tr>
            <tr><td>256 卡 All-Reduce 基准</td><td>智算</td><td className="mono">带宽 ≥ 标称 95%</td><td><Pill kind="ok">通过</Pill></td></tr>
            <tr><td>BGP 跨域秒级收敛</td><td>可靠性</td><td className="mono">收敛 &lt; 1s</td><td>{risk ? <Pill kind="warn">脚本缺失</Pill> : <Pill kind="ok">通过</Pill>}</td></tr>
            <tr><td>M-LAG 主备倒换</td><td>可靠性</td><td className="mono">业务无感知</td><td><Pill kind="ok">通过</Pill></td></tr>
          </tbody>
        </table>
        {risk ? (
          <React.Fragment>
            <SubH>推演结论</SubH>
            <p>【推演阻断】交付质量卡点校验不完全，存在无法自动验证的高阶可靠性特性，验收闭环未能形成。</p>
            <Alert title="核心脚本依赖缺失">策略涉及的「BGP 跨域秒级收敛」高阶特性，在当前测试资产库中找不到映射的自动化联调脚本（ID: <code>BGP_CVG_042</code>）。强行交付将导致验收闭环断裂，需补全脚本后重跑沙盘推演。</Alert>
          </React.Fragment>
        ) : (
          <React.Fragment>
            <SubH>推演结论</SubH>
            <p>【推演通过】交付质量卡点校验完整。「BGP 跨域秒级收敛」等高阶特性的自动化联调脚本已在测试资产库中命中并通过沙盘推演，验收闭环可正常形成。</p>
          </React.Fragment>
        )}
      </DocSec>

      {/* 风险清单 */}
      <EditableSection id="doc-risks" className="ont-dispatch" active={activeSection === 'doc-risks'} onToast={onToast}>
        <div className="ont-dispatch-h">
          <IcWarnTri s={19} />
          {risk ? '已识别风险清单 · 2 项（可下发责任人）' : '已识别风险清单 · 0 项'}
        </div>
        {risk ? (
          <React.Fragment>
            <RiskCard rid="R-01" sev="high" av="李" title="核心交换端口物理容量枯竭" domain="设备域 · 组网"
              desc="北京二区核心网元 SW-Core-BJ-02 可用 100G 光口仅余 4 个，当前组网策略需占用 8 个，硬件预留失败（ERR_CAPACITY_LIMIT），将阻断交付。"
              owner="李工 · 网络架构组" dispatched={dispatched['r0']} onDispatch={() => onDispatch('r0')} />
            <RiskCard rid="R-02" sev="mid" av="王" title="验收联调脚本依赖缺失" domain="验收域 · 质量"
              desc="「BGP 跨域秒级收敛」高阶特性在测试资产库中缺少映射的自动化联调脚本（ID: BGP_CVG_042），强行交付将导致验收闭环断裂。"
              owner="王工 · 测试开发组" dispatched={dispatched['r1']} onDispatch={() => onDispatch('r1')} />
          </React.Fragment>
        ) : (
          <div className="ont-empty-risk"><IcCheck s={20} />未识别到阻断性交付风险，四域校验全部通过，可直接进入交付实施。</div>
        )}
      </EditableSection>

      {/* 行动工单 */}
      <EditableSection id="doc-dispatch" className="ont-dispatch" active={activeSection === 'doc-dispatch'} onToast={onToast}>
        <div className="ont-dispatch-h">
          <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /></svg>
          {risk ? '处置任务工单 · 2 项 (Action Items)' : '交付实施行动工单 · 2 项 (Action Items)'}
        </div>
        {risk ? (
          <React.Fragment>
            <ActCard type="risk" av="李" title="硬件扩容 / 路径重规划工单" tag="RISK ACTION" desc="需对 SW-Core-BJ-02 紧急补充 4 个 100G 端口，或重定向链路绕行该拥塞节点。" owner="李工 · 网络架构组" dispatched={dispatched[0]} onDispatch={() => onDispatch(0)} />
            <ActCard type="risk" av="王" title="联调脚本紧急补充开发" tag="RISK ACTION" desc="请立刻编写跨域 BGP 路由收敛验证脚本并录入 CI/CD 验收测试库。" owner="王工 · 测试开发组" dispatched={dispatched[1]} onDispatch={() => onDispatch(1)} />
            <ActCard type="hold" av="AI" title="流程轮询挂起（等待人工修复）" tag="SYSTEM HOOK" desc="已自动将本次全局下发指令置为 Hold 状态，监听上述风险工单的解决回调事件。" owner="决策引擎 · 自动管控" />
          </React.Fragment>
        ) : (
          <React.Fragment>
            <ActCard type="task" av="张" title="下发交付实施指令" tag="DELIVER" desc="向下游编排系统下发组网 / 设备 / 服务 / 验收四域配置，启动自动化交付流水线。" owner="张工 · 交付实施组" dispatched={dispatched[0]} onDispatch={() => onDispatch(0)} />
            <ActCard type="task" av="陈" title="交付方案归档与基线锁定" tag="ARCHIVE" desc="将本次可交付方案文档归档并锁定为交付基线版本，供后续审计追溯。" owner="陈工 · 交付管理组" dispatched={dispatched[1]} onDispatch={() => onDispatch(1)} />
          </React.Fragment>
        )}
      </EditableSection>
    </React.Fragment>
  );
}

(function injectOntologyReportStyles() {
  const id = 'ont-report-styles';
  let s = document.getElementById(id);
  if (!s) { s = document.createElement('style'); s.id = id; document.head.appendChild(s); }
  s.textContent = `
    .ont-rep-scope{--blue:#2f7df6;--cyan:#19b8d8;--ink:#16233c;--ink-soft:#46566f;--ink-faint:#8a99b5;--success:#10b981;--success-dark:#059669;--warning:#f59e0b;--warning-dark:#b45309;--danger:#ef4444}
    .ont-doc-meta{display:flex;flex-wrap:wrap;gap:6px 18px;font-family:var(--font-mono,monospace);font-size:11px;color:var(--ink-faint);margin-bottom:16px;border-bottom:1px dashed #cbd8e8;padding-bottom:12px;letter-spacing:.3px}

    /* 综合判定 */
    .ont-verdict{position:relative;padding:16px 20px;border-radius:12px;margin-bottom:22px;border:1px solid;scroll-margin-top:18px;transition:box-shadow .4s,border-color .4s}
    .ont-verdict.risk{background:linear-gradient(135deg,#fffaf0,#fff5e6);border-color:#fde3a7}
    .ont-verdict.success{background:linear-gradient(135deg,#f0fdf8,#ecfdf3);border-color:#b8ebd4}
    .ont-verdict.active{box-shadow:0 0 0 3px rgba(47,125,246,.16)}
    .ont-vhead{font-size:16px;font-weight:800;display:flex;align-items:center;gap:9px;margin-bottom:8px}
    .ont-verdict.risk .ont-vhead{color:var(--warning-dark)}.ont-verdict.success .ont-vhead{color:var(--success-dark)}
    .ont-vhead svg{flex:none}
    .ont-vbody{font-size:13px;color:#3a4a63;line-height:1.7}
    .ont-vbody b.r{color:var(--warning-dark)}.ont-vbody b.g{color:var(--success-dark)}
    .ont-kpis{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
    .ont-kpi{background:rgba(255,255,255,.7);border:1px solid rgba(40,80,150,.1);border-radius:9px;padding:7px 12px;min-width:92px}
    .ont-kv{font-size:17px;font-weight:800;color:var(--ink);line-height:1.1}
    .ont-kv.r{color:var(--warning-dark)}.ont-kv.g{color:var(--success-dark)}
    .ont-kl{font-size:10px;color:var(--ink-faint);letter-spacing:.5px;text-transform:uppercase;margin-top:2px}

    /* 章节 */
    .ont-doc-sec{position:relative;margin-bottom:16px;padding:18px 22px;background:#fff;border-radius:12px;border:1px solid #e6edf6;box-shadow:0 3px 12px rgba(30,70,140,.03);scroll-margin-top:18px;transition:box-shadow .4s,border-color .4s,transform .4s}
    .ont-doc-sec.active{border-color:#2f7df6;box-shadow:0 0 0 3px rgba(47,125,246,.16)}
    .ont-doc-sec.ont-highlight,.ont-verdict.ont-highlight{animation:ontRepHl 1.6s ease;border-color:var(--blue)!important;box-shadow:0 0 0 3px rgba(47,125,246,.16)!important}
    @keyframes ontRepHl{0%,45%{background:#eff6ff;transform:scale(1.008)}100%{background:#fff;transform:scale(1)}}
    .ont-doc-sec .ont-sec-title{font-size:15px;font-weight:800;color:var(--ink);margin-bottom:4px;display:flex;align-items:center;gap:10px}
    .ont-idx{background:#e3ecff;color:var(--blue);font-size:12px;min-width:24px;height:24px;padding:0 5px;box-sizing:border-box;white-space:nowrap;display:inline-flex;align-items:center;justify-content:center;border-radius:7px;font-weight:800;font-family:var(--font-mono,monospace);flex:none}
    .ont-idx.ont-idx--label{font-size:10px;letter-spacing:.5px;padding:0 8px;border-radius:8px}
    .ont-st{margin-left:auto;font-family:var(--font-mono,monospace);font-size:10px;font-weight:800;padding:3px 9px;border-radius:5px;letter-spacing:.5px}
    .ont-st.ok{background:rgba(16,185,129,.12);color:var(--success-dark)}
    .ont-st.warn{background:rgba(245,158,11,.14);color:var(--warning-dark)}
    .ont-sec-sub{font-size:11px;color:var(--ink-faint);margin:0 0 12px 34px;letter-spacing:.3px}
    .ont-sec-content{font-size:13px;color:#3a4a63;line-height:1.7}
    .ont-sec-content p{margin-bottom:8px}
    .ont-sec-content code{font-family:var(--font-mono,monospace);background:#eef2f8;padding:1px 5px;border-radius:4px;font-size:12px;color:var(--blue)}
    .ont-subh{font-size:12.5px;font-weight:800;color:var(--ink);margin:16px 0 8px;display:flex;align-items:center;gap:7px}
    .ont-subh::before{content:'';width:3px;height:13px;border-radius:2px;background:linear-gradient(var(--blue),var(--cyan))}

    /* 每章工具条：编辑（hover 或编辑态显形，与预制演示 .sec-tools 一致） */
    .ont-sec-tools{position:absolute;top:14px;right:16px;display:flex;gap:6px;opacity:0;transform:translateY(-3px);transition:opacity .25s ease,transform .25s ease;z-index:4}
    .ont-doc-sec:hover .ont-sec-tools,.ont-doc-sec.editing .ont-sec-tools,.ont-verdict:hover .ont-sec-tools,.ont-verdict.editing .ont-sec-tools,.ont-dispatch:hover .ont-sec-tools,.ont-dispatch.editing .ont-sec-tools{opacity:1;transform:translateY(0)}
    .ont-sec-tool{display:inline-flex;align-items:center;gap:5px;cursor:pointer;font-family:inherit;font-size:11px;font-weight:700;color:var(--ink-soft);padding:5px 10px;border-radius:8px;background:rgba(255,255,255,.9);border:1px solid #e2e9f4;box-shadow:0 2px 8px -3px rgba(40,90,170,.25);transition:all .2s ease;backdrop-filter:blur(4px)}
    .ont-sec-tool svg{flex:none}
    .ont-sec-tool:hover{color:var(--blue);border-color:rgba(47,125,246,.5);background:#fff;transform:translateY(-1px);box-shadow:0 6px 16px -6px rgba(47,125,246,.5)}
    .ont-sec-tool.on{color:#fff;background:linear-gradient(135deg,var(--blue),#3f86ff);border-color:transparent;box-shadow:0 6px 16px -6px rgba(47,125,246,.7)}
    .ont-doc-sec.editing{border-color:rgba(47,125,246,.55);box-shadow:0 0 0 3px rgba(47,125,246,.12)}
    .ont-verdict.editing,.ont-dispatch.editing{box-shadow:0 0 0 3px rgba(47,125,246,.14)}
    .ont-sec-content[contenteditable="true"],.ont-sec-editable[contenteditable="true"]{outline:none;cursor:text}
    .ont-sec-content[contenteditable="true"]:focus,.ont-sec-editable[contenteditable="true"]:focus{background:#fbfdff;border-radius:8px;box-shadow:inset 0 0 0 1px rgba(47,125,246,.18);padding:6px;margin:-6px}

    /* 章节字段骨架 + 数据来源 + 结论 */
    .ont-ch-src{font-size:11px;color:var(--ink-faint);margin:2px 0 8px;font-family:var(--font-mono,monospace);letter-spacing:.2px}
    .ont-fields{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 2px}
    .ont-field{font-size:11px;color:#42526e;background:#f4f7fc;border:1px solid #e2e9f3;border-radius:6px;padding:3px 9px;font-weight:600;cursor:default}
    .ont-ch-concl{display:flex;align-items:center;gap:8px;font-size:12.5px;font-weight:600;padding:9px 12px;border-radius:9px;margin-top:10px}
    .ont-ch-concl.ok{background:#f0fdf8;border:1px solid #b8ebd4;color:var(--success-dark)}
    .ont-ch-concl svg{flex:none}

    /* 参数表 */
    .ont-ptable{width:100%;border-collapse:collapse;font-size:12px;margin:4px 0 6px}
    .ont-ptable th,.ont-ptable td{text-align:left;padding:7px 10px;border-bottom:1px solid #eef2f8}
    .ont-ptable th{color:var(--ink-faint);font-weight:700;font-size:10.5px;text-transform:uppercase;letter-spacing:.4px;background:#f7faff}
    .ont-ptable td{color:#34435c}
    .ont-ptable tr:last-child td{border-bottom:none}
    .ont-ptable td.mono{font-family:var(--font-mono,monospace);color:var(--ink)}
    /* 章节数据表（事实底座行投影） */
    .ont-rows-cap{font-size:11px;color:var(--ink-faint);font-weight:600;margin:10px 0 4px}
    .ont-rows-wrap{overflow-x:auto;margin:2px 0 6px;border:1px solid #eef2f8;border-radius:8px}
    .ont-rows{margin:0;min-width:100%}
    .ont-rows th{white-space:nowrap}
    .ont-rows td{white-space:nowrap;max-width:240px;overflow:hidden;text-overflow:ellipsis}
    .ont-rows tbody tr:hover td{background:#f7faff}
    .ont-rows td.ont-cell-editable{cursor:pointer;position:relative}
    .ont-rows td.ont-cell-editable:hover{background:#eef6ff;color:#1d4ed8}
    .ont-rows td.ont-cell-editing{background:#fbfdff!important;overflow:visible;max-width:none;min-width:230px}
    .ont-cell-editor{display:grid;grid-template-columns:minmax(150px,1fr) 28px 28px;align-items:center;gap:4px;min-width:220px}
    .ont-cell-editor input{width:100%;height:28px;box-sizing:border-box;border:1px solid rgba(47,125,246,.34);border-radius:6px;padding:4px 8px;font:inherit;font-size:12px;color:#1f2a44;background:#fff;outline:none;box-shadow:0 0 0 2px rgba(47,125,246,.08)}
    .ont-cell-editor button{width:28px;height:28px;border-radius:6px;border:1px solid #dbe6f6;background:#fff;color:#1d4ed8;display:inline-flex;align-items:center;justify-content:center;cursor:pointer;font-weight:800}
    .ont-cell-editor button:hover{background:#eff6ff;border-color:rgba(47,125,246,.5)}
    .ont-cell-editor button:disabled{cursor:wait;opacity:.62}
    /* 默认精简+命中追加：风险证据字段列（derived）表头标红，命中单元格着色可点回风险卡 */
    .ont-rows th.ont-th-derived{color:#b42318}
    .ont-th-hit{margin-left:5px;font-size:9px;font-weight:800;letter-spacing:.4px;padding:1px 5px;border-radius:4px;background:#fee2e2;color:#b42318}
    .ont-rows td.ont-cell-risk{background:#fef2f2;color:#b42318;font-weight:700;cursor:pointer}
    .ont-rows td.ont-cell-risk svg{vertical-align:-1px;margin-right:4px}
    .ont-rows tbody tr:hover td.ont-cell-risk,.ont-rows td.ont-cell-risk:hover{background:#fee2e2}
    .ont-rows tbody tr{scroll-margin-top:48px}
    .ont-rows tbody tr.ont-highlight td{animation:ontRowHl 1.6s ease}
    @keyframes ontRowHl{0%,45%{background:#fff1f0}100%{background:transparent}}
    /* 单对象叙述明细（项目背景）：标签列 + 值列竖排，长文本换行 */
    .ont-detail{margin:0}
    .ont-detail th{width:104px;white-space:nowrap;vertical-align:top;text-align:left}
    .ont-detail td{line-height:1.7;color:#34435c;white-space:normal}
    /* 交付计划甘特图（计划章 doc-ch-12 · 一级活动；月份轴 + 跨 PoD 聚合 bar） */
    .ont-gantt{border:1px solid #e6edf6;border-radius:10px;overflow:hidden;background:#fbfdff;margin:4px 0 8px}
    .ont-gantt-row,.ont-gantt-head{display:flex;align-items:stretch;min-height:34px;border-bottom:1px solid #eef2f8}
    .ont-gantt-row:last-child{border-bottom:none}
    .ont-gantt-head{background:#f1f6fd;min-height:28px}
    .ont-gantt .ont-gl{flex:none;width:190px;padding:5px 12px;font-size:12px;font-weight:700;color:var(--ink);display:flex;flex-direction:column;justify-content:center;line-height:1.25;box-sizing:border-box;border-right:1px solid #eef2f8}
    .ont-gantt .ont-gl em{font-style:normal;font-size:10.5px;font-weight:600;color:var(--ink-soft);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .ont-gantt .ont-gtrack{position:relative;flex:1;min-width:0}
    .ont-gantt .ont-gmonths{display:flex}
    .ont-gantt .ont-gmonths i{font-style:normal;font-size:10px;font-weight:700;color:var(--ink-soft);display:grid;place-items:center;border-left:1px dashed rgba(40,80,150,.16);box-sizing:border-box;overflow:hidden;white-space:nowrap;min-height:28px}
    .ont-gantt .ont-gmonths i:first-child{border-left:none}
    .ont-gbar{position:absolute;top:50%;transform:translateY(-50%);height:18px;min-width:6px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:#fff;background:linear-gradient(90deg,var(--blue),var(--cyan));box-shadow:0 1px 4px rgba(47,125,246,.28);white-space:nowrap;overflow:hidden;padding:0 6px;box-sizing:border-box;cursor:default}
    .ont-gbar.risk{background:linear-gradient(90deg,#f59e0b,#f97316);box-shadow:0 1px 4px rgba(245,158,11,.34)}
    .ont-glegend{display:flex;gap:16px;align-items:center;font-size:11px;color:var(--ink-soft);margin:6px 0 4px;flex-wrap:wrap}
    .ont-glegend i.ont-lg{display:inline-block;width:14px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}
    .ont-glegend i.ont-lg.plan{background:linear-gradient(90deg,var(--blue),var(--cyan))}
    .ont-glegend i.ont-lg.risk{background:linear-gradient(90deg,#f59e0b,#f97316)}
    .ont-gantt-note{font-size:12px;color:var(--ink-soft);background:#f7faff;border:1px dashed #dbe6f6;border-radius:8px;padding:8px 12px;margin:4px 0 8px}
    .ont-pill{display:inline-flex;align-items:center;gap:4px;font-size:10px;font-weight:800;font-family:var(--font-mono,monospace);padding:2px 8px;border-radius:999px}
    .ont-pill.ok{background:rgba(16,185,129,.12);color:var(--success-dark)}
    .ont-pill.warn{background:rgba(245,158,11,.14);color:var(--warning-dark)}
    .ont-pill.info{background:rgba(47,125,246,.1);color:var(--blue)}

    /* 容量条 */
    .ont-ubar{display:flex;align-items:center;gap:8px}
    .ont-ubar .ont-track{flex:1;height:6px;border-radius:99px;background:#eef2f8;overflow:hidden}
    .ont-ubar .ont-fill{height:100%;border-radius:99px;display:block}
    .ont-ubar .ont-fill.g{background:linear-gradient(90deg,var(--success),#34d399)}
    .ont-ubar .ont-fill.b{background:linear-gradient(90deg,var(--blue),var(--cyan))}
    .ont-ubar .ont-fill.r{background:linear-gradient(90deg,#f59e0b,#ef4444)}
    .ont-ubar .ont-uv{font-family:var(--font-mono,monospace);font-size:11px;font-weight:700;color:#34435c;min-width:60px;text-align:right}

    /* 图框 */
    .ont-diagram{margin:10px 0 6px;border:1px solid #e6edf6;border-radius:12px;background:linear-gradient(180deg,#fbfdff,#f4f8ff);padding:12px 14px 8px;overflow:hidden}
    .ont-diagram-svg svg{width:100%;height:auto;display:block}
    .ont-cap{font-size:10.5px;color:var(--ink-faint);margin-top:6px;letter-spacing:.3px}
    .ont-cap b{color:var(--blue);font-weight:700}
    .ont-dleg{display:flex;flex-wrap:wrap;gap:12px;font-size:10.5px;color:var(--ink-soft);margin-top:4px}
    .ont-dleg span{display:inline-flex;align-items:center;gap:5px}
    .ont-dleg i{width:14px;height:3px;border-radius:2px;display:inline-block}

    /* 告警 */
    .ont-alert{background:#fffbeb;border:1px solid #fde68a;border-left:3px solid var(--warning);padding:12px 16px;border-radius:9px;margin-top:12px}
    .ont-alert-title{font-weight:800;color:#92400e;font-size:13px;margin-bottom:5px;display:flex;align-items:center;gap:7px}
    .ont-alert-desc{color:var(--warning-dark);font-size:12.5px;line-height:1.6}
    .ont-alert-desc code{font-family:var(--font-mono,monospace);background:rgba(245,158,11,.12);padding:1px 5px;border-radius:4px}

    /* 工单 */
    .ont-dispatch{margin-top:26px}
    .ont-dispatch-h{font-size:16px;font-weight:800;color:var(--ink);margin-bottom:14px;display:flex;align-items:center;gap:9px;padding-bottom:9px;border-bottom:2px solid #e6edf6}
    .ont-dispatch-h svg{color:var(--blue)}
    .ont-act-card{background:#fff;border:1px solid #e6edf6;border-radius:11px;padding:13px 16px;margin-bottom:11px;display:flex;gap:13px;align-items:center;box-shadow:0 3px 10px rgba(30,70,140,.03)}
    .ont-act-card.risk{border-left:3px solid var(--warning)}
    .ont-act-card.task{border-left:3px solid var(--blue)}
    .ont-act-head .ont-sev{font-size:10px;padding:2px 7px;border-radius:5px;font-weight:800;font-family:var(--font-mono,monospace);flex:none}
    .ont-sev.high{background:#fee2e2;color:#b42318}.ont-sev.mid{background:#fef3c7;color:#d97706}.ont-sev.low{background:#e0f2fe;color:#0369a1}
    .ont-empty-risk{display:flex;align-items:center;gap:10px;padding:16px 18px;border-radius:11px;background:#f0fdf8;border:1px solid #b8ebd4;color:var(--success-dark);font-size:13px;font-weight:600}
    .ont-dispatch{position:relative;scroll-margin-top:18px;border-radius:12px;transition:box-shadow .4s}
    .ont-dispatch.active{box-shadow:0 0 0 3px rgba(47,125,246,.16)}
    .ont-dispatch.ont-highlight{animation:ontRepHl 1.6s ease;box-shadow:0 0 0 3px rgba(47,125,246,.16)!important}
    .ont-avatar{width:40px;height:40px;border-radius:50%;display:grid;place-items:center;color:#fff;font-weight:800;font-size:15px;flex:none}
    .ont-avatar.risk{background:linear-gradient(135deg,var(--warning),#ea580c);box-shadow:0 4px 12px rgba(245,158,11,.3)}
    .ont-avatar.task{background:linear-gradient(135deg,#3b82f6,var(--cyan));box-shadow:0 4px 12px rgba(59,130,246,.3)}
    .ont-act-main{flex:1;min-width:0}
    .ont-act-head{display:flex;align-items:center;gap:9px;margin-bottom:4px}
    .ont-act-title{font-weight:800;color:var(--ink);font-size:14px}
    .ont-act-tag{font-size:9px;padding:2px 7px;border-radius:5px;font-weight:800;font-family:var(--font-mono,monospace);text-transform:uppercase}
    .ont-act-tag.risk{background:#fef3c7;color:#d97706}.ont-act-tag.task{background:#eff6ff;color:var(--blue)}
    .ont-act-desc{font-size:12.5px;color:#475569;line-height:1.5;margin-bottom:6px}
    .ont-act-meta{font-size:11.5px;font-weight:600;color:var(--ink-faint);display:flex;align-items:center;gap:6px}
    .ont-act-btns{display:flex;flex-direction:column;gap:7px;flex:none}
    .ont-btn-dispatch{padding:8px 15px;border-radius:8px;font-weight:700;font-size:12.5px;cursor:pointer;flex:none;display:flex;align-items:center;gap:6px;min-width:104px;justify-content:center;border:1px solid transparent}
    .ont-btn-dispatch.go{background:var(--ink);color:#fff;box-shadow:0 6px 16px rgba(22,35,60,.2)}
    .ont-btn-dispatch.go:hover{background:#22344f;transform:translateY(-2px)}
    .ont-btn-dispatch.done{background:#ecfdf5;color:#065f46;border-color:#6ee7b7;cursor:default}
    .ont-btn-dispatch.lock{background:#eef2f8;color:var(--ink-faint);cursor:not-allowed}

    /* 推导溯源下钻：规则 → 命中事实行（证据）→ 源数据章节 */
    .ont-prov{margin-top:8px}
    .ont-prov-toggle{display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:700;color:var(--blue);background:#eef4ff;border:1px solid #d4e3fb;border-radius:7px;padding:4px 10px;cursor:pointer;font-family:var(--font-mono,monospace);letter-spacing:.2px}
    .ont-prov-toggle:hover,.ont-prov-toggle.on{background:#e2edff;border-color:#b8d2f7}
    .ont-prov-caret{font-style:normal;font-size:9px;opacity:.7}
    .ont-prov-body{margin-top:8px;border:1px solid #dbe6f5;border-radius:10px;background:#fbfdff;padding:10px 12px;display:flex;flex-direction:column;gap:7px}
    .ont-prov-row{display:flex;align-items:center;flex-wrap:wrap;gap:5px 8px;font-size:12px;color:var(--ink)}
    .ont-prov-chip{flex:none;font-size:10px;font-weight:800;letter-spacing:.5px;padding:2px 7px;border-radius:5px;background:#e8f1ff;color:var(--blue);border:1px solid #d4e3fb}
    .ont-prov-chip.fact{background:#f0fdf8;color:var(--success-dark);border-color:#b8ebd4}
    .ont-prov-dim{color:var(--ink-faint);font-size:11px}
    .ont-prov-key{font-family:var(--font-mono,monospace);font-size:10.5px;color:var(--ink-faint);background:#f1f5fb;border-radius:4px;padding:1px 6px}
    .ont-prov-reason{flex:1 1 100%;font-size:11.5px;color:var(--ink-soft);line-height:1.55;padding-left:2px}
    .ont-prov-row.jump{cursor:pointer;margin:0 -5px;padding:3px 5px;border-radius:7px}
    .ont-prov-row.jump:hover{background:#eef4ff}
    .ont-prov-row.jump:hover b{color:var(--blue)}
    .ont-prov-link{font-size:10.5px;color:var(--ink-faint);font-family:var(--font-mono,monospace)}
    .ont-prov-srcs{display:flex;align-items:center;flex-wrap:wrap;gap:6px;font-size:11px;color:var(--ink-faint);margin-top:2px}
    .ont-prov-srcbtn{font-size:11px;font-weight:700;color:var(--blue);background:#fff;border:1px solid #d4e3fb;border-radius:6px;padding:3px 9px;cursor:pointer}
    .ont-prov-srcbtn:hover{background:#eef4ff}
  `;
  document.head.appendChild(s);
})();

export { OntologyReport };
