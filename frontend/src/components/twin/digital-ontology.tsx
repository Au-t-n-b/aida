// @ts-nocheck
/* 从 DS-1 / twin-world-export 整体移植，与项目里既有 screens/*.tsx 同等做法 — 保留 @ts-nocheck */
import React from 'react';
import { OntologyReport } from './ontology-report';
/* AIDA · 数字孪生 — 本体决策引擎 v4
   移植自 ontology-decision-brain(2).html · 适配 React UMD + compact/instant + 抽屉自适应
*/
import { useState as useStateO, useEffect as useEffectO, useRef as useRefO } from 'react';

const ONT_DECISION = 'risk';
const ONT_KEYS = ['network', 'device', 'service', 'acceptance'];

const ONT_NODES = [
  { key: 'network', title: '组网配置', en: 'Network Topology', tag: 'PLANNING', resultTag: 'VALIDATED', result: 'success', pos: { x: -1, y: -1 }, desc: '拓扑结构、链路关系、网络资源校验与路由策略计算。' },
  { key: 'device', title: '设备配置', en: 'Device Capability', tag: 'MATCHING', resultTag: ONT_DECISION === 'risk' ? 'RESOURCE GAP' : 'MATCHED', result: ONT_DECISION === 'risk' ? 'warning' : 'success', pos: { x: 1, y: -1 }, desc: '设备型号识别、端口能力分配、硬件资源容量预留。' },
  { key: 'service', title: '服务配置', en: 'Service Catalog', tag: 'ORCHESTRATE', resultTag: 'GENERATED', result: 'success', pos: { x: -1, y: 1 }, desc: '服务目录解析、能力开通、全域业务参数与 QoS 策略生成。' },
  { key: 'acceptance', title: '验收策略', en: 'Acceptance Rules', tag: 'BUILDING', resultTag: ONT_DECISION === 'risk' ? 'SCRIPT MISSING' : 'READY', result: ONT_DECISION === 'risk' ? 'warning' : 'success', pos: { x: 1, y: 1 }, desc: '验收规则提取、测试项与联调脚本生成、交付质量卡点校验。' },
];

const ONT_PROC = { network: 'PLANNING', device: 'MATCHING', service: 'ORCHESTRATE', acceptance: 'BUILDING' };
const ONT_CORE_TEXT = {
  init: { html: '<b>AI 决策大脑启动中</b><br>正在读取本体规则与项目上下文' },
  network: { html: '<b>正在解析组网配置</b><br>校验拓扑结构、链路资源与网络约束' },
  device: { html: '<b>正在匹配设备配置</b><br>分析设备型号、端口能力与硬件资源' },
  service: { html: '<b>正在生成服务配置</b><br>编排服务目录、开通能力与参数策略' },
  acceptance: { html: '<b>正在构建验收策略</b><br>生成测试项、验收规则与交付标准' },
};

const IcNet = () => (<svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><rect x="16" y="16" width="6" height="6" rx="1" /><rect x="2" y="16" width="6" height="6" rx="1" /><rect x="9" y="2" width="6" height="6" rx="1" /><path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3" /><path d="M12 12V8" /></svg>);
const IcDev = () => (<svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><rect x="2" y="4" width="20" height="16" rx="2" /><path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M6 12h.01M10 12h.01M14 12h.01M18 12h.01M6 16h.01M10 16h.01M14 16h.01M18 16h.01" /></svg>);
const IcSvc = () => (<svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><polygon points="12 2 2 7 12 12 22 7 12 2" /><polyline points="2 17 12 22 22 17" /><polyline points="2 12 12 17 22 12" /></svg>);
const IcAcc = () => (<svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><path d="M9 15l2 2 4-4" /></svg>);
const ONT_ICONS = { network: IcNet, device: IcDev, service: IcSvc, acceptance: IcAcc };

const IcCheckSm = () => (<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>);
const IcWarnSm = () => (<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>);
const IcWarnTri = ({ s = 15  }: any) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>);
const IcTask = ({ s = 16  }: any) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></svg>);
const IcDoc = ({ s = 15  }: any) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /></svg>);
const IcArrowR = ({ s = 15  }: any) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></svg>);
const IcChevR = ({ s = 10  }: any) => (<svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6" /></svg>);

function nowStr() {
  const d = new Date(), p = (n: any) => String(n).padStart(2, '0');
  return p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds());
}

function nodeLogText( k: any, warn: any) {
  if (k === 'network') return (warn ? '⚠ ' : '') + '识别组网约束并校验拓扑';
  if (k === 'device') return warn ? '设备端口资源缺口待补充' : '完成设备能力匹配';
  if (k === 'service') return '生成服务配置与 QoS 策略';
  if (k === 'acceptance') return warn ? '验收联调脚本缺失待补全' : '构建验收规则集';
  return '';
}

