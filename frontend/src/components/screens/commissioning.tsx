'use client';

import { useState } from 'react';
import Link from '@/compat/link';

/* ─────────────────────────────────────────────
 * 5.28 H-6 · 调测中心（G1-G7 一次落地）
 * G1: 砍 Skill 视图
 * G2: 砍 Sequence 视图
 * G3: 砍"批次"概念
 * G4: 横向 5 步 + 可点击跳转
 * G5: 每步下挂双栏（执行结果 / 测试报告）
 * G6: 允许非严格顺序跳转
 * G7: 步下挂文档 + 顶部"整柜归档"按钮
 * ───────────────────────────────────────────── */

const STEPS = [
  {
    key: 'prep',
    name: '工程准备',
    sub: '上电前的物理校验',
    state: 'done',     // done | doing | risk | pending
    result: {
      summary: '校验 384 节点，0 项异常',
      bullets: ['冷池末端隔板已加固', 'PDU 三相平衡通过', '机柜接地阻抗 < 0.4Ω'],
      ts: '2026-06-08 14:22',
    },
    report: {
      title: '工程准备报告 #2026-PREP-K1903',
      pages: 12, signedBy: '何萍 · 客户工程',
    },
    docs: [
      { name: '机房三色图.dwg',   size: 1240, mime: 'dwg' },
      { name: '物理校验记录.xlsx', size:  68,  mime: 'xlsx' },
    ],
  },
  {
    key: 'deploy',
    name: '设备部署',
    sub: '一拍机 / 整柜入位',
    state: 'done',
    result: {
      summary: '36 机柜全部入位，光路通断率 100%',
      bullets: ['整柜运抵 36/36', '吊装预演无碰撞', '光纤连接通断 9 072/9 072'],
      ts: '2026-06-15 09:05',
    },
    report: {
      title: '设备部署完工报告 #2026-DPL-K1903',
      pages: 28, signedBy: '李泽 · 项目监理',
    },
    docs: [
      { name: '一拍机执行日志.json',     size:  84,  mime: 'json' },
      { name: '设备入位摆位图.pdf',      size: 312,  mime: 'pdf' },
      { name: '光纤通断扫描结果.csv',     size: 196,  mime: 'csv' },
    ],
  },
  {
    key: 'powerup',
    name: '上电',
    sub: '分级带电 · 风冷启动',
    state: 'doing',
    result: {
      summary: '已完成 22/36 机柜上电（61%）',
      bullets: ['一级带电 36/36', '二级带电 22/36', '在线监控 KPI 全绿'],
      ts: '今天 14:32',
    },
    report: {
      title: '上电过程报告 · 实时',
      pages: '—', signedBy: '执行中',
    },
    docs: [
      { name: '上电节奏表.xlsx',   size: 42, mime: 'xlsx' },
      { name: '在线 KPI 快照.png', size: 88, mime: 'png' },
    ],
  },
  {
    key: 'ztp',
    name: 'ZTP 升级',
    sub: '零接触配置下发',
    state: 'pending',
    result: {
      summary: '未开始 · 待"上电"完成 ≥ 80% 自动唤起',
      bullets: ['脚本基线 v3.2 已归档', '回滚预案已就绪'],
      ts: '—',
    },
    report: { title: '—', pages: '—', signedBy: '—' },
    docs: [
      { name: 'ZTP 模板包 v3.2.zip', size: 380, mime: 'zip' },
      { name: '回滚预案.md',          size:  18, mime: 'md' },
    ],
  },
  {
    key: 'accept',
    name: '安装与验收',
    sub: 'DOA / IGD / ICD 综合',
    state: 'pending',
    result: {
      summary: '未开始 · 待 ZTP 升级完成',
      bullets: ['DOA 模板已生成', 'IGD/ICD 检查项已锁'],
      ts: '—',
    },
    report: { title: '—', pages: '—', signedBy: '—' },
    docs: [
      { name: '验收清单.xlsx', size: 56, mime: 'xlsx' },
    ],
  },
];

