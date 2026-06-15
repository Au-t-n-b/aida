import { designSkillId } from '@/config/design-skill';

/** 前端模块 key → 后端 skill_id（与 module.tsx、侧栏 NAV_OPS 一致） */
export const MODULE_TO_SKILL: Record<string, string> = {
  survey: 'zhgk',
  modeling: 'guihua',
  design: designSkillId,
  install: 'device_install',
  deploy: 'software_deployment',
};

/** 从 /module/:key 路径解析当前应对齐的 skillId；非模块路由返回 null */
export function skillIdFromModulePath(pathname: string): string | null {
  const m = pathname.match(/\/module\/([^/?#]+)/);
  const moduleKey = m?.[1];
  if (!moduleKey) return null;
  return MODULE_TO_SKILL[moduleKey] ?? null;
}
