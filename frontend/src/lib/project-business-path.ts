/**
 * 当前项目物理根路径（UX 公共接口）
 *
 * 格式：`/opt/aida/aida-data/business/projects/{projectId}/`
 */

import { useMemo } from 'react';

import { useCurrentProject } from '@/lib/current-project';

/** 与 agent/manager `AIDA_BUSINESS_ROOT` 对齐；可通过 VITE_AIDA_BUSINESS_ROOT 覆盖（本地调试） */
export const BUSINESS_DATA_ROOT = (
  (import.meta.env.VITE_AIDA_BUSINESS_ROOT as string | undefined)?.trim()
  || '/opt/aida/aida-data/business'
).replace(/\/+$/, '');

/** 固定前缀：`/opt/aida/aida-data/business/projects` */
export const BUSINESS_PROJECTS_ROOT = `${BUSINESS_DATA_ROOT}/projects`;

/** 与 CurrentProjectProvider 共用 */
export const CURRENT_PROJECT_STORAGE_KEY = 'aida:current-project';

function assertSafeProjectId(projectId: string): string {
  const id = projectId.trim();
  if (!id) {
    throw new Error('projectId 不能为空');
  }
  if (/[\\/]/.test(id) || id.includes('..')) {
    throw new Error(`projectId 非法：${projectId}`);
  }
  return id;
}

/** 从 session 读取当前选中项目 id（非 React 场景可用） */
export function readCurrentProjectId(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem(CURRENT_PROJECT_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { id?: unknown };
    const id = typeof parsed?.id === 'string' ? parsed.id.trim() : '';
    return id || null;
  } catch {
    return null;
  }
}

/**
 * 构建项目物理根路径（末尾带 `/`）。
 */
export function buildProjectBusinessPath(projectId: string): string {
  return `${BUSINESS_PROJECTS_ROOT}/${assertSafeProjectId(projectId)}/`;
}

/** 当前选中项目的物理根路径；未选项目时抛错 */
export function getCurrentProjectBusinessPath(): string {
  const id = readCurrentProjectId();
  if (!id) {
    throw new Error('未选择项目，请先从落地页进入项目');
  }
  return buildProjectBusinessPath(id);
}

/**
 * 解析项目物理根路径：显式 projectId 优先，否则用当前选中项目。
 * @param projectId 可选；不传则读 session 中的当前项目
 */
export function resolveProjectBusinessPath(projectId?: string): string {
  const id = (projectId ?? readCurrentProjectId() ?? '').trim();
  if (!id) {
    throw new Error('未选择项目，请先从落地页进入项目');
  }
  return buildProjectBusinessPath(id);
}

/**
 * React 组件内获取当前项目物理根路径（订阅 CurrentProjectProvider）。
 * 未选项目时返回 null（不抛错，便于条件渲染）。
 */
export function useProjectBusinessPath(): string | null {
  const { project } = useCurrentProject();
  const id = project?.id?.trim() || readCurrentProjectId();
  return useMemo(
    () => (id ? buildProjectBusinessPath(id) : null),
    [id],
  );
}

/**
 * React 组件内获取当前项目物理根路径；未选项目时抛错。
 */
export function useRequiredProjectBusinessPath(): string {
  const path = useProjectBusinessPath();
  if (!path) {
    throw new Error('未选择项目，请先从落地页进入项目');
  }
  return path;
}
