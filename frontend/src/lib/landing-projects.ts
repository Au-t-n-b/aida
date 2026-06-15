/** 数据中心 projects/my → 落地页卡片模型映射 */

import type { CreateProjectBody, DcProjectDetail } from '@/lib/claw-manager-client';

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
  projectCode?: string;
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
  contractType?: string | null;
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

export type CreateProjectFormOptions = {
  /** 当前登录用户的系统 username（规范 4.6 tdUsername 示例 zhangsan） */
  sessionUsername?: string;
};

/**
 * 从「姓名 / 登录用户名」解析系统 username。
 * 尾段为纯数字时视为工号而非登录名，回退 sessionUsername。
 */
export function parsePersonUsername(
  raw: string | undefined,
  fallback?: string,
): string | undefined {
  const fb = (fallback || '').trim() || undefined;
  const s = (raw || '').trim();
  if (!s) return fb;
  const slash = s.lastIndexOf('/');
  if (slash >= 0) {
    const tail = s.slice(slash + 1).trim();
    if (tail && !/^\d+$/.test(tail)) return tail;
    return fb;
  }
  if (/^\d+$/.test(s)) return fb;
  return s;
}

function sceneCsvToDeliveryTraits(scene: string | undefined): string[] {
  return (scene || '')
    .split(',')
    .map((p) => p.trim())
    .filter(Boolean);
}

/**
 * 创建项目表单 → POST /api/v1/projects body（对齐规范 §4.6 / §5.2）
 * 必填：projectName、contractType；示例亦含 tdUsername、deliveryTraits。
 */
export function formToCreateProjectBody(
  fields: Record<string, string>,
  opts: CreateProjectFormOptions = {},
): CreateProjectBody {
  const projectName = (fields.name || '').trim();
  const contractType = (fields.contractType || '').trim();
  if (!projectName) {
    throw new Error('缺少必填参数 projectName（项目名称）');
  }
  if (contractType !== CONTRACT_PRESALE && contractType !== CONTRACT_STANDARD) {
    throw new Error('缺少必填参数 contractType（合同类型：预销售合同 / 标准合同）');
  }

  const code = (fields.code || '').trim();
  const proposal = (fields.proposal || '').trim();
  const sessionUser = (opts.sessionUsername || '').trim();
  const traits = sceneCsvToDeliveryTraits(fields.scene);

  const body: CreateProjectBody = {
    projectName,
    contractType,
    customerName: (fields.customerName || '').trim(),
  };

  if (contractType === CONTRACT_STANDARD) {
    if (proposal) body.bidCode = proposal;
  } else if (code) {
    body.projectCode = code;
  }

  const pdUsername = parsePersonUsername(fields.pd);
  const tdUsername = parsePersonUsername(fields.td, sessionUser) || sessionUser || undefined;
  const pcmUsername = parsePersonUsername(fields.pcm);
  if (pdUsername) body.pdUsername = pdUsername;
  if (tdUsername) body.tdUsername = tdUsername;
  if (pcmUsername) body.pcmUsername = pcmUsername;

  if (traits.length) body.deliveryTraits = traits;

  return body;
}

/** 编辑项目表单 → 数据中心 PUT /projects/{uuid} body */
export function formToUpdateProjectBody(fields: Record<string, string>): {
  projectName?: string;
  contractType?: string;
  tdUsername?: string;
  pdUsername?: string;
  pcmUsername?: string;
  deliveryTraits?: string[];
} {
  const body: {
    projectName?: string;
    contractType?: string;
    tdUsername?: string;
    pdUsername?: string;
    pcmUsername?: string;
    deliveryTraits?: string[];
  } = {};
  const projectName = (fields.name || '').trim();
  if (projectName) body.projectName = projectName;
  const contractType = (fields.contractType || '').trim();
  if (contractType) body.contractType = contractType;
  const pdUsername = parsePersonUsername(fields.pd);
  const tdUsername = parsePersonUsername(fields.td);
  const pcmUsername = parsePersonUsername(fields.pcm);
  if (pdUsername) body.pdUsername = pdUsername;
  if (tdUsername) body.tdUsername = tdUsername;
  if (pcmUsername) body.pcmUsername = pcmUsername;
  const traits = sceneCsvToDeliveryTraits(fields.scene);
  if (traits.length) body.deliveryTraits = traits;
  return body;
}

/** 编辑弹窗字段预填（与新建项目表单一致） */
export function projectToFormPreset(p: LandingProjectCard): Record<string, string> {
  return contractFieldsToFormPreset({
    name: p.name || '',
    projectCode: p.code,
    bidCode: p.bidCode,
    pdName: p.pdName,
    tdName: p.tdName,
    pcmName: p.pcmName,
    deliveryTraits: null,
  });
}

function contractFieldsToFormPreset(input: {
  name: string;
  contractType?: string | null;
  projectCode?: string | null;
  bidCode?: string | null;
  pdName?: string | null;
  tdName?: string | null;
  pcmName?: string | null;
  deliveryTraits?: unknown[] | null;
}): Record<string, string> {
  const code = (input.projectCode || '').trim();
  const bid = (input.bidCode || '').trim();
  const proposal = bid && bid !== code ? bid : '';
  const contractType = (input.contractType || '').trim()
    || (code && !proposal
      ? CONTRACT_PRESALE
      : (proposal && !code ? CONTRACT_STANDARD : CONTRACT_PRESALE));
  return {
    name: input.name || '',
    contractType,
    code: contractType === CONTRACT_PRESALE ? code : '',
    proposal: contractType === CONTRACT_STANDARD ? (proposal || bid || code) : '',
    scene: deliveryTraitsToSceneCsv(input.deliveryTraits),
    pd: input.pdName || '',
    td: input.tdName || '',
    pcm: input.pcmName || '',
  };
}

/** GET /projects/{uuid} 详情 → 编辑表单预填 */
export function dcProjectDetailToFormPreset(d: DcProjectDetail): Record<string, string> {
  const members = d.members || [];
  const byRole = (code: string) =>
    members.find((m) => (m.roleCode || '').toUpperCase() === code);
  const fmtMember = (m: { username?: string; roleName?: string } | undefined, fallback?: string | null) => {
    if (fallback?.trim()) return fallback.trim();
    if (!m) return '';
    const u = (m.username || '').trim();
    const rn = (m.roleName || '').trim();
    if (rn && u) return `${rn} / ${u}`;
    return u || rn;
  };
  return contractFieldsToFormPreset({
    name: d.projectName || '',
    contractType: d.contractType,
    projectCode: d.projectCode,
    bidCode: d.bidCode,
    pdName: fmtMember(byRole('PD'), d.pdName),
    tdName: fmtMember(byRole('TD'), d.tdName),
    pcmName: fmtMember(byRole('PCM'), d.pcmName),
    deliveryTraits: d.deliveryTraits,
  });
}

function deliveryTraitsToSceneCsv(traits: unknown[] | null | undefined): string {
  if (!Array.isArray(traits) || traits.length === 0) return '';
  const parts = traits.map((t) => {
    if (typeof t === 'string') return t.trim();
    if (t && typeof t === 'object') {
      const o = t as Record<string, unknown>;
      return String(o.label ?? o.name ?? o.value ?? o.trait ?? '').trim();
    }
    return '';
  }).filter(Boolean);
  return parts.join(',');
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
    projectCode: item.projectCode || undefined,
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
