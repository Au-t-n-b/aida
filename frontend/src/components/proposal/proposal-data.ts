/** 交付预案 · 静态 mock 数据（勿改业务值） */

export const SNAPSHOTS = {
  dtrb: {
    key: 'dtrb', label: 'DTRB · 解决方案就绪', version: 'v1.0',
    ts: '2026-05-26 14:42', tone: 'blue',
    desc: 'Design-Time Review Board · 解决方案技术评审基线',
    createdBy: '何博', createdAt: '2026-05-25 09:12',
    updatedBy: '李伟', updatedAt: '2026-05-26 14:42',
    prevVersion: 'v0.3',
    diffSummary: { added: 2, modified: 3, removed: 0, highlights: [
      '7. 机房信息：新增机柜归位 + 桥架路由',
      '4. 软件配置信息：CCAE 版本对齐（修订）',
      '6. 集成验证需求：新增 RDMA 全互联用例',
    ] },
  },
  drb: {
    key: 'drb', label: 'DRB · 决策评审', version: 'v1.0',
    ts: '2026-05-30 10:15', tone: 'amber',
    desc: 'Decision Review Board · 关键技术决策与里程碑评审 · 里程碑',
    createdBy: '何博', createdAt: '2026-05-26 14:42',
    updatedBy: '何博', updatedAt: '2026-05-30 10:15',
    prevVersion: 'DTRB v1.0',
    diffSummary: { added: 1, modified: 4, removed: 0, highlights: [
      '7. 机房信息：B2-RM02 配电改造方案确认',
      '4. 软件配置信息：CCAE 版本对齐 V100R025C20',
      '13.1 风险列表：新增 ConnectX-7 数量冲突',
      '10. 计划：高阶计划里程碑顺延 +5 天',
    ] },
  },
  contract: {
    key: 'contract', label: '合同 · 签署节点', version: 'v1.0',
    ts: '2026-06-02 11:20', tone: 'violet',
    desc: '合同签署时刻冻结 · 与 BOQ / 条款对齐 · 里程碑',
    createdBy: '李伟', createdAt: '2026-05-30 10:15',
    updatedBy: '李伟', updatedAt: '2026-06-02 11:20',
    prevVersion: 'DRB v1.0',
    diffSummary: { added: 1, modified: 2, removed: 0, highlights: [
      '1.2 合同信息：合同附件 BOQ 与系统 BOQ 对齐',
      '13.1 风险列表：合同罚则条款纳入',
      '11. 验收策略：验收标准待客户确认',
    ] },
  },
  exec: {
    key: 'exec', label: '可执行合同 · SOW', version: 'v1.0',
    ts: '2026-06-04 17:31', tone: 'green',
    desc: '可执行 SOW 落地 · 冻结基线 · 后续作业唯一依据 · 默认进入',
    createdBy: '何博', createdAt: '2026-06-02 11:20',
    updatedBy: '何博', updatedAt: '2026-06-04 17:31',
    prevVersion: '合同 v1.0',
    diffSummary: { added: 3, modified: 2, removed: 0, highlights: [
      '5.2 服务器配置：补齐 384 节点网卡带宽',
      '10. 计划：PoD#01-04 安装压缩 2 天',
      '11. 验收策略：新增 RTO ≤ 5s / p99 ≤ 30ms',
      '2. 设备配置：ConnectX-7 数量冲突已闭环',
    ] },
  },
};
/* 5.27 下午：DTRB → DRB → 合同 → 可执行合同 四节点均高亮 */
export const SNAPSHOT_ORDER = ['dtrb', 'drb', 'contract', 'exec'] as const;
export const MILESTONE_KEYS = new Set(SNAPSHOT_ORDER);

/* URL 兼容旧 ?snap=lld */
export const SNAP_ALIASES = { lld: 'exec' };

