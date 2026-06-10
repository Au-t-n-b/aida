import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { AppShell } from '@/components/app-shell';
import ClawRail from '@/components/claw-rail';
import { TweaksProvider, useTweaks } from '@/lib/tweaks-context';
import { TweaksPanel } from '@/components/tweaks-panel';
import { TwinWorld } from '@/components/twin/twin-world';
import { useTwinPhase, type TwinPhase } from '@/lib/twin-phase';

const VIEW_TO_PHASE: Record<string, TwinPhase> = {
  build: 'init',
  overview: 'built',
  physical: 'physical',
  digital: 'digital',
};
const PHASE_TO_VIEW: Record<TwinPhase, string> = {
  init: 'build',
  building: 'overview',
  built: 'overview',
  physical: 'physical',
  digital: 'digital',
};

function breadcrumbFor(phase: TwinPhase): string[] {
  const root = ['孪生世界', '算力底座孪生 · K1903'];
  if (phase === 'init') return [...root, '构建'];
  if (phase === 'physical') return [...root, '物理孪生'];
  if (phase === 'digital') return [...root, '数字孪生'];
  return [...root, '概览'];
}

function TwinInner() {
  const { tweaks, setTweak } = useTweaks();
  const [phase, setPhase] = useTwinPhase();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const viewParam = params.get('view');

  // URL 同步：view 参数变化 → 切 phase；phase 变化 → 回写 view
  useEffect(() => {
    if (!viewParam) return;
    const next = VIEW_TO_PHASE[viewParam];
    // 'building' 与 'built' 都回写成 view=overview；构建进行中时别让这条回写把
    // 正在跑的 'building' 立刻打回 'built'（会跳过左右两侧的构建动画）。
    if (next === 'built' && phase === 'building') return;
    if (next && next !== phase) setPhase(next);
  }, [viewParam]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const expected = PHASE_TO_VIEW[phase];
    if (viewParam !== expected) {
      const next = new URLSearchParams(params);
      next.set('view', expected);
      setParams(next, { replace: true });
    }
  }, [phase]); // eslint-disable-line react-hooks/exhaustive-deps

  // 清除后状态变回 init：若当前在 /twin?view=physical 之类，路由参数会被上面 effect 改写
  // TwinWorld 的 onPhase 直接调本组件 setPhase；当回到 init 时确保不停在 detail
  const handlePhase = (p: TwinPhase) => {
    setPhase(p);
  };

  // 切到 /cockpit 之类外部页时不动；这里只处理本路由
  useEffect(() => {
    // noop placeholder — 留作以后扩展（如 build 完成后 toast）
  }, [phase]);

  void navigate; // 当前没用到，但保留 import 以备扩展

  return (
    <AppShell
      breadcrumbs={breadcrumbFor(phase)}
      withClaw
      clawRail={
        <ClawRail
          collapsed={tweaks.clawCollapsed}
          onToggle={() => setTweak('clawCollapsed', !tweaks.clawCollapsed)}
          width={tweaks.clawWidth}
          onResize={(w: number) => setTweak('clawWidth', w)}
        />
      }
    >
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <TwinWorld phase={phase} onPhase={handlePhase} />
      </div>
    </AppShell>
  );
}

export default function TwinPage() {
  return (
    <TweaksProvider overrides={{ clawCollapsed: true }}>
      <TwinInner />
      <TweaksPanel />
    </TweaksProvider>
  );
}
