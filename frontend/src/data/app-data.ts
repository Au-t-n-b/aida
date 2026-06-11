/* AIDA · domain data (mirrors aida-delivery mock data) */

import type {
  AIInsight,
  ChatMessage,
  Milestone,
  Project,
  Risk,
  RiskSources,
  Summary,
} from '../types/domain';

export const SUMMARY = {
  contractPace: { value: 78, total: 100, unit: '%', on: 6, risk: 1, late: 1 },
  activeProjects: { value: 8, group: '智算交付 2026Q2' },
  pods: { total: 36, ready: 22, partial: 10, blocked: 4 },
  rooms: { total: 14, ready: 11, prep: 2, blocked: 1 },
  teams: { total: 12, dispatched: 10, headcount: 184, short: 1 },
  risks: { red: 3, amber: 5 },
  nearestMilestone: { name: 'A1 一期客户移交', days: 12, date: '06-03', status: 'risk' },
} satisfies Summary;

// title uses inline markup: {red:text} {num:text} {amber:text}
export const AI_INSIGHTS = [
  {
    id: 'INS-2026-0512-01',
    severity: 'red',
    ts: '11:42',
    title: '{red:B2 智算中心} 二期配电改造确认延期 {num:9} 天，与 PoD {num:#18 - #23} 上电窗口冲突，预计 B2 移交里程碑顺延 {red:5 ~ 7} 天。',
    evidence: [
      { src: 'Wiki', ref: 'HLD-B2 §4.2 配电规范' },
      { src: 'DORA', ref: '客户机房 · 入场约束链' },
      { src: '案例', ref: 'PJ-2025-014 顺延复盘' },
    ],
    impact: { route: 'B2-RM02 → PoD#18-23 → 上电点亮 → 一期移交', delay: '+5 ~ 7 天' },
    actions: [
      { label: '查看推理链路', kind: 'ghost', icon: 'Eye' },
      { label: '推演到沙箱', kind: 'primary', icon: 'Sandbox' },
      { label: '升级', kind: 'danger' },
    ],
  },
  {
    id: 'INS-2026-0512-02',
    severity: 'amber',
    ts: '10:18',
    title: '{num:A1} 集群 PoD {num:#04} 设备齐套缺 100G 交换机 {num:3} 台，物流 ETA 5/28；可压缩工厂联调 {num:2} 天，关键路径风险可控。',
    evidence: [
      { src: 'DORA', ref: 'BOQ-A1-001 齐套规则' },
      { src: 'Wiki', ref: '100G-SW 物流 SLA' },
    ],
    impact: { route: '供应链 → A1 PoD#04 齐套 → 安装', delay: '可吸收' },
    actions: [
      { label: '查看推理', kind: 'ghost', icon: 'Eye' },
      { label: '排期沙箱', kind: 'primary', icon: 'Sandbox' },
    ],
  },
  {
    id: 'INS-2026-0512-03',
    severity: 'blue',
    ts: '09:05',
    title: '施工队 {num:07} 并行能力饱和，未来 {num:7} 天无法承接新 PoD；建议从 {num:H 项目} 调度 {num:2} 名调试工程师补位。',
    evidence: [
      { src: 'Wiki', ref: '队伍负载 · 历史并行上限' },
      { src: 'DORA', ref: '人员能力矩阵' },
      { src: '工单', ref: 'R-2026-0512' },
    ],
    impact: { route: '施工队 7 → A1/B2 并行实施', delay: '提案' },
    actions: [
      { label: '查看依据', kind: 'ghost', icon: 'Eye' },
      { label: '发起协同', kind: 'primary' },
    ],
  },
  {
    id: 'INS-2026-0512-04',
    severity: 'amber',
    ts: '08:31',
    title: '{num:C3} 项目客户要求提前移交 {num:5} 天，当前关键路径不可压缩，建议触发"提前移交诉求评估"沙箱并拉通客户协调。',
    evidence: [
      { src: '合同', ref: 'C3-移交条款 §6' },
      { src: 'DORA', ref: 'C3 关键路径' },
    ],
    impact: { route: 'C3 客户诉求 → 关键路径', delay: '需协调' },
    actions: [
      { label: '查看依据', kind: 'ghost', icon: 'Eye' },
      { label: '评估沙箱', kind: 'primary', icon: 'Sandbox' },
    ],
  },
] satisfies AIInsight[];

/* 5.27 M-111 · 风险来源 5 大类（用于卡片标签 + 筛选 chip）
 * 客户 / 物流 / 施工 / 设计 / 合规 —— 与会议拍板一致 */
