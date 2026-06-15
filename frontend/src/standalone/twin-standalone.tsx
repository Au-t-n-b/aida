/* 算力底座孪生 · 单文件发布入口
 * 由 scripts/export-twin-standalone.mjs 构建：全屏挂载 TwinWorld，
 * physical-twin.html / digital-twin.html 以 __PHYSICAL_TWIN_B64 / __DIGITAL_TWIN_B64 内嵌（srcDoc）。 */
import { createRoot } from 'react-dom/client';
import '@/styles/globals.css';
import { TwinWorld } from '@/components/twin/twin-world';
import { useTwinPhase } from '@/lib/twin-phase';

function TwinStandaloneApp() {
  const [phase, setPhase] = useTwinPhase();
  return (
    <div style={{ position: 'fixed', inset: 0, display: 'flex', flexDirection: 'column', background: 'var(--c-bg)' }}>
      <TwinWorld phase={phase} onPhase={setPhase} />
    </div>
  );
}

const el = document.getElementById('root');
if (el) createRoot(el).render(<TwinStandaloneApp />);
