/* /landing · 项目选择落地页数据
 *
 * 5.27 早会决策（推翻 5.25 老字段）：
 *   ❌ 去掉 customer / progress / nextMs / 里程碑 / 交付金额
 *   ✅ 卡片只显示：项目名称 + 编码 + 多角色 chip + 4 段阶段 + 任务数 + 超期状态
 *   ✅ 一个项目可有多个角色（TD + TL + PCM 并列，不互斥）
 *   ✅ 编辑按钮在右上角，但仅 PD / PCM 可见
 *
 * 现 schema：
 *   roles: ['TD', 'TL', ...]        — 数组，多角色并列
 *   stage4: 'survey'|'modeling'|'install'|'deploy'  — 5.27 拍板的 4 段命名
 *   stage4Label: 中文标签
 *   todoCount: 数字
 *   overdueCount: 数字  — 超期任务数（替代旧 progress）
 *   canEdit: 当前用户是否能编辑（PD/PCM=true，TL=false）
 */

export const LANDING_USER = {
  account: 'he.bo@huawei.com',
  staffId: '01234567',
  name: '何博',
  title: '交付总监 · 华南区',
  avatar: 'HE',
  loginTs: '2026-05-27 09:01:22',
  newQuota: { used: 2, total: 5, label: '本季新建额度' },
};

/* 4 段阶段映射（5.27 拍板）*/
export const STAGE4_LABELS = {
  survey: '智慧工勘',
  modeling: '规划设计',
  install: '设备安装',
  deploy: '部署调测',
};

/* 进行中：每个项目支持多角色并列展示 */
export const LANDING_ACTIVE = [
  {
    id: 'K1903',
    name: '京东三期',
    code: 'PROP-2026-K1903',
    roles: ['TD', 'PCM'],      // 多角色并列
    stage4: 'install',
    todoCount: 5,
    overdueCount: 2,
    blocker: 'B2-RM02 配电延期 9d',
    canEdit: true,             // PD/PCM 可编辑
    updated: '12 min ago',
  },
  {
    id: 'A1',
    name: 'A1 智算集群一期',
    code: 'PROP-2026-A1-002',
    roles: ['TD', 'TL'],
    stage4: 'modeling',
    todoCount: 3,
    overdueCount: 0,
    blocker: 'PoD #04 100G 物流 ETA 5/28',
    canEdit: true,
    updated: '1h ago',
  },
  {
    id: 'C3',
    name: 'C3 算力底座扩容',
    code: 'PROP-2026-C3-007',
    roles: ['TL'],
    stage4: 'deploy',
    todoCount: 1,
    overdueCount: 0,
    blocker: null,
    canEdit: false,            // TL 不可编辑
    updated: '昨日',
  },
];

/* 历史 / 已归档项目 */
export const LANDING_ARCHIVED = [
  {
    id: 'L7',
    name: 'L7 通信枢纽（已交付）',
    code: 'PROP-2025-L7-091',
    roles: ['TL'],
    stage4: 'deploy',
    todoCount: 0,
    overdueCount: 0,
    canEdit: false,
    handover: '2026-03-18',
    summary: '提前 5 天移交，客户满意度 4.8 / 5.0',
  },
  {
    id: 'PJ-2025-014',
    name: '2025 西北骨干网',
    code: 'PROP-2025-014',
    roles: ['TD'],
    stage4: 'deploy',
    todoCount: 0,
    overdueCount: 0,
    canEdit: false,
    handover: '2025-12-04',
    summary: '复盘已并入 Wiki · 顺延 5d 闭环案例',
  },
];

/* 本季概览 */
export const LANDING_STATS = [
  { k: '我的项目', v: 3, sub: '进行中' },
  { k: '历史项目', v: 2, sub: '已归档' },
  { k: '本季新建', v: '2/5', sub: '余 3 个额度' },
  { k: '今日待办', v: 9, sub: '今日 3 紧急' },
];

/* 创建项目卡片的引导话术 */
export const LANDING_CREATE_HINT = {
  headline: '新建项目',
  body: '关联 Proposal ID 后，AIDA 会自动拉取机会点、合同、BOQ 等上下游数据；只需补 5 项基本字段即可建立项目空间。',
  steps: ['关联 Proposal', 'OCC 数据出境审批', '上传公勘/HLD/BOQ/CAD', '生成 DTRB → DRB → LLD'],
};