/* ── Canvas 粒子引擎（brain + node clouds + flows） ── */
function useOntologyEngine(containerRef, canvasRef, { compact, drawerRef, drawerWRef, simRef, layoutRef }) {
  const stateRef = useRefO<any>(null);
  useEffectO(() => {
    const container = containerRef.current, canvas = canvasRef.current;
    if (!container || !canvas) return;
    const ctx = canvas.getContext('2d')!;
    const TAU = Math.PI * 2;
    const rand = (a: any, b: any) => a + Math.random() * (b - a);
    const rgba = (c: any, a: any) => 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + a + ')';
    const ACCENT = { normal: [47, 125, 246], success: [16, 185, 129], risk: [245, 158, 11] };
    const PALETTE = {
      normal: [[47, 125, 246], [25, 184, 216], [123, 108, 240]],
      success: [[16, 185, 129], [5, 150, 105], [52, 211, 153]],
      risk: [[245, 158, 11], [239, 68, 68], [217, 119, 6]],
    };
    let W = 600, H = 500;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const DETAIL_NODE_W = 236;
    const DETAIL_NODE_H = 108;
    const DETAIL_BOTTOM_RESERVE = 96;
    const DETAIL_TOP_RESERVE = 46;
    const DETAIL_DRAWER_SPREAD = 0.72;
    const DETAIL_DRAWER_SPREAD_RESOLVED = 0.64;
    const DETAIL_DRAWER_GUTTER = 24;

    const getGraphBand = () => {
      const h = Math.max(280, H - DETAIL_TOP_RESERVE - DETAIL_BOTTOM_RESERVE);
      return {
        top: DETAIL_TOP_RESERVE,
        h,
        midY: DETAIL_TOP_RESERVE + h / 2,
      };
    };

    const getDrawerWidth = () => Math.min(520, Math.round(W * 0.52));
    const getLayout = () => layoutRef.current || {};
    const getGraphFit = () => {
      const drawerOpen = !compact && drawerRef.current;
      const { resolved } = getLayout();
      const drawerW = drawerOpen ? (drawerWRef.current || getDrawerWidth()) : 0;
      const areaW = Math.max(320, W - drawerW);
      const band = getGraphBand();
      if (compact) return { drawerOpen, drawerW, areaW, scale: 1, spread: 1 };
      if (!drawerOpen) {
        return {
          drawerOpen, drawerW, areaW: W,
          scale: resolved ? Math.max(0.88, Math.min(0.96, band.h / 560)) : 1,
          spread: resolved ? 0.90 : 1,
        };
      }
      const contentW = 480;
      const contentH = resolved ? 560 : 480;
      const scaleByWidth = (areaW - DETAIL_DRAWER_GUTTER * 2) / contentW;
      const scaleByHeight = (band.h - DETAIL_DRAWER_GUTTER * 2) / contentH;
      const spread = resolved ? DETAIL_DRAWER_SPREAD_RESOLVED : DETAIL_DRAWER_SPREAD;
      return {
        drawerOpen, drawerW, areaW,
        scale: Math.max(0.54, Math.min(resolved ? 0.74 : 0.80, scaleByWidth, scaleByHeight)),
        spread,
      };
    };

    const anim = { cx: W / 2, cy: H / 2, scale: 1, spread: 1, targetCx: W / 2, targetCy: H / 2, targetScale: 1, targetSpread: 1 };
    const offFactor = () => {
      if (!compact) {
        const fit = getGraphFit();
        const { resolved } = getLayout();
        const band = getGraphBand();
        const yExtraClosed = DETAIL_NODE_W * (0.5 - 1 / 3);
        const yExtraOpen = DETAIL_NODE_W * 0.5;
        if (!fit.drawerOpen) {
          const yBase = Math.min(band.h * (resolved ? 0.23 : 0.25), resolved ? 168 : 182);
          return {
            x: Math.min(W * (resolved ? 0.36 : 0.38), resolved ? 440 : 480),
            y: yBase + yExtraClosed,
          };
        }
        const nodeHalfW = (DETAIL_NODE_W * fit.scale) / 2;
        const centerHalfH = (resolved ? 170 : 110) * fit.scale;
        const availY = (band.h / 2 - DETAIL_DRAWER_GUTTER - centerHalfH * 0.48) / fit.spread;
        const yBase = Math.max(82, Math.min(availY, resolved ? 218 : 238));
        return {
          x: Math.max(68, (fit.areaW / 2 - nodeHalfW - DETAIL_DRAWER_GUTTER - 8) / fit.spread),
          y: yBase + yExtraOpen,
        };
      }
      const nodeW = 168, nodeH = 76, gutter = 28;
      return {
        x: Math.max(82, Math.min(176, (W - nodeW - gutter) / 2)),
        y: Math.max(96, Math.min(168, (H - nodeH - gutter) / 2)),
      };
    };
    const baseOffset = (node: any) => { const f = offFactor(); return { x: node.pos.x * f.x, y: node.pos.y * f.y }; };
    const brainOrigin = () => ({ x: anim.cx, y: anim.cy });
    const nodeOrigin = (k: any) => {
      const o = baseOffset(ONT_NODES.find((n: any) => n.key === k));
      return { x: anim.cx + o.x * anim.spread, y: anim.cy + o.y * anim.spread };
    };

    let brain: any[] = [], clouds: any = { network: [], device: [], service: [], acceptance: [] }, flows: any[] = [];
    let brainPulse = 0;
    const brainBaseR = () => Math.min(W, H) * (compact ? 0.18 : 0.275);

    function buildBrain() {
      brain = [];
      const count = compact ? (W < 400 ? 120 : 180) : (W < 700 ? 360 : 520);
      const maxR = brainBaseR();
      for (let i = 0; i < count; i++) {
        brain.push({
          idx: i,
          angle: Math.random() * TAU,
          speed: rand(0.0012, 0.0050) * (Math.random() < 0.5 ? 1 : -1),
          radius: Math.pow(Math.random(), 0.62) * maxR + rand(compact ? 6 : 6, compact ? 12 : 18),
          size: rand(0.6, compact ? 2.2 : 2.6),
          alpha: rand(0.12, compact ? 0.5 : 0.62),
          depth: Math.random(),
          colIdx: (Math.random() * 3) | 0,
          glow: !compact && Math.random() < 0.16,
          twk: Math.random() * TAU,
          x: anim.cx, y: anim.cy,
        });
      }
    }
    function buildClouds() {
      ONT_KEYS.forEach((k: any) => {
        const arr = [];
        const n = compact ? 28 : 56;
        for (let i = 0; i < n; i++) {
          const a = Math.random() * TAU, rad = Math.pow(Math.random(), 0.6) * (compact ? 52 : 84);
          const ta = Math.random() * TAU, trad = rand(compact ? 14 : 20, compact ? 26 : 38);
          arr.push({
            ox: Math.cos(a) * rad, oy: Math.sin(a) * rad,
            tx: Math.cos(ta) * trad, ty: Math.sin(ta) * trad,
            x: anim.cx, y: anim.cy, size: rand(0.7, 2.0), phase: Math.random() * TAU,
            speed: rand(0.3, 1.0), amp: rand(compact ? 4 : 6, compact ? 12 : 20), depth: Math.random(),
          });
        }
        clouds[k] = arr;
      });
    }

    function resize() {
      W = container.clientWidth || 600; H = container.clientHeight || 500;
      canvas.width = W * dpr; canvas.height = H * dpr;
      canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      anim.cy = H / 2;
      if (!compact) anim.cy = getGraphBand().midY;
      if (!compact) drawerWRef.current = getDrawerWidth();
      const fit = getGraphFit();
      anim.targetCx = fit.drawerOpen ? fit.areaW / 2 : W / 2;
      buildBrain(); buildClouds();
    }

    function spawnFlow( k: any) {
      for (let i = 0; i < 5; i++) flows.push({ key: k, t: -i * 0.18, speed: rand(0.006, 0.011), size: rand(1.2, 2.6) });
    }

    function qpoint( p0x: any, p0y: any, p1x: any, p1y: any, p2x: any, p2y: any, t: any) {
      const mt = 1 - t;
      return [mt * mt * p0x + 2 * mt * t * p1x + t * t * p2x, mt * mt * p0y + 2 * mt * t * p1y + t * t * p2y];
    }

    function drawConnections( time: any) {
      const sim = simRef.current, o0 = brainOrigin();
      const mode = sim.resultMode || 'normal';
      ONT_KEYS.forEach((k: any) => {
        const n = nodeOrigin(k), st = sim.nodeState[k] || 'particle';
        let alpha = 0.10;
        if (st === 'connecting') alpha = 0.30;
        else if (st === 'forming') alpha = 0.38;
        else if (st === 'completed') alpha = 0.46;
        const warn = st === 'completed' && sim.nodeResult[k] === 'warning';
        const col = warn ? ACCENT.risk : (st === 'completed' ? ACCENT.success : ACCENT.normal);
        const mx = (o0.x + n.x) / 2 + (o0.y - n.y) * 0.06;
        const my = (o0.y + n.y) / 2 + (n.x - o0.x) * 0.06;
        ctx.strokeStyle = rgba(col, alpha);
        ctx.lineWidth = st === 'completed' ? 1.6 : 1.1;
        ctx.beginPath(); ctx.moveTo(o0.x, o0.y); ctx.quadraticCurveTo(mx, my, n.x, n.y); ctx.stroke();
        if (st === 'connecting' || st === 'forming') {
          ctx.save(); ctx.setLineDash([3, 9]); ctx.lineDashOffset = -time * 30;
          ctx.strokeStyle = rgba([25, 184, 216], 0.35); ctx.lineWidth = 0.9;
          ctx.beginPath(); ctx.moveTo(o0.x, o0.y); ctx.quadraticCurveTo(mx, my, n.x, n.y); ctx.stroke(); ctx.restore();
        }
      });
    }

    function drawFlows() {
      const o0 = brainOrigin();
      for (let i = flows.length - 1; i >= 0; i--) {
        const f = flows[i]; f.t += f.speed;
        const st = simRef.current.nodeState[f.key];
        if (f.t > 1.05) {
          if (st === 'connecting' || st === 'forming') f.t = -0.05;
          else { flows.splice(i, 1); continue; }
        }
        if (f.t < 0) continue;
        const n = nodeOrigin(f.key);
        const mx = (o0.x + n.x) / 2 + (o0.y - n.y) * 0.06, my = (o0.y + n.y) / 2 + (n.x - o0.x) * 0.06;
        const p = qpoint(o0.x, o0.y, mx, my, n.x, n.y, f.t);
        const col = [25, 184, 216];
        const g = ctx.createRadialGradient(p[0], p[1], 0, p[0], p[1], f.size * 3);
        g.addColorStop(0, rgba(col, 0.9)); g.addColorStop(1, rgba(col, 0));
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(p[0], p[1], f.size * 3, 0, TAU); ctx.fill();
        ctx.fillStyle = 'rgba(255,255,255,0.95)'; ctx.beginPath(); ctx.arc(p[0], p[1], f.size * 0.7, 0, TAU); ctx.fill();
      }
    }

    function drawBrain( time: any) {
      const sim = simRef.current, o = brainOrigin();
      const mode = sim.resultMode || 'normal';
      const solid = sim.brainSolid || 0;
      const sp = anim.spread;
      const maxR = brainBaseR() * sp;
      const breath = Math.sin(time * 0.62) * ((compact ? 18 : 44) * (1 - solid) + (compact ? 4 : 8)) * sp;
      const corePulse = Math.sin(time * 0.6) * 0.5 + 0.5;
      const pal = PALETTE[mode] || PALETTE.normal;
      const acc = ACCENT[mode] || ACCENT.normal;
      const pulse = brainPulse;

      const haloR = maxR * (2.05 - solid * 0.40) + breath * 1.2;
      const h1 = ctx.createRadialGradient(o.x, o.y, maxR * 0.10, o.x, o.y, haloR);
      h1.addColorStop(0, rgba(acc, 0.12 + solid * 0.10));
      h1.addColorStop(0.42, rgba(acc, 0.045));
      h1.addColorStop(1, rgba(acc, 0));
      ctx.fillStyle = h1; ctx.beginPath(); ctx.arc(o.x, o.y, haloR, 0, TAU); ctx.fill();

      const h2r = maxR * (0.72 + corePulse * 0.05);
      const h2 = ctx.createRadialGradient(o.x, o.y, 0, o.x, o.y, h2r);
      h2.addColorStop(0, 'rgba(255,255,255,' + (0.34 + solid * 0.22) + ')');
      h2.addColorStop(0.5, 'rgba(244,249,255,' + (0.14 + solid * 0.10) + ')');
      h2.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.fillStyle = h2; ctx.beginPath(); ctx.arc(o.x, o.y, h2r, 0, TAU); ctx.fill();

      const coreR = maxR * (0.50 + solid * 0.18) * (0.95 + corePulse * 0.05);
      const cg = ctx.createRadialGradient(o.x, o.y, 0, o.x, o.y, coreR);
      cg.addColorStop(0, 'rgba(255,255,255,' + (0.30 + solid * 0.50 + pulse * 0.25) + ')');
      cg.addColorStop(0.38, rgba(acc, 0.14 + solid * 0.30 + pulse * 0.15));
      cg.addColorStop(1, rgba(acc, 0));
      ctx.fillStyle = cg; ctx.beginPath(); ctx.arc(o.x, o.y, coreR, 0, TAU); ctx.fill();

      for (const p of brain) {
        p.angle += p.speed;
        let r = (p.radius * sp) + breath * (0.5 + p.depth * 0.7);
        if (solid > 0.01) r = r * (1 - solid * 0.46) + (p.radius * sp * 0.34) * solid;
        const tx = o.x + Math.cos(p.angle) * r, ty = o.y + Math.sin(p.angle) * r;
        p.x += (tx - p.x) * 0.045; p.y += (ty - p.y) * 0.045;
      }

      const linkDist = (47 + solid * 12) * sp;
      const linkDistSq = linkDist * linkDist;
      const cell = Math.max(linkDist, 1);
      const grid = new Map();
      for (const p of brain) {
        const key = Math.floor(p.x / cell) + ':' + Math.floor(p.y / cell);
        let bucket = grid.get(key); if (!bucket) { bucket = []; grid.set(key, bucket); }
        bucket.push(p);
      }
      const linkBase = 0.13 + solid * 0.16 + pulse * 0.30;
      const NB = compact ? 4 : 6, segs = [];
      for (let i = 0; i < NB; i++) segs.push([]);
      const dirs = [[0, 0], [1, 0], [-1, 1], [0, 1], [1, 1]];
      grid.forEach((bucket: any, key: any) => {
        const parts = key.split(':'), gx = +parts[0], gy = +parts[1];
        for (const a of bucket) {
          for (const d of dirs) {
            const nb = grid.get((gx + d[0]) + ':' + (gy + d[1]));
            if (!nb) continue;
            for (const b of nb) {
              if (d[0] === 0 && d[1] === 0 && b.idx <= a.idx) continue;
              const dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy;
              if (d2 < linkDistSq) {
                const lvl = Math.min(NB - 1, ((1 - d2 / linkDistSq) * NB) | 0);
                segs[lvl].push(a.x, a.y, b.x, b.y);
              }
            }
          }
        }
      });
      ctx.lineWidth = 0.62;
      for (let l = 0; l < NB; l++) {
        const s = segs[l]!; if (!s.length) continue;
        ctx.strokeStyle = rgba(acc, linkBase * ((l + 0.6) / NB));
        ctx.beginPath();
        for (let i = 0; i < s.length; i += 4) { ctx.moveTo(s[i], s[i + 1]); ctx.lineTo(s[i + 2], s[i + 3]); }
        ctx.stroke();
      }

      for (const p of brain) {
        const c = pal[p.colIdx];
        const tw = 0.78 + Math.sin(time * 1.7 + p.twk) * 0.22;
        const r = p.size * (0.5 + p.depth * 1.05) * (1 + solid * 0.28);
        const a = p.alpha * (0.64 + solid * 0.36) * tw;
        if (p.glow) {
          const gr = r * 3.8;
          const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, gr);
          g.addColorStop(0, rgba(c, a * 0.55)); g.addColorStop(1, rgba(c, 0));
          ctx.fillStyle = g; ctx.beginPath(); ctx.arc(p.x, p.y, gr, 0, TAU); ctx.fill();
        }
        ctx.fillStyle = rgba(c, a); ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, TAU); ctx.fill();
        if (p.glow) { ctx.fillStyle = 'rgba(255,255,255,' + (a * 0.85) + ')'; ctx.beginPath(); ctx.arc(p.x, p.y, r * 0.45, 0, TAU); ctx.fill(); }
      }

      if (pulse > 0.01) {
        const ease = 1 - pulse;
        ctx.lineWidth = 1 + pulse * 4;
        ctx.strokeStyle = rgba(acc, pulse * 0.55);
        ctx.beginPath(); ctx.arc(o.x, o.y, maxR * (0.45 + ease * 1.55), 0, TAU); ctx.stroke();
        ctx.lineWidth = 1 + pulse * 2;
        ctx.strokeStyle = 'rgba(255,255,255,' + (pulse * 0.42) + ')';
        ctx.beginPath(); ctx.arc(o.x, o.y, maxR * (0.45 + ease * 1.05), 0, TAU); ctx.stroke();
      }
    }

    function drawCloud( k: any, time: any) {
      const sim = simRef.current, o = nodeOrigin(k), arr = clouds[k];
      const form = sim.formProgress[k] || 0, st = sim.nodeState[k] || 'particle';
      const active = st === 'connecting' || st === 'forming';
      const warn = sim.nodeResult[k] === 'warning', done = st === 'completed';
      const haloA = 0.05 + (active ? 0.10 : 0) + form * 0.05;
      const hr = (70 - form * 26) * anim.spread;
      const accCol = done ? (warn ? ACCENT.risk : ACCENT.success) : [120, 180, 255];
      const halo = ctx.createRadialGradient(o.x, o.y, 0, o.x, o.y, Math.max(hr, 1));
      halo.addColorStop(0, rgba(accCol, haloA)); halo.addColorStop(1, rgba(accCol, 0));
      ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(o.x, o.y, Math.max(hr, 1), 0, TAU); ctx.fill();
      for (const p of arr) {
        const fx = p.ox + Math.cos(time * p.speed + p.phase) * p.amp;
        const fy = p.oy + Math.sin(time * p.speed * 0.8 + p.phase) * p.amp;
        const x = o.x + (fx * (1 - form) + p.tx * form) * anim.spread;
        const y = o.y + (fy * (1 - form) + p.ty * form) * anim.spread;
        const alpha = (done ? (0.10 + p.depth * 0.2) : (0.25 + p.depth * 0.45)) * (1 - form * 0.55);
        let col;
        if (warn && (active || done)) col = ACCENT.risk;
        else if (active) col = [40, 150 + ((p.depth * 60) | 0), 215];
        else if (done) col = ACCENT.success;
        else col = [110, 135, 175];
        ctx.fillStyle = rgba(col, alpha);
        ctx.beginPath(); ctx.arc(x, y, Math.max(p.size * (0.6 + p.depth * 0.8) * anim.spread, 0.3), 0, TAU); ctx.fill();
      }
    }

    const _lastTf: Record<string, any> = {};
    let raf: any;
    function frame( now: any) {
      raf = requestAnimationFrame(frame);
      const time = now / 1000;
      const fit = getGraphFit();
      anim.targetScale = fit.scale;
      anim.targetSpread = fit.spread;
      anim.targetCx = fit.drawerOpen ? fit.areaW / 2 : W / 2;
      anim.targetCy = compact ? H / 2 : getGraphBand().midY;
      anim.cx += (anim.targetCx - anim.cx) * 0.08;
      anim.cy += (anim.targetCy - anim.cy) * 0.08;
      anim.scale += (anim.targetScale - anim.scale) * 0.08;
      anim.spread += (anim.targetSpread - anim.spread) * 0.08;
      if (brainPulse > 0.0005) brainPulse *= 0.972; else brainPulse = 0;

      const sim = simRef.current;
      const completed = ONT_KEYS.filter((k: any) => sim.nodeState[k] === 'completed').length;
      const targetSolid = sim.targetSolid != null ? sim.targetSolid : completed / 4 * 0.5;
      sim.brainSolid += (targetSolid - sim.brainSolid) * 0.04;
      ONT_KEYS.forEach((k: any) => {
        const st = sim.nodeState[k];
        const tgt = (st === 'forming' || st === 'completed') ? 1 : 0;
        sim.formProgress[k] = (sim.formProgress[k] || 0) + (tgt - (sim.formProgress[k] || 0)) * 0.06;
      });

      const setT = (el: any, key: any, x: any, y: any) => {
        if (!el) return;
        const val = 'translate(-50%,-50%) translate(' + x.toFixed(2) + 'px,' + y.toFixed(2) + 'px) scale(' + anim.scale.toFixed(3) + ')';
        if (_lastTf[key] === val) return;
        _lastTf[key] = val;
        el.style.transform = val;
      };
      const wraps = stateRef.current && stateRef.current.wraps;
      if (wraps) {
        setT(wraps.center, 'center', anim.cx, anim.cy);
        ONT_NODES.forEach((n: any) => { const o = baseOffset(n); setT(wraps[n.key], n.key, anim.cx + o.x * anim.spread, anim.cy + o.y * anim.spread); });
      }

      ctx.clearRect(0, 0, W, H);
      drawConnections(time);
      drawBrain(time);
      ONT_KEYS.forEach((k: any) => drawCloud(k, time));
      drawFlows();
    }

    resize();
    raf = requestAnimationFrame(frame);
    const ro = new ResizeObserver(resize); ro.observe(container);
    stateRef.current = { wraps: null, spawnFlow, resetFlows: () => { flows = []; }, pulseBrain: () => { brainPulse = 1; } };
    return () => { cancelAnimationFrame(raf); ro.disconnect(); };
  }, [compact]);
  return stateRef;
}

