// @ts-nocheck
'use client';

import { useState } from 'react';
import { IconSearch, IconSettings, IconUser, IconBolt, IconShield, IconBox, IconCpu, IconPlus } from '../icons';
import { Badge, Button, Panel, Progress } from '../primitives';

/* ── AssetsScreen ── */
const ASSET_TABS = ['组织资产', '个人资产'];
const ASSET_ROWS = [
  { name: '华南区 DC 工勘报告 v2.pdf', type: 'PDF', size: '2.4 MB', project: '华南区 DC 扩容', updated: '2025-06-12', status: '已审核' },
  { name: 'BOQ清单_最终版.xlsx', type: 'XLS', size: '864 KB', project: '华南区 DC 扩容', updated: '2025-06-10', status: '已审核' },
  { name: '网络拓扑图 v3.pdf', type: 'PDF', size: '1.8 MB', project: '华南区 DC 扩容', updated: '2025-06-08', status: '草稿' },
  { name: 'WBS结构表.xlsx', type: 'XLS', size: '420 KB', project: '华南区 DC 扩容', updated: '2025-06-05', status: '待审核' },
  { name: '设备台账.xlsx', type: 'XLS', size: '1.1 MB', project: '西北骨干网', updated: '2025-05-28', status: '已审核' },
  { name: '割接方案_v1.docx', type: 'DOC', size: '640 KB', project: '西北骨干网', updated: '2025-05-22', status: '已审核' },
];
const STATUS_TONE = { '已审核': 'green', '草稿': 'default', '待审核': 'amber' };

/* G-17 · 已抽取的产品手册（mock）
 * 字段：手册名 · 关联设备型号 · 抽取项 · 抽取状态 · 同步去向 */
const MANUAL_EXTRACTS = [
  {
    name: 'Atlas 900 A3 SuperPoD · 产品手册.pdf',
    model: 'A990-33-HEZSC1A0L01',
    extracted: 'EOS · 功耗 · 散热 · 兼容矩阵',
    state: '已抽取',
    syncTo: 'BOQ 解析 · 设计页',
    extractedAt: '2026-05-26 10:14',
  },
  {
    name: '灵衡 1.0 总线柜 · 工程指导.pdf',
    model: 'LGL_Rack2 · LGE5DV1',
    extracted: '机柜尺寸 · 配电 · 桥架',
    state: '已抽取',
    syncTo: '机房 / 机柜 · 设计页',
    extractedAt: '2026-05-26 11:32',
  },
  {
    name: 'CloudEngine S6720 · 配置手册.pdf',
    model: 'S6720-30L-LI-AC',
    extracted: 'AI 抽取中（17/24 章）',
    state: '抽取中',
    syncTo: '组网 · 服务器配套表',
    extractedAt: '—',
  },
];
const MANUAL_STATE_TONE = { '已抽取': 'green', '抽取中': 'amber', '失败': 'red' };

