/* ClawRail · 按模块隔离的对话种子 (G-8)
 *
 * 5.27 早会拍板：每个模块都有自己的「上下文」 —— 切换页面时
 * 助手的开场白与建议提问应该对齐当前页面的语境，而不是一直
 * 复读交付态势的风险总览。
 *
 * 路径匹配规则：用 pathname.includes(prefix) 命中，未命中回落到
 * '/cockpit'（默认 = 整体态势）。
 */

const ts = (h: number, m: number) => `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;

/* ───────────── 各模块的对话种子 ───────────── */

const SEED_COCKPIT = [
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
    ts: ts(9, 5),
  },
  {
    role: 'user',
    body: '如果 B2 配电真的延期 9 天，A1 这边来得及兜底吗？',
    ts: ts(9, 8),
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
    ts: ts(9, 9),
  },
];

/* /proposal · 交付预案三快照 */
const SEED_PROPOSAL = [
  {
    role: 'ai',
    body: '当前 K1903 预案 · 已生成 DTRB v1.0（完整度 78%）。第 5 章机房物理 2 处缺失，等你补完后即可推进 DRB。',
    reasoning: [
      { ix: '1', text: '主区右上「版本号 ▽」可切 DTRB / DRB / 合同 LLD 三快照' },
      { ix: '2', text: '5 子 tab：算力底座 / 智算部件 / 软件配置 / 网络平面 / 服务配置' },
      { ix: '3', text: '会话框「已有 4 / 8 文档」见左侧上传卡' },
    ],
    chips: ['DTRB v1.0', '机房物理待补'],
    actions: [
      { label: '看缺失章节', kind: 'primary', icon: 'Eye' },
    ],
    ts: '10:42',
  },
  {
    role: 'user',
    body: '为什么 ConnectX-7 那条 PBI 还在「待 PD 确认」？',
    ts: '10:43',
  },
  {
    role: 'ai',
    body: 'BOQ 写 192，HLD 写 384 — 客户特殊采购未对齐。建议下午评审会让 PD 一口拍板，否则 LLD 出图会卡。',
    chips: ['ConnectX-7 冲突'],
    ts: '10:43',
  },
];

const SEED_PREVIEW = [
  {
    role: 'ai',
    body: '当前项目 K1903 已识别 3 份合同 · 6 份 BOQ。你勾选哪几个 BOQ，我就解析哪几个 —— 默认全选。设备类走部件清单，服务类按 5 大类分组。',
    reasoning: [
      { ix: '1', text: 'Match: 项目编码 K1903 → 3 个月内未交付完合同 3 条' },
      { ix: '2', text: 'Aggregate: 4 设备 BOQ + 2 服务 BOQ + 1 维保 BOQ' },
      { ix: '3', text: '关键部件：CPU / GPU / Mem / PCIe（其余暂不展示）' },
    ],
    ts: ts(10, 12),
  },
  {
    role: 'user',
    body: '为什么 ConnectX-7 那行有冲突说明？',
    ts: ts(10, 14),
  },
  {
    role: 'ai',
    body: 'HLD 写 384、BOQ 写 192 —— 这是客户特殊采购的项，BOQ 是基线，但 HLD 由设计补录。我已经标记 "待确认"，建议在 LLD 出图前与 PD 对齐数量。',
    reasoning: [
      { ix: '1', text: 'Source: BOQ-K1903-D01 第 47 行 (qty=192)' },
      { ix: '2', text: 'Source: HLD §3.2.1 网络架构图 (qty=384)' },
      { ix: '3', text: 'Risk: 若以 BOQ 为准，万兆汇聚带宽不足' },
    ],
    chips: ['BOQ vs HLD 冲突', '客户特殊采购'],
    actions: [
      { label: '查看推理链', kind: 'primary', icon: 'Eye' },
      { label: '提交客户确认', kind: 'ghost' },
    ],
    ts: ts(10, 15),
  },
];

const SEED_PLAN = [
  {
    role: 'ai',
    body: '已根据 BOQ + 服务清单生成排期初稿，覆盖 4 阶段（智慧工勘 / 规划设计 / 设备安装 / 部署调测）。关键路径在 设备安装 → 部署调测 之间，预留 2 天 buffer。',
    reasoning: [
      { ix: '1', text: 'Input: 47 设备 + 9 服务项 + 客户移交日期' },
      { ix: '2', text: 'Constraint: B2 配电延期 9 天 → 影响 PoD#18-23' },
      { ix: '3', text: 'Optimize: 设备安装并行度从 3 降到 2，避免施工队冲突' },
    ],
    chips: ['关键路径', '设备安装阶段'],
    actions: [
      { label: '查看甘特图', kind: 'primary', icon: 'Eye' },
      { label: '推演到沙箱', kind: 'ghost', icon: 'Sandbox' },
    ],
    ts: ts(11, 30),
  },
];

const SEED_SANDBOX = [
  {
    role: 'ai',
    body: '沙箱模式 · 当前对照 2 个版本：α (压缩安装 2 天) vs β (调度 2 人补位)。指标对比已就绪 —— 移交成功率、客户满意度、单位成本 三个轴。',
    reasoning: [
      { ix: '1', text: '基线：原计划 v3.2，无干预' },
      { ix: '2', text: 'α：PoD#01-04 安装压缩 2 天，需 TD 确认风险' },
      { ix: '3', text: 'β：从 H 项目调 2 名调试工程师，5/26-6/04' },
    ],
    chips: ['沙箱 · 推演中'],
    actions: [
      { label: '对比指标', kind: 'primary', icon: 'Eye' },
      { label: '采纳 α', kind: 'ghost' },
    ],
    ts: ts(14, 8),
  },
];

const SEED_JOURNEY = [
  {
    role: 'ai',
    body: '交付旅程已展开 · 你正在看 A1 智算一期 的 36 个里程碑事件。当前停在 设备安装 阶段，PoD#04 因齐套延期处于"待物流"。',
    reasoning: [
      { ix: '1', text: '阶段进度：智慧工勘 ✓ / 规划设计 ✓ / 设备安装 进行中 / 部署调测 待启动' },
      { ix: '2', text: '阻塞点：100G 交换机 3 台，ETA 5/28' },
    ],
    chips: ['A1 设备安装阶段'],
    ts: ts(15, 22),
  },
];

const SEED_CREATE = [
  {
    role: 'ai',
    body: '新建项目模式 · 我会根据你填的字段自动拉对应的容器（不同 PD/TD 配置对应不同沙箱镜像）。如果只填了机会点编码，我可以反查关联的合同与 BOQ。',
    reasoning: [
      { ix: '1', text: '强制字段：项目名称 · PD · TD' },
      { ix: '2', text: '二选一：机会点编码 / 提议方案编号' },
      { ix: '3', text: '容器拉起后会自动开始 BOQ 解析' },
    ],
    chips: ['项目创建 · 字段校验'],
    ts: ts(9, 30),
  },
];

const SEED_DESIGN = [
  {
    role: 'ai',
    body: 'LLD 设计模式 · 已加载 BOQ 解析结果 + 客户机房约束。当前页面会用到部件清单的冲突项 (ConnectX-7 数量)，请先在 设备清单 Tab 里确认数量再落图。',
    reasoning: [
      { ix: '1', text: '依赖：BOQ-K1903-D01 已发布' },
      { ix: '2', text: '冲突待解：1 项 (ConnectX-7)' },
    ],
    chips: ['LLD 输出', '设备清单冲突'],
    actions: [
      { label: '回到设备清单', kind: 'primary', icon: 'Eye' },
    ],
    ts: ts(11, 5),
  },
];

const SEED_ADMIN = [
  {
    role: 'ai',
    body: '管理模式 · 当前账号是 PD 角色。可见配置：项目可见性 · 角色矩阵 · 数据接口源（陈卓 BOQ 接口 / DORA / Wiki）。',
    reasoning: [
      { ix: '1', text: '权限：可读 / 可编辑（本项目）' },
      { ix: '2', text: '审计：所有修改写入 audit log（保留 7 年）' },
    ],
    chips: ['权限管理'],
    ts: ts(8, 50),
  },
];

const SEED_ASSETS = [
  {
    role: 'ai',
    body: '交付作业 · 资产视图。所有 BOQ / HLD / LLD / 验收单都在这里，按 项目管理类 / 工勘类 / 其他作业类 三个 Tab 分。',
    reasoning: [
      { ix: '1', text: '总文件数：184' },
      { ix: '2', text: '近 7 天新增：12 份' },
    ],
    chips: ['资产库'],
    ts: ts(8, 30),
  },
];

// /module 路由：右侧有 SkillAgentScreen 专门处理，左侧无需 mock 开场白
const SEED_MODULE: never[] = [];

/* ───────────── 路由 → 种子映射 ───────────── */

export const CLAW_SEED_BY_ROUTE = {
  '/cockpit':  SEED_COCKPIT,
  '/preview':  SEED_PREVIEW,
  '/proposal': SEED_PROPOSAL,
  '/plan':     SEED_PLAN,
  '/sandbox':  SEED_SANDBOX,
  '/journey':  SEED_JOURNEY,
  '/create':   SEED_CREATE,
  '/design':   SEED_DESIGN,
  '/admin':    SEED_ADMIN,
  '/assets':   SEED_ASSETS,
  '/module':   SEED_MODULE,
};

/* ───────────── 各模块的建议提问 ───────────── */

export const CLAW_SUGGESTS_BY_ROUTE = {
  '/cockpit': [
    '今天哪些 PoD 卡住了？',
    'B2 延期会影响哪些合同节点？',
    '把当前风险按客户分组',
    '调整施工队 07 负载如何改善？',
  ],
  '/preview': [
    '为什么 ConnectX-7 数量有冲突？',
    '只解析设备 BOQ，跳过服务',
    '把 4 部件汇总成 BOM 表',
    '服务清单按金额排序',
  ],
  '/proposal': [
    'DTRB 章节齐备度多少？',
    '把 PBI 按优先级排',
    '导出预案 PPT 给客户',
    '推到 DRB 评审',
  ],
  '/plan': [
    '关键路径上有几个里程碑？',
    '安装阶段能否再压缩 2 天？',
    '导出甘特图给客户',
    '把排期推演到沙箱',
  ],
  '/sandbox': [
    '比较 α 和 β 哪个更稳？',
    '加一个 γ：从 G 项目调人',
    '采纳 α，自动同步到正式计划',
    '导出对比给业务汇报',
  ],
  '/journey': [
    '为什么 PoD#04 停在齐套？',
    '回放 设备安装 阶段',
    '跳到下一个里程碑',
    '这条旅程的关键事件有哪些？',
  ],
  '/create': [
    '机会点编码格式是什么？',
    '只填项目名能创建吗？',
    '容器拉起需要多久？',
    '能跳过 BOQ 解析吗？',
  ],
  '/design': [
    '设备清单冲突怎么处理？',
    '生成 LLD 模板',
    '同步给 TD 评审',
    '导出 PDF',
  ],
  '/admin': [
    '当前账号能改谁的项目？',
    '查看最近的审计日志',
    '接口源切换会影响哪些数据？',
    '导出权限矩阵',
  ],
  '/assets': [
    '哪些文件是本周新增的？',
    '按项目维度筛选',
    '只看工勘类作业',
    '搜索 K1903 相关文件',
  ],
  '/module': [
    '当前模块的输入是什么？',
    '上一步的输出在哪？',
    '同步到主任务',
    '退回工作台',
  ],
};

/* ───────────── 工具函数 ───────────── */

/** 从 pathname 取对应的 seed 对话；未命中回落到 /cockpit */
export function getSeedForPath(pathname: string) {
  if (!pathname) return CLAW_SEED_BY_ROUTE['/cockpit'];
  for (const key of Object.keys(CLAW_SEED_BY_ROUTE)) {
    if (pathname.includes(key)) return CLAW_SEED_BY_ROUTE[key as keyof typeof CLAW_SEED_BY_ROUTE];
  }
  return CLAW_SEED_BY_ROUTE['/cockpit'];
}

/** 从 pathname 取对应的建议提问 */
export function getSuggestsForPath(pathname: string) {
  if (!pathname) return CLAW_SUGGESTS_BY_ROUTE['/cockpit'];
  for (const key of Object.keys(CLAW_SUGGESTS_BY_ROUTE)) {
    if (pathname.includes(key)) return CLAW_SUGGESTS_BY_ROUTE[key as keyof typeof CLAW_SUGGESTS_BY_ROUTE];
  }
  return CLAW_SUGGESTS_BY_ROUTE['/cockpit'];
}

/** 模块名（用于 ClawRail header 显示） */
export function getModuleLabel(pathname: string) {
  if (!pathname) return '交付态势';
  if (pathname.includes('/cockpit'))  return '交付态势';
  if (pathname.includes('/preview'))  return '合同与 BOQ';
  if (pathname.includes('/proposal')) return '交付预案';
  if (pathname.includes('/plan'))     return '排期与计划';
  if (pathname.includes('/sandbox'))  return '沙箱推演';
  if (pathname.includes('/journey'))  return '交付旅程';
  if (pathname.includes('/create'))   return '项目创建';
  if (pathname.includes('/design'))   return 'LLD 设计';
  if (pathname.includes('/admin'))    return '管理';
  if (pathname.includes('/assets'))   return '交付作业';
  if (pathname.includes('/module'))   return '作业模块';
  return '交付态势';
}
