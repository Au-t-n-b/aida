/**
 * Skill 元数据注册表（前端 · P2）
 *
 * 单一真相：后端 `GET /agent/skills` 的 manifest（version/enabled/ui/runtime）。
 * 本模块在应用首次用到时惰性拉取一次，缓存在模块级 store，并用 `useSyncExternalStore`
 * 暴露给组件。导航树 / module 路由由此派生 —— 新增 skill 只要后端注册 + 写 manifest，
 * 前端零改即可出现入口。
 *
 * 韧性：拉取未完成 / 失败（Agent 不可达）时一律回落到 FALLBACK_*（与历史硬编码一致），
 * 因此本模块是「数据驱动优先、静态兜底」，不是「纯远程」。
 *
 * 依赖方向：本模块为叶子（只依赖 agentBase / design-skill 配置）。
 * module-skill-map.ts、left-nav-items.ts、left-nav-fdy.tsx 反过来依赖本模块，避免环。
 */
import { useEffect, useSyncExternalStore } from 'react';
import { agentBaseSync } from '@/lib/agentBase';
import { designSkillId } from '@/config/design-skill';

export interface SkillUiMeta {
  label: string;
  group: string;
  order: number;
  icon: string;
  route_key: string;
}

export interface SkillMeta {
  name: string;
  description: string;
  version: string;
  enabled: boolean;
  ui: SkillUiMeta;
  runtime: Record<string, unknown>;
  error?: string;
}

export interface SkillNavItem {
  name: string;
  key: string;
}

/** 交付作业（ops）分组的静态兜底 —— 与历史 NAV_OPS 一致，拉取失败时仍可用。 */
export const OPS_FALLBACK: SkillNavItem[] = [
  { name: '智慧工勘', key: 'survey' },
  { name: '规划设计', key: 'modeling' },
  { name: '设备安装', key: 'install' },
  { name: '部署调测', key: 'deploy' },
];

/** route_key → skill_id 的静态兜底（与历史 MODULE_TO_SKILL 一致；design 受 VITE_DESIGN_SKILL 控制）。 */
export const FALLBACK_ROUTE_MAP: Record<string, string> = {
  survey: 'zhgk',
  modeling: 'guihua',
  design: designSkillId,
  install: 'device_install',
  deploy: 'software_deployment',
};

// ── 模块级 store ──
let _skills: SkillMeta[] | null = null;
let _hydrating = false;
const _subs = new Set<() => void>();

function _emit(): void {
  for (const fn of _subs) fn();
}

function _subscribe(fn: () => void): () => void {
  _subs.add(fn);
  return () => {
    _subs.delete(fn);
  };
}

function _getSnapshot(): SkillMeta[] | null {
  return _skills;
}

function _normalize(raw: Partial<SkillMeta> & { name: string }): SkillMeta {
  const ui = (raw.ui ?? {}) as Partial<SkillUiMeta>;
  return {
    name: raw.name,
    description: raw.description ?? '',
    version: raw.version ?? '',
    enabled: raw.enabled !== false,
    ui: {
      label: ui.label || raw.name,
      group: ui.group ?? '',
      order: typeof ui.order === 'number' ? ui.order : 999,
      icon: ui.icon ?? '',
      route_key: ui.route_key || raw.name,
    },
    runtime: (raw.runtime ?? {}) as Record<string, unknown>,
    error: raw.error,
  };
}

/** 拉取一次 `/agent/skills`（幂等）。失败静默，保留 fallback。 */
export async function hydrateSkillRegistry(force = false): Promise<void> {
  if (_hydrating) return;
  if (_skills && !force) return;
  _hydrating = true;
  try {
    const base = agentBaseSync();
    const res = await fetch(`${base}/agent/skills`, { signal: AbortSignal.timeout(8000) });
    if (!res.ok) return;
    const json = (await res.json()) as { skills?: Array<Partial<SkillMeta> & { name: string }> };
    if (Array.isArray(json?.skills)) {
      _skills = json.skills.filter((s) => s && s.name).map(_normalize);
      _emit();
    }
  } catch {
    // 静默：Agent 不可达 → 继续用 fallback
  } finally {
    _hydrating = false;
  }
}

