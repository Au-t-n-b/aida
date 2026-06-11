// @ts-nocheck
'use client';

import { useState } from 'react';
import { JOURNEY_STAGES } from '../../data/journey-data';
import VersionBar, { bumpVersion } from '../version-bar';
import ActionFooter from '../action-footer';

/* ── 章节列表（来自 DTRB / DRB 快照，作为 LLD 主版本冻结依据） ── */
const LLD_CHAPTERS = [
  { name: '1. 客户与项目背景',     state: 'ok',  size: '12 页' },
  { name: '2. 集群规划与拓扑',     state: 'ok',  size: '24 页' },
  { name: '3. 设备清单与 EOS',     state: 'ok',  size: '18 页 · BOQ 锁定' },
  { name: '4. 组网与链路设计',     state: 'ok',  size: '32 页 · 含拓扑图 6 张' },
  { name: '5. 机房物理布局',       state: 'ok',  size: '21 页 · 12 机柜归位 / 桥架路由完整' },
  { name: '6. 软件与平台栈',       state: 'ok',  size: '14 页 · k8s 1.30 LTS' },
  { name: '7. 集成验证需求',       state: 'ok',  size: '9 页 · CASE-AI-INFER-v2' },
  { name: '8. 风险与假设',         state: 'ok',  size: '6 页 · 全部闭环' },
  { name: '9. 初始交付计划',       state: 'ok',  size: '11 页 · 关键路径压缩 3 天' },
  { name: '10. 命名 / 网络段配置', state: 'ok',  size: '7 页 · 合同事件后补充' },
  { name: '11. 集成测试用例集',     state: 'ok',  size: '15 页 · 47 用例' },
  { name: '12. 验收性能指标',       state: 'ok',  size: '4 页 · p99 < 30ms / T/s ≥ 240' },
];

/* ── 集成测试用例集（mock） ── */
/* 5.25 M-020 · 测试用例状态流转
 * 已设计 → 执行中 → 通过 / 失败 */
const TEST_CASES = [
  { id: 'TC-INFER-001', name: 'AI 推理 · 单 PoD 端到端', priority: 'P0', expected: 'p99 ≤ 30ms', state: '通过',   actual: 'p99 28ms', ranAt: '2026-05-26 14:22' },
  { id: 'TC-INFER-002', name: 'AI 推理 · 跨 PoD 负载',   priority: 'P0', expected: 'T/s ≥ 240',  state: '通过',   actual: 'T/s 252',  ranAt: '2026-05-26 15:08' },
  { id: 'TC-INFER-003', name: '故障切换 · 单节点宕机',    priority: 'P0', expected: 'RTO ≤ 5s',   state: '执行中', actual: '—',        ranAt: '2026-05-27 10:11' },
  { id: 'TC-NET-001',   name: '组网 · 100G 链路压力',    priority: 'P0', expected: '丢包 < 10⁻⁶', state: '失败',   actual: '丢包 3×10⁻⁶', ranAt: '2026-05-27 09:35' },
  { id: 'TC-NET-002',   name: '组网 · 多业务隔离',       priority: 'P1', expected: 'VLAN 完整',  state: '已设计', actual: '—',        ranAt: '—' },
  { id: 'TC-OPS-001',   name: '运维 · 监控告警链路',      priority: 'P1', expected: '告警 ≤ 60s', state: '草稿',   actual: '—',        ranAt: '—' },
];
const TEST_STATE_META = {
  '草稿':    { tone: 'gray',  desc: '尚未确认' },
  '已设计':  { tone: 'blue',  desc: '可执行' },
  '执行中':  { tone: 'amber', desc: '正在跑' },
  '通过':    { tone: 'green', desc: '断言达成' },
  '失败':    { tone: 'red',   desc: '断言未达成' },
};