export const RISK_SOURCES = {
  customer: { label: '客户', tone: 'red' },
  logistic: { label: '物流', tone: 'amber' },
  field:    { label: '施工', tone: 'violet' },
  design:   { label: '设计', tone: 'blue' },
  compliance: { label: '合规', tone: 'gray' },
  erp:      { label: 'ERP 评选', tone: 'amber' },
  doc:      { label: '文档不一致', tone: 'red' },
} satisfies RiskSources;

export const RISKS = [
  { cat: 'unmeet', sev: 'red', source: 'customer', title: 'B2-RM02 客户配电改造延期，影响 6 个 PoD 上电', project: 'B2 智算中心', pod: 'PoD #18-23', owner: 'PD 李伟 · 客户侧', delay: '+9 天', sla: 'T-12 通报', age: '2h' },
  { cat: 'unmeet', sev: 'red', source: 'field',    title: 'A1-RM01 ESS 装修验收未通过，需复检', project: 'A1 智算一期', pod: 'PoD #01-04', owner: 'TD 王明', delay: '+5 天', sla: '今日复检', age: '5h' },
  { cat: 'unmeet', sev: 'red', source: 'customer', title: 'D4-RM03 临时配电断电窗口拒批', project: 'D4 算力底座', pod: '测试阶段', owner: 'PD 张悦 · 客户侧', delay: '待审批', sla: 'T-3 升级', age: '1d' },
  { cat: 'atrisk', sev: 'amber', source: 'logistic', title: 'A1 PoD #04 100G 交换机齐套延期，物流 ETA 5/28', project: 'A1 智算一期', pod: 'PoD #04', owner: '供应链 陈光', delay: '+2 天', sla: '可吸收', age: '3h' },
  { cat: 'atrisk', sev: 'amber', source: 'field',    title: 'B2 PoD #19 调试工程师档期冲突', project: 'B2 智算中心', pod: 'PoD #19', owner: 'TD 赵丹', delay: '+1 天', sla: '可调度', age: '4h' },
  { cat: 'atrisk', sev: 'amber', source: 'customer', title: 'E5-RM01 网络接入工单仍在客户侧审批', project: 'E5 智算扩容', pod: 'PoD #28-30', owner: 'PD 周晗 · 客户侧', delay: '+3 天', sla: 'T-5 跟进', age: '1d' },
  { cat: 'atrisk', sev: 'amber', source: 'field',    title: '施工队 07 资源饱和，影响后续 PoD 并行实施', project: '跨项目', pod: '施工队 07', owner: 'PD 总监 何博', delay: '调度中', sla: 'T-7 提案', age: '1d' },
  { cat: 'atrisk', sev: 'amber', source: 'customer', title: 'C3 客户要求提前移交 5 天，关键路径不可压缩', project: 'C3 算力底座扩容', pod: '整体', owner: 'PD 李伟 · 客户侧', delay: '需协调', sla: 'T-2 评估', age: '5h' },
  /* 5.27 M-112 · BOQ 与 HLD 数量冲突自动入风险（设计类） */
  { cat: 'atrisk', sev: 'amber', source: 'design',   title: 'K1903 · ConnectX-7 400G 数量冲突：HLD 写 384 / BOQ 写 192', project: 'K1903 智算 Q3', pod: 'BOQ-K1903-D01 第 47 行', owner: 'TD 何博', delay: '待对齐', sla: 'LLD 出图前', age: '20m' },
  /* 5.27 M-112 · OCC 合规闸门（合规类） */
  { cat: 'atrisk', sev: 'amber', source: 'compliance', title: 'K1903 项目空间含 3 处敏感字段，跨境数据出境待 OCC 审批', project: 'K1903 智算 Q3', pod: '整体', owner: 'OCC 黎芳', delay: '审批中', sla: 'T-1 内', age: '15m' },
  { cat: 'atrisk', sev: 'amber', source: 'erp', title: 'ERP 评选 · 授权方案 SLA 与合同附件不一致', project: 'K1903 智算 Q3', pod: '合同附件 §4', owner: 'PD 李伟', delay: '待对齐', sla: '评审前', age: '1h' },
  { cat: 'unmeet', sev: 'red', source: 'doc', title: 'HLD v1.2 与 BOQ 封面版本号不一致（v1.2 vs v1.0）', project: 'K1903 智算 Q3', pod: '文档包', owner: 'TD 何博', delay: '阻塞出图', sla: '今日', age: '30m' },
] satisfies Risk[];

