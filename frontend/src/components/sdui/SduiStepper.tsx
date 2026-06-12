/**
 * SduiStepper — 执行步骤条（横向 / 纵向）· v4 语义
 *
 * 颜色语义（对齐 SDUI 组件库 v4）：
 *   done=绿（success）· running=琥珀转圈环（warning，spin）· pending=灰 · error=红。
 *   品牌蓝（indigo）专留给「可交互/选中」，不再表达运行态——避免语义过载。
 */
import type { SduiStepperStep } from '@/lib/sdui';

type Props = {
  steps: SduiStepperStep[];
  orientation?: 'horizontal' | 'vertical';
};

function labelColor(status: string): string {
  if (status === 'running') return 'var(--c-warning-text)';
  if (status === 'done')    return 'var(--c-text-2)';
  if (status === 'error')   return 'var(--c-danger)';
  return 'var(--c-text-muted)';
}
// 连接线：仅当前步骤已完成时，其后的线段才变绿；running/pending 之后保持灰
function connectorColor(status: string): string {
  if (status === 'done') return 'var(--c-success)';
  return 'var(--c-border-strong)';
}
function dotIcon(status: string, index: number): string {
  if (status === 'done')  return '✓';
  if (status === 'error') return '✗';
  if (status === 'running') return '';
  return String(index + 1);
}

/** 圆点样式（按状态）：running 为琥珀转圈环，其余为实心/描边点。size = 直径。 */
function dotStyle(status: string, size: number): React.CSSProperties {
  const iconSize = size >= 32 ? 13 : size >= 26 ? 11 : 10;
  const ring = size >= 32 ? 3 : 2.5;
  const base: React.CSSProperties = {
    width: size, height: size, borderRadius: '50%', flexShrink: 0,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: iconSize, fontWeight: 700, fontVariantNumeric: 'tabular-nums',
    transition: 'background .3s, border-color .3s, box-shadow .3s',
  };
  if (status === 'running') {
    return {
      ...base,
      background: 'var(--c-surface)',
      border: `${ring}px solid var(--c-warning-soft)`, borderTopColor: 'var(--c-warning)',
      color: 'transparent', animation: 'spin .8s linear infinite',
    };
  }
  if (status === 'done') {
    const glow = size >= 32 ? 6 : 4;
    return {
      ...base,
      background: 'var(--c-success)',
      border: `${ring}px solid var(--c-success)`,
      color: '#fff',
      boxShadow: `0 0 0 ${glow}px var(--c-success-soft)`,
    };
  }
  if (status === 'error') {
    return { ...base, background: 'var(--c-danger)', border: `${ring}px solid var(--c-danger)`, color: '#fff' };
  }
  return {
    ...base,
    background: 'var(--c-surface)',
    border: `${ring}px solid var(--c-border-strong)`,
    color: 'var(--c-text-muted)',
  };
}

const STATUS_BADGE: Record<string, { text: string; bg: string; fg: string }> = {
  running: { text: '执行中', bg: 'var(--c-warning-soft)', fg: 'var(--c-warning-text)' },
  done:    { text: '完成',   bg: 'var(--c-success-soft)', fg: 'var(--c-success-text)' },
  error:   { text: '失败',   bg: 'var(--c-danger-soft)', fg: 'var(--c-danger-text)' },
};

