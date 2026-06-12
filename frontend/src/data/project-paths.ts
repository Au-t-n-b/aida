/**
 * IPO 与平台目录路径常量（SSOT：业务数据规范 §2、§5）
 * 业务代码禁止散落路径字符串，一律从此模块引用。
 */

export const IpoLayer = {
  input: '输入文件',
  parse: '解析结果',
  output: '输出结果',
} as const;

export type IpoLayerKey = keyof typeof IpoLayer;

/** 默认演示项目根目录 */
export const DEFAULT_PROJECT_ROOT = 'JD2项目_test-boq';
export const DEFAULT_PROJECT_NAME = '京东三期';

/** 项目 0 级根目录 */
export function projectRoot(projectId: string): string {
  return projectId;
}

function ipoTriple(root: string, domain: string, module: string) {
  const base = `${root}/${domain}/${module}`;
  return {
    base,
    in: `${base}/${IpoLayer.input}`,
    parse: `${base}/${IpoLayer.parse}`,
    out: `${base}/${IpoLayer.output}`,
  };
}

/** 组织资产（跨项目，无项目根前缀） */
export const OrgAssets = {
  root: '组织资产',
  raciTemplate: '组织资产/责任矩阵标准模板.xlsx',
  productBasicInfo: '组织资产/产品基本信息表',
} as const;

/** 项目内各 module_id 的 IPO 路径 */
export const ProjectPaths = {
  contract: (root: string) => ({
    ...ipoTriple(root, '早期介入', '合同'),
    simulationDeviceMd: `${root}/早期介入/合同/${IpoLayer.output}/建模仿真设备信息表.md`,
  }),

  proposal: (root: string) => ({
    ...ipoTriple(root, '早期介入', '交付预案'),
    techProposalIn: `${root}/早期介入/交付预案/${IpoLayer.input}/技术建议书.docx`,
    testCasesIn: `${root}/早期介入/交付预案/${IpoLayer.input}/测试用例new.xlsx`,
    raciOut: `${root}/早期介入/交付预案/${IpoLayer.output}/项目责任矩阵.xlsx`,
    acceptanceOut: `${root}/早期介入/交付预案/${IpoLayer.output}/验收策略.xlsx`,
    testCasesOut: `${root}/早期介入/交付预案/${IpoLayer.output}/测试用例.xlsx`,
  }),

  pmPlan: (root: string) => ({
    ...ipoTriple(root, '项目管理', '计划'),
    scheduleXlsx: `${root}/项目管理/计划/项目计划进度表.xlsx`,
  }),
} as const;

/** 跨项目 · 项目管理计划表（0610 SSOT：mock数据/项目管理/计划/项目计划进度表.xlsx） */
export const PmPlanAssets = {
  scheduleXlsx: '项目管理/计划/项目计划进度表.xlsx',
} as const;

/** 0610 交付预案 · 逻辑路径快捷引用（基于默认项目根） */
export const ProposalMockPaths = {
  raciTemplate: OrgAssets.raciTemplate,
  raciOut: ProjectPaths.proposal(DEFAULT_PROJECT_ROOT).raciOut,
  acceptanceOut: ProjectPaths.proposal(DEFAULT_PROJECT_ROOT).acceptanceOut,
  testCasesOut: ProjectPaths.proposal(DEFAULT_PROJECT_ROOT).testCasesOut,
  techProposalIn: ProjectPaths.proposal(DEFAULT_PROJECT_ROOT).techProposalIn,
  testCasesIn: ProjectPaths.proposal(DEFAULT_PROJECT_ROOT).testCasesIn,
  planSchedule: PmPlanAssets.scheduleXlsx,
  simulationDeviceMd: ProjectPaths.contract(DEFAULT_PROJECT_ROOT).simulationDeviceMd,
} as const;
