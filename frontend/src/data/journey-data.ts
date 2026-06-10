/* Journey · 项目全生命周期故事线
 * 9 个阶段，覆盖从 TD 登录 → 项目创建 → 早期接入 → DTRB → DRB → 合同签署 → LLD
 * → 交付作业（工勘/建模/施工/调测/验收） → 项目完成
 *
 * 直接对齐 2026-05-25 会议结论：5 项初始字段、OCC 审批、预案三快照、合同事件触发 LLD、
 * 交付作业五步、单独验收报告（由调测自动产出）。
 *
 * 每个阶段同时声明：
 *   - productPath: 在产品中对应的产品页路由（演示时一键跳转）
 *   - sysSnapshot: 该阶段系统集成的"在线/降级"状态，驱动 TopBar 全局状态灯演示
 *   - durationDay: 该阶段实际占的日历天数，用于"项目进度条"
 */

import type {
  JourneyStage,
  PlanGanttRow,
  PlanGood,
  PlanPerson,
  PlanSite,
  TwinRoom,
} from '../types/domain';

export const JOURNEY_STAGES = [
  {
    key: 'landing',
    ord: 0,
    name: '登录落地',
    role: 'TD',
    title: 'TD 登录 · 项目列表',
    subtitle: '会议结论：登录后第一屏只有「项目列表 + 创建按钮」，无 AI 输入窗',
    storyTag: '起手式',
    summary: 'TD 何博登录系统。系统识别其在 3 个历史项目的 TD 身份，给出"我的项目"列表与"新建项目"入口。这是会议明确强调的 landing page。',
    aiPrompt: null,
    productPath: '/landing',
    productLabel: '在产品中查看 · 项目选择落地页',
    productPathExtra: [
      { path: '/login', label: '登录页（演示前点这里重头开始）' },
    ],
    durationDay: 0,
    sysSnapshot: { overall: 'ok', highlight: '账号系统在线 · 8 个上游集成全部在线' },
    keyData: [
      { k: '历史项目', v: '3 个' },
      { k: '待办合计', v: '8 项' },
      { k: '本季新建额度', v: '2 / 5' },
    ],
    decisions: [
      { label: '进入已有项目', kind: 'ghost' },
      { label: '+ 新建项目', kind: 'primary' },
    ],
  },
  {
    key: 'create',
    ord: 1,
    name: '项目初始化',
    role: 'TD',
    title: '新建项目 · 五项基本字段',
    subtitle: '会议结论：初始化字段不超过 5 项，关联 proposal 后由系统自动拉合同/BOQ',
    storyTag: '5 个字段封口',
    summary: 'TD 在弹窗里输入 5 项必填字段；只要 proposal ID 关联到，集群形态、新建/扩容、项目群名称会自动回填。',
    aiPrompt: 'AIDA：已为您预填 4 项可识别字段，建议核对 proposal ID 是否与"智算 Q3-K1903 客户甲"匹配。',
    productPath: '/create',
    productLabel: '在产品中查看 · 新建项目向导',
    durationDay: 1,
    sysSnapshot: { overall: 'ok', highlight: 'Proposal / OCC / Wiki / DORA 全在线 · MES 略有抖动' },
    fields: [
      { key: 'proposal', label: 'Proposal ID', value: 'PROP-2026-K1903', auto: true },
      { key: 'newExpand', label: '新建 / 扩容', value: '新建', auto: true },
      { key: 'product', label: '产品形态', value: '智算集群 384N', auto: true },
      { key: 'cluster', label: '集群形态', value: 'AI 训推一体', auto: true },
      { key: 'group', label: '项目群名称', value: '京东三期', auto: false, hint: '请确认' },
    ],
    decisions: [
      { label: '取消', kind: 'ghost' },
      { label: '提交审批', kind: 'primary' },
    ],
  },
  {
    key: 'approval',
    ord: 2,
    name: 'OCC 审批',
    role: 'OCC',
    title: 'OCC 数据出境审批',
    subtitle: '会议结论：关联 proposal 会拉取机会点/合同/BOQ 全量数据，存在数据出境风险，须 OCC 审批',
    storyTag: '合规闸门',
    summary: 'OCC 审批员审查本次项目的关联数据范围。审批通过后，项目空间才会真正生效，TD 才能进入。',
    aiPrompt: 'AIDA：发现 BOQ 关联客户敏感字段（地址 / 联系人 3 处），已在审批报文中高亮，待 OCC 决议。',
    productPath: '/admin?tab=privacy',
    productLabel: '在产品中查看 · OCC 审批中心',
    durationDay: 1,
    sysSnapshot: { overall: 'warn', highlight: 'OCC 审批中 · 敏感字段策略已触发 · 数据出境前止血' },
    keyData: [
      { k: '关联机会点', v: '1' },
      { k: '关联合同', v: '0 (未签)' },
      { k: 'BOQ 行数', v: '127' },
      { k: '敏感字段', v: '3 处' },
    ],
    decisions: [
      { label: '驳回', kind: 'danger' },
      { label: '审批通过', kind: 'primary' },
    ],
    approvalTimeline: [
      { t: '14:02', who: 'TD 何博', act: '提交审批', state: 'done' },
      { t: '14:08', who: 'AIDA', act: '风险扫描完成', state: 'done' },
      { t: '14:21', who: 'OCC 黎芳', act: '审批中', state: 'active' },
      { t: '—', who: '项目空间', act: '激活', state: 'pending' },
    ],
  },
  {
    key: 'ingest',
    ord: 3,
    name: '文档摄取与解析',
    role: 'TD',
    title: '上传文档 · 多模态解析要素',
    subtitle: '会议结论：售前工勘 + HLD + BOQ + CAD 一次上传，AI 按目录结构解析全部要素，下拉式呈现',
    storyTag: '一次性批量摄取',
    summary: 'TD 把售前工勘、HLD、BOQ 草表、CAD 底图全部拖上来。AIDA 调用多模态解析，按 ER 模型把要素全部写入项目空间。',
    aiPrompt: 'AIDA：已并行解析 4 个文档，识别 86 个要素（缺 14 项），关键缺失：机柜归位、走线路由。',
    productPath: '/preview?tab=contract',
    productLabel: '在产品中查看 · 早期接入 · 合同 / BOQ',
    durationDay: 2,
    sysSnapshot: { overall: 'ok', highlight: 'DocParser 在线 · CAD 解析降级（坐标识别受限）' },
    documents: [
      { name: '售前-工勘记录_K1903.pdf', size: '4.2 MB', parsed: true, items: 31 },
      { name: 'HLD-K1903-v2.docx', size: '1.8 MB', parsed: true, items: 24 },
      { name: 'BOQ-K1903.xlsx', size: '380 KB', parsed: true, items: 18 },
      { name: '机房-CAD底图.dwg', size: '6.1 MB', parsed: 'partial', items: 13, note: '坐标解析受限，机柜归位需手工补' },
    ],
    extractedElements: [
      { cat: '项目基本', total: 5, ready: 5 },
      { cat: '设备版本/部件', total: 12, ready: 12 },
      { cat: '软件配置', total: 6, ready: 4 },
      { cat: '组网规则', total: 8, ready: 8 },
      { cat: '机房物理（归位/路由）', total: 4, ready: 0, blocker: true },
      { cat: '服务/集成验证', total: 5, ready: 5 },
      { cat: '风险/假设', total: 7, ready: 5 },
      { cat: '初始计划要素', total: 3, ready: 3 },
    ],
    decisions: [
      { label: '导出当前解析快照', kind: 'ghost' },
      { label: '确认并写入项目空间', kind: 'primary' },
    ],
  },
  {
    key: 'dtrb',
    ord: 4,
    name: 'DTRB 预案',
    role: 'TD',
    title: '生成 DTRB 评审材料',
    subtitle: '会议结论：DTRB 是预案的第一个快照，要素阈值到了就触发，无需用户管阶段',
    storyTag: '快照 1 / 3',
    summary: '要素完整度 78%，AIDA 判断已可生成 DTRB 评审材料。预案章节 9 个，缺失项以橙色标注。',
    aiPrompt: 'AIDA：已生成 DTRB v1.0 评审材料。机房物理章节 2 处缺失（机柜归位、走线路由），其余 7 章节齐备。',
    productPath: '/preview?tab=dtrb',
    productLabel: '在产品中查看 · DTRB 快照',
    durationDay: 3,
    sysSnapshot: { overall: 'ok', highlight: 'Wiki / DORA / AIDA 推理引擎全部在线' },
    snapshot: {
      version: 'DTRB-v1.0',
      ts: '2026-05-26 14:42',
      completeness: 78,
      chapters: [
        { name: '1. 客户与项目背景', state: 'ok' },
        { name: '2. 集群规划与拓扑', state: 'ok' },
        { name: '3. 设备清单与 EOS', state: 'ok' },
        { name: '4. 组网与链路设计', state: 'ok' },
        { name: '5. 机房物理布局', state: 'gap', note: '机柜归位 / 桥架路由待补' },
        { name: '6. 软件与平台栈', state: 'partial', note: 'k8s 平台版本待确认' },
        { name: '7. 集成验证需求', state: 'ok' },
        { name: '8. 风险与假设', state: 'partial', note: '2 项假设待客户回复' },
        { name: '9. 初始交付计划', state: 'ok' },
      ],
    },
    decisions: [
      { label: '下载 DTRB 文档', kind: 'ghost' },
      { label: '提交 DTRB 评审', kind: 'primary' },
    ],
  },
  {
    key: 'drb',
    ord: 5,
    name: 'DRB 预案',
    role: 'TD',
    title: '刷新到 DRB 评审版本',
    subtitle: '会议结论：DRB 阶段要素无新增，只刷新已有要素；按时间点切快照',
    storyTag: '快照 2 / 3',
    summary: 'DTRB 评审反馈：第 5 章机房物理已闭环（手工补完归位），第 8 章假设已客户确认。完整度提升至 94%。',
    aiPrompt: 'AIDA：DRB v1.0 已生成。相比 DTRB 变化：3 处要素补全、5 处数值修订。',
    productPath: '/preview?tab=drb',
    productLabel: '在产品中查看 · DRB 快照',
    durationDay: 4,
    sysSnapshot: { overall: 'ok', highlight: '全部在线 · 客户评审会前最后一稿' },
    snapshot: {
      version: 'DRB-v1.0',
      ts: '2026-05-30 10:15',
      completeness: 94,
      diff: [
        { ch: '5. 机房物理', change: '+ 12 个机柜归位 / 桥架路由示意图' },
        { ch: '6. 软件平台', change: '~ k8s 1.28 → 1.30 LTS' },
        { ch: '8. 风险假设', change: '- 2 项假设关闭（客户已确认）' },
        { ch: '9. 初始计划', change: '~ 关键路径压缩 3 天' },
      ],
    },
    decisions: [
      { label: '对比 DTRB ↔ DRB', kind: 'ghost' },
      { label: '提交 DRB 评审', kind: 'primary' },
    ],
  },
  {
    key: 'contract',
    ord: 6,
    name: '合同签署 · LLD',
    role: 'System',
    title: '合同事件触发 · 生成 LLD',
    subtitle: '会议结论：合同签署→系统识别→通知 TD→TD 补充 LLD 必要字段→生成 LLD',
    storyTag: '快照 3 / 3',
    summary: '系统通过陈卓接口监测到合同已签署且绑定本项目。WeLink 推送通知 TD。TD 进入项目，补充命名方案、网络信息、集成测试用例后生成 LLD。',
    aiPrompt: 'AIDA：合同已签署 (CON-2026-K1903-001)，绑定本项目。请补充：① 命名方案 ② 网络配置 ③ 集成测试用例。',
    productPath: '/design',
    productLabel: '在产品中查看 · LLD 主版本',
    durationDay: 2,
    sysSnapshot: { overall: 'ok', highlight: '陈卓接口检测到合同事件 · WeLink 推送 TD' },
    contractEvent: {
      id: 'CON-2026-K1903-001',
      signTs: '2026-06-04 17:30',
      bindTs: '2026-06-04 17:31',
      amount: '¥ 1.84 亿',
      milestones: 5,
    },
    lldFields: [
      { k: '命名方案', v: 'K1903-{room}-{rack}-{u}', state: 'ok' },
      { k: '管理网段', v: '10.193.0.0/16', state: 'ok' },
      { k: '业务网段', v: '10.194.0.0/16', state: 'ok' },
      { k: '集成测试用例集', v: 'CASE-AI-INFER-v2', state: 'ok' },
      { k: '验收性能指标', v: 'p99 < 30ms, T/s ≥ 240', state: 'ok' },
    ],
    decisions: [
      { label: '下载 LLD 文档', kind: 'ghost' },
      { label: '冻结基线 · 启动交付', kind: 'primary' },
    ],
  },
  {
    key: 'delivery',
    ord: 7,
    name: '交付作业',
    role: 'TL',
    title: '五段交付作业 · 工勘 → 仿真 → 安装 → 调测 → 验收',
    subtitle: '会议结论：作业目录就是这五段，验收报告由调测自动产出，无须独立模块触发',
    storyTag: '人货站联动',
    summary: '人货站三因素并行推进。工勘已完成 11/14 机房，建模仿真 PoD 级 30/36，施工队 12 队就位 184 人，调测进入 4 个 PoD。',
    aiPrompt: 'AIDA：今日 3 个 PoD 卡住（B2-RM02 配电延期），建议沙箱推演：①PoD#01-04 安装压缩 2d ②从 H 项目调度 2 名工程师补位。',
    productPath: '/plan?view=plan',
    productLabel: '在产品中查看 · 人货站融合计划',
    productPathExtra: [
      { path: '/cockpit#twin', label: '同时打开 · 3D 孪生（演示视觉冲击）' },
      { path: '/sandbox?scenario=b2-power-delay', label: '打开 · AI 推演沙箱（α/β 方案对比）' },
    ],
    durationDay: 45,
    sysSnapshot: { overall: 'warn', highlight: 'MES 偶发延迟 · 客户配电改造延期 · B2-RM02 阻塞' },
    workstreams: [
      { key: 'survey', name: '智慧工勘', icon: '⊙', total: 14, done: 11, atRisk: 2, blocked: 1, kpi: '机房就绪率 78.6%' },
      { key: 'modeling', name: '建模仿真', icon: '◇', total: 36, done: 30, atRisk: 4, blocked: 2, kpi: 'PoD 拓扑 83.3% 通过' },
      { key: 'install', name: '安装施工', icon: '▢', total: 36, done: 18, atRisk: 8, blocked: 4, kpi: '机柜入场 50%' },
      { key: 'commission', name: '调测点亮', icon: '◈', total: 36, done: 8, atRisk: 6, blocked: 0, kpi: '业务面 4 套联通' },
      { key: 'accept', name: '客户验收', icon: '✓', total: 5, done: 0, atRisk: 1, blocked: 0, kpi: '里程碑 #1 倒计时 12d' },
    ],
    decisions: [
      { label: '进入人货站计划', kind: 'ghost' },
      { label: '进入 3D 孪生', kind: 'primary' },
    ],
  },
  {
    key: 'completion',
    ord: 8,
    name: '项目完成',
    role: 'PD',
    title: '验收闭环 · 移交客户',
    subtitle: '会议结论：验收报告由设备调测自动产出（不单独触发），客户签字即收口',
    storyTag: '收口',
    summary: '5 项合同里程碑全部达成。最终验收报告由调测数据 + 客户测试样本自动合成。客户已签字，项目进入 1 年质保期。',
    aiPrompt: 'AIDA：项目交付完成，合同金额 ¥ 1.84 亿全额回款，关键里程碑达成率 100%。已生成复盘材料初稿。',
    productPath: '/cockpit#twin',
    productLabel: '在产品中查看 · 3D 孪生（最终态 · 全绿）',
    productPathExtra: [
      { path: '/admin?tab=audit', label: '查看 · 全流程审计日志' },
    ],
    durationDay: 1,
    sysSnapshot: { overall: 'ok', highlight: '验收报告由调测数据自动合成 · 客户已签字 · 进入质保期' },
    closeMetrics: [
      { k: 'PoD 交付', v: '36 / 36' },
      { k: '里程碑达成', v: '5 / 5' },
      { k: '工期偏差', v: '-2d（提前）' },
      { k: '验收一次通过率', v: '94%' },
      { k: '回款比例', v: '100%' },
      { k: '客户满意度', v: '4.7 / 5.0' },
    ],
    handover: [
      { item: '运维手册', state: 'done' },
      { item: '调测原始日志', state: 'done' },
      { item: '客户培训记录', state: 'done' },
      { item: '质保期切换工单', state: 'done' },
      { item: 'Wiki 复盘条目', state: 'done', note: '已并入历史项目库，供未来项目参考' },
    ],
    decisions: [
      { label: '导出复盘材料', kind: 'ghost' },
      { label: '关闭项目 · 归档', kind: 'primary' },
    ],
  },
] satisfies JourneyStage[];

