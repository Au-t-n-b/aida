/* 评测中心指标说明 · 与 aida/agent/evals/METRICS.md 对齐 */

export type EvalView = 'common' | 'skill' | 'tools' | 'obs';

export interface MetricDef {
  /** 界面上的指标名 */
  label: string;
  /** 一句话含义 */
  meaning: string;
  /** 计算方法 / 数据源 */
  formula: string;
  /** 如何解读（绿/红、优化方向） */
  interpret?: string;
}

/** 四维总览（SKILL tab 顶部 KPI） */
export const SKILL_FOUR_DIM: MetricDef[] = [
  {
    label: '质量得分',
    meaning: '本次 run 的 golden 断言通过率，反映产物与关键 step 是否「没塌方」。',
    formula: 'quality_score = 通过断言数 / 断言总数。断言来自 eval_zhgk.py 读 Output/skill_result.json，与 CONTRACT 样例基线对比。',
    interpret: '≥90% 为健康；下降优先看下方「断言详情」哪条失败（completion / mandatory / open_issues / step 完成）。',
  },
  {
    label: '成功率',
    meaning: '本次评测是否全部断言通过（单次布尔）；总体视图为历史 run 的通过占比。',
    formula: '单次：success = 所有 checks.pass 为 true。总体：success_count / total（历次 eval 结果 JSON）。',
    interpret: '失败表示至少一条 golden 或关键 step 未达标，需结合产物与 Langfuse trace 排查。',
  },
  {
    label: '延迟',
    meaning: '端到端一次 Skill run 的 wall-clock 时间（含各 step 与 LLM）。',
    formula: 'latency_ms = Langfuse trace.latency（秒×1000），按 run_id 标签对齐；无 trace 时显示 —。',
    interpret: '突增 >20% 相对基线会进入「偏离 JSON」；step 耗时柱图可定位瓶颈 step。',
  },
  {
    label: '成本',
    meaning: '单次 run 的 LLM 费用合计（人民币）。',
    formula: 'cost_cny = Langfuse trace.total_cost（GENERATION 汇总）；与质量/成功率写回同一 trace 的 score。',
    interpret: '按 step/kind 在 Langfuse 细拆；贵 step 考虑减 prompt、缓存、换小模型。',
  },
];

/** 产物指标（skill_result.json → metrics 表） */
export const PRODUCT_METRICS: Record<string, MetricDef> = {
  completion_rate: {
    label: 'completion_rate',
    meaning: '勘测完成度（业务完成百分比）。',
    formula: '来自 skill_result.survey.completion_rate（各评估项汇总）。',
    interpret: '断言：≥ 45（基线来自样例 run-demo-0001）。低于基线表示大面积未填/未评估。',
  },
  mandatory_fill_rate: {
    label: 'mandatory_fill_rate',
    meaning: '强制评估项的填充率。',
    formula: 'mandatory_filled / mandatory_total（survey 段）。',
    interpret: '断言：≥ 0.40。低表示必填项缺口大，常伴随 HITL 或前置数据不全。',
  },
  open_issues: {
    label: 'open_issues',
    meaning: '待办/未闭合问题条数合计。',
    formula: 'sum(empty_by_type 各类型计数)。',
    interpret: '断言：≤ 80。过高表示遗留 open 项堆积，需看「待办构成」环图分型。',
  },
  steps_completed: {
    label: 'steps_completed',
    meaning: '已标记 completed 的 step 数量。',
    formula: 'count(execution.steps where status=completed)。',
    interpret: '与 steps_total 对比；漏斗图看各 step 留存。',
  },
  steps_total: {
    label: 'steps_total',
    meaning: 'Skill 定义的 step 总数。',
    formula: 'len(execution.steps)。',
    interpret: 'zhgk 为 4～5 个业务 step（含 distribute 等）。',
  },
};

/** 图表 / 面板 */
export const SKILL_CHARTS: Record<string, MetricDef> = {
  funnel: {
    label: '流程漏斗',
    meaning: '各 step 在历次 run 中处于 completed 的次数。',
    formula: '对每个 step key：count(runs where step_status[key]=completed)。',
    interpret: '条形应逐级递减；某 step 骤降表示流程在该步大量中断（含 HITL）。',
  },
  step_duration: {
    label: 'step 耗时拆解',
    meaning: '每次 run 各 step 耗时（秒），堆叠柱对比。',
    formula: 'step_durations[key]：优先产物 duration_ms，评测时从 Langfuse CHAIN span 补齐。',
    interpret: '最高的 step 即优化瓶颈（报告生成、大 prompt 等）。',
  },
  empty_donut: {
    label: '待办项构成',
    meaning: '最近一次 run 的 open 项按类型分布。',
    formula: 'skill_result.survey.empty_by_type → 环图各扇区。',
    interpret: '看哪类待办占比高，指导补数据或改评估规则。',
  },
};