type StateKey = 'done' | 'doing' | 'risk' | 'pending';
const STATE_LABEL: Record<StateKey, { label: string; tone: string }> = {
  done:    { label: '已完成', tone: 'green' },
  doing:   { label: '进行中', tone: 'blue'  },
  risk:    { label: '风险',   tone: 'red'   },
  pending: { label: '未开始', tone: 'gray'  },
};

export default function CommissioningScreen() {
  const [active, setActive] = useState(2); // 默认聚焦"上电"

  const step = (STEPS[active] ?? STEPS[0]) as (typeof STEPS)[number];
  const tone = STATE_LABEL[step.state as StateKey];

  return (
    <div style={{ flex: 1, overflow: 'auto' }}>
      <div className="main-inner">
        <div className="page-head">
          <div>
            <div className="bc">
              <Link href="/cockpit" style={{ color: 'var(--c-text-muted)', textDecoration: 'none' }}>项目孪生</Link>
              <span style={{ margin: '0 6px', color: 'var(--c-text-faint)' }}>/</span>
              <span>调测中心</span>
            </div>
            <h1>调测中心 · 智算 K1903</h1>
            <div className="sub">横向 5 步 · 双栏结果 · 可任意点击跳转</div>
          </div>
          <div className="right">
            <span className="text-mono" style={{ color: 'var(--c-text-muted)' }}>批次概念已下线 · 仅按机房 / PoD</span>
            <button className="btn sm primary">📦 整柜文档归档 →</button>
          </div>
        </div>

        {/* —— G4 · 横向 5 步 —— */}
        <div className="commission-stepper">
          {STEPS.map((s, i) => {
            const t = STATE_LABEL[s.state as StateKey];
            return (
              <button
                key={s.key}
                className={`commission-step state-${s.state}${i === active ? ' on' : ''}`}
                onClick={() => setActive(i)}
              >
                <div className="commission-step-bullet">
                  <span className="num">{i + 1}</span>
                </div>
                <div className="commission-step-text">
                  <div className="name">{s.name}</div>
                  <div className="sub">{s.sub}</div>
                </div>
                <div className={`commission-step-tag tone-${t.tone}`}>{t.label}</div>
                {i < STEPS.length - 1 && <div className="commission-step-link" />}
              </button>
            );
          })}
        </div>

        {/* —— G5 · 双栏结果 —— */}
        <div className="commission-dual">
          <section className="commission-dual-card">
            <div className="commission-dual-head">
              <h3>执行结果</h3>
              <span className={`q-state tone-${tone.tone}`}>{tone.label}</span>
              <span className="commission-dual-ts text-mono">{step.result.ts}</span>
            </div>
            <div className="commission-dual-body">
              <div className="commission-summary">{step.result.summary}</div>
              <ul className="commission-bullets">
                {step.result.bullets.map(b => <li key={b}>{b}</li>)}
              </ul>
            </div>
          </section>

          <section className="commission-dual-card">
            <div className="commission-dual-head">
              <h3>测试报告</h3>
              {step.report.title !== '—' && <button className="btn xs">↗ 查看 PDF</button>}
            </div>
            <div className="commission-dual-body">
              <div className="commission-report">
                <div className="commission-report-title">{step.report.title}</div>
                <div className="commission-report-meta">
                  <span>页数</span><b className="text-mono">{step.report.pages}</b>
                  <span style={{ marginLeft: 14 }}>签发</span><b>{step.report.signedBy}</b>
                </div>
              </div>
            </div>
          </section>
        </div>

        {/* —— G7 · 单步文档（继续保留顶部"整柜归档"） —— */}
        <section className="commission-docs">
          <div className="commission-docs-head">
            <h3>本步关联文档 · {step.name}</h3>
            <span className="commission-docs-meta">{step.docs.length} 份 · 自动归并到整柜文档包</span>
          </div>
          <div className="commission-docs-grid">
            {step.docs.map(d => (
              <div key={d.name} className={`commission-doc mime-${d.mime}`}>
                <div className="commission-doc-icon">.{d.mime}</div>
                <div className="commission-doc-text">
                  <div className="commission-doc-name">{d.name}</div>
                  <div className="commission-doc-size">{d.size} KB</div>
                </div>
                <button className="btn xs ghost">查看</button>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
