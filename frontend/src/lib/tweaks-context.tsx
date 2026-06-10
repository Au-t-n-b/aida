'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { TweakState } from '../types/domain';

type TweakKey = keyof TweakState;

interface TweaksContextValue {
  tweaks: TweakState;
  setTweak: <K extends TweakKey>(key: K, value: TweakState[K]) => void;
}

const TweaksContext = createContext<TweaksContextValue | null>(null);

export const TWEAK_DEFAULTS: TweakState = {
  density: 'regular',
  brand: '#3551d8',
  clawCollapsed: false,
  clawWidth: 360,
  stage: 'guide',
};

function shade(hex: string, pct: number): string {
  const n = parseInt(hex.slice(1), 16);
  const f = (c: number) => Math.max(0, Math.min(255, c + Math.round(2.55 * pct)));
  const r = f((n >> 16) & 0xff);
  const g = f((n >> 8) & 0xff);
  const b = f(n & 0xff);
  return '#' + [r, g, b].map((x) => x.toString(16).padStart(2, '0')).join('');
}

export function TweaksProvider({
  children,
  overrides,
}: {
  children: ReactNode;
  /** 覆盖部分默认值（仅初始化时生效，例如孪生世界默认收起 ClawRail） */
  overrides?: Partial<TweakState>;
}) {
  const [tweaks, setTweaks] = useState<TweakState>(() => ({ ...TWEAK_DEFAULTS, ...overrides }));

  function setTweak<K extends TweakKey>(key: K, value: TweakState[K]) {
    setTweaks((t) => ({ ...t, [key]: value }));
  }

  useEffect(() => {
    const brand = tweaks.brand || '#3551d8';
    document.documentElement.style.setProperty('--c-brand', brand);
    document.documentElement.style.setProperty('--c-brand-hover', shade(brand, -10));
  }, [tweaks.brand]);

  return (
    <TweaksContext.Provider value={{ tweaks, setTweak }}>
      <div data-density={tweaks.density} style={{ height: '100%' }}>
        {children}
      </div>
    </TweaksContext.Provider>
  );
}

export function useTweaks(): TweaksContextValue {
  const ctx = useContext(TweaksContext);
  if (!ctx) throw new Error('useTweaks must be used inside TweaksProvider');
  return ctx;
}
