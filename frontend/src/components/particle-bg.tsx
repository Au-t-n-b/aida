'use client';

/**
 * ParticleBg
 * ----------
 * Light-mode B2B constellation background (Stripe / Notion / SAP Joule style).
 * Pure CSS animation + a lightweight rAF loop. No <canvas>, no third-party libs.
 *
 * - White → pearl radial base + corner vignette
 * - 112 nodes across 3 depth layers (far / mid / near)
 * - Organic drift via per-frame angle jitter + edge-bounce
 * - Triangulated link mesh: 5 SVG <path> buckets faded by distance
 * - Cursor parallax: depth layers shift opposite the pointer
 * - Breathing opacity envelope 0.82 → 1.0, 4.5 s ease-in-out
 * - Staggered entrance: opacity 0 + translateY(8px) → settle
 */

import { useEffect, useMemo, useRef } from 'react';

export interface ParticleBgProps {
  className?: string;
  style?: React.CSSProperties;
  /** node count (default 112) */
  count?: number;
  /** link distance in px (default 150) */
  linkDist?: number;
}

type Depth = 'far' | 'mid' | 'near';

interface Particle {
  x: number;
  y: number;
  angle: number;
  speed: number;
  depth: Depth;
  size: number;
  opacity: number;
  color: string;
  glow: string;
  delay: number;
}

const DEFAULT_COUNT = 112;
const DEFAULT_LINK = 150;
const MAX_RED = 4;
const BUCKETS = 5;

// Gravity / nebula centre (normalised)
// const GX = 0.5, GY = 0.52; // unused in steady-drift mode

const DEPTH_TABLE: Record<Depth, { size: number; opacity: number; speed: number; amp: number }> = {
  far:  { size: 1.6, opacity: 0.26, speed: 0.00060, amp: 6  },
  mid:  { size: 3.2, opacity: 0.42, speed: 0.00100, amp: 14 },
  near: { size: 5.4, opacity: 0.62, speed: 0.00150, amp: 26 },
};

const STEEL      = '#8492a8';
const SLATE      = '#5d6b85';
const SILVER     = '#b9c4d6';
const BRAND_RED  = '#C7000A';
const LINK_COLOR = '#94a3b8';

const BUCKET_OPACITY = [0.22, 0.16, 0.11, 0.07, 0.04];

const rand = (a: number, b: number) => a + Math.random() * (b - a);

/** Deterministic PRNG — same output on server & client to avoid hydration mismatch. */
function createRng(seed: number) {
  let state = seed >>> 0;
  return () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    return state / 0x100000000;
  };
}

function buildParticles(count: number, seed = 0x41494441): Particle[] {
  const random = createRng(seed);
  const randSeeded = (a: number, b: number) => a + random() * (b - a);

  const pickDepth = (): Depth => {
    const r = random();
    if (r < 0.4) return 'far';
    if (r < 0.8) return 'mid';
    return 'near';
  };

  const list: Particle[] = [];
  let reds = 0;

  for (let i = 0; i < count; i++) {
    const depth = pickDepth();
    const cfg = DEPTH_TABLE[depth];

    let color = STEEL;
    let glow  = 'transparent';
    const roll = random();

    if (roll > 0.95 && reds < MAX_RED) {
      color = BRAND_RED;
      glow  = 'rgba(199,0,10,0.35)';
      reds++;
    } else if (roll > 0.74) {
      color = depth === 'far' ? STEEL : SLATE;
    } else if (roll > 0.62) {
      color = SILVER;
    } else if (depth === 'near') {
      glow = 'rgba(99,113,143,0.18)';
    }

    // Slight downward bias so the lower half stays populated
    let py = random();
    if (random() < 0.22) py = 0.5 + random() * 0.5;

    list.push({
      x: random(),
      y: py,
      angle: randSeeded(0, Math.PI * 2),
      speed: cfg.speed * randSeeded(0.8, 1.25),
      depth,
      size:    cfg.size,
      opacity: cfg.opacity,
      color,
      glow,
      delay: randSeeded(0, 1.0),
    });
  }
  return list;
}

