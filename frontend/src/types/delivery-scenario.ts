/** 项目交付场景信息表 · 人工三字段（对齐 05-规范 §4.1.1） */

export type DeployPhase = '新建' | '节点扩容';
export type ClusterForm = '训练' | '推理' | '训推一体';
export type LargeEpType = '大EP' | '非大EP';

export interface DeliveryScenarioManual {
  deploy_phase: DeployPhase;
  cluster_form: ClusterForm;
  large_ep_type: LargeEpType;
}

/** 创建弹窗 chip 选项（组1 / 组2 / 组3） */
export const SCENE_OPTION_GROUPS: readonly (readonly string[])[] = [
  ['新建', '节点扩容'],
  ['推理', '训练', '训推一体'],
  ['大EP'],
] as const;

export const SCENE_OPTIONS = SCENE_OPTION_GROUPS.flat();

const GROUP1 = new Set<string>(SCENE_OPTION_GROUPS[0]);
const GROUP2 = new Set<string>(SCENE_OPTION_GROUPS[1]);

/** 逗号分隔 chip 值 → 三字段（BR-EP-01：未勾选大EP → 非大EP） */
export function sceneCsvToDeliveryScenario(sceneCsv: string): Partial<DeliveryScenarioManual> {
  const selected = sceneCsv.split(',').map((s) => s.trim()).filter(Boolean);
  const deploy_phase = selected.find((s): s is DeployPhase => GROUP1.has(s));
  const cluster_form = selected.find((s): s is ClusterForm => GROUP2.has(s));
  const large_ep_type: LargeEpType = selected.includes('大EP') ? '大EP' : '非大EP';
  return { deploy_phase, cluster_form, large_ep_type };
}

export function validateSceneCsv(sceneCsv: string): string | null {
  const { deploy_phase, cluster_form } = sceneCsvToDeliveryScenario(sceneCsv);
  if (!deploy_phase) return '请选择部署阶段（新建或节点扩容）';
  if (!cluster_form) return '请选择集群形态';
  return null;
}
