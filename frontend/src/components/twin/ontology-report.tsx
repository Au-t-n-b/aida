// @ts-nocheck
/* 从 DS-1 / twin-world-export 整体移植，与项目里既有 screens/*.tsx 同等做法 — 保留 @ts-nocheck */
import React from 'react';
/* AIDA · 数字孪生 — 本体决策报告内容 (信息栏)
   移植自 ontology-decision-brain 升级版：综合判定 + KPI + 拓扑/机柜图 +
   参数表 / QoS 表 / 验收表 + 容量条 + 行动工单 + 孪生入口
   决策态: decision = 'risk' | 'success'
*/
import { useState as useStateOR } from 'react';

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

const Pill = ({ kind, children  }: any) => <span className={`ont-pill ${kind}`}>{children}</span>;
const Ubar = ({ fill, pct, label  }: any) => (
  <div className="ont-ubar"><span className="ont-track"><span className={`ont-fill ${fill}`} style={{ width: pct }} /></span><span className="ont-uv">{label}</span></div>
);

/* ── 章节包装 ── */
function DocSec({ id, idx, title, sub, st, active, children  }: any) {
  return (
    <div id={id} className={`ont-doc-sec${active ? ' active' : ''}`}>
      <div className="ont-sec-title"><span className="ont-idx">{idx}</span>{title}{st && <span className={`ont-st ${st.cls}`}>{st.text}</span>}</div>
      {sub && <div className="ont-sec-sub">{sub}</div>}
      <div className="ont-sec-content">{children}</div>
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

/* ── 风险清单卡 ── */
function RiskCard({ rid, sev, av, title, domain, desc, owner, onDispatch, dispatched  }: any) {
  const sevLabel = sev === 'high' ? '高危' : (sev === 'mid' ? '中危' : '低危');
  return (
    <div className="ont-act-card risk">
      <div className="ont-avatar risk">{av}</div>
      <div className="ont-act-main">
        <div className="ont-act-head">
          <div className="ont-act-title">{rid} · {title}</div>
          <span className={'ont-sev ' + sev}>{sevLabel}</span>
          <span className="ont-act-tag risk">{domain}</span>
        </div>
        <div className="ont-act-desc">{desc}</div>
        <div className="ont-act-meta"><IcUser />处置责任人：{owner}</div>
      </div>
      <button type="button" className={`ont-btn-dispatch${dispatched === 'done' ? ' done' : ' go'}`} onClick={dispatched ? undefined : onDispatch}>
        {dispatched === 'done' ? <><IcCheck s={15} />已派发</> : dispatched === 'sending' ? '派发中…' : <><IcSend />下发处理</>}
      </button>
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

/* =========================================================
   OntologyReport — 报告主体（注入到 .ont-drawer-body 内）
   ========================================================= */
function OntologyReport({ decision = 'risk', activeSection, dispatched = {} as Record<string|number, any>, onDispatch, onToast }: any) {
  const risk = decision === 'risk';

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
      <div id="doc-overall" className={`ont-verdict ${risk ? 'risk' : 'success'}${activeSection === 'doc-overall' ? ' active' : ''}`}>
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
      </div>

      {/* 1. 组网 */}
      <DocSec id="doc-network" idx="1" title="组网拓扑规划与无损网络验证" st={{ cls: 'ok', text: 'VALIDATED' }} active={activeSection === 'doc-network'}
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
      <DocSec id="doc-device" idx="2" title="设备层资源锁定与容量探测"
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
      <DocSec id="doc-service" idx="3" title="业务服务编排与 QoS 策略" st={{ cls: 'ok', text: 'GENERATED' }} active={activeSection === 'doc-service'}
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
      <DocSec id="doc-acceptance" idx="4" title="自动化验收沙盘推演"
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
      <div id="doc-risks" className={'ont-dispatch' + (activeSection === 'doc-risks' ? ' active' : '')}>
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
      </div>

      {/* 行动工单 */}
      <div id="doc-dispatch" className={'ont-dispatch' + (activeSection === 'doc-dispatch' ? ' active' : '')}>
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
      </div>
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
    .ont-verdict{padding:16px 20px;border-radius:12px;margin-bottom:22px;border:1px solid;scroll-margin-top:18px;transition:box-shadow .4s,border-color .4s}
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
    .ont-doc-sec{margin-bottom:16px;padding:18px 22px;background:#fff;border-radius:12px;border:1px solid #e6edf6;box-shadow:0 3px 12px rgba(30,70,140,.03);scroll-margin-top:18px;transition:box-shadow .4s,border-color .4s,transform .4s}
    .ont-doc-sec.active{border-color:#2f7df6;box-shadow:0 0 0 3px rgba(47,125,246,.16)}
    .ont-doc-sec.ont-highlight,.ont-verdict.ont-highlight{animation:ontRepHl 1.6s ease;border-color:var(--blue)!important;box-shadow:0 0 0 3px rgba(47,125,246,.16)!important}
    @keyframes ontRepHl{0%,45%{background:#eff6ff;transform:scale(1.008)}100%{background:#fff;transform:scale(1)}}
    .ont-doc-sec .ont-sec-title{font-size:15px;font-weight:800;color:var(--ink);margin-bottom:4px;display:flex;align-items:center;gap:10px}
    .ont-idx{background:#e3ecff;color:var(--blue);font-size:12px;width:24px;height:24px;display:inline-flex;align-items:center;justify-content:center;border-radius:7px;font-weight:800;font-family:var(--font-mono,monospace);flex:none}
    .ont-st{margin-left:auto;font-family:var(--font-mono,monospace);font-size:10px;font-weight:800;padding:3px 9px;border-radius:5px;letter-spacing:.5px}
    .ont-st.ok{background:rgba(16,185,129,.12);color:var(--success-dark)}
    .ont-st.warn{background:rgba(245,158,11,.14);color:var(--warning-dark)}
    .ont-sec-sub{font-size:11px;color:var(--ink-faint);margin:0 0 12px 34px;letter-spacing:.3px}
    .ont-sec-content{font-size:13px;color:#3a4a63;line-height:1.7}
    .ont-sec-content p{margin-bottom:8px}
    .ont-sec-content code{font-family:var(--font-mono,monospace);background:#eef2f8;padding:1px 5px;border-radius:4px;font-size:12px;color:var(--blue)}
    .ont-subh{font-size:12.5px;font-weight:800;color:var(--ink);margin:16px 0 8px;display:flex;align-items:center;gap:7px}
    .ont-subh::before{content:'';width:3px;height:13px;border-radius:2px;background:linear-gradient(var(--blue),var(--cyan))}

    /* 参数表 */
    .ont-ptable{width:100%;border-collapse:collapse;font-size:12px;margin:4px 0 6px}
    .ont-ptable th,.ont-ptable td{text-align:left;padding:7px 10px;border-bottom:1px solid #eef2f8}
    .ont-ptable th{color:var(--ink-faint);font-weight:700;font-size:10.5px;text-transform:uppercase;letter-spacing:.4px;background:#f7faff}
    .ont-ptable td{color:#34435c}
    .ont-ptable tr:last-child td{border-bottom:none}
    .ont-ptable td.mono{font-family:var(--font-mono,monospace);color:var(--ink)}
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
    .ont-dispatch{scroll-margin-top:18px;border-radius:12px;transition:box-shadow .4s}
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
    .ont-btn-dispatch{padding:8px 15px;border-radius:8px;font-weight:700;font-size:12.5px;cursor:pointer;flex:none;display:flex;align-items:center;gap:6px;min-width:104px;justify-content:center;border:1px solid transparent}
    .ont-btn-dispatch.go{background:var(--ink);color:#fff;box-shadow:0 6px 16px rgba(22,35,60,.2)}
    .ont-btn-dispatch.go:hover{background:#22344f;transform:translateY(-2px)}
    .ont-btn-dispatch.done{background:#ecfdf5;color:#065f46;border-color:#6ee7b7;cursor:default}
    .ont-btn-dispatch.lock{background:#eef2f8;color:var(--ink-faint);cursor:not-allowed}
  `;
  document.head.appendChild(s);
})();

export { OntologyReport };