/* 章节齐备情况（对齐规范 1–12 编号体系，含子章节）*/
export const BASE_CHAPTERS_DTRB = [
  { name: '元数据信息',           state: 'ok'      as const },
  { name: '1. 项目背景',          state: 'ok'      as const },
  { name: '2. 设备配置信息',      state: 'ok'      as const },
  { name: '3. 部件配置信息',      state: 'ok'      as const },
  { name: '4. 软件配置信息',      state: 'partial'  as const, note: 'k8s 平台版本待确认' },
  { name: '5. 组网配置信息',      state: 'ok'      as const },
  { name: '5.1 网络平面配置',     state: 'ok'      as const },
  { name: '5.2 服务器配置',       state: 'partial'  as const, note: '字段待与田杨敏确认' },
  { name: '6. 集成验证需求',      state: 'ok'      as const },
  { name: '7. 机房信息',          state: 'miss'    as const, note: '机柜归位 / 桥架路由待补' },
  { name: '8. 服务&维保信息',     state: 'ok'      as const },
  { name: '8.1 服务交付界面',     state: 'ok'      as const },
  { name: '8.2 服务配置',         state: 'ok'      as const },
  { name: '8.3 维保策略',         state: 'partial'  as const, note: '维保 SLA 版本待客户确认' },
  { name: '8.4 维保SLA',          state: 'ok'      as const },
  { name: '9. 责任矩阵信息',      state: 'ok'      as const },
  { name: '10. 计划',             state: 'miss'    as const, note: '实施计划联动计划模块' },
  { name: '11. 验收策略',         state: 'miss'    as const, note: '合同签署前暂无' },
  { name: '12. 测试用例',         state: 'ok'      as const },
];
export const CHAPTERS_BY_SNAP = {
  dtrb: BASE_CHAPTERS_DTRB,
  drb: BASE_CHAPTERS_DTRB.map(c => ({
    ...c,
    state: (
      c.name === '7. 机房信息'    ? 'partial'
      : c.name === '10. 计划'     ? 'partial'
      : c.name === '11. 验收策略' ? 'miss'
      : 'ok'
    ) as 'ok' | 'partial' | 'miss',
    note: (
      c.name === '7. 机房信息'    ? 'B2-RM02 配电改造方案确认'
      : c.name === '10. 计划'     ? '高阶计划已输入'
      : c.name === '11. 验收策略' ? '合同签署前暂无'
      : undefined
    ),
  })),
  contract: BASE_CHAPTERS_DTRB.map(c => ({
    ...c,
    state: (
      c.name === '13. 风险&假设信息' || c.name === '13.1 风险列表' ? 'partial'
      : c.name === '10. 计划'       ? 'partial'
      : c.name === '11. 验收策略'   ? 'partial'
      : 'ok'
    ) as 'ok' | 'partial' | 'miss',
    note: (
      c.name === '13. 风险&假设信息' ? '合同罚则 1 项待法务确认'
      : c.name === '13.1 风险列表'    ? '合同罚则条款纳入中'
      : c.name === '10. 计划'        ? '实施计划排期中'
      : c.name === '11. 验收策略'    ? '验收标准待客户确认'
      : undefined
    ),
  })),
  exec: BASE_CHAPTERS_DTRB.map(c => ({ ...c, state: 'ok' as const, note: undefined })),
};

/* 12. 测试用例 · 列表（测试类型 × 用例名称）+ 用例详情模板（图四 / 图五）*/
export const TEST_CASE_GROUPS = [
  { type: '光模块功能测试', cases: ['Link-delay测试', '光模块信息查询', '光模块LOS/LOL告警（trap/notification/syslog）测试', '光模块lane测试', '光模块电子标签信息获取'] },
  { type: '风扇基本功能', cases: ['电源电压输入过压状态异常告警测试', '风扇热插拔与告警收效'] },
  { type: 'BGP功能测试', cases: ['BGP配置方案及收敛', 'route-policy测试', 'BGP 配置参数测试', '路由延时发布'] },
  { type: '流控测试', cases: ['HCCS链路重传测试', 'HCCS场景下可用信用证状态查询及上报', '带宽测试跨节点最大网络带宽长稳测试', '带宽测试，多打一场景测试'] },
  { type: '管理测试', cases: ['ssh测试', '热补丁测试', 'LLDP测试', 'ACL基本功能测试', 'ACL规格测试', '北向上报能力（netconf/syslog/telemetry）', 'ZTP测试', 'Snmp测试', '一键式收集日志测试', 'hwtacacs 功能'] },
  { type: '可靠性测试', cases: ['光模块拔插告警', '光模块信号震荡压力测试', '版本升级时间'] },
  { type: '性能测试', cases: ['典配场景启动及业务恢复时间'] },
];

/* 用例详情模板（图五）：演示数据，所有用例复用同一结构 */
export const TEST_CASE_DETAIL_TEMPLATE = {
  purpose: '测试接口 link-delay-up 的能力',
  topology: { left: '1520', right: '1520', leftPort: 'port1', rightPort: 'port2' },
  steps: [
    'DUT1 和 DUT2 查看端口信息 display interface brief，有预期结果 1；',
    'DUT1 port1 配置端口延时 up 600s，并 shutdown port1 端口，有预期结果 2；',
    'DUT1 保存配置并重启设备，有预期结果 3；',
    '重启成功后，立即 undo shutdown DUT1 port1 端口，并查看端口状态，有预期结果 4；',
    '等待 10 分钟以上，查看端口状态，有预期结果 5；',
  ],
  expects: [
    '预期结果 1. DUT1 port1 和 DUT2 port2，端口 up，状态正常；',
    '预期结果 2. DUT1 port1 端口延时 up 配置成功，DUT1 port1 端口关闭成功；',
    '预期结果 3. DUT1 保存配置成功，重启成功；',
    '预期结果 4. 设备重启无异常，DUT1 port1 命令行下发成功，端口状态 down；',
    '预期结果 5. DUT1 port1 端口恢复，状态为 up；',
  ],
  remark: '—',
  result: '待执行',
};

/* PBI 数据（TD 手动写）*/
export const PBI_LIST = [
  { id: 'PBI-001', type: '需求', tone: 'amber',  title: '训练集群 384 节点 RDMA 全互联', chapter: '§6 网络规划', state: 'ok' },
  { id: 'PBI-002', type: '技术', tone: 'gray',   title: 'k8s 1.30 LTS + GPU Operator 部署', chapter: '§7 平台版本', state: 'ok' },
  { id: 'PBI-003', type: '风险', tone: 'red',    title: 'ConnectX-7 数量与 HLD 冲突', chapter: '§3 设备清单', state: 'pending' },
];