export const JOURNEY_LANE_ROLES = {
  TD: { color: 'var(--c-brand)', label: 'TD · 技术总监' },
  PD: { color: 'var(--c-success)', label: 'PD · 项目总监' },
  TL: { color: 'var(--c-warning)', label: 'TL · 作业人员' },
  OCC: { color: 'var(--c-danger)', label: 'OCC · 合规审批' },
  System: { color: 'var(--c-text-muted)', label: 'System · 系统事件' },
};

/* Module status lights for left nav · 会议结论：每个模块加一个状态灯 */
export const MODULE_STATUS = {
  cockpit: { state: 'live', label: '实时' },
  survey: { state: 'ok', label: '在线' },
  modeling: { state: 'ok', label: '在线' },
  job: { state: 'warn', label: '待办 3' },
  design: { state: 'ok', label: '在线' },
  install: { state: 'alert', label: '阻塞 1' },
  deploy: { state: 'ok', label: '在线' },
  plan: { state: 'warn', label: '待决策' },
};

/* 项目计划 · 人货站三因素 */
export const PLAN_GANTT = [
  { id: 'G1', task: '工程勘测 & 设计审核', start: 0,  dur: 18, owner: '何博',  status: 'done', critPath: true },
  { id: 'G2', task: '预布线 & 桥架安装',   start: 10, dur: 20, owner: '施工队', status: 'done', critPath: true },
  { id: 'G3', task: '设备到货 & 验货',     start: 18, dur: 14, owner: '王明',   status: 'risk', critPath: true },
  { id: 'G4', task: '服务器上架 & 综合布线',start: 32, dur: 22, owner: '施工队', status: 'in',   critPath: true },
  { id: 'G5', task: '液冷 CDU 安装',       start: 38, dur: 12, owner: '液冷组', status: 'in',   critPath: false },
  { id: 'G6', task: '上电 & ZTP 开局',     start: 54, dur: 10, owner: '调试组', status: 'plan', critPath: true },
  { id: 'G7', task: '集群联调 & 压测',     start: 64, dur: 14, owner: '调试组', status: 'plan', critPath: true },
  { id: 'G8', task: '验收 & 移交',         start: 78, dur: 7,  owner: '何博',   status: 'plan', critPath: true },
];