function OntResolvedPanel({ risk, compact, onOpenReport  }: any) {
  const stop = (e: any, id: any) => { e.stopPropagation(); onOpenReport(id); };
  const riskN = risk ? '2' : '0';
  const taskN = '2';
  return (
    <div className="ont-resolved-panel">
      <div className={'ont-res-badge ' + (risk ? 'risk' : 'success')}>
        {risk ? <IcWarnTri s={15} /> : <IcCheckSm />}
        {risk ? 'DELIVERY BLOCKED' : 'DELIVERABLE'}
      </div>
      <div className={'ont-res-title ' + (risk ? 'risk' : 'success')}>{risk ? '交付具较高风险' : '项目可交付'}</div>
      <p className="ont-res-sub">{risk ? '系统已拦截自动下发指令 · 检测到端口资源枯竭与验收脚本缺失' : '交付方案策略已生成 · 四个子决策点全部通过校验'}</p>
      {!compact && (
        <React.Fragment>
          <div className="ont-r-cta" onClick={(e: any) => stop(e, 'doc-overall')}><IcDoc />点击查阅最终方案<IcArrowR /></div>
          <div className="ont-r-stats">
            <div className="ont-r-stat" onClick={(e: any) => stop(e, 'doc-risks')}>
              <div className={'ont-rs-ic ' + (risk ? 'warn' : 'ok')}>{risk ? <IcWarnTri s={16} /> : <IcCheckSm />}</div>
              <div className="ont-rs-txt"><div className="ont-rs-n">{riskN}</div><div className="ont-rs-l">已识别风险<IcChevR /></div></div>
            </div>
            <div className="ont-r-stat" onClick={(e: any) => stop(e, 'doc-dispatch')}>
              <div className="ont-rs-ic task"><IcTask /></div>
              <div className="ont-rs-txt"><div className="ont-rs-n">{taskN}</div><div className="ont-rs-l">已生成任务<IcChevR /></div></div>
            </div>
          </div>
        </React.Fragment>
      )}
    </div>
  );
}

