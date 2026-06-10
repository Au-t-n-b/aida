/**
 * SduiStepper — 执行步骤条（横向 / 纵向）
 *
 * 竖向模式：done=品牌蓝 ✓（最后一步 done=绿），running=品牌蓝脉冲+「执行中…」，连接线随步骤完成变品牌蓝。
 * 横向模式：紧凑头部，同竖向色规则。
 */
import type { SduiStepperStep } from '@/lib/sdui';

type Props = {
  steps: SduiStepperStep[];
  orientation?: 'horizontal' | 'vertical';
};

// Brand blue (#3551d8) for done & running; green only for the last-step success dot
function dotBg(status: string, isLast = false): string {
  if (status === 'done')    return isLast ? '#10b981' : '#3551d8';
  if (status === 'running') return '#3551d8';
  if (status === 'error')   return 'var(--red-600)';
  return 'var(--zinc-200)';
}
function dotFg(status: string): string {
  return status === 'waiting' ? 'var(--zinc-400)' : '#fff';
}
function labelColor(status: string): string {
  if (status === 'running') return 'var(--text-primary)';
  if (status === 'done')    return 'var(--text-secondary)';
  if (status === 'error')   return 'var(--red-600)';
  return 'var(--text-tertiary)';
}
// Connector uses brand blue for done state (not green)
function connectorColor(status: string, _nextStatus?: string): string {
  if (status === 'done')    return '#3551d8';
  if (status === 'running') return 'rgba(53,81,216,.25)';
  return 'var(--zinc-200)';
}
function dotIcon(status: string, index: number): string {
  if (status === 'done')  return '✓';
  if (status === 'error') return '✗';
  return String(index + 1);
}

export function SduiStepper({ steps, orientation = 'horizontal' }: Props) {

  // ── 竖向（zhgk 主用） ──────────────────────────────────────────────────────
  if (orientation === 'vertical') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {steps.map((s, i) => {
          const isLast = i === steps.length - 1;
          const nextStatus = !isLast ? steps[i + 1]?.status : undefined;
          // running 步骤显示最近3行日志，done/其他只显示最后1行（折叠）
          const detailLines = s.status === 'running'
            ? (s.detail ?? []).slice(-3)
            : s.status === 'done'
              ? (s.detail ?? []).slice(-1)
              : [];
          return (
            <div key={s.id} style={{ display: 'flex', alignItems: 'stretch' }}>

              {/* 时间轴列：圆点 + 连接线 */}
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                width: 26, flexShrink: 0, marginRight: 12,
              }}>
                {/* 圆点 */}
                <div style={{
                  width: 26, height: 26, borderRadius: '50%', flexShrink: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '11px', fontWeight: 700,
                  background: dotBg(s.status, isLast), color: dotFg(s.status),
                  boxShadow: s.status === 'running'
                    ? '0 0 0 4px rgba(53,81,216,.14)'
                    : s.status === 'done'
                      ? (isLast ? '0 0 0 4px rgba(16,185,129,.14)' : '0 0 0 4px rgba(53,81,216,.14)')
                      : 'none',
                  animation: s.status === 'running'
                    ? 'clawStepperPulse 1.4s ease-in-out infinite'
                    : 'none',
                  transition: 'background .3s, box-shadow .3s',
                }}>
                  {dotIcon(s.status, i)}
                </div>

                {/* 连接线 */}
                {!isLast && (
                  <div style={{
                    width: 2, flex: 1, minHeight: 12,
                    background: connectorColor(s.status, nextStatus),
                    borderRadius: 1,
                    transition: 'background .4s ease',
                  }} />
                )}
              </div>

              {/* 内容列：标题 + 状态标签 + detail */}
              <div style={{ flex: 1, paddingTop: 4, paddingBottom: isLast ? 0 : 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  <span style={{
                    fontSize: 'var(--text-xs)',
                    fontWeight: s.status === 'running' ? 600 : 400,
                    color: labelColor(s.status),
                  }}>
                    {s.title}
                  </span>

                  {/* 状态徽标 — brand blue for done, brand for running */}
                  {s.status === 'running' && (
                    // 三点依次亮起（每点 350ms 延迟），替代静态省略号
                    <span style={{
                      fontSize: '10px', color: '#3551d8', fontWeight: 500,
                      background: '#eef1fc', borderRadius: 4, padding: '1px 6px',
                      display: 'inline-flex', alignItems: 'center', gap: 0,
                    }}>
                      执行中
                      {(['0s', '.35s', '.7s'] as const).map((delay, di) => (
                        <span key={di} style={{
                          display: 'inline-block', width: 3, height: 3,
                          borderRadius: '50%', background: '#3551d8',
                          marginLeft: di === 0 ? 3 : 2,
                          animation: `sdui-dot-blink 1.05s step-start ${delay} infinite`,
                        }} />
                      ))}
                    </span>
                  )}
                  {s.status === 'done' && (
                    <span style={{
                      fontSize: '10px', color: '#3551d8', fontWeight: 500,
                      background: '#eef1fc', borderRadius: 4, padding: '1px 5px',
                    }}>
                      完成
                    </span>
                  )}
                  {s.status === 'error' && (
                    <span style={{
                      fontSize: '10px', color: 'var(--red-700)', fontWeight: 500,
                      background: 'var(--red-50)', borderRadius: 4, padding: '1px 5px',
                    }}>
                      失败
                    </span>
                  )}
                </div>

                {/* 日志 detail：running 显示3行，done 显示最后1行 */}
                {detailLines.length > 0 && (
                  <div style={{ marginTop: 4, display: 'flex', flexDirection: 'column', gap: 2 }}>
                    {detailLines.map((line, li) => (
                      // key=line 而非 li：当日志数组滑窗时，新出现的行触发 remount + 动画
                      <div key={line} style={{
                        fontSize: '10px', lineHeight: 1.45,
                        color: s.status === 'running' ? 'var(--text-secondary)' : 'var(--text-tertiary)',
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

  // ── 横向（紧凑头部） ────────────────────────────────────────────────────────
  return (
    <div style={{ display: 'flex', alignItems: 'center' }}>
      {steps.map((s, i) => {
        const last = i === steps.length - 1;
        return (
          <div
            key={s.id}
            style={{ display: 'flex', alignItems: 'center', flex: last ? 'none' : 1, minWidth: 0 }}
          >
            <div
              style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}
              title={s.detail?.join(' · ')}
            >
              <div style={{
                width: 20, height: 20, borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '10px', fontWeight: 700, lineHeight: 1,
                background: dotBg(s.status, last), color: dotFg(s.status),
                animation: s.status === 'running'
                  ? 'clawStepperPulse 1.4s ease-in-out infinite'
                  : 'none',
                transition: 'background .3s',
              }}>
                {dotIcon(s.status, i)}
              </div>
              <span style={{
                fontSize: 'var(--text-xs)',
                fontWeight: s.status === 'running' ? 600 : 400,
                color: labelColor(s.status),
                whiteSpace: 'nowrap',
              }}>
                {s.title}
              </span>
            </div>

            {!last && (
              <div style={{
                flex: 1, height: 2, minWidth: 12, maxWidth: 40, margin: '0 6px',
                background: connectorColor(s.status),
                borderRadius: 1, transition: 'background .4s ease',
              }} />
            )}
          </div>
        );
      })}
    </div>
  );
}
