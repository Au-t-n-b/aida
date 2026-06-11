// @ts-nocheck
'use client';

/* /sandbox · AI 推演沙箱
 * 入口：cockpit 关键研判卡片的"推演到沙箱" / TopBar FocusHero 的"推演到沙箱"
 * 输入：scenario key（默认 b2-power-delay）
 * 输出：α/β 方案对比 + 一键写回 /plan + 一键导出汇报片
 */

import { useState, useEffect } from 'react';
import Link from '@/compat/link';
import { SANDBOX_SCENARIOS, SANDBOX_DEFAULT_KEY, SANDBOX_INDEX } from '../../data/sandbox-data';
import VersionBar, { bumpVersion } from '../version-bar';
import ActionFooter from '../action-footer';

/* 读 URL 参数 — 不用 useSearchParams 避免静态导出后 Suspense fallback=null 空白 */
function readUrlParam(key) {
  if (typeof window === 'undefined') return null;
  return new URLSearchParams(window.location.search).get(key);
}

/* ── tiny icons ── */
const IcSparkle = () => (
  <svg width={10} height={10} viewBox="0 0 11 11" fill="none">
    <path d="M5.5 0.5 L6.4 4.6 L10.5 5.5 L6.4 6.4 L5.5 10.5 L4.6 6.4 L0.5 5.5 L4.6 4.6 Z" fill="currentColor" />
  </svg>
);
const IcCheck = () => (
  <svg width={12} height={12} viewBox="0 0 12 12" fill="none">
    <path d="M2 6.5 L5 9 L10 3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="square" fill="none" />
  </svg>
);
const IcDoc = () => (
  <svg width={11} height={11} viewBox="0 0 12 12" fill="none">
    <path d="M2 1 L8 1 L10 3 L10 11 L2 11 Z M8 1 L8 3 L10 3" stroke="currentColor" strokeWidth="1" fill="none" />
  </svg>
);

/* ── scenario picker ── */
function ScenarioPicker({ currentKey, onPick }) {
  return (
    <div className="sb-picker">
      <span className="sb-picker-label">推演场景</span>
      {SANDBOX_INDEX.map(s => (
        <button
          key={s.key}
          className={`sb-picker-btn sev-${s.sev}${s.key === currentKey ? ' on' : ''}`}
          onClick={() => onPick(s.key)}
        >
          <span className="sb-picker-dot" />
          <span>{s.title}</span>
        </button>
      ))}
    </div>
  );
}

/* 5.27 M-119 · 决策三档徽章
 * 从 plan.hitRate 推导：≥80 自动应用 / ≥60 提议 / 其余 待人工确认
 * 真实产品里 plan.decisionTier 也可显式指定，覆盖默认推导 */
function decisionTierOf(plan) {
  if (plan.decisionTier) return plan.decisionTier;       // 显式优先
  if (plan.hitRate >= 80) return 'auto';
  if (plan.hitRate >= 60) return 'propose';
  return 'human';
}
const TIER_META = {
  auto:    { label: '自动应用', tone: 'green',  desc: 'AIDA 高置信，可直接写回 /plan 触发流程' },
  propose: { label: '提议',     tone: 'amber',  desc: '需 PD/TD 二次确认，确认后写回' },
  human:   { label: '待人工确认', tone: 'red',  desc: '置信度不足，需人工细看再决策' },
};
function TierBadge({ tier }) {
  const meta = TIER_META[tier];
  if (!meta) return null;
  return (
    <span className={`sb-plan-tier tone-${meta.tone}`} title={meta.desc}>
      <span className="sb-plan-tier-dot" />
      {meta.label}
    </span>
  );
}

