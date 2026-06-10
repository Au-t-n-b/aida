/* 孪生世界 phase 全局状态
 * - init    : 未构建（左导显示「孪生构建」）
 * - building: 构建动画进行中（短暂中间态）
 * - built   : 已构建（左导显示「孪生概览/物理/数字」三项）
 * - physical: 进入物理世界详情
 * - digital : 进入数字世界详情
 * 持久化到 localStorage['twin:phase']；用 storage 事件 + 同窗自定义事件让左导航与主区联动。 */
import { useEffect, useState } from 'react';

export type TwinPhase = 'init' | 'building' | 'built' | 'physical' | 'digital';

const KEY = 'twin:phase';
const EVT = 'twin:phase-change';

function readStored(): TwinPhase {
  try {
    const s = localStorage.getItem(KEY);
    if (s === 'built' || s === 'physical' || s === 'digital' || s === 'building') return s;
  } catch {}
  return 'init';
}

function writeStored(p: TwinPhase) {
  try {
    if (p === 'init') localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, p);
  } catch {}
}

export function setTwinPhase(p: TwinPhase) {
  writeStored(p);
  window.dispatchEvent(new CustomEvent(EVT, { detail: p }));
}

export function useTwinPhase(): [TwinPhase, (p: TwinPhase) => void] {
  const [phase, setPhase] = useState<TwinPhase>(() => readStored());

  useEffect(() => {
    const onCustom = (e: Event) => {
      const detail = (e as CustomEvent<TwinPhase>).detail;
      if (detail) setPhase(detail);
      else setPhase(readStored());
    };
    const onStorage = (e: StorageEvent) => {
      if (e.key === KEY) setPhase(readStored());
    };
    window.addEventListener(EVT, onCustom);
    window.addEventListener('storage', onStorage);
    return () => {
      window.removeEventListener(EVT, onCustom);
      window.removeEventListener('storage', onStorage);
    };
  }, []);

  const update = (p: TwinPhase) => {
    setPhase(p);
    setTwinPhase(p);
  };

  return [phase, update];
}

export function isTwinBuilt(p: TwinPhase): boolean {
  return p === 'built' || p === 'physical' || p === 'digital';
}
