import type { CurrentProject } from './current-project';

/**
 * 本地 `npm run dev` 调测：无 sessionStorage 项目时注入默认项目。
 * 与 auth-guard 同范式：`npm run build` / CI 下恒为 false。
 */
export function isDevLocalAuthEnabled(): boolean {
  return import.meta.env.DEV;
}

/** 与 TopBar PROJECT_LIST_MINI[0] 对齐的本地默认项目。 */
export const DEV_MOCK_PROJECT: CurrentProject = {
  id: 'K1903',
  name: '京东三期',
  projectCode: 'K1903',
};