/* ── 一个方案卡片 ── */
function PlanCard({ plan, isChosen, onChoose }) {
  const tier = decisionTierOf(plan);
  return (
    <div className={`sb-plan ${plan.recommended ? 'recommended' : ''} ${isChosen ? 'chosen' : ''}`}>
      <div className="sb-plan-head">
        <div className="sb-plan-tag">{plan.label}</div>
        <TierBadge tier={tier} />
        <div className="sb-plan-hit">
          命中率 <span className="sb-plan-hit-v">{plan.hitRate}%</span>
        </div>
        {plan.recommended && <span className="sb-plan-rec">AIDA 推荐</span>}
      </div>

      <div className="sb-plan-summary">{plan.summary}</div>

      <div className="sb-plan-grid">
        <div className="sb-plan-kv">
          <span className="k">增量成本</span>
          <span className="v text-mono">{plan.deltaCost}</span>
        </div>
        <div className="sb-plan-kv">
          <span className="k">工期影响</span>
          <span className="v">{plan.deltaTime}</span>
        </div>
        <div className="sb-plan-kv">
          <span className="k">风险态势</span>
          <span className={`v sb-plan-risk ${plan.riskAfter.includes('green') ? 'green' : plan.riskAfter.includes('red') ? 'red' : 'amber'}`}>
            {plan.riskAfter}
          </span>
        </div>
      </div>

      {/* 行动列表 · 人/货/站 三色 */}
      <div className="sb-plan-section">关键动作</div>
      <div className="sb-plan-moves">
        {plan.moves.map((m, i) => (
          <div key={i} className={`sb-move tone-${m.tone}`}>
            <span className="sb-move-stream">{m.stream}</span>
            <span className="sb-move-text">{m.text}</span>
          </div>
        ))}
      </div>

      {/* 甘特 diff（如果有） */}
      {plan.ganttDiff?.length > 0 && (
        <>
          <div className="sb-plan-section">甘特 diff（相对基线）</div>
          <div className="sb-mini-gantt">
            {plan.ganttDiff.map(r => {
              const total = 36;
              const left = (r.start / total) * 100;
              const w = (r.dur / total) * 100;
              return (
                <div key={r.id} className="sb-mini-gantt-row">
                  <span className="sb-mini-gantt-name">{r.name}</span>
                  <div className="sb-mini-gantt-track">
                    <div className={`sb-mini-gantt-bar s-${r.status}`} style={{ left: `${left}%`, width: `${w}%` }}>
                      <span>{r.dur}d</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* 推理依据 */}
      <div className="sb-plan-section">推理依据</div>
      <div className="sb-plan-confidence">
        {plan.confidence.map((c, i) => (
          <div key={i} className="sb-confidence-row">
            <span className="k">{c.k}</span>
            <span className="v">{c.v}</span>
          </div>
        ))}
      </div>

      {/* 残余风险 */}
      <div className="sb-plan-section">残余风险</div>
      <div className="sb-plan-risks">
        {plan.risks.map((r, i) => (
          <div key={i} className={`sb-risk-row lvl-${r.lvl}`}>
            <span className="sb-risk-lvl">{r.lvl === 'high' ? '高' : r.lvl === 'med' ? '中' : '低'}</span>
            <span className="sb-risk-text">{r.text}</span>
          </div>
        ))}
      </div>

      <div className="sb-plan-foot">
        {isChosen ? (
          <div className="sb-plan-chosen-tag"><IcCheck /> 已选择</div>
        ) : (
          <button className={`btn sm ${plan.recommended ? 'primary' : 'ghost'}`} onClick={() => onChoose(plan.key)}>
            选择此方案 →
          </button>
        )}
      </div>
    </div>
  );
}

/* ── 主屏 ── */
export default function SandboxScreen() {
  /* 初始用默认 key，hydration 后再从 URL 同步 — 保证 SSG HTML 有完整内容 */
  const [scenarioKey, setScenarioKey] = useState(SANDBOX_DEFAULT_KEY);
  const [chosen, setChosen] = useState(null);
  const [writebackToast, setWriteback] = useState(null);
  /* 5.27 M-116 · 沙箱推演结果版本回看 */
  const [versions, setVersions] = useState(['v0.1', 'v0.2']);
  const [currentVersion, setCurrentVersion] = useState('v0.2');
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    const v = readUrlParam('scenario');
    if (v && SANDBOX_SCENARIOS[v]) {
      setScenarioKey(v);
      setChosen(null);
    }
  }, []);

  const scenario = SANDBOX_SCENARIOS[scenarioKey];
  if (!scenario) return null;

  const handleChoose = (planKey) => setChosen(planKey);
  const handleWriteback = () => {
    if (!chosen) return;
    setWriteback(`方案 ${chosen.toUpperCase()} 已写回 /plan?view=plan`);
    setTimeout(() => setWriteback(null), 3500);
    /* 真实产品里会调 mutation 写回 plan，并改 risk 状态 */
  };
  const handleExport = () => {
    setWriteback(`已生成汇报片：方案对比_${scenario.key}.pptx`);
    setTimeout(() => setWriteback(null), 3500);
  };

  return (
    <div className="jn-wrap" style={{ flex: 1, overflow: 'auto' }}>
      <div className="main-inner">
        {/* page head */}
        <div className="page-head">
          <div>
            <h1>AI 推演沙箱 · K1903</h1>
            <div className="sub">α / β 方案对比 · 一键写回计划 · 一键导出汇报片</div>
          </div>
          <div className="right">
            <span>沙箱节点</span>
            <span className="text-mono" style={{ color: '#1b84ff' }}>Composer-2.5-fast</span>
            <span style={{ width: 1, height: 14, background: 'var(--c-border)', margin: '0 6px' }} />
            <span>耗时</span>
            <span className="text-mono" style={{ color: 'var(--c-text)' }}>4.1s</span>
          </div>
        </div>

        <VersionBar
          versions={versions}
          currentVersion={currentVersion}
          onSelectVersion={(v) => { setCurrentVersion(v); setDirty(false); setChosen(null); }}
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
          confirmLabel="固化为新一轮推演 · +0.1"
        />

        {/* AI 输入：场景描述 */}
        <div className="jn-ai" style={{ marginBottom: 14 }}>
          <div className="jn-ai-tag"><IcSparkle /> AIDA</div>
          <div className="jn-ai-text">
            <strong>{scenario.title}</strong>
            <span style={{ display: 'block', marginTop: 4, color: 'var(--c-text-muted)' }}>
              影响链路：{scenario.impactRoute} · 基线影响：{scenario.baselineDelay}
            </span>
          </div>
        </div>

        {/* 场景选择 */}
        <ScenarioPicker currentKey={scenarioKey} onPick={(k) => {
          setScenarioKey(k); setChosen(null);
          /* 用 history.replaceState 直接更新 URL — 静态导出后 Next.js 的 router.replace 失效。
           * 只更新 URL，不导航；scenario 状态已由本地 setScenarioKey 同步。 */
          if (typeof window !== 'undefined') {
            window.history.replaceState({}, '', `?scenario=${k}`);
          }
        }} />

        {/* 约束条件展示 */}
        <div className="sb-constraints">
          <div className="sb-constraints-head">已知约束（AIDA 推理输入）</div>
          <ul>
            {scenario.constraints.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
          <div className="sb-constraints-meta">
            <span>来源：{scenario.sourceInsight} · {scenario.sourceRisk}</span>
            <span>SLA：{scenario.sla}</span>
            <span>客户感知：{scenario.customerNotice}</span>
          </div>
        </div>

        {/* 双方案对比 */}
        <div className="sb-plan-row">
          {scenario.plans.map(p => (
            <PlanCard key={p.key} plan={p} isChosen={chosen === p.key} onChoose={handleChoose} />
          ))}
        </div>

        {/* 历史记录 */}
        {scenario.history?.length > 0 && (
          <div className="sb-history">
            <div className="sb-history-head">历史推演记录</div>
            <table className="vs-table">
              <thead><tr><th>时间</th><th>触发人</th><th>选定方案</th><th>动作</th></tr></thead>
              <tbody>
                {scenario.history.map((h, i) => (
                  <tr key={i}>
                    <td className="num" style={{ fontFamily: 'var(--font-mono)' }}>{h.ts}</td>
                    <td>{h.who}</td>
                    <td><span className="status-pill">方案 {h.plan}</span></td>
                    <td>{h.action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* 底部操作栏 */}
        <div className="sb-action-bar">
          <Link href="/cockpit" className="btn sm ghost">← 返回驾驶舱</Link>
          <div className="sb-action-spacer" />
          {chosen && (
            <div className="sb-action-status">已选定方案 {chosen.toUpperCase()}</div>
          )}
          <button className="btn sm ghost" onClick={handleExport} disabled={!chosen}>
            <IcDoc /> 导出汇报片
          </button>
          <button className="btn sm primary" onClick={handleWriteback} disabled={!chosen}>
            写回计划 → /plan
          </button>
        </div>

        {/* toast */}
        {writebackToast && (
          <div className="sb-toast">{writebackToast}</div>
        )}
      </div>

      <ActionFooter
        dirty={dirty}
        onSaveDraft={() => setDirty(false)}
        onConfirm={() => {
          const next = bumpVersion(currentVersion);
          setVersions(vs => [...vs, next]);
          setCurrentVersion(next);
          setDirty(false);
        }}
        confirmLabel="固化推演 · 版本 +0.1"
        readonly={currentVersion !== versions[versions.length - 1]}
      />
    </div>
  );
}