/* 2. 设备配置信息 · 含生命周期 / 空间 / 功耗（产品生命周期接口 + 手册 CSV）*/
export const COMPUTE_DEVICES = [
  { cat: '计算',       vendor: '华为', model: 'Atlas 900 A3 SuperPoD', code: '02350WBX', qty: 1,  ver: 'V100R001C001', lifecycle: 'TR5', unitSpace: '42 U', totalSpace: '42 U',  unitPower: '54 kW', totalPower: '54 kW',  source: 'BOQ' },
  { cat: '存储',       vendor: '华为', model: 'OceanStor A800',          code: '02352UGC', qty: 1,  ver: 'V100R001C002', lifecycle: 'GA', unitSpace: '4 U',  totalSpace: '4 U',   unitPower: '2.8 kW', totalPower: '2.8 kW', source: 'BOQ' },
  { cat: '存储',       vendor: '华为', model: 'OceanStor Pacific 9550',  code: '02352JGC', qty: 9,  ver: 'V100R001C002', lifecycle: 'GA', unitSpace: '2 U',  totalSpace: '18 U',  unitPower: '1.2 kW', totalPower: '10.8 kW', source: 'BOQ' },
  { cat: 'DME 服务器', vendor: '华为', model: 'TaiShan 200',             code: '02312GRW', qty: 1,  ver: 'V100R001C004', lifecycle: 'GA', unitSpace: '2 U',  totalSpace: '2 U',   unitPower: '0.8 kW', totalPower: '0.8 kW', source: 'BOQ' },
  { cat: 'CCAE 服务器',vendor: '华为', model: 'TaiShan 200',             code: '02312GRW', qty: 3,  ver: 'V100R001C005', lifecycle: 'GA', unitSpace: '2 U',  totalSpace: '6 U',   unitPower: '0.8 kW', totalPower: '2.4 kW', source: 'BOQ' },
  { cat: 'NCE 服务器', vendor: '华为', model: 'TaiShan 200',             code: '02312GRW', qty: 3,  ver: 'V100R001C007', lifecycle: 'GA', unitSpace: '2 U',  totalSpace: '6 U',   unitPower: '0.8 kW', totalPower: '2.4 kW', source: 'BOQ' },
];

/* 3. 部件配置信息 */
export const INTEL_PARTS = [
  { cat: 'DPU',    code: 'BF3-DPU-400', name: 'BlueField-3 DPU 智能网卡', vendor: '伙伴', source: '自动解析' },
  { cat: 'CPU',    code: 'Ascend-910C', name: '昇腾 910C 训练处理器',     vendor: '华为', source: '自动解析' },
  { cat: '网卡',   code: 'CX7-400G',    name: 'ConnectX-7 400G NIC',      vendor: '伙伴', source: '人工录入' },
];

/* 4. 软件配置信息 · 含备注 */
export const SOFTWARE_STACK = [
  { type: '昇腾训练版本', isHW: true,  software: 'Ascend Training Solution', ver: '24.0.0',           source: '自动解析', conflict: '', remark: '' },
  { type: '昇腾推理版本', isHW: true,  software: 'Ascend Inference Solution', ver: '24.0.0',           source: '自动解析', conflict: '', remark: '' },
  { type: '操作系统',     isHW: false, software: 'FresBSD',                   ver: '—',                source: '人工录入', conflict: 'BOQ 未列项 · HLD 指定 FresBSD', remark: '待客户确认' },
  { type: 'ASCEND HDK',  isHW: true,  software: 'ASCEND HDK',                ver: 'V100R001C020',     source: '自动解析', conflict: '', remark: '' },
  { type: '存储 DPC',     isHW: true,  software: '存储 DPC',                  ver: 'V100R001C020',     source: '自动解析', conflict: '', remark: '' },
  { type: 'CCAE AGENT',  isHW: true,  software: 'iMaster CCAE',              ver: 'V100R025C20SPC010',source: '自动解析', conflict: 'BOQ V100R025C20 vs HLD V100R025C10', remark: '已生成风险 R-002' },
  { type: 'CANN',        isHW: true,  software: 'CANN',                       ver: 'CANN 8.0.1',       source: '自动解析', conflict: '', remark: '' },
];

/* 5.1 网络平面配置 */
export const NETWORK_PLANES = [
  { type: '参数面汇聚交换机',      vendor: '华为', model: 'XH9330-128EO', ver: 'V100R001C020', qty: 64,  source: '人工录入', note: '' },
  { type: '参数面接入交换机',      vendor: '华为', model: 'XH9930-128DQ', ver: 'V100R001C020', qty: 174, source: '人工录入', note: '' },
  { type: '样本面-存储接入交换机', vendor: '华为', model: 'XH9930-128DQ', ver: 'V100R001C020', qty: 6,   source: '人工录入', note: '' },
  { type: '样本面-汇聚交换机',     vendor: '华为', model: 'XH9930-128DQ', ver: 'V100R001C020', qty: 16,  source: '人工录入', note: '' },
  { type: '样本面-计算接入交换机', vendor: '华为', model: 'XH9930-128DQ', ver: 'V100R001C020', qty: 22,  source: '人工录入', note: '' },
];

