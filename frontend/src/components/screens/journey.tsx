// @ts-nocheck
'use client';

import { useState, useEffect, useRef } from 'react';
import Link from '@/compat/link';
import { JOURNEY_STAGES, JOURNEY_LANE_ROLES } from '../../data/journey-data';

/* ── tiny icons ── */
const IcCheck = () => (
  <svg width={11} height={11} viewBox="0 0 12 12" fill="none">
    <path d="M2 6.5 L5 9 L10 3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="square" fill="none" />
  </svg>
);
const IcArrowRight = () => (
  <svg width={14} height={14} viewBox="0 0 18 18" fill="none">
    <path d="M3 9 L14 9 M10 5 L14 9 L10 13" stroke="currentColor" strokeWidth="1.4" strokeLinecap="square" fill="none" />
  </svg>
);
const IcSparkle = () => (
  <svg width={10} height={10} viewBox="0 0 11 11" fill="none">
    <path d="M5.5 0.5 L6.4 4.6 L10.5 5.5 L6.4 6.4 L5.5 10.5 L4.6 6.4 L0.5 5.5 L4.6 4.6 Z" fill="currentColor" />
  </svg>
);
const IcDot = ({ color = 'currentColor' }) => (
  <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: color }} />
);

/* ── Stage stepper across the top ── */
function StageStepper({ current, onPick }) {
  return (
    <div className="jn-stepper">
      {JOURNEY_STAGES.map((st, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <button
            key={st.key}
            type="button"
            onClick={() => onPick(i)}
            className={`jn-step${active ? ' active' : ''}${done ? ' done' : ''}`}
            title={`${st.role} · ${st.name}`}
          >
            <div className="jn-step-dot">
              {done ? <IcCheck /> : <span className="jn-step-ord">{i + 1}</span>}
            </div>
            <div className="jn-step-meta">
              <div className="jn-step-name">{st.name}</div>
              <div className="jn-step-role" style={{ color: JOURNEY_LANE_ROLES[st.role]?.color }}>
                {st.role}
              </div>
            </div>
            {i < JOURNEY_STAGES.length - 1 && <div className="jn-step-line" />}
          </button>
        );
      })}
    </div>
  );
}

/* ── Stage detail body — switches based on stage shape ── */
function StageBody({ stage }) {
  return (
    <>
      {/* AI badge */}
      {stage.aiPrompt && (
        <div className="jn-ai">
          <div className="jn-ai-tag"><IcSparkle /> AIDA</div>
          <div className="jn-ai-text">{stage.aiPrompt}</div>
        </div>
      )}

      {/* Per-stage shapes */}
      {stage.key === 'landing' && <LandingBody stage={stage} />}
      {stage.key === 'create' && <CreateBody stage={stage} />}
      {stage.key === 'approval' && <ApprovalBody stage={stage} />}
      {stage.key === 'ingest' && <IngestBody stage={stage} />}
      {(stage.key === 'dtrb' || stage.key === 'drb') && <SnapshotBody stage={stage} />}
      {stage.key === 'contract' && <ContractBody stage={stage} />}
      {stage.key === 'delivery' && <DeliveryBody stage={stage} />}
      {stage.key === 'completion' && <CompletionBody stage={stage} />}
    </>
  );
}

/* ── 0. landing ── */
function LandingBody({ stage }) {
  return (
    <div className="jn-grid-2">
      <div className="jn-panel">
        <div className="jn-panel-head">我的项目（3）</div>
        <div className="jn-list">
          {[
            { id: 'A1', name: 'A1 智算集群一期', role: 'TD', pace: '62% · 移交 07-15', status: 'amber' },
            { id: 'C3', name: 'C3 算力底座扩容', role: 'TD', pace: '88% · 移交 06-30', status: 'green' },
            { id: 'L7', name: 'L7 通信枢纽（历史）', role: 'TL', pace: '已归档', status: 'idle' },
          ].map(p => (
            <div key={p.id} className="jn-list-row">
              <div className="jn-list-id">{p.id}</div>
              <div className="jn-list-name">{p.name}</div>
              <div className={`jn-list-role role-${p.role}`}>{p.role}</div>
              <div className="jn-list-pace">{p.pace}</div>
              <IcDot color={{ amber: 'var(--c-warning)', green: 'var(--c-success)', idle: 'var(--c-text-muted)' }[p.status]} />
            </div>
          ))}
        </div>
      </div>
      <div className="jn-panel">
        <div className="jn-panel-head">本季概览</div>
        <div className="jn-stats">
          {stage.keyData.map(kd => (
            <div key={kd.k} className="jn-stat">
              <div className="jn-stat-k">{kd.k}</div>
              <div className="jn-stat-v">{kd.v}</div>
            </div>
          ))}
        </div>
        <div className="jn-hint">注：此页无 AI 输入窗，只展示"项目列表 + 创建按钮"。</div>
      </div>
    </div>
  );
}

