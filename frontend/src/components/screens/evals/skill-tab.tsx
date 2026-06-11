/* Tab 1 · SKILL 测评 —— 质量塌没塌 + 流程哪步流失 */
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, LabelList,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import {
  C, STEP_META, tickStyle, tooltipStyle, fmt,
  fmtTs, fmtLatency, fmtCost, qualityTone, pickColor,
  LANGFUSE_HOST,
  type EvalReport,
  type EvalRun,
  type EvalViewMode,
} from './shared';
import { SKILL_CHARTS, SKILL_FOUR_DIM, getProductMetricHelp } from './metric-glossary';
import { EvalStat } from './metric-stat';

const H = {
  quality: SKILL_FOUR_DIM[0]!.formula,
  successOverview: '总体：success_count / total（历次 eval 落盘 JSON）。',
  latency: SKILL_FOUR_DIM[2]!.formula,
  cost: SKILL_FOUR_DIM[3]!.formula,
};

function KpiRow({ s }: { s: EvalReport['summary'] }) {
  const q = s.latest_quality;
  return (
    <div className="jn-stats" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 14 }}>
      <EvalStat
        label="最近质量得分"
        hint={H.quality}
        valueStyle={{ color: q != null && q < 0.9 ? 'var(--c-warning)' : undefined }}
        value={q != null ? `${(q * 100).toFixed(0)}%` : '—'}
      />
      <EvalStat
        label="总体成功率"
        hint={H.successOverview}
        valueStyle={{ color: s.success_rate < 0.8 ? 'var(--c-danger)' : undefined }}
        value={s.total > 0 ? `${s.success_count}/${s.total}` : '—'}
      />
      <EvalStat label="最近延迟" hint={H.latency} value={fmtLatency(s.latest_latency_ms)} />
      <EvalStat label="最近成本" hint={H.cost} value={fmtCost(s.latest_cost_cny)} />
    </div>
  );
}