/* 5.2 服务器网络配置 */
export const SERVER_NETWORK = [
  { clusterId: 'CLU-JD3-01', planeType: '样本面',     serverModel: 'Atlas 900 A3 计算节点', portCount: 8, nicModel: 'ConnectX-7 400G', qty: 384 },
  { clusterId: 'CLU-JD3-01', planeType: '带内管理面', serverModel: 'TaiShan 200 管理节点',  portCount: 2, nicModel: 'SP6810',          qty: 7 },
  { clusterId: 'CLU-JD3-01', planeType: '业务面',     serverModel: 'OceanStor 存储节点',    portCount: 4, nicModel: '—',               qty: 10 },
  { clusterId: 'CLU-JD3-01', planeType: '带外管理面', serverModel: 'TaiShan 200 管理节点',  portCount: 2, nicModel: 'SP6810',          qty: 7 },
];

/* 共平面类型多选 */
export const COMMON_PLANE_TYPES = [
  { key: 'outband',  label: '带外管理面' },
  { key: 'inband',   label: '带内管理面' },
  { key: 'business', label: '业务面' },
  { key: 'sample',   label: '样本面' },
];

/* 7.1 服务交付界面 · 交付界面：华为 / 伙伴 / 客户 */
export const SERVICE_CONFIG = [
  { major: '硬件安装',       item: '数通设备安装',          channel: '伙伴',  source: 'BOQ' },
  { major: '硬件安装',       item: '存储设备安装',          channel: '伙伴',  source: 'BOQ' },
  { major: '硬件安装',       item: '昇腾服务器安装',        channel: '华为',  source: 'BOQ' },
  { major: '规划设计与实施', item: '数通设备规划设计与实施', channel: '华为',  source: 'BOQ' },
  { major: '规划设计与实施', item: '存储设备规划设计与实施', channel: '华为',  source: 'BOQ' },
  { major: '规划设计与实施', item: '昇腾设备规划设计与实施', channel: '华为',  source: 'BOQ' },
  { major: '技术集成服务',   item: '数通设备技术集成服务',   channel: '华为',  source: 'BOQ' },
  { major: '技术集成服务',   item: '存储设备技术集成服务',   channel: '华为',  source: 'BOQ' },
  { major: '技术集成服务',   item: '昇腾设备技术集成服务',   channel: '华为',  source: 'BOQ' },
  { major: '使能服务',       item: 'AI 计算使能服务',        channel: '华为',  source: 'BOQ' },
  { major: '运维服务',       item: '数通设备运维服务',       channel: '客户',  source: 'BOQ' },
  { major: '运维服务',       item: '存储设备运维服务',       channel: '华为',  source: 'BOQ' },
  { major: '运维服务',       item: '昇腾设备运维服务',       channel: '华为',  source: 'BOQ' },
];

/* 7.2 服务内容 · BOQ 解析 */
export const SERVICE_CONTENT = [
  { name: '昇腾集群部署调测', content: '384 节点上架、液冷压测、ZTP 开局', qty: 1, unit: '套', source: 'BOQ' },
  { name: 'RDMA 全互联验证',  content: '400G RoCE 全互联压测与验收报告',   qty: 1, unit: '项', source: 'BOQ' },
  { name: 'CCAE 平台集成',    content: 'iMaster CCAE 对接客户运维平台',    qty: 1, unit: '套', source: 'BOQ' },
  { name: 'AI 使能培训',      content: 'MindStudio / CANN 开发培训 3 天',  qty: 2, unit: '人天', source: '建议书' },
];

/* 预集成预验证需求 */
export const PRE_INTEGRATION = [
  { cat: '回测版本配置', desc: '昇腾 ATLAS A3 900 Superpod*1 CCAE V1R2 版本未确认',     hw: 'ATALAS A3 900 Superpod*1 TAISHAN 2280 服务器', sw: 'Ascend Training 1.00 + CCAE V1R2', owner: 'TD', state: '已完成', date: '20260511' },
  { cat: '跨网络配置',  desc: 'DT 950 产品系列与 HCS V1R2 物认匹配',                    hw: 'ATALAS A3 900 Superpod*1 TAISHAN 2280 服务器', sw: 'Ascend Training 1.00 + CCAE V1R2', owner: 'TD', state: '未完成', date: 'N/A' },
  { cat: '三方集成',    desc: 'ATALAS A3 产品本身移动九天平台 KBS 兼容性测试',           hw: 'ATALAS A3 900 Superpod*1 TAISHAN 2280 服务器', sw: 'Ascend Training 1.00 + CCAE V1R2', owner: 'TD', state: '未完成', date: 'N/A' },
];

/* 机房机柜 (CAD 解析) */
export const ROOMS_RACKS = [
  { room: 'A1-RM01', type: '液冷柜', power: '54 KW', qty: 8,  note: 'CAD 自动' },
  { room: 'A1-RM01', type: '灵衡柜', power: '36 KW', qty: 4,  note: 'CAD 自动' },
  { room: 'A1-RM01', type: '网络柜', power: '12 KW', qty: 6,  note: 'CAD 自动' },
  { room: 'A1-RM01', type: '存储柜', power: '8 KW',  qty: 6,  note: 'CAD 自动' },
  { room: 'A1-RM02', type: '液冷柜', power: '54 KW', qty: 8,  note: 'CAD 自动' },
  { room: 'A1-RM02', type: '灵衡柜', power: '36 KW', qty: 6,  note: 'CAD 自动' },
  { room: 'B2-RM02', type: '液冷柜', power: '—',     qty: 0,  note: '客户未提供 CAD · 待 TD 手填' },
];

