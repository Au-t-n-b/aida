import type { ModuleSchemas } from '../types/domain';

export const MODULE_SCHEMAS = {
  survey: {
    key: 'survey',
    name: '智慧工勘',
    iconName: 'IconSurvey',
    subtitle: '现场勘察 · 场景评估 · 交付基线',
    steps: ['引导', '决策', '上传', '执行', '汇总', '完成'],
    embed: null,
    welcome: '我将协助您完成智慧工勘模块的交付工作。本模块涵盖现场勘察数据采集、场景评估和交付基线确认，预计提效 42%。',
    decideAsk: '请选择本次工勘的作业场景类型，我会针对性地配置评估模型：',
    uploadAsk: '请上传现场勘察相关文件（支持 Excel、PDF、图片格式）：',
    executeAsk: '文件已收到，现在开始执行工勘分析。系统将并行运行以下任务：',
    finishAsk: '工勘报告已生成，请确认以下关键指标，然后提交交付基线。',
    hitl: {
      title: '选择勘察场景',
      hint: '请选择最符合本次工勘的场景类型（可多选）',
      multi: true,
      options: [
        { label: '数据中心机房', value: 'dc', desc: '含机柜、走线架、PDU 等设施评估', badge: '常用' },
        { label: '园区网络', value: 'campus', desc: '含接入、汇聚、核心层拓扑规划' },
        { label: '运营商骨干网', value: 'carrier', desc: '含 OTN/DWDM 传输路由规划', badge: '复杂' },
        { label: '政企专线', value: 'enterprise', desc: '含 CPE 部署与 SLA 评估' },
      ],
    },
    scenarioTable: [
      { scenario: '数据中心机房', score: 92, risk: '低', notes: '机柜利用率 ≤ 80%', tone: 'green' },
      { scenario: '园区接入', score: 78, risk: '中', notes: '存在弱电间散热隐患', tone: 'amber' },
      { scenario: '核心骨干', score: 65, risk: '高', notes: '跨段距离超过规划阈值', tone: 'red' },
    ],
    files: [
      { name: '现场勘察模板.xlsx', size: 42000 },
      { name: '设备清单草稿.xlsx', size: 18000 },
    ],
    outputs: [
      { name: '工勘报告_v1.pdf', size: 256000 },
      { name: '场景评分表.xlsx', size: 64000 },
      { name: '交付基线.json', size: 8000 },
    ],
    skillNames: ['场景识别', '风险评估', '基线生成'],
    finalOutput: '工勘报告_v1.pdf',
    metricsByStage: {
      execute: [
        { label: '扫描点位', value: 1247, unit: '个', tone: 'accent' },
        { label: '场景识别率', value: 98.3, unit: '%', decimals: 1, tone: 'green' },
        { label: '风险项', value: 7, unit: '条', tone: 'amber' },
        { label: '处理速度', value: 312, unit: 'pts/s', tone: 'default' },
      ],
      synthesize: [
        { label: '综合评分', value: 82, unit: '分', tone: 'accent' },
        { label: '提效预估', value: 42, unit: '%', tone: 'green' },
        { label: '高风险项', value: 2, unit: '条', tone: 'red' },
        { label: '置信度', value: 94.1, unit: '%', decimals: 1, tone: 'default' },
      ],
      finish: [
        { label: '综合评分', value: 82, unit: '分', tone: 'accent' },
        { label: '提效预估', value: 42, unit: '%', tone: 'green' },
        { label: '高风险项', value: 2, unit: '条', tone: 'red' },
        { label: '已确认基线', value: 1, unit: '份', tone: 'default' },
      ],
    },
    tracks: [
      { id: 'scene', label: '场景识别', skill: '场景识别引擎' },
      { id: 'risk', label: '风险评估', skill: '风险分析模型' },
      { id: 'baseline', label: '基线生成', skill: '基线生成器' },
    ],
    synthesisParagraphs: [
      { title: '勘察总结', text: '本次智慧工勘共识别 3 种场景类型，覆盖 1,247 个点位。数据中心机房场景得分最高（92分），整体交付基线可信度达 94.1%。' },
      { title: '主要风险', text: '识别到 7 条风险项，其中 2 条高风险：跨段传输距离超阈值（骨干网段）和弱电间散热隐患（园区接入层）。建议在交付前完成整改确认。' },
      { title: '交付建议', text: '建议优先推进数据中心机房和政企专线场景的交付，暂缓核心骨干段直至风险整改完成。预估整体交付周期可压缩至 18 个工作日。' },
    ],
  },

  modeling: {
    key: 'modeling',
    name: '建模仿真',
    iconName: 'IconTopo',
    subtitle: 'BOQ 提取 · 拓扑生成 · 仿真验证',
    steps: ['引导', '决策', '上传', '执行', '汇总', '完成'],
    embed: 'topology',
    welcome: '建模仿真模块将自动完成 BOQ 提取、网络拓扑生成和仿真验证，支持在线调整和导出。',
    decideAsk: '请选择建模目标和约束条件：',
    uploadAsk: '请上传 BOQ 清单和网络规划基础文件：',
    executeAsk: '正在执行 BOQ 解析和拓扑建模，以下任务并行运行：',
    finishAsk: '拓扑模型已验证通过，请确认最终交付物。',
    hitl: {
      title: '建模目标配置',
      hint: '选择本次建模的主要目标（单选）',
      multi: false,
      options: [
        { label: '最优成本方案', value: 'cost', desc: '在满足 SLA 前提下最小化硬件投入' },
        { label: '最优性能方案', value: 'perf', desc: '最大化带宽利用率和冗余度', badge: '推荐' },
        { label: '快速交付方案', value: 'fast', desc: '优先使用库存设备，缩短交付周期' },
        { label: '自定义约束', value: 'custom', desc: '手动配置约束参数' },
      ],
    },
    scenarioTable: [
      { scenario: '核心交换层', score: 96, risk: '低', notes: '冗余链路配置完整', tone: 'green' },
      { scenario: '汇聚接入层', score: 88, risk: '低', notes: '符合 802.3ad 规范', tone: 'green' },
      { scenario: 'WAN 出口', score: 71, risk: '中', notes: 'BGP 路由策略需优化', tone: 'amber' },
    ],
    files: [
      { name: 'BOQ清单_v3.xlsx', size: 86000 },
      { name: '网络规划书.docx', size: 124000 },
      { name: '现有设备台账.xlsx', size: 56000 },
    ],
    outputs: [
      { name: '网络拓扑图.pdf', size: 480000 },
      { name: '设备配置模板.xlsx', size: 96000 },
      { name: '仿真验证报告.pdf', size: 320000 },
    ],
    skillNames: ['BOQ解析', '拓扑生成', '仿真验证'],
    finalOutput: '网络拓扑图.pdf',
    metricsByStage: {
      execute: [
        { label: '解析设备', value: 486, unit: '台', tone: 'accent' },
        { label: '生成链路', value: 1024, unit: '条', tone: 'default' },
        { label: '冲突项', value: 12, unit: '处', tone: 'amber' },
        { label: '仿真轮次', value: 8, unit: '轮', tone: 'green' },
      ],
      synthesize: [
        { label: '拓扑评分', value: 94, unit: '分', tone: 'accent' },
        { label: '链路利用率', value: 67.3, unit: '%', decimals: 1, tone: 'green' },
        { label: 'SPOF 节点', value: 3, unit: '个', tone: 'red' },
        { label: '仿真通过率', value: 100, unit: '%', tone: 'green' },
      ],
      finish: [
        { label: '拓扑评分', value: 94, unit: '分', tone: 'accent' },
        { label: '链路利用率', value: 67.3, unit: '%', decimals: 1, tone: 'green' },
        { label: 'SPOF 节点', value: 3, unit: '个', tone: 'red' },
        { label: '已确认交付物', value: 3, unit: '份', tone: 'default' },
      ],
    },
    tracks: [
      { id: 'boq', label: 'BOQ 解析', skill: '文档解析引擎' },
      { id: 'topo', label: '拓扑生成', skill: '图论建模器' },
      { id: 'sim', label: '仿真验证', skill: '流量仿真引擎' },
    ],
    synthesisParagraphs: [
      { title: '建模摘要', text: '已完成对 486 台设备的 BOQ 解析，生成包含 1,024 条链路的网络拓扑。核心交换层和汇聚接入层评分均超过 85 分，整体架构满足高可用要求。' },
      { title: '风险点', text: '识别 3 个单点故障（SPOF）节点，均位于 WAN 出口区域。BGP 路由策略存在优化空间，建议配置双活出口以消除 SPOF。' },
      { title: '交付建议', text: '拓扑方案已通过 8 轮仿真验证，可直接用于施工配置。建议在割接前对 WAN 出口进行额外压力测试，确认 BGP 收敛时间满足 SLA 要求。' },
    ],
  },

  // design → xtsj（系统设计 / A3 智能网络开局），dispatch 命令模式，非线性流水线
  design: {
    key: 'design',
    name: '系统设计',
    iconName: 'IconDesign',
    subtitle: '输入件检查 · 地址规划 · LLD 生成',
    steps: ['命令选择', '输入件检查', '地址规划', 'LLD 生成', '完成'],
    embed: null,
    welcome: '系统设计（A3 智能网络开局）将检查输入件完整性、批量规划 IP 地址段，并生成标准化 LLD 文档，支持按需触发各命令。',
    decideAsk: '请选择本次要执行的系统设计命令：',
    uploadAsk: '请上传项目输入件（BOQ、需求书等）：',
    executeAsk: '正在执行系统设计命令，请查阅下方实时日志：',
    finishAsk: '命令已完成，请下载产物文件。',
    hitl: {
      title: '选择执行命令',
      hint: '选择本次系统设计要执行的命令（单选）',
      multi: false,
      options: [
        { label: '检查输入件', value: 'input_check', desc: '验证 BOQ、规划书等输入件是否齐备', badge: '推荐' },
        { label: '地址批规划', value: 'address_plan', desc: 'CSM / CC-GLM / CC-YBM / CPM-LQ 批量 IP 分配' },
        { label: 'LLD 生成', value: 'lld_generate', desc: '生成骨架 LLD 并融合各平面配置' },
        { label: 'ZTP 配置', value: 'ztp_cfg', desc: '生成零接触开局配置文件' },
      ],
    },
    scenarioTable: [
      { scenario: '计算面（CSM）', score: 0, risk: '待检查', notes: '执行 input_check 后刷新', tone: 'amber' },
      { scenario: '网络面（CC-GLM）', score: 0, risk: '待检查', notes: '执行 input_check 后刷新', tone: 'amber' },
      { scenario: '存储面（CC-YBM）', score: 0, risk: '待检查', notes: '执行 input_check 后刷新', tone: 'amber' },
    ],
    files: [],
    outputs: [
      { name: 'address_plan.xlsx', size: 64000 },
      { name: 'LLD_骨架.docx', size: 128000 },
    ],
    skillNames: ['输入件检查', '地址批规划', 'LLD 生成'],
    finalOutput: 'LLD_骨架.docx',
    metricsByStage: {
      execute: [
        { label: '检查网络平面', value: 4, unit: '个', tone: 'accent' },
        { label: '已分配地址段', value: 0, unit: '段', tone: 'default' },
      ],
      synthesize: [
        { label: '输入件完整度', value: 0, unit: '%', tone: 'accent' },
      ],
      finish: [
        { label: '已生成产物', value: 0, unit: '份', tone: 'default' },
      ],
    },
    tracks: [
      { id: 'input_check', label: '输入件检查', skill: '输入件验证器' },
      { id: 'address_plan', label: '地址批规划', skill: '地址规划引擎' },
      { id: 'lld', label: 'LLD 生成', skill: 'LLD 生成器' },
    ],
    synthesisParagraphs: [
      { title: '系统设计摘要', text: '系统设计（A3 智能网络开局）采用命令分发模式，支持按需触发各子命令。运行后请通过 SDUI 面板查阅命令详细结果与产物。' },
    ],
  },

  // job 是独立的「作业管理（CPM 进度规划）」占位模块，待后端 skill 接入前沿用 MockModuleRoute
  job: {
    key: 'job',
    name: '作业管理',
    iconName: 'IconGantt',
    subtitle: '进度规划 · CPM 计算 · 风险预警',
    steps: ['引导', '决策', '上传', '执行', '汇总', '完成'],
    embed: 'gantt',
    welcome: '作业管理模块将自动生成交付进度计划，利用关键路径法（CPM）识别瓶颈任务并进行风险预警。',
    decideAsk: '请选择项目进度优化策略：',
    uploadAsk: '请上传 WBS 和资源需求文件：',
    executeAsk: '正在执行进度建模和 CPM 分析：',
    finishAsk: '进度计划已通过 CPM 验证，请确认最终交付。',
    hitl: {
      title: '进度优化策略',
      hint: '选择进度规划的主要约束（单选）',
      multi: false,
      options: [
        { label: '工期最短', value: 'time', desc: '允许资源超配以压缩工期', badge: '常用' },
        { label: '资源均衡', value: 'resource', desc: '保持资源负载均衡，允许适当延期' },
        { label: '成本最优', value: 'cost', desc: '最小化赶工成本，适度延长工期' },
        { label: '里程碑锁定', value: 'milestone', desc: '保证关键里程碑不延期' },
      ],
    },
    scenarioTable: [
      { scenario: '硬件部署', score: 88, risk: '低', notes: '设备到货按时', tone: 'green' },
      { scenario: '系统配置', score: 74, risk: '中', notes: '依赖工勘报告延误', tone: 'amber' },
      { scenario: '联调测试', score: 61, risk: '高', notes: '关键路径瓶颈，需赶工', tone: 'red' },
    ],
    files: [
      { name: 'WBS结构表.xlsx', size: 72000 },
      { name: '资源需求计划.xlsx', size: 48000 },
    ],
    outputs: [
      { name: '项目进度计划.xlsx', size: 96000 },
      { name: 'CPM分析报告.pdf', size: 240000 },
      { name: '风险预警清单.xlsx', size: 36000 },
    ],
    skillNames: ['进度建模', 'CPM分析', '风险检测'],
    finalOutput: 'CPM分析报告.pdf',
    metricsByStage: {
      execute: [
        { label: '任务节点', value: 234, unit: '个', tone: 'accent' },
        { label: '关键路径', value: 47, unit: '天', tone: 'amber' },
        { label: '资源冲突', value: 18, unit: '处', tone: 'red' },
        { label: '浮动空间', value: 8.2, unit: '天', decimals: 1, tone: 'green' },
      ],
      synthesize: [
        { label: '计划评分', value: 79, unit: '分', tone: 'accent' },
        { label: '工期压缩', value: 15, unit: '%', tone: 'green' },
        { label: '高风险任务', value: 5, unit: '个', tone: 'red' },
        { label: '资源利用率', value: 82.4, unit: '%', decimals: 1, tone: 'default' },
      ],
      finish: [
        { label: '计划评分', value: 79, unit: '分', tone: 'accent' },
        { label: '工期压缩', value: 15, unit: '%', tone: 'green' },
        { label: '高风险任务', value: 5, unit: '个', tone: 'red' },
        { label: '已确认计划', value: 1, unit: '份', tone: 'default' },
      ],
    },
    tracks: [
      { id: 'schedule', label: '进度建模', skill: '进度引擎' },
      { id: 'cpm', label: 'CPM 分析', skill: '关键路径计算器' },
      { id: 'risk', label: '风险检测', skill: '风险预警模型' },
    ],
    synthesisParagraphs: [
      { title: '进度摘要', text: '已完成 234 个任务节点的进度建模，识别关键路径长度为 47 天。通过赶工优化，工期相较初版计划压缩 15%，满足交付里程碑要求。' },
      { title: '资源分析', text: '识别到 18 处资源冲突，主要集中在系统配置阶段（第 15-28 天）。建议在此阶段增配 2 名网络工程师，可消除 14 处冲突。' },
      { title: '风险预警', text: '5 个高风险任务中，联调测试阶段风险最高（得分 61 分）。建议提前 3 天启动测试环境准备，并锁定第三方测试资源，降低延期概率。' },
    ],
  },
} satisfies ModuleSchemas;

export const ALL_MODULES = [
  { key: 'survey', name: '智慧工勘', iconName: 'IconSurvey', desc: '现场勘察 · 场景评估' },
  { key: 'modeling', name: '建模仿真', iconName: 'IconTopo', desc: 'BOQ 提取 · 拓扑生成' },
  { key: 'job', name: '作业管理', iconName: 'IconGantt', desc: '进度规划 · CPM 分析' },
  { key: 'design', name: '概要设计', iconName: 'IconDesign', desc: 'HLD · 方案文档' },
  { key: 'install', name: '设备安装', iconName: 'IconInstall', desc: '计划下发 · SN扫码 · ESN填写' },
  { key: 'deploy', name: '割接部署', iconName: 'IconDeploy', desc: '割接脚本 · 应急预案' },
];