function OntNodeCard({ node, st, clickable, onClick  }: any) {
  const Icon = (ONT_ICONS as any)[node.key];
  const isWarn = st === 'completed' && node.result === 'warning';
  const cardCls = ['ont-card'];
  if (st === 'connecting' || st === 'forming') cardCls.push('active');
  if (st === 'completed') { cardCls.push('completed'); if (isWarn) cardCls.push('warn'); }
  if (clickable && st === 'completed') cardCls.push('clickable');
  let statTxt = '待决策';
  if (st === 'connecting' || st === 'forming') statTxt = '决策中 · ' + (ONT_PROC as any)[node.key];
  else if (st === 'completed') statTxt = isWarn ? '需介入' : '已生成';
  return (
    <div className={cardCls.join(' ')} onClick={clickable && st === 'completed' ? onClick : undefined}>
      <div className="ont-card-head">
        <div className="ont-card-ic"><Icon /></div>
        <div><div className="ont-card-name">{node.title}</div><div className="ont-card-en">{node.en}</div></div>
      </div>
      <div className="ont-card-desc">{node.desc}</div>
      <div className="ont-card-foot">
        <span className="ont-card-stat"><i className="ont-led" /><span>{statTxt}</span></span>
        {st === 'completed' && (
          <span className="ont-card-badge">{isWarn ? <IcWarnSm /> : <IcCheckSm />}{node.resultTag}</span>
        )}
      </div>
      <div className="ont-card-energy"><i className={st === 'connecting' || st === 'forming' ? 'scan' : st === 'completed' ? (isWarn ? 'warn' : 'ok') : ''} /></div>
    </div>
  );
}