// --------------------------------------------------------------------------
// Static style constants
// --------------------------------------------------------------------------

const VIGNETTE_STYLE: React.CSSProperties = {
  position: 'absolute', inset: 0, pointerEvents: 'none',
  background:
    'radial-gradient(120% 120% at 0% 0%,   rgba(148,163,184,0.06), transparent 26%),' +
    'radial-gradient(120% 120% at 100% 0%,  rgba(148,163,184,0.06), transparent 26%),' +
    'radial-gradient(120% 120% at 0% 100%,  rgba(148,163,184,0.06), transparent 26%),' +
    'radial-gradient(120% 120% at 100% 100%,rgba(148,163,184,0.06), transparent 26%)',
};

const GLOW_STYLE: React.CSSProperties = {
  position: 'absolute', top: '50%', left: '50%',
  width: 240, height: 240, marginLeft: -120, marginTop: -120,
  pointerEvents: 'none',
  background: 'radial-gradient(circle at 50% 50%, rgba(199,0,10,0.045) 0%, transparent 70%)',
  animation: 'pbBreathe 4.5s ease-in-out infinite',
};

const BREATH_STYLE: React.CSSProperties = {
  position: 'absolute', inset: 0,
  animation: 'pbBreathe 4.5s ease-in-out infinite',
};

const CLEARZONE_STYLE: React.CSSProperties = {
  position: 'absolute', inset: 0, pointerEvents: 'none',
  background:
    'radial-gradient(58% 26% at 50% 47%, rgba(255,255,255,0.74) 0%, rgba(255,255,255,0.3) 42%, transparent 74%)',
};

const KEYFRAMES = `
@keyframes pbBreathe { 0%,100%{opacity:.82} 50%{opacity:1} }
@keyframes pbFadeIn  { from{opacity:0;transform:translateY(8px)} to{opacity:var(--pb-op,.4);transform:translateY(0)} }
`;

// --------------------------------------------------------------------------
// Component
// --------------------------------------------------------------------------

