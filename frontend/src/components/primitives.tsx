'use client';

import { useEffect, useRef, useState, type CSSProperties, type ElementType, type ReactNode } from 'react';
import type { BadgeProps, ButtonProps, PanelProps } from '../types/components';

/* ── Badge ── */
const BADGE_STYLES = {
  default: { bg: 'var(--zinc-100)', color: 'var(--zinc-600)', border: 'var(--zinc-200)' },
  accent:  { bg: 'var(--accent-muted)', color: 'var(--accent)', border: 'transparent' },
  blue:    { bg: 'var(--blue-50)', color: 'var(--blue-700)', border: 'var(--blue-100)' },
  green:   { bg: 'var(--green-50)', color: 'var(--green-700)', border: 'var(--green-100)' },
  red:     { bg: 'var(--red-50)', color: 'var(--red-700)', border: 'var(--red-100)' },
  amber:   { bg: 'var(--amber-50)', color: 'var(--amber-700)', border: 'var(--amber-100)' },
  purple:  { bg: 'var(--purple-50)', color: 'var(--purple-600)', border: 'var(--purple-100)' },
  dark:    { bg: 'var(--zinc-800)', color: 'var(--zinc-100)', border: 'transparent' },
};

export function Badge({ tone = 'default', size = 'sm', dot = false, children }: BadgeProps & { tone?: keyof typeof BADGE_STYLES; size?: 'xs' | 'sm' | 'md' }) {
  const s = BADGE_STYLES[tone as keyof typeof BADGE_STYLES] || BADGE_STYLES.default;
  const fontSize = size === 'xs' ? '10px' : size === 'sm' ? '11px' : '12px';
  const padding = size === 'xs' ? '1px 5px' : size === 'sm' ? '2px 6px' : '3px 8px';
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      fontSize, fontWeight: 500, lineHeight: 1.4, padding,
      background: s.bg, color: s.color,
      border: `1px solid ${s.border}`,
      borderRadius: 'var(--radius-full)', whiteSpace: 'nowrap',
    }}>
      {dot && <span style={{ width: 5, height: 5, borderRadius: '50%', background: s.color, flexShrink: 0 }} />}
      {children}
    </span>
  );
}

/* ── Button ── */
const BTN_VARIANTS = {
  primary:  { bg: 'var(--accent)', color: '#fff', border: 'transparent', hover: 'var(--accent-hover)' },
  secondary: { bg: 'var(--zinc-100)', color: 'var(--text-primary)', border: 'var(--border)', hover: 'var(--zinc-200)' },
  ghost:    { bg: 'transparent', color: 'var(--text-secondary)', border: 'transparent', hover: 'var(--zinc-100)' },
  danger:   { bg: 'var(--red-50)', color: 'var(--red-700)', border: 'var(--red-100)', hover: 'var(--red-100)' },
  dark:     { bg: 'var(--zinc-800)', color: 'var(--zinc-100)', border: 'transparent', hover: 'var(--zinc-700)' },
};
const BTN_SIZES = {
  sm: { height: 'var(--ctrl-h-sm)', padding: '0 8px', fontSize: '12px', gap: 4 },
  md: { height: 'var(--ctrl-h)', padding: '0 12px', fontSize: '13px', gap: 6 },
  lg: { height: '40px', padding: '0 16px', fontSize: '14px', gap: 8 },
};

export function Button({ variant = 'primary', size = 'md', icon, iconRight, children, onClick, disabled, style }: ButtonProps & { variant?: keyof typeof BTN_VARIANTS; size?: keyof typeof BTN_SIZES }) {
  const v = BTN_VARIANTS[variant] || BTN_VARIANTS.primary;
  const s = BTN_SIZES[size] || BTN_SIZES.md;
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      className="claw-tactile claw-focus"
      style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        gap: s.gap, height: s.height, padding: s.padding,
        fontSize: s.fontSize, fontWeight: 500, lineHeight: 1,
        background: hover && !disabled ? v.hover : v.bg,
        color: v.color,
        border: `1px solid ${v.border}`,
        borderRadius: 'var(--radius-md)',
        opacity: disabled ? .5 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
        whiteSpace: 'nowrap',
        transition: 'background .12s',
        ...style,
      }}
    >
      {icon && <span style={{ display: 'flex', flexShrink: 0 }}>{icon}</span>}
      {children}
      {iconRight && <span style={{ display: 'flex', flexShrink: 0 }}>{iconRight}</span>}
    </button>
  );
}