/* ── 网络段配置 ── */
const NET_SEGMENTS = [
  { name: '管理网段',      cidr: '10.193.0.0/16',  vlan: 'VLAN 100', usage: 'BMC / 监控 / 运维' },
  { name: '业务网段',      cidr: '10.194.0.0/16',  vlan: 'VLAN 200', usage: 'AI 推理业务' },
  { name: '存储网段',      cidr: '10.195.0.0/16',  vlan: 'VLAN 300', usage: '分布式存储 · NVMe-oF' },
  { name: 'GPU 互联网段',  cidr: '10.196.0.0/16',  vlan: 'VLAN 400', usage: 'NVLink / RoCE v2' },
];

/* G-13 · 服务器网络配置配套表（5.27 会议）
 * 字段：服务器角色 · 上联交换机 · 网卡型号 · 端口 · 速率 · 所属网段 · IP 段 · MTU · 备注
 * 用途：把网段规划落到「每台服务器要插哪几张网卡 / 上行哪几个交换机」的执行级清单 */
const SERVER_NET_CONFIG = [
  {
    role: 'AI 计算节点 · A3 SuperPoD',
    uplink: 'Leaf1 / Leaf11',
    nic: 'Hi1822 SP680',
    ports: '2 × 100GE',
    speed: '100GE',
    segment: '业务 / 样本面',
    ipRange: '10.194.10.0/22',
    mtu: 9000,
    note: '断点续训聚合 6.7 GB/s',
  },
  {
    role: 'AI 计算节点 · A3 SuperPoD',
    uplink: 'L2HCCS sw1 / sw224',
    nic: 'Hi1822 SP680',
    ports: '8 × 200GE',
    speed: '200GE',
    segment: 'GPU 互联（HCCS 平面）',
    ipRange: '10.196.0.0/20',
    mtu: 9000,
    note: 'NPU-NPU NVLink/RoCE v2',
  },
  {
    role: 'AI 计算节点 · A3 SuperPoD',
    uplink: 'BMC 接入',
    nic: '板载 1GE',
    ports: '1 × 1GE',
    speed: '1GE',
    segment: '管理（BMC）',
    ipRange: '10.193.10.0/22',
    mtu: 1500,
    note: 'iBMC / 带外运维',
  },
  {
    role: '存储节点 · X 系列',
    uplink: 'Leaf11',
    nic: 'CX6 Dx',
    ports: '4 × 100GE',
    speed: '100GE',
    segment: '存储（NVMe-oF）',
    ipRange: '10.195.0.0/20',
    mtu: 9000,
    note: '分布式 EC · 算存比 100:1',
  },
  {
    role: '管理服务器 · 通用',
    uplink: 'BMC 汇聚',
    nic: '板载 4×10GE',
    ports: '2 × 10GE',
    speed: '10GE',
    segment: '管理 / 运维',
    ipRange: '10.193.0.0/22',
    mtu: 1500,
    note: 'NCE-F / FI / 监控平台',
  },
  {
    role: '运管 / 训练平台节点',
    uplink: '运管接入',
    nic: '板载 4×25GE',
    ports: '2 × 25GE',
    speed: '25GE',
    segment: '业务',
    ipRange: '10.194.200.0/24',
    mtu: 1500,
    note: 'CCAE / MindX DL',
  },
];

const SPEED_TONE = {
  '400GE': 'red',
  '200GE': 'amber',
  '100GE': 'cyan',
  '25GE':  'sky',
  '10GE':  'yellow',
  '1GE':   'gray',
};

/* ── 关键性能指标 ── */
const KPIS = [
  { k: '推理 p99 时延',     v: '< 30 ms',   src: '合同 §6 验收条款' },
  { k: '吞吐 (T/s)',       v: '≥ 240',    src: '合同 §6 验收条款' },
  { k: '可用性',           v: '≥ 99.95%', src: 'SLA 协议' },
  { k: 'GPU 利用率（峰值）', v: '≥ 80%',    src: '客户业务目标' },
  { k: '功耗 PUE',         v: '< 1.25',   src: '机房合同要求' },
];

