/* Tab 2 · 工具测评 —— 本次调用明细 vs 总体趋势 */
import {
  ScatterChart, Scatter, ZAxis, BarChart, Bar, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import {
  C, tickStyle, tooltipStyle, fmt, fmtTs, fmtLatency,
  type ToolMetric, type ToolsReport, type EvalViewMode,
} from './shared';
import { TOOL_METRICS } from './metric-glossary';
import { EvalStat } from './metric-stat';

const SELF_CORRECT_THRESHOLD = 0.15;

const TH = {
  quality: TOOL_METRICS.find(m => m.label.startsWith('评测质量'))!.formula,
  calls: 'calls = 时间窗内工具调用记录条数（Langfuse kind=tool 或 session 本地日志）。',
  toolCount: '聚合后的不同工具 name 数量。',
  flagged: TOOL_METRICS.find(m => m.label.startsWith('需优化'))!.formula,
  avgSelf: TOOL_METRICS[0]!.formula,
  avgSucc: TOOL_METRICS[1]!.formula,
  totalTools: '注册表中参与聚合的工具个数。',
};

const TYPE_TONE: Record<string, string> = {
  '会话': 'blue', 'skill-as-tool': 'violet', '副作用·外发': 'amber', '控制·HITL': 'gray',
};

function ScatterTip({ active, payload }: { active?: boolean; payload?: { payload: ToolMetric }[] }) {
  if (!active || !payload?.length) return null;
  const t = payload[0]!.payload;
  return (
    <div style={{ background: '#fff', border: `1px solid ${C.border}`, borderRadius: 6, padding: '6px 9px', fontSize: 11 }}>
      <div style={{ fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{t.name}</div>
      <div style={{ color: C.muted }}>自纠率 {(t.self_correct_rate * 100).toFixed(0)}% · 调用 {t.calls}</div>
      <div style={{ color: C.muted }}>p95 {fmtLatency(t.latency_p95)}</div>
    </div>
  );
}

function LatestToolsView({
  toolsReport,
  tools,
  onExport,
  live,
}: {
  toolsReport: ToolsReport | null;
  tools: ToolMetric[];
  onExport: () => void;
  live: boolean;
}) {
  const records = toolsReport?.records ?? [];
  const checks = toolsReport?.checks ?? [];
  const s = toolsReport?.summary ?? {};

  return (
    <>
      <div className="jn-stats" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 14 }}>
        <EvalStat label="评测质量" hint={TH.quality} value={s.quality_score != null ? `${(s.quality_score * 100).toFixed(0)}%` : '—'} />
        <EvalStat label="调用次数" hint={TH.calls} value={s.calls ?? 0} />
        <EvalStat label="工具数" hint={TH.toolCount} value={s.tool_count ?? tools.length} />
        <EvalStat
          label="需优化"
          hint={TH.flagged}
          valueStyle={{ color: (s.flagged_count ?? 0) ? 'var(--c-danger)' : undefined }}
          value={s.flagged_count ?? 0}
        />
      </div>

      <div className="jn-panel" style={{ marginBottom: 14 }}>
        <div className="jn-panel-head">本次评测上下文</div>
        <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--c-text-muted)', lineHeight: 1.8 }}>
          <div>evaluated_at: {toolsReport?.evaluated_at ? fmtTs(toolsReport.evaluated_at) : '—'}</div>
          <div>source: {toolsReport?.source ?? '—'}</div>
          <div>window: {toolsReport?.window || '—'}</div>
          {toolsReport?.conv_id && <div>conv_id: {toolsReport.conv_id}</div>}
          {toolsReport?.run_id && <div>run_id: {toolsReport.run_id}</div>}
          <div>record_count: {toolsReport?.record_count ?? records.length}</div>
        </div>
      </div>

      {checks.length > 0 && (
        <div className="jn-panel" style={{ marginBottom: 14 }}>
          <div className="jn-panel-head">基线断言</div>
          <table className="vs-table">
            <thead><tr><th>工具</th><th>检查项</th><th>结果</th><th>详情</th></tr></thead>
            <tbody>
              {checks.map((c, i) => (
                <tr key={i}>
                  <td className="text-mono" style={{ fontSize: 11 }}>{c.tool || '—'}</td>
                  <td>{c.name}</td>
                  <td><span className={`status-pill ${c.pass ? 'green' : 'red'}`}>{c.pass ? '✓' : '✗'}</span></td>
                  <td style={{ fontSize: 11, color: 'var(--c-text-muted)' }}>{c.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="jn-panel" style={{ marginBottom: 14 }}>
        <div className="jn-panel-head">
          调用明细
          <span className="jn-panel-meta" style={{ marginRight: 'auto' }}>{records.length} 条</span>
          <button
            onClick={onExport}
            style={{
              padding: '3px 10px', fontSize: 11, fontWeight: 600,
              background: 'var(--c-brand-soft)', color: 'var(--c-brand)',
              border: '1px solid var(--c-brand)', borderRadius: 'var(--r-md)', cursor: 'pointer',
            }}
          >
            导出待优化工具 →
          </button>
        </div>
        {records.length === 0 ? (
          <div className="jn-hint">无调用记录。会话调工具或跑 eval_tools 后会写入 records。</div>
        ) : (
          <table className="vs-table">
            <thead>
              <tr><th>时间</th><th>工具</th><th>scope</th><th>step</th><th>结果</th><th>延迟</th><th>错误摘要</th></tr>
            </thead>
            <tbody>
              {records.map((r, i) => (
                <tr key={i}>
                  <td className="text-mono" style={{ fontSize: 10 }}>{r.ts ? fmtTs(r.ts) : '—'}</td>
                  <td><b style={{ fontFamily: 'var(--font-mono)' }}>{r.tool}</b></td>
                  <td className="text-mono" style={{ fontSize: 10 }}>{r.scope || '—'}</td>
                  <td className="text-mono" style={{ fontSize: 10 }}>{r.step || '—'}</td>
                  <td><span className={`status-pill ${r.ok ? 'green' : 'red'}`}>{r.ok ? 'ok' : 'fail'}</span></td>
                  <td className="text-mono">{fmtLatency(r.latency_ms)}</td>
                  <td style={{ fontSize: 10, color: 'var(--c-text-muted)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.error || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="jn-hint" style={{ marginTop: 8 }}>
          {live
            ? '数据源：会话本地日志 / Langfuse（按 conv_id 过滤）'
            : '未连上 Agent（7401）或无评测结果 · 请确认 Agent 已启动，在会话里再调一次工具后点「跑评测」'}
        </div>
      </div>

      <div className="jn-panel" style={{ marginBottom: 14 }}>
        <div className="jn-panel-head">按工具聚合（本次窗口）</div>
        <table className="vs-table">
          <thead><tr><th>工具</th><th>类型</th><th>调用</th><th>自纠率</th><th>p95</th></tr></thead>
          <tbody>
            {tools.map(t => (
              <tr key={t.name}>
                <td><b style={{ fontFamily: 'var(--font-mono)' }}>{t.name}</b></td>
                <td><span className={`status-pill ${TYPE_TONE[t.type] ?? ''}`}>{t.type}</span></td>
                <td className="num">{t.calls}</td>
                <td><span className={`status-pill ${t.self_correct_rate > SELF_CORRECT_THRESHOLD ? 'red' : 'green'}`}>{(t.self_correct_rate * 100).toFixed(0)}%</span></td>
                <td className="text-mono">{fmtLatency(t.latency_p95)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function OverviewToolsView({
  tools,
  onExport,
  live,
}: {
  tools: ToolMetric[];
  onExport: () => void;
  live: boolean;
}) {
  const avgSelf = tools.reduce((a, t) => a + t.self_correct_rate, 0) / (tools.length || 1);
  const avgSucc = tools.reduce((a, t) => a + t.success_rate, 0) / (tools.length || 1);
  const totalCalls = tools.reduce((a, t) => a + t.calls, 0);
  const bySelf = [...tools].sort((a, b) => b.self_correct_rate - a.self_correct_rate);
  const flagged = tools.filter(t => t.self_correct_rate > SELF_CORRECT_THRESHOLD).length;

  return (
    <>
      <div className="jn-stats" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 14 }}>
        <EvalStat label="工具总数" hint={TH.totalTools} value={tools.length} />
        <EvalStat
          label="平均自纠率"
          hint={TH.avgSelf}
          valueStyle={{ color: avgSelf > SELF_CORRECT_THRESHOLD ? 'var(--c-warning)' : undefined }}
          value={`${(avgSelf * 100).toFixed(0)}%`}
        />
        <EvalStat label="平均成功率" hint={TH.avgSucc} value={`${(avgSucc * 100).toFixed(0)}%`} />
        <EvalStat
          label="需优化工具"
          hint={TH.flagged}
          valueStyle={{ color: flagged ? 'var(--c-danger)' : undefined }}
          value={flagged}
        />
      </div>

      <div className="jn-panel" style={{ marginBottom: 14 }}>
        <div className="jn-panel-head">
          自纠率 × 调用热度
          <span className="jn-panel-meta">{TOOL_METRICS[3]!.interpret}</span>
        </div>
        <ResponsiveContainer width="100%" height={260}>
          <ScatterChart margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={C.border} />
            <XAxis type="number" dataKey="calls" name="调用次数" tick={tickStyle} domain={[0, 'dataMax']} label={{ value: '调用次数 →', position: 'insideBottomRight', offset: -4, style: { fontSize: 10, fill: C.muted } }} />
            <YAxis type="number" dataKey="self_correct_rate" name="自纠率" tick={tickStyle} domain={[0, 0.4]} tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
            <ZAxis type="number" dataKey="latency_p95" range={[60, 500]} />
            <Tooltip content={<ScatterTip />} cursor={{ strokeDasharray: '3 3' }} />
            <ReferenceLine y={SELF_CORRECT_THRESHOLD} stroke={C.danger} strokeDasharray="4 2" label={{ value: '阈值 15%', position: 'right', style: { fontSize: 9, fill: C.danger } }} />
            <Scatter data={tools}>
              {tools.map((t, i) => <Cell key={i} fill={t.self_correct_rate > SELF_CORRECT_THRESHOLD ? C.danger : C.brand} />)}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      <div className="jn-grid-2" style={{ marginBottom: 14 }}>
        <div className="jn-panel" style={{ marginBottom: 0 }}>
          <div className="jn-panel-head">自纠率排行<span className="jn-panel-meta">红=超阈值</span></div>
          <ResponsiveContainer width="100%" height={170}>
            <BarChart layout="vertical" data={bySelf} margin={{ top: 4, right: 30, left: 20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} horizontal={false} />
              <XAxis type="number" tick={tickStyle} tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
              <YAxis type="category" dataKey="name" tick={{ ...tickStyle, fontSize: 10 }} width={88} />
              <Tooltip contentStyle={tooltipStyle} formatter={fmt(v => [`${(v * 100).toFixed(0)}%`, '自纠率'])} />
              <Bar dataKey="self_correct_rate" radius={[0, 3, 3, 0]}>
                {bySelf.map((t, i) => <Cell key={i} fill={t.self_correct_rate > SELF_CORRECT_THRESHOLD ? C.danger : C.success} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="jn-panel" style={{ marginBottom: 0 }}>
          <div className="jn-panel-head">延迟 p50 / p95<span className="jn-panel-meta">对数轴</span></div>
          <ResponsiveContainer width="100%" height={170}>
            <BarChart data={tools} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} vertical={false} />
              <XAxis dataKey="name" tick={{ ...tickStyle, fontSize: 9 }} interval={0} angle={-15} textAnchor="end" height={42} />
              <YAxis scale="log" domain={[1, 'auto']} tick={tickStyle} tickFormatter={(v: number) => v >= 1000 ? `${v / 1000}s` : `${v}`} />
              <Tooltip contentStyle={tooltipStyle} formatter={fmt((v, n) => [fmtLatency(v), n ?? ''])} />
              <Bar dataKey="latency_p50" fill={C.info} name="p50" radius={[2, 2, 0, 0]} />
              <Bar dataKey="latency_p95" fill={C.warning} name="p95" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="jn-panel" style={{ marginBottom: 14 }}>
        <div className="jn-panel-head">
          工具注册表
          <span className="jn-panel-meta" style={{ marginRight: 'auto' }}>{tools.length} 个 · 共 {totalCalls} 次调用</span>
          <button
            onClick={onExport}
            style={{
              padding: '3px 10px', fontSize: 11, fontWeight: 600,
              background: 'var(--c-brand-soft)', color: 'var(--c-brand)',
              border: '1px solid var(--c-brand)', borderRadius: 'var(--r-md)', cursor: 'pointer',
            }}
          >
            导出待优化工具 →
          </button>
        </div>
        <table className="vs-table">
          <thead><tr><th>工具</th><th>类型</th><th>scope</th><th>调用</th><th>自纠率</th><th>成功率</th><th>p95</th></tr></thead>
          <tbody>
            {bySelf.map(t => (
              <tr key={t.name}>
                <td><b style={{ fontFamily: 'var(--font-mono)' }}>{t.name}</b></td>
                <td><span className={`status-pill ${TYPE_TONE[t.type] ?? ''}`}>{t.type}</span></td>
                <td className="text-mono" style={{ fontSize: 11, color: 'var(--c-text-muted)' }}>{t.scope}</td>
                <td className="num">{t.calls}</td>
                <td><span className={`status-pill ${t.self_correct_rate > SELF_CORRECT_THRESHOLD ? 'red' : 'green'}`}>{(t.self_correct_rate * 100).toFixed(0)}%</span></td>
                <td className="num">{(t.success_rate * 100).toFixed(0)}%</td>
                <td className="text-mono">{fmtLatency(t.latency_p95)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="jn-hint">
          数据源：{live ? 'agent/evals/results/tools-*.json（Langfuse 聚合）' : '演示数据 · 会话/工勘结束后会自动跑评测'}
        </div>
      </div>
    </>
  );
}

export default function ToolsTab({
  tools,
  toolsReport,
  mode,
  onExport,
  live = false,
}: {
  tools: ToolMetric[];
  toolsReport: ToolsReport | null;
  mode: EvalViewMode;
  onExport: () => void;
  live?: boolean;
}) {
  if (mode === 'latest') {
    return <LatestToolsView toolsReport={toolsReport} tools={tools} onExport={onExport} live={live} />;
  }
  return <OverviewToolsView tools={tools} onExport={onExport} live={live} />;
}
