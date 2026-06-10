/* 早期接入 · 合同 → BOQ → 设备/服务 三层数据
 *
 * 5.27 早会拍板的数据形态：
 *   - 合同列表只展示 3 个月内还未交付完的（AM-23 筛选规则）
 *   - 每条合同含：编码、机会点、收入触发比例、关联 BOQ 数组
 *   - 每个 BOQ 含：BOQ 名称、销售类型（设备/服务/设备+服务）、状态、文件
 *   - BOQ 下挂部件清单（AM-31 裸 BOQ 不加工）
 *   - 服务分 5 大类（AM-35）
 *
 * 真实场景里这些数据从陈卓的接口拉，本地只 mock 给演示用。
 */

/* 合同列表 · 已通过 3 个月筛选 */
export const CONTRACTS = [
  {
    id: 'CON-K1903-001',
    name: 'AI 训推一体集群一期 · 智算 Q3',
    oppCode: 'OPP-2026-K1903',                  // 机会点编码
    signedAt: '2026-04-12',
    orderVersion: 'V3.0',                        // 订单版本号
    orderStatus: '已发布',                        // 订单状态
    createdAt: '2026-04-10',                      // 创建日期
    publishedAt: '2026-04-12',                    // 发布日期
    deliveryDeadline: '2026-07-15',
    revenueTriggerPct: 50,                       // 收入触发比例 (AM-24)
    amount: '¥ 1.84 亿',
    status: 'signed',                            // signed | unsigned
    boqs: ['BOQ-K1903-D01', 'BOQ-K1903-D02', 'BOQ-K1903-S01', 'BOQ-K1903-S02'],
  },
  {
    id: 'CON-K1903-002',
    name: 'AI 训推一体集群一期 · 网络扩容',
    oppCode: 'OPP-2026-K1903',
    signedAt: '2026-04-20',
    orderVersion: 'V1.0',
    orderStatus: '已发布',
    createdAt: '2026-04-18',
    publishedAt: '2026-04-20',
    deliveryDeadline: '2026-06-30',
    revenueTriggerPct: 30,
    amount: '¥ 2,840 万',
    status: 'signed',
    boqs: ['BOQ-K1903-N01'],
  },
  {
    id: 'CON-K1903-003',
    name: '智算 Q3 · 维保培训补充合同',
    oppCode: 'OPP-2026-K1903',
    signedAt: '2026-05-08',
    orderVersion: 'V1.0',
    orderStatus: '草稿',
    createdAt: '2026-05-06',
    publishedAt: '2026-05-08',
    deliveryDeadline: '2027-05-08',
    revenueTriggerPct: 20,
    amount: '¥ 980 万',
    status: 'signed',
    boqs: ['BOQ-K1903-M01'],
  },
];

/* BOQ 字典 · boqVersion 是业务版本号（PD/TD 维护，区分销售迭代）
 * version 是状态机：draft | published（草稿态可上传）
 */
