/**
 * 前端模块 key → 后端 skill_id。
 *
 * P2：真相源迁移到 `skill-registry`（后端 `/agent/skills` manifest 驱动）。
 * 本文件保留历史公共 API（`MODULE_TO_SKILL` / `skillIdFromModulePath`）作门面，
 * 内部委托给 registry：拉取成功用远程，否则回落 FALLBACK_ROUTE_MAP（= 历史硬编码）。
 */
import {
  FALLBACK_ROUTE_MAP,
  getRouteSkillMapSync,
} from './skill-registry';

/** 静态兜底映射（拉取未完成 / 失败时使用）；动态映射见 getRouteSkillMapSync()。 */
export const MODULE_TO_SKILL: Record<string, string> = FALLBACK_ROUTE_MAP;

/** 从 /module/:key 路径解析当前应对齐的 skillId；非模块路由返回 null。 */
export function skillIdFromModulePath(pathname: string): string | null {
  const m = pathname.match(/\/module\/([^/?#]+)/);
  const moduleKey = m?.[1];
  if (!moduleKey) return null;
  return getRouteSkillMapSync()[moduleKey] ?? null;
}
