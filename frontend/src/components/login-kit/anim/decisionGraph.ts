/* ──────────────────────────────────────────────────────────────────────────
   decisionGraph — 玻璃登录页左侧的「推理决策图」(vanilla canvas)
   ----------------------------------------------------------------------------
   5×5 玻璃节点格栅，一束彗星状的「推理光」逐节点游走，点亮经过的连线，
   节点上有激活涟漪、镜面高光、随光标的微视差。DPR 自适应。
   原导出 window.__lgGraphStart(delayMs)；此处改为 init() 返回 { start, destroy }。
   ────────────────────────────────────────────────────────────────────────── */

interface GraphNode {
  gx: number;
  gy: number;
  bx: number;
  by: number;
  x: number;
  y: number;
  act: number;
  hover: number;
  ripple: number;
  pulse: number;
}
interface TrailEdge {
  from: number;
  to: number;
  t: number;
}

export interface DecisionGraphHandle {
  /** 在 delayMs 之后开始让推理光游走 */
  start: (delayMs?: number) => void;
  /** 停止渲染、移除监听 */
  destroy: () => void;
}

export function initDecisionGraph(
  canvas: HTMLCanvasElement,
  host: HTMLElement,
): DecisionGraphHandle {
  const ctx = canvas.getContext('2d')!;

  const COLS = 5;
  const ROWS = 5;
  let nodes: GraphNode[] = [];
  let W = 0;
  let H = 0;
  let dpr = 1;
  let gapX = 0;
  let gapY = 0;
  let cx = 0;
  let cy = 0;
  const mouse = { x: -9999, y: -9999, active: false };
  const me = { x: 0, y: 0 }; // eased cursor (parallax + specular)

  let cur = 0;
  let prev = -1;
  let nextI = -1;
  let trail: TrailEdge[] = []; // committed edges (fading tail)
  let prog = 0;
  const EDGE_MS = 640; // ms per edge — continuous, no pause
  let settleAt = 0;

  const GB = '175,205,240'; // low-saturation whitish bright blue

  const idx = (gx: number, gy: number) => gy * COLS + gx;
  const ekey = (a: number, b: number) => (a < b ? a + '_' + b : b + '_' + a);

  function layout() {
    const r = canvas.getBoundingClientRect();
    W = r.width;
    H = r.height;
    if (!W || !H) return;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const span = Math.min(W, H) * 0.78;
    const ox = (W - span) / 2;
    const oy = (H - span) / 2;
    cx = W / 2;
    cy = H / 2;
    gapX = span / (COLS - 1);
    gapY = span / (ROWS - 1);
    nodes.forEach((n) => {
      n.bx = ox + n.gx * gapX;
      n.by = oy + n.gy * gapY;
      n.x = n.bx;
      n.y = n.by;
    });
  }

  function build() {
    nodes = [];
    for (let gy = 0; gy < ROWS; gy++) {
      for (let gx = 0; gx < COLS; gx++) {
        nodes.push({ gx, gy, bx: 0, by: 0, x: 0, y: 0, act: 0, hover: 0, ripple: 0, pulse: Math.random() * Math.PI * 2 });
      }
    }
    cur = idx((Math.random() * COLS) | 0, (Math.random() * ROWS) | 0);
    prev = -1;
    nodes[cur]!.act = 1;
    nodes[cur]!.ripple = 1;
    nextI = pickNext();
    prog = 0;
  }

  function neighbors(i: number) {
    const n = nodes[i]!;
    const out: number[] = [];
    if (n.gx > 0) out.push(idx(n.gx - 1, n.gy));
    if (n.gx < COLS - 1) out.push(idx(n.gx + 1, n.gy));
    if (n.gy > 0) out.push(idx(n.gx, n.gy - 1));
    if (n.gy < ROWS - 1) out.push(idx(n.gx, n.gy + 1));
    return out;
  }

  function pickNext() {
    let opts = neighbors(cur).filter((i) => i !== prev);
    if (!opts.length) opts = neighbors(cur);
    if (mouse.active) {
      let best = Infinity;
      let pick = opts[0]!;
      opts.forEach((i) => {
        const ni = nodes[i]!;
        let d = (ni.bx - mouse.x) * (ni.bx - mouse.x) + (ni.by - mouse.y) * (ni.by - mouse.y);
        d *= 0.7 + Math.random() * 0.6;
        if (d < best) {
          best = d;
          pick = i;
        }
      });
      return pick;
    }
    return opts[(Math.random() * opts.length) | 0]!;
  }

  function roundRect(x: number, y: number, w: number, h: number, r: number) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }
  const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

  let last = performance.now();
  let raf = 0;
  let disposed = false;

  function frame(now: number) {
    if (disposed) return;
    raf = requestAnimationFrame(frame);
    const dt = Math.min(50, now - last);
    last = now;
    if (!W || !H) {
      layout();
      return;
    }

    // advance the head continuously (no per-step pause)
    if (settleAt && now > settleAt) {
      prog += dt / EDGE_MS;
      let guard = 0;
      while (prog >= 1 && guard++ < 8) {
        prog -= 1;
        trail.push({ from: cur, to: nextI, t: 0 });
        if (trail.length > 12) trail.shift();
        prev = cur;
        cur = nextI;
        nextI = pickNext();
        nodes[cur]!.act = 1;
        nodes[cur]!.ripple = 1;
      }
    }

    // ease cursor → relaxes to centre when inactive
    const tx = mouse.active ? mouse.x : cx;
    const ty = mouse.active ? mouse.y : cy;
    me.x += (tx - me.x) * Math.min(1, dt / 140);
    me.y += (ty - me.y) * Math.min(1, dt / 140);

    // age trail
    trail.forEach((e) => {
      e.t = Math.min(1, e.t + dt / 1100);
    });

    // build edge intensity map (circuit-flow)
    const edgeLit: Record<string, number> = {};
    for (let et = 0; et < trail.length; et++) {
      const ee = trail[et]!;
      const inten = (1 - ee.t) * (0.4 + 0.6 * ((et + 1) / trail.length));
      const k = ekey(ee.from, ee.to);
      if (!edgeLit[k] || inten > edgeLit[k]) edgeLit[k] = inten;
    }
    if (nextI >= 0) {
      const lk = ekey(cur, nextI);
      if (!edgeLit[lk] || 1 > edgeLit[lk]) edgeLit[lk] = 1;
    }

    // node state + parallax
    nodes.forEach((n) => {
      n.act *= Math.pow(0.9975, dt);
      n.ripple = Math.max(0, n.ripple - dt / 900);
      let hv = 0;
      if (mouse.active) {
        const dxm = n.bx - mouse.x;
        const dym = n.by - mouse.y;
        const dd = Math.sqrt(dxm * dxm + dym * dym);
        hv = Math.max(0, 1 - dd / 92);
      }
      n.hover += (hv - n.hover) * Math.min(1, dt / 90);
      n.pulse += dt * 0.0016;
      n.x = n.bx;
      n.y = n.by;
    });

    ctx.clearRect(0, 0, W, H);

    // ── lattice threads ──
    ctx.save();
    ctx.lineCap = 'round';
    function fiber(ia: number, ib: number) {
      const a = nodes[ia]!;
      const b = nodes[ib]!;
      ctx.shadowBlur = 0;
      ctx.lineWidth = 2.4;
      ctx.strokeStyle = 'rgba(255,255,255,.03)';
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
      ctx.lineWidth = 0.8;
      ctx.shadowBlur = 3;
      ctx.shadowColor = 'rgba(255,255,255,.3)';
      ctx.strokeStyle = 'rgba(255,255,255,.12)';
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
      const lit = edgeLit[ekey(ia, ib)];
      if (lit) {
        ctx.lineWidth = 1.4;
        ctx.shadowBlur = 7;
        ctx.shadowColor = 'rgba(' + GB + ',' + lit * 0.7 + ')';
        ctx.strokeStyle = 'rgba(' + GB + ',' + lit * 0.5 + ')';
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
    }
    for (let gy = 0; gy < ROWS; gy++) {
      for (let gx = 0; gx < COLS; gx++) {
        if (gx < COLS - 1) fiber(idx(gx, gy), idx(gx + 1, gy));
        if (gy < ROWS - 1) fiber(idx(gx, gy), idx(gx, gy + 1));
      }
    }
    ctx.restore();

    // ── comet light ──
    if (trail.length || nextI >= 0) {
      const startFrom = trail.length ? trail[0]!.from : cur;
      const pts = [{ x: nodes[startFrom]!.x, y: nodes[startFrom]!.y }];
      for (let i = 0; i < trail.length; i++) {
        const to = nodes[trail[i]!.to]!;
        pts.push({ x: to.x, y: to.y });
      }
      if (nextI >= 0) {
        const la = nodes[cur]!;
        const lb = nodes[nextI]!;
        pts.push({ x: la.x + (lb.x - la.x) * prog, y: la.y + (lb.y - la.y) * prog });
      }
      const segN = pts.length - 1;
      ctx.save();
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      for (let s = 0; s < segN; s++) {
        const f = (s + 1) / segN; // 0 tail → 1 head
        const p0 = pts[s]!;
        const p1 = pts[s + 1]!;
        ctx.lineWidth = 4 + f * 7;
        ctx.shadowBlur = 14;
        ctx.shadowColor = 'rgba(' + GB + ',' + f * 0.5 + ')';
        ctx.strokeStyle = 'rgba(' + GB + ',' + f * f * 0.22 + ')';
        ctx.beginPath();
        ctx.moveTo(p0.x, p0.y);
        ctx.lineTo(p1.x, p1.y);
        ctx.stroke();
        ctx.lineWidth = 1.2 + f * 3;
        ctx.shadowBlur = 8;
        ctx.strokeStyle = 'rgba(' + GB + ',' + (0.12 + f * f * 0.8) + ')';
        ctx.beginPath();
        ctx.moveTo(p0.x, p0.y);
        ctx.lineTo(p1.x, p1.y);
        ctx.stroke();
      }
      const head = pts[pts.length - 1]!;
      const hr = ctx.createRadialGradient(head.x, head.y, 0, head.x, head.y, 9);
      hr.addColorStop(0, 'rgba(' + GB + ',.95)');
      hr.addColorStop(0.4, 'rgba(' + GB + ',.55)');
      hr.addColorStop(1, 'rgba(' + GB + ',0)');
      ctx.fillStyle = hr;
      ctx.beginPath();
      ctx.arc(head.x, head.y, 9, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = 'rgba(255,255,255,.92)';
      ctx.shadowBlur = 12;
      ctx.shadowColor = 'rgba(' + GB + ',.9)';
      ctx.beginPath();
      ctx.arc(head.x, head.y, 2.4, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

    // ── glass tiles ──
    const lightAng = now * 0.00018;
    let lx = Math.cos(lightAng) * 0.5 + (me.x - cx) / W;
    let ly = Math.sin(lightAng) * 0.5 + (me.y - cy) / H;
    const llen = Math.hypot(lx, ly) || 1;
    lx /= llen;
    ly /= llen;

    for (let n3 = 0; n3 < nodes.length; n3++) {
      const n2 = nodes[n3]!;
      const isCur = n3 === cur;
      const act = Math.max(n2.act, n2.hover * 0.9);
      const amb = 0.5 + 0.5 * Math.sin(n2.pulse);
      const sizeTile = 30 + act * 2;
      const rad = sizeTile * 0.34;
      const x0 = n2.x - sizeTile / 2;
      const y0 = n2.y - sizeTile / 2;

      ctx.save();
      ctx.shadowColor = 'rgba(0,0,0,.32)';
      ctx.shadowBlur = 10;
      ctx.shadowOffsetY = 4;
      roundRect(x0, y0, sizeTile, sizeTile, rad);
      ctx.fillStyle = 'rgba(255,255,255,0.02)';
      ctx.fill();
      ctx.restore();

      ctx.save();
      roundRect(x0, y0, sizeTile, sizeTile, rad);
      ctx.clip();
      const g = ctx.createLinearGradient(x0, y0, x0, y0 + sizeTile);
      g.addColorStop(0, 'rgba(255,255,255,' + (0.18 + act * 0.16) + ')');
      g.addColorStop(0.5, 'rgba(255,255,255,' + (0.06 + act * 0.07) + ')');
      g.addColorStop(1, 'rgba(255,255,255,' + (0.11 + act * 0.09) + ')');
      ctx.fillStyle = g;
      ctx.fillRect(x0, y0, sizeTile, sizeTile);
      const vg = ctx.createRadialGradient(n2.x, n2.y, sizeTile * 0.2, n2.x, n2.y, sizeTile * 0.75);
      vg.addColorStop(0, 'rgba(0,0,0,0)');
      vg.addColorStop(1, 'rgba(0,0,0,.14)');
      ctx.fillStyle = vg;
      ctx.fillRect(x0, y0, sizeTile, sizeTile);
      const sxp = n2.x - lx * sizeTile * 0.26;
      const syp = n2.y - ly * sizeTile * 0.26;
      const sp = ctx.createRadialGradient(sxp, syp, 0, sxp, syp, sizeTile * 0.5);
      sp.addColorStop(0, 'rgba(255,255,255,' + (0.16 + act * 0.12) + ')');
      sp.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.fillStyle = sp;
      ctx.fillRect(x0, y0, sizeTile, sizeTile);
      if (act > 0.03) {
        const glr = ctx.createRadialGradient(n2.x, n2.y, 0, n2.x, n2.y, sizeTile * 0.8);
        glr.addColorStop(0, 'rgba(' + GB + ',' + act * 0.5 + ')');
        glr.addColorStop(1, 'rgba(' + GB + ',0)');
        ctx.fillStyle = glr;
        ctx.fillRect(x0, y0, sizeTile, sizeTile);
      }
      ctx.restore();

      ctx.save();
      roundRect(x0 + 0.5, y0 + 0.5, sizeTile - 1, sizeTile - 1, rad);
      ctx.lineWidth = 1;
      if (act > 0.05) {
        ctx.strokeStyle = 'rgba(' + GB + ',' + (0.45 + act * 0.45) + ')';
        ctx.shadowColor = 'rgba(' + GB + ',' + act * 0.6 + ')';
        ctx.shadowBlur = 10;
      } else {
        ctx.strokeStyle = 'rgba(255,255,255,' + (0.22 + amb * 0.05) + ')';
      }
      ctx.stroke();
      ctx.restore();

      if (n2.ripple > 0.01) {
        const rp = 1 - n2.ripple;
        const rr = sizeTile * (0.5 + easeOut(rp) * 0.9);
        ctx.save();
        ctx.lineWidth = 1.4;
        ctx.strokeStyle = 'rgba(' + GB + ',' + n2.ripple * 0.5 + ')';
        roundRect(n2.x - rr, n2.y - rr, rr * 2, rr * 2, rr * 0.34);
        ctx.stroke();
        ctx.restore();
      }

      if (isCur) {
        ctx.save();
        ctx.beginPath();
        ctx.arc(n2.x, n2.y, 2.6, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255,255,255,.95)';
        ctx.shadowColor = 'rgba(' + GB + ',.9)';
        ctx.shadowBlur = 12;
        ctx.fill();
        ctx.restore();
      }
    }
  }

  function onMove(e: PointerEvent) {
    const r = canvas.getBoundingClientRect();
    mouse.x = e.clientX - r.left;
    mouse.y = e.clientY - r.top;
    mouse.active = true;
  }
  function onLeave() {
    mouse.active = false;
    mouse.x = mouse.y = -9999;
  }

  const ro = new ResizeObserver(layout);
  ro.observe(canvas);

  build();
  layout();
  me.x = cx;
  me.y = cy;
  host.addEventListener('pointermove', onMove);
  host.addEventListener('pointerleave', onLeave);
  raf = requestAnimationFrame(frame);

  return {
    start(delayMs?: number) {
      settleAt = performance.now() + (delayMs || 0);
    },
    destroy() {
      disposed = true;
      cancelAnimationFrame(raf);
      ro.disconnect();
      host.removeEventListener('pointermove', onMove);
      host.removeEventListener('pointerleave', onLeave);
    },
  };
}