/* ── 1. create ── */
function CreateBody({ stage }) {
  return (
    <div className="jn-panel">
      <div className="jn-panel-head">新建项目 · 5 项基本字段</div>
      <div className="jn-form">
        {stage.fields.map(f => (
          <div key={f.key} className="jn-form-row">
            <label>{f.label}</label>
            <div className="jn-form-input">
              <span className="jn-form-val">{f.value}</span>
              {f.auto && <span className="jn-form-auto">系统识别</span>}
              {f.hint && <span className="jn-form-hint">{f.hint}</span>}
            </div>
          </div>
        ))}
      </div>
      <div className="jn-hint">注：字段总数不超过 5 项，避免冗长。</div>
    </div>
  );
}

/* ── 2. approval ── */
function ApprovalBody({ stage }) {
  return (
    <div className="jn-grid-2">
      <div className="jn-panel">
        <div className="jn-panel-head">关联数据范围（待 OCC 审批）</div>
        <div className="jn-stats">
          {stage.keyData.map(kd => (
            <div key={kd.k} className="jn-stat">
              <div className="jn-stat-k">{kd.k}</div>
              <div className="jn-stat-v">{kd.v}</div>
            </div>
          ))}
        </div>
      </div>
      <div className="jn-panel">
        <div className="jn-panel-head">审批时间线</div>
        <div className="jn-tl">
          {stage.approvalTimeline.map((it, i) => (
            <div key={i} className={`jn-tl-row state-${it.state}`}>
              <span className="jn-tl-time">{it.t}</span>
              <span className="jn-tl-dot" />
              <span className="jn-tl-who">{it.who}</span>
              <span className="jn-tl-act">{it.act}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── 3. ingest ── */
function IngestBody({ stage }) {
  return (
    <div className="jn-grid-2">
      <div className="jn-panel">
        <div className="jn-panel-head">已上传文档（4）</div>
        <div className="jn-docs">
          {stage.documents.map(d => (
            <div key={d.name} className={`jn-doc state-${d.parsed === true ? 'ok' : d.parsed === 'partial' ? 'partial' : 'gap'}`}>
              <div className="jn-doc-name">{d.name}</div>
              <div className="jn-doc-meta">
                <span>{d.size}</span>
                <span>· 解析 {d.items} 项</span>
                {d.note && <span className="jn-doc-note">· {d.note}</span>}
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="jn-panel">
        <div className="jn-panel-head">要素解析进度</div>
        <div className="jn-elem-list">
          {stage.extractedElements.map(e => {
            const pct = Math.round((e.ready / e.total) * 100);
            const tone = e.blocker ? 'red' : pct === 100 ? 'green' : pct >= 70 ? 'amber' : 'red';
            return (
              <div key={e.cat} className={`jn-elem tone-${tone}`}>
                <div className="jn-elem-cat">{e.cat}</div>
                <div className="jn-elem-bar"><span style={{ width: `${pct}%` }} /></div>
                <div className="jn-elem-num">{e.ready}/{e.total}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ── 4 & 5. dtrb / drb snapshot ── */
function SnapshotBody({ stage }) {
  const s = stage.snapshot;
  return (
    <div className="jn-panel">
      <div className="jn-panel-head">
        <span>{s.version} 快照</span>
        <span className="jn-panel-meta">{s.ts} · 完整度 {s.completeness}%</span>
      </div>
      {s.chapters && (
        <div className="jn-chapters">
          {s.chapters.map(c => (
            <div key={c.name} className={`jn-chapter state-${c.state}`}>
              <span className="jn-chapter-name">{c.name}</span>
              {c.note && <span className="jn-chapter-note">{c.note}</span>}
              <span className={`jn-chapter-pill state-${c.state}`}>
                {c.state === 'ok' ? '齐备' : c.state === 'partial' ? '部分' : '缺失'}
              </span>
            </div>
          ))}
        </div>
      )}
      {s.diff && (
        <div className="jn-diff">
          {s.diff.map((d, i) => (
            <div key={i} className="jn-diff-row">
              <span className="jn-diff-ch">{d.ch}</span>
              <IcArrowRight />
              <span className="jn-diff-change">{d.change}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── 6. contract ── */
function ContractBody({ stage }) {
  const c = stage.contractEvent;
  return (
    <>
      <div className="jn-panel">
        <div className="jn-panel-head">合同事件 · 系统监测</div>
        <div className="jn-contract">
          <div><span className="k">合同 ID</span><span className="v">{c.id}</span></div>
          <div><span className="k">签署时间</span><span className="v">{c.signTs}</span></div>
          <div><span className="k">绑定项目</span><span className="v">{c.bindTs}</span></div>
          <div><span className="k">合同金额</span><span className="v">{c.amount}</span></div>
          <div><span className="k">里程碑数</span><span className="v">{c.milestones}</span></div>
        </div>
      </div>
      <div className="jn-panel">
        <div className="jn-panel-head">LLD 补充字段</div>
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
    </>
  );
}

/* ── 7. delivery ── */
function DeliveryBody({ stage }) {
  return (
    <div className="jn-panel">
      <div className="jn-panel-head">
        <span>五段交付作业</span>
        <span className="jn-panel-meta">人 · 货 · 站 并行推进</span>
      </div>
      <div className="jn-ws">
        {stage.workstreams.map(w => {
          const pct = Math.round((w.done / w.total) * 100);
          return (
            <div key={w.key} className="jn-ws-card">
              <div className="jn-ws-head">
                <span className="jn-ws-icon">{w.icon}</span>
                <span className="jn-ws-name">{w.name}</span>
                <span className="jn-ws-pct">{pct}%</span>
              </div>
              <div className="jn-ws-bar">
                <span className="seg-g" style={{ width: `${pct}%` }} />
                <span className="seg-a" style={{ width: `${(w.atRisk / w.total) * 100}%` }} />
                <span className="seg-r" style={{ width: `${(w.blocked / w.total) * 100}%` }} />
              </div>
              <div className="jn-ws-foot">
                <span>{w.done}/{w.total}</span>
                <span className="jn-ws-kpi">{w.kpi}</span>
              </div>
              {(w.atRisk + w.blocked) > 0 && (
                <div className="jn-ws-risk">
                  {w.atRisk > 0 && <span className="amber">{w.atRisk} 风险</span>}
                  {w.blocked > 0 && <span className="red">{w.blocked} 阻塞</span>}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── 8. completion ── */
function CompletionBody({ stage }) {
  return (
    <div className="jn-grid-2">
      <div className="jn-panel">
        <div className="jn-panel-head">收口指标</div>
        <div className="jn-stats">
          {stage.closeMetrics.map(m => (
            <div key={m.k} className="jn-stat">
              <div className="jn-stat-k">{m.k}</div>
              <div className="jn-stat-v">{m.v}</div>
            </div>
          ))}
        </div>
      </div>
      <div className="jn-panel">
        <div className="jn-panel-head">移交物</div>
        <div className="jn-handover">
          {stage.handover.map(h => (
            <div key={h.item} className="jn-handover-row">
              <span className="jn-handover-check"><IcCheck /></span>
              <span className="jn-handover-item">{h.item}</span>
              {h.note && <span className="jn-handover-note">{h.note}</span>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Stage hero ── */
function StageHero({ stage, idx }) {
  const role = JOURNEY_LANE_ROLES[stage.role];
  return (
    <div className="jn-hero">
      <div className="jn-hero-tag">
        <span className="jn-hero-ord">阶段 {idx + 1} / {JOURNEY_STAGES.length}</span>
        <span className="jn-hero-storyTag">{stage.storyTag}</span>
        <span className="jn-hero-role" style={{ color: role?.color, borderColor: role?.color }}>{role?.label}</span>
        {stage.durationDay != null && (
          <span className="jn-hero-dur" title="该阶段实际占用的日历天数">
            ⏱ {stage.durationDay === 0 ? '即时' : `${stage.durationDay} 天`}
          </span>
        )}
        {stage.sysSnapshot && (
          <span className={`jn-hero-sys sys-${stage.sysSnapshot.overall}`} title={stage.sysSnapshot.highlight}>
            <span className="jn-hero-sys-dot" />
            {stage.sysSnapshot.highlight}
          </span>
        )}
      </div>
      <h1 className="jn-hero-title">{stage.title}</h1>
      <p className="jn-hero-sub">{stage.subtitle}</p>
      <p className="jn-hero-summary">{stage.summary}</p>
    </div>
  );
}

/* ── 全局进度条 ── */
function GlobalProgress({ current, isPlaying, progressInStage }) {
  const totalDays = JOURNEY_STAGES.reduce((s, st) => s + (st.durationDay || 0), 0);
  let daysBefore = 0;
  for (let i = 0; i < current; i++) daysBefore += JOURNEY_STAGES[i].durationDay || 0;
  const currentStageDays = JOURNEY_STAGES[current].durationDay || 0;
  const elapsed = daysBefore + currentStageDays * progressInStage;
  const pct = totalDays === 0 ? 0 : (elapsed / totalDays) * 100;

  return (
    <div className="jn-globalprog">
      <div className="jn-globalprog-bar">
        <div className="jn-globalprog-fill" style={{ width: `${pct}%` }} />
        {JOURNEY_STAGES.map((st, i) => {
          let cum = 0;
          for (let j = 0; j < i; j++) cum += JOURNEY_STAGES[j].durationDay || 0;
          const x = totalDays === 0 ? 0 : (cum / totalDays) * 100;
          return (
            <span
              key={st.key}
              className={`jn-globalprog-tick${i <= current ? ' done' : ''}${i === current ? ' active' : ''}`}
              style={{ left: `${x}%` }}
              title={`${st.name} · ${st.durationDay || 0} 天`}
            />
          );
        })}
      </div>
      <div className="jn-globalprog-meta">
        <span><b>{Math.round(elapsed)}</b> / {totalDays} 天</span>
        <span className="jn-globalprog-stage">{JOURNEY_STAGES[current].name}（{currentStageDays || 0}d）</span>
        {isPlaying && <span className="jn-globalprog-playing">▶ AUTOPLAY · {Math.round(progressInStage * 100)}%</span>}
      </div>
    </div>
  );
}

/* ── Main Journey screen ── */
const AUTOPLAY_MS = 4500;

function readUrlParam(key) {
  if (typeof window === 'undefined') return null;
  return new URLSearchParams(window.location.search).get(key);
}

export default function JourneyScreen() {
  const [current, setCurrent] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progressInStage, setProgressInStage] = useState(0);
  const tickerRef = useRef(null);
  const stage = JOURNEY_STAGES[current];

  /* URL 同步：?autoplay=1 启动 autoplay；?step=N 跳到指定阶段（不用 useSearchParams，避免 SSG 空白） */
  useEffect(() => {
    const ap = readUrlParam('autoplay');
    const st = readUrlParam('step');
    if (st != null) {
      const n = parseInt(st, 10);
      if (!isNaN(n) && n >= 0 && n < JOURNEY_STAGES.length) setCurrent(n);
    }
    if (ap === '1') setIsPlaying(true);
  }, []);

  /* Autoplay 引擎：每阶段播放 AUTOPLAY_MS，自动前进 */
  useEffect(() => {
    if (!isPlaying) {
      setProgressInStage(0);
      if (tickerRef.current) { clearInterval(tickerRef.current); tickerRef.current = null; }
      return;
    }
    const startedAt = Date.now();
    tickerRef.current = setInterval(() => {
      const dt = Date.now() - startedAt;
      const pct = Math.min(1, dt / AUTOPLAY_MS);
      setProgressInStage(pct);
      if (pct >= 1) {
        if (current < JOURNEY_STAGES.length - 1) {
          setCurrent(c => c + 1);
          setProgressInStage(0);
        } else {
          setIsPlaying(false);
        }
      }
    }, 80);
    return () => { if (tickerRef.current) clearInterval(tickerRef.current); };
  }, [isPlaying, current]);

  const togglePlay = () => setIsPlaying(v => !v);
  const restart = () => { setCurrent(0); setProgressInStage(0); setIsPlaying(true); };
  const pick = (i) => { setCurrent(i); setProgressInStage(0); };

  return (
    <div className="jn-wrap" style={{ flex: 1, overflow: 'auto' }}>
      <div className="main-inner">
        <div className="page-head">
          <div>
            <h1>项目全生命周期 · 故事线</h1>
            <div className="sub">TD 登录 → 项目创建 → OCC 审批 → 文档摄取 → DTRB / DRB / 合同 → 交付作业 → 移交收口 · 9 阶段串起产品全貌</div>
          </div>
          <div className="right">
            <button className={`btn sm ${isPlaying ? 'danger' : 'primary'}`} onClick={togglePlay} title={isPlaying ? '暂停' : '从当前阶段播放'}>
              {isPlaying ? '⏸ 暂停' : '▶ 演示'}
            </button>
            <button className="btn sm ghost" onClick={restart} title="重头开始演示">⟲ 重头</button>
            <span style={{ width: 1, height: 14, background: 'var(--c-border)', margin: '0 6px' }} />
            <span>当前</span>
            <span className="text-mono" style={{ color: 'var(--c-text)' }}>
              {String(current + 1).padStart(2, '0')} / {String(JOURNEY_STAGES.length).padStart(2, '0')}
            </span>
            <span style={{ color: JOURNEY_LANE_ROLES[stage.role]?.color, fontFamily: 'var(--font-mono)' }}>{stage.role}</span>
          </div>
        </div>

        <GlobalProgress current={current} isPlaying={isPlaying} progressInStage={progressInStage} />
        <StageStepper current={current} onPick={pick} />
        <StageHero stage={stage} idx={current} />

        {/* 产品页深链 · 一键跳到真实产品页 */}
        {stage.productPath && (
          <div className="jn-deeplink">
            <div className="jn-deeplink-tag">DEEP LINK</div>
            <div className="jn-deeplink-text">
              <strong>{stage.productLabel || '在产品中查看'}</strong>
              <span>本阶段对应的真实产品页面：<code>{stage.productPath}</code></span>
            </div>
            <Link href={stage.productPath} className="btn sm primary">打开产品页 →</Link>
          </div>
        )}
        {/* 次链：同阶段的辅助产品页 */}
        {Array.isArray(stage.productPathExtra) && stage.productPathExtra.length > 0 && (
          <div className="jn-deeplink-extra">
            {stage.productPathExtra.map((p, i) => (
              <Link key={i} href={p.path} className="jn-deeplink-extra-link">
                <span className="jn-deeplink-tag alt">ALT</span>
                <span className="jn-deeplink-extra-label">{p.label}</span>
                <code>{p.path}</code>
                <span className="jn-deeplink-extra-arrow">→</span>
              </Link>
            ))}
          </div>
        )}

        <StageBody stage={stage} />

        <div className="jn-actions-bar">
          <button className="btn sm ghost" disabled={current === 0} onClick={() => pick(Math.max(0, current - 1))}>
            ← 上一阶段
          </button>
          <div className="jn-decision">
            {stage.decisions?.map((d, i) => (
              <button
                key={i}
                className={`btn sm ${d.kind === 'primary' ? 'primary' : d.kind === 'danger' ? 'danger' : 'ghost'}`}
                onClick={() => {
                  if (d.kind === 'primary' && current < JOURNEY_STAGES.length - 1) {
                    pick(current + 1);
                  }
                }}
              >
                {d.label}
              </button>
            ))}
          </div>
          <button
            className="btn sm primary"
            disabled={current === JOURNEY_STAGES.length - 1}
            onClick={() => pick(Math.min(JOURNEY_STAGES.length - 1, current + 1))}
          >
            下一阶段 →
          </button>
        </div>
      </div>
    </div>
  );
}