/* ── Panel ── */
const PANEL_TONES = {
  default: { bg: 'var(--surface)',       border: 'var(--border)',         accent: null },
  raised:  { bg: 'var(--surface-raised)',border: 'var(--border)',         accent: null },
  accent:  { bg: 'var(--accent-muted)',  border: 'rgba(202,138,4,.2)',    accent: null },
  amber:   { bg: 'var(--amber-50)',      border: 'var(--amber-100)',      accent: '#d97706' },
  blue:    { bg: 'var(--blue-50)',       border: 'var(--blue-100)',       accent: 'var(--blue-600)' },
  red:     { bg: 'var(--red-50)',        border: 'var(--red-100)',        accent: 'var(--red-600)' },
  green:   { bg: 'var(--green-50)',      border: 'var(--green-100)',      accent: 'var(--green-600)' },
};

export function Panel({ title, subtitle, action, children, padding, as: Tag = 'div', tone = 'default', style }: PanelProps & { tone?: keyof typeof PANEL_TONES; as?: ElementType; padding?: string | number }) {
  const t = PANEL_TONES[tone] || PANEL_TONES.default;
  return (
    <Tag style={{
      background: t.bg,
      border: `1px solid ${t.border}`,
      ...(t.accent ? { borderLeft: `3px solid ${t.accent}` } : {}),
      borderRadius: 'var(--radius-lg)',
      boxShadow: 'var(--shadow-sm)',
      overflow: 'hidden',
      ...style,
    }}>
      {(title || action) && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: 'var(--sp-3) var(--pad-panel)',
          borderBottom: `1px solid ${t.border}`,
          gap: 8,
        }}>
          <div>
            {title && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                {t.accent && (
                  <span style={{ width: 3, height: 14, borderRadius: 2, background: t.accent, flexShrink: 0 }} />
                )}
                <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>{title}</span>
              </div>
            )}
            {subtitle && <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginTop: 1 }}>{subtitle}</div>}
          </div>
          {action && <div style={{ flexShrink: 0 }}>{action}</div>}
        </div>
      )}
      <div style={{ padding: padding ?? 'var(--pad-panel)' }}>{children}</div>
    </Tag>
  );
}