export default function ParticleBg({
  className,
  style,
  count    = DEFAULT_COUNT,
  linkDist = DEFAULT_LINK,
}: ParticleBgProps) {
  const rootRef  = useRef<HTMLDivElement>(null);
  const pathRefs = useRef<Array<SVGPathElement | null>>([]);
  const dotRefs  = useRef<Array<HTMLDivElement | null>>([]);
  const rafRef   = useRef<number>(0);
  const reduceMotion = useRef(false);

  const particles = useMemo(() => buildParticles(count), [count]);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;

    reduceMotion.current =
      typeof window !== 'undefined' &&
      !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

    let w = root.clientWidth  || 1;
    let h = root.clientHeight || 1;

    const ro = new ResizeObserver(() => {
      w = root.clientWidth  || 1;
      h = root.clientHeight || 1;
    });
    ro.observe(root);

    const buckets: string[] = new Array(BUCKETS).fill('') as string[];
    const sx = new Float32Array(particles.length);
    const sy = new Float32Array(particles.length);

    let ptx = 0, pty = 0, pox = 0, poy = 0;

    const onMove = (e: MouseEvent) => {
      const r = root.getBoundingClientRect();
      ptx = (e.clientX - r.left) / r.width  - 0.5;
      pty = (e.clientY - r.top)  / r.height - 0.5;
    };
    const onLeave = () => { ptx = 0; pty = 0; };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseleave', onLeave);

    const step = () => {
      pox += (ptx - pox) * 0.05;
      poy += (pty - poy) * 0.05;

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i]!;

        if (!reduceMotion.current) {
          p.angle += rand(-0.025, 0.025);
          p.x += Math.cos(p.angle) * p.speed;
          p.y += Math.sin(p.angle) * p.speed;
          if (p.x < 0) { p.x = 0; p.angle = Math.PI - p.angle; }
          else if (p.x > 1) { p.x = 1; p.angle = Math.PI - p.angle; }
          if (p.y < 0) { p.y = 0; p.angle = -p.angle; }
          else if (p.y > 1) { p.y = 1; p.angle = -p.angle; }
        }

        const amp = DEPTH_TABLE[p.depth].amp;
        const X = p.x * w - pox * amp;
        const Y = p.y * h - poy * amp;
        sx[i] = X;
        sy[i] = Y;
        const el = dotRefs.current[i];
        if (el) el.style.transform = `translate3d(${X}px,${Y}px,0)`;
      }

      for (let b = 0; b < BUCKETS; b++) buckets[b] = '';

      const limit2 = linkDist * linkDist;
      for (let i = 0; i < particles.length; i++) {
        const ax = sx[i]!;
        const ay = sy[i]!;
        for (let j = i + 1; j < particles.length; j++) {
          const dx = ax - sx[j]!, dy = ay - sy[j]!;
          const d2 = dx * dx + dy * dy;
          if (d2 < limit2) {
            const t  = Math.sqrt(d2) / linkDist;
            let   bk = (t * BUCKETS) | 0;
            if (bk >= BUCKETS) bk = BUCKETS - 1;
            buckets[bk] += `M${ax.toFixed(1)} ${ay.toFixed(1)}L${sx[j]!.toFixed(1)} ${sy[j]!.toFixed(1)}`;
          }
        }
      }

      for (let b = 0; b < BUCKETS; b++) {
        pathRefs.current[b]?.setAttribute('d', buckets[b]!);
      }

      rafRef.current = requestAnimationFrame(step);
    };

    step(); // synchronous first paint so positions are correct on frame 0

    return () => {
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseleave', onLeave);
    };
  }, [particles, linkDist]);

  const rootStyle: React.CSSProperties = {
    position: 'absolute', inset: 0, overflow: 'hidden',
    pointerEvents: 'none', zIndex: 0,
    background: 'radial-gradient(150% 100% at 50% 18%, #ffffff 0%, #ffffff 52%, #f4f7fb 100%)',
    ...style,
  };

  return (
    <div ref={rootRef} className={className} style={rootStyle} aria-hidden="true">
      <style>{KEYFRAMES}</style>
      <div style={VIGNETTE_STYLE} />
      <div style={GLOW_STYLE} />
      <div style={BREATH_STYLE}>
        <svg width="100%" height="100%" style={{ position: 'absolute', inset: 0, display: 'block' }}>
          {BUCKET_OPACITY.map((op, b) => (
            <path
              key={b}
              ref={el => { pathRefs.current[b] = el; }}
              d=""
              stroke={LINK_COLOR}
              strokeWidth={b === 0 ? 0.7 : 0.5}
              strokeLinecap="round"
              fill="none"
              style={{ opacity: op }}
            />
          ))}
        </svg>

        {particles.map((p, i) => (
          <div
            key={i}
            ref={el => { dotRefs.current[i] = el; }}
            style={{ position: 'absolute', top: 0, left: 0, willChange: 'transform' }}
          >
            <div style={{
              width: p.size, height: p.size,
              marginLeft: -p.size / 2, marginTop: -p.size / 2,
              borderRadius: '50%', background: p.color,
              opacity: 0,
              animation: `pbFadeIn 1.4s cubic-bezier(0.22,0.61,0.36,1) ${p.delay}s forwards`,
              ['--pb-op' as string]: p.opacity,
              boxShadow: p.glow === 'transparent' ? 'none' : `0 0 ${p.size * 2.2}px ${p.glow}`,
            } as React.CSSProperties} />
          </div>
        ))}
      </div>
      <div style={CLEARZONE_STYLE} />
    </div>
  );
}