export const BOQS = {
  'BOQ-K1903-D01': {
    id: 'BOQ-K1903-D01',
    name: '算力底座 · 计算柜 BOQ',
    saleType: '设备',              // 设备 / 服务 / 设备+服务
    version: 'draft',              // 草稿状态也可上传
    boqVersion: 'V3.0',
    fileName: 'BOQ-K1903-D01-v3-draft.xlsx',
    size: '184 KB',
    items: 47,
    updatedAt: '2026-05-25',
    contractId: 'CON-K1903-001',
  },
  'BOQ-K1903-D02': {
    id: 'BOQ-K1903-D02',
    name: '存储设备 BOQ',
    saleType: '设备',
    version: 'published',
    boqVersion: 'V2.0',
    fileName: 'BOQ-K1903-D02-v2.xlsx',
    size: '76 KB',
    items: 18,
    updatedAt: '2026-04-20',
    contractId: 'CON-K1903-001',
  },
  'BOQ-K1903-N01': {
    id: 'BOQ-K1903-N01',
    name: '网络扩容设备 BOQ',
    saleType: '设备',
    version: 'published',
    boqVersion: 'V1.0',
    fileName: 'BOQ-K1903-N01-v1.xlsx',
    size: '64 KB',
    items: 12,
    updatedAt: '2026-04-22',
    contractId: 'CON-K1903-002',
  },
  'BOQ-K1903-S01': {
    id: 'BOQ-K1903-S01',
    name: '算力集成服务 BOQ',
    saleType: '服务',
    version: 'published',
    boqVersion: 'V1.0',
    fileName: 'BOQ-K1903-S01-v1.xlsx',
    size: '42 KB',
    items: 8,
    updatedAt: '2026-04-12',
    contractId: 'CON-K1903-001',
  },
  'BOQ-K1903-S02': {
    id: 'BOQ-K1903-S02',
    name: '算力使能优化服务 BOQ',
    saleType: '服务',
    version: 'published',
    boqVersion: 'V1.0',
    fileName: 'BOQ-K1903-S02-v1.xlsx',
    size: '38 KB',
    items: 6,
    updatedAt: '2026-04-15',
    contractId: 'CON-K1903-001',
  },
  'BOQ-K1903-M01': {
    id: 'BOQ-K1903-M01',
    name: '维保培训服务 BOQ',
    saleType: '设备+服务',
    version: 'published',
    boqVersion: 'V1.0',
    fileName: 'BOQ-K1903-M01-v1.xlsx',
    size: '36 KB',
    items: 9,
    updatedAt: '2026-05-08',
    contractId: 'CON-K1903-003',
  },
};

/* ───────────── 设备 BOQ 解析结果（AM-30 / AM-31 / AM-32 / AM-33）
 * 5.27 拍板看 7 部件：CPU / NPU / Mem / PCIe / DPU / 存储 / 网络
 * 厂商列加在 编码 和 名称 之间
 * dataSource: BOQ (自动解析) / 人工 (手填) / HLD (设计文档补录)
 * 后两列：冲突说明 + 备注 (AM-27 / D-27)
 */
export const PARSED_DEVICES = [
  /* CPU */
  { code: '02351NEC',  vendor: '华为',   part: 'CPU',  name: 'Kunpeng-920 7270', qty: 384, dataSource: 'BOQ',     conflict: '',                          note: '' },
  /* NPU */
  { code: '02350TYU',  vendor: '华为',   part: 'NPU',  name: 'Atlas 910 训练卡',  qty: 1536, dataSource: 'BOQ',    conflict: '',                          note: '主力计算单元' },
  { code: '02351MFD',  vendor: '华为',   part: 'NPU',  name: 'Atlas 300I 推理卡', qty: 384, dataSource: 'BOQ',     conflict: '',                          note: '' },
  /* Mem */
  { code: '02350QHA',  vendor: '华为',   part: 'Mem',  name: 'DDR5 64GB 5600',    qty: 6144, dataSource: 'BOQ',    conflict: '',                          note: '' },
  { code: '02350HBM',  vendor: '华为',   part: 'Mem',  name: 'HBM3 64GB',         qty: 1536, dataSource: 'BOQ',    conflict: '',                          note: 'NPU 板载' },
  /* PCIe */
  { code: '02351PNX',  vendor: '华为',   part: 'PCIe', name: '100G NIC 双口',     qty: 768, dataSource: 'BOQ',     conflict: '',                          note: '' },
  { code: 'NX-Q5780',  vendor: 'Mellanox', part: 'PCIe', name: 'ConnectX-7 400G', qty: 192, dataSource: '人工',   conflict: 'HLD 写 384 / BOQ 写 192',    note: '客户特殊采购 · 待确认' },
  /* DPU (5.27 新增 R-2) */
  { code: '02352DPU',  vendor: '华为',   part: 'DPU',  name: 'BlueField-3 智能网卡', qty: 384, dataSource: 'BOQ', conflict: '',                          note: '加速 RDMA + 存储卸载' },
  /* 存储 (5.27 SVG "补充存储") */
  { code: '02353SSD',  vendor: '华为',   part: 'Storage', name: 'OceanStor 全闪存储 64T', qty: 12, dataSource: 'BOQ', conflict: '',                       note: '训练数据集主存' },
  { code: '02351CV7',  vendor: '华为',   part: 'Storage', name: 'NVMe SSD 7.68TB',     qty: 768, dataSource: 'BOQ', conflict: '',                         note: '节点本地缓存' },
  /* 网络 (5.27 SVG "补充网络") */
  { code: '02354SW1',  vendor: '华为',   part: 'Network', name: 'CE16800 核心交换机 400G', qty: 8,  dataSource: 'BOQ', conflict: '',                      note: '脊层' },
  { code: '02354SW2',  vendor: '华为',   part: 'Network', name: 'CE9860 叶节点交换机 100G', qty: 48, dataSource: 'BOQ', conflict: '',                     note: '叶层' },
  { code: '02354SW3',  vendor: '华为',   part: 'Network', name: 'NetEngine 路由器',     qty: 4,   dataSource: 'HLD',  conflict: 'BOQ 未列 / HLD 补录',     note: '出口路由' },
];

