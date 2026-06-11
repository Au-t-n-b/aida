// @ts-nocheck
'use client';

import { useState, useEffect } from 'react';
import {
  PLAN_GANTT,
  PLAN_PEOPLE,
  PLAN_GOODS,
  PLAN_SITES,
} from '../../data/journey-data';
import { RISKS } from '../../data/app-data';
import VersionBar, { bumpVersion } from '../version-bar';
import ActionFooter from '../action-footer';

/* ── 子视图标签 ── */
const PLAN_VIEWS = [
  { key: 'info',       label: '基础信息',     sub: '项目元数据 / 5 项基本字段' },
  { key: 'plan',       label: '计划（人货站）', sub: '甘特 + 三因素并行' },
  { key: 'task',       label: '任务',         sub: '可执行任务卡' },
  { key: 'raci',       label: '责任矩阵',     sub: 'RACI · 8 类作业' },         /* NEW-11 (SVG L217) */
  { key: 'risk',       label: '风险',         sub: '红 3 / 橙 5' },
  { key: 'assumption', label: '假设',         sub: '3 项待客户回复' },
  { key: 'issue',      label: '问题',         sub: '2 项 · 售前继承 / 现场提出' },
  { key: 'change',     label: '变更',         sub: '近 30 天 4 项 · 关联 LLD' },
  { key: 'teams',      label: '跨项目调度',   sub: '12 队 × 8 周 饱和度' },
  /* 5.28 H-5 · 新增"质量·工程"视图：客户工程报单 / Agent 问题 / DOA 详情 / DOA 部件统计
   * 4 张表统一去除"区域"字段，仅保留"状态" */
  { key: 'quality',    label: '质量 · 工程',  sub: '4 表合一 · 无区域字段' },
];

/* ── 起手式 callout（按视图切换） ── */
const FOCUS = {
  info:       { tone: 'info',  text: '基础信息已冻结：5 项基本字段 + proposal/合同绑定关系。系统每次刷新自动核对。' },
  plan:       { tone: 'amber', text: '人货站三因素并行：B2-RM02 配电延期 9 天，建议从 H 项目调度 2 人补位（沙箱 α 命中率 78%）。先上传 HLD/CAD/BOQ → 机房数/PoD 数自动填入。' },
  task:       { tone: 'info',  text: '今日 12 个任务，3 个阻塞：B2-RM02 配电、A1-RM01 ESS 复检、施工队 07 调度。' },
  raci:       { tone: 'info',  text: '责任矩阵：8 类作业 × 5 角色。设备安装阶段「TL 主责」突显，所有里程碑客户至少"知情"。' },
  risk:       { tone: 'red',   text: '3 条不可满足风险已升级，5 条 at-risk 已纳入 SLA 跟进。最快闭环窗口：T-12 通报 B2 客户配电改造决议。' },
  assumption: { tone: 'amber', text: '3 项假设待客户回复（2 项售前继承），已并入 DRB 第 8 章。建议下周二评审会一并闭环。' },
  issue:      { tone: 'amber', text: '2 项问题：1 项售前公勘继承（电源容量复核），1 项现场提出（机房承重）。' },
  change:     { tone: 'info',  text: '近 30 天 4 项变更：1 项配置 / 2 项进度 / 1 项范围。变更日志由 AIDA 自动归档，每条均关联 LLD 章节。' },
  teams:      { tone: 'info',  text: '跨项目队伍负载热图：施工队 07 在 W22 饱和度 96%（红），建议 H 项目调 2 人。' },
  quality:    { tone: 'info',  text: '5.28 评审：客户工程报单 / Agent 问题 / DOA 详情 / DOA 部件统计 4 表合一，"区域"字段统一删除，"基地 / 园区" 也不再展示。' },
};

/* ─────────────────────────  basic info  ─────────────────────────
 * G-16 · 字段精简：
 *   - 砍掉 风冷 / 液冷 / 产品形态 / 集群形态（自动从 BOQ 解析，不再让用户手填）
 *   - 5 项基本字段定型为：Proposal ID / 项目编码 / 客户 / 业务变化场景（新增/扩容）/ 推训场景（推理/训练/训推一体）
 *   - 责任人字段拆到「项目元数据」侧边栏，不挤占 5 项主字段
 */