export const PROJECTS = [
  {
    id: 'A1', name: 'A1 智算集群一期', customer: '客户甲',
    deadline: '2026-07-15', progress: 62, status: 'amber',
    rooms: 3, podCount: 12, pd: '李伟', td: '王明',
    pods: [
      { id: 'P-01', room: 'A1-RM01', stage: '安装', chain: ['a','g','g'], state: 'at-risk' },
      { id: 'P-02', room: 'A1-RM01', stage: '安装', chain: ['a','g','g'], state: 'at-risk' },
      { id: 'P-03', room: 'A1-RM01', stage: '齐套', chain: ['a','g','a'], state: 'at-risk' },
      { id: 'P-04', room: 'A1-RM01', stage: '齐套', chain: ['g','a','g'], state: 'at-risk' },
      { id: 'P-05', room: 'A1-RM02', stage: '上电', chain: ['g','g','g'], state: 'ready' },
      { id: 'P-06', room: 'A1-RM02', stage: '上电', chain: ['g','g','g'], state: 'ready' },
      { id: 'P-07', room: 'A1-RM02', stage: '调试', chain: ['g','g','g'], state: 'ready' },
      { id: 'P-08', room: 'A1-RM02', stage: '调试', chain: ['g','g','g'], state: 'ready' },
      { id: 'P-09', room: 'A1-RM03', stage: '齐套', chain: ['g','g','a'], state: 'at-risk' },
      { id: 'P-10', room: 'A1-RM03', stage: '未到货', chain: ['g','idle','idle'], state: 'ready' },
      { id: 'P-11', room: 'A1-RM03', stage: '未到货', chain: ['g','idle','idle'], state: 'ready' },
      { id: 'P-12', room: 'A1-RM03', stage: '未到货', chain: ['g','idle','idle'], state: 'ready' },
    ],
  },
  {
    id: 'B2', name: 'B2 智算中心', customer: '客户乙',
    deadline: '2026-08-10', progress: 38, status: 'red',
    rooms: 4, podCount: 9, pd: '李伟', td: '赵丹',
    pods: [
      { id: 'P-13', room: 'B2-RM01', stage: '上电', chain: ['g','g','g'], state: 'ready' },
      { id: 'P-14', room: 'B2-RM01', stage: '上电', chain: ['g','g','g'], state: 'ready' },
      { id: 'P-15', room: 'B2-RM01', stage: '调试', chain: ['g','g','a'], state: 'at-risk' },
      { id: 'P-16', room: 'B2-RM02', stage: '等场地', chain: ['r','g','g'], state: 'blocked' },
      { id: 'P-17', room: 'B2-RM02', stage: '等场地', chain: ['r','g','g'], state: 'blocked' },
      { id: 'P-18', room: 'B2-RM02', stage: '等场地', chain: ['r','g','idle'], state: 'blocked' },
      { id: 'P-19', room: 'B2-RM02', stage: '等场地', chain: ['r','g','idle'], state: 'blocked' },
      { id: 'P-20', room: 'B2-RM03', stage: '齐套', chain: ['g','a','idle'], state: 'at-risk' },
      { id: 'P-21', room: 'B2-RM04', stage: '齐套', chain: ['g','a','idle'], state: 'at-risk' },
    ],
  },
  {
    id: 'C3', name: 'C3 算力底座扩容', customer: '客户丙',
    deadline: '2026-06-30', progress: 88, status: 'amber',
    rooms: 2, podCount: 6, pd: '周晗', td: '王明',
    pods: [
      { id: 'P-22', room: 'C3-RM01', stage: '测试', chain: ['g','g','g'], state: 'ready' },
      { id: 'P-23', room: 'C3-RM01', stage: '测试', chain: ['g','g','g'], state: 'ready' },
      { id: 'P-24', room: 'C3-RM01', stage: '测试', chain: ['g','g','g'], state: 'ready' },
      { id: 'P-25', room: 'C3-RM02', stage: '验收', chain: ['g','g','g'], state: 'ready' },
      { id: 'P-26', room: 'C3-RM02', stage: '调试', chain: ['g','g','a'], state: 'at-risk' },
      { id: 'P-27', room: 'C3-RM02', stage: '调试', chain: ['g','g','g'], state: 'ready' },
    ],
  },
  {
    id: 'D4-E5', name: 'D4 算力底座 / E5 智算扩容 等 5 项', customer: '客户丁 等',
    deadline: '2026-09-20', progress: 22, status: 'amber',
    rooms: 5, podCount: 9, pd: '张悦 等', td: '赵丹 等',
    pods: [
      { id: 'P-28', room: 'D4-RM01', stage: '等货', chain: ['g','a','idle'], state: 'at-risk' },
      { id: 'P-29', room: 'D4-RM01', stage: '等货', chain: ['g','a','idle'], state: 'at-risk' },
      { id: 'P-30', room: 'D4-RM03', stage: '等审批', chain: ['a','idle','idle'], state: 'at-risk' },
      { id: 'P-31', room: 'E5-RM01', stage: '等审批', chain: ['a','idle','idle'], state: 'at-risk' },
      { id: 'P-32', room: 'E5-RM01', stage: '等审批', chain: ['a','idle','idle'], state: 'at-risk' },
      { id: 'P-33', room: 'E5-RM02', stage: '未启动', chain: ['idle','idle','idle'], state: 'ready' },
      { id: 'P-34', room: 'F6-RM01', stage: '未启动', chain: ['idle','idle','idle'], state: 'ready' },
      { id: 'P-35', room: 'G7-RM01', stage: '未启动', chain: ['idle','idle','idle'], state: 'ready' },
      { id: 'P-36', room: 'H8-RM01', stage: '未启动', chain: ['idle','idle','idle'], state: 'ready' },
    ],
  },
] satisfies Project[];

