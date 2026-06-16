import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { TwinWorld } from '@/components/twin/twin-world';
import { useTwinPhase, consumeTwinAutoBuild, type TwinPhase } from '@/lib/twin-phase';

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

export default function TwinPage() {
  const [phase, setPhase] = useTwinPhase();
  const [params, setParams] = useSearchParams();
  const viewParam = params.get('view');

  // 入口（如「生成预案并决策」）置位的一次性自动构建请求：消费一次 → 自动跑「构建算力底座孪生」。
  // 不依赖 URL（避免 Outlet 因 search 变化重挂载丢状态）；配合 ?view=build 进入即清除/init 态。
  const [autoBuild, setAutoBuild] = useState(false);
  useEffect(() => {
    if (consumeTwinAutoBuild()) setAutoBuild(true);
  }, []);

  useEffect(() => {
    if (!viewParam) return;
    const next = VIEW_TO_PHASE[viewParam];
    if (next === 'built' && phase === 'building') return;
    if (next && next !== phase) setPhase(next);
  }, [viewParam]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const expected = PHASE_TO_VIEW[phase];
    // 外部带 ?view=digital 进入时，先由 viewParam effect 改 phase，勿把 URL 改回 build。
    if (viewParam && VIEW_TO_PHASE[viewParam] && VIEW_TO_PHASE[viewParam] !== phase) return;
    if (viewParam !== expected) {
      const next = new URLSearchParams(params);
      next.set('view', expected);
      setParams(next, { replace: true });
    }
  }, [phase]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <TwinWorld phase={phase} onPhase={setPhase} autoBuild={autoBuild} />
    </div>
  );
}