/** React 订阅 store；首次挂载触发惰性拉取。返回 null 表示尚未拉取（消费方应回落 fallback）。 */
export function useSkillRegistry(): SkillMeta[] | null {
  const skills = useSyncExternalStore(_subscribe, _getSnapshot, _getSnapshot);
  useEffect(() => {
    void hydrateSkillRegistry();
  }, []);
  return skills;
}

/** 取某分组的导航项（enabled，按 order 升序）；未拉取 → 该组 fallback（目前仅 ops）。 */
export function selectNavItems(skills: SkillMeta[] | null, group: string): SkillNavItem[] {
  if (!skills || skills.length === 0) {
    return group === 'ops' ? OPS_FALLBACK : [];
  }
  return skills
    .filter((s) => s.enabled && s.ui.group === group)
    .sort((a, b) => a.ui.order - b.ui.order)
    .map((s) => ({ name: s.ui.label, key: s.ui.route_key }));
}

/** route_key → skill_id 映射（enabled）；design 始终受 VITE_DESIGN_SKILL 控制。 */
export function selectRouteMap(skills: SkillMeta[] | null): Record<string, string> {
  const out: Record<string, string> = { ...FALLBACK_ROUTE_MAP };
  if (skills && skills.length) {
    for (const s of skills) {
      if (!s.enabled) continue;
      out[s.ui.route_key] = s.name;
    }
    out.design = designSkillId; // design 入口由配置切换 system_design ↔ xtsj，不被元数据覆盖
  }
  return out;
}

/** 同步取最新 route→skill 映射（非 React 上下文用，如 skillIdFromModulePath）。 */
export function getRouteSkillMapSync(): Record<string, string> {
  return selectRouteMap(_skills);
}

/** skill_id → route_key（如 zhgk → survey）；未注册返回 null。 */
export function getRouteKeyBySkillId(skillId: string): string | null {
  const sid = skillId.trim();
  if (!sid) return null;
  const map = getRouteSkillMapSync();
  for (const [routeKey, name] of Object.entries(map)) {
    if (name === sid) return routeKey;
  }
  return null;
}

/** skill 对应作业模块路径（如 /module/survey）；无映射返回 null。 */
export function getSkillModulePath(skillId: string): string | null {
  const routeKey = getRouteKeyBySkillId(skillId);
  return routeKey ? `/module/${routeKey}` : null;
}

/** 同步取某 route_key 的导航显示名（ClawRail 标题用）；未命中返回 null。 */
export function getSkillLabelByRouteKeySync(routeKey: string): string | null {
  if (_skills) {
    const hit = _skills.find((s) => s.ui.route_key === routeKey);
    if (hit) return hit.ui.label;
  }
  return OPS_FALLBACK.find((i) => i.key === routeKey)?.name ?? null;
}

/**
 * 强制重拉 `/agent/skills`（热刷新）。
 * 后端热加载（`/admin/skills/reload` 增/删 skill）后，调用本函数即可让导航/路由反映最新——
 * 无需刷新整页。返回 Promise，便于"手动刷新钮"等待。
 */
export function refreshSkillRegistry(): Promise<void> {
  return hydrateSkillRegistry(true);
}

// ── 模块级热刷新（闭合热加载闭环 · P4 收尾）──
// 标签页重新可见时立即热刷一次（覆盖"管理员在服务器 reload 后切回页面"），
// 并在可见状态下每 SKILL_POLL_MS 轮询一次，确保热增/删最终反映到导航树。
// visibilitychange 门控：标签页隐藏时不轮询，避免后台网络空转。
const SKILL_POLL_MS = 60_000;
if (typeof window !== 'undefined' && typeof document !== 'undefined') {
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') void hydrateSkillRegistry(true);
  });
  window.setInterval(() => {
    if (document.visibilityState === 'visible') void hydrateSkillRegistry(true);
  }, SKILL_POLL_MS);
}