/* ───────────────────────────────────────── */

/* SVG 校正：版本号下拉 ▽ ——
 * 主区右上角单一下拉，DTRB/DRB/合同 LLD 三个特殊版本用色块高亮（SVG L174）
 * 旧的 v0.x 草稿历史按时间倒序排在下面（演示用 2 条） */
/* 元数据信息（按快照）*/
export const PROPOSAL_META_BY_SNAP = {
  dtrb:     { docVersion: 'v1.0', compiledAt: '2026-05-26', updateSummary: '首版 DTRB 基线：补齐 1 项目背景、2–5 配置章节；6 机房 CAD 待补；11/12 待合同后冻结' },
  drb:      { docVersion: 'v1.0', compiledAt: '2026-05-30', updateSummary: '相比 DTRB v1.0：修订 6 机房配电、4 软件 CCAE 版本、9.1 新增 ConnectX-7 风险、12 高阶计划' },
  contract: { docVersion: 'v1.0', compiledAt: '2026-06-02', updateSummary: '相比 DRB v1.0：修订 1.2 合同 BOQ 对齐、9.1 纳入合同罚则、11 验收策略部分、12 实施计划排期中' },
  exec:     { docVersion: 'v1.0', compiledAt: '2026-06-04', updateSummary: '相比合同 v1.0：新增 11 验收性能指标、12 实施计划锁定、5.2 服务器网络、2 设备 ConnectX-7 闭环' },
};

/* 1. 项目背景 */
export const PROJECT_BACKGROUND = {
  oppCode: 'K1903',
  oppName: '京东三期',
  industry: '金融 · 大模型',
  customer: '京东',
  projectScene: '新址新建',
  background: '客户计划 Q3 上线 384 节点训练集群，替代现有 GPU 租赁方案，要求算力自主可控与液冷节能。',
  goal: '建设 384 节点昇腾训练集群，支持大模型训练与推理业务，实现算力自主可控。',
  scope: '算力底座（Atlas 900 A3 SuperPoD）+ 网络（400G RoCE）+ 存储（OceanStor）+ 液冷系统，含机房改造与上电。',
  planSummary: '客户里程碑：2026-06-01 机房就绪 → 2026-07-20 到货 → 2026-08-10 上线；与第 12 章计划联动',
  location: '和林格尔数据中心',
  pd: '李伟 · 00603554',
  td: '何博 · 00623478',
  pcm: '王婷 · 00640215',
};

/* 1.2 合同信息 · 支持多合同 */
export const CONTRACT_LIST = [
  {
    id: 'CON-2026-K1903-001', name: '智算一期主合同', amount: '¥ 1.84 亿', signDate: '2026-06-04', party: '客户甲',
    boq: [
      { name: 'Atlas 900 A3 SuperPoD', saleType: '硬件', qty: 1 },
      { name: 'ConnectX-7 400G NIC', saleType: '部件', qty: 192 },
      { name: '昇腾集群部署调测', saleType: '服务', qty: 1 },
    ],
  },
  {
    id: 'CON-2026-K1903-SVC', name: '维保与服务附属协议', amount: '¥ 0.12 亿', signDate: '2026-06-04', party: '客户甲',
    boq: [
      { name: '5 年 NBD+4H 维保', saleType: '维保', qty: 1 },
      { name: 'AI 使能培训', saleType: '培训', qty: 2 },
    ],
  },
];

/* ── §10 维保与维护策略 ── */
export const MAINT_STRATEGY = [
  { seq: 1, model: 'Atlas 900 A3 SuperPoD', warranty: '按华为标准保修政策', maint: '5 年', maintType: 'NBD+4H',  start: '2026-07-01', end: '2031-06-30', eos: '2033-12-31', overEos: '否', approval: '—' },
  { seq: 2, model: 'OceanStor A800',         warranty: '按华为标准保修政策', maint: '3 年', maintType: '7×24H',   start: '2026-07-01', end: '2029-06-30', eos: '2032-12-31', overEos: '否', approval: '—' },
  { seq: 3, model: 'OceanStor Pacific 9550', warranty: '按华为标准保修政策', maint: '3 年', maintType: '7×24H',   start: '2026-07-01', end: '2029-06-30', eos: '2032-12-31', overEos: '否', approval: '—' },
  { seq: 4, model: 'CE6881-48S6CQ 交换机',   warranty: '按华为标准保修政策', maint: '3 年', maintType: 'NBD+8H',  start: '2026-07-01', end: '2029-06-30', eos: '2030-12-31', overEos: '否', approval: '—' },
  { seq: 5, model: 'TaiShan 200 服务器',      warranty: '按华为标准保修政策', maint: '3 年', maintType: 'NBD+4H',  start: '2026-07-01', end: '2029-06-30', eos: '2031-12-31', overEos: '否', approval: '—' },
];
export const SLA_REQUIREMENTS = [
  { level: 'P1 · 紧急', def: '业务中断、严重影响生产', coverage: '7×24 小时', response: '15 分钟', restore: '2 小时', resolve: '8 小时' },
  { level: 'P2 · 严重', def: '核心功能受损、性能下降 50%+', coverage: '7×24 小时', response: '30 分钟', restore: '4 小时', resolve: '24 小时' },
  { level: 'P3 · 一般', def: '非核心功能异常，有临时方案', coverage: '5×8 小时', response: '2 小时', restore: '8 小时', resolve: '72 小时' },
  { level: 'P4 · 低级', def: '优化建议、咨询类', coverage: '5×8 小时', response: '下一工作日', restore: '—', resolve: '1 周' },
];

