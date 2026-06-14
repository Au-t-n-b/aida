/** 数据中心 projects/my → 落地页卡片模型映射 */

export const CONTRACT_PRESALE = '预销售合同';
export const CONTRACT_STANDARD = '标准合同';

export const LANDING_STATUS_LABEL = {
  approved: '已审批',
  draft: '草稿',
} as const;

export type LandingProjectCard = {
  /** 数据中心 projectId（UUID32） */
  id: string;
  dbId?: number;
  name: string;
  code: string;
  roles: string[];
  stage4: 'survey' | 'modeling' | 'install' | 'deploy';
  todoCount: number;
  overdueCount: number;
  blocker: string | null;
  /** 已审批项目展示编辑入口 */
  canEdit: boolean;
  updated: string;
  canEnter: boolean;
  disabledReason?: string;
  status?: string;
  progress?: number;
  risk?: string;
  bidCode?: string;
  customerName?: string;
  description?: string;
  pdName?: string;
  tdName?: string;
  pcmName?: string;
};

export type DcProjectRole = {
  roleCode: string;
  roleName?: string;
};

export type DcMyProject = {
  id: number;
  projectId: string;
  projectName: string;
  projectCode?: string | null;
  bidCode?: string | null;
  customerName?: string | null;
  status: string;
  stage?: string | null;
  progress: number;
  risk: string;
  description?: string | null;
  updatedAt?: string | null;
  pdName?: string | null;
  tdName?: string | null;
  pcmName?: string | null;
  myRoles: DcProjectRole[];
  canEnter: boolean;
  disabledReason?: string | null;
};

export type DcMyProjectsData = {
  list: DcMyProject[];
  total: number;
};

const STAGE_KEYS = ['survey', 'modeling', 'install', 'deploy'] as const;

const STATUS_SORT_ORDER: Record<string, number> = {
  APPROVED: 0,
  PENDING_APPROVAL: 1,
  REJECTED: 2,
  ARCHIVED: 3,
};

export function isApprovedProject(p: Pick<LandingProjectCard, 'status' | 'canEnter'>): boolean {
  return p.status === 'APPROVED' || p.canEnter === true;
}

export function isPendingProject(p: Pick<LandingProjectCard, 'status'>): boolean {
  return p.status === 'PENDING_APPROVAL';
}

/** 落地页状态徽章：已审批 / 草稿（待审批等） */
export function landingStatusKey(
  p: Pick<LandingProjectCard, 'status' | 'canEnter'>,
): keyof typeof LANDING_STATUS_LABEL {
  return p.status === 'APPROVED' || p.canEnter ? 'approved' : 'draft';
}

/** 已审批在前，待审批在后 */
export function sortLandingProjects(items: LandingProjectCard[]): LandingProjectCard[] {
  return [...items].sort((a, b) => {
    const oa = STATUS_SORT_ORDER[a.status || ''] ?? 9;
    const ob = STATUS_SORT_ORDER[b.status || ''] ?? 9;
    if (oa !== ob) return oa - ob;
    return (a.name || '').localeCompare(b.name || '', 'zh-CN');
  });
}

/** 落地页仅展示已审批 + 待审批，已审批在前 */
export function visibleLandingProjects(items: LandingProjectCard[]): LandingProjectCard[] {
  return sortLandingProjects(
    items.filter((p) => p.status === 'APPROVED' || p.status === 'PENDING_APPROVAL'),
  );
}

/** 从「姓名 / 工号」文本解析可选用户 ID（数据中心 tdUserId 等） */
function parseOptionalUserId(raw: string | undefined): number | undefined {
  const s = (raw || '').trim();
  if (!s) return undefined;
  const tail = s.match(/(\d{5,})\s*$/);
  if (tail) {
    const n = Number(tail[1]);
    return Number.isFinite(n) ? n : undefined;
  }
  if (/^\d+$/.test(s)) return Number(s);
  return undefined;
}

