/**
 * commissionBusyStore — 部署调测命令/范围处理中（左栏输入、按钮、HITL 全局锁）
 */
import { useSyncExternalStore } from 'react';

export interface CommissionBusyState {
  active: boolean;
  label?: string;
  kind?: 'scope' | 'command' | 'import';
}

let _current: CommissionBusyState = { active: false };
const _subs = new Set<() => void>();

function _notify(): void {
  _subs.forEach(fn => fn());
}

export function setCommissionBusy(
  active: boolean,
  label?: string,
  kind?: 'scope' | 'command' | 'import',
): void {
  const next: CommissionBusyState = active
    ? { active: true, label, kind }
    : { active: false };
  if (
    _current.active === next.active
    && _current.label === next.label
    && _current.kind === next.kind
  ) {
    return;
  }
  _current = next;
  _notify();
}

export function clearCommissionBusy(): void {
  setCommissionBusy(false);
}

export function getCommissionBusy(): CommissionBusyState {
  return _current;
}

export function useCommissionBusy(): CommissionBusyState {
  return useSyncExternalStore(
    cb => {
      _subs.add(cb);
      return () => { _subs.delete(cb); };
    },
    () => _current,
    () => _current,
  );
}