function InfoView() {
  const fields = [
    { k: 'Proposal ID',     v: 'PROP-2026-K1903',          state: 'ok' },
    { k: '项目编码',         v: 'PROP-2026-K1903',          state: 'ok' },
    { k: '客户',             v: '客户甲（华南区）',         state: 'ok' },
    { k: '业务变化场景',     v: '新建',                     state: 'ok' },
    { k: '推训场景',         v: '训推一体',                 state: 'ok' },
  ];
  const meta = [
    { k: 'PD',          v: '李伟' },
    { k: 'TD',          v: '何博' },
    { k: 'PCM',         v: '王婷' },
    { k: '合同 ID',      v: 'CON-2026-K1903-001' },
    { k: '合同金额',     v: '¥ 1.84 亿' },
    { k: '签署日期',     v: '2026-06-04' },
    { k: '里程碑',       v: '5 项' },
    { k: '基线版本',     v: 'LLD-v1.0' },
  ];
  return (
    <div className="jn-grid-2">
      <div className="jn-panel">
        <div className="jn-panel-head">5 项基本字段（项目初始化）</div>
        <div className="jn-lld">
          {fields.map((f) => (
            <div key={f.k} className="jn-lld-row">
              <span className="k">{f.k}</span>
              <span className="v">{f.v}</span>
              <span className={`pill state-${f.state}`}>已冻结</span>
            </div>
          ))}
        </div>
        <div className="jn-hint" style={{ marginTop: 10 }}>
          初始化字段不超过 5 项 · 其它由 Proposal / 合同自动回填。
        </div>
      </div>
      <div className="jn-panel">
        <div className="jn-panel-head">项目元数据 · 自动绑定</div>
        <div className="jn-stats">
          {meta.map((m) => (
            <div key={m.k} className="jn-stat">
              <div className="jn-stat-k">{m.k}</div>
              <div className="jn-stat-v">{m.v}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────────  人货站（默认主视图）  ───────────────────────── */
function GanttBar({ row, total }) {
  const left = (row.start / total) * 100;
  const width = (row.dur / total) * 100;
  return (
    <div className="plan-gantt-grid">
      <div className="plan-gantt-name">{row.name}</div>
      <div className="plan-gantt-track">
        <div
          className={`plan-gantt-bar s-${row.stream}`}
          style={{ left: `${left}%`, width: `${width}%` }}
        >
          <span className="plan-gantt-bar-label">
            {row.id} · {row.dur}d {row.status === 'risk' ? ' · 风险' : ''}
          </span>
        </div>
      </div>
    </div>
  );
}

/* 5.27 R-6 · 计划页起手式自动填条
 * 起手式：先上传 HLD/CAD/BOQ → 机房数 / PoD 数 / GPU 数 自动填入；人改为先则不覆盖 */
function PlanStarterBar() {
  /* 演示数据：从已解析的 HLD/CAD/BOQ 自动推导 */
  const auto = {
    rooms: 14,
    pods:  36,
    gpus:  1920,
    startDate: '2026-05-30',
    endDate:   '2026-08-10',
    /* NEW-12 · SVG L225 客户提供 / 上线时间 / 到货时间 */
    customerReq: '2026-08-15',
    onlineReq:   '2026-08-10',
    deliveryReq: '2026-07-20',
  };
  const [overrides, setOverrides] = useState({});
  const set = (k, v) => setOverrides(s => ({ ...s, [k]: v }));
  const val = (k) => overrides[k] !== undefined ? overrides[k] : auto[k];
  const isAuto = (k) => overrides[k] === undefined;

  return (
    <div className="plan-starter">
      <div className="plan-starter-head">
        <strong>快速开始 · 关键字段</strong>
        <span className="plan-starter-hint">自动从 HLD / CAD / BOQ 解析 · 人改为先则不覆盖</span>
      </div>
      <div className="plan-starter-grid">
        {[
          { k: 'rooms', label: '机房数', src: 'CAD' },
          { k: 'pods',  label: 'PoD 数',  src: 'HLD' },
          { k: 'gpus',  label: 'GPU 总数', src: 'BOQ' },
          { k: 'startDate', label: '开始时间', src: '手填', type: 'date' },
          { k: 'endDate',   label: '结束时间', src: '自动算' },
          /* NEW-12 · 3 个时间要求字段 */
          { k: 'customerReq', label: '客户提供节点', src: '客户', type: 'date' },
          { k: 'onlineReq',   label: '上线时间要求', src: '客户', type: 'date' },
          { k: 'deliveryReq', label: '到货时间要求', src: 'BOQ', type: 'date' },
        ].map(f => (
          <div key={f.k} className="plan-starter-cell">
            <span className="plan-starter-k">{f.label}</span>
            <input
              type={f.type === 'date' ? 'date' : 'text'}
              value={val(f.k)}
              onChange={e => set(f.k, e.target.value)}
              className="plan-starter-v"
            />
            <span className={`plan-starter-src${isAuto(f.k) ? ' auto' : ' manual'}`}>
              {isAuto(f.k) ? f.src : '人填'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function PlanView() {
  const total = PLAN_GANTT.reduce((m, r) => Math.max(m, r.start + r.dur), 0);
  const ticks = [0, Math.round(total * 0.25), Math.round(total * 0.5), Math.round(total * 0.75), total];

  return (
    <>
      <PlanStarterBar />
      <div className="plan-gantt">
        <div className="jn-panel-head" style={{ marginBottom: 4 }}>项目甘特 · 关键路径（{total} 天）</div>
        {PLAN_GANTT.map((r) => (
          <GanttBar key={r.id} row={r} total={total} />
        ))}
        <div className="plan-gantt-scale">
          <div />
          <div className="plan-gantt-ticks">
            {ticks.map((t) => (
              <span key={t}>D+{t}</span>
            ))}
          </div>
        </div>
      </div>

      <div className="plan-row" style={{ marginTop: 12 }}>
        {/* 人 */}
        <div className="plan-card">
          <h3>
            <span className="tag people">人</span>施工 / 调测队伍
          </h3>
          <div className="plan-team">
            {PLAN_PEOPLE.map((t) => (
              <div key={t.team} className={`plan-team-row${t.status !== 'ok' ? ' status-risk' : ''}`}>
                <div className="plan-team-head">
                  <span>{t.team} · {t.members} 人</span>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{t.allocPct}%</span>
                </div>
                <div className="plan-team-meta">{t.current}</div>
                <div className="plan-team-alloc">
                  <span style={{ width: `${t.allocPct}%` }} />
                </div>
                {t.warn && <div className="plan-team-warn">⚠ {t.warn}</div>}
              </div>
            ))}
          </div>
        </div>

        {/* 货 */}
        <div className="plan-card">
          <h3>
            <span className="tag goods">货</span>BOQ / 物料齐套
          </h3>
          <div className="plan-sku">
            {PLAN_GOODS.map((g) => (
              <div key={g.sku} className="plan-sku-row">
                <span className="plan-sku-name">{g.sku}</span>
                <span className="plan-sku-prog">{g.arrived} / {g.total}</span>
                <span className={`plan-sku-eta ${g.status === 'risk' ? 'risk' : 'ok'}`}>
                  {g.eta}
                </span>
              </div>
            ))}
          </div>
          <div className="jn-hint" style={{ marginTop: 8 }}>
            注：齐套规则按 BOQ 行匹配，384N 节点和 100G 交换机为关键路径物料。
          </div>
        </div>

        {/* 站 */}
        <div className="plan-card">
          <h3>
            <span className="tag site">站</span>机房就绪
          </h3>
          <div className="plan-site-grid">
            {PLAN_SITES.map((s) => (
              <div key={s.room} className={`plan-site state-${s.state}`}>
                <div className="plan-site-name">{s.room}</div>
                <div className="plan-site-meta">{s.pods} PoD · {s.state === 'ready' ? '就绪' : s.state === 'prep' ? '准备中' : '阻塞'}</div>
                {s.blocker && <div className="plan-site-blocker">⚠ {s.blocker}</div>}
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

/* ─────────────────────────  任务  ───────────────────────── */
const TASKS = [
  { id: 'T-2026-101', title: 'B2-RM02 客户配电改造对齐会', owner: 'PD 李伟', due: '今日 16:00', state: 'urgent', stream: '人' },
  { id: 'T-2026-102', title: 'A1-RM01 ESS 复检准备',         owner: 'TD 王明', due: '今日 18:00', state: 'urgent', stream: '站' },
  { id: 'T-2026-103', title: '施工队 07 跨项目调度审批',       owner: 'PD 何博', due: '明日 12:00', state: 'todo',   stream: '人' },
  { id: 'T-2026-104', title: '100G 交换机物流跟踪 · ETA 5/28', owner: '供应链 陈光', due: '5/28', state: 'todo', stream: '货' },
  { id: 'T-2026-105', title: 'PoD#04 工厂联调压缩 2 天方案',   owner: 'TD 王明', due: '5/27', state: 'todo', stream: '货' },
  { id: 'T-2026-106', title: 'D4 设备到货齐套对齐',           owner: 'PD 张悦', due: '5/28', state: 'todo', stream: '货' },
  { id: 'T-2026-107', title: 'C3 客户提前移交诉求评估沙箱',     owner: 'PD 李伟', due: '5/30', state: 'review', stream: '人' },
  { id: 'T-2026-108', title: 'WiKi 历史复盘 · PJ-2025-014',   owner: 'AIDA',   due: '已完成', state: 'done', stream: '系统' },
  { id: 'T-2026-109', title: 'DRB 评审材料下发客户',          owner: 'TD 何博', due: '5/29', state: 'todo', stream: '系统' },
  { id: 'T-2026-110', title: 'B2-RM03 弱电整改进度跟进',       owner: 'PD 李伟', due: '6/01', state: 'todo', stream: '站' },
  { id: 'T-2026-111', title: 'E5-RM01 网络接入工单催办',       owner: 'PD 周晗', due: '5/27', state: 'urgent', stream: '站' },
  { id: 'T-2026-112', title: 'A1 一期客户移交里程碑准备',       owner: 'PD 李伟', due: '6/03', state: 'todo', stream: '人' },
];
const TASK_STATE = {
  urgent: { label: '紧急', cls: 'red' },
  todo:   { label: '待办', cls: '' },
  review: { label: '评审中', cls: 'amber' },
  done:   { label: '完成', cls: 'green' },
};
function TaskView() {
  const [filter, setFilter] = useState('all');
  const filtered = TASKS.filter((t) => filter === 'all' ? true : t.state === filter);
  const counts = TASKS.reduce((m, t) => { m[t.state] = (m[t.state] || 0) + 1; return m; }, {});
  return (
    <div className="jn-panel" style={{ padding: 0 }}>
      <div className="jn-panel-head" style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px' }}>
        <span>项目任务（共 {TASKS.length}）</span>
        <div style={{ display: 'flex', gap: 6, marginLeft: 'auto' }}>
          {[
            ['all',    '全部'],
            ['urgent', `紧急 ${counts.urgent || 0}`],
            ['todo',   `待办 ${counts.todo || 0}`],
            ['review', `评审中 ${counts.review || 0}`],
            ['done',   `完成 ${counts.done || 0}`],
          ].map(([k, l]) => (
            <button
              key={k}
              className={`snap-tab${filter === k ? ' active' : ''}`}
              onClick={() => setFilter(k)}
              style={{ padding: '4px 10px', fontSize: 12 }}
            >
              {l}
            </button>
          ))}
        </div>
      </div>
      <table className="vs-table">
        <thead>
          <tr><th>任务 ID</th><th>标题</th><th>归口</th><th>责任人</th><th>截止</th><th>状态</th></tr>
        </thead>
        <tbody>
          {filtered.map((t) => {
            const s = TASK_STATE[t.state];
            return (
              <tr key={t.id}>
                <td className="num" style={{ fontFamily: 'var(--font-mono)' }}>{t.id}</td>
                <td>{t.title}</td>
                <td>{t.stream}</td>
                <td>{t.owner}</td>
                <td className="num">{t.due}</td>
                <td><span className={`status-pill ${s.cls}`}>{s.label}</span></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ─────────────────────────  风险  ─────────────────────────
 * G-14 · 5 大场景（来源）过滤 chip：客户 / 物流 / 施工 / 设计 / 合规
 * 所有 chip 默认全选；可点击切换；上方动态汇总 X 红 / Y 橙
 */
const RISK_SOURCE_FILTERS = [
  { key: 'all',        label: '全部', tone: 'gray' },
  { key: 'customer',   label: '客户', tone: 'red' },
  { key: 'logistic',   label: '物流', tone: 'amber' },
  { key: 'field',      label: '施工', tone: 'violet' },
  { key: 'design',     label: '设计', tone: 'blue' },
  { key: 'compliance', label: '合规', tone: 'gray' },
  { key: 'erp',        label: 'ERP 评选', tone: 'amber' },
  { key: 'doc',        label: '文档不一致', tone: 'red' },
];
function RiskView() {
  const [activeSource, setActiveSource] = useState('all');
  const filtered = RISKS.filter(r => activeSource === 'all' ? true : r.source === activeSource);
  const red = filtered.filter((r) => r.sev === 'red');
  const amber = filtered.filter((r) => r.sev === 'amber');

  /* 各来源风险数（用于 chip 上的角标） */
  const counts = RISK_SOURCE_FILTERS.reduce((m, s) => {
    m[s.key] = s.key === 'all'
      ? RISKS.length
      : RISKS.filter(r => r.source === s.key).length;
    return m;
  }, {} as Record<string, number>);

  return (
    <>
      {/* G-14 · 来源场景过滤 chip */}
      <div className="risk-source-filters">
        <span className="risk-source-filters-label">按场景过滤</span>
        {RISK_SOURCE_FILTERS.map(s => (
          <button
            key={s.key}
            className={`risk-source-chip tone-${s.tone}${activeSource === s.key ? ' on' : ''}`}
            onClick={() => setActiveSource(s.key)}
            disabled={counts[s.key] === 0}
            title={counts[s.key] === 0 ? '当前无此场景风险' : `查看 ${counts[s.key]} 项`}
          >
            <span>{s.label}</span>
            <span className="risk-source-chip-num">{counts[s.key]}</span>
          </button>
        ))}
      </div>

      <div className="jn-grid-2">
        <div className="jn-panel">
          <div className="jn-panel-head">不可满足风险（红 · {red.length}）</div>
          <div className="risk-list">
            {red.length === 0 && (
              <div style={{ padding: '14px 12px', fontSize: 12, color: 'var(--c-text-muted)' }}>
                当前过滤条件下无红色风险。
              </div>
            )}
            {red.map((r, i) => (
              <div key={i} className="risk-row sev-red" style={{ padding: '10px 12px', borderBottom: '1px solid var(--c-border)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12.5, fontWeight: 600 }}>
                  <span>{r.title}</span>
                  <span className="status-pill red">{r.delay}</span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--c-text-muted)', marginTop: 4 }}>
                  {r.project} · {r.pod} · {r.owner} · SLA {r.sla} · 已 {r.age}
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="jn-panel">
          <div className="jn-panel-head">在线风险（橙 · {amber.length}）</div>
          <div className="risk-list">
            {amber.length === 0 && (
              <div style={{ padding: '14px 12px', fontSize: 12, color: 'var(--c-text-muted)' }}>
                当前过滤条件下无橙色风险。
              </div>
            )}
            {amber.map((r, i) => (
              <div key={i} className="risk-row sev-amber" style={{ padding: '10px 12px', borderBottom: '1px solid var(--c-border)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12.5, fontWeight: 600 }}>
                  <span>{r.title}</span>
                  <span className="status-pill amber">{r.delay}</span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--c-text-muted)', marginTop: 4 }}>
                  {r.project} · {r.pod} · {r.owner} · SLA {r.sla} · 已 {r.age}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

/* ─────────────────────────  假设 / 问题  ───────────────────────── */
/* 5.25 M-013 · 来源字段（售前工单 / 公勘 / 客户反馈 / 现场提出）
 * 5.27 R-12 · 假设 / 问题 拆成两个视图 */
const ISSUES = [
  /* 假设 */
  { id: 'I-01', title: '客户机房 B2 配电改造方案以乙方设计为准', cat: '假设', source: 'presale',  state: '待客户回复', owner: 'PD 李伟', due: '5/28' },
  { id: 'I-02', title: 'k8s 平台版本统一升级到 1.30 LTS',        cat: '假设', source: 'survey',   state: '待客户回复', owner: 'TD 何博', due: '5/30' },
  { id: 'I-03', title: 'A1-RM01 ESS 装修验收标准为 GB50174-2017', cat: '假设', source: 'customer', state: '待复检',   owner: 'TD 王明', due: '今日' },
  /* 问题 */
  { id: 'I-04', title: '电源容量复核 · 售前估算偏低 30%',         cat: '问题', source: 'presale',  state: '待复算',   owner: 'TD 何博', due: 'T-3' },
  { id: 'I-05', title: 'C3-RM02 机房承重不足，需结构加固',         cat: '问题', source: 'onsite',   state: '客户协调', owner: 'PD 李伟', due: '5/30' },
];

const ISSUE_SOURCE_META = {
  presale:  { label: '售前继承', tone: 'violet' },
  survey:   { label: '公勘',     tone: 'blue' },
  customer: { label: '客户反馈', tone: 'amber' },
  onsite:   { label: '现场提出', tone: 'green' },
};
function IssueSourceTag({ source }) {
  const m = ISSUE_SOURCE_META[source];
  if (!m) return null;
  return <span className={`risk-source-tag tone-${m.tone}`}>{m.label}</span>;
}

/* 5.27 R-12 · 假设视图（cat === '假设'） */
function AssumptionView() {
  const list = ISSUES.filter(i => i.cat === '假设');
  return (
    <div className="jn-panel" style={{ padding: 0 }}>
      <div className="jn-panel-head" style={{ padding: '12px 14px' }}>
        假设（{list.length} 项 · 与 DRB 第 8 章关联）· <span style={{ color: 'var(--c-text-muted)', fontWeight: 400 }}>来源支持售前继承</span>
      </div>
      <table className="vs-table">
        <thead>
          <tr><th>ID</th><th>描述</th><th>来源</th><th>责任人</th><th>状态</th><th>截止</th></tr>
        </thead>
        <tbody>
          {list.map(i => (
            <tr key={i.id}>
              <td className="num" style={{ fontFamily: 'var(--font-mono)' }}>{i.id}</td>
              <td>{i.title}</td>
              <td><IssueSourceTag source={i.source} /></td>
              <td>{i.owner}</td>
              <td>{i.state}</td>
              <td className="num">{i.due}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* 5.27 R-12 · 问题视图（cat === '问题'） */
function IssueView() {
  const list = ISSUES.filter(i => i.cat === '问题');
  return (
    <div className="jn-panel" style={{ padding: 0 }}>
      <div className="jn-panel-head" style={{ padding: '12px 14px' }}>
        问题（{list.length} 项）· <span style={{ color: 'var(--c-text-muted)', fontWeight: 400 }}>支持售前公勘问题一键继承</span>
      </div>
      <table className="vs-table">
        <thead>
          <tr><th>ID</th><th>描述</th><th>来源</th><th>责任人</th><th>状态</th><th>截止</th></tr>
        </thead>
        <tbody>
          {list.map(i => (
            <tr key={i.id}>
              <td className="num" style={{ fontFamily: 'var(--font-mono)' }}>{i.id}</td>
              <td>{i.title}</td>
              <td><IssueSourceTag source={i.source} /></td>
              <td>{i.owner}</td>
              <td>{i.state}</td>
              <td className="num">{i.due}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ─────────────────────────  变更  ─────────────────────────
 * 5.25 M-021 · 变更 → LLD 基线传导链：每行加 lldImpact（影响哪些 PoD / LLD 章节）
 */
const CHANGES = [
  { id: 'CHG-2026-001', cat: '配置', title: 'k8s 平台版本 1.28 → 1.30 LTS',        impact: '低',  state: '已批准', date: '2026-05-30', owner: 'TD 何博', lldImpact: 'LLD §7 平台版本' },
  { id: 'CHG-2026-002', cat: '进度', title: 'B2 二期上电点亮里程碑顺延 7 天',       impact: '高',  state: '审批中', date: '2026-05-28', owner: 'PD 李伟', lldImpact: 'PoD#18-23 · LLD §11 实施计划' },
  { id: 'CHG-2026-003', cat: '进度', title: 'PoD#01-04 安装压缩 2 天',             impact: '中',  state: '已批准', date: '2026-05-26', owner: 'TD 王明', lldImpact: 'PoD#01-04 · LLD §11 / §13 验收' },
  { id: 'CHG-2026-004', cat: '范围', title: 'A1 增加 2 个备用机柜（客户追加）',     impact: '低',  state: '已批准', date: '2026-05-22', owner: 'TD 王明', lldImpact: 'LLD §5 机房 / §8 物理布局' },
];
function ChangeView() {
  return (
    <div className="jn-panel" style={{ padding: 0 }}>
      <div className="jn-panel-head" style={{ padding: '12px 14px' }}>
        变更日志（近 30 天 · {CHANGES.length} 项）· <span style={{ color: 'var(--c-text-muted)', fontWeight: 400 }}>每条自动关联 LLD 章节</span>
      </div>
      <table className="vs-table">
        <thead>
          <tr><th>变更号</th><th>分类</th><th>标题</th><th>影响</th><th>关联 LLD</th><th>状态</th><th>责任人</th><th>日期</th></tr>
        </thead>
        <tbody>
          {CHANGES.map((c) => (
            <tr key={c.id}>
              <td className="num" style={{ fontFamily: 'var(--font-mono)' }}>{c.id}</td>
              <td><span className="status-pill">{c.cat}</span></td>
              <td>{c.title}</td>
              <td>
                <span className={`status-pill ${c.impact === '高' ? 'red' : c.impact === '中' ? 'amber' : 'green'}`}>
                  {c.impact}
                </span>
              </td>
              <td style={{ fontSize: 11, color: 'var(--c-text-muted)' }}>{c.lldImpact}</td>
              <td>{c.state}</td>
              <td>{c.owner}</td>
              <td className="num">{c.date}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ─────────────────────────  责任矩阵 RACI (NEW-11 / SVG L217)  ─────────────────────────
 * R = Responsible · 执行 / A = Accountable · 主责 / C = Consulted · 咨询 / I = Informed · 知情
 */
const RACI_ROLES = ['PD', 'TD', 'PCM', 'TL', '客户'];
const RACI_TASKS = [
  { task: '项目初始化 (5 字段 + OCC)',    raci: ['A', 'C', 'I', 'I', 'I'] },
  { task: '合同签署 + LLD 冻结',         raci: ['A', 'R', 'C', 'I', 'C'] },
  { task: '智慧工勘',                    raci: ['I', 'A', 'I', 'R', 'C'] },
  { task: '规划设计 (HLD/LLD)',          raci: ['C', 'A', 'I', 'R', 'I'] },
  { task: '设备到货齐套',                raci: ['I', 'A', 'C', 'R', 'I'] },
  { task: '设备安装 + 上电',             raci: ['I', 'C', 'I', 'A', 'I'] },
  { task: '部署调测 + 验收',             raci: ['I', 'A', 'I', 'R', 'C'] },
  { task: '客户移交 + 复盘',             raci: ['A', 'R', 'C', 'I', 'A'] },
];
const RACI_META = {
  'R': { tone: 'blue',   desc: 'Responsible · 执行' },
  'A': { tone: 'red',    desc: 'Accountable · 主责' },
  'C': { tone: 'amber',  desc: 'Consulted · 咨询' },
  'I': { tone: 'gray',   desc: 'Informed · 知情' },
};
function RaciView() {
  return (
    <div className="jn-panel" style={{ padding: 0 }}>
      <div className="jn-panel-head" style={{ padding: '12px 14px' }}>
        责任矩阵（RACI · {RACI_TASKS.length} 类作业 × {RACI_ROLES.length} 角色）
      </div>
      <table className="vs-table raci-table">
        <thead>
          <tr>
            <th style={{ textAlign: 'left' }}>作业</th>
            {RACI_ROLES.map(r => <th key={r} style={{ textAlign: 'center', minWidth: 64 }}>{r}</th>)}
          </tr>
        </thead>
        <tbody>
          {RACI_TASKS.map(row => (
            <tr key={row.task}>
              <td>{row.task}</td>
              {row.raci.map((cell, i) => {
                const m = RACI_META[cell];
                return (
                  <td key={i} style={{ textAlign: 'center' }}>
                    <span className={`raci-cell tone-${m.tone}`} title={m.desc}>{cell}</span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="raci-legend">
        <span><span className="raci-cell tone-red">A</span> 主责</span>
        <span><span className="raci-cell tone-blue">R</span> 执行</span>
        <span><span className="raci-cell tone-amber">C</span> 咨询</span>
        <span><span className="raci-cell tone-gray">I</span> 知情</span>
      </div>
    </div>
  );
}

/* ─────────────────────────  跨项目调度热图 (N-2 / M-014)  ─────────────────────────
 * 12 队 × 8 周 饱和度，红 ≥ 90 / 橙 70-90 / 绿 < 70
 */
const TEAMS_HEATMAP = [
  { team: '施工队 01', loads: [60, 72, 80, 55, 40, 35, 50, 65] },
  { team: '施工队 02', loads: [45, 50, 60, 70, 80, 75, 60, 55] },
  { team: '施工队 03', loads: [80, 85, 88, 82, 76, 70, 65, 60] },
  { team: '施工队 04', loads: [55, 60, 70, 78, 82, 80, 70, 60] },
  { team: '施工队 05', loads: [70, 75, 82, 88, 86, 80, 72, 65] },
  { team: '施工队 06', loads: [40, 50, 60, 70, 75, 70, 60, 50] },
  { team: '施工队 07', loads: [85, 92, 96, 94, 88, 80, 72, 65] }, /* 饱和点 */
  { team: '施工队 08', loads: [50, 55, 60, 65, 70, 75, 70, 65] },
  { team: '施工队 09', loads: [60, 65, 70, 72, 70, 65, 60, 55] },
  { team: '施工队 10', loads: [70, 72, 75, 78, 80, 78, 72, 65] },
  { team: '调试组 H', loads: [30, 35, 40, 35, 28, 25, 30, 35] },  /* H 项目可调 */
  { team: '调试组 K', loads: [55, 60, 65, 70, 72, 70, 65, 60] },
];
function TeamsView() {
  const weeks = ['W22', 'W23', 'W24', 'W25', 'W26', 'W27', 'W28', 'W29'];
  const color = (v) => v >= 90 ? 'red' : v >= 70 ? 'amber' : 'green';
  return (
    <div className="jn-panel" style={{ padding: 0 }}>
      <div className="jn-panel-head" style={{ padding: '12px 14px' }}>
        跨项目队伍负载热图（{TEAMS_HEATMAP.length} 队 × {weeks.length} 周）· <span style={{ color: 'var(--c-text-muted)', fontWeight: 400 }}>沙箱方案 α 调度依据</span>
      </div>
      <table className="vs-table teams-heatmap">
        <thead>
          <tr>
            <th style={{ textAlign: 'left', minWidth: 110 }}>队伍</th>
            {weeks.map(w => <th key={w} style={{ textAlign: 'center', minWidth: 56 }}>{w}</th>)}
            <th style={{ textAlign: 'center' }}>峰值</th>
          </tr>
        </thead>
        <tbody>
          {TEAMS_HEATMAP.map(row => {
            const peak = Math.max(...row.loads);
            return (
              <tr key={row.team}>
                <td>{row.team}</td>
                {row.loads.map((v, i) => (
                  <td key={i} style={{ textAlign: 'center', padding: 2 }}>
                    <span className={`heatmap-cell tone-${color(v)}`} title={`${row.team} ${weeks[i]}：${v}%`}>
                      {v}
                    </span>
                  </td>
                ))}
                <td style={{ textAlign: 'center' }}>
                  <span className={`status-pill ${color(peak) === 'red' ? 'red' : color(peak) === 'amber' ? 'amber' : 'green'}`}>
                    {peak}%
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div style={{ padding: '10px 14px', fontSize: 11, color: 'var(--c-text-muted)' }}>
        红 ≥ 90 不可接 · 橙 70-90 谨慎 · 绿 &lt; 70 有冗余 —— 沙箱 α 推荐"H 项目调 2 人补 07"，可见 H 队 W22-29 全绿。
      </div>
    </div>
  );
}

/* 读 URL 参数 — 不用 useSearchParams 避免静态导出后 Suspense fallback=null 空白 */
function readUrlParam(key) {
  if (typeof window === 'undefined') return null;
  return new URLSearchParams(window.location.search).get(key);
}

/* ─────────────────────────  主屏  ───────────────────────── */
export default function PlanScreen() {
  /* 初始用 'plan'，hydration 后再从 URL 同步 — 保证 SSG HTML 有完整内容 */
  const [view, setView] = useState('plan');
  /* 5.27 M-116 · 计划版本回看 */
  const [versions, setVersions] = useState(['v0.1', 'v0.2', 'v0.3']);
  const [currentVersion, setCurrentVersion] = useState('v0.3');
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    const v = readUrlParam('view');
    if (v && PLAN_VIEWS.some((x) => x.key === v)) setView(v);
  }, []);

  const focus = FOCUS[view] || FOCUS.plan;

  return (
    <div className="jn-wrap" style={{ flex: 1, overflow: 'auto' }}>
      <div className="main-inner">
        <div className="page-head">
          <div>
            <h1>项目管理 · K1903</h1>
            <div className="sub">基础信息 · 计划（人货站） · 任务 · 风险 · 假设 · 变更</div>
          </div>
          <div className="right">
            <span>项目阶段</span>
            <span className="text-mono" style={{ color: '#1b84ff' }}>交付作业 · D+18</span>
          </div>
        </div>

        <VersionBar
          versions={versions}
          currentVersion={currentVersion}
          onSelectVersion={(v) => { setCurrentVersion(v); setDirty(false); }}
          onSaveDraft={() => setDirty(false)}
          onConfirm={() => {
            const next = bumpVersion(currentVersion);
            setVersions(vs => [...vs, next]);
            setCurrentVersion(next);
            setDirty(false);
          }}
          onConfirmWithVersion={(v) => {
            setVersions(vs => vs.includes(v) ? vs : [...vs, v]);
            setCurrentVersion(v);
            setDirty(false);
          }}
          dirty={dirty}
          confirmLabel="发布新版本 · +0.1"
        />


        <div className={`callout ${focus.tone === 'green' ? 'green' : focus.tone === 'amber' ? '' : focus.tone === 'red' ? '' : 'info'}`}
             style={{ marginBottom: 14 }}>
          <span style={{ fontWeight: 700 }}>快速开始 · </span>
          {focus.text}
        </div>

        <div className="snap-tabs">
          {PLAN_VIEWS.map((v) => (
            <button
              key={v.key}
              className={`snap-tab${view === v.key ? ' active' : ''}`}
              onClick={() => setView(v.key)}
            >
              <span>{v.label}</span>
              <span className="v-label">· {v.sub}</span>
            </button>
          ))}
        </div>

        {view === 'info'       && <InfoView />}
        {view === 'plan'       && <PlanView />}
        {view === 'task'       && <TaskView />}
        {view === 'raci'       && <RaciView />}
        {view === 'risk'       && <RiskView />}
        {view === 'assumption' && <AssumptionView />}
        {view === 'issue'      && <IssueView />}
        {view === 'change'     && <ChangeView />}
        {view === 'teams'      && <TeamsView />}
        {view === 'quality'    && <QualityView />}
      </div>

      {/* SVG 校正：主区底部 fixed 操作条 */}
      <ActionFooter
        dirty={dirty}
        onSaveDraft={() => setDirty(false)}
        onConfirm={() => {
          const next = bumpVersion(currentVersion);
          setVersions(vs => [...vs, next]);
          setCurrentVersion(next);
          setDirty(false);
        }}
        confirmLabel="发布新版本 · +0.1"
        readonly={currentVersion !== versions[versions.length - 1]}
      />
    </div>
  );
}

/* ─────────────────────────  5.28 H-5 · QualityView  ─────────────────────────
 *  4 张表一气合一，刻意不含"区域"字段
 *    1. 客户工程报单（E1）            —— 仅 状态，不含 区域
 *    2. Agent 问题列表（E3）          —— 仅 状态，不含 区域
 *    3. DOA 部件统计 · 柱图（E4）     —— 仅 销量合计 / 数量合计，去掉 基地 / 园区
 *    4. DOA 详情（E5）                —— 与 #3 同源，按部件展开
 * ────────────────────────────────────────────────────────── */

const ENG_TICKETS = [
  { id: 'ENG-2026-0612', title: 'A1-RM01 #07 机柜 PDU 跳闸',     submitter: '张航 · 客户值班',  team: '施工 03',   level: 'P1', state: 'doing',   eta: '06-13 14:00' },
  { id: 'ENG-2026-0608', title: 'B2-RM02 配电改造 + 验收',         submitter: '何萍 · 客户工程',  team: '配电 02',   level: 'P0', state: 'risk',    eta: '06-15 10:00' },
  { id: 'ENG-2026-0605', title: 'A3 到货 · 整柜清点漏 2 件',      submitter: '陈睿 · 客户仓储',  team: '仓储 01',   level: 'P2', state: 'done',    eta: '—'         },
  { id: 'ENG-2026-0601', title: 'C3 桥架预埋孔位偏差',             submitter: '何萍 · 客户工程',  team: '施工 02',   level: 'P2', state: 'pending', eta: '06-18 09:00' },
  { id: 'ENG-2026-0529', title: 'A1 冷池末端缝隙 > 5mm',           submitter: '韦楠 · 客户运维',  team: '机房 01',   level: 'P1', state: 'done',    eta: '—'         },
];

const AGENT_ISSUES = [
  { id: 'AGT-014', skill: '调测 · ZTP',     title: 'ZTP 升级偶发回滚（38 节点）',      raise: 'Agent · ZTP-Skill',  level: 'P0', state: 'doing',   updated: '今天 09:32' },
  { id: 'AGT-012', skill: '设计 · LLD',     title: '路由策略缺 BGP 邻居关键参数',     raise: 'Agent · LLD-Skill',  level: 'P1', state: 'done',    updated: '昨天 16:08' },
  { id: 'AGT-009', skill: '安装 · 一拍机',  title: '柜内布线遮挡 OOB',                raise: 'Agent · 安装-Skill', level: 'P2', state: 'pending', updated: '06-22 11:25' },
  { id: 'AGT-007', skill: '测试 · DOA',     title: '内存 ECC 误判 2 次 / 万小时',     raise: 'Agent · DOA-Skill',  level: 'P1', state: 'doing',   updated: '06-20 18:40' },
];

const DOA_PARTS = [
  { part: 'CPU',      sold: 1840, qty: 1840, doa:  4, rate: 0.22 },
  { part: 'GPU',      sold:  920, qty:  920, doa: 12, rate: 1.30 },
  { part: 'DIMM',     sold: 7360, qty: 7360, doa:  9, rate: 0.12 },
  { part: 'NIC',      sold: 1840, qty: 1840, doa:  3, rate: 0.16 },
  { part: 'SSD',      sold: 3680, qty: 3680, doa:  6, rate: 0.16 },
  { part: '电源',     sold:  920, qty:  920, doa:  2, rate: 0.22 },
  { part: '光模块',   sold: 9072, qty: 9072, doa: 18, rate: 0.20 },
  { part: '风扇',     sold: 1840, qty: 1840, doa:  1, rate: 0.05 },
];

const DOA_DETAIL = [
  { ts: '06-22 11:08', sn: 'SN-GPU-0091823', part: 'GPU',      lot: 'L20251214', supplier: '联营 A',   action: '换新', status: 'closed' },
  { ts: '06-21 09:42', sn: 'SN-OPT-0012873', part: '光模块',   lot: 'L20260118', supplier: '海光 D',   action: '换新', status: 'closed' },
  { ts: '06-19 16:31', sn: 'SN-DIMM-0098231',part: 'DIMM',     lot: 'L20260201', supplier: '海光 D',   action: '换新', status: 'open'   },
  { ts: '06-19 14:22', sn: 'SN-GPU-0091741', part: 'GPU',      lot: 'L20251214', supplier: '联营 A',   action: '研发回测', status: 'open' },
  { ts: '06-18 17:08', sn: 'SN-NIC-0001923', part: 'NIC',      lot: 'L20260102', supplier: '玖龙 B',   action: '换新', status: 'closed' },
];

const TICKET_TONE = { pending: 'gray', doing: 'blue', done: 'green', risk: 'red' } as const;
const ISSUE_TONE  = TICKET_TONE;

function QualityView() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* —— E1 · 客户工程报单 —— */}
      <section className="jn-panel">
        <div className="jn-panel-head">
          客户工程报单
          <span className="jn-panel-meta">{ENG_TICKETS.length} 单 · 不含「区域」字段，仅以「状态」收口</span>
        </div>
        <table className="vs-table">
          <thead>
            <tr>
              <th>单号</th>
              <th>问题描述</th>
              <th>提交人</th>
              <th>承接团队</th>
              <th>等级</th>
              <th>状态</th>
              <th>ETA</th>
            </tr>
          </thead>
          <tbody>
            {ENG_TICKETS.map(t => (
              <tr key={t.id}>
                <td className="text-mono">{t.id}</td>
                <td>{t.title}</td>
                <td>{t.submitter}</td>
                <td>{t.team}</td>
                <td><span className={`q-level lv-${t.level.toLowerCase()}`}>{t.level}</span></td>
                <td><span className={`q-state tone-${TICKET_TONE[t.state]}`}>{stateLabel(t.state)}</span></td>
                <td className="text-mono">{t.eta}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* —— E3 · Agent 问题列表 —— */}
      <section className="jn-panel">
        <div className="jn-panel-head">
          Agent 问题列表
          <span className="jn-panel-meta">{AGENT_ISSUES.length} 条 · 同样不含「区域」字段</span>
        </div>
        <table className="vs-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Skill</th>
              <th>问题</th>
              <th>来源</th>
              <th>等级</th>
              <th>状态</th>
              <th>更新</th>
            </tr>
          </thead>
          <tbody>
            {AGENT_ISSUES.map(t => (
              <tr key={t.id}>
                <td className="text-mono">{t.id}</td>
                <td><span className="q-skill">{t.skill}</span></td>
                <td>{t.title}</td>
                <td>{t.raise}</td>
                <td><span className={`q-level lv-${t.level.toLowerCase()}`}>{t.level}</span></td>
                <td><span className={`q-state tone-${ISSUE_TONE[t.state]}`}>{stateLabel(t.state)}</span></td>
                <td className="text-mono">{t.updated}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* —— E4 · DOA 部件统计（柱图）—— */}
      <section className="jn-panel">
        <div className="jn-panel-head">
          DOA 部件统计
          <span className="jn-panel-meta">仅 销量合计 / 数量合计 · 已删除 基地 / 园区</span>
        </div>
        <DoaPartsChart data={DOA_PARTS} />
      </section>

      {/* —— E5 · DOA 详情 —— */}
      <section className="jn-panel">
        <div className="jn-panel-head">
          DOA 详情
          <span className="jn-panel-meta">{DOA_DETAIL.length} 条 · 与上图同源 · 按 SN 展开</span>
        </div>
        <table className="vs-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>SN</th>
              <th>部件</th>
              <th>批次</th>
              <th>供应商</th>
              <th>处置</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            {DOA_DETAIL.map(d => (
              <tr key={d.sn}>
                <td className="text-mono">{d.ts}</td>
                <td className="text-mono">{d.sn}</td>
                <td>{d.part}</td>
                <td className="text-mono">{d.lot}</td>
                <td>{d.supplier}</td>
                <td>{d.action}</td>
                <td><span className={`q-state tone-${d.status === 'closed' ? 'green' : 'amber'}`}>{d.status === 'closed' ? '已闭环' : '处理中'}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function stateLabel(s: string) {
  switch (s) {
    case 'pending': return '待处理';
    case 'doing':   return '处理中';
    case 'done':    return '已闭环';
    case 'risk':    return '风险';
    default:        return s;
  }
}

function DoaPartsChart({ data }: { data: typeof DOA_PARTS }) {
  const maxSold = Math.max(...data.map(d => d.sold));
  return (
    <div className="doa-chart">
      <div className="doa-chart-bars">
        {data.map(d => {
          const h = (d.sold / maxSold) * 100;
          const doaH = (d.doa / d.sold) * 100 * 10; // 放大 10x 让红条可见
          return (
            <div key={d.part} className="doa-bar-col">
              <div className="doa-bar-col-stack">
                <div className="doa-bar sold" style={{ height: `${h}%` }}>
                  <span className="doa-bar-val text-mono">{d.sold.toLocaleString()}</span>
                </div>
                <div className="doa-bar doa-failed" style={{ height: `${Math.max(doaH, 2)}%` }}>
                  <span className="doa-bar-val text-mono">{d.doa}</span>
                </div>
              </div>
              <div className="doa-bar-label">{d.part}</div>
              <div className="doa-bar-rate text-mono">{d.rate.toFixed(2)}‰</div>
            </div>
          );
        })}
      </div>
      <div className="doa-chart-legend">
        <span><i className="legend-dot sold" /> 销量合计 / 数量合计</span>
        <span><i className="legend-dot doa-failed" /> DOA（×10 可视化）</span>
      </div>
    </div>
  );
}