export const TOOL_METRICS: MetricDef[] = [
  {
    label: '自纠率 ⭐',
    meaning: '模型调用工具后失败（需重试）的比例，衡量 description/JSON Schema 是否清晰。',
    formula: 'self_correction_rate = errors / calls。error：output 以 "Error" 开头或 ok=false（validate 失败/执行异常）。',
    interpret: '界面阈值 15%（展示用）；CI 基线 ≤30%。高 → 优先改该工具的 description 与 parameters。',
  },
  {
    label: '成功率',
    meaning: '工具 execute 一次成功的比例。',
    formula: 'success_rate = (calls - errors) / calls = 1 - 自纠率（按工具聚合）。',
    interpret: 'CI 基线 ≥70%；与自纠率同向，低表示工具不稳或环境缺依赖。',
  },
  {
    label: '延迟 p50 / p95',
    meaning: '工具执行耗时的中位数与 95 分位。',
    formula: '对每条记录的 latency_ms 做线性插值百分位（eval_tools._pctl）。',
    interpret: 'CI：p95 ≤ 5000ms。高延迟工具考虑缓存、减 IO、异步化。',
  },
  {
    label: '调用热度',
    meaning: '工具被调用次数，用于排优化优先级。',
    formula: 'calls = 时间窗内该工具记录条数；散点图 X 轴。',
    interpret: '右上角（高热×高自纠）= 优先打磨；样本 <3 次不下结论（基线断言跳过）。',
  },
  {
    label: '评测质量（工具 tab）',
    meaning: '工具基线断言通过率（非业务产物质量）。',
    formula: 'quality_score = 通过 checks 数 / checks 总数（每工具：自纠率/成功率/p95 三条，样本不足仅「样本量」）。',
    interpret: '与 SKILL 质量得分同名不同义：此处评的是工具契约健康度。',
  },
  {
    label: '需优化工具',
    meaning: '自纠率超过展示阈值（15%）的工具个数。',
    formula: 'count(tools where self_correct_rate > 0.15)。',
    interpret: '点击「导出待优化工具」可生成给 Cursor 的 JSON。',
  },
];

export const OBS_METRICS: MetricDef[] = [
  {
    label: '本月成本 / 成本趋势',
    meaning: 'Langfuse 按天、按模型汇总的 LLM 费用（演示 tab 为 mock）。',
    formula: 'trace GENERATION 的 cost 按 date × model 聚合。',
    interpret: '生产环境接 Langfuse API 后与 SKILL 单次 cost 交叉验证。',
  },
  {
    label: '总 Token',
    meaning: 'input + output token 消耗量。',
    formula: 'Langfuse observation 的 usage 字段按日汇总。',
    interpret: 'output 突增常对应长报告或重复生成。',
  },
  {
    label: '总 run',
    meaning: '统计窗内的 Skill/会话 trace 条数。',
    formula: 'trace 计数（按 tag skill:* 等过滤）。',
    interpret: '与评测次数不一定 1:1（未跑 eval 的 run 不会出现断言）。',
  },
  {
    label: '平均延迟',
    meaning: 'trace 级延迟的算术平均。',
    formula: 'avg(trace.latency)。',
    interpret: '直方图看长尾；p95 比均值更能反映用户体感。',
  },
];

export const COMMON_HELP: MetricDef[] = [
  {
    label: '本次执行 vs 总体情况',
    meaning: 'latest 只看最近一次 eval 落盘结果；overview 看趋势、漏斗与历次表。',
    formula: 'GET /agent/evals/report?mode=latest|overview；工具同理 tools/report。',
    interpret: '工勘 done 或会话调工具后会自动 refresh；也可手动「跑评测」。',
  },
  {
    label: '实时数据 vs 演示数据',
    meaning: '能否连上 Agent(7401) 且存在 evals/results 或 Langfuse 数据。',
    formula: 'report.source=live 为绿点；否则回退 mock 样例。',
    interpret: '演示数据仅用于 UI 走查，数值不可用于回归判断。',
  },
  {
    label: '跑评测',
    meaning: '主动触发 eval_zhgk + eval_tools 写结果 JSON，再刷新图表。',
    formula: 'POST /agent/evals/refresh?live=1（可带 conv_id）；本地 npm run eval 为 CI 离线 fixture。',
    interpret: 'CI 用 fixture 保证无 Langfuse 也能过闸；日常以 live 为准。',
  },
];

export function getProductMetricHelp(key: string): MetricDef | undefined {
  return PRODUCT_METRICS[key];
}

export function metricsForView(view: EvalView): MetricDef[] {
  switch (view) {
    case 'skill': return [...SKILL_FOUR_DIM, ...Object.values(SKILL_CHARTS)];
    case 'tools': return TOOL_METRICS;
    case 'obs': return OBS_METRICS;
    default: return COMMON_HELP;
  }
}