/* ───────────── 服务 BOQ 解析结果（AM-35）
 * 5.27 拍板服务 5 大类：算力集成 / 算力使能优化 / 智算上路 / 维保 / 培训
 */
export const PARSED_SERVICES = [
  { code: 'SVC-001', category: '算力集成',     name: 'AI 训推集群上电点亮服务',   qty: 1, unit: '套', period: '6 个月',  contractId: 'CON-K1903-001' },
  { code: 'SVC-002', category: '算力集成',     name: '机房改造工程服务',         qty: 14, unit: '机房', period: '3 个月', contractId: 'CON-K1903-001' },
  { code: 'SVC-003', category: '算力使能优化', name: '推理模型蒸馏优化',         qty: 12, unit: '人月', period: '6 个月', contractId: 'CON-K1903-001' },
  { code: 'SVC-004', category: '算力使能优化', name: 'NPU 利用率提升咨询',       qty: 6,  unit: '人月', period: '3 个月', contractId: 'CON-K1903-001' },
  { code: 'SVC-005', category: '智算上路',     name: 'AI 业务首批上线护航',     qty: 1,  unit: '套', period: '12 周',  contractId: 'CON-K1903-001' },
  { code: 'SVC-006', category: '维保',         name: '3 年硬件维保服务',         qty: 36, unit: '人月', period: '36 个月', contractId: 'CON-K1903-003' },
  { code: 'SVC-007', category: '维保',         name: '7×24 远程支持',           qty: 1,  unit: '套', period: '36 个月', contractId: 'CON-K1903-003' },
  { code: 'SVC-008', category: '培训',         name: 'AI 平台运维培训 · 30 人', qty: 1,  unit: '场', period: '5 天',   contractId: 'CON-K1903-003' },
  { code: 'SVC-009', category: '培训',         name: '模型开发培训 · 15 人',    qty: 1,  unit: '场', period: '10 天',  contractId: 'CON-K1903-003' },
];

/* 5 大服务类的展示色（与 BOQ 服务表 chip 颜色对齐） */
export const SERVICE_CATEGORY_TONE = {
  '算力集成':     'green',
  '算力使能优化': 'amber',
  '智算上路':     'blue',
  '维保':         'violet',
  '培训':         'gray',
};

/* 部件 7 类的展示色（5.27 R-2 补 DPU/存储/网络）*/
export const PART_TONE = {
  CPU:     'brand',
  NPU:     'green',
  Mem:     'amber',
  PCIe:    'violet',
  DPU:     'pink',
  Storage: 'blue',
  Network: 'cyan',
};
