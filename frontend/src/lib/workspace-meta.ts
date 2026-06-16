import type { CurrentProject } from '@/lib/current-project';

type ProjectMini = Pick<CurrentProject, 'id' | 'name'>;

export type WorkspaceClawProps = {
  hideSwap?: boolean;
  hideSuggests?: boolean;
  hideChat?: boolean;
  inputPlaceholder?: string;
};

export type WorkspaceMeta = {
  breadcrumbs: string[];
  clawProps: WorkspaceClawProps;
  /** 进入该路由时默认收起 ClawRail（孪生世界分组） */
  clawCollapsedDefault?: boolean;
};

const DEFAULT_CLAW: WorkspaceClawProps = {
  inputPlaceholder: '对当前页面提问 / 下指令 · 支持引用 #PoD #机房 #项目',
};

const PROPOSAL_CLAW: WorkspaceClawProps = {
  hideSwap: true,
  hideSuggests: true,
  inputPlaceholder: '',
};

const PREVIEW_CLAW: WorkspaceClawProps = {
  hideSwap: true,
  hideSuggests: true,
  inputPlaceholder: '对当前页面提问 / 下指令…',
};

function matchPath(pathname: string, prefix: string): boolean {
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

/** 按 pathname 解析工作台壳层元数据（面包屑 + ClawRail 参数） */
export function getWorkspaceMeta(
  pathname: string,
  search: string,
  project?: ProjectMini | null,
): WorkspaceMeta {
  if (pathname === '/cockpit' || pathname.startsWith('/cockpit?')) {
    const label = project ? `${project.name} · ${project.id}` : '项目孪生';
    return {
      breadcrumbs: [`项目孪生 · ${label}`],
      clawProps: DEFAULT_CLAW,
      clawCollapsedDefault: true,
    };
  }

  if (pathname === '/proposal') {
    return { breadcrumbs: ['早期介入 · 交付预案'], clawProps: PROPOSAL_CLAW };
  }

  if (pathname === '/preview') {
    return { breadcrumbs: ['早期接入 · 合同 + 预案三快照'], clawProps: PREVIEW_CLAW };
  }

  if (pathname === '/twin') {
    return {
      breadcrumbs: ['孪生世界', '算力底座孪生'],
      clawProps: DEFAULT_CLAW,
      clawCollapsedDefault: true,
    };
  }

  if (pathname === '/twin/survey') {
    return {
      breadcrumbs: ['孪生世界', '实景孪生'],
      clawProps: DEFAULT_CLAW,
      clawCollapsedDefault: true,
    };
  }

  if (pathname === '/twin/digital-demo') {
    return {
      breadcrumbs: ['孪生世界', '数字孪生 · 预制演示'],
      clawProps: DEFAULT_CLAW,
      clawCollapsedDefault: true,
    };
  }

  if (pathname === '/design') {
    return { breadcrumbs: ['交付方案 · LLD 主版本'], clawProps: DEFAULT_CLAW };
  }

  if (pathname === '/sandbox') {
    return { breadcrumbs: ['AI 推演沙箱'], clawProps: DEFAULT_CLAW };
  }

  if (pathname === '/journey') {
    return { breadcrumbs: ['项目全生命周期 · 故事线'], clawProps: DEFAULT_CLAW };
  }

  if (pathname === '/create') {
    return { breadcrumbs: ['项目创建向导', '5 字段 → OCC 审批 → 激活'], clawProps: DEFAULT_CLAW };
  }

  if (pathname === '/milestones') {
    return { breadcrumbs: ['项目孪生 · K1903', 'PoD 级里程碑'], clawProps: DEFAULT_CLAW };
  }

  if (pathname === '/commissioning') {
    return { breadcrumbs: ['调测中心 · K1903'], clawProps: DEFAULT_CLAW };
  }

  if (matchPath(pathname, '/module')) {
    return { breadcrumbs: ['交付作业'], clawProps: DEFAULT_CLAW };
  }

  if (pathname === '/plan' && search.includes('view=')) {
    return { breadcrumbs: ['项目管理 · 人货站融合'], clawProps: DEFAULT_CLAW };
  }

  return { breadcrumbs: ['AIDA'], clawProps: DEFAULT_CLAW };
}