/** 创建项目表单 → 数据中心 POST /projects body */
export function formToCreateProjectBody(fields: Record<string, string>): {
  projectName: string;
  projectCode?: string;
  bidCode?: string;
  tdUserId?: number;
  pdUserId?: number;
  pcmUserId?: number;
} {
  const projectName = (fields.name || '').trim();
  const code = (fields.code || '').trim();
  const proposal = (fields.proposal || '').trim();
  const body: {
    projectName: string;
    projectCode?: string;
    bidCode?: string;
    tdUserId?: number;
    pdUserId?: number;
    pcmUserId?: number;
  } = { projectName };
  if (fields.contractType === CONTRACT_STANDARD) {
    if (proposal) body.bidCode = proposal;
  } else {
    if (code) body.projectCode = code;
  }
  const pdUserId = parseOptionalUserId(fields.pd);
  const tdUserId = parseOptionalUserId(fields.td);
  const pcmUserId = parseOptionalUserId(fields.pcm);
  if (pdUserId) body.pdUserId = pdUserId;
  if (tdUserId) body.tdUserId = tdUserId;
  if (pcmUserId) body.pcmUserId = pcmUserId;
  return body;
}

/** 编辑弹窗字段预填（与新建项目表单一致） */
export function projectToFormPreset(p: LandingProjectCard): Record<string, string> {
  const code = (p.code || '').trim();
  const bid = (p.bidCode || '').trim();
  const proposal = bid && bid !== code ? bid : '';
  const contractType = code && !proposal ? CONTRACT_PRESALE : (proposal && !code ? CONTRACT_STANDARD : CONTRACT_PRESALE);
  return {
    name: p.name || '',
    contractType,
    code: contractType === CONTRACT_PRESALE ? code : '',
    proposal: contractType === CONTRACT_STANDARD ? (proposal || bid || code) : '',
    scene: '',
    pd: p.pdName || '',
    td: p.tdName || '',
    pcm: p.pcmName || '',
  };
}

export function mapDcProjectToCard(item: DcMyProject): LandingProjectCard {
  const roles = (item.myRoles || [])
    .map((r) => r.roleCode)
    .filter(Boolean);
  const stage4 = mapStage4(item.stage, item.progress);
  const overdueCount = item.risk === 'high' ? 1 : 0;

  return {
    id: item.projectId,
    dbId: item.id,
    name: item.projectName,
    code: item.projectCode || item.bidCode || item.projectId,
    roles,
    stage4,
    todoCount: item.progress > 0 ? Math.max(1, Math.round(item.progress / 25)) : 0,
    overdueCount,
    blocker: item.canEnter ? null : (item.disabledReason || '项目暂不可进入'),
    canEdit: item.status === 'APPROVED' || item.status === 'PENDING_APPROVAL',
    updated: formatRelativeTime(item.updatedAt),
    canEnter: item.canEnter,
    disabledReason: item.disabledReason || undefined,
    status: item.status,
    progress: item.progress,
    risk: item.risk,
    bidCode: item.bidCode || undefined,
    customerName: item.customerName || undefined,
    description: item.description || undefined,
    pdName: item.pdName || undefined,
    tdName: item.tdName || undefined,
    pcmName: item.pcmName || undefined,
  };
}

export function mapStage4(
  stage: string | null | undefined,
  progress: number,
): LandingProjectCard['stage4'] {
  const s = (stage || '').toLowerCase();
  if (s.includes('survey') || s.includes('工勘')) return 'survey';
  if (s.includes('model') || s.includes('design') || s.includes('plan') || s.includes('规划')) {
    return 'modeling';
  }
  if (s.includes('install') || s.includes('设备')) return 'install';
  if (s.includes('deploy') || s.includes('delivery') || s.includes('调测')) return 'deploy';
  if (progress >= 75) return 'deploy';
  if (progress >= 50) return 'install';
  if (progress >= 25) return 'modeling';
  return 'survey';
}

export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const ts = Date.parse(iso);
  if (Number.isNaN(ts)) return iso;
  const diffMs = Date.now() - ts;
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 1) return '刚刚';
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return '昨日';
  if (days < 30) return `${days} 天前`;
  return iso.slice(0, 10);
}

export { STAGE_KEYS };
