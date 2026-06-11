/* Tab 3 · Langfuse 可观测大盘（混合模式）—— 业务口径自渲染 + trace 深链接跳 Langfuse */
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import {
  C, PALETTE, LANGFUSE_HOST, tickStyle, tooltipStyle, pickColor, fmt,
  fmtLatency, fmtTs, type ObsData,
} from './shared';
import { OBS_METRICS } from './metric-glossary';
import { EvalStat } from './metric-stat';

function fmtTokens(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(0)}k` : String(n);
}

export default function ObsTab({ obs }: { obs: ObsData }) {
  const { kpi, models, cost_by_day, model_share, token_trend, latency_hist, traces } = obs;

  return (
    <>
      {/* KPI */}
      <div className="jn-hint" style={{ marginBottom: 10, borderTop: 'none', paddingTop: 0, fontStyle: 'normal' }}>
        本 Tab 当前为演示数据；指标含义与 Langfuse 大盘一致，接入 live 后口径相同。
      </div>
      <div className="jn-stats" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 14 }}>
        <EvalStat label="本月成本" hint={OBS_METRICS[0]!.formula} value={`¥${kpi.cost_cny.toFixed(2)}`} />
        <EvalStat label="总 Token" hint={OBS_METRICS[1]!.formula} value={fmtTokens(kpi.tokens)} />
        <EvalStat label="总 run" hint={OBS_METRICS[2]!.formula} value={kpi.runs} />
        <EvalStat label="平均延迟" hint={OBS_METRICS[3]!.formula} value={fmtLatency(kpi.avg_latency_ms)} />
      </div>

      {/* 成本按天堆叠（按模型） */}
      <div className="jn-panel" style={{ marginBottom: 14 }}>
        <div className="jn-panel-head">成本趋势<span className="jn-panel-meta">按天 × 模型 · ¥</span></div>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={cost_by_day} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={C.border} vertical={false} />
            <XAxis dataKey="date" tick={tickStyle} />
            <YAxis tick={tickStyle} />
            <Tooltip contentStyle={tooltipStyle} formatter={fmt(v => `¥${v.toFixed(2)}`)} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {models.map((m, i) => <Bar key={m} dataKey={m} stackId="c" fill={pickColor(i)} />)}
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 成本构成饼 + token 双线 */}
      <div className="jn-grid-2" style={{ marginBottom: 14 }}>
        <div className="jn-panel" style={{ marginBottom: 0 }}>
          <div className="jn-panel-head">成本构成<span className="jn-panel-meta">按模型 · ¥</span></div>
          <ResponsiveContainer width="100%" height={160}>
            <PieChart>
              <Pie data={model_share} dataKey="cost" nameKey="name" innerRadius={40} outerRadius={64} paddingAngle={2}>
                {model_share.map((_, i) => <Cell key={i} fill={pickColor(i)} />)}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} formatter={fmt(v => `¥${v.toFixed(2)}`)} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="jn-panel" style={{ marginBottom: 0 }}>
          <div className="jn-panel-head">Token 消耗<span className="jn-panel-meta">input / output</span></div>
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={token_trend} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} vertical={false} />
              <XAxis dataKey="date" tick={tickStyle} />
              <YAxis tick={tickStyle} tickFormatter={fmtTokens} />
              <Tooltip contentStyle={tooltipStyle} formatter={fmt(v => fmtTokens(v))} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line type="monotone" dataKey="input" stroke={C.brand} strokeWidth={2} dot={{ r: 2 }} name="input" />
              <Line type="monotone" dataKey="output" stroke={C.success} strokeWidth={2} dot={{ r: 2 }} name="output" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 模型路由占比 + 延迟分布直方 */}
      <div className="jn-grid-2" style={{ marginBottom: 14 }}>
        <div className="jn-panel" style={{ marginBottom: 0 }}>
          <div className="jn-panel-head">模型路由<span className="jn-panel-meta">按调用次数占比</span></div>
          <ResponsiveContainer width="100%" height={160}>
            <PieChart>
              <Pie data={model_share} dataKey="calls" nameKey="name" outerRadius={64} label={{ fontSize: 10 }}>
                {model_share.map((_, i) => <Cell key={i} fill={pickColor(i)} />)}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} formatter={fmt(v => `${v} 次`)} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="jn-panel" style={{ marginBottom: 0 }}>
          <div className="jn-panel-head">延迟分布<span className="jn-panel-meta">调用数 × 延迟区间</span></div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={latency_hist} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={C.border} vertical={false} />
              <XAxis dataKey="range" tick={{ ...tickStyle, fontSize: 9 }} />
              <YAxis tick={tickStyle} />
              <Tooltip contentStyle={tooltipStyle} formatter={fmt(v => [`${v} 次`, '调用'])} />
              <Bar dataKey="count" radius={[2, 2, 0, 0]}>
                {latency_hist.map((_, i) => <Cell key={i} fill={i >= 3 ? C.warning : C.info} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Trace 浏览器 · 深链接跳 Langfuse 原生（混合模式精髓） */}
      <div className="jn-panel" style={{ marginBottom: 14 }}>
        <div className="jn-panel-head">最近 Trace<span className="jn-panel-meta">点击跳 Langfuse 看 span 明细</span></div>
        <table className="vs-table">
          <thead><tr><th>Trace</th><th>名称</th><th>模型</th><th>成本</th><th>延迟</th><th>时间</th></tr></thead>
          <tbody>
            {traces.map(t => (
              <tr key={t.trace_id}>
                <td>
                  <a href={`${LANGFUSE_HOST}/trace/${t.trace_id}`} target="_blank" rel="noreferrer"
                     style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--c-brand)' }}>
                    {t.trace_id.slice(0, 10)}… ↗
                  </a>
                </td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{t.name}</td>
                <td><span className={`status-pill ${t.model === 'glm-4.5' ? 'violet' : 'blue'}`}>{t.model}</span></td>
                <td className="text-mono">¥{t.cost_cny.toFixed(4)}</td>
                <td className="text-mono">{fmtLatency(t.latency_ms)}</td>
                <td className="text-mono" style={{ fontSize: 11, color: 'var(--c-text-muted)' }}>{fmtTs(t.ts)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="jn-hint">
          混合模式：聚合指标（成本/token/模型路由）用 AIDA 样式自渲染；单条 trace 的 span/prompt 明细深链接跳 Langfuse 原生，不重复造轮子。
        </div>
      </div>
    </>
  );
}
