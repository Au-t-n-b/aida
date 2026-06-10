/* ──────────────────────────────────────────────────────────────────────────
   glassIntro — 玻璃登录页入场编排 (vanilla canvas + rAF)
   ----------------------------------------------------------------------------
   1) 暗场中光晕点(bokeh)闪烁、漂浮
   2) 它们沿同一拍缓起→匀速→缓停地飞向目标(背景灯位 / 卡片边缘)
   3) logo 克隆在中央虚化浮现，再与光晕点同拍飞回左上角，落定时真 logo 显形，
      卡片解析聚焦、决策图开始游走。
   FLIP：克隆终态为 transform:none 落在真 logo 测得的 rect 上，落点像素级一致。

   与原版差异：原版把 settled / logo-pinned 加在 document.body 上，并含
   embedded/postMessage/sessionStorage/unstick 等为受限预览环境写的兜底。
   迁到真实框架后这些都不需要——这里把状态类加在传入的 root 上，CSS 选择器相应
   用 .lg-root.settled / .lg-root.logo-pinned。
   ────────────────────────────────────────────────────────────────────────── */

interface Part {
  x: number;
  y: number;
  sx0: number;
  sy0: number;
  tx: number;
  ty: number;
  type: 'card' | 'bg';
  color: string;
  size: number;
  baseA: number;
  ph: number;
  spd: number;
  drift: number;
}

interface IntroOptions {
  /** 决策图开始游走的回调（在 GRAPH_AT 时刻触发） */
  startGraph?: () => void;
  /** 强制走精简快速版（默认读取 prefers-reduced-motion） */
  reduce?: boolean;
}

