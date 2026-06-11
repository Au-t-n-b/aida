/**
 * SduiDonutChart — SVG 圆环图（移植自 survey-agent.tsx MiniDonut）
 */
import type { SduiDonutSegment } from '@/lib/sdui';

type Props = {
  segments: SduiDonutSegment[];
  centerLabel?: string;
  centerValue?: string;
};

const SEMANTIC_COLORS: Record<string, string> = {
  accent:  'var(--blue-600)',
  success: 'var(--green-600)',
  warning: '#d97706',
  error:   'var(--red-600)',
  subtle:  'var(--zinc-200)',
};

function resolveColor(c?: string): string {
  if (!c) return 'var(--zinc-200)';
  return SEMANTIC_COLORS[c] ?? c;
}

export function SduiDonutChart({ segments, centerLabel, centerValue }: Props) {
  const visible = segments.filter(s => (s.value || 0) > 0);
  const total = visible.reduce((s, x) => s + (x.value || 0), 0) || 1;
  const r = 34, circumference = 2 * Math.PI * r;

  let offset = 0;
  const arcs = visible.map((seg) => {
    const pct = seg.value / total;
    const arc = {
      color: resolveColor(seg.color),
      dash: pct * circumference,
      offset,
    };
    offset += pct * circumference;
    return arc;
  });

  const mainValue = centerValue ?? `${Math.round((visible[0]?.value ?? 0) / total * 100)}%`;
  const mainLabel = centerLabel ?? visible[0]?.label ?? '';

  return (
    <svg width={92} height={92} viewBox="0 0 92 92" style={{ flexShrink: 0 }}>
      <circle cx={46} cy={46} r={r} fill="none" stroke="var(--zinc-100)" strokeWidth={9} />
      {arcs.map((arc, i) => (
        <circle
          key={i}
          cx={46} cy={46} r={r} fill="none"
          stroke={arc.color} strokeWidth={9}
          strokeDasharray={`${arc.dash} ${circumference - arc.dash}`}
          strokeDashoffset={-arc.offset}
          strokeLinecap="butt"
          transform="rotate(-90 46 46)"
          style={{ transition: 'stroke-dasharray .5s ease' }}
        />
      ))}
      {/* key=mainValue：值变化时 SVG text remount，触发弹入动画 */}
      <text key={mainValue} x={46} y={mainLabel ? 44 : 48} textAnchor="middle" fontSize="18" fontWeight={700}
            fill="var(--text-primary)" fontFamily="var(--font-mono)"
            style={{ animation: 'sdui-pop .3s cubic-bezier(.2,.65,.4,1) both' }}>
        {mainValue}
      </text>
      {mainLabel && (
        <text x={46} y={58} textAnchor="middle" fontSize="9" fill="var(--text-tertiary)">{mainLabel}</text>
      )}
    </svg>
  );
}