/* ── §11 责任矩阵 (RACI) ── */
export const RACI_ROWS = [
  /* 公共 */
  { stack: '公共', cat: '项目管理', act: '计划进度管理、沟通管理、风险管理、变更管理、问题管理、质量管理、采购管理、验收管理等', gts: 'R', hw: '', partner: 'S', customer: 'S' },
  { stack: '公共', cat: '计算-工程安装', act: '工程勘测',   gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '公共', cat: '计算-工程安装', act: '设备签收',   gts: 'S', hw: '', partner: '', customer: 'R' },
  { stack: '公共', cat: '计算-工程安装', act: '硬件部署',   gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '公共', cat: '计算-工程安装', act: '硬件初始化', gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '公共', cat: '计算-工程安装', act: '固件升级',   gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '公共', cat: '计算-工程安装', act: '硬件压测',   gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '公共', cat: '计算-工程安装', act: '硬件验收',   gts: 'S', hw: '', partner: '', customer: 'R' },
  { stack: '公共', cat: '计算-规划设计与实施', act: '规划设计',       gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '公共', cat: '计算-规划设计与实施', act: 'OS安装',         gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '公共', cat: '计算-规划设计与实施', act: '计算服务软件安装', gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '公共', cat: '计算-规划设计与实施', act: '单机综合测试',   gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '公共', cat: '计算-规划设计与实施', act: '单机测试',       gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '公共', cat: '计算-规划设计与实施', act: '管理子系统验收', gts: 'S', hw: '', partner: '', customer: 'R' },
  { stack: '公共', cat: '计算-规划设计与实施', act: '项目管理',       gts: 'R', hw: '', partner: '', customer: 'R' },
  { stack: '公共', cat: '计算-规划设计与实施', act: '站点工勘',       gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '公共', cat: '计算-规划设计与实施', act: '需求调研',       gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '公共', cat: '计算-规划设计与实施', act: '硬件安装',       gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '公共', cat: '计算-规划设计与实施', act: '系统部署',       gts: 'R', hw: '', partner: '', customer: 'S' },
  /* 硬件底座 */
  { stack: '硬件底座', cat: '存储-规划设计与集成', act: '存储网络连接', gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '硬件底座', cat: '存储-规划设计与集成', act: '基础功能配置', gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '硬件底座', cat: '存储-规划设计与集成', act: '增值特性配置', gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '硬件底座', cat: '存储-规划设计与集成', act: '验收方案',     gts: 'R', hw: '', partner: '', customer: 'R' },
  { stack: '硬件底座', cat: '存储-规划设计与集成', act: '验收测试',     gts: 'S', hw: '', partner: '', customer: 'R' },
  { stack: '硬件底座', cat: '存储-规划设计与集成', act: '项目移交',     gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '硬件底座', cat: '存储-规划设计与集成', act: '存储升级',     gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '硬件底座', cat: '网络-工程安装',       act: '工程安装',     gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '硬件底座', cat: '网络-规划设计与实施', act: '规划设计与实施', gts: 'R', hw: '', partner: '', customer: 'S' },
  /* 算存网 */
  { stack: '算存网', cat: '算存网-集群集成', act: '集群系统需求调研',     gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '算存网', cat: '算存网-集群集成', act: '集群系统规划设计',     gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '算存网', cat: '算存网-集群集成', act: '集群系统对接联网',     gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '算存网', cat: '算存网-集群集成', act: '参数面集合通信测试',   gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '算存网', cat: '算存网-集群集成', act: '集群性能测试',         gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '算存网', cat: '算存网-集群集成', act: '集群稳定性测试（训练）', gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '算存网', cat: '算存网-集群集成', act: '集群初始化调优（训练）', gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '算存网', cat: '算存网-集群集成', act: '集群试运行（可选）',   gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '算存网', cat: '算存网-集群集成', act: '集群验收',             gts: 'S', hw: '', partner: '', customer: 'R' },
  { stack: '算存网', cat: '算存网-集群集成', act: '需求环境调研',         gts: '', hw: 'R', partner: '', customer: '' },
  { stack: '算存网', cat: '算存网-集群集成', act: '云网规划设计',         gts: '', hw: 'R', partner: '', customer: '' },
  /* AI平台 */
  { stack: 'AI平台', cat: 'HCS+ModelArts-规划设计与实施', act: '云服务设计',     gts: '', hw: 'R', partner: '', customer: '' },
  { stack: 'AI平台', cat: 'HCS+ModelArts-规划设计与实施', act: '资源池设计',     gts: '', hw: 'R', partner: '', customer: '' },
  { stack: 'AI平台', cat: 'HCS+ModelArts-规划设计与实施', act: 'LLD设计',         gts: '', hw: 'R', partner: '', customer: '' },
  { stack: 'AI平台', cat: 'HCS+ModelArts-规划设计与实施', act: 'HCS安装实施',     gts: '', hw: 'R', partner: '', customer: '' },
  { stack: 'AI平台', cat: 'HCS+ModelArts-规划设计与实施', act: 'ModelArts安装实施', gts: '', hw: 'R', partner: '', customer: '' },
  { stack: 'AI平台', cat: 'HCS+ModelArts-规划设计与实施', act: '平台测试与验收支持', gts: '', hw: 'S', partner: '', customer: '' },
  { stack: 'AI平台', cat: 'DCS-规划设计与实施', act: '需求分析', gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: 'AI平台', cat: 'DCS-规划设计与实施', act: '整体规划', gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: 'AI平台', cat: 'DCS-规划设计与实施', act: '系统设计', gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: 'AI平台', cat: 'DCS-规划设计与实施', act: '集成实施', gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: 'AI平台', cat: 'DCS-规划设计与实施', act: '项目验收', gts: 'S', hw: '', partner: '', customer: 'R' },
  { stack: 'AI平台', cat: 'DCS-规划设计与实施', act: '系统移交', gts: 'R', hw: '', partner: '', customer: 'S' },
  /* 模型 */
  { stack: '模型', cat: 'AI计算使能-模型部署支持', act: '模型部署支持-训练', gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '模型', cat: 'AI计算使能-模型部署支持', act: '模型部署支持-推理', gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '模型', cat: 'AI计算使能-AI计算软件栈技术支持', act: '问题定位', gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '模型', cat: 'AI计算使能-AI计算软件栈技术支持', act: '使用支持', gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '模型', cat: 'AI计算使能-模型部署样例演示', act: '人员组织，协调场地环境', gts: 'S', hw: '', partner: '', customer: 'R' },
  { stack: '模型', cat: 'AI计算使能-模型部署样例演示', act: '开发环境搭建演示', gts: 'R', hw: '', partner: '', customer: 'S' },
  { stack: '模型', cat: 'AI计算使能-模型部署样例演示', act: '模型部署演示', gts: 'R', hw: '', partner: '', customer: 'S' },
  /* 应用 */
  { stack: '应用', cat: '应用', act: '应用', gts: '', hw: '', partner: '', customer: '' },
  { stack: '应用', cat: '应用', act: '应用', gts: '', hw: '', partner: '', customer: '' },
  /* 公共 · 验收签发 */
  { stack: '公共', cat: '初验PAC', act: '签发初验PAC', gts: 'C', hw: '', partner: 'R/A', customer: '' },
  { stack: '公共', cat: '终验FAC', act: '签发终验FAC', gts: 'C', hw: '', partner: 'R/A', customer: '' },
];

