// @ts-nocheck
'use client';

import { useState, useEffect } from 'react';

/* 读 URL 参数 — 不用 useSearchParams 避免静态导出后 Suspense fallback=null 空白 */
function readUrlParam(key) {
  if (typeof window === 'undefined') return null;
  return new URLSearchParams(window.location.search).get(key);
}

/* ── 子 tab ── */
const TABS = [
  { key: 'integration', label: '接入与集成',     sub: '上游 / 下游系统 8 个' },
  { key: 'roles',       label: '用户与角色',     sub: 'TD / PD / TL / OCC / AIDA' },
  { key: 'privacy',     label: '数据与隐私',     sub: 'OCC 审批策略 / 敏感字段' },
  { key: 'ai',          label: 'AI / 模型',     sub: 'AIDA 模型路由 / 大脑数据源' },
  /* 5.28 H-7 · Sub-Skills 管理（H1-H5） */
  { key: 'skills',      label: 'Sub-Skills',   sub: '作业工序 · 执行机 · 工具 · 三层架构' },
  { key: 'audit',       label: '审计日志',       sub: '最近 50 条' },
];

/* ── 集成（陈卓接口 = 合同事件流） ── */
const INTEGRATIONS = [
  { id: 'INT-CHENZ',   name: '陈卓 · 合同事件流',     dir: '上游', state: 'live',   ts: '2026-05-26 14:31', desc: '监听合同签署 → 自动触发 LLD' },
  { id: 'INT-PROP',    name: 'Proposal 系统',         dir: '上游', state: 'live',   ts: '2026-05-26 14:28', desc: '机会点 / BOQ 拉取' },
  { id: 'INT-OCC',     name: 'OCC 数据出境审批',       dir: '上游', state: 'live',   ts: '2026-05-26 14:25', desc: 'TD 提交后路由到 OCC' },
  { id: 'INT-WELINK',  name: 'WeLink 通知',           dir: '下游', state: 'live',   ts: '2026-05-26 14:25', desc: '合同事件后推送 TD' },
  { id: 'INT-WIKI',    name: 'Wiki 大脑',             dir: '上游', state: 'live',   ts: '2026-05-26 14:00', desc: '12k 条业务术语 / 历史复盘' },
  { id: 'INT-DORA',    name: 'DORA 本体建模',         dir: '上游', state: 'live',   ts: '2026-05-26 13:54', desc: 'v3.4 · 463 个本体类' },
  { id: 'INT-MES',     name: '供应链 MES',            dir: '上游', state: 'warn',   ts: '2026-05-26 12:08', desc: '物流 ETA · 偶发延迟 5 ~ 10 分钟' },
  { id: 'INT-PLM',     name: '设备 PLM (EOS)',        dir: '上游', state: 'live',   ts: '2026-05-26 11:42', desc: '设备版本 / EOS 信息' },
];

const ROLES = [
  { role: 'TD · 技术总监', count: 23, perms: ['建项目', '上传文档', '提 OCC', '审批 LLD', '冻结基线'], note: '何博 等' },
  { role: 'PD · 项目总监', count: 31, perms: ['看板',     '风险升级', '人员调度', '客户协同'],         note: '李伟 / 周晗 / 张悦 等' },
  { role: 'TL · 作业人员', count: 184, perms: ['作业打卡', '问题上报', '验收数据'],                   note: '12 队' },
  { role: 'OCC · 合规',   count: 6,   perms: ['审批数据出境', '敏感字段策略', '驳回 / 升级'],          note: '黎芳 等' },
  { role: 'AIDA · AI',    count: 1,   perms: ['只读全量', '推理 / 沙箱', '自动产出报告'],              note: '系统账号' },
];

const SENSITIVE_FIELDS = [
  { cat: '客户敏感',   fields: ['地址', '联系人', '联系方式', '客户合同金额'], rule: '一律红高亮 / 出境前 OCC 审批' },
  { cat: '合规字段',   fields: ['出口管制清单', '加密设备型号'],            rule: '禁止外送 · 仅本地处理' },
  { cat: '商业敏感',   fields: ['毛利率', '采购成本', '供应商名单'],         rule: '橙高亮 / TD+ 可见' },
  { cat: '人员隐私',   fields: ['身份证号', '银行账户'],                   rule: '加密存储 / 不在前端出现' },
];

