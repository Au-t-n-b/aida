/* 三 tab 演示数据 · 锚定真实 step / 工具 / 模型名，截图有说服力。
 * 真实数据接通后逐个替换（SKILL 已有 /agent/evals/report；工具/大盘待 v1.5/v2）。 */
import type { EvalReport, EvalRun, ToolMetric, ObsData } from './shared';

// ─── SKILL：8 次 run，中间一次 report_gen 失败、最近一次卡在 report_gen（漏斗断崖）───
function mkRun(i: number, q: number, ok: boolean, lat: number, stuck: boolean): EvalRun {
  return {
    skill: 'zhgk',
    evaluated_at: new Date(Date.now() - (7 - i) * 3600_000).toISOString(),
    quality_score: q,
    success: ok,
    cost_cny: +(0.018 + Math.random() * 0.012).toFixed(4),
    latency_ms: lat,
    metrics: { completion_rate: 53.9, mandatory_fill_rate: 0.5, open_issues: 59, steps_completed: stuck ? 2 : 4, steps_total: 4 },
    checks: [
      { name: 'completion_rate ≥ 基线', pass: q >= 0.6, detail: '53.9 ≥ 45.0' },
      { name: 'mandatory_fill_rate ≥ 基线', pass: true, detail: '0.5 ≥ 0.4' },
      { name: 'open_issues ≤ 基线', pass: true, detail: '59 ≤ 80' },
      { name: 'step[scene_filter] = completed', pass: true, detail: '' },
      { name: 'step[survey_build] = completed', pass: q >= 0.6, detail: '' },
    ],
    run_id: `run-demo-000${i}`,
    trace_id: `6e060${i}abcdef1234567890`,
    step_durations: { scene_filter: 1200, survey_build: 8800, report_gen: stuck ? 0 : 24000, distribute: stuck ? 0 : 4600 },
    step_status: stuck
      ? { scene_filter: 'completed', survey_build: 'completed', report_gen: 'pending', distribute: 'pending' }
      : { scene_filter: 'completed', survey_build: 'completed', report_gen: 'completed', distribute: 'completed' },
    empty_by_type: { 待客户确认: 3, 待拍摄图片: 28, 待补充勘测: 28 },
  };
}

const SKILL_RUNS: EvalRun[] = [
  mkRun(0, 1.0, true, 38600, false),
  mkRun(1, 0.8, false, 41200, false),
  mkRun(2, 1.0, true, 36100, false),
  mkRun(3, 1.0, true, 39000, false),
  mkRun(4, 0.6, false, 52000, false),
  mkRun(5, 1.0, true, 35800, false),
  mkRun(6, 1.0, true, 37200, false),
  mkRun(7, 1.0, true, 38100, true),   // 最近一次：卡在 report_gen
].reverse(); // 最近的在前

export const MOCK_SKILL_REPORT: EvalReport = {
  skill: 'zhgk',
  total: SKILL_RUNS.length,
  source: 'mock',
  summary: {
    quality_avg: 0.925,
    success_rate: 0.75,
    success_count: 6,
    total: 8,
    latest_quality: SKILL_RUNS[0]!.quality_score,
    latest_success: SKILL_RUNS[0]!.success,
    latest_cost_cny: SKILL_RUNS[0]!.cost_cny,
    latest_latency_ms: SKILL_RUNS[0]!.latency_ms,
    latency_p50: 38345,
  },
  runs: SKILL_RUNS,
};