/* 9.1 风险列表 · 统一风险表字段 */
export const PROPOSAL_RISKS = [
  { id: 'R-001', riskPoint: '配电改造延期', desc: 'B2-RM02 配电改造延期 9 天，影响上电节点', impact: '上电节点顺延 9 天', type: '进度', level: '高', source: '售前公开风险', identifiedAt: '2026-05-18', closedAt: '', strategy: '协调甲方提前介入，临时柴发兜底', owner: '何博', state: '处理中' },
  { id: 'R-002', riskPoint: 'ConnectX-7 数量冲突', desc: 'BOQ 写 192 / HLD 写 384 不一致', impact: '组网带宽与器件可交付性', type: '技术', level: '高', source: '文档不一致风险', identifiedAt: '2026-05-22', closedAt: '', strategy: '评审会 PD 拍板口径，重出 LLD', owner: '李伟', state: '处理中' },
  { id: 'R-003', riskPoint: 'CAD 桥架缺失', desc: 'B2-RM02 机柜桥架路由 CAD 缺失', impact: '机房物理布局不完整', type: '机房', level: '中', source: '工勘', identifiedAt: '2026-05-10', closedAt: '2026-05-25', strategy: 'TD 手填机柜归位', owner: '何博', state: '已关闭' },
  { id: 'R-004', riskPoint: '数据出境合规', desc: 'BOQ 含客户机房信息，需 OCC 审批', impact: '合同交付合规', type: '合规', level: '中', source: '售前公开风险', identifiedAt: '2026-05-12', closedAt: '2026-05-28', strategy: '已提交 OCC 审批通过', owner: '王婷', state: '已关闭' },
  { id: 'R-005', riskPoint: 'CANN 兼容性', desc: 'CANN 版本与客户 AI 框架兼容性未验证', impact: '预集成验证', type: '集成', level: '低', source: '文档不一致风险', identifiedAt: '2026-05-26', closedAt: '', strategy: '补充预集成测试用例', owner: '何博', state: '处理中' },
];
/* 9.2 假设 · 数据湖 + 人工录入（前端展示序号 / 假设项 / 来源） */
export const PROPOSAL_ASSUMPTIONS = [
  { seq: 1, item: '客户机房 A1/A1-RM02 在 2026-06-01 前完成电力改造', source: '数据湖', owner: '客户甲', fulfill: '客户书面确认', closed: '待确认' },
  { seq: 2, item: '100G 光模块由客户自采，ETA 不晚于 2026-05-28', source: '人工录入', owner: '客户甲', fulfill: '物流单确认', closed: '待确认' },
  { seq: 3, item: 'CCAE V1R2 版本 5/30 前通过回测，版本配套无风险', source: '数据湖', owner: '何博', fulfill: '版本配套查询', closed: '已闭环' },
  { seq: 4, item: '施工队 07 可在 6/2 进场，无外部项目冲突', source: '人工录入', owner: '施工队', fulfill: '调度确认函', closed: '已闭环' },
];

