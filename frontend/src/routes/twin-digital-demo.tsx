import { AppShell } from '@/components/app-shell';
import ClawRail from '@/components/claw-rail';
import { TweaksProvider, useTweaks } from '@/lib/tweaks-context';
import { TweaksPanel } from '@/components/tweaks-panel';

/* 数字世界预制演示页（digital-twin.html）：
   · 多文件版：无 __DIGITAL_TWIN_B64 → iframe 走 /twin/digital-twin.html
   · 单文件版：构建注入 base64 → srcDoc 内联渲染 */
const TW_DIGITAL_SRCDOC = (function () {
  try {
    const b64 = (window as Window & { __DIGITAL_TWIN_B64?: string }).__DIGITAL_TWIN_B64;
    if (!b64) return null;
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new TextDecoder('utf-8').decode(bytes);
  } catch {
    return null;
  }
})();

function TwinDigitalDemoInner() {
  const { tweaks, setTweak } = useTweaks();

  return (
    <AppShell
      breadcrumbs={['孪生世界', '数字孪生 · 预制演示']}
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
        {TW_DIGITAL_SRCDOC ? (
          <iframe
            className="tw-digi-demo-frame"
            srcDoc={TW_DIGITAL_SRCDOC}
            title="数字孪生 · 预制演示"
          />
        ) : (
          <iframe
            className="tw-digi-demo-frame"
            src="/twin/digital-twin.html?instant=1&v=okl7"
            title="数字孪生 · 预制演示"
          />
        )}
      </div>
    </AppShell>
  );
}

export default function TwinDigitalDemoPage() {
  return (
    <TweaksProvider overrides={{ clawCollapsed: true }}>
      <TwinDigitalDemoInner />
      <TweaksPanel />
      <style>{`.tw-digi-demo-frame{width:100%;height:100%;border:0;display:block;background:transparent}`}</style>
    </TweaksProvider>
  );
}