const AI_ROUTES = [
  { task: '风险研判（高复杂度）',       model: 'Claude 4.6 Sonnet (thinking)', latency: '~ 6.2s', cost: '高' },
  { task: '日常 QA / 摘要',           model: 'GPT-5.5 medium',              latency: '~ 1.4s', cost: '中' },
  { task: '文档解析 · 多模态',         model: '内部 AIDA-DocParser-v2',      latency: '~ 8.8s', cost: '中' },
  { task: '沙箱推演 · 长上下文',       model: 'Composer-2.5-fast',          latency: '~ 4.1s', cost: '低' },
  { task: '代码 / 配置生成',          model: 'GPT-5.3 Codex',              latency: '~ 2.0s', cost: '中' },
];

const AUDIT_LOG = [
  { ts: '14:42', who: 'AIDA',     act: '生成 DTRB v1.0',                    target: 'K1903 · 项目空间' },
  { ts: '14:31', who: '系统',      act: '识别合同事件 · CON-2026-K1903-001', target: 'K1903 · 项目空间' },
  { ts: '14:28', who: '何博',      act: '提交项目初始化 5 项字段',            target: 'K1903 · proposal 绑定' },
  { ts: '14:21', who: 'OCC 黎芳', act: '审批通过 · K1903 数据关联范围',      target: 'OCC · 审批中心' },
  { ts: '14:08', who: 'AIDA',     act: '完成风险扫描 · 3 处敏感字段',        target: 'K1903 · BOQ' },
  { ts: '13:54', who: '系统',      act: 'DORA v3.4 完成同步（463 个本体类）', target: '本体建模' },
  { ts: '12:08', who: 'MES',      act: '供应链 ETA 数据延迟报警 (8 分钟)',    target: '集成监控' },
  { ts: '11:42', who: '系统',      act: 'PLM EOS 信息每日同步完成',           target: '资产中心' },
];

const STATE_TONE = { live: 'green', warn: 'amber', down: 'red' };

