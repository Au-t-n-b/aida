// @ts-nocheck
/* 从 DS-1 / twin-world-export 整体移植，与项目里既有 screens/*.tsx 同等做法 — 保留 @ts-nocheck */
import React from 'react';
import { OntologyReport } from './ontology-report';
import { adoptDerivedRisk, generateRemediationTask, ensureContingencyAnchor,
  generateContingencyNarratives, editChapterNarrative, acceptChapterMerge,
  restoreChapterNarrativeVersion,
  listContingencyChapters, setContingencyChapters, resetContingencyChapters } from '@/lib/ontology-api';
import {
  getMissingNarrativeChapterIds,
  makeNarrativeAutogenKey,
  markNarrativeAutogenAttempt,
  shouldRunNarrativeAutogen,
} from '@/lib/narrative-autogen';
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
  hold: { html: '<b>正在等待本体引擎判定</b><br>四域配置已具化，正在汇总派生风险与可交付结论' },
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

/** pending（真实生成）模式的完成日志：取真实节点 title + resultTag（如「设备配置 · 2 项风险」），不用 demo 味文案 */
function liveLogText(node: { title?: string; resultTag?: string } | null | undefined, warn: boolean) {
  if (!node || !node.title) return warn ? '⚠ 该域存在派生风险' : '该域配置校验通过';
  const tag = node.resultTag ? ' · ' + node.resultTag : '';
  return (warn ? '⚠ ' : '') + node.title + tag;
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
    /* compact（概览半屏）随容器放大：以 620×460 为基准等比放大，上限 1.6 倍 */
    const compactZoom = () => Math.max(1, Math.min(1.6, Math.min(W / 620, H / 460)));
    const getLayout = () => layoutRef.current || {};
    const getGraphFit = () => {
      const drawerOpen = !compact && drawerRef.current;
      const { resolved } = getLayout();
      const drawerW = drawerOpen ? (drawerWRef.current || getDrawerWidth()) : 0;
      const areaW = Math.max(320, W - drawerW);
      const band = getGraphBand();
      if (compact) return { drawerOpen, drawerW, areaW, scale: compactZoom(), spread: 1 };
      if (!drawerOpen) {
        return {
          drawerOpen, drawerW, areaW: W,
          scale: resolved ? Math.max(0.88, Math.min(1.3, band.h / 560)) : 1,
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
        scale: Math.max(0.54, Math.min(resolved ? 1.0 : 1.1, scaleByWidth, scaleByHeight)),
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
            x: Math.min(W * (resolved ? 0.42 : 0.44), resolved ? 640 : 700),
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
      const z = compactZoom();
      const nodeW = 168 * z, nodeH = 76 * z, gutter = 28;
      return {
        x: Math.max(82, Math.min(176 * z, (W - nodeW - gutter) / 2)),
        y: Math.max(96, Math.min(168 * z, (H - nodeH - gutter) / 2)),
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

function OntResolvedPanel({ risk, riskCount = 0, core = null, compact, onOpenReport  }: any) {
  const stop = (e: any, id: any) => { e.stopPropagation(); onOpenReport(id); };
  const riskN = String(riskCount);
  const taskN = String(riskCount);
  // 核心决策点（DP-CORE「方案可交付性」）驱动中心标题/结论/可交付指数；缺 core 时回退原写死文案。
  const title = (core && core.decisionName) ? core.decisionName : (risk ? '预案存在风险' : '预案无阻断风险');
  const conclusion = (core && core.conclusion) ? core.conclusion : (risk ? '存在风险' : '可交付');
  const hasIdx = !!core && typeof core.deliverabilityIndex === 'number';
  return (
    <div className="ont-resolved-panel">
      <div className={'ont-res-badge ' + (risk ? 'risk' : 'success')}>
        {risk ? <IcWarnTri s={15} /> : <IcCheckSm />}
        {risk ? 'RISK DETECTED' : 'NO RISK'}
      </div>
      <div className={'ont-res-title ' + (risk ? 'risk' : 'success')}>{title}</div>
      <p className="ont-res-sub">{core
        ? ('决策结论：' + conclusion + (hasIdx ? ' · 可交付指数 ' + core.deliverabilityIndex + '/100' : '') + (risk ? ' · ' + riskCount + ' 项预案风险' : ''))
        : (risk ? ('本体已生成 · 识别到 ' + riskCount + ' 项预案风险，详见报告') : '本体已生成 · 未识别到阻断性风险')}</p>
      {!compact && (
        <React.Fragment>
          <div className="ont-r-cta" onClick={(e: any) => stop(e, 'doc-overall')}><IcDoc />点击查阅预案报告<IcArrowR /></div>
          <div className="ont-r-stats">
            <div className="ont-r-stat" onClick={(e: any) => stop(e, 'doc-overall')}>
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

/* ── 章节拖拽组装器（本体要素托盘 ↔ 章节大纲）的展示常量 ── */
const DP_LABEL: any = { device: '设备决策', network: '组网决策', service: '服务决策', acceptance: '验收决策', global: '全局输入' };
const DP_GROUPS: any[] = [
  { key: 'device', label: '设备配置可交付性' },
  { key: 'network', label: '组网配置可交付性' },
  { key: 'service', label: '服务配置可交付性' },
  { key: 'acceptance', label: '验收可交付性' },
  { key: 'global', label: '全局输入' },
];
const AUTO_NARRATIVE_CHAPTER_IDS = new Set(['doc-ch-1']);
// 元数据章与风险&假设汇总章已从后端章节目录删除；此屏蔽仅兜底旧后端 / 历史 overlay 里残留的 include id
//（与 contingency-view 的 HIDDEN_REPORT_CHAPTER_IDS 同契约），正常路径下不命中。
const COMPOSER_HIDDEN_IDS: string[] = ['doc-ch-meta', 'doc-risks'];
const _tray: any = { margin: '0 0 8px', border: '1px dashed #cfe0f6', borderRadius: 10, background: 'rgba(47,125,246,0.05)', padding: 8 };
const _trayHd: any = { display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 12, fontWeight: 700, color: '#2f7df6', userSelect: 'none' };
const _trayGroupTtl: any = { fontSize: 10.5, fontWeight: 700, color: '#94a3b8', margin: '8px 0 3px', letterSpacing: '.04em' };
const _chip: any = { display: 'flex', flexDirection: 'column', gap: 1, padding: '5px 8px', margin: '4px 0', background: '#fff', border: '1px solid #d9e4f3', borderRadius: 8, cursor: 'grab', fontSize: 12 };
const _chipMeta: any = { fontSize: 10, color: '#94a3b8' };
const _traySearch: any = { width: '100%', boxSizing: 'border-box', margin: '2px 0 4px', padding: '5px 8px', border: '1px solid #d9e4f3', borderRadius: 8, fontSize: 11.5, color: '#23344d', background: '#fff', outline: 'none' };
const _emptyBadge: any = { fontSize: 9.5, color: '#b45309', background: 'rgba(180,83,9,0.08)', border: '1px solid rgba(180,83,9,0.25)', borderRadius: 6, padding: '0 4px', marginLeft: 5, fontWeight: 600 };
// 大纲插入位置指示线（拖拽悬停目标项顶部 2.5px accent；inset shadow 不挤布局）
const _insertLine = 'inset 0 2.5px 0 0 #2f7df6';
const _grip: any = { cursor: 'grab', color: '#b6c2d6', fontSize: 13, marginRight: 2, flex: '0 0 auto' };
const _xbtn: any = { border: 'none', background: 'transparent', color: '#c2410c', cursor: 'pointer', fontSize: 13, fontWeight: 700, lineHeight: 1, padding: '0 2px', flex: '0 0 auto' };
const _lock: any = { color: '#b6c2d6', fontSize: 11, padding: '0 3px', flex: '0 0 auto' };
const _actionBar: any = { display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap', margin: '8px 0 2px' };
const _applyBtn: any = { flex: 1, padding: '7px 10px', borderRadius: 8, border: '1px solid #16a34a', background: '#16a34a', color: '#fff', fontSize: 12, fontWeight: 700, cursor: 'pointer' };
const _applyBtnOff: any = { flex: 1, padding: '7px 10px', borderRadius: 8, border: '1px solid #d4ddec', background: '#f1f5fb', color: '#94a3b8', fontSize: 12, fontWeight: 600, cursor: 'default' };
const _miniBtn: any = { padding: '7px 10px', borderRadius: 8, border: '1px solid #d4ddec', background: '#fff', color: '#3a4a63', fontSize: 12, fontWeight: 600, cursor: 'pointer' };
// 章节融合：多选工具条 / 合并按钮 / 复选框 / 组徽章 / 展开箭头 / 成员子行 / 改名输入 / 拖叠目标高亮
const _selBar: any = { display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', margin: '6px 0 2px', padding: '6px 10px', borderRadius: 8, border: '1px solid #c9bdf6', background: 'rgba(122,90,240,0.1)', fontSize: 12, color: '#5b3fb8', fontWeight: 600 };
const _mergeBtn: any = { padding: '5px 12px', borderRadius: 7, border: '1px solid #7a5af0', background: '#7a5af0', color: '#fff', fontSize: 12, fontWeight: 700, cursor: 'pointer' };
const _selChk: any = { width: 14, height: 14, flex: '0 0 auto', cursor: 'pointer', accentColor: '#7a5af0', margin: 0 };
const _grpBadge: any = { fontSize: 9.5, fontWeight: 700, color: '#7a5af0', background: 'rgba(122,90,240,0.12)', border: '1px solid rgba(122,90,240,0.3)', borderRadius: 6, padding: '0 5px', marginLeft: 5, whiteSpace: 'nowrap' };
// 组标题尚未被 AI 融合命名（titleBy 仍为 auto/空）时的占位提示 —— 别把拼接占位名误读成最终名。
const _pendingChip: any = { fontSize: 9, fontWeight: 600, color: '#b45309', background: 'rgba(180,83,9,0.08)', border: '1px solid rgba(180,83,9,0.25)', borderRadius: 6, padding: '0 5px', marginLeft: 4, whiteSpace: 'nowrap' };
const _grpCaret: any = { cursor: 'pointer', color: '#7a5af0', fontSize: 10, flex: '0 0 auto', width: 12, textAlign: 'center', userSelect: 'none' };
const _memberRow: any = { display: 'flex', alignItems: 'center', gap: 6, padding: '3px 8px 3px 32px', fontSize: 11.5, color: '#5a6b85', background: 'rgba(122,90,240,0.05)', borderLeft: '2px solid rgba(122,90,240,0.4)' };
const _memberType: any = { fontSize: 10, color: '#94a3b8', flex: '0 0 auto' };
const _splitBtn: any = { border: 'none', background: 'transparent', color: '#7a5af0', cursor: 'pointer', fontSize: 11, fontWeight: 600, padding: '0 4px', flex: '0 0 auto' };
const _renameInput: any = { flex: 1, minWidth: 0, fontSize: 12.5, padding: '2px 6px', border: '1px solid #7a5af0', borderRadius: 6, outline: 'none', color: '#23344d' };
const _mergeRowShadow = 'inset 0 0 0 2px #7a5af0'; // 拖叠合并：目标行整行高亮

/** pending：真实生成进行中（data 尚未到达）——播放生成动画，但判定性步骤（各域 completed 的
 *  warn 判定、finale verdict）门控在 data 到达之后；仅 view=digital 真实生成分支传入。 */
function DigitalTwinOntology({ compact = false, instant = false, pending = false, data = null, onReload = null }: any) {
  const containerRef = useRefO<any>(null);
  const canvasRef = useRefO<any>(null);
  const wrapRefs = useRefO<any>({});
  const drawerRef = useRefO<any>(!compact && instant);
  const drawerWRef = useRefO<any>(0);
  const layoutRef = useRefO<any>({ resolved: instant, reportOpen: !compact && instant });
  const flowTimers = useRefO<any>([]);
  const effPending = pending && !instant && !compact;
  // data 存在时由后端真实预案视图驱动；否则回退内置写死常量（兼容旧 demo / 加载前）。
  const effNodes = (data && data.nodes && data.nodes.length) ? data.nodes : ONT_NODES;
  const effDecision = data ? data.decision : ONT_DECISION;
  const effRisks = data ? data.risks : null;
  const effSummary = data ? data.summary : null;
  const effChapters = data ? data.chapters : null;
  const effCore = data ? (data.coreDecision ?? null) : null;
  const isRisk = effDecision === 'risk';
  const riskCountTxt = effSummary ? effSummary.riskCount : (isRisk ? 2 : 0);
  const verdictPill = isRisk ? ('预案本体已生成 · ' + riskCountTxt + ' 项风险') : '预案本体已生成 · 无风险';
  const verdictLog = isRisk ? ('已生成预案本体 · ' + riskCountTxt + ' 项风险') : '已生成预案本体 · 未识别风险';

  // 渲染期同步鲜值：生成脚本的 timer / 门控回调一律读此 ref，不靠 effect 闭包捕获——
  // pending 模式下 data 是后到的，闭包里的 demo 假判定绝不能落到真实生成结果上。
  const liveRef = useRefO<any>(null);
  liveRef.current = { data, effNodes, effDecision, verdictPill, verdictLog, isRisk };
  /** 判定门控（仅 effPending 激活）：queue=数据未到时错过判定的 [key,i]；finaleDue=脚本已到终局时点；
   *  finaleFired=终局已触发（去重）；resume=data 到达后由 gate effect 调用，级联补完 queue。 */
  const gateRef = useRefO<any>({ queue: [], finaleDue: false, finaleFired: false, resume: null });

  const initNodeState = () => {
    const s: Record<string, any> = {};
    ONT_KEYS.forEach((k: any) => { s[k] = instant ? 'completed' : 'particle'; });
    return s;
  };
  const initNodeResult = () => {
    const r: Record<string, any> = {};
    effNodes.forEach((n: any) => { r[n.key] = n.result === 'warning' ? 'warning' : 'success'; });
    return r;
  };

  const simRef = useRefO<any>({
    nodeState: initNodeState(),
    nodeResult: initNodeResult(),
    formProgress: { network: 0, device: 0, service: 0, acceptance: 0 },
    brainSolid: instant ? 0.5 : 0,
    targetSolid: instant ? 0.5 : null,
    resultMode: instant ? effDecision : 'normal',
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
  const [resultMode, setResultMode] = useStateO<any>(instant ? effDecision : 'normal');
  const [coreKey, setCoreKey] = useStateO<any>(instant ? 'resolved' : 'init');
  const [progress, setProgress] = useStateO<any>(instant ? 100 : 0);
  const [pillText, setPillText] = useStateO<any>(instant ? verdictPill : '预案本体生成中');
  const [reportOpen, setReportOpen] = useStateO<any>(() => false);
  const [activeSection, setActiveSection] = useStateO<any>('doc-overall');
  const [dispatched, setDispatched] = useStateO<any>({});
  // 章节正文（ChapterNarrative）本地 override + 忙碌态：写操作返回的最新 narrative 直接合并渲染。
  const [narrOverrides, setNarrOverrides] = useStateO<any>({});
  const [narrBusy, setNarrBusy] = useStateO<any>({});
  // 章节拖拽组装（ContingencyOutline）：本体要素全集 + 当前有序纳入集（拖拽大纲）+ 忙碌/托盘态。
  // outlineIds=null 表示未加载（离线/预制）→ 回退渲染静态目录；非 null 即启用拖拽组装。
  const [elements, setElements] = useStateO<any>([]);
  const [candidates, setCandidates] = useStateO<any>([]);     // 本体类型库：未入章的业务 ObjectType（doc-ot-* 候选）
  const [outlineIds, setOutlineIds] = useStateO<any>(null);   // 本地草稿（编辑中、未应用）
  const [committedIds, setCommittedIds] = useStateO<any>(null); // 已应用集（与报告一致）
  // 章节融合（groups）：本地草稿 groups + 已应用 committedGroups；多选合并 selectedIds；展开看成员 expandedGroups。
  const [groups, setGroups] = useStateO<any>({});
  const [committedGroups, setCommittedGroups] = useStateO<any>({});
  const [selectedIds, setSelectedIds] = useStateO<any>([]);
  const [expandedGroups, setExpandedGroups] = useStateO<any>([]);
  const [renamingGid, setRenamingGid] = useStateO<any>(null);  // 正在改名的组 id
  const [renameDraft, setRenameDraft] = useStateO<any>('');
  const [composerBusy, setComposerBusy] = useStateO<any>(false);
  const [trayOpen, setTrayOpen] = useStateO<any>(false);
  const [traySearch, setTraySearch] = useStateO<any>('');
  const [dragOverIdx, setDragOverIdx] = useStateO<any>(null); // 大纲插入位置指示线（拖拽悬停的目标 idx）
  const [mergeTargetId, setMergeTargetId] = useStateO<any>(null); // 拖叠合并：高亮的目标行 id
  const dragRef = useRefO<any>(null);
  const dropRef = useRefO<any>(null); // 当前 drop 决策 { mode:'insert'|'merge', idx, targetId }（避免 drop 闭包读到陈旧 state）
  const autoNarrKeysRef = useRefO<any>({});
  const [logs, setLogs] = useStateO<any>(instant ? [{ t: nowStr(), text: verdictLog, warn: isRisk }] : []);
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

  // 真实生成先只展示决策大脑全景；预案章节默认隐藏，决策生成后点「查阅预案报告」再揭开章节目录（参考预制演示流程）。
  useEffectO(() => {
    setReportOpen(false);
    drawerRef.current = false;
    setActiveSection('doc-overall');
  }, [compact, instant]);

  const addLog = (text: any, warn: any) => setLogs((prev: any) => [...prev.slice(-5), { t: nowStr(), text, warn }]);

  useEffectO(() => {
    const clearAll = () => { flowTimers.current.forEach(clearTimeout); flowTimers.current = []; };
    const T = (fn: any, ms: any) => flowTimers.current.push(setTimeout(fn, ms));
    // 每次脚本启动重置门控（StrictMode 双跑 / 重挂时干净起步）
    gateRef.current = { queue: [], finaleDue: false, finaleFired: false, resume: null };

    if (instant) {
      const done = initNodeState();
      syncAllNodes(done);
      simRef.current.nodeResult = initNodeResult();
      simRef.current.resultMode = effDecision;
      simRef.current.targetSolid = 0.5;
      simRef.current.brainSolid = 0.5;
      setResultMode(effDecision);
      setCenterPhase('resolved');
      setCoreKey('resolved');
      setProgress(100);
      setPillText(verdictPill);
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

    // ── 判定门控 helpers ──
    // pending（真实生成）模式：判定性步骤读 liveRef 鲜值；数据未到则节点停在 forming 入 queue，
    // 由 resume 级联补完。demo / 概览 compact 路径沿用 effect 启动时种入的 demo 判定，时序逐毫秒不变。
    const hasData = () => !!liveRef.current.data;
    const findNode = (k: any) => (liveRef.current.effNodes || []).find((n: any) => n.key === k);
    const realNodeResult = (k: any) => {
      if (!hasData()) return null;
      const n = findNode(k);
      return n ? (n.result === 'warning' ? 'warning' : 'success') : 'success'; // 真实数据缺该域 → 视为无风险，防卡死
    };
    const allCompleted = () => ONT_KEYS.every((k: any) => simRef.current.nodeState[k] === 'completed');

    const runFinale = () => {
      const g = gateRef.current;
      if (g.finaleFired) return; // 双源触发去重（脚本时点 vs 级联尾）
      g.finaleFired = true;
      const live = liveRef.current;
      simRef.current.resultMode = live.effDecision;
      simRef.current.targetSolid = 0.5;
      setResultMode(live.effDecision);
      if (engine.current) engine.current.pulseBrain();
      setPillText(live.verdictPill);
      setProgress(100);
      addLog(live.verdictLog, live.isRisk);
      setCenterPhase('fading');
      setCoreKey('resolved');
      T(() => setCenterPhase('revealing'), compact ? 380 : 520);
      T(() => setCenterPhase('resolved'), compact ? 1200 : 1680);
    };

    const completeNode = (k: any, i: any) => {
      // pending 此处必有真实数据；demo 路径 realNodeResult 为 null 时沿用种入的 demo 判定
      const res = effPending ? realNodeResult(k) : (realNodeResult(k) ?? simRef.current.nodeResult[k]);
      if (res) simRef.current.nodeResult[k] = res;
      syncNode(k, 'completed');
      const warn = simRef.current.nodeResult[k] === 'warning';
      addLog(effPending ? liveLogText(findNode(k), warn) : nodeLogText(k, warn), warn);
      setProgress((p: any) => Math.max(p, 22 + i * 21)); // 单调：与 hold 蠕升 / 级联交错不回跳
      if (gateRef.current.finaleDue && allCompleted()) T(runFinale, 420);
    };

    const enterHold = () => { // 脚本走完但数据未到：停在"等待判定"，进度有限蠕升
      setCoreKey('hold');
      setPillText('生成中 · 等待本体引擎判定');
      addLog('四域配置生成完毕 · 等待本体引擎汇总判定');
      for (let j = 1; j <= 11; j++) {
        T(() => { if (!gateRef.current.finaleFired) setProgress((p: any) => Math.max(p, 85 + j)); }, 900 * j);
      }
    };

    // data 到达时由 gate effect 调用：把错过判定的域 260ms 级联补完（finale 由最后完成者经 completeNode 触发）
    gateRef.current.resume = () => {
      const g = gateRef.current;
      if (g.finaleFired) return; // 已揭晓（SWR reload 的新 view 由渲染层 eff* 直接反映）
      const q = g.queue.splice(0);
      q.forEach((args: any, j: any) => T(() => completeNode(args[0], args[1]), 260 * (j + 1)));
    };

    const startDelay = compact ? 400 : effPending ? 600 : 2200;
    const stepDur = compact ? 850 : effPending ? 1000 : 2200;

    T(() => { setCoreKey('init'); addLog('已加载项目本体模型'); }, compact ? 200 : effPending ? 250 : 1500);

    ONT_KEYS.forEach((k: any, i: any) => {
      const base = startDelay + i * stepDur;
      T(() => {
        syncNode(k, 'connecting');
        setCoreKey(k);
        if (engine.current) engine.current.spawnFlow(k);
        setProgress((p: any) => Math.max(p, 12 + i * 21));
        if (!compact) setPillText('生成中 · ' + ((findNode(k) || {}).title || ''));
      }, base);
      T(() => { syncNode(k, 'forming'); }, base + (compact ? 320 : effPending ? 450 : 1000));
      T(() => {
        if (!effPending || hasData()) completeNode(k, i);
        else gateRef.current.queue.push([k, i]); // 判定门控：数据未到，停在 forming 等 resume
      }, base + stepDur - (compact ? 120 : effPending ? 220 : 320));
    });

    const finale = startDelay + 4 * stepDur + (compact ? 80 : 200);
    T(() => {
      gateRef.current.finaleDue = true;
      if (allCompleted()) runFinale();
      else if (!hasData()) enterHold();
      // else：数据刚到、级联还在飞——finale 由最后一个 completeNode 触发
    }, finale);

    return clearAll;
  }, [instant, compact, pending]);

  // 真实生成（pending）模式：data 到达 → 叫醒脚本，把门控住的判定级联落地
  useEffectO(() => {
    if (effPending && data && gateRef.current.resume) gateRef.current.resume();
  }, [data]);

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
    const verdictTxt = isRisk ? ('存在 ' + riskCountTxt + ' 项预案风险') : '未识别到阻断性风险';
    const css = '<style>body{font-family:"Segoe UI","Microsoft YaHei",Arial,sans-serif;color:#1f2a40;line-height:1.7;margin:0;padding:36px 48px;font-size:13px;}'
      + 'h1{font-size:22px;margin:0 0 4px;color:#0f2a52;}.sub{color:#64748b;font-size:12px;margin-bottom:6px;}'
      + '.ont-doc-sec,.ont-dispatch,.ont-verdict{border:1px solid #e6edf6;border-radius:10px;padding:16px 20px;margin-bottom:16px;page-break-inside:avoid;}'
      + '.ont-btn-dispatch,.ont-card-energy,.ont-sec-tools{display:none!important;}.ont-diagram svg{width:100%;height:auto;}</style>';
    const body = scrollRef.current.innerHTML.replace(/<button[^>]*>[\s\S]*?<\/button>/gi, '');
    const html = '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>预案本体生成报告</title>' + css + '</head><body>'
      + '<h1>预案本体生成报告</h1><div class="sub">Contingency Ontology · 总体结论：' + verdictTxt + '</div>' + body + '</body></html>';
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

  const showToast = (text: any) => { setToast(text); setTimeout(() => setToast(null), 2600); };
  // 「下发处理 / 一键派发」→ 调后端真实 Action：risk 卡 → AdoptDerivedRisk，task 卡 → GenerateRemediationTask。
  // 写回 run-record overlay，可在 RiskItem/RemediationTask 查到。预制演示卡（无 risk 对象）保留本地动画。
  const dispatch = (key: any, risk?: any, kind?: any) => {
    setDispatched((d: any) => ({ ...d, [key]: 'sending' }));
    if (!risk) { // 预制演示：无真实风险对象可下发
      setTimeout(() => setDispatched((d: any) => ({ ...d, [key]: 'done' })), 1400);
      return;
    }
    // 先确保锚点预案实例 + 可交付评估真实存在（幂等），再把风险采纳/派发进去 ——
    // 这样写回的 RiskItem.planId / assessmentId 指向真实对象，而非悬空字符串。
    const anchorCtx = effCore
      ? { decisionId: effCore.decisionId, decisionName: effCore.decisionName, conclusion: effCore.conclusion, deliverabilityIndex: effCore.deliverabilityIndex }
      : {};
    const run = ensureContingencyAnchor(anchorCtx).then(() =>
      kind === 'task' ? generateRemediationTask(risk) : adoptDerivedRisk(risk),
    );
    run
      .then(() => {
        setDispatched((d: any) => ({ ...d, [key]: 'done' }));
        showToast(
          kind === 'task' ? '处置任务工单已下发 · GenerateRemediationTask' : '风险已采纳下发 · AdoptDerivedRisk',
        );
      })
      .catch((e: any) => {
        setDispatched((d: any) => { const next = { ...d }; delete next[key]; return next; }); // 复位以便重试
        showToast('操作失败：' + (e && e.message ? e.message : '本体服务未响应'));
      });
  };

  // ── 章节正文：生成 / 编辑 / 智能融合 / 版本里程碑 ──
  // 写操作返回的最新 narrative 直接合并到对应章节（本地 override），免整页重新派生（更快、不丢其它态）。
  const applyNarrativeView = (v: any) => {
    if (!v || !v.chapterId) return;
    setNarrOverrides((m: any) => ({ ...m, [v.chapterId]: v }));
    // 融合组：把生成/采纳得到的融合标题回灌组装器本地草稿，让左侧目录树也显示 AI 融合名
    // （报告侧已经 narrOverrides.title 通行）。人工改名（titleBy='human'）永不被覆盖。
    if (v.chapterTitle && String(v.chapterId).startsWith('doc-grp-')) {
      const sync = (g: any) => (g && g[v.chapterId] && g[v.chapterId].titleBy !== 'human')
        ? { ...g, [v.chapterId]: { ...g[v.chapterId], title: v.chapterTitle, titleBy: 'ai' } }
        : g;
      setGroups(sync);
      setCommittedGroups(sync);
    }
  };
  const narrFields = (v: any) => ({
    narrative: v.displayText || undefined,
    // 融合组章：生成的融合标题随响应回来（chapterTitle），即时更新报告章名，无需整页重载。
    // 普通章 chapterTitle 与自身同名、无副作用；仅 doc-ch-1 + 组章会有 narrative override。
    title: v.chapterTitle || undefined,
    narrativeStatus: v.status,
    narrativeModel: v.generatedModel || undefined,
    narrativeEditedAt: v.editedAt || undefined,
    narrativeGenerated: v.generatedText || undefined,
    narrativeEdited: v.editedText || undefined,
    pendingGenerated: v.pendingGenerated || undefined,
    mergeCandidate: v.mergeCandidate || undefined,
    versions: v.versions || undefined,
  });
  const effChaptersMerged = Array.isArray(effChapters)
    ? effChapters.map((c: any) => (narrOverrides[c.id] ? { ...c, ...narrFields(narrOverrides[c.id]) } : c))
    : effChapters;

  const onNarrative = (action: any, chapterId: any, payload: any = {}) => {
    const busyKey = chapterId || '*';
    setNarrBusy((b: any) => ({ ...b, [busyKey]: action }));
    const done = () => setNarrBusy((b: any) => { const n = { ...b }; delete n[busyKey]; return n; });
    let p: Promise<any>;
    if (action === 'generate' || action === 'regenerate' || action === 'smartmerge' || action === 'generateAll') {
      const mode = action === 'regenerate' ? 'regenerate' : action === 'smartmerge' ? 'smart_merge' : 'only_empty';
      const scope = action === 'generateAll' ? 'all' : 'chapter';
      p = generateContingencyNarratives({ scope, chapterId: scope === 'chapter' ? chapterId : undefined, mode }).then((r: any) => {
        (r.narratives || []).forEach(applyNarrativeView);
        if (r.degraded) showToast('LLM 未配置，已跳过生成（请配置 agent/.env 模型 key）');
        else showToast(action === 'generateAll' ? ('已生成 ' + (r.narratives || []).length + ' 章正文') : action === 'smartmerge' ? '已生成融合候选稿，请在对比中采纳' : '已生成本章正文');
      });
    } else if (action === 'edit') {
      p = editChapterNarrative(chapterId, payload.text || '').then((v: any) => { applyNarrativeView(v); showToast('本章修改已保存'); });
    } else if (action === 'accept') {
      p = acceptChapterMerge(chapterId, payload.choice).then((v: any) => { applyNarrativeView(v); showToast('已采纳 · ' + (payload.choice === 'mine' ? '保留我的' : payload.choice === 'new' ? '新稿' : '融合稿')); });
    } else if (action === 'restore') {
      p = restoreChapterNarrativeVersion(chapterId, { seq: payload.seq, versionLabel: payload.versionLabel }).then((v: any) => { applyNarrativeView(v); showToast('已回滚到历史版本'); });
    } else { done(); return; }
    p.catch((e: any) => showToast('操作失败：' + (e && e.message ? e.message : '本体服务未响应'))).finally(done);
  };

  useEffectO(() => {
    if (!reportOpen || !Array.isArray(effChaptersMerged) || narrBusy.__auto) return;
    const missingIds = getMissingNarrativeChapterIds(effChaptersMerged, AUTO_NARRATIVE_CHAPTER_IDS);
    if (!missingIds.length) return;
    const key = makeNarrativeAutogenKey({
      projectKey: data && data.projectKey,
      planId: data && data.planId,
      chapterIds: missingIds,
    });
    if (autoNarrKeysRef.current[key]) return;
    const store = typeof window !== 'undefined' ? window.localStorage : null;
    if (!shouldRunNarrativeAutogen(store, key)) return;
    autoNarrKeysRef.current[key] = true;
    markNarrativeAutogenAttempt(store, key);
    setNarrBusy((b: any) => ({ ...b, __auto: 'generate' }));
    generateContingencyNarratives({ scope: 'all', mode: 'only_empty' })
      .then((r: any) => {
        (r.narratives || []).forEach(applyNarrativeView);
        if (r.degraded) showToast('LLM 未配置，已跳过默认正文生成（请配置 agent/.env 模型 key）');
      })
      .catch((e: any) => showToast('默认正文生成失败：' + (e && e.message ? e.message : '本体服务未响应')))
      .finally(() => setNarrBusy((b: any) => { const n = { ...b }; delete n.__auto; return n; }));
  }, [reportOpen, effChaptersMerged, narrBusy.__auto, data]);

  // ── 章节拖拽组装（暂存式）：本体要素托盘 ↔ 章节大纲（拖入加章 / 拖动排序 / ✕ 删章）──
  // 编辑只改本地草稿 outlineIds（不落库、不动报告）；点「应用更改」才确定性写回 ContingencyOutline
  // .include+order（保留拖动顺序）+ onReload() 重新派生报告。committedIds=已应用集；「恢复默认」清 overlay。
  const elById: any = {};
  (elements || []).forEach((e: any) => { if (e && e.id) elById[e.id] = e; });
  // 本体类型库候选并入查找表：拖入后（仅本地草稿、尚未应用）大纲行立刻可渲染
  (candidates || []).forEach((e: any) => { if (e && e.id && !elById[e.id]) elById[e.id] = e; });
  const structuralSet = new Set((elements || []).filter((e: any) => e && e.structural).map((e: any) => e.id));
  const titleOf = (id: any) => (elById[id] && elById[id].title) || id;
  // 融合组伪元素：把每个组 id 合成成一个可在大纲渲染的「element」（isGroup + 成员标题）。
  // memberSet：已被某组吸纳的成员 id —— 这些章不再独立出现在大纲，也不应在托盘里当「可加」。
  const memberSet = new Set<any>();
  Object.keys(groups || {}).forEach((gid: any) => {
    const g = groups[gid] || {};
    const members = g.members || [];
    members.forEach((m: any) => memberSet.add(m));
    elById[gid] = {
      id: gid,
      title: g.title || members.map(titleOf).join(' + ') || '融合章',
      isGroup: true,
      memberIds: members,
      memberTitles: members.map(titleOf),
      decisionPoint: g.decisionPoint || 'global',
      titleBy: g.titleBy || '',
      objectType: '',
    };
  });
  const sameIds = (a: any, b: any) => Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((x: any, i: any) => x === b[i]);
  // groups 比较键：组序无关（按 id 排序），成员顺序/标题/决策点敏感 → 任一变即 dirty。
  const groupsKey = (g: any) => JSON.stringify(Object.keys(g || {}).sort().map((k: any) => [k, (g[k] && g[k].title) || '', (g[k] && g[k].members) || [], (g[k] && g[k].decisionPoint) || '']));
  const dirty = outlineIds != null && committedIds != null
    && (!sameIds(outlineIds, committedIds) || groupsKey(groups) !== groupsKey(committedGroups));
  const visibleOutlineCount = (outlineIds || []).filter((id: any) => COMPOSER_HIDDEN_IDS.indexOf(id) < 0).length;
  // 序号按草稿位置连续重编（1..N）：裁剪后存活章不再跳号 2、5、8。元数据屏蔽不计号。
  const outlineNoById: any = {};
  let _vno = 0;
  (outlineIds || []).forEach((id: any) => { if (COMPOSER_HIDDEN_IDS.indexOf(id) < 0 && elById[id]) { _vno += 1; outlineNoById[id] = _vno; } });
  // 多选合并：仅统计仍在大纲、非结构的已选行。
  const selectedValid = (selectedIds || []).filter((id: any) => (outlineIds || []).includes(id) && !structuralSet.has(id));
  const dedupe = (arr: any) => { const s: any = {}; const out: any[] = []; (arr || []).forEach((x: any) => { if (!s[x]) { s[x] = 1; out.push(x); } }); return out; };
  // 会话唯一、永不复用的组 id：复用 doc-grp-1 会撞上「上一组」遗留的 ChapterNarrative（orphan）
  // 与 24h 自动生成节流键，导致 auto-gen 把新组当「已生成」跳过 → 标题停在拼接名、甚至串旧组 intro。
  // 时间戳+随机后缀保证每次合并都是全新 id（后端接受任意 doc-grp-* id）。
  const newGroupId = () => 'doc-grp-' + Date.now().toString(36) + Math.floor(Math.random() * 1296).toString(36).padStart(2, '0');
  const expandMembers = (id: any) => (groups && groups[id] && groups[id].members) ? groups[id].members : [id];
  const defaultGroupTitle = (members: any) => {
    const ts = (members || []).map(titleOf);
    return ts.length <= 2 ? ts.join(' + ') : (ts.slice(0, 2).join(' + ') + ' 等 ' + ts.length + ' 项');
  };

  const loadComposer = () => {
    listContingencyChapters()
      .then((r: any) => {
        const ids = Array.isArray(r.include) && r.include.length ? r.include : (r.elements || []).map((e: any) => e.id);
        const grp = (r.groups && typeof r.groups === 'object') ? r.groups : {};
        setElements(r.elements || []);
        setCandidates(r.candidates || []);
        setOutlineIds(ids);
        setCommittedIds(ids);
        setGroups(grp);
        setCommittedGroups(grp);
      })
      .catch(() => { /* 离线 / 预制演示：保持 outlineIds=null → 回退静态目录 */ });
  };

  // 草稿编辑：仅改本地 outlineIds / groups，不落库、不刷新报告（待「应用更改」确认）——
  const addChapter = (id: any, atIdx: any = -1) => {
    if (!id || (outlineIds || []).includes(id)) return;
    const cur = outlineIds || [];
    setOutlineIds(atIdx >= 0 ? [...cur.slice(0, atIdx), id, ...cur.slice(atIdx)] : [...cur, id]);
  };
  const removeChapter = (id: any) => {
    if (structuralSet.has(id)) return; // 结构章固定，不可删
    setOutlineIds((outlineIds || []).filter((x: any) => x !== id));
    if (groups && groups[id]) { const n = { ...groups }; delete n[id]; setGroups(n); } // 删组 = 连成员一起移出本预案
    setSelectedIds((s: any) => (s || []).filter((x: any) => x !== id));
  };
  const moveChapter = (id: any, toIdx: any) => {
    const cur = outlineIds || [];
    if (cur.indexOf(id) < 0) return;
    const without = cur.filter((x: any) => x !== id);
    const idx = Math.max(0, Math.min(toIdx, without.length));
    if (without.indexOf(id) === idx) return;
    setOutlineIds([...without.slice(0, idx), id, ...without.slice(idx)]);
  };

  // ── 融合：多选合并 / 拖叠合并 / 改名 / 拆成员 / 拆分整组（全是本地草稿，「应用更改」才落库）──
  const toggleSelect = (id: any) => {
    if (structuralSet.has(id)) return;
    setSelectedIds((s: any) => (s || []).includes(id) ? s.filter((x: any) => x !== id) : [...(s || []), id]);
  };
  const mergeSelected = () => {
    const ids = (outlineIds || []).filter((x: any) => selectedValid.includes(x)); // 保留大纲顺序
    if (ids.length < 2) return;
    const nextGroups = { ...groups };
    let members: any[] = [];
    ids.forEach((id: any) => {
      if (nextGroups[id]) { members = members.concat(nextGroups[id].members || []); delete nextGroups[id]; }
      else members.push(id);
    });
    members = dedupe(members);
    const gid = newGroupId();
    nextGroups[gid] = { title: defaultGroupTitle(members), members, decisionPoint: (elById[members[0]] && elById[members[0]].decisionPoint) || 'global' };
    const firstIdx = (outlineIds || []).indexOf(ids[0]);
    const nextOutline = (outlineIds || []).filter((x: any) => !ids.includes(x));
    nextOutline.splice(Math.max(0, Math.min(firstIdx, nextOutline.length)), 0, gid);
    setGroups(nextGroups); setOutlineIds(nextOutline); setSelectedIds([]);
    setExpandedGroups((e: any) => [...(e || []).filter((x: any) => x !== gid), gid]);
    showToast('已合并为一章 · ' + members.length + ' 个要素');
  };
  const mergeInto = (targetId: any, draggedId: any, fromTray: any) => {
    if (!targetId || !draggedId || targetId === draggedId) return;
    if (structuralSet.has(targetId) || (!fromTray && structuralSet.has(draggedId))) return;
    const addMembers = expandMembers(draggedId);
    const nextGroups = { ...groups };
    let nextOutline = [...(outlineIds || [])];
    if (!fromTray) nextOutline = nextOutline.filter((x: any) => x !== draggedId);
    if (nextGroups[draggedId]) delete nextGroups[draggedId];
    let label = '';
    if (nextGroups[targetId]) {
      nextGroups[targetId] = { ...nextGroups[targetId], members: dedupe([...(nextGroups[targetId].members || []), ...addMembers]) };
      label = nextGroups[targetId].title;
      setExpandedGroups((e: any) => [...(e || []).filter((x: any) => x !== targetId), targetId]);
    } else {
      const gid = newGroupId();
      const members = dedupe([targetId, ...addMembers]);
      nextGroups[gid] = { title: defaultGroupTitle(members), members, decisionPoint: (elById[targetId] && elById[targetId].decisionPoint) || 'global' };
      label = nextGroups[gid].title;
      nextOutline = nextOutline.map((x: any) => (x === targetId ? gid : x));
      setExpandedGroups((e: any) => [...(e || []).filter((x: any) => x !== gid), gid]);
    }
    setGroups(nextGroups); setOutlineIds(nextOutline);
    setSelectedIds((s: any) => (s || []).filter((x: any) => x !== draggedId && x !== targetId));
    showToast('已并入《' + label + '》');
  };
  const splitMember = (gid: any, mid: any) => {
    const g = groups[gid]; if (!g) return;
    const remaining = (g.members || []).filter((x: any) => x !== mid);
    const nextGroups = { ...groups };
    const nextOutline = [...(outlineIds || [])];
    const gIdx = nextOutline.indexOf(gid);
    if (remaining.length >= 2) {
      nextGroups[gid] = { ...g, members: remaining };
      nextOutline.splice(gIdx + 1, 0, mid); // 拆出的成员落到组后面成为独立章
    } else {
      delete nextGroups[gid]; // 只剩 1 个 → 整组解散，成员全部恢复独立章（保留原顺序）
      if (gIdx >= 0) nextOutline.splice(gIdx, 1, ...(g.members || []));
      setExpandedGroups((e: any) => (e || []).filter((x: any) => x !== gid));
    }
    setGroups(nextGroups); setOutlineIds(nextOutline);
  };
  const dissolveGroup = (gid: any) => {
    const g = groups[gid]; if (!g) return;
    const nextGroups = { ...groups }; delete nextGroups[gid];
    const nextOutline = [...(outlineIds || [])];
    const gIdx = nextOutline.indexOf(gid);
    if (gIdx >= 0) nextOutline.splice(gIdx, 1, ...(g.members || []));
    setGroups(nextGroups); setOutlineIds(nextOutline);
    setExpandedGroups((e: any) => (e || []).filter((x: any) => x !== gid));
    showToast('已拆分本章 · 恢复 ' + (g.members || []).length + ' 个独立章');
  };
  const commitRename = () => {
    if (!renamingGid) { return; }
    const t = String(renameDraft || '').trim();
    // 人工改名 → titleBy='human'：后端 set_group_title 守卫，AI 融合标题永不覆盖人工命名。
    if (t && groups[renamingGid]) setGroups({ ...groups, [renamingGid]: { ...groups[renamingGid], title: t, titleBy: 'human' } });
    setRenamingGid(null); setRenameDraft('');
  };
  const toggleExpand = (gid: any) => setExpandedGroups((e: any) => (e || []).includes(gid) ? e.filter((x: any) => x !== gid) : [...(e || []), gid]);

  const onComposerDrop = () => {
    const d = dragRef.current; const drop = dropRef.current;
    dragRef.current = null; dropRef.current = null;
    setDragOverIdx(null); setMergeTargetId(null);
    if (!d || !d.id || !drop) return;
    if (drop.mode === 'merge' && drop.targetId) { mergeInto(drop.targetId, d.id, d.from === 'tray'); return; }
    if (d.from === 'tray') addChapter(d.id, drop.idx);
    else moveChapter(d.id, drop.idx);
  };
  // 拖拽稳定性：drop 落空（拖到目录区外松手）时 dragEnd 兜底清态，否则残留的 dragRef 会让下一次
  // drop 误插上一个元素；同时收掉插入指示线 / 合并高亮。
  const onComposerDragEnd = () => { dragRef.current = null; dropRef.current = null; setDragOverIdx(null); setMergeTargetId(null); };
  const onComposerDragStart = (e: any, id: any, from: any) => {
    dragRef.current = { id, from };
    try { e.dataTransfer.effectAllowed = 'move'; } catch { /* 旧内核无 dataTransfer */ }
  };
  // 行级拖拽悬停：中间 50% = 并入该行（merge 高亮），上下各 1/4 = 插入排序（按指针定前/后插入位）。
  const onComposerDragOver = (e: any, idx: any, id: any) => {
    e.preventDefault();
    const d = dragRef.current; if (!d) return;
    const rect = e.currentTarget && e.currentTarget.getBoundingClientRect ? e.currentTarget.getBoundingClientRect() : null;
    const ratio = rect && rect.height ? (e.clientY - rect.top) / rect.height : 0.5;
    const canMerge = !!elById[id] && !structuralSet.has(id) && d.id !== id && !(d.from === 'outline' && structuralSet.has(d.id));
    if (canMerge && ratio > 0.28 && ratio < 0.72) {
      dropRef.current = { mode: 'merge', idx, targetId: id };
      setMergeTargetId((v: any) => (v === id ? v : id)); setDragOverIdx(null);
    } else {
      const insertIdx = ratio >= 0.5 ? idx + 1 : idx;
      dropRef.current = { mode: 'insert', idx: insertIdx, targetId: null };
      setMergeTargetId(null); setDragOverIdx((v: any) => (v === insertIdx ? v : insertIdx));
    }
  };
  // 目录区空白（末尾）：插到末尾。
  const onComposerDragOverEnd = (e: any) => {
    e.preventDefault();
    if (!dragRef.current) return;
    const end = (outlineIds || []).length;
    dropRef.current = { mode: 'insert', idx: end, targetId: null };
    setMergeTargetId(null); setDragOverIdx((v: any) => (v === end ? v : end));
  };

  // 确认 / 撤销 / 还原默认 ——
  const applyOutline = () => {
    if (!dirty || composerBusy) return;
    const ids = outlineIds || [];
    const grp = groups || {};
    setComposerBusy(true);
    setContingencyChapters(ids, grp)
      .then(() => { setCommittedIds(ids); setCommittedGroups(grp); showToast('已应用 · ' + visibleOutlineCount + ' 章'); if (onReload) onReload(); })
      .catch((e: any) => showToast('应用失败：' + (e && e.message ? e.message : '本体服务未响应')))
      .finally(() => setComposerBusy(false));
  };
  const revertChanges = () => { if (committedIds) { setOutlineIds(committedIds); setGroups(committedGroups || {}); setSelectedIds([]); } };
  const resetDefault = () => {
    setComposerBusy(true);
    resetContingencyChapters()
      // 重置后从服务端重拉 elements/include/candidates/groups：本地状态可能含已 materialize 的
      // 临时章（doc-ot-*）/ 草稿组，用旧值回填会留下服务端已不存在的幽灵章/幽灵组。
      .then(() => { loadComposer(); setSelectedIds([]); setExpandedGroups([]); showToast('已还原默认章节目录'); if (onReload) onReload(); })
      .catch((e: any) => showToast('还原失败：' + (e && e.message ? e.message : '本体服务未响应')))
      .finally(() => setComposerBusy(false));
  };

  useEffectO(() => {
    // 首次拿到 view 后加载本体要素全集（仅详情视图：onReload 存在才能提交+刷新）。
    if (onReload && Array.isArray(effChapters) && outlineIds === null) loadComposer();
  }, [onReload, effChapters, outlineIds]);

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
    + ((isResolved || isRevealing || isFading) ? ' res-' + effDecision : '')
    + (clickable ? ' clickable' : '')
    + (instant ? ' instant' : '');

  return (
    <div ref={containerRef} className={'ont-wrap' + (compact ? ' ont-compact' : ' ont-detail') + (reportOpen ? ' ont-report-open' : '') + (resultMode === 'risk' ? ' ont-risk' : '')}>
      <canvas ref={canvasRef} className="ont-canvas" />

      {!compact && (
        <div className="ont-topbar">
          <div className="ont-brand">
            <div className="ont-brand-dot" aria-hidden="true" />
            <div className="ont-brand-txt"><b>预案本体生成</b><span>Contingency Ontology</span></div>
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
                  <div className="ont-core-title">预案本体生成中</div>
                  <div className="ont-core-sub">Generating contingency ontology</div>
                  <div className="ont-core-state" dangerouslySetInnerHTML={{ __html: ((ONT_CORE_TEXT as any)[coreKey] || ONT_CORE_TEXT.init).html }} />
                  <div className="ont-progress"><i style={{ width: progress + '%' }} /></div>
                </div>
              )}
              {showResolved && (
                <OntResolvedPanel risk={riskResolved} riskCount={riskCountTxt} core={effCore} compact={compact} onOpenReport={openReport} />
              )}
            </div>
          </div>
        </div>

        {effNodes.map((n: any) => (
          <div ref={setWrap(n.key)} key={n.key} className="ont-node-wrapper">
            <OntNodeCard node={n} st={nodeState[n.key]} clickable={clickable} onClick={() => openReport(n.anchor || ('doc-' + n.key))} />
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
        <div className="ont-drawer" style={{ width: 'calc(100% - 320px)' }}>
          <div className="ont-drawer-head">
            <div className="ont-drawer-title-row">
              <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#2f7df6" strokeWidth="2.4"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /></svg>
              <span className="ont-drawer-title-text">预案本体生成报告</span>
              <span className={'ont-vtag ' + effDecision}>{isRisk ? 'RISK' : 'CLEAR'}</span>
            </div>
            <div className="ont-rep-tools">
              <button type="button" className="ont-btn-exp" onClick={() => exportReport('word')}><IcDoc s={14} />导出 Word</button>
              <button type="button" className="ont-btn-exp pdf" onClick={() => exportReport('pdf')}><IcDoc s={14} />导出 PDF</button>
              <button type="button" className="ont-back" onClick={closeReport}>← 返回全景</button>
            </div>
          </div>
          <div className="ont-drawer-body ont-rep-scope" ref={scrollRef}>
            {OntologyReport
              ? <OntologyReport decision={effDecision} risks={effRisks} chapters={effChaptersMerged} summary={effSummary} activeSection={activeSection} dispatched={dispatched} onDispatch={dispatch} onToast={showToast} narrBusy={narrBusy} onNarrative={onNarrative} />
              : <div style={{ padding: 20, color: '#64748b' }}>报告模块加载中…</div>}
          </div>
        </div>
      )}

      {/* 章节目录（左侧）：决策生成后揭开，点章节跳到右侧内容并高亮（参考预制演示 digital-twin.html 的左目录布局） */}
      {!compact && (
        <div className="ont-toc">
          <div className="ont-toc-head">
            <div className="ont-toc-title"><span className="ont-toc-bar" />交付预案目录</div>
            <div className="ont-toc-en">CONTINGENCY CONTENTS · {(outlineIds ? visibleOutlineCount : (effChapters && effChapters.length)) || 13} 章{outlineIds ? (dirty ? ' · 未应用更改' : ' · 拖拽组装') : ''}</div>
          </div>
          <div className={'ont-toc-verdict ' + effDecision} onClick={() => openReport('doc-overall')}>
            {isRisk ? <IcWarnTri s={15} /> : <IcCheckSm />}
            <span>{effCore
              ? ('总体判定：' + effCore.decisionName + ' · ' + (effCore.conclusion || (isRisk ? '存在风险' : '可交付'))
                  + (isRisk ? ' · ' + riskCountTxt + ' 项待处置' : ''))
              : (isRisk ? ('总体判定：预案存在风险 · ' + riskCountTxt + ' 项待处置') : '总体判定：预案可交付 · 无阻断风险')}</span>
          </div>
          {outlineIds ? (
            <React.Fragment>
              {/* 本体要素托盘：未纳入的目录章按子决策点分组 + 本体类型库（任意业务 ObjectType 拖入即成章 doc-ot-*） */}
              <div className="ont-tray" style={_tray}>
                <div style={_trayHd} onClick={() => setTrayOpen((v: any) => !v)}>
                  <span>{trayOpen ? '▾' : '▸'}</span>
                  <span>添加要素{(() => {
                    const inc = (id: any) => (outlineIds || []).includes(id) || memberSet.has(id);
                    const n = (elements || []).filter((e: any) => !e.structural && !inc(e.id)).length
                      + (candidates || []).filter((e: any) => !inc(e.id)).length;
                    return n ? '（' + n + ' 个可加）' : '';
                  })()}</span>
                </div>
                {trayOpen ? (
                  <div className="ont-tray-body" style={{ marginTop: 4 }}>
                    <input style={_traySearch} value={traySearch} placeholder="搜索本体类型 / 章节名…"
                      onChange={(ev: any) => setTraySearch(ev.target.value)} />
                    <div className="ont-tray-results">
                      {(() => {
                        const q = String(traySearch || '').trim().toLowerCase();
                        const hit = (e: any) => !q || (String(e.title || '') + ' ' + String(e.objectType || '')).toLowerCase().includes(q);
                        const inc = (id: any) => (outlineIds || []).includes(id) || memberSet.has(id);
                        const dirPool = (elements || []).filter((e: any) => !e.structural && !inc(e.id) && hit(e));
                        const candPool = (candidates || []).filter((e: any) => !inc(e.id) && hit(e));
                        const chip = (e: any, dim: any) => (
                          <div key={e.id} style={dim ? { ..._chip, opacity: 0.62 } : _chip} draggable
                            onDragStart={(ev: any) => onComposerDragStart(ev, e.id, 'tray')}
                            onDragEnd={onComposerDragEnd}
                            onDoubleClick={() => addChapter(e.id)}
                            title={'拖入目录或双击加章 · ' + e.objectType}>
                            <span style={{ fontWeight: 600, color: '#23344d' }}>{e.title}{dim ? <span style={_emptyBadge}>暂无数据</span> : null}</span>
                            <span style={_chipMeta}>{e.objectType}{e.rowCount ? ' · ' + e.rowCount + ' 数据' : ''}{e.riskCount ? ' · ' + e.riskCount + ' 险' : ''} · {(e.fields || []).length} 字段</span>
                          </div>
                        );
                        return (
                          <React.Fragment>
                            {DP_GROUPS.map((g: any) => {
                              const items = dirPool.filter((e: any) => e.decisionPoint === g.key);
                              if (!items.length) return null;
                              return (
                                <div key={g.key}>
                                  <div style={_trayGroupTtl}>{g.label}</div>
                                  {items.map((e: any) => chip(e, false))}
                                </div>
                              );
                            })}
                            {candPool.length ? (
                              <div>
                                <div style={_trayGroupTtl}>本体类型库 · 未入章（拖入即成章）</div>
                                {candPool.map((e: any) => chip(e, !(e.rowCount > 0)))}
                              </div>
                            ) : null}
                            {dirPool.length + candPool.length === 0
                              ? <div style={{ fontSize: 11, color: '#94a3b8', padding: '4px 2px' }}>{q ? '无匹配的本体类型。' : '全部对象类型已纳入本预案。'}</div> : null}
                          </React.Fragment>
                        );
                      })()}
                    </div>
                  </div>
                ) : null}
              </div>

              {/* 章节大纲：拖拽排序 / ✕ 删章 / ☑ 多选合并 / 拖叠并入；结构章固定；组章可展开看成员、拆分 */}
              <div className="ont-toc-list" onDragOver={onComposerDragOverEnd} onDrop={(e: any) => { e.preventDefault(); onComposerDrop(); }}>
                {(outlineIds || []).map((id: any, idx: any) => {
                  const el = elById[id];
                  if (!el || COMPOSER_HIDDEN_IDS.indexOf(id) >= 0) return null; // 非正文章节屏蔽，但 idx 仍为真实位置（拖拽定位不乱）
                  const structural = structuralSet.has(id);
                  const isGroup = !!el.isGroup;
                  const selected = (selectedIds || []).includes(id);
                  const expanded = (expandedGroups || []).includes(id);
                  const renaming = renamingGid === id;
                  return (
                    <React.Fragment key={id}>
                      <div className={'ont-toc-item' + (activeSection === id ? ' active' : '') + (selected ? ' sel' : '')}
                        style={{ cursor: 'grab', boxShadow: mergeTargetId === id ? _mergeRowShadow : (dragOverIdx === idx ? _insertLine : undefined) }}
                        draggable={!renaming} onDragStart={(e: any) => onComposerDragStart(e, id, 'outline')}
                        onDragEnd={onComposerDragEnd}
                        onDragOver={(e: any) => { e.stopPropagation(); onComposerDragOver(e, idx, id); }}
                        onDrop={(e: any) => { e.preventDefault(); e.stopPropagation(); onComposerDrop(); }}>
                        {structural
                          ? <span style={{ width: 14, flex: '0 0 auto' }} aria-hidden="true" />
                          : <input type="checkbox" style={_selChk} checked={selected} title="选择以合并为一章"
                              onClick={(e: any) => e.stopPropagation()} onChange={(e: any) => { e.stopPropagation(); toggleSelect(id); }} />}
                        <span style={_grip} aria-hidden="true">⠿</span>
                        {isGroup
                          ? <span style={_grpCaret} title={expanded ? '收起成员' : '展开成员'} onClick={(e: any) => { e.stopPropagation(); toggleExpand(id); }}>{expanded ? '▾' : '▸'}</span>
                          : null}
                        <span className="ont-ti-idx">{outlineNoById[id]}</span>
                        <span className="ont-ti-main" style={{ cursor: renaming ? 'text' : 'pointer' }} onClick={() => { if (!renaming) openReport(id); }}>
                          {renaming
                            ? <input autoFocus style={_renameInput} value={renameDraft}
                                onClick={(e: any) => e.stopPropagation()}
                                onChange={(e: any) => setRenameDraft(e.target.value)}
                                onBlur={commitRename}
                                onKeyDown={(e: any) => { if (e.key === 'Enter') commitRename(); if (e.key === 'Escape') { setRenamingGid(null); setRenameDraft(''); } }} />
                            : <span className="ont-ti-name"
                                title={isGroup ? '双击改名 · 融合章' : undefined}
                                onDoubleClick={isGroup ? (e: any) => { e.stopPropagation(); setRenamingGid(id); setRenameDraft(el.title || ''); } : undefined}>
                                {el.title}{isGroup ? <span style={_grpBadge}>组 · {(el.memberIds || []).length} 要素</span> : null}{isGroup && el.titleBy !== 'ai' && el.titleBy !== 'human' ? <span style={_pendingChip}>待 AI 命名</span> : null}
                              </span>}
                          {!renaming
                            ? <span className={'ont-ti-src dp-' + el.decisionPoint}>{isGroup ? '融合章 · 单段正文' : (el.objectType || (DP_LABEL[el.decisionPoint] || '全局输入'))}</span>
                            : null}
                        </span>
                        {isGroup
                          ? <button type="button" style={_splitBtn} title="拆分本章（成员恢复独立章）" disabled={!!composerBusy} onClick={(e: any) => { e.stopPropagation(); dissolveGroup(id); }}>拆分</button>
                          : null}
                        {structural
                          ? <span style={_lock} title="结构章 · 固定纳入">🔒</span>
                          : <button type="button" style={_xbtn} title="移出本预案" disabled={!!composerBusy} onClick={(e: any) => { e.stopPropagation(); removeChapter(id); }}>✕</button>}
                      </div>
                      {isGroup && expanded
                        ? (el.memberIds || []).map((mid: any) => (
                            <div key={id + '/' + mid} style={_memberRow}>
                              <span aria-hidden="true">↳</span>
                              <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{titleOf(mid)}</span>
                              <span style={_memberType}>{(elById[mid] && elById[mid].objectType) || ''}</span>
                              <button type="button" style={_splitBtn} title="移出本组（恢复独立章）" disabled={!!composerBusy} onClick={(e: any) => { e.stopPropagation(); splitMember(id, mid); }}>✕ 移出</button>
                            </div>
                          ))
                        : null}
                    </React.Fragment>
                  );
                })}
                {dragOverIdx === (outlineIds || []).length
                  ? <div style={{ height: 0, boxShadow: '0 -2.5px 0 0 #2f7df6' }} aria-hidden="true" /> : null}
              </div>
              {selectedValid.length >= 1
                ? <div style={_selBar}>
                    <span>已选 {selectedValid.length} 章{selectedValid.length < 2 ? '（再选 1 章可合并）' : ''}</span>
                    <button type="button" style={{ ..._mergeBtn, ...(selectedValid.length < 2 ? { opacity: 0.5, cursor: 'default' } : {}) }}
                      disabled={selectedValid.length < 2 || !!composerBusy} onClick={mergeSelected}>合并为一章</button>
                    <button type="button" style={_miniBtn} disabled={!!composerBusy} onClick={() => setSelectedIds([])}>取消选择</button>
                  </div>
                : null}
              <div style={_actionBar}>
                <button type="button" style={dirty ? _applyBtn : _applyBtnOff} disabled={!dirty || !!composerBusy} onClick={applyOutline}>{composerBusy ? '处理中…' : (dirty ? ('✓ 应用更改 · ' + visibleOutlineCount + ' 章') : '已应用')}</button>
                {dirty ? <button type="button" style={_miniBtn} disabled={!!composerBusy} onClick={revertChanges}>撤销</button> : null}
                <button type="button" style={_miniBtn} disabled={!!composerBusy} onClick={resetDefault} title="清空裁剪，恢复全量本体目录">恢复默认</button>
              </div>
            </React.Fragment>
          ) : (
            /* 离线 / 预制演示：回退静态目录（不可拖拽） */
            <div className="ont-toc-list">
              {(effChapters || []).map((c: any) => (
                <a key={c.id} className={'ont-toc-item' + (activeSection === c.id ? ' active' : '') + (c.state === 'gap' ? ' warn' : '')}
                  onClick={() => openReport(c.id)}>
                  <span className={'ont-ti-idx' + (/^\d+$/.test(String(c.no)) ? '' : ' ont-ti-idx--label')}>{c.no}</span>
                  <span className="ont-ti-main">
                    <span className="ont-ti-name">{c.title}</span>
                    <span className={'ont-ti-src dp-' + c.decisionPoint}>{DP_LABEL[c.decisionPoint] || '全局输入'}</span>
                  </span>
                  {c.state === 'gap' ? <span className="ont-ti-dot" /> : null}
                </a>
              ))}
            </div>
          )}
          <div className="ont-toc-foot" onClick={closeReport}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg>
            返回决策大脑全景
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

    /* ===== 阅读视图：决策生成后揭开，章节目录在左、内容在右；脑图全景淡出（参考预制演示 digital-twin.html） ===== */
    .ont-report-open .ont-layer{opacity:0;pointer-events:none;transition:opacity .45s ease}
    .ont-report-open .ont-canvas{opacity:.12;transition:opacity .5s ease}
    .ont-report-open .ont-topbar{opacity:0;pointer-events:none;transition:opacity .4s ease}
    /* 内容面板：用基础 .ont-drawer 的右侧滑入（right:0 / translateX(105%)），宽度 calc(100% - 320px) 留出左侧目录 */
    /* 章节目录（左侧 TOC，参考预制演示 digital-twin.html 的 #toc：left:0 / 从左滑入） */
    .ont-toc{position:absolute;top:0;left:0;height:100%;width:320px;z-index:100;display:flex;flex-direction:column;background:rgba(255,255,255,.8);backdrop-filter:blur(42px);border-right:1px solid rgba(255,255,255,.92);box-shadow:24px 0 70px rgba(30,70,140,.1);padding:18px 14px 14px;transform:translateX(-106%);opacity:0;pointer-events:none;transition:transform .7s cubic-bezier(.22,.9,.3,1.15),opacity .5s ease}
    .ont-report-open .ont-toc{transform:translateX(0);opacity:1;pointer-events:auto}
    .ont-toc-head{padding:0 6px 12px;border-bottom:1px solid rgba(40,80,150,.1);margin-bottom:10px}
    .ont-toc-title{font-size:16px;font-weight:800;color:oklch(0.255 0.045 260);display:flex;align-items:center;gap:9px}
    .ont-toc-bar{width:4px;height:17px;border-radius:2px;background:linear-gradient(#2f7df6,#19b8d8);display:inline-block}
    .ont-toc-en{font-family:var(--font-mono,monospace);font-size:9.5px;letter-spacing:1.4px;color:#8a99b5;margin:6px 0 0 13px;text-transform:uppercase}
    .ont-toc-verdict{margin:0 4px 10px;padding:9px 11px;border-radius:10px;font-size:11.5px;font-weight:700;line-height:1.45;display:flex;align-items:center;gap:8px;cursor:pointer}
    .ont-toc-verdict svg{flex:none}
    .ont-toc-verdict.risk{background:#fff7ec;border:1px solid #fde3a7;color:#b45309}
    .ont-toc-verdict.success{background:#f0fdf8;border:1px solid #b8ebd4;color:#059669}
    .ont-tray{max-height:min(42vh,400px);display:flex;flex-direction:column;min-height:0;overflow:hidden;flex:none}
    .ont-tray-body{display:flex;flex-direction:column;min-height:0;flex:1}
    .ont-tray-results{flex:1;min-height:72px;overflow-y:auto;padding-right:3px}
    .ont-tray-results::-webkit-scrollbar{width:6px}.ont-tray-results::-webkit-scrollbar-thumb{background:#cdd9ea;border-radius:3px}
    .ont-toc-list{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:3px;padding-right:3px}
    .ont-toc-list::-webkit-scrollbar{width:6px}.ont-toc-list::-webkit-scrollbar-thumb{background:#cdd9ea;border-radius:3px}
    .ont-toc-item{display:flex;align-items:center;gap:10px;padding:8px 9px;border-radius:9px;cursor:pointer;border:1px solid transparent;transition:background .2s,border-color .2s,transform .2s}
    .ont-toc-item:hover{background:rgba(47,125,246,.06);transform:translateX(2px)}
    .ont-toc-item.active{background:rgba(47,125,246,.1);border-color:rgba(47,125,246,.26)}
    .ont-toc-item.sel{background:rgba(122,90,240,.09);border-color:rgba(122,90,240,.32)}
    .ont-toc-item{gap:8px}
    .ont-ti-idx{font-family:var(--font-mono,monospace);font-size:11px;font-weight:800;color:#94a3b8;min-width:26px;text-align:center;white-space:nowrap;flex:none}
    .ont-ti-idx.ont-ti-idx--label{font-size:9px;letter-spacing:.2px;padding:2px 6px;border-radius:5px;background:#f1f5f9;color:#64748b}
    .ont-toc-item.active .ont-ti-idx{color:#2f7df6}
    .ont-ti-main{display:flex;flex-direction:column;gap:3px;min-width:0;flex:1}
    .ont-ti-name{font-size:12.5px;font-weight:700;color:#46566f;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .ont-toc-item.active .ont-ti-name{color:#16233c}
    .ont-ti-src{font-size:9px;font-weight:800;letter-spacing:.2px;padding:1px 6px;border-radius:4px;align-self:flex-start}
    .ont-ti-src.dp-device{background:#eef4ff;color:#2563eb}
    .ont-ti-src.dp-network{background:#ecfeff;color:#0e7490}
    .ont-ti-src.dp-service{background:#f5f3ff;color:#7c3aed}
    .ont-ti-src.dp-acceptance{background:#fff7ed;color:#c2410c}
    .ont-ti-src.dp-global{background:#f1f5f9;color:#64748b}
    .ont-ti-dot{width:7px;height:7px;border-radius:50%;background:#f59e0b;flex:none;box-shadow:0 0 0 3px rgba(245,158,11,.16)}
    .ont-toc-foot{margin-top:10px;display:flex;align-items:center;justify-content:center;gap:7px;cursor:pointer;font-size:12px;font-weight:700;color:#475569;padding:10px;border-radius:10px;background:rgba(255,255,255,.7);border:1px solid #dde5f0;transition:background .2s,transform .2s}
    .ont-toc-foot:hover{background:#eef2f8;transform:translateX(-2px)}
    .ont-toc-foot svg{width:14px;height:14px}
    .ont-highlight{animation:ontHl 1.6s ease;border-color:oklch(0.621 0.193 256)!important;box-shadow:0 0 0 3px rgba(47,125,246,.16)!important}
    @keyframes ontHl{0%,45%{background:#eff6ff;transform:scale(1.008)}100%{background:#fff;transform:scale(1)}}

    .ont-toast{position:absolute;left:50%;bottom:28px;transform:translate(-50%,0);z-index:200;background:oklch(0.255 0.045 260);color:#fff;font-size:14px;font-weight:600;padding:12px 20px;border-radius:12px;box-shadow:0 16px 40px rgba(0,0,0,.25);display:flex;align-items:center;gap:8px;opacity:0;pointer-events:none;transition:all .4s cubic-bezier(.22,.9,.3,1.15)}
    .ont-toast.show{opacity:1}
    .ont-toast svg{color:#5eead4;flex:none}
  `;
  document.head.appendChild(s);
})();

export { DigitalTwinOntology };