export const PLAN_PEOPLE = [
  { team: '施工队 07',  members: 18, allocPct: 95, current: '设备安装 B2-RM01',  status: 'risk', warn: '超负荷 · 建议从 H 项目调 2 人' },
  { team: '调试组 K',   members: 12, allocPct: 72, current: 'ZTP 开局准备',        status: 'ok',   warn: null },
  { team: '液冷维保',   members: 4,  allocPct: 60, current: 'CDU 压测',            status: 'ok',   warn: null },
  { team: '验收组',     members: 6,  allocPct: 20, current: '等待安装完成',         status: 'ok',   warn: null },
];

export const PLAN_GOODS = [
  { sku: 'A3 SuperPoD 整机柜 · 384N',  total: 36, arrived: 28, status: 'risk', eta: 'ETA 06/02' },
  { sku: '100G 光模块 · QSFP28',        total: 288, arrived: 288, status: 'ok',  eta: '已齐套' },
  { sku: 'ConnectX-7 HCA · 192 端口',   total: 192, arrived: 192, status: 'ok',  eta: '已齐套' },
  { sku: '液冷 CDU 组件',               total: 8,   arrived: 7,   status: 'risk', eta: 'ETA 06/05' },
];

export const PLAN_SITES = [
  { room: 'A1-RM01', pods: 4, state: 'ready',   blocker: null },
  { room: 'A1-RM02', pods: 4, state: 'ready',   blocker: null },
  { room: 'B2-RM01', pods: 3, state: 'prep',    blocker: null },
  { room: 'B2-RM02', pods: 4, state: 'blocked', blocker: '配电延期 9d' },
  { room: 'C3-RM01', pods: 3, state: 'ready',   blocker: null },
];

