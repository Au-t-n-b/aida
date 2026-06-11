/** 左侧导航子项 · 与 left-nav-fdy 共用（ClawRail 标题同步导航栏名称） */

import { getModuleLabel } from './claw-seeds';

export type NavSubItem = {
  name: string;
  href?: string;
  key?: string;
};

export type NavLeafItem = {
  name: string;
  href: string;
};

export const NAV_TWIN: NavSubItem[] = [
  { name: '算力底座孪生', href: '/twin' },
  { name: '项目孪生', href: '/cockpit' },
  { name: '工勘孪生', href: '/twin/survey' },
];

export const NAV_EARLY: NavSubItem[] = [
  { name: '合同', href: '/preview' },
  { name: '交付预案', href: '/proposal' },
];

export const NAV_PLAN: NavSubItem[] = [
  { name: '基本信息', href: '/plan?view=info' },
  { name: '计划', href: '/plan?view=plan' },
  { name: '任务', href: '/plan?view=task' },
  { name: '风险', href: '/plan?view=risk' },
  { name: '假设', href: '/plan?view=assumption' },
  { name: '问题', href: '/plan?view=issue' },
  { name: '变更', href: '/plan?view=change' },
  { name: '计划排期（初始化）', href: '/plan-init' },
  { name: '计划排期（计划调整）', href: '/plan-adjust' },
];

export const NAV_OPS: NavSubItem[] = [
  { name: '智慧工勘', key: 'survey' },
  { name: '规划设计', key: 'modeling' },
  { name: '设备安装', key: 'install' },
  { name: '部署调测', href: '/commissioning' },
];

export const NAV_DOCS: NavSubItem[] = [
  { name: '项目管理类', href: '/assets?cat=mgmt' },
  { name: '工勘类', href: '/assets?cat=survey' },
  { name: '其他作业类', href: '/assets?cat=ops' },
];

export const NAV_LEAVES: NavLeafItem[] = [
  { name: '交付方案', href: '/design' },
  { name: '评测中心', href: '/evals' },
];

const NAV_GROUPS: Array<{ sub: NavSubItem[]; hrefPrefix?: string }> = [
  { sub: NAV_TWIN },
  { sub: NAV_EARLY },
  { sub: NAV_PLAN },
  { sub: NAV_OPS, hrefPrefix: '/module' },
  { sub: NAV_DOCS },
];

/** 与 left-nav-fdy isSubActive 一致 */
export function isNavSubActive(navPath: string, s: NavSubItem, hrefPrefix?: string): boolean {
  if (s.href) {
    if (s.href === '/cockpit') return navPath === '/cockpit' || navPath.startsWith('/cockpit?');
    if (s.href.includes('?')) return navPath === s.href;
    return navPath === s.href || navPath.startsWith(`${s.href}/`) || navPath.startsWith(`${s.href}?`);
  }
  if (hrefPrefix && s.key) {
    const base = `${hrefPrefix}/${s.key}`;
    return navPath === base || navPath.startsWith(`${base}/`) || navPath.startsWith(`${base}?`);
  }
  return false;
}

function resolveHref(s: NavSubItem, hrefPrefix?: string): string {
  if (s.href) return s.href;
  if (hrefPrefix && s.key) return `${hrefPrefix}/${s.key}`;
  return '';
}

function findActiveSub(navPath: string, sub: NavSubItem[], hrefPrefix?: string): NavSubItem | null {
  const sorted = [...sub].sort(
    (a, b) => resolveHref(b, hrefPrefix).length - resolveHref(a, hrefPrefix).length,
  );
  return sorted.find((s) => isNavSubActive(navPath, s, hrefPrefix)) ?? null;
}

/** 当前路由对应的侧栏子项名称；未命中时回落到模块级标签 */
export function getNavLabel(navPath: string): string {
  if (!navPath) return getModuleLabel('');

  if (navPath === '/plan' || navPath.startsWith('/plan?')) {
    const params = new URLSearchParams(navPath.includes('?') ? navPath.split('?')[1] : '');
    const view = params.get('view');
    const planItem = NAV_PLAN.find((s) => s.href === `/plan?view=${view}`);
    if (planItem) return planItem.name;
    if (navPath === '/plan' || !view) return '计划';
  }

  for (const { sub, hrefPrefix } of NAV_GROUPS) {
    const hit = findActiveSub(navPath, sub, hrefPrefix);
    if (hit) return hit.name;
  }

  for (const leaf of NAV_LEAVES) {
    if (
      navPath === leaf.href ||
      navPath.startsWith(`${leaf.href}/`) ||
      navPath.startsWith(`${leaf.href}?`)
    ) {
      return leaf.name;
    }
  }

  const pathname = navPath.split('?')[0] ?? navPath;
  return getModuleLabel(pathname);
}