export function SduiStepper({ steps, orientation = 'horizontal' }: Props) {

  // ── 竖向（zhgk 主用） ──────────────────────────────────────────────────────
  if (orientation === 'vertical') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {steps.map((s, i) => {
          const isLast = i === steps.length - 1;
          // running 步骤显示最近3行日志，done/其他只显示最后1行（折叠）
          const detailLines = s.status === 'running'
            ? (s.detail ?? []).slice(-3)
            : s.status === 'done'
              ? (s.detail ?? []).slice(-1)
              : [];
          const badge = STATUS_BADGE[s.status];
          return (
            <div key={s.id} style={{ display: 'flex', alignItems: 'stretch' }}>

              {/* 时间轴列：圆点 + 连接线 */}
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                width: 26, flexShrink: 0, marginRight: 12,
              }}>
                <div style={dotStyle(s.status, 26)}>{dotIcon(s.status, i)}</div>
                {!isLast && (
                  <div style={{
                    width: 2, flex: 1, minHeight: 12,
                    background: connectorColor(s.status),
                    borderRadius: 1, transition: 'background .4s ease',
                  }} />
                )}
              </div>

              {/* 内容列：标题 + 状态标签 + detail */}
              <div style={{ flex: 1, paddingTop: 4, paddingBottom: isLast ? 0 : 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  <span style={{
                    fontSize: 'var(--fs-13)',
                    fontWeight: s.status === 'running' ? 600 : 400,
                    color: labelColor(s.status),
                  }}>
                    {s.title}
                  </span>

                  {badge && (
                    <span style={{
                      fontSize: 'var(--fs-10)', color: badge.fg, fontWeight: 600,
                      background: badge.bg, borderRadius: 'var(--r-sm)', padding: '1px 6px',
                      display: 'inline-flex', alignItems: 'center',
                    }}>
                      {badge.text}
                      {s.status === 'running' && (['0s', '.35s', '.7s'] as const).map((delay, di) => (
                        <span key={di} style={{
                          display: 'inline-block', width: 3, height: 3, borderRadius: '50%',
                          background: 'var(--c-warning)', marginLeft: di === 0 ? 3 : 2,
                          animation: `sdui-dot-blink 1.05s step-start ${delay} infinite`,
                        }} />
                      ))}
                    </span>
                  )}
                </div>

                {/* 日志 detail：running 显示3行，done 显示最后1行 */}
                {detailLines.length > 0 && (
                  <div style={{ marginTop: 4, display: 'flex', flexDirection: 'column', gap: 2 }}>
                    {detailLines.map((line, li) => (
                      <div key={line} style={{
                        fontSize: 'var(--fs-10)', lineHeight: 1.45,
                        color: s.status === 'running' ? 'var(--c-text-2)' : 'var(--c-text-muted)',
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                        animation: `sdui-stagger .18s ease-out ${li * 0.04}s both`,
                      }}>
                        {line}
                      </div>
                    ))}
                  </div>
                )}
              </div>

            </div>
          );
        })}
      </div>
    );
  }

  // ── 横向：N 等分列 · 圆点/标题同轴 · 连线用绝对定位整段（无列间断点） ──
  const H_DOT = 32;
  const H_CONN = 3;
  const n = steps.length;
  const colPct = 100 / n;
  const trackTop = H_DOT / 2 - H_CONN / 2;

  return (
    <div style={{ width: '100%', padding: '10px 8px 6px' }}>
      <div
        style={{
          position: 'relative',
          display: 'grid',
          gridTemplateColumns: `repeat(${n}, minmax(72px, 1fr))`,
        }}
      >
        {steps.slice(0, -1).map((s, i) => (
          <div
            key={`conn-${s.id}`}
            aria-hidden
            style={{
              position: 'absolute',
              top: trackTop,
              left: `${(i + 0.5) * colPct}%`,
              width: `${colPct}%`,
              height: H_CONN,
              background: connectorColor(s.status),
              zIndex: 0,
              pointerEvents: 'none',
              transition: 'background .4s ease',
            }}
          />
        ))}
        {steps.map((s, i) => (
          <div
            key={s.id}
            style={{
              gridColumn: i + 1,
              position: 'relative',
              zIndex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
            }}
          >
            <div style={dotStyle(s.status, H_DOT)} title={s.detail?.join(' · ')}>
              {dotIcon(s.status, i)}
            </div>
            <span
              style={{
                marginTop: 10,
                width: '100%',
                padding: '0 4px',
                fontSize: 'var(--fs-12)',
                fontWeight: s.status === 'running' ? 650 : 500,
                color: labelColor(s.status),
                textAlign: 'center',
                lineHeight: 1.4,
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
              }}
            >
              {s.title}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
