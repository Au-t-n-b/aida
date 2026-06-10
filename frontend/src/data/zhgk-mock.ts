/**
 * 智慧工勘 · ZhgkState v1 mock 数据（B 阶段·前端先行）
 *
 * 取自数据中心种子 run-demo-0001，调成"执行中"快照以便面板演示。
 * 后端投影层就绪后（审计 P1 / CONTRACT §4），此 mock 由真实 GET state.json 替换。
 *
 * 遵循 src/data 约定：as const 字面量 + satisfies 结构校验。
 */
import type { ZhgkState } from '../types/zhgk';

export const ZHGK_MOCK = {
  schemaVersion: 'v1',
  skill: 'zhgk',
  projectId: 'K1903',
  runId: 'run-demo-0001',

  status: 'running',
  currentStep: 'report_gen',

  steps: [
    { key: 'scene_filter', name: '场景筛选与底表过滤', status: 'completed', progress: 100 },
    { key: 'survey_build', name: '勘测数据汇总', status: 'completed', progress: 100 },
    { key: 'report_gen', name: '评估与报告生成', status: 'running', progress: 40 },
    { key: 'report_distribute', name: '审批与分发', status: 'pending', progress: 0 },
  ],

  metrics: {
    surveyCompletion: 53.9,
    dataIntegrity: 50.0,
    openIssues: 59,
  },

  charts: {
    donut: {
      centerLabel: '任务完成度',
      centerValue: '50%',
      segments: [
        { label: '已完成', value: 2, color: 'success' },
        { label: '待办', value: 2, color: 'subtle' },
      ],
    },
    bar: [
      { label: '勘测完成度', value: 53.9, color: 'accent' },
      { label: '数据完整率', value: 50.0, color: 'success' },
      { label: '遗留问题数', value: 59, color: 'warning' },
    ],
  },

  /* ⚠ 示意数据：真实 alerts 需 report_gen 补吐结构化风险（审计 B2 / CONTRACT §4.1）。
   * 面板对空数组也有兜底空态，这里填两条仅为展示告警区设计。 */
  alerts: [
    { id: 'RISK-01', level: 'high', category: '供电', room: 'B2 机房', title: 'B2 配电延期 9 天，影响上电窗口', recommendation: '拉通客户确认断电窗口，优先排 A1', source: 'report_gen' },
    { id: 'RISK-02', level: 'medium', category: '承重', room: 'A3 机房', title: 'A3 液冷机柜区楼板承重待复核', recommendation: '补充承重检测报告', source: 'report_gen' },
  ],

  inputs: [
    { name: 'BOQ.xlsx', path: 'input/BOQ.xlsx', kind: 'boq' },
    { name: '入场评估标准表.xlsx', path: 'template/入场评估标准表.xlsx', kind: 'template' },
    { name: '勘测结果.xlsx', path: 'input/勘测结果.xlsx', kind: 'survey' },
    { name: '勘测结果补充材料.xlsx', path: 'input/勘测结果补充材料.xlsx', kind: 'survey' },
  ],

  outputs: [
    { name: '全量勘测结果表.xlsx', path: 'output/全量勘测结果表.xlsx', step: 'survey_build', kind: 'survey' },
    { name: '待客户确认勘测项.xlsx', path: 'output/待客户确认勘测项.xlsx', step: 'survey_build', kind: 'todo' },
    { name: '待拍摄图片项.xlsx', path: 'output/待拍摄图片项.xlsx', step: 'survey_build', kind: 'todo' },
    { name: '待补充勘测项.xlsx', path: 'output/待补充勘测项.xlsx', step: 'survey_build', kind: 'todo' },
  ],

  summary: '已完成场景筛选与勘测汇总，正在生成评估报告。勘测完成度 53.9%，强制项 23/46，遗留 59 项（待客户确认 3 / 待拍摄 28 / 待补充 28）。',

  hitl: null,
} satisfies ZhgkState;