export function initGlassIntro(root: HTMLElement, opts: IntroOptions = {}): () => void {
  const canvas = root.querySelector<HTMLCanvasElement>('#lg-spark');
  if (!canvas) return () => {};
  const ctx = canvas.getContext('2d')!;
  let W = 0;
  let H = 0;
  let dpr = 1;

  const reduce =
    opts.reduce ?? (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

  // timeline (ms) — logo emerges, then logo + glints fly home on ONE shared beat
  let FLY_AT = 1650;
  let FLY_MS = 1400;
  let TWK = FLY_AT;
  let SETTLE = FLY_MS;
  let REVEAL_AT = FLY_AT + 120;
  let GRAPH_AT = REVEAL_AT + 480;
  let DONE_AT = TWK + SETTLE + 700;
  if (reduce) {
    TWK = 200;
    SETTLE = 500;
    FLY_AT = 200;
    FLY_MS = 500;
    REVEAL_AT = 240;
    GRAPH_AT = 360;
    DONE_AT = 800;
  }

  const COLORS = ['245,177,74', '120,200,235', '90,150,230', '220,232,248'];
  const WEIGHTS = [0.42, 0.28, 0.16, 0.14];
  function pickColor() {
    const r = Math.random();
    let a = 0;
    for (let i = 0; i < WEIGHTS.length; i++) {
      a += WEIGHTS[i]!;
      if (r <= a) return COLORS[i]!;
    }
    return COLORS[0]!;
  }

  const CLUSTERS = [
    { x: 0.1, y: 0.3, sx: 0.12, sy: 0.3, w: 5 },
    { x: 0.2, y: 0.62, sx: 0.13, sy: 0.28, w: 4 },
    { x: 0.34, y: 0.42, sx: 0.08, sy: 0.3, w: 3 },
    { x: 0.74, y: 0.3, sx: 0.04, sy: 0.22, w: 3 },
    { x: 0.88, y: 0.34, sx: 0.07, sy: 0.26, w: 2 },
  ];
  function bgTarget() {
    const tot = CLUSTERS.reduce((s, c) => s + c.w, 0);
    const r = Math.random() * tot;
    let a = 0;
    let c = CLUSTERS[0]!;
    for (let i = 0; i < CLUSTERS.length; i++) {
      a += CLUSTERS[i]!.w;
      if (r <= a) {
        c = CLUSTERS[i]!;
        break;
      }
    }
    const g = () => (Math.random() + Math.random() + Math.random()) / 3 - 0.5; // ~gaussian
    return { x: (c.x + g() * c.sx) * W, y: (c.y + g() * c.sy) * H };
  }

  function cardRect() {
    const el = root.querySelector('#lg-card');
    if (!el) return null;
    const r = el.getBoundingClientRect();
    if (!r.width) return null;
    return r;
  }

  function perimeterTarget(rect: DOMRect) {
    const corners = [
      [rect.left, rect.top],
      [rect.right, rect.top],
      [rect.right, rect.bottom],
      [rect.left, rect.bottom],
    ];
    if (Math.random() < 0.5) {
      const c = corners[(Math.random() * 4) | 0]!;
      return { x: c[0]! + (Math.random() - 0.5) * 26, y: c[1]! + (Math.random() - 0.5) * 26 };
    }
    const per = 2 * (rect.width + rect.height);
    const d = Math.random() * per;
    let x: number;
    let y: number;
    if (d < rect.width) {
      x = rect.left + d;
      y = rect.top;
    } else if (d < rect.width + rect.height) {
      x = rect.right;
      y = rect.top + (d - rect.width);
    } else if (d < 2 * rect.width + rect.height) {
      x = rect.right - (d - rect.width - rect.height);
      y = rect.bottom;
    } else {
      x = rect.left;
      y = rect.bottom - (d - 2 * rect.width - rect.height);
    }
    return { x, y };
  }

  let parts: Part[] = [];
  function build() {
    parts = [];
    const rect = cardRect();
    const N = Math.round(Math.min(86, Math.max(46, (W * H) / 26000)));
    for (let i = 0; i < N; i++) {
      const onCard = !!rect && Math.random() < 0.42;
      const tgt = onCard ? perimeterTarget(rect) : bgTarget();
      parts.push({
        x: Math.random() * W,
        y: Math.random() * H,
        sx0: 0,
        sy0: 0,
        tx: tgt.x,
        ty: tgt.y,
        type: onCard ? 'card' : 'bg',
        color: pickColor(),
        size: onCard ? 1.6 + Math.random() * 1.8 : 2.5 + Math.random() * 5.5,
        baseA: onCard ? 0.5 + Math.random() * 0.4 : 0.35 + Math.random() * 0.45,
        ph: Math.random() * Math.PI * 2,
        spd: 0.6 + Math.random() * 1.1,
        drift: 0.2 + Math.random() * 0.5,
      });
    }
    parts.forEach((p) => {
      p.sx0 = p.x;
      p.sy0 = p.y;
    });
  }

  function resize() {
    W = window.innerWidth;
    H = window.innerHeight;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas!.width = W * dpr;
    canvas!.height = H * dpr;
    canvas!.style.width = W + 'px';
    canvas!.style.height = H + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  // smooth ease-in-out (gentle start → steady glide → gentle stop)
  const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

  let t0 = performance.now();
  let raf = 0;
  let disposed = false;

  function reveal() {
    if (!root.classList.contains('settled')) root.classList.add('settled');
  }
  function startGraph() {
    opts.startGraph?.();
  }

  function frame(now: number) {
    if (disposed) return;
    const T = now - t0;
    ctx.clearRect(0, 0, W, H);

    const settleP = T <= TWK ? 0 : Math.min(1, (T - TWK) / SETTLE);
    const sp = ease(settleP);

    for (let i = 0; i < parts.length; i++) {
      const p = parts[i]!;
      const driftX = Math.sin(now * 0.0006 * p.spd + p.ph) * 10 * p.drift;
      const driftY = Math.cos(now * 0.0005 * p.spd + p.ph) * 10 * p.drift;
      const baseX = p.sx0 + driftX;
      const baseY = p.sy0 + driftY;
      const x = baseX + (p.tx - baseX) * sp;
      const y = baseY + (p.ty - baseY) * sp;

      const twk = 0.45 + 0.55 * (0.5 + 0.5 * Math.sin(now * 0.004 * p.spd + p.ph));
      const fadeIn = Math.min(1, T / 420);
      let a = p.baseA * twk * fadeIn;
      let bloom = 1;
      let coreF = 1;
      if (settleP >= 1) {
        if (p.type === 'bg') {
          const after = Math.min(1, (T - TWK - SETTLE) / 1000);
          const ae = after < 0.5 ? 2 * after * after : 1 - Math.pow(-2 * after + 2, 2) / 2;
          bloom = 1 + ae * 2.6;
          coreF = Math.max(0, 1 - ae * 1.6);
          a = p.baseA * (0.55 + 0.45 * twk) * (1 - ae * 0.92);
        } else {
          a = p.baseA * (0.4 + 0.45 * twk);
        }
      }
      if (a <= 0.004) continue;

      const sz = p.size * (1 + (1 - sp) * 0.45) * bloom;
      const R = sz * 2.4;
      const g = ctx.createRadialGradient(x, y, 0, x, y, R);
      g.addColorStop(0, 'rgba(' + p.color + ',' + a + ')');
      g.addColorStop(0.35, 'rgba(' + p.color + ',' + a * 0.55 + ')');
      g.addColorStop(0.7, 'rgba(' + p.color + ',' + a * 0.2 + ')');
      g.addColorStop(1, 'rgba(' + p.color + ',0)');
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(x, y, R, 0, Math.PI * 2);
      ctx.fill();
      if (coreF > 0.01) {
        ctx.fillStyle = 'rgba(' + p.color + ',' + Math.min(1, a * 1.5) * coreF + ')';
        ctx.beginPath();
        ctx.arc(x, y, p.size * 0.55, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    if (T < DONE_AT + 4000) {
      stepFlight(now);
      raf = requestAnimationFrame(frame);
    } else {
      stepFlight(now);
      ambient();
    }
  }

  function ambient() {
    const glints = parts.filter((p) => p.type === 'card');
    function loop(now: number) {
      if (disposed) return;
      ctx.clearRect(0, 0, W, H);
      for (let i = 0; i < glints.length; i++) {
        const p = glints[i]!;
        const twk = 0.4 + 0.6 * (0.5 + 0.5 * Math.sin(now * 0.0028 * p.spd + p.ph));
        const a = p.baseA * 0.5 * twk;
        const x = p.tx + Math.sin(now * 0.0004 + p.ph) * 3;
        const y = p.ty + Math.cos(now * 0.00035 + p.ph) * 3;
        const sz = p.size;
        const g = ctx.createRadialGradient(x, y, 0, x, y, sz * 2.4);
        g.addColorStop(0, 'rgba(' + p.color + ',' + a + ')');
        g.addColorStop(1, 'rgba(' + p.color + ',0)');
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(x, y, sz * 2.4, 0, Math.PI * 2);
        ctx.fill();
      }
      raf = requestAnimationFrame(loop);
    }
    raf = requestAnimationFrame(loop);
  }

  // ── intro logo clone: big centre with sparks, then pins onto the real logo ──
  const brandEl = root.querySelector<HTMLElement>('.lg-visual .lg-brand');
  let introBrand: HTMLElement | null = null;
  let flight: { t0: number; dx: number; dy: number; s: number } | null = null;
  let bigOffset = { dx: 0, dy: 0, s: 1 };
  const homeRect = () => brandEl!.getBoundingClientRect();

  function setupLogo() {
    if (!brandEl) return;
    introBrand = brandEl.cloneNode(true) as HTMLElement;
    introBrand.classList.add('lg-intro-brand');
    root.appendChild(introBrand);
    placeBig();
  }
  function placeBig() {
    if (!introBrand) return;
    const r = homeRect();
    introBrand.style.left = r.left + 'px';
    introBrand.style.top = r.top + 'px';
    introBrand.style.transformOrigin = 'left top';
    introBrand.style.transition = 'none';
    introBrand.style.transform = 'none';
    const cr = introBrand.getBoundingClientRect();
    const S = window.innerWidth < 760 ? 2.0 : 2.8;
    const destX = (window.innerWidth - cr.width * S) / 2;
    const destY = (window.innerHeight - cr.height * S) / 2;
    introBrand.style.transform =
      'translate(' + (destX - cr.left) + 'px,' + (destY - cr.top) + 'px) scale(' + S + ')';
    bigOffset = { dx: destX - cr.left, dy: destY - cr.top, s: S };
    introBrand.style.opacity = '0';
    introBrand.style.filter = 'blur(12px) brightness(1.4) drop-shadow(0 0 4px rgba(130,165,230,0))';
  }
  function fadeLogoIn() {
    if (!introBrand) return;
    introBrand.style.transition =
      'opacity 1.25s cubic-bezier(.4,.12,.22,1), filter 1.5s cubic-bezier(.4,.12,.22,1)';
    introBrand.style.opacity = '1';
    introBrand.style.filter =
      'blur(0px) brightness(1.08) drop-shadow(0 0 26px rgba(130,165,230,.85)) drop-shadow(0 0 60px rgba(130,165,230,.45))';
  }
  function pinLogo() {
    if (!introBrand) {
      root.classList.add('logo-pinned');
      return;
    }
    if (flight) return;
    const r = homeRect();
    introBrand.style.left = r.left + 'px';
    introBrand.style.top = r.top + 'px';
    introBrand.style.transition = 'none';
    flight = { t0: performance.now(), dx: bigOffset.dx, dy: bigOffset.dy, s: bigOffset.s };
  }

  // advance the logo's home-flight one frame (called from the particle rAF loop)
  function stepFlight(now: number) {
    if (!flight || !introBrand) return;
    const fp = Math.min(1, (now - flight.t0) / FLY_MS);
    const fe = ease(fp);
    const rem = 1 - fe;
    const dx = flight.dx * rem;
    const dy = flight.dy * rem;
    const s = 1 + (flight.s - 1) * rem;
    introBrand.style.transform = 'translate(' + dx + 'px,' + dy + 'px) scale(' + s + ')';
    introBrand.style.filter =
      'blur(0px) brightness(' +
      (1 + 0.08 * rem) +
      ') drop-shadow(0 0 ' +
      26 * rem +
      'px rgba(130,165,230,' +
      0.85 * rem +
      ')) drop-shadow(0 0 ' +
      60 * rem +
      'px rgba(130,165,230,' +
      0.45 * rem +
      '))';
    if (fp >= 1) {
      flight = null;
      root.classList.add('logo-pinned');
      const clone = introBrand;
      introBrand = null;
      clone.style.transition = 'opacity .34s ease';
      clone.style.opacity = '0';
      window.setTimeout(() => {
        if (clone && clone.parentNode) clone.parentNode.removeChild(clone);
      }, 360);
    }
  }

  // click anywhere to skip the intro
  function skip() {
    if (root.classList.contains('settled')) return;
    t0 = performance.now() - (TWK + SETTLE);
    reveal();
    startGraph();
    flight = null;
    if (introBrand) {
      const clone = introBrand;
      introBrand = null;
      clone.parentNode && clone.parentNode.removeChild(clone);
    }
    root.classList.add('logo-pinned');
  }

  function onResize() {
    resize();
    if (introBrand && !root.classList.contains('logo-pinned')) placeBig();
  }

  resize();
  build();
  setupLogo();
  requestAnimationFrame(fadeLogoIn);
  window.addEventListener('resize', onResize);
  window.addEventListener('pointerdown', skip, { once: true });

  const tReveal = window.setTimeout(reveal, REVEAL_AT);
  const tPin = window.setTimeout(pinLogo, FLY_AT);
  const tGraph = window.setTimeout(startGraph, GRAPH_AT);
  raf = requestAnimationFrame(frame);

  return () => {
    disposed = true;
    cancelAnimationFrame(raf);
    clearTimeout(tReveal);
    clearTimeout(tPin);
    clearTimeout(tGraph);
    window.removeEventListener('resize', onResize);
    window.removeEventListener('pointerdown', skip);
    if (introBrand && introBrand.parentNode) introBrand.parentNode.removeChild(introBrand);
  };
}