/* 系统集成监控（TopBar 健康度） */
export const SYSTEM_INTEGRATIONS = [
  { id: 'crm',      name: 'CRM · 机会点',     dir: '↑ 上游', desc: '合同 / 机会点 / 客户信息',  state: 'live', latencyMs: 42  },
  { id: 'ecare',    name: 'eCare · 工程报单',  dir: '↑ 上游', desc: '客户工程报单 / SLA 状态',    state: 'live', latencyMs: 88  },
  { id: 'boq',      name: 'BOQ · 采购系统',    dir: '↑ 上游', desc: 'BOQ 行 / 到货状态',          state: 'warn', latencyMs: 210 },
  { id: 'contract', name: '合同系统',           dir: '↑ 上游', desc: '合同签署 / 变更通知',        state: 'live', latencyMs: 65  },
  { id: 'occ',      name: 'OCC · 合规',        dir: '↑ 上游', desc: '数据出境审批 / 合规规则',    state: 'live', latencyMs: 31  },
  { id: 'welink',   name: 'WeLink · 通知',     dir: '↑ 上游', desc: '跨系统消息推送',             state: 'live', latencyMs: 19  },
  { id: 'nvisual',  name: 'Nvisual · 建模',    dir: '↓ 下游', desc: '机房 3D 建模 iframe',        state: 'down', latencyMs: 0   },
  { id: 'dora',     name: 'DORA · 本体',       dir: '⇅ 双向', desc: '交付规则库 / 风险校验',      state: 'live', latencyMs: 55  },
];

export const SYSTEM_HEADLINE = {
  version: 'v1.0-alpha',
  project: 'K1903',
  env: 'demo',
};