/* ── 子 tab ── */
const TABS = [
  { key: 'overview', label: '概览',           sub: '冻结状态 / 章节齐备' },
  { key: 'fields',   label: 'LLD 关键字段',    sub: '命名 / 网络 / 用例 / 指标' },
  { key: 'planes',   label: '共平面规划',      sub: '业务/网管/存储/超平面 多选' }, /* 5.27 R-5 */
  { key: 'rooms',    label: '机房 / 机柜 (CAD)', sub: 'CAD 解析有就读，没有就填' }, /* NEW-10 SVG L208 */
  { key: 'tests',    label: '集成测试用例集',   sub: 'CASE-AI-INFER-v2 · 47 项' },
  { key: 'diff',     label: '与 DRB 差异',     sub: '合同事件后增量' },
];

/* NEW-10 · 机房机柜 + CAD 解析视图（SVG L208-210）
 * "CAD 解析，有就解析没有就填" —— 有 CAD 自动列出机房 / 机柜；没 CAD 显示手填提示 */
const ROOMS_FROM_CAD = [
  { id: 'A1-RM01', cad: 'A1-floor-plan.dwg', racks: 24, used: 18, area: 320, status: 'parsed',  note: 'CAD 自动解析' },
  { id: 'A1-RM02', cad: 'A1-floor-plan.dwg', racks: 24, used: 22, area: 320, status: 'parsed',  note: 'CAD 自动解析' },
  { id: 'A1-RM03', cad: 'A1-floor-plan.dwg', racks: 12, used: 4,  area: 180, status: 'parsed',  note: 'CAD 自动解析' },
  { id: 'B2-RM01', cad: 'B2-floor-plan.dwg', racks: 18, used: 14, area: 280, status: 'parsed',  note: 'CAD 自动解析' },
  { id: 'B2-RM02', cad: null,                 racks: 0,  used: 0,  area: 0,   status: 'manual',  note: '客户未提供 CAD · 待 TD 手填' },
  { id: 'C3-RM01', cad: 'C3-floor.dxf',       racks: 12, used: 10, area: 200, status: 'parsed',  note: 'DXF 兜底解析' },
];
function RoomsCadView() {
  return (
    <div className="jn-panel" style={{ padding: 0 }}>
      <div className="jn-panel-head" style={{ padding: '12px 14px' }}>
        机房 / 机柜清单（{ROOMS_FROM_CAD.length} 间）· <span style={{ color: 'var(--c-text-muted)', fontWeight: 400 }}>CAD 解析有则读，没有则手填</span>
      </div>
      <table className="vs-table">
        <thead>
          <tr>
            <th>机房</th>
            <th>CAD 源</th>
            <th className="num">机柜总数</th>
            <th className="num">已占用</th>
            <th className="num">面积 m²</th>
            <th>状态</th>
            <th>备注</th>
          </tr>
        </thead>
        <tbody>
          {ROOMS_FROM_CAD.map(r => (
            <tr key={r.id} className={r.status === 'manual' ? 'has-conflict' : ''}>
              <td style={{ fontFamily: 'var(--font-mono)' }}>{r.id}</td>
              <td>
                {r.cad
                  ? <span className="data-source-badge tone-green"><span className="data-source-dot" />CAD</span>
                  : <span className="data-source-badge tone-amber"><span className="data-source-dot" />无 CAD</span>}
                {r.cad && <span style={{ marginLeft: 6, fontSize: 11, color: 'var(--c-text-muted)' }}>{r.cad}</span>}
              </td>
              <td className="num">
                {r.status === 'manual'
                  ? <input type="number" defaultValue={0} className="boq-qty-input" placeholder="手填" />
                  : <strong>{r.racks}</strong>}
              </td>
              <td className="num"><strong>{r.used || '—'}</strong></td>
              <td className="num">{r.area || <input type="number" defaultValue={0} className="boq-qty-input" placeholder="手填" />}</td>
              <td>
                <span className={`status-pill ${r.status === 'parsed' ? 'green' : 'amber'}`}>
                  {r.status === 'parsed' ? '已解析' : '待手填'}
                </span>
              </td>
              <td style={{ fontSize: 11, color: 'var(--c-text-muted)' }}>{r.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ padding: '10px 14px', fontSize: 11, color: 'var(--c-text-muted)', borderTop: '1px solid var(--c-border)' }}>
        <strong style={{ color: 'var(--c-warning)' }}>兜底策略</strong>：CAD 自动解析做不到时（如 B2-RM02），由 TD 手工填 + AIDA 校验。
      </div>
    </div>
  );
}

/* 5.27 R-5 · 共平面类型多选（业务面 / 网管面 / 存储面 / 超平面）*/
const COMMON_PLANES = [
  { key: 'business', label: '业务面', desc: 'AI 训练/推理流量主通道，400G RDMA',  default: true },
  { key: 'oam',      label: '网管面', desc: 'OAM 设备管理 + 监控告警，1G 隔离',    default: true },
  { key: 'storage',  label: '存储面', desc: '训练数据集 + checkpoint，100G RoCE', default: true },
  { key: 'super',    label: '超平面', desc: 'GPU 间集合通信，200G/400G 无损以太', default: false },
];
function CommonPlanesView() {
  const [selected, setSelected] = useState(
    () => new Set(COMMON_PLANES.filter(p => p.default).map(p => p.key))
  );
  /* NEW-8 · 共平面"加备注列"（SVG L207） */
  const [notes, setNotes] = useState({});
  const toggle = (k) => setSelected(s => {
    const next = new Set(s);
    if (next.has(k)) next.delete(k); else next.add(k);
    return next;
  });
  return (
    <div className="jn-panel" style={{ padding: 0 }}>
      <div className="jn-panel-head" style={{ padding: '12px 14px' }}>
        共平面规划（多选 + 备注）· <span style={{ color: 'var(--c-text-muted)', fontWeight: 400 }}>详情请联系网络架构师对齐</span>
      </div>
      <div className="plane-grid">
        {COMMON_PLANES.map(p => (
          <div key={p.key} className={`plane-card${selected.has(p.key) ? ' on' : ''}`}>
            <label style={{ cursor: 'pointer', display: 'block' }}>
              <input
                type="checkbox"
                checked={selected.has(p.key)}
                onChange={() => toggle(p.key)}
              />
              <div className="plane-card-name">{p.label}</div>
              <div className="plane-card-desc">{p.desc}</div>
              {selected.has(p.key) && <span className="plane-card-tag">已选</span>}
            </label>
            {/* NEW-8 · 每个平面一个备注输入 */}
            <input
              type="text"
              className="plane-card-note"
              placeholder="备注（VLAN 段 / 带宽 / 隔离要求 …）"
              value={notes[p.key] || ''}
              onChange={e => setNotes(n => ({ ...n, [p.key]: e.target.value }))}
              disabled={!selected.has(p.key)}
            />
          </div>
        ))}
      </div>
      <div className="plane-note">
        已选 <strong>{selected.size}</strong> / {COMMON_PLANES.length} 个平面。每个平面对应一组 VLAN + 路由策略，备注会随平面写入 LLD §6 网络规划。
      </div>

      {/* NEW-9 · 设计阶段顺序约束（SVG L203）*/}
      <div className="plane-flow">
        <strong>设计顺序</strong>
        <span className="plane-flow-step done">① 组网（共平面）</span>
        <span className="plane-flow-arrow">→</span>
        <span className="plane-flow-step current">② 设备清单（BOQ 7 部件）</span>
        <span className="plane-flow-arrow">→</span>
        <span className="plane-flow-step">③ 角色 & 责任矩阵</span>
        <span className="plane-flow-hint">设计顺序约束：先组网、再设备清单、后角色 —— 不可跳序</span>
      </div>
    </div>
  );
}

function Overview({ stage }) {
  const c = stage.contractEvent;
  return (
    <>
      <div className="snap-meta">
        <div className="snap-meta-cell"><div className="k">主版本</div><div className="v">LLD-v1.0</div></div>
        <div className="snap-meta-cell"><div className="k">冻结时间</div><div className="v">{c.bindTs}</div></div>
        <div className="snap-meta-cell"><div className="k">合同 ID</div><div className="v">{c.id}</div></div>
        <div className="snap-meta-cell"><div className="k">合同金额</div><div className="v">{c.amount}</div></div>
        <div className="snap-meta-cell"><div className="k">里程碑</div><div className="v">{c.milestones} 项</div></div>
        <div className="snap-meta-cell"><div className="k">章节</div><div className="v">{LLD_CHAPTERS.length}</div></div>
      </div>

      <div className="jn-panel" style={{ marginBottom: 0 }}>
        <div className="jn-panel-head">章节齐备情况</div>
        <div className="jn-chapters">
          {LLD_CHAPTERS.map((c) => (
            <div key={c.name} className={`jn-chapter state-${c.state}`}>
              <span className="jn-chapter-name">{c.name}</span>
              <span className="jn-chapter-note">{c.size}</span>
              <span className={`jn-chapter-pill state-${c.state}`}>齐备</span>
            </div>
          ))}
        </div>
      </div>

      <div className="callout green" style={{ marginTop: 14 }}>
        <span style={{ fontWeight: 700 }}>已冻结基线 · </span>
        LLD-v1.0 已绑定合同 {c.id}，作为本次交付的唯一权威依据。后续任何变更须走变更单（/plan?view=change）。
      </div>
    </>
  );
}

function FieldsView({ stage }) {
  return (
    <>
      <div className="jn-panel">
        <div className="jn-panel-head">LLD 必要字段（合同事件后由 TD 补充）</div>
        <div className="jn-lld">
          {stage.lldFields.map((f) => (
            <div key={f.k} className="jn-lld-row">
              <span className="k">{f.k}</span>
              <span className="v">{f.v}</span>
              <span className={`pill state-${f.state}`}>已确认</span>
            </div>
          ))}
        </div>
      </div>

      <div className="jn-grid-2" style={{ marginTop: 12 }}>
        <div className="jn-panel">
          <div className="jn-panel-head">网络段规划</div>
          <table className="vs-table">
            <thead>
              <tr><th>网段名称</th><th>CIDR</th><th>VLAN</th><th>用途</th></tr>
            </thead>
            <tbody>
              {NET_SEGMENTS.map((n) => (
                <tr key={n.name}>
                  <td>{n.name}</td>
                  <td className="num" style={{ fontFamily: 'var(--font-mono)' }}>{n.cidr}</td>
                  <td className="num" style={{ fontFamily: 'var(--font-mono)' }}>{n.vlan}</td>
                  <td>{n.usage}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="jn-panel">
          <div className="jn-panel-head">验收性能指标（KPI）</div>
          <div className="jn-stats">
            {KPIS.map((k) => (
              <div key={k.k} className="jn-stat">
                <div className="jn-stat-k">{k.k}</div>
                <div className="jn-stat-v">{k.v}</div>
                <div style={{ fontSize: 10, color: 'var(--c-text-faint)', marginTop: 2 }}>{k.src}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* G-13 · 服务器网络配置配套表（与网段规划成对出现，落到每台机的实施级清单） */}
      <div className="jn-panel" style={{ marginTop: 12 }}>
        <div className="jn-panel-head" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span>服务器网络配置配套表（每类节点的网卡 / 端口 / 上行 / 网段映射）</span>
          <span style={{ fontSize: 11, color: 'var(--c-text-muted)', fontWeight: 500 }}>
            网段规划 → 服务器实施级清单
          </span>
        </div>
        <table className="vs-table server-net-table">
          <thead>
            <tr>
              <th style={{ width: 220 }}>服务器角色</th>
              <th style={{ width: 160 }}>上联交换机</th>
              <th style={{ width: 130 }}>网卡型号</th>
              <th style={{ width: 110 }}>端口配置</th>
              <th style={{ width: 70 }}>速率</th>
              <th style={{ width: 160 }}>所属网段</th>
              <th style={{ width: 150 }}>IP 段（规划）</th>
              <th style={{ width: 64 }}>MTU</th>
              <th>备注</th>
            </tr>
          </thead>
          <tbody>
            {SERVER_NET_CONFIG.map((r, i) => (
              <tr key={i}>
                <td><strong>{r.role}</strong></td>
                <td className="num" style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}>{r.uplink}</td>
                <td className="num" style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}>{r.nic}</td>
                <td className="num" style={{ fontFamily: 'var(--font-mono)' }}>{r.ports}</td>
                <td>
                  <span className={`speed-chip tone-${SPEED_TONE[r.speed] || 'gray'}`}>{r.speed}</span>
                </td>
                <td>{r.segment}</td>
                <td className="num" style={{ fontFamily: 'var(--font-mono)' }}>{r.ipRange}</td>
                <td className="num">{r.mtu}</td>
                <td style={{ fontSize: 11.5, color: 'var(--c-text-muted)' }}>{r.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function TestsView() {
  /* 5.25 M-020 · 状态聚合统计 */
  const counts = TEST_CASES.reduce((acc, t) => { acc[t.state] = (acc[t.state] || 0) + 1; return acc; }, {});
  return (
    <div className="jn-panel" style={{ padding: 0 }}>
      <div className="jn-panel-head" style={{ padding: '12px 14px' }}>
        集成测试用例集（CASE-AI-INFER-v2 · 共 47 项 · 显示 6 项关键）
      </div>
      {/* 状态汇总条 */}
      <div className="test-state-summary">
        {Object.entries(TEST_STATE_META).map(([state, m]) => (
          <span key={state} className={`test-state-pill tone-${m.tone}`}>
            <span className="test-state-dot" /> {state} <strong>{counts[state] || 0}</strong>
          </span>
        ))}
      </div>
      <table className="vs-table">
        <thead>
          <tr><th>用例 ID</th><th>名称</th><th>优先级</th><th>预期结果</th><th>实际结果</th><th>状态</th><th>最近执行</th></tr>
        </thead>
        <tbody>
          {TEST_CASES.map((t) => {
            const m = TEST_STATE_META[t.state] || { tone: 'gray' };
            return (
              <tr key={t.id} className={t.state === '失败' ? 'has-conflict' : ''}>
                <td className="num" style={{ fontFamily: 'var(--font-mono)' }}>{t.id}</td>
                <td>{t.name}</td>
                <td>
                  <span className={`status-pill ${t.priority === 'P0' ? 'red' : 'amber'}`}>{t.priority}</span>
                </td>
                <td className="num" style={{ fontFamily: 'var(--font-mono)' }}>{t.expected}</td>
                <td className="num" style={{ fontFamily: 'var(--font-mono)', color: t.state === '失败' ? 'var(--c-danger)' : 'inherit' }}>{t.actual}</td>
                <td>
                  <span className={`test-state-pill tone-${m.tone}`}><span className="test-state-dot" />{t.state}</span>
                </td>
                <td style={{ fontSize: 11, color: 'var(--c-text-muted)' }}>{t.ranAt}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function DiffView() {
  const drb = JOURNEY_STAGES.find((s) => s.key === 'drb');
  /* LLD - DRB 增量 */
  const lldAdds = [
    { ch: '10. 命名方案',   change: '+ K1903-{room}-{rack}-{u}（合同事件后）' },
    { ch: '10. 网络段',     change: '+ 4 段：管理 / 业务 / 存储 / GPU 互联' },
    { ch: '11. 测试用例',   change: '+ 47 用例（CASE-AI-INFER-v2）' },
    { ch: '12. 验收 KPI',  change: '+ p99 / T/s / 可用性 / GPU 利用 / PUE' },
    { ch: '8. 假设',       change: '- 全部 5 项已闭环' },
  ];
  return (
    <div className="jn-grid-2">
      <div className="jn-panel">
        <div className="jn-panel-head">DRB → LLD 增量</div>
        <div className="jn-diff">
          {lldAdds.map((d, i) => (
            <div key={i} className="jn-diff-row">
              <span className="jn-diff-ch">{d.ch}</span>
              <span style={{ color: 'var(--c-text-muted)' }}>→</span>
              <span className="jn-diff-change">{d.change}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="jn-panel">
        <div className="jn-panel-head">DRB v{drb?.snapshot?.version || '1.0'} · 历史增量（参考）</div>
        <div className="jn-diff">
          {drb?.snapshot?.diff?.map((d, i) => (
            <div key={i} className="jn-diff-row">
              <span className="jn-diff-ch">{d.ch}</span>
              <span style={{ color: 'var(--c-text-muted)' }}>→</span>
              <span className="jn-diff-change">{d.change}</span>
            </div>
          ))}
        </div>
        <div className="jn-hint" style={{ marginTop: 8 }}>
          注：完整 DTRB → DRB → LLD 三快照流可在 /preview 中对照查看。
        </div>
      </div>
    </div>
  );
}

const FOCUS = {
  overview: { tone: 'green', text: 'LLD-v1.0 已冻结 · 12 章节全部齐备。这是预案三快照的最后一站，也是后续交付作业的唯一基线。' },
  fields:   { tone: 'info',  text: '合同事件后由 TD 补充的 5 项关键字段：命名方案 / 管理网段 / 业务网段 / 集成测试用例集 / 验收性能指标。' },
  planes:   { tone: 'info',  text: '共平面规划：业务面 / 网管面 / 存储面 / 超平面 多选 + 备注。先组网 → 再设备清单 → 后角色。' },
  rooms:    { tone: 'amber', text: 'CAD 解析有就读，没有就填。CAD 自动解析做不到时改为 TD 手填 + AIDA 校验。' },
  tests:    { tone: 'info',  text: 'CASE-AI-INFER-v2 共 47 项用例 · P0 优先（推理时延/吞吐/故障切换）。验收阶段由调测自动采集。' },
  diff:     { tone: 'amber', text: '相对 DRB v1.0 增量：本阶段新增 3 章（命名/网络/用例/指标），其余章节内容刷新但要素无新增。' },
};

export default function DesignScreen() {
  const stage = JOURNEY_STAGES.find((s) => s.key === 'contract');
  const [tab, setTab] = useState('overview');
  /* 5.27 M-116 · VersionBar：LLD 主版本支持只读历史回看 + 草稿/确认 */
  const [versions, setVersions] = useState(['v0.8', 'v0.9', 'v1.0']);
  const [currentVersion, setCurrentVersion] = useState('v1.0');
  const [dirty, setDirty] = useState(false);
  if (!stage) return null;
  const focus = FOCUS[tab] || FOCUS.overview;

  return (
    <div className="jn-wrap" style={{ flex: 1, overflow: 'auto' }}>
      <div className="main-inner">
        <div className="page-head">
          <div>
            <h1>交付方案 · LLD 主版本（K1903）</h1>
            <div className="sub">合同事件触发 · 冻结基线 · 后续作业唯一依据</div>
          </div>
          <div className="right">
            <span>状态</span>
            <span className="text-mono" style={{ color: 'var(--c-success)' }}>已冻结 · LLD-v1.0</span>
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
          confirmLabel="冻结新 LLD · 版本 +0.1"
        />


        <div className={`callout ${focus.tone === 'green' ? 'green' : focus.tone === 'amber' ? '' : 'info'}`} style={{ marginBottom: 14 }}>
          <span style={{ fontWeight: 700 }}>快速开始 · </span>
          {focus.text}
        </div>

        <div className="snap-tabs">
          {TABS.map((t) => (
            <button key={t.key} className={`snap-tab${tab === t.key ? ' active' : ''}`} onClick={() => setTab(t.key)}>
              <span>{t.label}</span>
              <span className="v-label">· {t.sub}</span>
            </button>
          ))}
        </div>

        {tab === 'overview' && <Overview stage={stage} />}
        {tab === 'fields'   && <FieldsView stage={stage} />}
        {tab === 'planes'   && <CommonPlanesView />}
        {tab === 'rooms'    && <RoomsCadView />}
        {tab === 'tests'    && <TestsView />}
        {tab === 'diff'     && <DiffView />}
      </div>

      {/* SVG 校正：主区底部 fixed 「保存草稿 / 确认」 */}
      <ActionFooter
        dirty={dirty}
        onSaveDraft={() => setDirty(false)}
        onConfirm={() => {
          const next = bumpVersion(currentVersion);
          setVersions(vs => [...vs, next]);
          setCurrentVersion(next);
          setDirty(false);
        }}
        confirmLabel="冻结 LLD · 版本 +0.1"
        readonly={currentVersion !== versions[versions.length - 1]}
      />
    </div>
  );
}