/* 11. 验收策略 · 所有快照可见 */
export const ACCEPTANCE_ITEMS = [
  { cat: '到货',     scheme: '设备到货清点', standard: '型号/数量与 BOQ 一致，外观无损', milestone: '到货签收', doc: '到货验收单', payment: '20%', paymentMilestone: '到货' },
  { cat: '安装 PAC', scheme: '整机柜 ST 测试', standard: 'GPU 数量与 BOQ 一致，误码率 ≤ 1e-12', milestone: '部署调测完成', doc: '验收测试报告', payment: '30%', paymentMilestone: '安装 PAC' },
  { cat: '安装 PAC', scheme: 'RDMA 全互联压测', standard: '400G 带宽达标，时延 p99 ≤ 2μs', milestone: '集群联调完成', doc: '网络测试报告', payment: '—', paymentMilestone: '—' },
  { cat: '维保',     scheme: '维保服务启动', standard: '维保策略与 SLA 合同一致', milestone: '维保生效', doc: '维保确认函', payment: '—', paymentMilestone: '—' },
  { cat: '培训',     scheme: 'AI 使能培训', standard: '参训人数 ≥ 合同，考核通过', milestone: '培训完成', doc: '培训签到表', payment: '—', paymentMilestone: '—' },
  { cat: '安装 PAC', scheme: '整体性能基线', standard: 'RTO ≤ 5s / p99 ≤ 30ms', milestone: '整体压测完成', doc: '性能基线报告', payment: '20%', paymentMilestone: '终验' },
  { cat: '安装 PAC', scheme: '客户签收移交', standard: '文档齐套，客户代表签字', milestone: '客户验收', doc: '移交确认函', payment: '30%', paymentMilestone: '终验' },
];

/* 12. 计划 · 活动明细（参考计划模块排期表） */
export const PLAN_ACTIVITIES = [
  {
    name: 'L1机房准备',
    start: '2025-08-01',
    end: '',
    actualStart: '',
    actualEnd: '',
    owner: '王长龙',
    unit: '',
    status: '已派发',
    progress: 90,
    progressTone: 'blue' as const,
  },
  {
    name: '机房改造实施',
    start: '2025-12-15',
    end: '',
    actualStart: '',
    actualEnd: '',
    owner: '王长龙',
    unit: '',
    status: '已派发',
    progress: 90,
    progressTone: 'blue' as const,
  },
  {
    name: '工程勘测',
    start: '2025-08-16',
    end: '2025-09-20',
    actualStart: '2026-01-10',
    actualEnd: '2026-02-28',
    owner: '王长龙',
    unit: '',
    status: '已完成',
    progress: 100,
    progressTone: 'green' as const,
  },
];

/* 12. 计划 · 摘要（计划模块回写，前端暂不展示） */
export const PLAN_CHAPTER = {
  scheduleResult: '站/机房 14 · 货 3 批 · 人 12 队（计划模块 v0.8 输出）',
  highLevel: '2026-05-30 高阶：到货 7/20 · 上电 8/1 · 联调 8/10 · 验收 8/15',
  implementation: '条件锁定后：PoD#01-04 安装压缩 2 天 · B2 配电 +5 天缓冲已纳入',
};

export const DELIVER_RISKS = [
  { level: 'high', title: 'BOQ vs HLD · ConnectX-7 数量不一致', action: '下午评审会让 PD 拍板 192/384' },
  { level: 'high', title: '组网拓扑 · 样本面接入设备未齐套', action: '补全 CE6881 数量或调整 HLD' },
  { level: 'med', title: '§5 机房物理 · CAD 桥架路由缺失', action: 'TD 补 CAD 或手填机柜归位' },
  { level: 'med', title: 'k8s 平台版本待客户确认', action: '发假设清单给客户 · 5/30 前回复' },
];

export type SnapKey = keyof typeof SNAPSHOTS;

/* 右上角版本历史下拉（参考图四） */
export const PROPOSAL_VERSION_HISTORY: {
  snapKey: SnapKey;
  label: string;
  status: 'published' | 'draft';
  tone: 'green' | 'amber';
}[] = [
  { snapKey: 'dtrb', label: 'V1.0_20260526144200_DTRB', status: 'published', tone: 'green' },
  { snapKey: 'drb', label: 'V1.0_20260530101500_DRB', status: 'draft', tone: 'amber' },
];