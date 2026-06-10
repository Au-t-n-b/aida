/* 项目孪生 · 下发追踪数据（K1903 智算 Q3）
 *
 * 来源：第③幕「可交付性研判 #DLV-01」产出的风险与任务，经 WeLink 下发到人，
 *       在项目孪生 /cockpit 里追踪闭环。数据对齐：
 *   - contract-data.ts  ConnectX-7 数量冲突（HLD 384 / BOQ 192）
 *   - app-data.ts       RISKS（5 大来源）+ HLD/BOQ 版本号不一致
 *   - journey-data.ts   沙箱「关键前置动作」（拉通客户乙 / 调度 H 项目 / 100G 优先发 A1）
 *
 * 真实场景里这些由「可交付性研判 Skill + 沙箱推演」产出，本地 mock 给演示用。
 * 遵循 app-data.ts 模式：satisfies 校验（靠上下文类型保留字面量），不写 as const。
 */

import type { DispatchItem, DispatchRun } from '../types/domain';

/* 本次下发批次元数据 */
export const DISPATCH_RUN = {
  id: 'DLV-01',
  title: '可交付性研判',
  proposalVersion: 'DRB v1.0',
  dispatchedAt: '2026-05-30 10:18',
} satisfies DispatchRun;

/* 8 项下发（3 风险 / 5 任务）· 覆盖 4 人 · 状态铺满闭环板各泳道 */
export const DISPATCH_ITEMS = [
  /* ── 风险（3）── */
  {
    id: 'R-D01',
    kind: 'risk',
    title: 'ConnectX-7 400G 数量冲突：HLD 写 384 / BOQ 写 192',
    status: 'in-progress',
    owner: { name: '何博', role: 'TD', avatar: 'HE' },
    dispatchedAt: '05-30 10:18',
    channel: 'WeLink',
    sla: 'LLD 出图前',
    due: 'T-2',
    source: { deliverability: 'DLV-01', risk: 'R-D01', proposalRef: '预案 §3 设备清单 · BOQ-K1903-D01 L47' },
    impact: { route: 'BOQ 对齐缺口 → 阻塞 LLD 出图 → 关键路径', drift: '设计基线未冻结' },
    acks: [
      { ts: '10:20', actor: '何博 · TD', note: '已接收，正在与 PD 核对采购口径' },
    ],
  },
  {
    id: 'R-DOC1',
    kind: 'risk',
    title: 'HLD v1.2 与 BOQ 封面版本号不一致（v1.2 vs v1.0）',
    status: 'pending-ack',
    owner: { name: '何博', role: 'TD', avatar: 'HE' },
    dispatchedAt: '05-30 10:18',
    channel: 'WeLink',
    sla: '今日',
    due: 'T-0',
    source: { deliverability: 'DLV-01', risk: 'R-DOC1', proposalRef: '文档包 · 封面元数据' },
    impact: { route: '文档版本错位 → 阻塞出图评审', drift: '章节齐备度卡在 94%' },
  },
  {
    id: 'R-C01',
    kind: 'risk',
    title: 'B2-RM02 客户配电改造延期 9 天，6 个 PoD 无法上电',
    status: 'acked',
    owner: { name: '李伟', role: 'PD', avatar: 'LW' },
    dispatchedAt: '05-30 10:18',
    channel: 'WeLink',
    sla: 'T-12 通报',
    due: 'T-12',
    source: { deliverability: 'DLV-01', risk: 'R-C01', proposalRef: '预案 §5 机房物理布局' },
    impact: { route: 'B2-RM02 配电 → PoD#18-23 上电 → 一期移交', drift: '里程碑顺延 5~7 天', room: 'B2-RM02', pod: 'PoD#18-23' },
    acks: [
      { ts: '10:25', actor: '李伟 · PD', note: '已接收，今日拉通客户乙' },
    ],
  },

  /* ── 任务（5）── */
  {
    id: 'T-01',
    kind: 'task',
    title: 'ConnectX-7 数量对齐到 192 台（按 BOQ 口径）',
    status: 'overdue',
    parentRiskId: 'R-D01',
    owner: { name: '何博', role: 'TD', avatar: 'HE' },
    dispatchedAt: '05-29 16:40',
    channel: 'WeLink',
    sla: 'LLD 出图前',
    due: 'T-2',
    overdueBy: '6h',
    source: { deliverability: 'DLV-01', risk: 'R-D01', proposalRef: '预案 §3 设备清单' },
    impact: { route: 'BOQ 对齐 → 解锁 §3 章节齐备 → LLD 出图', drift: '阻塞可执行合同冻结' },
    acks: [
      { ts: '05-29 16:42', actor: 'AIDA', note: '已下发（WeLink）' },
      { ts: '05-30 09:10', actor: 'AIDA', note: '临近 SLA 自动提醒' },
    ],
  },
  {
    id: 'T-02',
    kind: 'task',
    title: '§5 CAD 桥架路由补全 / 手填机柜归位',
    status: 'in-progress',
    owner: { name: '王明', role: 'TD', avatar: 'WM' },
    dispatchedAt: '05-30 10:18',
    channel: 'WeLink',
    sla: 'DRB 评审前',
    due: 'T-1',
    source: { deliverability: 'DLV-01', proposalRef: '预案 §5 机房物理布局' },
    impact: { route: 'CAD 解析降级 → 机柜归位补全 → §5 齐备', drift: '机房物理章节缺口', room: 'A1-RM01' },
    acks: [
      { ts: '10:30', actor: '王明 · TD', note: '已接收，CAD 坐标手工补录中' },
    ],
  },
  {
    id: 'T-03',
    kind: 'task',
    title: '拉通客户乙 · 通报 B2 顺延 5 天（合同 §6.3 安全区）',
    status: 'in-progress',
    parentRiskId: 'R-C01',
    owner: { name: '李伟', role: 'PD', avatar: 'LW' },
    dispatchedAt: '05-30 10:18',
    channel: 'WeLink',
    sla: 'T-2',
    due: 'T-2',
    source: { deliverability: 'DLV-01', risk: 'R-C01', proposalRef: '合同 §6.3 顺延条款' },
    impact: { route: '客户沟通 → 顺延获认可 → 保住 B2 验收', drift: '回归 should-be 基线', room: 'B2-RM02' },
    acks: [
      { ts: '10:26', actor: '李伟 · PD', note: '已接收' },
      { ts: '11:05', actor: '李伟 · PD', note: '已发客户乙，待回复' },
    ],
  },
  {
    id: 'T-04',
    kind: 'task',
    title: '从 H 项目调度 2 名调试工程师补位（5/26-6/04）',
    status: 'acked',
    parentRiskId: 'R-C01',
    owner: { name: '李伟', role: 'PD', avatar: 'LW' },
    dispatchedAt: '05-30 10:18',
    channel: 'WeLink',
    sla: 'T-3',
    due: 'T-3',
    source: { deliverability: 'DLV-01', risk: 'R-C01', proposalRef: '沙箱方案 α · 资源补位' },
    impact: { route: '跨项目调度 → A1 联调补位 → 吸收顺延', drift: '施工队 07 饱和缓解' },
    acks: [
      { ts: '10:40', actor: '李伟 · PD', note: '已接收，联系 H 项目 PD' },
    ],
  },
  {
    id: 'T-05',
    kind: 'task',
    title: '供应链：100G-SW 优先发往 A1 PoD#04',
    status: 'done',
    owner: { name: '陈光', role: '供应链', avatar: 'CG' },
    dispatchedAt: '05-29 14:00',
    channel: 'WeLink',
    sla: 'T-1',
    due: 'T-1',
    source: { deliverability: 'DLV-01', proposalRef: '沙箱方案 α · 供应优先级' },
    impact: { route: '物流提前 → A1 PoD#04 齐套 → 安装', drift: '齐套缺口闭合', room: 'A1-RM01', pod: 'PoD#04' },
    acks: [
      { ts: '05-29 14:10', actor: '陈光 · 供应链', note: '已接收' },
      { ts: '05-30 08:30', actor: '陈光 · 供应链', note: '已改单，ETA 5/28 → 优先批次' },
      { ts: '05-30 09:15', actor: '陈光 · 供应链', note: '已完成，3 台已发运' },
    ],
  },
] satisfies DispatchItem[];