/* ── 各视图 ── */
function IntegrationView() {
  return (
    <div className="jn-panel" style={{ padding: 0 }}>
      <div className="jn-panel-head" style={{ padding: '12px 14px' }}>
        系统集成（共 {INTEGRATIONS.length} 个 · 上游 6 / 下游 1 / 双向 1）
      </div>
      <table className="vs-table">
        <thead>
          <tr><th>ID</th><th>系统名称</th><th>方向</th><th>用途</th><th>最近心跳</th><th>状态</th></tr>
        </thead>
        <tbody>
          {INTEGRATIONS.map((i) => (
            <tr key={i.id}>
              <td className="num" style={{ fontFamily: 'var(--font-mono)' }}>{i.id}</td>
              <td><strong>{i.name}</strong></td>
              <td>{i.dir}</td>
              <td>{i.desc}</td>
              <td className="num" style={{ fontFamily: 'var(--font-mono)' }}>{i.ts}</td>
              <td>
                <span className={`status-pill ${STATE_TONE[i.state]}`}>
                  {i.state === 'live' ? '在线' : i.state === 'warn' ? '降级' : '离线'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RolesView() {
  return (
    <div className="jn-panel" style={{ padding: 0 }}>
      <div className="jn-panel-head" style={{ padding: '12px 14px' }}>
        角色与权限矩阵（共 {ROLES.reduce((s, r) => s + r.count, 0)} 个账号）
      </div>
      <table className="vs-table">
        <thead>
          <tr><th>角色</th><th>账号数</th><th>核心权限</th><th>代表</th></tr>
        </thead>
        <tbody>
          {ROLES.map((r) => (
            <tr key={r.role}>
              <td><strong>{r.role}</strong></td>
              <td className="num">{r.count}</td>
              <td>
                {r.perms.map((p) => (
                  <span key={p} className="status-pill" style={{ marginRight: 4 }}>{p}</span>
                ))}
              </td>
              <td style={{ color: 'var(--c-text-muted)' }}>{r.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PrivacyView() {
  return (
    <div className="jn-grid-2">
      <div className="jn-panel">
        <div className="jn-panel-head">敏感字段策略（OCC 审批依据）</div>
        <div className="jn-lld">
          {SENSITIVE_FIELDS.map((c) => (
            <div key={c.cat} className="jn-lld-row" style={{ alignItems: 'flex-start', flexWrap: 'wrap' }}>
              <span className="k">{c.cat}</span>
              <span className="v" style={{ flex: 1 }}>
                {c.fields.map((f) => (
                  <span key={f} className="status-pill amber" style={{ marginRight: 4, marginBottom: 4 }}>{f}</span>
                ))}
                <div style={{ fontSize: 11, color: 'var(--c-text-muted)', marginTop: 4 }}>{c.rule}</div>
              </span>
            </div>
          ))}
        </div>
      </div>
      <div className="jn-panel">
        <div className="jn-panel-head">OCC 审批参数</div>
        <div className="jn-stats">
          <div className="jn-stat"><div className="jn-stat-k">SLA · 平均</div><div className="jn-stat-v">38 分钟</div></div>
          <div className="jn-stat"><div className="jn-stat-k">SLA · 最大</div><div className="jn-stat-v">2.4 小时</div></div>
          <div className="jn-stat"><div className="jn-stat-k">通过率</div><div className="jn-stat-v">94%</div></div>
          <div className="jn-stat"><div className="jn-stat-k">驳回率</div><div className="jn-stat-v">3%</div></div>
          <div className="jn-stat"><div className="jn-stat-k">补充材料</div><div className="jn-stat-v">3%</div></div>
          <div className="jn-stat"><div className="jn-stat-k">本月审批</div><div className="jn-stat-v">42 次</div></div>
        </div>
        <div className="jn-hint" style={{ marginTop: 8 }}>
          注：所有出境数据访问会自动触发 OCC 审批，敏感字段在前端永远红 / 橙高亮。
        </div>
      </div>
    </div>
  );
}

function AIView() {
  return (
    <>
      <div className="jn-panel" style={{ padding: 0 }}>
        <div className="jn-panel-head" style={{ padding: '12px 14px' }}>AIDA 模型路由（按任务类型）</div>
        <table className="vs-table">
          <thead>
            <tr><th>任务类型</th><th>路由模型</th><th>P50 时延</th><th>成本</th></tr>
          </thead>
          <tbody>
            {AI_ROUTES.map((a) => (
              <tr key={a.task}>
                <td><strong>{a.task}</strong></td>
                <td className="num" style={{ fontFamily: 'var(--font-mono)' }}>{a.model}</td>
                <td className="num">{a.latency}</td>
                <td>
                  <span className={`status-pill ${a.cost === '高' ? 'red' : a.cost === '中' ? 'amber' : 'green'}`}>{a.cost}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="jn-grid-2" style={{ marginTop: 12 }}>
        <div className="jn-panel">
          <div className="jn-panel-head">Wiki 大脑数据源</div>
          <div className="jn-stats">
            <div className="jn-stat"><div className="jn-stat-k">业务术语库</div><div className="jn-stat-v">2,341</div></div>
            <div className="jn-stat"><div className="jn-stat-k">历史项目复盘</div><div className="jn-stat-v">184</div></div>
            <div className="jn-stat"><div className="jn-stat-k">交付规则库</div><div className="jn-stat-v">67</div></div>
            <div className="jn-stat"><div className="jn-stat-k">总条目</div><div className="jn-stat-v">12,083</div></div>
          </div>
        </div>
        <div className="jn-panel">
          <div className="jn-panel-head">DORA 本体（v3.4）</div>
          <div className="jn-stats">
            <div className="jn-stat"><div className="jn-stat-k">本体类</div><div className="jn-stat-v">463</div></div>
            <div className="jn-stat"><div className="jn-stat-k">关系</div><div className="jn-stat-v">1,872</div></div>
            <div className="jn-stat"><div className="jn-stat-k">实例化项目</div><div className="jn-stat-v">8</div></div>
            <div className="jn-stat"><div className="jn-stat-k">最后同步</div><div className="jn-stat-v">13:54</div></div>
          </div>
        </div>
      </div>
    </>
  );
}

function AuditView() {
  return (
    <div className="jn-panel" style={{ padding: 0 }}>
      <div className="jn-panel-head" style={{ padding: '12px 14px' }}>
        审计日志（最近 {AUDIT_LOG.length} 条 · 按时间倒序）
      </div>
      <table className="vs-table">
        <thead>
          <tr><th>时间</th><th>操作者</th><th>动作</th><th>目标</th></tr>
        </thead>
        <tbody>
          {AUDIT_LOG.map((l, i) => (
            <tr key={i}>
              <td className="num" style={{ fontFamily: 'var(--font-mono)' }}>{l.ts}</td>
              <td><strong>{l.who}</strong></td>
              <td>{l.act}</td>
              <td style={{ color: 'var(--c-text-muted)' }}>{l.target}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AdminScreen() {
  const [tab, setTab] = useState('integration');
  useEffect(() => {
    const v = readUrlParam('tab');
    if (v && TABS.some((t) => t.key === v)) setTab(v);
  }, []);
  return (
    <div className="jn-wrap" style={{ flex: 1, overflow: 'auto' }}>
      <div className="main-inner">
        <div className="page-head">
          <div>
            <h1>系统级配置</h1>
            <div className="sub">仅平台管理员可见 · 上游接入 / 角色 / 数据隐私 / AI 路由 / 审计</div>
          </div>
          <div className="right">
            <span>当前用户</span>
            <span className="text-mono" style={{ color: '#1b84ff' }}>何博 · 平台管理员</span>
          </div>
        </div>

        <div className="callout info" style={{ marginBottom: 14 }}>
          <span style={{ fontWeight: 700 }}>快速开始 · </span>
          系统级配置只承担"接通 + 治理"两件事。所有项目内规则（人货站、风险、变更）走 /plan，所有合规规则走 OCC + 数据隐私。
        </div>

        <div className="snap-tabs">
          {TABS.map((t) => (
            <button key={t.key} className={`snap-tab${tab === t.key ? ' active' : ''}`} onClick={() => setTab(t.key)}>
              <span>{t.label}</span>
              <span className="v-label">· {t.sub}</span>
            </button>
          ))}
        </div>

        {tab === 'integration' && <IntegrationView />}
        {tab === 'roles'       && <RolesView />}
        {tab === 'privacy'     && <PrivacyView />}
        {tab === 'ai'          && <AIView />}
        {tab === 'skills'      && <SkillsView />}
        {tab === 'audit'       && <AuditView />}
      </div>
    </div>
  );
}

/* ─────────────────────────  5.28 H-7 · Sub-Skills 管理（H1-H5）
 *   - H1：Sub-Skills 架构（这里以表 + 关系图呈现）
 *   - H2：新增功能 = 新 Sub-Skill（OS 镜像 / 入参 / 兼容设备 / 调用 API）
 *   - H3：管理界面（专业用户增删改查）
 *   - H4：评审 / 发布到「公共池」
 *   - H5：三层架构图（作业工序 → 执行机 → 工具）
 * ─────────────────────────  */

const SKILL_LANES = [
  { stage: '工勘',   id: 'SK-001', name: 'CAD-Parser',       impl: 'python:3.11 + drawingjs',       params: 'file: dwg/dxf', api: 'POST /v1/cad/parse',   status: 'published', maintainer: '何博' },
  { stage: '工勘',   id: 'SK-002', name: 'Survey-VLM',        impl: 'gpu:Llama3-Vision-70B',        params: 'video: mp4',    api: 'POST /v1/survey/vlm',  status: 'reviewing',  maintainer: '李泽' },
  { stage: '设计',   id: 'SK-010', name: 'HLD-LLD-Drafter',   impl: 'cpu:Qwen2-VL-7B',              params: 'spec: json',    api: 'POST /v1/design/draft',status: 'published', maintainer: '周倩' },
  { stage: '设计',   id: 'SK-011', name: 'BOQ-Solver',        impl: 'cpu:wasm-mip-solver',          params: 'sku-list: csv', api: 'POST /v1/boq/solve',   status: 'published', maintainer: '韦楠' },
  { stage: '安装',   id: 'SK-020', name: 'One-Click-Rack',    impl: 'k8s:python-orchestrator',      params: 'pod: id',       api: 'POST /v1/rack/cast',   status: 'published', maintainer: '李泽' },
  { stage: '调测',   id: 'SK-030', name: 'ZTP-Pusher',        impl: 'k8s:ansible-runner',           params: 'fleet: id[]',   api: 'POST /v1/ztp/push',    status: 'published', maintainer: '陈睿' },
  { stage: '调测',   id: 'SK-031', name: 'DOA-Classifier',    impl: 'cpu:LightGBM v3.7',            params: 'sn: str',       api: 'POST /v1/doa/classify',status: 'draft',     maintainer: '张航' },
  { stage: '验收',   id: 'SK-040', name: 'IGD-ICD-Checker',   impl: 'cpu:rule-engine',              params: 'report: pdf',   api: 'POST /v1/accept/check',status: 'published', maintainer: '何萍' },
];

const SKILL_STATE_TONE = {
  published: { tone: 'green', label: '公共池' },
  reviewing: { tone: 'blue',  label: '评审中' },
  draft:     { tone: 'gray',  label: '草稿'   },
};

function SkillsView() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <ThreeLayerArchCard />
      <SkillsLanesTable />
      <SkillReviewFlow />
      <NewSkillForm />
    </div>
  );
}

/* H5 · 三层架构图 */
function ThreeLayerArchCard() {
  return (
    <section className="jn-panel">
      <div className="jn-panel-head">
        三层架构 · 作业工序 → 执行机 → 工具
        <span className="jn-panel-meta">数据流自上而下 · 反馈自下而上</span>
      </div>
      <div className="three-layer-arch">
        <div className="arch-layer layer-process">
          <div className="arch-layer-tag">作业工序 (Process)</div>
          <div className="arch-layer-body">
            <span className="arch-chip">工勘</span>
            <span className="arch-chip">设计</span>
            <span className="arch-chip">安装</span>
            <span className="arch-chip">调测</span>
            <span className="arch-chip">验收</span>
          </div>
          <div className="arch-layer-sub">PD / TL · 业务语义</div>
        </div>
        <div className="arch-down">↓ 编排</div>
        <div className="arch-layer layer-runtime">
          <div className="arch-layer-tag">执行机 (Runtime)</div>
          <div className="arch-layer-body">
            <span className="arch-chip">Agent · Survey</span>
            <span className="arch-chip">Agent · Design</span>
            <span className="arch-chip">Agent · Install</span>
            <span className="arch-chip">Agent · ZTP</span>
            <span className="arch-chip">Agent · Acceptance</span>
          </div>
          <div className="arch-layer-sub">AIDA 子代理 · 任务编排 + 异常路由</div>
        </div>
        <div className="arch-down">↓ 调用</div>
        <div className="arch-layer layer-tools">
          <div className="arch-layer-tag">工具 (Tools / Sub-Skills)</div>
          <div className="arch-layer-body">
            <span className="arch-chip">CAD-Parser</span>
            <span className="arch-chip">Survey-VLM</span>
            <span className="arch-chip">HLD-Drafter</span>
            <span className="arch-chip">BOQ-Solver</span>
            <span className="arch-chip">One-Click-Rack</span>
            <span className="arch-chip">ZTP-Pusher</span>
            <span className="arch-chip">DOA-Classifier</span>
            <span className="arch-chip">IGD-ICD-Checker</span>
            <span className="arch-chip more">+ 新增 SUB-SKILL</span>
          </div>
          <div className="arch-layer-sub">专业用户 / 开发者 · 注册 → 评审 → 公共池</div>
        </div>
      </div>
    </section>
  );
}

/* H1 / H3 · 已注册 Sub-Skill 表 */
function SkillsLanesTable() {
  return (
    <section className="jn-panel">
      <div className="jn-panel-head">
        已注册 Sub-Skills
        <span className="jn-panel-meta">{SKILL_LANES.length} 个 · 按作业工序分组</span>
      </div>
      <table className="vs-table">
        <thead>
          <tr>
            <th>工序</th>
            <th>ID</th>
            <th>Skill</th>
            <th>执行机 / 镜像</th>
            <th>入参</th>
            <th>调用 API</th>
            <th>负责人</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          {SKILL_LANES.map(s => {
            const t = SKILL_STATE_TONE[s.status];
            return (
              <tr key={s.id}>
                <td><span className={`arch-stage-pill stage-${s.stage}`}>{s.stage}</span></td>
                <td className="text-mono">{s.id}</td>
                <td><b>{s.name}</b></td>
                <td className="text-mono">{s.impl}</td>
                <td className="text-mono">{s.params}</td>
                <td className="text-mono">{s.api}</td>
                <td>{s.maintainer}</td>
                <td><span className={`q-state tone-${t.tone}`}>{t.label}</span></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

/* H4 · 评审流 */
function SkillReviewFlow() {
  const flow = [
    { name: '注册',   sub: '专业用户提交', state: 'done' },
    { name: '联调',   sub: 'AIDA 用合成数据回归', state: 'done' },
    { name: '评审',   sub: 'TD + 安全 + AIDA 三方', state: 'doing' },
    { name: '发布',   sub: '上架公共池 · 全员可调用', state: 'pending' },
  ];
  return (
    <section className="jn-panel">
      <div className="jn-panel-head">
        评审 · 发布到公共池
        <span className="jn-panel-meta">从注册到上架的标准流</span>
      </div>
      <div className="skill-flow">
        {flow.map((f, i) => (
          <div key={f.name} className={`skill-flow-step state-${f.state}`}>
            <div className="skill-flow-bullet">{i + 1}</div>
            <div className="skill-flow-text">
              <div className="name">{f.name}</div>
              <div className="sub">{f.sub}</div>
            </div>
            {i < flow.length - 1 && <div className="skill-flow-arrow">→</div>}
          </div>
        ))}
      </div>
    </section>
  );
}

/* H2 · 新增 Sub-Skill 表单 */
function NewSkillForm() {
  return (
    <section className="jn-panel">
      <div className="jn-panel-head">
        新增 Sub-Skill
        <span className="jn-panel-meta">用 OS 镜像 + 入参 + 调用 API 三件套定义</span>
      </div>
      <div className="skill-form">
        <div className="skill-form-row">
          <label>Skill 名称</label>
          <input type="text" defaultValue="" placeholder="如 OSPF-Stress-Tester" />
        </div>
        <div className="skill-form-row">
          <label>所属工序</label>
          <select>
            <option>工勘</option><option>设计</option>
            <option>安装</option><option>调测</option>
            <option>验收</option>
          </select>
        </div>
        <div className="skill-form-row">
          <label>OS 镜像 / 运行时</label>
          <input type="text" defaultValue="" placeholder="如 python:3.11 / gpu:Llama3 / k8s:ansible-runner" />
        </div>
        <div className="skill-form-row">
          <label>入参 (JSON Schema)</label>
          <textarea defaultValue={'{ "fleet": "id[]", "policy": "string" }'} rows={3} />
        </div>
        <div className="skill-form-row">
          <label>调用 API</label>
          <input type="text" defaultValue="POST /v1/" />
        </div>
        <div className="skill-form-row">
          <label>兼容设备</label>
          <input type="text" defaultValue="" placeholder="支持的硬件型号 / 网元" />
        </div>
        <div className="skill-form-actions">
          <button className="btn sm ghost">保存草稿</button>
          <button className="btn sm primary">提交评审 →</button>
        </div>
      </div>
    </section>
  );
}