export const MILESTONES = [
  { date: '05-28', days: 'T-6',  title: 'D4 设备到货齐套',       project: 'D4', status: 'risk', label: 'RISK' },
  { date: '06-03', days: 'T-12', title: 'A1 一期 PoD 安装完成',  project: 'A1', status: 'ok',   label: 'ON TRACK' },
  { date: '06-15', days: 'T-24', title: 'B2 二期上电点亮',        project: 'B2', status: 'late', label: 'DELAYED' },
  { date: '07-15', days: 'T-54', title: 'A1 一期客户移交',        project: 'A1', status: 'ok',   label: 'ON TRACK' },
  { date: '08-10', days: 'T-80', title: 'B2 整体验收',            project: 'B2', status: 'risk', label: 'RISK' },
] satisfies Milestone[];

export const CLAW_SEED = [
  {
    role: 'ai',
    body: '早上 9 点已自动扫盘。发现 3 条不可满足风险与 5 条待协调项，其中 B2 配电延期 会传导至 A1 移交里程碑，已置顶。',
    reasoning: [
      { ix: '1', text: 'BG-Survey: 14 机房 · 36 PoD · 12 队伍 · 184 人' },
      { ix: '2', text: 'Match: B2-RM02 配电 → PoD#18-23 入场依赖' },
      { ix: '3', text: 'Trace: 上电窗口 → A1 联调资源 → 移交里程碑' },
    ],
    chips: ['交付盘子 · 智算 Q2', 'B2 配电延期', 'A1 移交里程碑'],
    actions: [
      { label: '看 B2 推理链', kind: 'primary', icon: 'Eye' },
      { label: '全部研判', kind: 'ghost' },
    ],
    ts: '09:05',
  },
  {
    role: 'user',
    body: '如果 B2 配电真的延期 9 天，A1 这边来得及兜底吗？',
    ts: '09:08',
  },
  {
    role: 'ai',
    body: '已在沙箱推演两版方案，对照原计划基线：A1 关键路径 与 施工队 7 负载 是两个关键变量。方案 B 把 PoD#01-04 安装压缩 2 天 + 调度 H 项目 2 人补位，可吸收 5 / 7 天延期。',
    reasoning: [
      { ix: '1', text: 'Sandbox-α: 顺延 5d，移交保住 — 风险概率 78%' },
      { ix: '2', text: 'Sandbox-β: 顺延 7d，移交保住 — 风险概率 54%' },
      { ix: '3', text: '推荐 α，需 H 项目调度 2 名工程师 (5/26-6/04)' },
    ],
    chips: ['A1 关键路径', '施工队 7 负载'],
    actions: [
      { label: '看沙箱对照', kind: 'primary', icon: 'Sandbox' },
      { label: '导出汇报片', kind: 'ghost', icon: 'Doc' },
    ],
    ts: '09:09',
  },
] satisfies ChatMessage[];

export const CLAW_SUGGESTS = [
  '今天哪些 PoD 卡住了？',
  'B2 延期会影响哪些合同节点？',
  '把当前风险按客户分组',
  '调整施工队 07 负载如何改善？',
];
