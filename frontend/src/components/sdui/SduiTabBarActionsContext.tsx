/**
 * TabGroup 页签栏右侧操作区 — 供嵌套的 DataTable 注册「一键同步 / 提交」等按钮。
 * 切到甘特图页签时表格仍保持挂载，按钮始终可见。
 */
import { createContext, useContext, type ReactNode } from 'react';

export type SduiTabBarActionsApi = {
  setActions: (actions: ReactNode) => void;
  clearActions: () => void;
};

export const SduiTabBarActionsContext = createContext<SduiTabBarActionsApi | null>(null);

export function useSduiTabBarActions(): SduiTabBarActionsApi | null {
  return useContext(SduiTabBarActionsContext);
}
