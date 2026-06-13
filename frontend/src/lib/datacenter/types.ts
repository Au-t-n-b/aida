/** 表格读写的数据中心 slot 名称 */
export type ProposalTableSlot =
  | 'raci_template'
  | 'raci_out'
  | 'plan'
  | 'acceptance_out'
  | 'acceptance_input'
  | 'testcases_template'
  | 'testcases_out'
  | 'card_scale';

export interface ApiMeta {
  source?: 'datacenter' | 'mock' | 'none';
  logicalPath?: string;
  warnings?: string[];
}

export interface ProjectDataContext {
  token?: string;
  dcProjectId: string;
  projectCode?: string;
  projectName: string;
}

export interface TableReadResult {
  kind: string;
  rows?: unknown[];
  version?: number;
  cardScale?: number;
  text?: string;
  path?: string;
  meta?: ApiMeta;
}