/* ── Stepper ── */
export function Stepper({ steps, currentIndex }: { steps: string[]; currentIndex: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0, overflow: 'hidden' }}>
      {steps.map((step, i) => {
        const done = i < currentIndex;
        const active = i === currentIndex;
        return (
          <div key={i} style={{ display: 'flex', alignItems: 'center', flex: i < steps.length - 1 ? 1 : 'none', minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
              <div style={{
                width: 20, height: 20,
                borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '10px', fontWeight: 700, lineHeight: 1,
                background: done ? 'var(--green-600)' : active ? 'var(--accent)' : 'var(--zinc-200)',
                color: done || active ? '#fff' : 'var(--zinc-500)',
                animation: active ? 'clawStepperPulse 1.4s ease-in-out infinite' : 'none',
                flexShrink: 0,
              }}>
                {done ? '✓' : i + 1}
              </div>
              <span style={{
                fontSize: 'var(--text-xs)', fontWeight: active ? 600 : 400,
                color: active ? 'var(--text-primary)' : done ? 'var(--text-secondary)' : 'var(--text-tertiary)',
                whiteSpace: 'nowrap',
              }}>{step}</span>
            </div>
            {i < steps.length - 1 && (
              <div style={{
                flex: 1, height: 1, minWidth: 12, maxWidth: 40, margin: '0 6px',
                background: i < currentIndex ? 'var(--green-600)' : 'var(--zinc-200)',
              }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ── AnimatedNumber ── */
export function AnimatedNumber({ value, decimals = 0, duration = 800, suffix = '', prefix = '' }: { value: number; decimals?: number; duration?: number; suffix?: string; prefix?: string }) {
  const [display, setDisplay] = useState(0);
  const startRef = useRef<number | null>(null);
  const prevRef = useRef(0);

  useEffect(() => {
    const from = prevRef.current;
    const to = value;
    prevRef.current = value;
    const start = performance.now();
    startRef.current = start;

    function tick(now: number) {
      if (startRef.current !== start) return;
      const t = Math.min((now - start) / duration, 1);
      const ease = 1 - Math.pow(1 - t, 3);
      setDisplay(from + (to - from) * ease);
      if (t < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }, [value, duration]);

  return (
    <span>{prefix}{display.toFixed(decimals)}{suffix}</span>
  );
}

/* ── Sparkline ── */
export function Sparkline({ points = [], width = 60, height = 24, color = 'var(--accent)', filled = false }: { points?: number[]; width?: number; height?: number; color?: string; filled?: boolean }) {
  if (!points.length) return <svg width={width} height={height} />;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const w = width, h = height;
  const xs = points.map((_, i) => (i / (points.length - 1)) * w);
  const ys = points.map(p => h - ((p - min) / range) * (h - 2) - 1);
  const d = xs.map((x, i) => `${i === 0 ? 'M' : 'L'}${x},${ys[i]}`).join(' ');
  const fillD = `${d} L${w},${h} L0,${h} Z`;
  return (
    <svg width={w} height={h} style={{ overflow: 'visible' }}>
      {filled && <path d={fillD} fill={color} fillOpacity={.15} />}
      <path d={d} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/* ── KPI ── */
export function KPI({ label, value, unit, suffix, decimals = 0, delta, tone = 'default', sparkline }: { label: string; value: number | string; unit?: string; suffix?: string; decimals?: number; delta?: number; tone?: string; sparkline?: number[] }) {
  const accentColor = tone === 'accent' ? 'var(--accent)' : tone === 'green' ? 'var(--green-600)' : tone === 'red' ? 'var(--red-600)' : tone === 'blue' ? 'var(--blue-600)' : 'var(--text-primary)';
  const numVal = typeof value === 'number' ? value : parseFloat(value) || 0;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', fontWeight: 500 }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
        <span style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: accentColor, fontVariantNumeric: 'tabular-nums', fontFamily: 'var(--font-mono)' }}>
          <AnimatedNumber value={numVal} decimals={decimals} />
        </span>
        {(unit || suffix) && <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', fontWeight: 500 }}>{unit || suffix}</span>}
        {sparkline && <div style={{ marginLeft: 'auto' }}><Sparkline points={sparkline} color={accentColor} filled /></div>}
      </div>
      {delta != null && (
        <div style={{ fontSize: 'var(--text-xs)', color: delta >= 0 ? 'var(--green-600)' : 'var(--red-600)' }}>
          {delta >= 0 ? '▲' : '▼'} {Math.abs(delta)}%
        </div>
      )}
    </div>
  );
}

/* ── FileKindBadge ── */
const EXT_STYLES = {
  xlsx: { bg: '#16a34a', label: 'XLS' },
  xls:  { bg: '#16a34a', label: 'XLS' },
  csv:  { bg: '#059669', label: 'CSV' },
  pdf:  { bg: '#dc2626', label: 'PDF' },
  docx: { bg: '#2563eb', label: 'DOC' },
  doc:  { bg: '#2563eb', label: 'DOC' },
  pptx: { bg: '#d97706', label: 'PPT' },
  png:  { bg: '#7c3aed', label: 'PNG' },
  jpg:  { bg: '#7c3aed', label: 'JPG' },
  jpeg: { bg: '#7c3aed', label: 'JPG' },
  json: { bg: '#0891b2', label: 'JSON' },
  md:   { bg: '#475569', label: 'MD' },
  txt:  { bg: '#71717a', label: 'TXT' },
};

export function FileKindBadge({ ext = '', size = 28 }: { ext?: string; size?: number }) {
  const e = (ext || '').toLowerCase().replace(/^\./, '');
  const style = EXT_STYLES[e as keyof typeof EXT_STYLES] || { bg: 'var(--zinc-500)', label: e.toUpperCase().slice(0, 3) || 'FILE' };
  return (
    <div style={{
      width: size, height: size,
      borderRadius: 'var(--radius-sm)',
      background: style.bg,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: size > 24 ? '9px' : '8px', fontWeight: 700, color: '#fff',
      fontFamily: 'var(--font-mono)', flexShrink: 0, letterSpacing: '-.02em',
    }}>
      {style.label}
    </div>
  );
}

/* ── FileChip ── */
export function FileChip({ file, onClick, output = false, justUploaded = false }: { file: { name: string; size?: number }; onClick?: () => void; output?: boolean; justUploaded?: boolean }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => { if (justUploaded) { const t = setTimeout(() => setMounted(true), 10); return () => clearTimeout(t); } else { setMounted(true); } }, [justUploaded]);

  const ext = (file.name || '').split('.').pop();
  const kb = file.size ? (file.size / 1024).toFixed(0) : null;
  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 6,
        padding: '5px 8px', borderRadius: 'var(--radius-md)',
        background: output ? 'var(--green-50)' : 'var(--surface)',
        border: `1px solid ${output ? 'var(--green-100)' : 'var(--border)'}`,
        cursor: onClick ? 'pointer' : 'default',
        transition: 'background .12s',
        animation: justUploaded && mounted ? 'clawSpringIn .4s ease forwards' : 'none',
        opacity: justUploaded && !mounted ? 0 : 1,
      }}
    >
      <FileKindBadge ext={ext} size={24} />
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 500, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 120 }}>
          {file.name}
        </div>
        {kb && <div style={{ fontSize: '10px', color: 'var(--text-tertiary)' }}>{kb} KB</div>}
      </div>
      {output && (
        <span style={{ marginLeft: 'auto', fontSize: '10px', color: 'var(--green-600)', fontWeight: 500 }}>输出</span>
      )}
    </div>
  );
}

/* ── Progress ── */
export function Progress({ value = 0, status = 'default', height = 6, showValue = false }: { value?: number; status?: string; height?: number; showValue?: boolean }) {
  const isRunning = status === 'running';
  const color = status === 'done' ? 'var(--green-600)' : status === 'error' ? 'var(--red-600)' : 'var(--accent)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{
        flex: 1, height, borderRadius: height,
        background: 'var(--zinc-100)', overflow: 'hidden', position: 'relative',
      }}>
        <div
          className={isRunning ? 'claw-flow-bar' : ''}
          style={{
            height: '100%', width: `${Math.min(100, Math.max(0, value))}%`,
            background: isRunning ? undefined : color,
            borderRadius: height,
            transition: 'width .4s ease',
          }}
        />
      </div>
      {showValue && (
        <span style={{ fontSize: '10px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', flexShrink: 0, minWidth: 28, textAlign: 'right' }}>
          {value}%
        </span>
      )}
    </div>
  );
}

/* ── Skeleton ── */
export function Skeleton({ width = '100%', height = 16, radius = 4, style }: { width?: string | number; height?: number; radius?: number; style?: CSSProperties }) {
  return (
    <div
      className="claw-shimmer"
      style={{ width, height, borderRadius: radius, flexShrink: 0, ...style }}
    />
  );
}

/* ── StreamingText ── */
export function StreamingText({ text = '', speed = 18, showCaret = true, onDone }: { text?: string; speed?: number; showCaret?: boolean; onDone?: () => void }) {
  const [displayed, setDisplayed] = useState('');
  const [done, setDone] = useState(false);
  const idxRef = useRef(0);
  const textRef = useRef(text);

  useEffect(() => {
    textRef.current = text;
    idxRef.current = 0;
    setDisplayed('');
    setDone(false);
    const interval = setInterval(() => {
      idxRef.current += 1;
      setDisplayed(textRef.current.slice(0, idxRef.current));
      if (idxRef.current >= textRef.current.length) {
        clearInterval(interval);
        setDone(true);
        onDone?.();
      }
    }, speed);
    return () => clearInterval(interval);
  }, [text, speed]);

  return (
    <span>
      {displayed}
      {showCaret && !done && <span className="claw-caret" />}
    </span>
  );
}
