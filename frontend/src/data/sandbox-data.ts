/* /sandbox · AI 推演沙箱
 * 会议结论："推到沙箱里看 α/β 方案"、"沙箱 α 命中率 78%"、"导出汇报片"
 * 这是 AIDA 最具说服力的一个能力 — 让 AI 替人做决策推演。
 */

/* 触发场景：每个 scenario 对应一个 cockpit insight 或风险 */
export const SANDBOX_SCENARIOS = {
  /* 默认场景：B2 配电延期 */
  'b2-power-delay': {
    key: 'b2-power-delay',
    title: 'B2-RM02 客户配电改造延期 9 天',
    sev: 'red',
    sourceInsight: 'INS-2026-0512-01',
    sourceRisk: 'B2-RM02 客户配电改造延期，影响 6 个 PoD 上电',
    impactRoute: 'B2-RM02 → PoD#18-23 → 上电点亮 → A1 一期客户移交',
    baselineDelay: '+5 ~ 7 天 · 直接顺延 A1 移交里程碑',
    sla: 'T-12 客户通报窗口',
    customerNotice: '客户已确认改造时间表，无法压缩',
    constraints: [
      'A1 一期客户移交里程碑 07-15 不可顺延（合同硬约束）',
      'PoD#01-04 已齐套 · 安装可前置',
      '施工队 07 当前 96% 饱和，无空闲',
      'H 项目（湖北通枢）调测组本周节奏可放缓 2 天',
    ],
    plans: [
      {
        key: 'alpha',
        label: '方案 α',
        recommended: true,
        hitRate: 78,
        summary: 'PoD#01-04 安装压缩 2d + H 项目调度 2 名工程师补位',
        deltaCost: '+ ¥ 84,000（H 项目跨调差旅 + 加班）',
        deltaTime: '吸收 5 / 7 天延期',
        riskAfter: 'amber → green（移交保住）',
        moves: [
          { stream: '人', text: 'H 项目调度 2 名调试工程师（陈工 + 周工）补位 5/26 - 6/04', tone: 'people' },
          { stream: '货', text: 'PoD#01-04 工厂联调压缩 2 天（已与供应链对齐）', tone: 'goods' },
          { stream: '站', text: 'B2-RM02 改造期间，先把 PoD#13-15 在 B2-RM01 提前点亮', tone: 'site' },
        ],
        ganttDiff: [
          { id: 'M3', name: '机柜入场', start: 6, dur: 6, status: 'ok' },   // 提前 2 天
          { id: 'M4', name: '上电点亮', start: 12, dur: 8, status: 'ok' },  // 提前 2 天
          { id: 'M5', name: '业务联调', start: 18, dur: 10, status: 'risk' }, // 紧张但可控
          { id: 'M6', name: '客户验收', start: 28, dur: 6, status: 'ok' },
        ],
        confidence: [
          { k: '历史相似项目', v: 'PJ-2025-014 顺延 5d 闭环案例' },
          { k: 'DORA 推理', v: '关键路径压缩 2d 可行 · 资源充足' },
          { k: '客户态度', v: '07-15 节点客户已明确不让步' },
        ],
        risks: [
          { lvl: 'med', text: '陈工 / 周工跨项目调度需 H 项目 PD 配合，预计今日 18:00 前回复' },
          { lvl: 'low', text: 'B2-RM01 提前点亮需要客户配合开放通道' },
        ],
      },
      {
        key: 'beta',
        label: '方案 β',
        recommended: false,
        hitRate: 54,
        summary: '不调人 · 全靠工期压缩 · 单点超负荷',
        deltaCost: '+ ¥ 32,000（仅施工队 07 加班）',
        deltaTime: '吸收 5 天延期，7 天仍超 2 天',
        riskAfter: 'amber → amber（仍存在顺延 2 天风险）',
        moves: [
          { stream: '人', text: '施工队 07 改三班倒（饱和度 96% → 110%）', tone: 'people' },
          { stream: '货', text: 'PoD#01-04 / PoD#05-08 工厂联调全压 3 天', tone: 'goods' },
          { stream: '站', text: '维持原 RM02 等待，不提前到 RM01', tone: 'site' },
        ],
        ganttDiff: [
          { id: 'M3', name: '机柜入场', start: 7, dur: 5, status: 'risk' },
          { id: 'M4', name: '上电点亮', start: 12, dur: 7, status: 'risk' },
          { id: 'M5', name: '业务联调', start: 19, dur: 9, status: 'risk' },
          { id: 'M6', name: '客户验收', start: 28, dur: 6, status: 'risk' },
        ],
        confidence: [
          { k: '历史相似项目', v: 'PJ-2024-031 队伍超载 → 调测质量下滑案例' },
          { k: 'DORA 推理', v: '110% 饱和度 = 36% 概率次日有人员请假反噬' },
          { k: '客户态度', v: '若再顺延，触发合同罚则条款' },
        ],
        risks: [
          { lvl: 'high', text: '施工队 07 已连续 4 周高位运行，超载存在质量隐患' },
          { lvl: 'med', text: '一旦 7 天延期成真，仍需追加方案' },
        ],
      },
    ],
    /* 当前选择的方案（写回时使用） */
    chosenPlan: null,
    /* 历史推演记录（已写回过的） */
    history: [
      { ts: '2026-05-25 17:24', who: 'TD 何博', plan: 'α', action: '已写回 /plan' },
      { ts: '2026-05-23 09:50', who: 'PD 李伟', plan: 'β', action: '驳回 · 风险过高' },
    ],
  },

  /* 第二个示例场景：A1 PoD#04 100G 物流 */
  'a1-pod04-logistics': {
    key: 'a1-pod04-logistics',
    title: 'A1 PoD#04 100G 交换机物流 ETA 5/28（晚 3 天）',
    sev: 'amber',
    sourceInsight: 'INS-2026-0512-02',
    sourceRisk: 'A1 PoD #04 100G 交换机齐套延期',
    impactRoute: '供应链 → A1 PoD#04 齐套 → 安装',
    baselineDelay: '+2 天 · 可吸收',
    sla: '可吸收 · 压缩工厂联调',
    customerNotice: '客户尚未感知',
    constraints: [
      'PoD#04 是关键节点，影响 A1 整体进度',
      '工厂联调可压缩 1~2 天但需安全冗余',
    ],
    plans: [
      {
        key: 'alpha',
        label: '方案 α',
        recommended: true,
        hitRate: 86,
        summary: '工厂联调压缩 2 天 · 现场补 1 天 = 全吸收',
        deltaCost: '+ ¥ 12,000（工厂加班）',
        deltaTime: '吸收 3 天延期',
        riskAfter: 'amber → green',
        moves: [
          { stream: '货', text: '100G 交换机工厂联调由 5d 压缩到 3d', tone: 'goods' },
          { stream: '人', text: 'A1 调测组从其他 PoD 抽 4h 补 PoD#04', tone: 'people' },
        ],
        ganttDiff: [],
        confidence: [
          { k: '工厂能力', v: '上周类似 SKU 压缩 2d 成功率 92%' },
        ],
        risks: [
          { lvl: 'low', text: '工厂压缩 2d 是常规操作' },
        ],
      },
      {
        key: 'beta',
        label: '方案 β',
        recommended: false,
        hitRate: 41,
        summary: '不动 · 等物流自然到货 · 顺延 2 天',
        deltaCost: '0',
        deltaTime: '不吸收，顺延 2 天',
        riskAfter: 'amber → red（影响 A1 移交）',
        moves: [
          { stream: '货', text: '不压缩 · 等 5/28 自然到货', tone: 'goods' },
        ],
        ganttDiff: [],
        confidence: [
          { k: '客户态度', v: '客户对 A1 移交 07-15 不让步' },
        ],
        risks: [
          { lvl: 'high', text: '直接传导到合同里程碑' },
        ],
      },
    ],
    chosenPlan: null,
    history: [],
  },
};

export const SANDBOX_DEFAULT_KEY = 'b2-power-delay';

/* 给左导航 / cockpit insight 用的浅 index */
export const SANDBOX_INDEX = Object.values(SANDBOX_SCENARIOS).map(s => ({
  key: s.key,
  title: s.title,
  sev: s.sev,
}));