function MiniLine({ data, dataKey, color, label, unit, domain, refLine }: {
  data: object[]; dataKey: string; color: string; label: string; unit: string;
  domain?: [number, number]; refLine?: number;
}) {
  return (
    <div className="jn-panel" style={{ marginBottom: 0 }}>
      <div className="jn-panel-head">{label}<span className="jn-panel-meta">最近 {data.length} 次 · {unit}</span></div>
      <ResponsiveContainer width="100%" height={140}>
        <LineChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={C.border} vertical={false} />
          <XAxis dataKey="ts" tick={tickStyle} interval="preserveStartEnd" />
          <YAxis tick={tickStyle} domain={domain} />
          <Tooltip contentStyle={tooltipStyle} />
          {refLine != null && <ReferenceLine y={refLine} stroke={C.border} strokeDasharray="4 2" />}
          <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} dot={{ r: 3, fill: color }} activeDot={{ r: 5 }} connectNulls />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function LatestSkillView({ run, onExport }: { run: EvalRun; onExport: () => void }) {
  const passN = run.checks.filter(c => c.pass).length;
  const metrics = run.metrics ?? {};
  const stepBars = STEP_META.map(s => ({
    name: s.label,
    ms: run.step_durations?.[s.key] ?? 0,
    status: run.step_status?.[s.key] ?? 'pending',
    fill: s.color,
  }));

  return (
    <>
      <div className="jn-stats" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 14 }}>
        <EvalStat
          label="质量得分"
          hint={H.quality}
          valueStyle={{ color: run.quality_score < 0.9 ? 'var(--c-warning)' : undefined }}
          value={`${(run.quality_score * 100).toFixed(0)}%`}
        />
        <EvalStat
          label="成功率"
          hint={SKILL_FOUR_DIM[1]!.formula}
          valueStyle={{ color: run.success ? undefined : 'var(--c-danger)' }}
          value={run.success ? '通过' : '失败'}
        />
        <EvalStat label="延迟" hint={H.latency} value={fmtLatency(run.latency_ms)} />
        <EvalStat label="成本" hint={H.cost} value={fmtCost(run.cost_cny)} />
      </div>

      <div className="jn-panel" style={{ marginBottom: 14 }}>
        <div className="jn-panel-head">执行标识</div>
        <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--c-text-muted)', lineHeight: 1.8 }}>
          <div>evaluated_at: {fmtTs(run.evaluated_at)}</div>
          <div>run_id: {run.run_id || '—'}</div>
          <div>trace_id: {run.trace_id || '—'}</div>
          {run.metrics_source && <div>metrics_source: {run.metrics_source}</div>}
          {run.trace_id && (
            <a
              href={`${LANGFUSE_HOST}/trace/${run.trace_id}`}
              target="_blank"
              rel="noreferrer"
              style={{ color: 'var(--c-brand)', fontSize: 11 }}
            >
              在 Langfuse 查看 trace →
            </a>
          )}
        </div>
      </div>

      {stepBars.some(s => s.ms > 0) && (
        <div className="jn-panel" style={{ marginBottom: 14 }}>
          <div className="jn-panel-head">
            step 耗时
            <span className="jn-panel-meta">CHAIN span / 产物 duration_ms</span>
          </div>
          <ResponsiveContainer width="100%" height={120}>
            <BarChart data={stepBars} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} vertical={false} />
              <XAxis dataKey="name" tick={{ ...tickStyle, fontSize: 9 }} />
              <YAxis tick={tickStyle} tickFormatter={(v: number) => `${(v / 1000).toFixed(1)}s`} />
              <Tooltip contentStyle={tooltipStyle} formatter={fmt(v => [`${(v / 1000).toFixed(2)}s`, '耗时'])} />
              <Bar dataKey="ms" fill={C.brand} radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="jn-panel" style={{ marginBottom: 14 }}>
        <div className="jn-panel-head">产物指标<span className="jn-panel-meta">来自 skill_result.json</span></div>
        <table className="vs-table">
          <thead><tr><th>指标</th><th>值</th><th>含义 / 基线</th></tr></thead>
          <tbody>
            {Object.entries(metrics).map(([k, v]) => {
              const help = getProductMetricHelp(k);
              return (
                <tr key={k}>
                  <td className="text-mono" style={{ fontSize: 12 }}>{k}</td>
                  <td>{v != null ? String(v) : '—'}</td>
                  <td style={{ fontSize: 11, color: 'var(--c-text-muted)', maxWidth: 280 }}>
                    {help ? help.interpret ?? help.meaning : '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="jn-panel" style={{ marginBottom: 14 }}>
        <div className="jn-panel-head">
          断言详情
          <span className="jn-panel-meta" style={{ marginRight: 'auto' }}>{passN}/{run.checks.length} 通过</span>
          <button
            onClick={onExport}
            style={{
              padding: '3px 10px', fontSize: 11, fontWeight: 600,
              background: 'var(--c-brand-soft)', color: 'var(--c-brand)',
              border: '1px solid var(--c-brand)', borderRadius: 'var(--r-md)', cursor: 'pointer',
            }}
          >
            导出偏离 JSON →
          </button>
        </div>
        <table className="vs-table">
          <thead><tr><th>断言</th><th>结果</th><th>详情</th></tr></thead>
          <tbody>
            {run.checks.map((c, i) => (
              <tr key={i}>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{c.name}</td>
                <td><span className={`status-pill ${c.pass ? 'green' : 'red'}`}>{c.pass ? '✓ 通过' : '✗ 失败'}</span></td>
                <td style={{ color: 'var(--c-text-muted)', fontSize: 12 }}>{c.detail || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function SkillTab({
  report,
  mode,
  onExport,
}: {
  report: EvalReport;
  mode: EvalViewMode;
  onExport: () => void;
}) {
  const runs = report.runs?.length ? report.runs : report.run ? [report.run] : [];
  if (!runs.length) {
    return (
      <div className="jn-panel">
        <div className="jn-hint">
          还没有 eval 结果。跑完工勘/会话工具后会自动评测，或点「跑评测」。
        </div>
      </div>
    );
  }
  const latest = runs[0]!;

  if (mode === 'latest') {
    return <LatestSkillView run={latest} onExport={onExport} />;
  }
  const ordered = report.runs.slice(0, 20).reverse();

  const trend = ordered.map(r => ({
    ts: fmtTs(r.evaluated_at),
    quality: r.quality_score != null ? Math.round(r.quality_score * 100) : null,
    latency: r.latency_ms != null ? +(r.latency_ms / 1000).toFixed(1) : null,
    cost: r.cost_cny,
  }));

  // 流程漏斗：各 step 在所有 run 里完成的数量（自然递减 → 看流失）
  const funnelData = STEP_META.map(s => ({
    name: s.label,
    value: report.runs.filter(r => r.step_status?.[s.key] === 'completed').length,
    fill: s.color,
  }));

  // step 耗时堆叠柱（秒）
  const stepBars = report.runs.slice(0, 8).reverse().map(r => {
    const row: Record<string, number | string> = { ts: fmtTs(r.evaluated_at) };
    for (const s of STEP_META) row[s.key] = +((r.step_durations?.[s.key] ?? 0) / 1000).toFixed(1);
    return row;
  });

  // 待办构成环图（最近一次 empty_by_type）
  const empty = latest.empty_by_type ?? {};
  const donut = Object.entries(empty).map(([name, value]) => ({ name, value }));
  const openTotal = donut.reduce((a, b) => a + b.value, 0);

  const passN = latest.checks.filter(c => c.pass).length;

  return (
    <>
      <KpiRow s={report.summary} />

      {/* 趋势区 */}
      <div className="jn-grid-2" style={{ marginBottom: 14 }}>
        <MiniLine data={trend} dataKey="quality" color={C.brand} label="质量得分趋势" unit="%" domain={[0, 100]} refLine={90} />
        <MiniLine data={trend} dataKey="latency" color={C.warning} label="端到端延迟趋势" unit="秒" />
      </div>

      {/* 流程区 · SKILL 灵魂 */}
      <div className="jn-grid-2" style={{ marginBottom: 14 }}>
        <div className="jn-panel" style={{ marginBottom: 0 }}>
          <div className="jn-panel-head">
            流程漏斗
            <span className="jn-panel-meta">{SKILL_CHARTS.funnel!.meaning} · {report.runs.length} run</span>
          </div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart layout="vertical" data={funnelData} margin={{ top: 8, right: 44, left: 16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} horizontal={false} />
              <XAxis type="number" tick={tickStyle} domain={[0, report.runs.length]} allowDecimals={false} />
              <YAxis type="category" dataKey="name" tick={{ ...tickStyle, fontSize: 11 }} width={64} />
              <Tooltip contentStyle={tooltipStyle} formatter={fmt(v => [`${v} / ${report.runs.length} run`, '完成'])} />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={22}>
                {funnelData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                <LabelList dataKey="value" position="right" style={{ fontSize: 11, fontWeight: 700, fill: C.muted }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="jn-panel" style={{ marginBottom: 0 }}>
          <div className="jn-panel-head">
            step 耗时拆解
            <span className="jn-panel-meta">最近 8 次 · 秒 · {SKILL_CHARTS.step_duration!.interpret}</span>
          </div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={stepBars} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} vertical={false} />
              <XAxis dataKey="ts" tick={tickStyle} interval="preserveStartEnd" />
              <YAxis tick={tickStyle} />
              <Tooltip contentStyle={tooltipStyle} />
              {STEP_META.map(s => <Bar key={s.key} dataKey={s.key} stackId="d" fill={s.color} name={s.label} />)}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 成本趋势 + 待办构成 */}
      <div className="jn-grid-2" style={{ marginBottom: 14 }}>
        <MiniLine data={trend} dataKey="cost" color={C.success} label="成本趋势" unit="¥/run" />
        <div className="jn-panel" style={{ marginBottom: 0 }}>
          <div className="jn-panel-head">
            待办项构成
            <span className="jn-panel-meta">{SKILL_CHARTS.empty_donut!.formula} · {openTotal} 项</span>
          </div>
          <ResponsiveContainer width="100%" height={140}>
            <PieChart>
              <Pie data={donut} dataKey="value" nameKey="name" innerRadius={38} outerRadius={62} paddingAngle={2}>
                {donut.map((_, i) => <Cell key={i} fill={pickColor(i + 2)} />)}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
              <text x="50%" y="50%" textAnchor="middle" dominantBaseline="middle" style={{ fontSize: 18, fontWeight: 800, fill: C.muted }}>{openTotal}</text>
            </PieChart>
          </ResponsiveContainer>
          <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap', fontSize: 11, color: C.muted }}>
            {donut.map((d, i) => (
              <span key={d.name} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: pickColor(i + 2) }} />{d.name} {d.value}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* 断言详情 + 导出 */}
      <div className="jn-panel" style={{ marginBottom: 14 }}>
        <div className="jn-panel-head">
          最新断言详情
          <span className="jn-panel-meta" style={{ marginRight: 'auto' }}>{fmtTs(latest.evaluated_at)} · {passN}/{latest.checks.length} 通过</span>
          <button onClick={onExport} style={{ padding: '3px 10px', fontSize: 11, fontWeight: 600, background: 'var(--c-brand-soft)', color: 'var(--c-brand)', border: '1px solid var(--c-brand)', borderRadius: 'var(--r-md)', cursor: 'pointer' }}>
            导出偏离 JSON →
          </button>
        </div>
        <table className="vs-table">
          <thead><tr><th>断言</th><th>结果</th><th>详情</th></tr></thead>
          <tbody>
            {latest.checks.map((c, i) => (
              <tr key={i}>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>{c.name}</td>
                <td><span className={`status-pill ${c.pass ? 'green' : 'red'}`}>{c.pass ? '✓ 通过' : '✗ 失败'}</span></td>
                <td style={{ color: 'var(--c-text-muted)', fontSize: 12 }}>{c.detail || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 历次记录 */}
      <div className="jn-panel" style={{ marginBottom: 14 }}>
        <div className="jn-panel-head">历次评测记录<span className="jn-panel-meta">{report.runs.length} 条</span></div>
        <table className="vs-table">
          <thead><tr><th>时间</th><th>质量</th><th>成功</th><th>延迟</th><th>成本</th><th>Trace</th></tr></thead>
          <tbody>
            {report.runs.map((r, i) => (
              <tr key={i}>
                <td className="text-mono" style={{ fontSize: 11 }}>{fmtTs(r.evaluated_at)}</td>
                <td><span className={`status-pill ${qualityTone(r.quality_score)}`}>{r.quality_score != null ? `${(r.quality_score * 100).toFixed(0)}%` : '—'}</span></td>
                <td><span className={`status-pill ${r.success ? 'green' : 'red'}`}>{r.success ? '通过' : '失败'}</span></td>
                <td className="text-mono">{fmtLatency(r.latency_ms)}</td>
                <td className="text-mono">{fmtCost(r.cost_cny)}</td>
                <td className="text-mono" style={{ fontSize: 10, color: 'var(--c-text-faint)' }}>{r.trace_id ? r.trace_id.slice(0, 8) + '…' : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