function DigitalTwinOntology({ compact = false, instant = false  }: any) {
  const containerRef = useRefO<any>(null);
  const canvasRef = useRefO<any>(null);
  const wrapRefs = useRefO<any>({});
  const drawerRef = useRefO<any>(!compact && instant);
  const drawerWRef = useRefO<any>(0);
  const layoutRef = useRefO<any>({ resolved: instant, reportOpen: !compact && instant });
  const flowTimers = useRefO<any>([]);
  const isRisk = ONT_DECISION === 'risk';

  const initNodeState = () => {
    const s: Record<string, any> = {};
    ONT_KEYS.forEach((k: any) => { s[k] = instant ? 'completed' : 'particle'; });
    return s;
  };
  const initNodeResult = () => {
    const r: Record<string, any> = {};
    ONT_NODES.forEach((n: any) => { r[n.key] = n.result === 'warning' ? 'warning' : 'success'; });
    return r;
  };

  const simRef = useRefO<any>({
    nodeState: initNodeState(),
    nodeResult: initNodeResult(),
    formProgress: { network: 0, device: 0, service: 0, acceptance: 0 },
    brainSolid: instant ? 0.5 : 0,
    targetSolid: instant ? 0.5 : null,
    resultMode: instant ? ONT_DECISION : 'normal',
  });

  const [nodeState, setNodeState] = useStateO<any>(initNodeState);
  const syncNode = (k: any, v: any) => {
    simRef.current.nodeState[k] = v;
    setNodeState((s: any) => ({ ...s, [k]: v }));
  };
  const syncAllNodes = (obj: any) => {
    simRef.current.nodeState = obj;
    setNodeState({ ...obj });
  };

  const [centerPhase, setCenterPhase] = useStateO<any>(instant ? 'resolved' : 'reasoning');
  const [resultMode, setResultMode] = useStateO<any>(instant ? ONT_DECISION : 'normal');
  const [coreKey, setCoreKey] = useStateO<any>(instant ? 'resolved' : 'init');
  const [progress, setProgress] = useStateO<any>(instant ? 100 : 0);
  const [pillText, setPillText] = useStateO<any>(instant ? (isRisk ? '决策完成 · 交付存在风险' : '决策完成 · 项目可交付') : '决策引擎运行中');
  const [reportOpen, setReportOpen] = useStateO<any>(() => !compact && instant);
  const [activeSection, setActiveSection] = useStateO<any>('doc-overall');
  const [dispatched, setDispatched] = useStateO<any>({});
  const [logs, setLogs] = useStateO<any>(instant ? [{ t: nowStr(), text: isRisk ? '已形成项目可交付性结论（存在风险）' : '已形成项目可交付性结论', warn: isRisk }] : []);
  const [toast, setToast] = useStateO<any>(null);
  const scrollRef = useRefO<any>(null);
  const fill0Ref = useRefO<any>(null), fill1Ref = useRefO<any>(null), fill2Ref = useRefO<any>(null);

  const engine = useOntologyEngine(containerRef, canvasRef, { compact, drawerRef, drawerWRef, simRef, layoutRef });

  useEffectO(() => { if (engine.current) engine.current.wraps = wrapRefs.current; });

  useEffectO(() => {
    layoutRef.current = {
      resolved: centerPhase === 'resolved' || centerPhase === 'revealing',
      reportOpen: !compact && reportOpen,
    };
  }, [centerPhase, reportOpen, compact]);

  useEffectO(() => {
    if (!compact && instant) {
      setReportOpen(true);
      drawerRef.current = true;
      setActiveSection('doc-overall');
    } else if (compact) {
      setReportOpen(false);
      drawerRef.current = false;
    }
  }, [compact, instant]);

  const addLog = (text: any, warn: any) => setLogs((prev: any) => [...prev.slice(-5), { t: nowStr(), text, warn }]);

  useEffectO(() => {
    const clearAll = () => { flowTimers.current.forEach(clearTimeout); flowTimers.current = []; };
    const T = (fn: any, ms: any) => flowTimers.current.push(setTimeout(fn, ms));

    if (instant) {
      const done = initNodeState();
      syncAllNodes(done);
      simRef.current.nodeResult = initNodeResult();
      simRef.current.resultMode = ONT_DECISION;
      simRef.current.targetSolid = 0.5;
      simRef.current.brainSolid = 0.5;
      setResultMode(ONT_DECISION);
      setCenterPhase('resolved');
      setCoreKey('resolved');
      setProgress(100);
      setPillText(isRisk ? '决策完成 · 交付存在风险' : '决策完成 · 项目可交付');
      return clearAll;
    }

    const fresh = { network: 'particle', device: 'particle', service: 'particle', acceptance: 'particle' };
    syncAllNodes(fresh);
    simRef.current.nodeResult = initNodeResult();
    simRef.current.formProgress = { network: 0, device: 0, service: 0, acceptance: 0 };
    simRef.current.brainSolid = 0;
    simRef.current.targetSolid = null;
    simRef.current.resultMode = 'normal';
    setResultMode('normal');
    if (engine.current) engine.current.resetFlows();
    setCenterPhase('reasoning');
    setCoreKey('init');
    setProgress(0);
    setPillText('决策引擎运行中');
    setLogs([]);

    const startDelay = compact ? 400 : 2200;
    const stepDur = compact ? 850 : 2200;

    T(() => { setCoreKey('init'); addLog('已加载项目本体模型'); }, compact ? 200 : 1500);

    ONT_KEYS.forEach((k: any, i: any) => {
      const base = startDelay + i * stepDur;
      T(() => {
        syncNode(k, 'connecting');
        setCoreKey(k);
        if (engine.current) engine.current.spawnFlow(k);
        setProgress(12 + i * 21);
        if (!compact) setPillText('推理中 · ' + ONT_NODES.find((n: any) => n.key === k).title);
      }, base);
      T(() => { syncNode(k, 'forming'); }, base + (compact ? 320 : 1000));
      T(() => {
        syncNode(k, 'completed');
        const warn = simRef.current.nodeResult[k] === 'warning';
        addLog(nodeLogText(k, warn), warn);
        setProgress(22 + i * 21);
      }, base + stepDur - (compact ? 120 : 320));
    });

    const finale = startDelay + 4 * stepDur + (compact ? 80 : 200);
    T(() => {
      simRef.current.resultMode = ONT_DECISION;
      simRef.current.targetSolid = 0.5;
      setResultMode(ONT_DECISION);
      if (engine.current) engine.current.pulseBrain();
      setPillText(isRisk ? '决策完成 · 交付存在风险' : '决策完成 · 项目可交付');
      setProgress(100);
      addLog(isRisk ? '已形成项目可交付性结论（存在风险）' : '已形成项目可交付性结论', isRisk);
      setCenterPhase('fading');
      setCoreKey('resolved');
      T(() => setCenterPhase('revealing'), compact ? 380 : 520);
      T(() => setCenterPhase('resolved'), compact ? 1200 : 1680);
    }, finale);

    return clearAll;
  }, [instant, compact]);

  const openReport = (sectionId: any) => {
    if (compact || centerPhase !== 'resolved') return;
    setReportOpen(true); drawerRef.current = true;
    layoutRef.current = { ...layoutRef.current, reportOpen: true };
    setActiveSection(sectionId || 'doc-overall');
    setTimeout(() => {
      const el = scrollRef.current && scrollRef.current.querySelector('#' + (sectionId || 'doc-overall'));
      if (el && scrollRef.current) scrollRef.current.scrollTo({ top: el.offsetTop - 24, behavior: 'smooth' });
      if (el && sectionId && sectionId !== 'doc-overall') {
        el.classList.add('ont-highlight');
        setTimeout(() => el.classList.remove('ont-highlight'), 1600);
      }
    }, 420);
  };
  const closeReport = () => {
    setReportOpen(false); drawerRef.current = false;
    layoutRef.current = { ...layoutRef.current, reportOpen: false };
  };

  const exportReport = (type: any) => {
    if (!scrollRef.current) return;
    const verdictTxt = isRisk ? '交付存在风险（Blocked）' : '项目可交付（Deliverable）';
    const css = '<style>body{font-family:"Segoe UI","Microsoft YaHei",Arial,sans-serif;color:#1f2a40;line-height:1.7;margin:0;padding:36px 48px;font-size:13px;}'
      + 'h1{font-size:22px;margin:0 0 4px;color:#0f2a52;}.sub{color:#64748b;font-size:12px;margin-bottom:6px;}'
      + '.ont-doc-sec,.ont-dispatch,.ont-verdict{border:1px solid #e6edf6;border-radius:10px;padding:16px 20px;margin-bottom:16px;page-break-inside:avoid;}'
      + '.ont-btn-dispatch,.ont-card-energy{display:none!important;}.ont-diagram svg{width:100%;height:auto;}</style>';
    const body = scrollRef.current.innerHTML.replace(/<button[^>]*>[\s\S]*?<\/button>/gi, '');
    const html = '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>本体决策系统 · 总体交付方案与分析报告</title>' + css + '</head><body>'
      + '<h1>本体决策系统 · 总体交付方案与分析报告</h1><div class="sub">Ontology Decision System · 总体结论：' + verdictTxt + '</div>' + body + '</body></html>';
    if (type === 'word') {
      const blob = new Blob(['\ufeff', html], { type: 'application/msword;charset=utf-8' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = '交付方案报告_ONT-DLV-20260530.doc';
      document.body.appendChild(a); a.click();
      setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
      showToast('已导出 Word 文档');
    } else {
      const w = window.open('', '_blank');
      if (!w) { showToast('请允许弹出窗口以导出 PDF'); return; }
      w.document.open(); w.document.write(html); w.document.close();
      setTimeout(() => { try { w.focus(); w.print(); } catch (e) {} }, 600);
      showToast('已打开 PDF 打印预览（请选择“另存为 PDF”）');
    }
  };

  const dispatch = (i: any) => { setDispatched((d: any) => ({ ...d, [i]: 'sending' })); setTimeout(() => setDispatched((d: any) => ({ ...d, [i]: 'done' })), 1400); };
  const showToast = (text: any) => { setToast(text); setTimeout(() => setToast(null), 2600); };

  const clickable = instant || centerPhase === 'resolved';
  const isResolved = centerPhase === 'resolved';
  const isRevealing = centerPhase === 'revealing';
  const isFading = centerPhase === 'fading';
  const showReasoning = centerPhase === 'reasoning' || isFading;
  const showResolved = isResolved || isRevealing;
  const setWrap = (k: any) => (el: any) => { wrapRefs.current[k] = el; };
  const riskResolved = isRisk;
  const centerCls = 'ont-center-wrap'
    + (isResolved ? ' is-resolved' : '')
    + (isRevealing ? ' revealing' : '')
    + (isFading ? ' fading' : '')
    + ((isResolved || isRevealing || isFading) ? ' res-' + ONT_DECISION : '')
    + (clickable ? ' clickable' : '')
    + (instant ? ' instant' : '');

  return (
    <div ref={containerRef} className={'ont-wrap' + (compact ? ' ont-compact' : ' ont-detail') + (reportOpen ? ' ont-report-open' : '') + (resultMode === 'risk' ? ' ont-risk' : '')}>
      <canvas ref={canvasRef} className="ont-canvas" />

      {!compact && (
        <div className="ont-topbar">
          <div className="ont-brand">
            <div className="ont-brand-dot" aria-hidden="true" />
            <div className="ont-brand-txt"><b>本体决策系统</b><span>Ontology Decision Brain</span></div>
          </div>
          <div className="ont-status-pill"><i aria-hidden="true" /><span>{pillText}</span></div>
        </div>
      )}

      <div className="ont-layer">
        <div ref={setWrap('center')} className="ont-node-wrapper">
          <div className={centerCls} onClick={clickable ? () => openReport('doc-overall') : undefined}>
            <div className="ont-halo" aria-hidden="true" />
            <div className="ont-core-card">
              {showReasoning && (
                <div className="ont-reasoning">
                  <div className="ont-brainmark">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>
                  </div>
                  <div className="ont-core-badge">● CENTRAL DECISION</div>
                  <div className="ont-core-title">可交付性决策中</div>
                  <div className="ont-core-sub">Ontology Decision Brain is reasoning</div>
                  <div className="ont-core-state" dangerouslySetInnerHTML={{ __html: ((ONT_CORE_TEXT as any)[coreKey] || ONT_CORE_TEXT.init).html }} />
                  <div className="ont-progress"><i style={{ width: progress + '%' }} /></div>
                </div>
              )}
              {showResolved && (
                <OntResolvedPanel risk={riskResolved} compact={compact} onOpenReport={openReport} />
              )}
            </div>
          </div>
        </div>

        {ONT_NODES.map((n: any) => (
          <div ref={setWrap(n.key)} key={n.key} className="ont-node-wrapper">
            <OntNodeCard node={n} st={nodeState[n.key]} clickable={clickable} onClick={() => openReport('doc-' + n.key)} />
          </div>
        ))}
      </div>

      {!compact && (
        <React.Fragment>
          <div className={'ont-logs' + (reportOpen ? ' hidden' : '')}>
            <h4><span className="ont-lv" />决策日志流 · Decision Log</h4>
            <ul className="ont-log-list">
              {logs.map((l: any, i: any) => (
                <li key={i} className={'show' + (l.warn ? ' warn' : '')}>
                  <span className="ont-tick">{l.warn ? <IcWarnSm /> : <IcCheckSm />}</span>
                  <span><span className="ont-lt">{l.t}</span> {l.text}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className={'ont-legend' + (reportOpen ? ' hidden' : '')}>
            <div className="ont-leg-row"><span className="ont-sw s1" />粒子呼吸态 · 思考中</div>
            <div className="ont-leg-row"><span className="ont-sw s2" />推理连接态 · 数据流</div>
            <div className="ont-leg-row"><span className="ont-sw s3" />具化完成态 · 方案生成</div>
          </div>
        </React.Fragment>
      )}

      {!compact && (
        <div className="ont-drawer" ref={(el: any) => { if (el) drawerWRef.current = Math.min(520, Math.round((containerRef.current ? containerRef.current.clientWidth : 760) * 0.52)); }} style={{ width: 'min(520px, 52%)' }}>
          <div className="ont-drawer-head">
            <div className="ont-drawer-title-row">
              <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#2f7df6" strokeWidth="2.4"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /></svg>
              <span className="ont-drawer-title-text">总体交付方案与分析报告</span>
              <span className={'ont-vtag ' + ONT_DECISION}>{isRisk ? 'BLOCKED' : 'DELIVERABLE'}</span>
            </div>
            <div className="ont-rep-tools">
              <button type="button" className="ont-btn-exp" onClick={() => exportReport('word')}><IcDoc s={14} />导出 Word</button>
              <button type="button" className="ont-btn-exp pdf" onClick={() => exportReport('pdf')}><IcDoc s={14} />导出 PDF</button>
              <button type="button" className="ont-back" onClick={closeReport}>← 返回</button>
            </div>
          </div>
          <div className="ont-drawer-body ont-rep-scope" ref={scrollRef}>
            {OntologyReport
              ? <OntologyReport decision={ONT_DECISION} activeSection={activeSection} dispatched={dispatched} onDispatch={dispatch} onToast={showToast} />
              : <div style={{ padding: 20, color: '#64748b' }}>报告模块加载中…</div>}
          </div>
        </div>
      )}

      {toast && (
        <div className="ont-toast show">
          <IcCheckSm /><span>{toast}</span>
        </div>
      )}
    </div>
  );
}

(function injectOntologyStyles() {
  const id = 'ont-styles';
  let s = document.getElementById(id);
  if (!s) { s = document.createElement('style'); s.id = id; document.head.appendChild(s); }
  s.textContent = `
    .ont-wrap{position:relative;width:100%;height:100%;overflow:hidden;border-radius:inherit;background:radial-gradient(1300px 850px at 28% 16%,#fff 0%,transparent 55%),radial-gradient(1200px 950px at 82% 90%,#eef4ff 0%,transparent 60%),linear-gradient(135deg,#f4f8fd 0%,#e9f0fa 45%,#e2ebf6 100%);font-family:var(--font-sans)}
    .ont-wrap::before{content:'';position:absolute;inset:0;background-image:linear-gradient(rgba(70,120,200,.05) 1px,transparent 1px),linear-gradient(90deg,rgba(70,120,200,.05) 1px,transparent 1px);background-size:46px 46px;mask-image:radial-gradient(closest-side at 50% 50%,#000 35%,transparent 92%);-webkit-mask-image:radial-gradient(closest-side at 50% 50%,#000 35%,transparent 92%);pointer-events:none;transition:opacity .6s;z-index:1}
    .ont-report-open.ont-wrap::before{opacity:.4}
    .ont-canvas{position:absolute;inset:0;z-index:0;pointer-events:none}
    .ont-topbar{position:absolute;top:0;left:0;right:0;display:flex;align-items:center;justify-content:space-between;padding:14px 20px;z-index:30;pointer-events:none}
    .ont-brand{display:flex;align-items:center;gap:10px}
    .ont-brand-dot{width:26px;height:26px;border-radius:8px;background:linear-gradient(135deg,oklch(0.621 0.193 256),oklch(0.715 0.118 215));box-shadow:0 6px 18px -4px rgba(47,125,246,.6);position:relative}
    .ont-brand-dot::after{content:'';position:absolute;inset:6px;border-radius:4px;background:rgba(255,255,255,.85)}
    .ont-brand-txt b{font-size:14px;letter-spacing:.5px;color:oklch(0.255 0.045 260)}
    .ont-brand-txt span{display:block;font-size:10px;color:oklch(0.660 0.036 264);letter-spacing:2px;text-transform:uppercase}
    .ont-status-pill{display:flex;align-items:center;gap:8px;background:rgba(255,255,255,.62);border:1px solid rgba(120,160,220,.35);padding:7px 14px;border-radius:999px;font-size:12px;color:oklch(0.448 0.040 262);backdrop-filter:blur(8px);box-shadow:0 18px 50px -20px rgba(38,86,160,.45)}
    .ont-status-pill i{width:8px;height:8px;border-radius:50%;background:oklch(0.715 0.118 215);box-shadow:0 0 0 0 rgba(25,184,216,.5);animation:ontPulse 1.8s infinite}
    .ont-layer{position:absolute;inset:0;z-index:10;pointer-events:none}
    .ont-node-wrapper{position:absolute;top:0;left:0;display:flex;align-items:center;justify-content:center;will-change:transform;pointer-events:auto}

    .ont-center-wrap{position:relative;width:480px;min-height:200px;display:grid;place-items:center}
    .ont-compact .ont-center-wrap{width:200px;min-height:150px}
    .ont-report-open .ont-center-wrap{width:210px;min-height:120px}
    .ont-halo{position:absolute;top:50%;left:50%;width:480px;height:480px;transform:translate(-50%,-50%);border-radius:50%;background:radial-gradient(circle,rgba(255,255,255,.95) 0%,rgba(255,255,255,.74) 19%,rgba(246,250,255,.4) 37%,rgba(232,242,255,.12) 55%,rgba(255,255,255,0) 70%);animation:ontBreathe 6.5s ease-in-out infinite;pointer-events:none;transition:background .8s,width .6s,height .6s}
    .ont-compact .ont-halo{width:200px;height:200px}
    .ont-prog-ring{position:absolute;top:50%;left:50%;width:248px;height:248px;transform:translate(-50%,-50%);pointer-events:none;z-index:2;overflow:visible}
    .opr-track{fill:none;stroke:rgba(120,160,220,.16);stroke-width:4;stroke-linecap:round;stroke-dasharray:144 9999}
    .opr-fill{fill:none;stroke-width:4;stroke-linecap:round;stroke-dasharray:0 9999}
    .opr-people{stroke:oklch(0.621 0.193 256)}
    .opr-goods{stroke:oklch(0.715 0.118 215)}
    .opr-station{stroke:oklch(0.620 0.190 285)}
    .ont-prog-total{position:absolute;left:50%;top:50%;transform:translate(-50%,118px);z-index:3;pointer-events:none;font-size:10px;font-weight:700;color:oklch(0.448 0.040 262);background:rgba(255,255,255,.72);border:1px solid rgba(120,160,220,.3);padding:2px 9px;border-radius:999px;white-space:nowrap;backdrop-filter:blur(4px)}
    .ont-prog-total b{color:oklch(0.585 0.196 268);font-weight:800;margin-left:2px}
    .ont-report-open .ont-halo{width:220px;height:220px}
    .ont-center-wrap.res-success .ont-halo{background:radial-gradient(circle,rgba(255,255,255,.92) 0%,rgba(232,251,243,.6) 28%,rgba(209,245,231,.2) 50%,rgba(255,255,255,0) 70%)}
    .ont-center-wrap.res-risk .ont-halo{background:radial-gradient(circle,rgba(255,255,255,.92) 0%,rgba(255,247,232,.62) 28%,rgba(254,238,205,.22) 50%,rgba(255,255,255,0) 70%)}
    @keyframes ontBreathe{0%,100%{transform:translate(-50%,-50%) scale(1);opacity:.92}50%{transform:translate(-50%,-50%) scale(1.07);opacity:1}}
    .ont-core-card{position:relative;z-index:1;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:12px 24px;text-align:center;transition:background 1s ease,border-color 1s ease,box-shadow 1s ease,transform 1s ease}
    .ont-center-wrap.revealing .ont-core-card,.ont-center-wrap.is-resolved .ont-core-card{background:linear-gradient(160deg,#fff,#eef5ff);backdrop-filter:blur(18px);border-radius:26px;border:1px solid rgba(120,210,175,.5);box-shadow:0 30px 70px -22px rgba(16,160,110,.25);padding:20px 24px}
    .ont-center-wrap.revealing .ont-core-card{animation:ontCoreReveal 1.15s cubic-bezier(.22,1,.36,1) both}
    .ont-center-wrap.instant.is-resolved .ont-core-card{animation:none}
    .ont-center-wrap.res-risk.revealing .ont-core-card,.ont-center-wrap.res-risk.is-resolved .ont-core-card{border-color:rgba(245,190,110,.55);box-shadow:0 30px 70px -22px rgba(200,130,20,.4)}
    .ont-center-wrap.clickable.is-resolved .ont-core-card{cursor:pointer}
    .ont-center-wrap.clickable.is-resolved .ont-core-card:hover{transform:scale(1.02)}
    .ont-reasoning{display:flex;flex-direction:column;align-items:center;transition:opacity .55s ease,transform .55s ease,filter .55s ease}
    .ont-center-wrap.fading .ont-reasoning{opacity:0;transform:scale(.94);filter:blur(4px)}
    .ont-center-wrap.is-resolved .ont-reasoning,.ont-center-wrap.revealing .ont-reasoning{display:none}
    .ont-brainmark{color:oklch(0.621 0.193 256);margin-bottom:10px;filter:drop-shadow(0 0 14px rgba(255,255,255,.95));animation:ontSpin 16s linear infinite}
    .ont-brainmark svg{width:36px;height:36px}
    .ont-compact .ont-brainmark svg{width:28px;height:28px}
    @keyframes ontSpin{to{transform:rotate(360deg)}}
    .ont-core-badge{font-size:10px;letter-spacing:2.5px;text-transform:uppercase;font-weight:700;color:oklch(0.621 0.193 256);background:rgba(255,255,255,.55);padding:5px 12px;border-radius:999px;margin-bottom:10px}
    .ont-core-title{font-size:20px;font-weight:800;letter-spacing:1px;color:oklch(0.255 0.045 260);margin-bottom:4px;text-shadow:0 0 18px #fff}
    .ont-compact .ont-core-title{font-size:15px}
    .ont-core-sub{font-size:9px;color:oklch(0.621 0.193 256);font-weight:600;letter-spacing:2px;text-transform:uppercase;margin-bottom:10px;opacity:.85}
    .ont-compact .ont-core-sub{display:none}
    .ont-core-state{font-size:12px;color:oklch(0.355 0.040 262);font-weight:500;min-height:38px;line-height:1.5;max-width:260px;padding:8px 12px;border-radius:14px;background:rgba(255,255,255,.55);border:1px solid rgba(255,255,255,.85);backdrop-filter:blur(6px);transition:opacity .4s}
    .ont-compact .ont-core-state{font-size:11px;min-height:32px;padding:8px 10px;max-width:170px}
    .ont-core-state b{color:oklch(0.621 0.193 256);font-weight:700}
    .ont-progress{margin-top:14px;height:5px;width:200px;border-radius:99px;background:rgba(47,125,246,.14);overflow:hidden}
    .ont-compact .ont-progress{width:140px;margin-top:10px}
    .ont-progress i{display:block;height:100%;background:linear-gradient(90deg,oklch(0.621 0.193 256),oklch(0.715 0.118 215));border-radius:99px;transition:width .8s;box-shadow:0 0 12px rgba(25,184,216,.6)}
    .ont-resolved-panel{display:none;flex-direction:column;align-items:center;width:100%;opacity:0;transform:scale(.94) translateY(12px);filter:blur(8px)}
    .ont-center-wrap.revealing .ont-resolved-panel,.ont-center-wrap.is-resolved .ont-resolved-panel{display:flex}
    .ont-center-wrap.revealing .ont-resolved-panel{animation:ontResolvedReveal 1.05s cubic-bezier(.22,1,.36,1) forwards}
    .ont-center-wrap.is-resolved .ont-resolved-panel{opacity:1;transform:none;filter:none}
    .ont-center-wrap.revealing .ont-res-badge{animation:ontItemIn .5s .14s both}
    .ont-center-wrap.revealing .ont-res-title{animation:ontItemIn .5s .28s both}
    .ont-center-wrap.revealing .ont-res-sub{animation:ontItemIn .5s .42s both}
    .ont-center-wrap.revealing .ont-r-cta{animation:ontItemIn .5s .56s both}
    .ont-center-wrap.revealing .ont-r-stats{animation:ontItemIn .5s .68s both}
    @keyframes ontCoreReveal{0%{background:rgba(255,255,255,0);border-color:transparent;box-shadow:none;transform:scale(.97)}100%{transform:scale(1)}}
    @keyframes ontResolvedReveal{0%{opacity:0;transform:scale(.93) translateY(16px);filter:blur(10px)}55%{opacity:.82;filter:blur(2px)}100%{opacity:1;transform:scale(1) translateY(0);filter:blur(0)}}
    @keyframes ontItemIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
    .ont-res-badge{display:inline-flex;align-items:center;gap:7px;font-family:var(--font-mono);font-size:11px;font-weight:800;letter-spacing:1.5px;padding:5px 14px;border-radius:999px;margin-bottom:10px;background:rgba(255,255,255,.85)}
    .ont-res-badge.risk{color:oklch(0.548 0.130 56);border:1px solid rgba(245,158,11,.4)}
    .ont-res-badge.success{color:oklch(0.620 0.130 163);border:1px solid rgba(16,185,129,.35)}
    .ont-res-title{font-size:28px;font-weight:800;letter-spacing:1px;margin-bottom:6px;line-height:1.15}
    .ont-res-title.risk{color:oklch(0.395 0.080 53)}.ont-res-title.success{color:oklch(0.375 0.070 163)}
    .ont-compact .ont-res-title{font-size:16px;white-space:nowrap}
    .ont-report-open .ont-res-title{font-size:17px;margin-bottom:4px}
    .ont-compact .ont-res-badge{font-size:9px;padding:4px 9px;margin-bottom:8px}
    .ont-res-sub{font-size:12px;color:oklch(0.448 0.040 262);font-weight:500;line-height:1.55;max-width:300px;margin:0 0 12px}
    .ont-report-open .ont-res-sub{font-size:10.5px;line-height:1.45;margin-bottom:8px;max-width:190px}
    .ont-compact .ont-res-sub{display:none}
    .ont-report-open .ont-r-cta{font-size:11px;padding:7px 12px;margin-bottom:10px}
    .ont-report-open .ont-r-stats{gap:6px}
    .ont-report-open .ont-r-stat{min-width:92px;padding:7px 10px}
    .ont-report-open .ont-rs-n{font-size:15px}
    .ont-report-open .ont-rs-ic{width:26px;height:26px}
    .ont-r-cta{display:inline-flex;align-items:center;gap:8px;cursor:pointer;font-size:12px;font-weight:800;padding:8px 16px;border-radius:999px;margin-bottom:10px;transition:all .25s;border:1px solid transparent}
    .ont-center-wrap.res-risk .ont-r-cta{color:oklch(0.548 0.130 56);background:rgba(245,158,11,.12);border-color:rgba(245,158,11,.28)}
    .ont-center-wrap.res-risk .ont-r-cta:hover{background:rgba(245,158,11,.2);transform:translateY(-2px);box-shadow:0 10px 24px -10px rgba(245,158,11,.6)}
    .ont-center-wrap.res-success .ont-r-cta{color:oklch(0.620 0.130 163);background:rgba(16,185,129,.12);border-color:rgba(16,185,129,.3)}
    .ont-center-wrap.res-success .ont-r-cta:hover{background:rgba(16,185,129,.2);transform:translateY(-2px);box-shadow:0 10px 24px -10px rgba(16,160,110,.6)}
    .ont-r-stats{display:flex;gap:8px;flex-wrap:wrap;justify-content:center}
    .ont-r-stat{display:flex;align-items:center;gap:8px;cursor:pointer;padding:7px 12px;border-radius:12px;background:rgba(255,255,255,.7);border:1px solid rgba(40,80,150,.12);transition:all .25s;min-width:104px}
    .ont-r-stat:hover{transform:translateY(-2px);box-shadow:0 12px 26px -12px rgba(40,90,170,.5);border-color:rgba(40,80,150,.28)}
    .ont-rs-ic{width:28px;height:28px;border-radius:8px;display:grid;place-items:center;flex:none}
    .ont-rs-ic.warn{background:rgba(245,158,11,.14);color:oklch(0.548 0.130 56)}
    .ont-rs-ic.task{background:rgba(47,125,246,.12);color:oklch(0.621 0.193 256)}
    .ont-rs-ic.ok{background:rgba(16,185,129,.14);color:oklch(0.620 0.130 163)}
    .ont-rs-txt{text-align:left;line-height:1.1}
    .ont-rs-n{font-size:16px;font-weight:800;color:oklch(0.255 0.045 260)}
    .ont-rs-l{font-size:10px;color:oklch(0.448 0.040 262);font-weight:600;margin-top:2px;display:flex;align-items:center;gap:4px}
    .ont-rs-l svg{opacity:.6}

    .ont-card{position:relative;width:236px;padding:12px 14px;border-radius:15px;background:rgba(255,255,255,.3);border:1px solid rgba(120,160,220,.18);backdrop-filter:blur(2px);box-shadow:0 10px 30px -18px rgba(40,90,170,.4);opacity:.26;filter:saturate(.6);transform:scale(.96);transition:opacity .7s,transform .7s,background .7s,border-color .7s,filter .7s,box-shadow .7s}
    .ont-compact .ont-card{width:168px;padding:10px 12px;border-radius:12px}
    .ont-report-open .ont-card{width:218px;padding:11px 13px}
    .ont-card.active{opacity:.95;background:rgba(255,255,255,.55);border-color:rgba(47,125,246,.45);filter:saturate(.85);transform:scale(.98)}
    .ont-card.completed{opacity:1;filter:saturate(1);transform:scale(1);background:linear-gradient(160deg,rgba(255,255,255,.84),rgba(236,244,255,.6));border-color:rgba(120,160,220,.35);backdrop-filter:blur(13px);box-shadow:0 10px 30px -18px rgba(40,90,170,.4)}
    .ont-card.warn.completed{border-color:rgba(245,158,11,.5)}
    .ont-card.clickable{cursor:pointer}
    .ont-card.clickable:hover{border-color:rgba(47,125,246,.6);box-shadow:0 20px 50px -12px rgba(47,125,246,.3)}
    .ont-card.warn.clickable:hover{border-color:rgba(245,158,11,.7);box-shadow:0 20px 50px -12px rgba(245,158,11,.3)}
    .ont-card::before{content:'';position:absolute;top:0;left:14px;right:14px;height:2px;border-radius:2px;background:linear-gradient(90deg,transparent,oklch(0.715 0.118 215),transparent);opacity:0;transition:opacity .6s}
    .ont-card.completed::before{opacity:.6}
    .ont-card.warn.completed::before{background:linear-gradient(90deg,transparent,oklch(0.760 0.158 70),transparent)}
    .ont-card-head{display:flex;align-items:center;gap:9px;margin-bottom:6px}
    .ont-card-ic{width:34px;height:34px;border-radius:9px;display:grid;place-items:center;background:linear-gradient(135deg,rgba(47,125,246,.14),rgba(25,184,216,.14));border:1px solid rgba(47,125,246,.22);color:oklch(0.621 0.193 256);transition:all .6s;flex:none}
    .ont-card-ic svg{width:17px;height:17px}
    .ont-compact .ont-card-ic{width:28px;height:28px;border-radius:8px}
    .ont-compact .ont-card-ic svg{width:15px;height:15px}
    .ont-card.completed .ont-card-ic{background:linear-gradient(135deg,oklch(0.621 0.193 256),oklch(0.715 0.118 215));color:#fff;box-shadow:0 8px 18px -6px rgba(47,125,246,.6)}
    .ont-card.warn.completed .ont-card-ic{background:linear-gradient(135deg,oklch(0.760 0.158 70),#ea580c);box-shadow:0 8px 18px -6px rgba(245,158,11,.6)}
    .ont-card-name{font-size:13px;font-weight:700;letter-spacing:.3px;color:oklch(0.255 0.045 260)}
    .ont-compact .ont-card-name{font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:110px}
    .ont-card-en{font-size:8.5px;color:oklch(0.660 0.036 264);letter-spacing:1.5px;text-transform:uppercase}
    .ont-compact .ont-card-en{display:none}
    .ont-card-desc{font-size:10.5px;color:oklch(0.448 0.040 262);line-height:1.45;min-height:28px}
    .ont-compact .ont-card-desc{display:none}
    .ont-card-foot{display:flex;align-items:center;justify-content:space-between;margin-top:6px;gap:6px}
    .ont-card-stat{font-size:9px;color:oklch(0.660 0.036 264);display:flex;align-items:center;gap:5px;white-space:nowrap}
    .ont-led{width:7px;height:7px;border-radius:50%;background:oklch(0.660 0.036 264);transition:all .5s;flex:none}
    .ont-card.active .ont-led{background:oklch(0.715 0.118 215);animation:ontPulse 1.6s infinite}
    .ont-card.completed .ont-led{background:oklch(0.710 0.148 162)}
    .ont-card.warn.completed .ont-led{background:oklch(0.760 0.158 70)}
    @keyframes ontPulse{0%{box-shadow:0 0 0 0 rgba(25,184,216,.45)}70%{box-shadow:0 0 0 8px rgba(25,184,216,0)}100%{box-shadow:0 0 0 0 rgba(25,184,216,0)}}
    .ont-card-badge{font-size:9.5px;font-weight:700;font-family:var(--font-mono);color:oklch(0.620 0.130 163);background:rgba(16,185,129,.12);border:1px solid rgba(16,185,129,.25);padding:3px 8px;border-radius:999px;display:flex;align-items:center;gap:4px;opacity:0;transform:translateY(4px);transition:opacity .5s,transform .5s;white-space:nowrap}
    .ont-card.completed .ont-card-badge{opacity:1;transform:translateY(0)}
    .ont-card.warn.completed .ont-card-badge{color:oklch(0.548 0.130 56);background:rgba(245,158,11,.12);border-color:rgba(245,158,11,.3)}
    .ont-compact .ont-card-badge{font-size:8px;padding:2px 6px}
    .ont-card-energy{position:absolute;left:0;right:0;bottom:0;height:3px;background:rgba(0,0,0,.05);border-radius:0 0 18px 18px;overflow:hidden}
    .ont-card-energy i{display:block;height:100%;width:0;background:oklch(0.715 0.118 215);transition:width .5s}
    .ont-card.active .ont-card-energy i{width:100%;background:linear-gradient(90deg,transparent,oklch(0.715 0.118 215),transparent);animation:ontEscan 1.6s linear infinite}
    .ont-card.completed .ont-card-energy i{width:100%;background:oklch(0.710 0.148 162);animation:none}
    .ont-card.warn.completed .ont-card-energy i{width:100%;background:oklch(0.760 0.158 70);animation:none}
    @keyframes ontEscan{0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}

    .ont-logs,.ont-legend{position:absolute;z-index:25;background:rgba(255,255,255,.62);border:1px solid rgba(120,160,220,.35);backdrop-filter:blur(10px);box-shadow:0 18px 50px -20px rgba(38,86,160,.45);transition:opacity .5s,transform .5s;pointer-events:none}
    .ont-logs.hidden,.ont-legend.hidden{opacity:0;transform:translateY(10px);pointer-events:none}
    .ont-legend{left:12px;bottom:12px;top:auto;padding:7px 10px;border-radius:11px;font-size:9.5px;color:oklch(0.448 0.040 262);display:flex;flex-direction:column;gap:4px;max-width:156px}
    .ont-logs{right:12px;bottom:12px;top:auto;width:min(220px,32%);padding:9px 11px;border-radius:12px}
    .ont-logs h4{font-size:9px;letter-spacing:1.8px;text-transform:uppercase;color:oklch(0.660 0.036 264);font-weight:600;display:flex;align-items:center;gap:6px;margin:0 0 6px}
    .ont-lv{width:5px;height:12px;border-radius:3px;background:linear-gradient(oklch(0.621 0.193 256),oklch(0.715 0.118 215))}
    .ont-log-list{list-style:none;margin:0;padding:0;max-height:88px;overflow:hidden}
    .ont-log-list li{display:flex;align-items:flex-start;gap:7px;font-size:10px;color:oklch(0.448 0.040 262);padding:3px 0;line-height:1.35;opacity:0;transform:translateX(8px);transition:opacity .5s,transform .5s}
    .ont-log-list li.show{opacity:1;transform:translateX(0)}
    .ont-tick{flex:none;margin-top:2px;width:14px;height:14px;border-radius:50%;background:rgba(15,157,107,.15);display:grid;place-items:center;color:oklch(0.620 0.130 163)}
    .ont-log-list li.warn .ont-tick{background:rgba(245,158,11,.18);color:oklch(0.548 0.130 56)}
    .ont-lt{font-family:var(--font-mono);color:oklch(0.660 0.036 264);font-size:10px;margin-right:2px}
    .ont-leg-row{display:flex;align-items:center;gap:6px}
    .ont-sw{width:18px;height:7px;border-radius:99px}
    .ont-sw.s1{background:rgba(122,140,170,.5)}.ont-sw.s2{background:oklch(0.715 0.118 215)}.ont-sw.s3{background:linear-gradient(90deg,oklch(0.621 0.193 256),oklch(0.715 0.118 215))}

    .ont-drawer{position:absolute;top:0;right:0;height:100%;z-index:100;display:flex;flex-direction:column;background:rgba(255,255,255,.74);backdrop-filter:blur(42px);border-left:1px solid rgba(255,255,255,.9);box-shadow:-24px 0 70px rgba(30,70,140,.14);transform:translateX(105%);transition:transform .7s cubic-bezier(.22,.9,.3,1.15)}
    .ont-report-open .ont-drawer{transform:translateX(0)}
    .ont-drawer-head{display:flex;flex-direction:column;align-items:stretch;padding:14px 18px 12px;border-bottom:1px solid rgba(40,80,150,.08);background:rgba(255,255,255,.7);gap:10px}
    .ont-drawer-title-row{display:flex;align-items:center;gap:8px;width:100%;min-width:0;white-space:nowrap}
    .ont-drawer-title-text{font-size:15px;font-weight:800;color:oklch(0.255 0.045 260);flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis}
    .ont-rep-tools{display:flex;align-items:center;justify-content:flex-end;gap:8px;flex-wrap:wrap;width:100%}
    .ont-btn-exp{cursor:pointer;display:flex;align-items:center;gap:6px;font-size:12px;font-weight:700;color:#1d4ed8;padding:7px 12px;border-radius:8px;background:rgba(47,125,246,.08);border:1px solid rgba(47,125,246,.22);transition:all .2s}
    .ont-btn-exp:hover{background:rgba(47,125,246,.16);transform:translateY(-1px)}
    .ont-btn-exp.pdf{color:#b42318;background:rgba(239,68,68,.07);border-color:rgba(239,68,68,.22)}
    .ont-btn-exp.pdf:hover{background:rgba(239,68,68,.14)}
    .ont-vtag{font-family:var(--font-mono);font-size:10px;font-weight:700;padding:3px 8px;border-radius:6px;letter-spacing:.5px;flex:none}
    .ont-vtag.risk{background:rgba(245,158,11,.12);color:oklch(0.548 0.130 56);border:1px solid rgba(245,158,11,.3)}
    .ont-vtag.success{background:rgba(16,185,129,.12);color:oklch(0.620 0.130 163);border:1px solid rgba(16,185,129,.3)}
    .ont-back{cursor:pointer;font-size:12px;font-weight:700;color:#475569;background:#eef2f8;border:1px solid #dde5f0;border-radius:8px;padding:7px 12px;transition:all .2s;flex:none;white-space:nowrap}
    .ont-back:hover{background:#e2e9f3;transform:translateX(-2px)}
    .ont-drawer-body{flex:1;height:0;overflow-y:auto;padding:20px 22px 28px;scroll-behavior:smooth}
    .ont-drawer-body::-webkit-scrollbar{width:7px}.ont-drawer-body::-webkit-scrollbar-thumb{background:#c4d2e6;border-radius:4px}
    .ont-highlight{animation:ontHl 1.6s ease;border-color:oklch(0.621 0.193 256)!important;box-shadow:0 0 0 3px rgba(47,125,246,.16)!important}
    @keyframes ontHl{0%,45%{background:#eff6ff;transform:scale(1.008)}100%{background:#fff;transform:scale(1)}}

    .ont-toast{position:absolute;left:50%;bottom:28px;transform:translate(-50%,0);z-index:200;background:oklch(0.255 0.045 260);color:#fff;font-size:14px;font-weight:600;padding:12px 20px;border-radius:12px;box-shadow:0 16px 40px rgba(0,0,0,.25);display:flex;align-items:center;gap:8px;opacity:0;pointer-events:none;transition:all .4s cubic-bezier(.22,.9,.3,1.15)}
    .ont-toast.show{opacity:1}
    .ont-toast svg{color:#5eead4;flex:none}
  `;
  document.head.appendChild(s);
})();

export { DigitalTwinOntology };