function ManualExtractCard() {
  return (
    <Panel padding="0" style={{ marginBottom: 16, border: '1px solid var(--accent-muted)' }}>
      <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)', background: 'var(--accent-bg, rgba(27,132,255,.04))', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ width: 22, height: 22, display: 'inline-grid', placeItems: 'center', background: 'var(--accent)', color: '#fff', borderRadius: 4, fontSize: 11, fontWeight: 800 }}>AI</span>
          <strong style={{ fontSize: 13 }}>产品手册抽取</strong>
          <span style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>
            上传产品手册 → AI 抽取 EOS / 规格 / 兼容矩阵 → 同步到 BOQ 解析与设计页
          </span>
        </div>
        <Button variant="ghost" size="sm">查看抽取规则</Button>
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--text-xs)' }}>
        <thead>
          <tr style={{ background: 'var(--zinc-50)' }}>
            {['手册名', '关联设备型号', '已抽取项', '状态', '同步去向', '抽取时间', '操作'].map(h => (
              <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 600, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {MANUAL_EXTRACTS.map((m, i) => (
            <tr key={i} style={{ borderBottom: '1px solid var(--zinc-100)' }}>
              <td style={{ padding: '8px 12px', fontWeight: 500 }}>{m.name}</td>
              <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{m.model}</td>
              <td style={{ padding: '8px 12px', color: 'var(--text-secondary)' }}>{m.extracted}</td>
              <td style={{ padding: '8px 12px' }}>
                <Badge tone={MANUAL_STATE_TONE[m.state] || 'default'} size="xs">{m.state}</Badge>
              </td>
              <td style={{ padding: '8px 12px', color: 'var(--text-tertiary)' }}>{m.syncTo}</td>
              <td style={{ padding: '8px 12px', fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>{m.extractedAt}</td>
              <td style={{ padding: '8px 12px' }}>
                <div style={{ display: 'flex', gap: 4 }}>
                  <Button variant="ghost" size="sm" style={{ height: 24, padding: '0 6px', fontSize: 10 }}>预览抽取</Button>
                  <Button variant="ghost" size="sm" style={{ height: 24, padding: '0 6px', fontSize: 10 }}>同步到 BOQ</Button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

export function AssetsScreen() {
  const [tab, setTab] = useState(0);
  const [search, setSearch] = useState('');

  const filtered = ASSET_ROWS.filter(r => r.name.toLowerCase().includes(search.toLowerCase()) || r.project.toLowerCase().includes(search.toLowerCase()));

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 'var(--pad-panel)' }} className="claw-scroll">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <h1 style={{ fontSize: 'var(--text-xl)', fontWeight: 800 }}>资产中心</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          {/* G-17 · 产品手册抽取入口（5.27 会议）
           * 让 PD/TD/SE 上传产品手册（PDF/DOC），AI 抽取 EOS/规格/兼容性矩阵 → 同步到 BOQ 解析与设计页 */}
          <Button variant="ghost" size="sm" icon={<IconBolt size={12} />}>↑ 上传产品手册（AI 抽取 EOS / 规格 / 兼容性）</Button>
          <Button variant="primary" size="sm" icon={<IconPlus size={12} />}>上传资产</Button>
        </div>
      </div>

      {/* G-17 · 产品手册抽取面板（紧贴标题下方） */}
      <ManualExtractCard />

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', marginBottom: 16, gap: 0 }}>
        {ASSET_TABS.map((t, i) => (
          <button
            key={i}
            onClick={() => setTab(i)}
            style={{
              padding: '8px 16px', fontSize: 'var(--text-sm)', fontWeight: 500,
              color: tab === i ? 'var(--accent)' : 'var(--text-secondary)',
              background: 'none',
              borderTop: 'none', borderLeft: 'none', borderRight: 'none',
              borderBottom: tab === i ? '2px solid var(--accent)' : '2px solid transparent',
              cursor: 'pointer',
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Search */}
      <div style={{ position: 'relative', marginBottom: 12 }}>
        <IconSearch size={14} color="var(--text-tertiary)" style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)' }} />
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="搜索文件名或项目…"
          style={{
            width: '100%', height: 36, padding: '0 10px 0 32px',
            border: '1px solid var(--border)', borderRadius: 'var(--radius-md)',
            fontSize: 'var(--text-sm)', background: 'var(--surface)', outline: 'none',
          }}
        />
      </div>

      {/* Table */}
      <Panel padding="0">
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--text-xs)' }}>
          <thead>
            <tr style={{ background: 'var(--zinc-50)' }}>
              {['文件名', '类型', '大小', '所属项目', '更新时间', '状态', '操作'].map(h => (
                <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 600, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((row, i) => (
              <tr key={i} style={{ borderBottom: '1px solid var(--zinc-100)', transition: 'background .1s' }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--zinc-50)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                <td style={{ padding: '8px 12px', fontWeight: 500, color: 'var(--text-primary)' }}>{row.name}</td>
                <td style={{ padding: '8px 12px' }}><Badge tone="default" size="xs">{row.type}</Badge></td>
                <td style={{ padding: '8px 12px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{row.size}</td>
                <td style={{ padding: '8px 12px', color: 'var(--text-secondary)' }}>{row.project}</td>
                <td style={{ padding: '8px 12px', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>{row.updated}</td>
                <td style={{ padding: '8px 12px' }}><Badge tone={STATUS_TONE[row.status] || 'default'} size="xs">{row.status}</Badge></td>
                <td style={{ padding: '8px 12px' }}>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <Button variant="ghost" size="sm" style={{ height: 24, padding: '0 6px', fontSize: '10px' }}>预览</Button>
                    <Button variant="ghost" size="sm" style={{ height: 24, padding: '0 6px', fontSize: '10px' }}>下载</Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 'var(--text-sm)' }}>暂无匹配资产</div>
        )}
      </Panel>
    </div>
  );
}

/* ── ConfigScreen ── */
const CONFIG_NAV = [
  { key: 'model', label: '模型配置', icon: IconCpu },
  { key: 'agents', label: 'Agent 配置', icon: IconBolt },
  { key: 'network', label: '网络代理', icon: IconSettings },
  { key: 'tools', label: '工具集成', icon: IconBox },
  { key: 'creds', label: '凭证管理', icon: IconShield },
];

const AGENT_PROFILES = [
  { name: '工勘分析 Agent', model: 'claude-opus-4-7', status: 'active', tasks: 247 },
  { name: '建模仿真 Agent', model: 'claude-sonnet-4-6', status: 'active', tasks: 183 },
  { name: '作业管理 Agent', model: 'claude-sonnet-4-6', status: 'active', tasks: 129 },
  { name: '文档生成 Agent', model: 'claude-haiku-4-5', status: 'idle', tasks: 412 },
];

export function ConfigScreen() {
  const [activeNav, setActiveNav] = useState('model');
  const [model, setModel] = useState('claude-opus-4-7');

  return (
    <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
      {/* Sidebar */}
      <aside style={{ width: 200, borderRight: '1px solid var(--border)', padding: 'var(--pad-panel)', background: 'var(--surface)', flexShrink: 0 }}>
        <h2 style={{ fontSize: 'var(--text-sm)', fontWeight: 700, marginBottom: 12 }}>配置中心</h2>
        <nav style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {CONFIG_NAV.map(item => {
            const Icon = item.icon;
            const active = activeNav === item.key;
            return (
              <button
                key={item.key}
                onClick={() => setActiveNav(item.key)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8, padding: '7px 10px',
                  borderRadius: 'var(--radius-md)', textAlign: 'left', width: '100%',
                  background: active ? 'var(--accent-muted)' : 'transparent',
                  color: active ? 'var(--accent)' : 'var(--text-secondary)',
                  fontSize: 'var(--text-sm)', fontWeight: active ? 600 : 400,
                  border: `1px solid ${active ? 'rgba(202,138,4,.2)' : 'transparent'}`,
                  cursor: 'pointer', transition: 'all .12s',
                }}
              >
                <Icon size={14} color={active ? 'var(--accent)' : 'var(--text-tertiary)'} />
                {item.label}
              </button>
            );
          })}
        </nav>
      </aside>

      {/* Main content */}
      <div style={{ flex: 1, overflow: 'auto', padding: 'var(--pad-panel)' }} className="claw-scroll">
        {activeNav === 'model' && (
          <div style={{ maxWidth: 600 }}>
            <h3 style={{ fontSize: 'var(--text-base)', fontWeight: 700, marginBottom: 16 }}>默认模型配置</h3>
            <Panel style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {[
                  { label: '主模型', value: model, options: ['claude-opus-4-7', 'claude-sonnet-4-6', 'claude-haiku-4-5'] },
                  { label: 'API 端点', value: 'https://api.anthropic.com/v1' },
                  { label: '最大 Token', value: '8192' },
                  { label: '温度', value: '0.7' },
                ].map((field, i) => (
                  <div key={i}>
                    <label style={{ display: 'block', fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4 }}>{field.label}</label>
                    {field.options ? (
                      <select
                        value={field.value}
                        onChange={e => setModel(e.target.value)}
                        style={{ height: 34, padding: '0 10px', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', fontSize: 'var(--text-sm)', width: '100%', background: 'var(--surface)', outline: 'none' }}
                      >
                        {field.options.map(o => <option key={o} value={o}>{o}</option>)}
                      </select>
                    ) : (
                      <input
                        defaultValue={field.value}
                        style={{ height: 34, padding: '0 10px', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', fontSize: 'var(--text-sm)', width: '100%', background: 'var(--surface)', outline: 'none' }}
                      />
                    )}
                  </div>
                ))}
              </div>
            </Panel>
            <Button variant="primary" size="sm">保存配置</Button>
          </div>
        )}

        {activeNav === 'agents' && (
          <div>
            <h3 style={{ fontSize: 'var(--text-base)', fontWeight: 700, marginBottom: 16 }}>Agent 配置</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {AGENT_PROFILES.map((agent, i) => (
                <Panel key={i}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 'var(--text-sm)', marginBottom: 3 }}>{agent.name}</div>
                      <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{agent.model}</div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>{agent.tasks} 次调用</span>
                      <Badge tone={agent.status === 'active' ? 'green' : 'default'} size="xs" dot>
                        {agent.status === 'active' ? '运行中' : '空闲'}
                      </Badge>
                      <Button variant="ghost" size="sm">编辑</Button>
                    </div>
                  </div>
                </Panel>
              ))}
            </div>
          </div>
        )}

        {activeNav !== 'model' && activeNav !== 'agents' && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', flexDirection: 'column', gap: 8, color: 'var(--text-tertiary)' }}>
            <span style={{ fontSize: 32 }}>🔧</span>
            <span style={{ fontSize: 'var(--text-sm)' }}>{CONFIG_NAV.find(n => n.key === activeNav)?.label} 配置</span>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── OnboardScreen ── */
const ONBOARD_STEPS = ['模型配置', '工具授权', '完成'];

export function OnboardScreen() {
  const [step, setStep] = useState(0);
  const [model, setModel] = useState('claude-opus-4-7');

  return (
    <div style={{ minHeight: '100vh', background: 'var(--zinc-50)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
      <div style={{ width: '100%', maxWidth: 520 }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 800, marginBottom: 6 }}>初始化配置</h1>
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>完成以下步骤开始使用 AIDA</p>
        </div>

        {/* Progress */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 32 }}>
          {ONBOARD_STEPS.map((s, i) => (
            <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
              <Progress value={i < step ? 100 : i === step ? 50 : 0} status={i < step ? 'done' : i === step ? 'running' : 'default'} height={4} />
              <span style={{ fontSize: '10px', color: i <= step ? 'var(--text-primary)' : 'var(--text-tertiary)', fontWeight: i === step ? 600 : 400, textAlign: 'center' }}>{s}</span>
            </div>
          ))}
        </div>

        {/* Step content */}
        <Panel style={{ marginBottom: 20 }}>
          {step === 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, marginBottom: 2 }}>选择默认 AI 模型</div>
              {['claude-opus-4-7', 'claude-sonnet-4-6', 'claude-haiku-4-5'].map(m => (
                <button
                  key={m}
                  onClick={() => setModel(m)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px',
                    borderRadius: 'var(--radius-md)', textAlign: 'left', width: '100%',
                    background: model === m ? 'var(--accent-muted)' : 'var(--zinc-50)',
                    border: `1px solid ${model === m ? 'var(--accent)' : 'var(--border)'}`,
                    cursor: 'pointer', transition: 'all .12s',
                  }}
                >
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: model === m ? 'var(--accent)' : 'var(--zinc-300)' }} />
                  <div>
                    <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, fontFamily: 'var(--font-mono)', color: model === m ? 'var(--accent)' : 'var(--text-primary)' }}>{m}</div>
                    <div style={{ fontSize: '10px', color: 'var(--text-tertiary)' }}>
                      {m.includes('opus') ? '最强推理，适合复杂分析' : m.includes('sonnet') ? '平衡性能，推荐日常使用' : '快速响应，适合简单任务'}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
          {step === 1 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, marginBottom: 2 }}>授权工具集成</div>
              {[{ name: '文件解析工具', desc: 'Excel / PDF / Word 解析', required: true }, { name: '网络拓扑工具', desc: '图论建模与可视化', required: true }, { name: '外部 API 集成', desc: 'ITSM / CMDB 对接', required: false }].map((tool, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 10px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--zinc-50)' }}>
                  <div>
                    <div style={{ fontSize: 'var(--text-sm)', fontWeight: 500 }}>{tool.name}</div>
                    <div style={{ fontSize: '10px', color: 'var(--text-tertiary)' }}>{tool.desc}</div>
                  </div>
                  <Badge tone={tool.required ? 'accent' : 'default'} size="xs">{tool.required ? '必需' : '可选'}</Badge>
                </div>
              ))}
            </div>
          )}
          {step === 2 && (
            <div style={{ textAlign: 'center', padding: '24px 16px' }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>🎉</div>
              <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700, marginBottom: 6 }}>配置完成！</div>
              <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
                AIDA 已就绪，6 个交付模块可立即使用。<br />开始您的第一个项目吧。
              </div>
            </div>
          )}
        </Panel>

        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <Button variant="secondary" size="md" disabled={step === 0} onClick={() => setStep(s => Math.max(0, s - 1))}>上一步</Button>
          {step < ONBOARD_STEPS.length - 1
            ? <Button variant="primary" size="md" onClick={() => setStep(s => s + 1)}>下一步</Button>
            : <Button variant="primary" size="md" onClick={() => { window.location.assign('../cockpit/'); }}>开始使用</Button>
          }
        </div>
      </div>
    </div>
  );
}