// ─── 工具：5 个真实工具，read_file 自纠率高（path 老写错）= 散点右上角明星问题 ───
export const MOCK_TOOLS: ToolMetric[] = [
  { name: 'read_file',       type: '会话',        scope: 'default',     calls: 342, self_correct_rate: 0.31, success_rate: 0.94, latency_p50: 12,   latency_p95: 45 },
  { name: 'run_survey',      type: 'skill-as-tool', scope: 'default',   calls: 47,  self_correct_rate: 0.06, success_rate: 0.91, latency_p50: 38000, latency_p95: 52000 },
  { name: 'send_mail',       type: '副作用·外发',  scope: 'default',    calls: 89,  self_correct_rate: 0.04, success_rate: 0.99, latency_p50: 220,  latency_p95: 480 },
  { name: 'send_welink',     type: '副作用·外发',  scope: 'default',    calls: 53,  self_correct_rate: 0.02, success_rate: 0.98, latency_p50: 180,  latency_p95: 390 },
  { name: 'present_choices', type: '控制·HITL',    scope: 'default',    calls: 118, self_correct_rate: 0.09, success_rate: 1.0,  latency_p50: 5,    latency_p95: 12 },
];

// ─── Langfuse 大盘：成本主要来自 glm-4.5（report_gen），glm-4-flash 便宜量大 ───
export const MOCK_OBS: ObsData = {
  kpi: { cost_cny: 4.82, tokens: 1_284_000, runs: 47, avg_latency_ms: 38600 },
  models: ['glm-4.5', 'glm-4-flash'],
  cost_by_day: [
    { date: '05-28', 'glm-4.5': 0.42, 'glm-4-flash': 0.08 },
    { date: '05-29', 'glm-4.5': 0.61, 'glm-4-flash': 0.11 },
    { date: '05-30', 'glm-4.5': 0.38, 'glm-4-flash': 0.07 },
    { date: '05-31', 'glm-4.5': 0.55, 'glm-4-flash': 0.13 },
    { date: '06-01', 'glm-4.5': 0.72, 'glm-4-flash': 0.15 },
    { date: '06-02', 'glm-4.5': 0.68, 'glm-4-flash': 0.12 },
    { date: '06-03', 'glm-4.5': 0.51, 'glm-4-flash': 0.10 },
  ],
  model_share: [
    { name: 'glm-4.5',     cost: 3.87, calls: 188 },
    { name: 'glm-4-flash', cost: 0.95, calls: 612 },
  ],
  token_trend: [
    { date: '05-28', input: 142000, output: 18000 },
    { date: '05-29', input: 198000, output: 24000 },
    { date: '05-30', input: 121000, output: 15000 },
    { date: '05-31', input: 176000, output: 21000 },
    { date: '06-01', input: 231000, output: 28000 },
    { date: '06-02', input: 209000, output: 25000 },
    { date: '06-03', input: 163000, output: 19000 },
  ],
  latency_hist: [
    { range: '0-1s', count: 412 },
    { range: '1-5s', count: 168 },
    { range: '5-15s', count: 47 },
    { range: '15-30s', count: 23 },
    { range: '30-60s', count: 31 },
    { range: '>60s', count: 6 },
  ],
  traces: [
    { trace_id: '6e0600abcdef12', name: 'zhgk.run.run-demo-0007', cost_cny: 0.021, latency_ms: 38100, model: 'glm-4.5', ts: '2026-06-03T09:20:58' },
    { trace_id: '6e0601abcdef12', name: 'zhgk.run.run-demo-0006', cost_cny: 0.019, latency_ms: 37200, model: 'glm-4.5', ts: '2026-06-03T08:14:22' },
    { trace_id: 'a3f2c1deadbe45', name: 'chat.react.read_file',   cost_cny: 0.001, latency_ms: 1400,  model: 'glm-4-flash', ts: '2026-06-03T08:02:11' },
    { trace_id: '6e0602abcdef12', name: 'zhgk.run.run-demo-0005', cost_cny: 0.024, latency_ms: 35800, model: 'glm-4.5', ts: '2026-06-03T07:41:09' },
    { trace_id: 'b8d4e2facec78', name: 'chat.react.send_mail',    cost_cny: 0.002, latency_ms: 2100,  model: 'glm-4-flash', ts: '2026-06-03T07:20:33' },
  ],
};
