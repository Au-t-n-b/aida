// @ts-nocheck
/* 从 DS-1 / twin-world-export 整体移植，与项目里既有 screens/*.tsx 同等做法 — 保留 @ts-nocheck */
import React from 'react';
import { PhysicalTwin3D } from './room3d';
import { DigitalTwinOntology } from './digital-ontology';
/* AIDA · 算力底座孪生模块 — 构建动效 v2 */
import { useState as useStateTW, useEffect as useEffectTW, useRef as useRefTW } from 'react';

const TW_ANIM_MS = 5600;

/* 数字世界详情页（digital-twin.html）的来源：
   · 多文件版：(window as any).__DIGITAL_TWIN_B64 不存在 → 返回 null → iframe 走相对路径 src="digital-twin.html"
   · 单文件版：构建时注入了 base64 内联文档 → 解码为字符串 → iframe 用 srcDoc 内联渲染（无需外部文件） */
const TW_DIGITAL_SRCDOC = (function () {
  try {
    var b64 = (window as any).__DIGITAL_TWIN_B64;
    if (!b64) return null;
    var bin = atob(b64);
    var bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new TextDecoder('utf-8').decode(bytes);
  } catch (e) { return null; }
})();

(function injectTwinStyles() {
  if (document.getElementById('tw-styles')) return;
  const s = document.createElement('style');
  s.id = 'tw-styles';
  s.textContent = `
    /* ── Init ── */
    .tw-init{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:48px 24px;position:relative;overflow:hidden;background:radial-gradient(circle at 50% 38%,#f6f9fd 0%,#e7edf5 100%)}
    .tw-init-bg{position:absolute;inset:0;z-index:0;overflow:hidden;pointer-events:none}
    .tw-init-bg-canvas{position:absolute;inset:0;width:100%;height:100%;display:block}
    .tw-init > :not(.tw-init-bg){position:relative;z-index:1}
    .tw-init-emblem{width:88px;height:88px;border-radius:22px;background:var(--c-surface);border:1px solid var(--c-border);box-shadow:var(--shadow-md);display:grid;place-items:center;margin-bottom:28px;color:var(--c-brand);position:relative;animation:twEmblemBreathe 3.4s ease-in-out infinite}
    @keyframes twEmblemBreathe{0%,100%{transform:scale(1);box-shadow:var(--shadow-md),0 0 0 0 rgba(53,81,216,.22)}50%{transform:scale(1.06);box-shadow:var(--shadow-lg),0 0 0 16px rgba(53,81,216,0)}}
    .tw-init-emblem > *{animation:twEmblemGlyph 3.4s ease-in-out infinite}
    @keyframes twEmblemGlyph{0%,100%{transform:scale(1);opacity:.9}50%{transform:scale(1.08);opacity:1}}
    .tw-init-emblem::before{content:'';position:absolute;inset:-1px;border-radius:23px;padding:1px;background:linear-gradient(135deg,rgba(53,81,216,.35),transparent 55%);-webkit-mask:linear-gradient(#fff 0 0) content-box,linear-gradient(#fff 0 0);mask:linear-gradient(#fff 0 0) content-box,linear-gradient(#fff 0 0);-webkit-mask-composite:xor;mask-composite:exclude;pointer-events:none}
    .tw-init-title{font-size:20px;font-weight:650;color:var(--c-text);letter-spacing:-.02em}
    .tw-init-desc{font-size:13px;color:var(--c-text-muted);margin-top:8px;text-align:center;line-height:1.65;max-width:360px;text-wrap:pretty}
    .tw-build-btn{margin-top:32px;padding:11px 26px;border-radius:8px;background:var(--c-brand);color:#fff;font-size:14px;font-weight:600;border:none;cursor:pointer;transition:background .14s,box-shadow .14s,transform .14s;display:inline-flex;align-items:center;gap:8px;font-family:var(--font-sans);box-shadow:0 1px 2px rgba(53,81,216,.25),0 4px 14px rgba(53,81,216,.12)}
    .tw-build-btn:hover{background:var(--c-brand-hover);transform:translateY(-1px);box-shadow:0 2px 4px rgba(53,81,216,.3),0 8px 20px rgba(53,81,216,.16)}
    .tw-build-btn:active{transform:translateY(0)}

    /* ── Shell layout (overview ↔ detail morph) ── */
    .tw-shell{flex:1;display:flex;flex-direction:column;min-height:0;background:var(--c-bg);overflow:hidden}
    .tw-shell-body{flex:1;display:flex;gap:14px;padding:16px 18px;min-height:0;position:relative}
    .tw-shell--physical .tw-shell-body,.tw-shell--digital .tw-shell-body{gap:0;padding:0}
    .tw-shell-bar{opacity:1;overflow:hidden;border-bottom:1px solid var(--c-border)}
    .tw-shell--overview .tw-shell-bar{animation:twBarIn .95s cubic-bezier(.4,0,.2,1) both}
    @keyframes twBarIn{0%{max-height:0;opacity:0}70%{opacity:1}100%{max-height:66px;opacity:1}}

    .tw-shell-body--legacy{position:relative}
    .tw-half{flex:1 1 0;min-width:0;min-height:0;border-radius:var(--r-lg);display:flex;flex-direction:column;position:relative;overflow:hidden}
    .tw-shell--overview .tw-half{transition:opacity .42s cubic-bezier(.16,1,.3,1),box-shadow .2s ease,border-color .2s ease}
    .tw-shell--physical .tw-half-phys,.tw-shell--digital .tw-half-digi{animation:twDetailReveal .5s cubic-bezier(.16,1,.3,1) both}
    @keyframes twDetailReveal{from{opacity:.35}to{opacity:1}}
    .tw-half-phys{background:#0a0f18}
    .tw-half-digi{background:var(--c-surface);border:1px solid var(--c-border);box-shadow:var(--shadow-sm)}
    .tw-shell--physical .tw-half-digi,.tw-shell--digital .tw-half-phys{flex:0 0 0;opacity:0;pointer-events:none;transform:scale(.96)}
    .tw-shell--physical .tw-half-phys,.tw-shell--digital .tw-half-digi{border-radius:0;border:none;box-shadow:none}
    .tw-shell--overview .tw-half-phys,.tw-shell--overview .tw-half-digi{border-radius:var(--r-lg)}

    .tw-half-head{display:flex;align-items:center;justify-content:space-between;padding:14px 18px 0;flex-shrink:0;z-index:2}
    .tw-half-phys .tw-half-head{padding-top:16px}
    .tw-half-label{font-size:11px;font-weight:650;letter-spacing:.08em;text-transform:uppercase;font-family:var(--font-mono)}
    .tw-half-phys .tw-half-label{color:rgba(148,163,184,.85)}
    .tw-half-digi .tw-half-label{color:var(--c-text-muted)}
    .tw-half-badge{font-size:10px;font-weight:600;padding:3px 8px;border-radius:999px;font-family:var(--font-mono);letter-spacing:.02em}
    .tw-half-phys .tw-half-badge{background:rgba(220,38,38,.12);color:#fca5a5;border:1px solid rgba(220,38,38,.22)}
    .tw-half-digi .tw-half-badge{background:var(--c-brand-soft);color:var(--c-brand-text);border:1px solid rgba(53,81,216,.15)}
    .tw-half-badge.idle{background:rgba(15,157,88,.12)!important;color:#86efac!important;border-color:rgba(15,157,88,.25)!important}

    .tw-half-viz{flex:1;min-height:0;display:flex;align-items:center;justify-content:center;padding:8px 16px 12px;position:relative}
    .tw-shell--physical .tw-half-viz,.tw-shell--digital .tw-half-viz{padding:16px 24px 24px}

    .tw-half-foot{padding:0 18px 14px;font-size:11px;color:var(--c-text-faint);text-align:center;flex-shrink:0;transition:opacity .25s,height .25s,padding .25s}
    .tw-half-phys .tw-half-foot{color:rgba(148,163,184,.45)}
    .tw-shell--overview.interactive .tw-half{cursor:pointer}
    .tw-shell--overview.interactive .tw-half-phys:hover{box-shadow:inset 0 0 0 1px rgba(148,163,184,.25),0 16px 40px rgba(0,0,0,.35)}
    .tw-shell--overview.interactive .tw-half-digi:hover{box-shadow:var(--shadow-lg);border-color:var(--c-border-strong)}
    .tw-shell--overview.interactive .tw-half:hover .tw-half-foot{color:var(--c-brand);opacity:1}
    .tw-shell--physical .tw-half-foot,.tw-shell--digital .tw-half-foot{opacity:0;height:0;padding:0;overflow:hidden}

    /* ── Physical scene ── */
    .tw-phys-stage{width:100%;max-width:420px;aspect-ratio:1.35/1;position:relative}
    .tw-phys-svg{width:100%;height:100%;display:block;overflow:visible}
    .tw-cad-layer,.tw-iso-layer{transition:opacity .65s cubic-bezier(.16,1,.3,1)}
    .tw-cad-layer{opacity:1}
    .tw-iso-layer{opacity:0;position:absolute;inset:0}
    .tw-phys-stage.phase-iso .tw-cad-layer{opacity:.08}
    .tw-phys-stage.phase-iso .tw-iso-layer{opacity:1}
    .tw-phys-stage.phase-done .tw-cad-layer{opacity:0}

    .tw-rack-extrude{transform-box:fill-box;transform-origin:center bottom;transform:scaleY(0);transition:transform .55s cubic-bezier(.16,1,.3,1)}
    .tw-phys-stage.phase-iso .tw-rack-extrude{transform:scaleY(1)}
    .tw-rack-extrude.d1{transition-delay:.05s}.tw-rack-extrude.d2{transition-delay:.1s}.tw-rack-extrude.d3{transition-delay:.15s}
    .tw-rack-extrude.d4{transition-delay:.2s}.tw-rack-extrude.d5{transition-delay:.25s}.tw-rack-extrude.d6{transition-delay:.3s}
    .tw-rack-extrude.d7{transition-delay:.35s}.tw-rack-extrude.d8{transition-delay:.4s}.tw-rack-extrude.d9{transition-delay:.45s}

    .tw-floor-plane{opacity:0;transition:opacity .5s ease .15s}
    .tw-phys-stage.phase-iso .tw-floor-plane{opacity:1}

    .tw-mark{opacity:0;transform:scale(.4);transform-box:fill-box;transform-origin:center;transition:opacity .4s cubic-bezier(.16,1,.3,1),transform .45s cubic-bezier(.34,1.4,.64,1)}
    .tw-phys-stage.phase-done .tw-mark.m1{opacity:1;transform:scale(1);transition-delay:1.85s}
    .tw-phys-stage.phase-done .tw-mark.m2{opacity:1;transform:scale(1);transition-delay:2.05s}
    .tw-phys-stage.phase-done .tw-mark.m3{opacity:1;transform:scale(1);transition-delay:2.25s}
    .tw-phys-stage.static .tw-cad-layer{opacity:0}
    .tw-phys-stage.static .tw-iso-layer{opacity:1}
    .tw-phys-stage.static .tw-rack-extrude{transform:scaleY(1);transition:none}
    .tw-phys-stage.static .tw-floor-plane{opacity:1;transition:none}
    .tw-phys-stage.static .tw-mark{opacity:1;transform:scale(1);transition:none}

    .tw-mark-ring{animation:twMarkRing 2.4s ease-out infinite;transform-origin:center;transform-box:fill-box}
    .tw-mark-ring.r2{animation-delay:.8s}
    @keyframes twMarkRing{0%{opacity:.55;transform:scale(.6)}100%{opacity:0;transform:scale(2.2)}}

    /* ── Digital scene ── */
    .tw-digi-stage{width:100%;max-width:400px;aspect-ratio:1.15/1;position:relative}
    .tw-digi-svg{width:100%;height:100%;display:block;overflow:visible}
    .tw-d-center{opacity:0;transform:scale(.88);transform-box:fill-box;transform-origin:center;transition:opacity .45s cubic-bezier(.16,1,.3,1),transform .5s cubic-bezier(.34,1.4,.64,1)}
    .tw-digi-stage.phase-scan .tw-d-center,.tw-digi-stage.phase-expand .tw-d-center,.tw-digi-stage.phase-done .tw-d-center,.tw-digi-stage.static .tw-d-center{opacity:1;transform:scale(1)}
    .tw-digi-stage.static .tw-d-center{transition:none}

    .tw-d-scan{opacity:0;transition:opacity .3s}
    .tw-digi-stage.phase-scan .tw-d-scan{opacity:1;animation:twScan 1.1s ease-in-out infinite}
    @keyframes twScan{0%,100%{transform:translateY(-14px);opacity:0}15%,85%{opacity:.7}50%{transform:translateY(14px);opacity:.35}}

    .tw-d-path{stroke-dasharray:120;stroke-dashoffset:120;transition:stroke-dashoffset .65s cubic-bezier(.16,1,.3,1)}
    .tw-digi-stage.phase-expand .tw-d-path.p1,.tw-digi-stage.phase-done .tw-d-path.p1,.tw-digi-stage.static .tw-d-path.p1{stroke-dashoffset:0;transition-delay:.05s}
    .tw-digi-stage.phase-expand .tw-d-path.p2,.tw-digi-stage.phase-done .tw-d-path.p2,.tw-digi-stage.static .tw-d-path.p2{stroke-dashoffset:0;transition-delay:.18s}
    .tw-digi-stage.phase-expand .tw-d-path.p3,.tw-digi-stage.phase-done .tw-d-path.p3,.tw-digi-stage.static .tw-d-path.p3{stroke-dashoffset:0;transition-delay:.31s}
    .tw-digi-stage.phase-expand .tw-d-path.p4,.tw-digi-stage.phase-done .tw-d-path.p4,.tw-digi-stage.static .tw-d-path.p4{stroke-dashoffset:0;transition-delay:.44s}
    .tw-digi-stage.static .tw-d-path{transition:none}

    .tw-d-node{opacity:0;transform:scale(.82);transform-box:fill-box;transform-origin:center;transition:opacity .4s cubic-bezier(.16,1,.3,1),transform .45s cubic-bezier(.34,1.4,.64,1)}
    .tw-digi-stage.phase-done .tw-d-node.n1,.tw-digi-stage.static .tw-d-node.n1{opacity:1;transform:scale(1);transition-delay:1.05s}
    .tw-digi-stage.phase-done .tw-d-node.n2,.tw-digi-stage.static .tw-d-node.n2{opacity:1;transform:scale(1);transition-delay:1.2s}
    .tw-digi-stage.phase-done .tw-d-node.n3,.tw-digi-stage.static .tw-d-node.n3{opacity:1;transform:scale(1);transition-delay:1.35s}
    .tw-digi-stage.phase-done .tw-d-node.n4,.tw-digi-stage.static .tw-d-node.n4{opacity:1;transform:scale(1);transition-delay:1.5s}
    .tw-digi-stage.static .tw-d-node{transition:none}

    .tw-d-count{opacity:0;transition:opacity .35s ease}
    .tw-digi-stage.phase-done .tw-d-count,.tw-digi-stage.static .tw-d-count{opacity:1}
    .tw-digi-stage.phase-done .tw-d-count.c1{transition-delay:1.65s}
    .tw-digi-stage.phase-done .tw-d-count.c2{transition-delay:1.78s}
    .tw-digi-stage.phase-done .tw-d-count.c3{transition-delay:1.91s}
    .tw-digi-stage.phase-done .tw-d-count.c4{transition-delay:2.04s}
    .tw-digi-stage.static .tw-d-count{transition:none}

    /* ── Tab bar ── */
    .tw-bar{display:flex;align-items:center;gap:8px;padding:10px 20px;background:var(--c-surface);min-height:46px}
    .tw-tabs{display:flex;gap:2px;background:var(--c-bg-soft);border-radius:var(--r-md);padding:3px}
    .tw-tab{padding:6px 16px;border-radius:5px;border:none;font-size:12px;font-weight:550;cursor:pointer;background:transparent;color:var(--c-text-muted);transition:all .15s;font-family:var(--font-sans)}
    .tw-tab.active{background:var(--c-surface);color:var(--c-text);box-shadow:var(--shadow-sm)}
    .tw-tab:hover:not(.active){color:var(--c-text-2)}
    .tw-act{padding:5px 14px;border-radius:var(--r-md);border:1px solid var(--c-border);background:var(--c-surface);color:var(--c-text-muted);font-size:12px;cursor:pointer;transition:all .15s;font-family:var(--font-sans);display:inline-flex;align-items:center;gap:5px;white-space:nowrap;flex-shrink:0}
    .tw-act:hover{border-color:var(--c-border-strong);color:var(--c-text)}
    .tw-act.danger:hover{border-color:var(--c-danger);color:var(--c-danger);background:var(--c-danger-soft)}
    .tw-act:disabled{opacity:.5;cursor:not-allowed}

    @keyframes twFi{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
    .tw-fi{animation:twFi .35s cubic-bezier(.16,1,.3,1) both}

    /* ── Build → 水滴分裂过渡 ── */
    .tw-init-exit{position:absolute;inset:0;z-index:6;pointer-events:none;animation:twInitOut .3s cubic-bezier(.4,0,1,1) forwards}
    @keyframes twInitOut{to{opacity:0;transform:scale(.82)}}

    .tw-split{position:absolute;inset:0;z-index:8;pointer-events:none;overflow:hidden}
    .tw-goo-defs{position:absolute;width:0;height:0}
    .tw-goo{position:absolute;inset:0;filter:url(#twGoo) drop-shadow(0 8px 22px rgba(30,50,110,.16))}
    .tw-split-box{position:absolute;left:0;top:0;width:0;height:0;border-radius:22px;background:var(--c-surface)}
    /* 阶段一 (0→40%) 对齐方块大小、原尺寸裂开；阶段二 (40→100%) 放大变色 */
    @keyframes twSplitL{
      0%{left:50%;width:9%;height:16%;background:var(--c-surface);border-color:var(--c-border);opacity:0}
      10%{opacity:1}
      40%{left:38%;width:9%;height:16%;background:var(--c-surface);border-color:var(--c-border);opacity:1}
      88%{opacity:1}
      100%{left:25.5%;width:47%;height:86%;background:#0a0f18;border-color:#0a0f18;opacity:0}
    }
    @keyframes twSplitR{
      0%{left:50%;width:9%;height:16%;background:var(--c-surface);border-color:var(--c-border);opacity:0}
      10%{opacity:1}
      40%{left:62%;width:9%;height:16%;background:var(--c-surface);border-color:var(--c-border);opacity:1}
      88%{opacity:1}
      100%{left:74.5%;width:47%;height:86%;background:var(--c-surface);border-color:var(--c-border);opacity:0}
    }

    .tw-shell-enter{animation:twShellIn .5s ease both}
    @keyframes twShellIn{from{opacity:0}to{opacity:1}}
    .tw-shell-enter .tw-half-phys{animation:twHalfInL .5s ease .7s both}
    .tw-shell-enter .tw-half-digi{animation:twHalfInR .5s ease .7s both}
    @keyframes twHalfInL{0%{opacity:0}100%{opacity:1}}
    @keyframes twHalfInR{0%{opacity:0}100%{opacity:1}}

    /* ── Overview header ── */
    .tw-ovbar{display:flex;align-items:center;gap:14px;padding:10px 20px;background:var(--c-surface);min-height:62px;container-type:inline-size}
    .tw-ovbar-id{display:flex;flex-direction:column;gap:2px;flex-shrink:0}
    .tw-ovbar-eyebrow{display:flex;align-items:center;gap:7px;font-size:14px;font-weight:680;color:var(--c-text);letter-spacing:-.01em;line-height:1.15}
    .tw-ovbar-live{font-family:var(--font-mono);font-size:9px;font-weight:700;letter-spacing:.1em;color:var(--c-success-text);background:var(--c-success-soft);border:1px solid rgba(15,157,88,.2);padding:1px 6px;border-radius:4px}
    .tw-ovbar-sub{font-size:11px;color:var(--c-text-muted);font-family:var(--font-mono);letter-spacing:.01em}
    .tw-ovbar-div{width:1px;height:30px;background:var(--c-border);flex-shrink:0}
    .tw-ovbar-verdict{display:flex;align-items:center;gap:10px;padding:6px 14px 6px 12px;border-radius:10px;border:1px solid rgba(217,119,6,.28);background:var(--c-warning-soft);min-width:0;flex-shrink:1;overflow:hidden}
    .tw-ov-dot{width:9px;height:9px;border-radius:50%;flex-shrink:0;background:var(--c-warning);box-shadow:0 0 0 3px rgba(217,119,6,.14)}
    .tw-ov-vtext{display:flex;flex-direction:column;gap:1px;min-width:0}
    .tw-ov-vtext b{font-size:12.5px;font-weight:650;color:var(--c-warning-text);letter-spacing:.01em;line-height:1.2;white-space:nowrap}
    .tw-ov-vtext span{font-size:10.5px;color:var(--c-text-muted);white-space:nowrap;font-variant-numeric:tabular-nums;overflow:hidden;text-overflow:ellipsis}
    .tw-ov-vtext span b{font-weight:700;color:var(--c-text-2);font-family:var(--font-mono)}
    .tw-ov-spring{flex:1;min-width:8px}
    /* 窄宽降级：先隐次要计数行，再隐整个结论块，最后隐副标题 */
    @container (max-width:640px){.tw-ov-vtext span{display:none}}
    @container (max-width:540px){.tw-ovbar-div,.tw-ovbar-verdict{display:none}}
    @container (max-width:430px){.tw-ovbar-sub{display:none}.tw-ovbar{gap:10px}}

    /* ── Entry affordance ── */
    .tw-enter{display:inline-flex;align-items:center;gap:7px;padding:5px 14px;border-radius:999px;font-size:11.5px;font-weight:600;font-family:var(--font-sans);border:1px solid;transition:gap .18s ease,background .18s ease,border-color .18s ease,color .18s ease}
    .tw-half-phys .tw-enter{color:#aeb9c9;border-color:rgba(148,163,184,.24);background:rgba(148,163,184,.07)}
    .tw-half-digi .tw-enter{color:var(--c-text-muted);border-color:var(--c-border);background:var(--c-surface)}
    .tw-enter i{font-style:normal;font-size:13px;line-height:1;transition:transform .18s ease}
    .tw-shell--overview.interactive .tw-half-phys:hover .tw-enter{color:#eaf1fb;border-color:rgba(125,211,252,.4);background:rgba(56,130,200,.18);gap:9px}
    .tw-shell--overview.interactive .tw-half-digi:hover .tw-enter{color:var(--c-brand-text);border-color:rgba(53,81,216,.28);background:var(--c-brand-soft);gap:9px}
    .tw-shell--overview.interactive .tw-half:hover .tw-enter i{transform:translateX(2px)}

    /* ── Twin link emblem ── */
    .tw-twinlink{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);z-index:12;display:none;align-items:center;pointer-events:none}
    .tw-shell--overview.interactive .tw-twinlink{display:flex;animation:twFi .4s ease both}
    .tw-twinlink-line{width:16px;height:1px;background:linear-gradient(90deg,transparent,var(--c-border-strong))}
    .tw-twinlink-line.r{background:linear-gradient(90deg,var(--c-border-strong),transparent)}
    .tw-twinlink-node{width:32px;height:32px;border-radius:50%;background:var(--c-surface);border:1px solid var(--c-border-strong);box-shadow:var(--shadow-md);display:grid;place-items:center;color:var(--c-brand)}
    .tw-digi-frame{width:100%;height:100%;border:0;display:block;background:transparent}

    /* ── 3-way view switcher (页眉内) ── */
    .tw-seg{position:relative;display:flex;flex-shrink:0;padding:3px;border-radius:999px;background:var(--c-surface-2,#eef1f6);border:1px solid var(--c-border);font-family:var(--font-sans)}
    .tw-seg-thumb{position:absolute;top:3px;bottom:3px;width:calc((100% - 6px)/3);left:3px;border-radius:999px;background:var(--c-brand);box-shadow:0 2px 8px rgba(53,81,216,.28);transition:transform .3s cubic-bezier(.16,1,.3,1)}
    .tw-seg.on-overview .tw-seg-thumb{transform:translateX(0)}
    .tw-seg.on-physical .tw-seg-thumb{transform:translateX(100%)}
    .tw-seg.on-digital .tw-seg-thumb{transform:translateX(200%)}
    .tw-seg-btn{position:relative;z-index:1;border:none;background:transparent;padding:6px 16px;font-size:12px;font-weight:600;cursor:pointer;color:var(--c-text-muted);transition:color .25s;white-space:nowrap;font-family:var(--font-sans);min-width:74px;text-align:center}
    .tw-seg-btn:hover{color:var(--c-text)}
    .tw-seg.on-overview .tw-seg-btn:nth-of-type(1),.tw-seg.on-physical .tw-seg-btn:nth-of-type(2),.tw-seg.on-digital .tw-seg-btn:nth-of-type(3){color:#fff}

    /* ── 左导航子页签出现 ── */
    @keyframes fdySubIn{from{opacity:0;transform:translateX(-6px)}to{opacity:1;transform:none}}
    .fdy-sub-twin{animation:fdySubIn .3s cubic-bezier(.16,1,.3,1) both}
  `;
  document.head.appendChild(s);
})();

const IcTwinWorld = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
    <circle cx="8.5" cy="12" r="5" stroke="currentColor" strokeWidth="1.3" />
    <circle cx="15.5" cy="12" r="5" stroke="currentColor" strokeWidth="1.3" />
    <path d="M12 8.5v7" stroke="currentColor" strokeWidth="1" opacity=".25" />
  </svg>
);
const IcRefreshTW = () => (
  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
    <path d="M2.5 6C2.5 4.07 4.07 2.5 6 2.5C7.93 2.5 9.5 4.07 9.5 6C9.5 7.93 7.93 9.5 6 9.5C4.8 9.5 3.74 8.9 3.1 8" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" />
    <path d="M2.5 3.5 L2.5 6 L5 5.5" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
const IcBack = () => (
  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
    <path d="M8 1 L3 6 L8 11" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

/* ── Isometric helpers ── */
function iso( x: any, y: any, z: any) {
  return { x: 120 + (x - y) * 0.866, y: 95 + (x + y) * 0.5 - z };
}
function isoRack( bx: any, by: any, w: any, d: any, h: any, delayCls: any) {
  const fl = iso(bx, by, 0), fr = iso(bx + w, by, 0), bl = iso(bx, by + d, 0);
  const tl = iso(bx, by, h), tr = iso(bx + w, by, h), trb = iso(bx + w, by + d, h), tlb = iso(bx, by + d, h);
  const top = `${tl.x},${tl.y} ${tr.x},${tr.y} ${trb.x},${trb.y} ${tlb.x},${tlb.y}`;
  const left = `${fl.x},${fl.y} ${bl.x},${bl.y} ${tlb.x},${tlb.y} ${tl.x},${tl.y}`;
  const right = `${fr.x},${fr.y} ${fl.x},${fl.y} ${tl.x},${tl.y} ${tr.x},${tr.y}`;
  return (
    <g key={`${bx}-${by}`} className={`tw-rack-extrude ${delayCls}`}>
      <polygon points={left} fill="#1a2744" stroke="rgba(100,116,139,.35)" strokeWidth=".4" />
      <polygon points={right} fill="#243352" stroke="rgba(100,116,139,.35)" strokeWidth=".4" />
      <polygon points={top} fill="#2d3f5c" stroke="rgba(148,163,184,.4)" strokeWidth=".45" />
      {[0.25, 0.5, 0.75].map((t: any, i: any) => {
        const y0 = fl.y + (tl.y - fl.y) * t;
        const y1 = fr.y + (tr.y - fr.y) * t;
        return <line key={i} x1={fl.x + (bl.x - fl.x) * t * 0.3} y1={y0} x2={fr.x} y2={y1} stroke="rgba(53,81,216,.25)" strokeWidth=".35" />;
      })}
    </g>
  );
}

function ProblemMark({ cx, cy, tone, cls  }: any) {
  const color = tone === 'warn' ? '#f59e0b' : '#ef4444';
  return (
    <g className={`tw-mark ${cls}`} transform={`translate(${cx},${cy})`}>
      <circle r="14" fill={color} opacity=".08" className="tw-mark-ring" />
      <circle r="14" fill={color} opacity=".08" className="tw-mark-ring r2" />
      <circle r="4.5" fill={color} />
      <circle r="1.8" fill="#fff" opacity=".9" />
      <line x1="-7" y1="0" x2="7" y2="0" stroke={color} strokeWidth=".6" opacity=".5" />
      <line x1="0" y1="-7" x2="0" y2="7" stroke={color} strokeWidth=".6" opacity=".5" />
    </g>
  );
}

function PhysicalViz({ playing  }: any) {
  const [phase, setPhase] = useStateTW<any>(playing ? 'cad' : 'static');
  useEffectTW(() => {
    if (!playing) { setPhase('static'); return; }
    setPhase('cad');
    const t1 = setTimeout(() => setPhase('iso'), 600);
    const t2 = setTimeout(() => setPhase('done'), 1800);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [playing]);

  const stageCls = phase === 'static' ? 'static' : phase === 'cad' ? 'phase-cad' : phase === 'iso' ? 'phase-iso' : 'phase-done';
  const racks = [
    [20, 18, 8, 5, 22, 'd1'], [32, 18, 8, 5, 22, 'd2'], [44, 18, 8, 5, 22, 'd3'],
    [56, 18, 8, 5, 22, 'd4'], [68, 18, 8, 5, 22, 'd5'], [80, 18, 8, 5, 22, 'd6'],
    [20, 28, 8, 5, 22, 'd7'], [32, 28, 8, 5, 22, 'd8'], [44, 28, 8, 5, 22, 'd9'],
  ];

  return (
    <div className={`tw-phys-stage ${stageCls}`}>
      <svg className="tw-phys-svg tw-cad-layer" viewBox="0 0 240 170" aria-hidden="true">
        <defs>
          <pattern id="twCadGrid" width="12" height="12" patternUnits="userSpaceOnUse">
            <path d="M12 0 L0 0 0 12" fill="none" stroke="rgba(148,163,184,.12)" strokeWidth=".5" />
          </pattern>
        </defs>
        <rect width="240" height="170" fill="#0a0f18" />
        <rect width="240" height="170" fill="url(#twCadGrid)" />
        <rect x="28" y="22" width="164" height="118" fill="none" stroke="rgba(148,163,184,.55)" strokeWidth=".8" />
        <line x1="28" y1="68" x2="140" y2="68" stroke="rgba(148,163,184,.35)" strokeWidth=".5" strokeDasharray="4 2" />
        <line x1="140" y1="22" x2="140" y2="108" stroke="rgba(148,163,184,.35)" strokeWidth=".5" strokeDasharray="4 2" />
        <text x="82" y="58" textAnchor="middle" fill="rgba(148,163,184,.5)" fontSize="7" fontFamily="var(--font-mono)" letterSpacing=".6">HALL-A · PoD 区</text>
        <text x="168" y="42" textAnchor="middle" fill="rgba(148,163,184,.4)" fontSize="6" fontFamily="var(--font-mono)">NETWORK</text>
        <text x="168" y="82" textAnchor="middle" fill="rgba(148,163,184,.4)" fontSize="6" fontFamily="var(--font-mono)">PDU</text>
        {[36, 48, 60, 72, 84, 96, 108, 120].map(x => (
          <g key={x}>
            <rect x={x} y={76} width="8" height="18" fill="none" stroke="rgba(148,163,184,.45)" strokeWidth=".6" />
            <rect x={x} y={98} width="8" height="18" fill="none" stroke="rgba(148,163,184,.45)" strokeWidth=".6" />
          </g>
        ))}
        <rect x="148" y="30" width="36" height="28" fill="none" stroke="rgba(148,163,184,.35)" strokeWidth=".5" strokeDasharray="3 2" />
        <text x="32" y="148" fill="rgba(148,163,184,.3)" fontSize="5.5" fontFamily="var(--font-mono)">DWG-DC-K1903-A · 1:200</text>
        <text x="208" y="148" textAnchor="end" fill="rgba(148,163,184,.3)" fontSize="5.5" fontFamily="var(--font-mono)">REV.03</text>
      </svg>

      <svg className="tw-phys-svg tw-iso-layer" viewBox="0 0 240 170">
        <defs>
          <radialGradient id="twFloorGlow" cx="50%" cy="40%" r="65%">
            <stop offset="0%" stopColor="rgba(53,81,216,.12)" />
            <stop offset="100%" stopColor="rgba(10,15,24,0)" />
          </radialGradient>
          <filter id="twMarkGlow" x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur stdDeviation="2.5" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        <rect width="240" height="170" fill="#0a0f18" />
        <ellipse cx="120" cy="108" rx="88" ry="36" fill="url(#twFloorGlow)" className="tw-floor-plane" />
        {(() => {
          const f0 = iso(14, 12, 0), f1 = iso(98, 12, 0), f2 = iso(98, 42, 0), f3 = iso(14, 42, 0);
          return <polygon className="tw-floor-plane" points={`${f0.x},${f0.y} ${f1.x},${f1.y} ${f2.x},${f2.y} ${f3.x},${f3.y}`} fill="rgba(30,41,59,.65)" stroke="rgba(100,116,139,.3)" strokeWidth=".6" />;
        })()}
        {racks.map(r => isoRack(r[0], r[1], r[2], r[3], r[4], r[5]))}
        {isoRack(72, 12, 18, 8, 14, 'd3')}
        <g filter="url(#twMarkGlow)">
          <ProblemMark cx={iso(38, 22, 24).x} cy={iso(38, 22, 24).y - 8} tone="danger" cls="m1" />
          <ProblemMark cx={iso(88, 14, 16).x} cy={iso(88, 14, 16).y - 6} tone="warn" cls="m2" />
          <ProblemMark cx={iso(88, 14, 16).x + 18} cy={iso(88, 14, 16).y + 10} tone="danger" cls="m3" />
        </g>
      </svg>
    </div>
  );
}

const DIGI_NODES = [
  { key: 'net', label: '组网配置', count: 2, path: 'M120,82 C120,58 120,42 120,28', box: { x: 82, y: 8, w: 76, h: 36 }, anchor: { x: 120, y: 44 }, cls: 'n1 p1 c1' },
  { key: 'dev', label: '设备配置', count: 3, path: 'M120,82 C148,82 168,82 182,82', box: { x: 168, y: 64, w: 76, h: 36 }, anchor: { x: 182, y: 82 }, cls: 'n2 p2 c2' },
  { key: 'svc', label: '服务配置', count: 1, path: 'M120,82 C120,106 120,122 120,132', box: { x: 82, y: 132, w: 76, h: 36 }, anchor: { x: 120, y: 132 }, cls: 'n3 p3 c3' },
  { key: 'acc', label: '验收策略', count: 1, path: 'M120,82 C96,82 78,82 66,82', box: { x: 10, y: 64, w: 76, h: 36 }, anchor: { x: 66, y: 82 }, cls: 'n4 p4 c4' },
];

function DigitalViz({ playing  }: any) {
  const [phase, setPhase] = useStateTW<any>(playing ? 'idle' : 'static');
  useEffectTW(() => {
    if (!playing) { setPhase('static'); return; }
    setPhase('idle');
    const t0 = setTimeout(() => setPhase('scan'), 200);
    const t1 = setTimeout(() => setPhase('expand'), 900);
    const t2 = setTimeout(() => setPhase('done'), 1600);
    return () => { clearTimeout(t0); clearTimeout(t1); clearTimeout(t2); };
  }, [playing]);

  const stageCls = phase === 'static' ? 'static' : `phase-${phase}`;

  return (
    <div className={`tw-digi-stage ${stageCls}`}>
      <svg className="tw-digi-svg" viewBox="0 0 240 170">
        <defs>
          <filter id="twNodeShadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="rgba(15,23,42,.08)" />
          </filter>
        </defs>
        {DIGI_NODES.map(n => (
          <path key={`path-${n.key}`} d={n.path} fill="none" stroke="var(--c-border-strong)" strokeWidth="1.2" strokeLinecap="round" className={`tw-d-path ${n.cls.split(' ')[1]}`} />
        ))}
        <g className="tw-d-center" filter="url(#twNodeShadow)">
          <rect x="88" y="66" width="64" height="32" rx="8" fill="var(--c-surface)" stroke="var(--c-brand)" strokeWidth="1.2" />
          <rect x="88" y="66" width="64" height="32" rx="8" fill="var(--c-brand-soft)" opacity=".55" />
          <text x="120" y="80" textAnchor="middle" fill="var(--c-brand-text)" fontSize="10.5" fontWeight="650" fontFamily="var(--font-sans)">交付预案</text>
          <text x="120" y="91" textAnchor="middle" fill="var(--c-text-muted)" fontSize="7.5" fontFamily="var(--font-mono)" letterSpacing=".4">PARSING</text>
          <rect x="92" y="70" width="56" height="1.5" rx="1" fill="var(--c-brand)" opacity=".15" className="tw-d-scan" />
        </g>
        {DIGI_NODES.map(n => {
          const [nc, pc, cc] = n.cls.split(' ');
          const hasIssue = n.count > 0;
          return (
            <g key={n.key} className={`tw-d-node ${nc}`} filter="url(#twNodeShadow)">
              <rect x={n.box.x} y={n.box.y} width={n.box.w} height={n.box.h} rx="7" fill="var(--c-surface)" stroke={hasIssue ? 'var(--c-danger)' : 'var(--c-border)'} strokeWidth="1" />
              <text x={n.box.x + n.box.w / 2} y={n.box.y + 15} textAnchor="middle" fill="var(--c-text)" fontSize="10" fontWeight="600" fontFamily="var(--font-sans)">{n.label}</text>
              <text x={n.box.x + n.box.w / 2} y={n.box.y + 28} textAnchor="middle" fontSize="9.5" fontWeight="650" fontFamily="var(--font-mono)" className={`tw-d-count ${cc}`} fill={hasIssue ? 'var(--c-danger)' : 'var(--c-success)'}>
                {hasIssue ? `${n.count} 项待修复` : '已通过'}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function TwinSplitOverlay({ origin  }: any) {
  const rootRef = useRefTW<any>(null);
  const gooRef = useRefTW<any>(null);
  const lRef = useRefTW<any>(null), rRef = useRefTW<any>(null);
  useEffectTW(() => {
    const root = rootRef.current, goo = gooRef.current, L = lRef.current, R = rRef.current;
    if (!root || !L || !R) return;
    const W = root.clientWidth || 800, H = root.clientHeight || 500;
    // 起点: 中央呼吸方块(emblem)的实际位置 = 那颗"方形水滴"
    const o = (origin && origin.w) ? origin : { w: 88, h: 88, x: W / 2 - 44, y: H * 0.4 - 44 };
    const pad = 16, gap = 14;
    const halfW = (W - pad * 2 - gap) / 2;
    const topY = H * 0.08, halfH = H * 0.84;
    const lT = { x: pad, y: topY, w: halfW, h: halfH };
    const rT = { x: pad + halfW + gap, y: topY, w: halfW, h: halfH };
    const DUR = 1650;
    // 关键帧 (dir: -1 左 / +1 右)。水滴: 方形水滴 → 鼓胀 → 拉长颈缩 → 断裂 → 扩展成半区
    const stops = (dir: any, t: any) => [
      { o: 0,    x: o.x,                   y: o.y,                w: o.w,        h: o.h,        r: 0.42 * o.w },
      { o: 0.14, x: o.x,                   y: o.y - o.h * 0.05,   w: o.w,        h: o.h * 1.07, r: 0.47 * o.w },
      { o: 0.40, x: o.x + dir * o.w * 0.60, y: o.y,               w: o.w * 1.22, h: o.h * 0.88, r: 0.46 * o.w },
      { o: 0.60, x: o.x + dir * o.w * 1.28, y: o.y,               w: o.w,        h: o.h,        r: 0.40 * o.w },
      { o: 1,    x: t.x,                   y: t.y,                w: t.w,        h: t.h,        r: 16 },
    ];
    const lS = stops(-1, lT), rS = stops(1, rT);
    const lerp = (a: any, b: any, t: any) => a + (b - a) * t;
    const ease = (t: any) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
    function sample( S: any, p: any) {
      for (let i = 0; i < S.length - 1; i++) {
        const s = S[i], e = S[i + 1];
        if (p <= e.o || i === S.length - 2) {
          const span = e.o - s.o;
          const tt = ease(Math.max(0, Math.min(1, span ? (p - s.o) / span : 1)));
          return { x: lerp(s.x, e.x, tt), y: lerp(s.y, e.y, tt), w: lerp(s.w, e.w, tt), h: lerp(s.h, e.h, tt), r: lerp(s.r, e.r, tt) };
        }
      }
      return S[S.length - 1];
    }
    function put( el: any, v: any) { el.style.left = v.x + 'px'; el.style.top = v.y + 'px'; el.style.width = v.w + 'px'; el.style.height = v.h + 'px'; el.style.borderRadius = v.r + 'px'; }
    // 同步先画出起始水滴(即使 rAF 被节流也有可见的方形水滴)
    put(L, sample(lS, 0)); put(R, sample(rS, 0));
    // rAF 手动驱动 (本环境 WAAPI/CSS 动画会被节流冻结, rAF 稳定)
    let raf: any, start: any = null;
    function tick( now: any) {
      if (start == null) start = now;
      const p = Math.min(1, (now - start) / DUR);
      put(L, sample(lS, p)); put(R, sample(rS, p));
      if (goo) goo.style.opacity = p < 0.72 ? 1 : Math.max(0, 1 - (p - 0.72) / 0.28);
      if (p < 1) raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);
  return (
    <div ref={rootRef} className="tw-split" aria-hidden="true">
      <svg className="tw-goo-defs" aria-hidden="true"><defs>
        <filter id="twGoo" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="9" result="b" />
          <feColorMatrix in="b" mode="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 20 -8" />
        </filter>
      </defs></svg>
      <div ref={gooRef} className="tw-goo">
        <div ref={lRef} className="tw-split-box" />
        <div ref={rRef} className="tw-split-box" />
      </div>
    </div>
  );
}

function TwinAmbientBg() {
  const wrapRef = useRefTW<any>(null);
  const canvasRef = useRefTW<any>(null);
  useEffectTW(() => {
    const wrap = wrapRef.current, canvas = canvasRef.current;
    if (!wrap || !canvas) return;
    const ctx = canvas.getContext('2d')!;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let W = 0, H = 0, particles: any[] = [];
    const mouse = { x: -9999, y: -9999, mvx: 0, mvy: 0, active: false };
    const MR = 108, MR2 = MR * MR;
    const COLORS = ['37, 99, 235', '6, 182, 212', '99, 102, 241'];
    function build() {
      const count = Math.round(Math.min(130, Math.max(46, (W * H) / 9000)));
      particles = [];
      for (let i = 0; i < count; i++) {
        const px = Math.random() * W, py = Math.random() * H;
        particles.push({
          x: px, y: py,
          hx: px, hy: py,
          hvx: (Math.random() - 0.5) * 0.16, hvy: (Math.random() - 0.5) * 0.16,
          vx: 0, vy: 0,
          size: Math.random() * 2.1 + 0.6,
          alpha: Math.random() * 0.4 + 0.16,
          color: COLORS[(Math.random() * COLORS.length) | 0],
        });
      }
    }
    function resize() {
      W = wrap.clientWidth || 600; H = wrap.clientHeight || 400;
      canvas.width = W * dpr; canvas.height = H * dpr;
      canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      build();
    }
    let raf: any;
    const maxDistSq = 122 * 122;
    function frame( t: any) {
      raf = requestAnimationFrame(frame);
      ctx.clearRect(0, 0, W, H);
      mouse.mvx *= 0.8; mouse.mvy *= 0.8;   // 游标移动速度衰减
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        // home 缓慢漂移, 保持场的流动感
        p.hx += p.hvx; p.hy += p.hvy;
        if (p.hx < 0 || p.hx > W) p.hvx *= -1;
        if (p.hy < 0 || p.hy > H) p.hvy *= -1;
        // 鼠标牡引: 尖端碰到的粒子被挑动, 并顺着游标移动被拉扯
        if (mouse.active) {
          const mdx = mouse.x - p.x, mdy = mouse.y - p.y;
          const md2 = mdx * mdx + mdy * mdy;
          if (md2 < MR2 && md2 > 0.5) {
            const md = Math.sqrt(md2);
            const w = 1 - md / MR;
            p.vx += (mdx / md) * w * 0.4 + mouse.mvx * w * 0.22;
            p.vy += (mdy / md) * w * 0.4 + mouse.mvy * w * 0.22;
          }
        }
        // 弹簧拉回 home: 鼠标停下后粒子重新聚拢
        p.vx += (p.hx - p.x) * 0.012;
        p.vy += (p.hy - p.y) * 0.012;
        p.vx *= 0.86; p.vy *= 0.86;
        p.x += p.vx; p.y += p.vy;
      }
      ctx.lineWidth = 0.4;
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const a = particles[i], b = particles[j];
          const dx = a.x - b.x, dy = a.y - b.y, d = dx * dx + dy * dy;
          if (d < maxDistSq) {
            const al = (1 - d / maxDistSq) * 0.15;
            ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
            ctx.strokeStyle = `rgba(37,99,235,${al})`; ctx.stroke();
          }
        }
      }
      const breathe = Math.sin(t * 0.0008) * 0.12 + 1;
      // 被游标挑动的“strand”: 从尖端牵出到附近粒子, 表现“拉扯”
      if (mouse.active) {
        ctx.lineWidth = 0.7;
        for (let i = 0; i < particles.length; i++) {
          const p = particles[i];
          const dx = p.x - mouse.x, dy = p.y - mouse.y, d2 = dx * dx + dy * dy;
          if (d2 < MR2) {
            const al = (1 - Math.sqrt(d2) / MR) * 0.5;
            ctx.beginPath(); ctx.moveTo(mouse.x, mouse.y); ctx.lineTo(p.x, p.y);
            ctx.strokeStyle = `rgba(${p.color},${al})`; ctx.stroke();
          }
        }
      }
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        ctx.beginPath(); ctx.arc(p.x, p.y, p.size * breathe, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${p.color},${p.alpha})`; ctx.fill();
      }
    }
    resize();
    raf = requestAnimationFrame(frame);
    const host = wrap.parentElement || wrap;
    const onMove = (e: any) => {
      const r = canvas.getBoundingClientRect();
      const nx = e.clientX - r.left, ny = e.clientY - r.top;
      if (mouse.active) { mouse.mvx = nx - mouse.x; mouse.mvy = ny - mouse.y; }
      mouse.x = nx; mouse.y = ny; mouse.active = true;
    };
    const onLeave = () => { mouse.active = false; };
    host.addEventListener('pointermove', onMove);
    host.addEventListener('pointerleave', onLeave);
    const ro = new ResizeObserver(resize); ro.observe(wrap);
    return () => { cancelAnimationFrame(raf); ro.disconnect(); host.removeEventListener('pointermove', onMove); host.removeEventListener('pointerleave', onLeave); };
  }, []);
  return (
    <div ref={wrapRef} className="tw-init-bg" aria-hidden="true">
      <canvas ref={canvasRef} className="tw-init-bg-canvas" />
    </div>
  );
}

function TwinWorldInit({ onBuild, exiting  }: any) {
  return (
    <div className={`tw-init${exiting ? ' tw-init-exit' : ''}`}>
      {!exiting && <TwinAmbientBg />}
      <div className="tw-init-emblem"><IcTwinWorld /></div>
      <div className="tw-init-title">算力底座孪生</div>
      <div className="tw-init-desc">基于项目解析数据，构建物理机房与数字交付配置的双向孪生映射</div>
      <button type="button" className="tw-build-btn" onClick={onBuild} disabled={exiting}>构建算力底座孪生</button>
    </div>
  );
}

function TwinShellBar({ onRefresh, onClear, isRefreshing, visible, phase, setPhase, physCount, digiCount  }: any) {
  if (!visible) return null;
  const isOverview = phase === 'built';
  const segPos = phase === 'physical' ? 'physical' : phase === 'digital' ? 'digital' : 'overview';
  const sub = phase === 'physical'
    ? 'D01 一层机房 · 物理孪生 · 工勘问题标注'
    : phase === 'digital'
      ? 'D01 一层机房 · 数字孪生 · 配置决策分析'
      : 'D01 一层机房 · 物理 ⇄ 数字双向映射';
  return (
    <div className="tw-shell-bar">
      <div className="tw-ovbar">
        {isOverview ? (
          <React.Fragment>
            <div className="tw-ovbar-id">
              <div className="tw-ovbar-eyebrow">算力底座孪生<span className="tw-ovbar-live">LIVE</span></div>
              <div className="tw-ovbar-sub">{sub}</div>
            </div>
            <div className="tw-ovbar-div" />
            <div className="tw-ovbar-verdict">
              <span className="tw-ov-dot" />
              <div className="tw-ov-vtext">
                <b>交付存在风险 · 待处置</b>
                <span>物理侧 <b>{physCount}</b> 处现场异常 · 数字侧 <b>{digiCount}</b> 项配置待修复</span>
              </div>
            </div>
            <div className="tw-ov-spring" />
            <button type="button" className="tw-act" onClick={onRefresh} disabled={isRefreshing}>
              <IcRefreshTW />{isRefreshing ? '更新中…' : '更新'}
            </button>
            <button type="button" className="tw-act danger" onClick={onClear}>清除</button>
          </React.Fragment>
        ) : (
          <React.Fragment>
            <div className="tw-ov-spring" />
            <div className={`tw-seg on-${segPos}`} role="tablist" aria-label="切换孪生视图">
              <span className="tw-seg-thumb" aria-hidden="true" />
              <button type="button" className="tw-seg-btn" role="tab" aria-selected={phase === 'built'} onClick={() => setPhase('built')}>概览</button>
              <button type="button" className="tw-seg-btn" role="tab" aria-selected={phase === 'physical'} onClick={() => setPhase('physical')}>物理孪生</button>
              <button type="button" className="tw-seg-btn" role="tab" aria-selected={phase === 'digital'} onClick={() => setPhase('digital')}>数字孪生</button>
            </div>
            <div className="tw-ov-spring" />
          </React.Fragment>
        )}
      </div>
    </div>
  );
}

function TwinWorld({ phase, onPhase  }: any) {
  const setPhase = onPhase;
  const [playing, setPlaying] = useStateTW<any>(false);
  const [isRefreshing, setIsRefreshing] = useStateTW<any>(false);
  const [introExiting, setIntroExiting] = useStateTW<any>(false);
  const [splitOrigin, setSplitOrigin] = useStateTW<any>(null);
  const rootRef = useRefTW<any>(null);
  const buildTimer = useRefTW<any>(null);
  const exitTimer = useRefTW<any>(null);

  const layout = phase === 'physical' ? 'physical' : phase === 'digital' ? 'digital' : 'overview';
  const interactive = phase === 'built';
  const showViz = phase !== 'init';

  useEffectTW(() => {
    if (phase === 'building') {
      setPlaying(true);
      buildTimer.current = setTimeout(() => {
        setPlaying(false);
        setIsRefreshing(false);
        setPhase('built');
      }, TW_ANIM_MS);
    } else {
      setPlaying(false);
    }
    return () => { if (buildTimer.current) clearTimeout(buildTimer.current); };
  }, [phase]);

  useEffectTW(() => () => { if (exitTimer.current) clearTimeout(exitTimer.current); }, []);

  const handleBuild = () => {
    // 捕获中央呼吸方块(emblem)的位置, 供两个矩形从它身上裂开
    try {
      const emblem = document.querySelector('.tw-init-emblem');
      const root = rootRef.current;
      if (emblem && root) {
        const er = emblem.getBoundingClientRect(), cr = root.getBoundingClientRect();
        setSplitOrigin({ x: er.left - cr.left, y: er.top - cr.top, w: er.width, h: er.height });
      } else { setSplitOrigin(null); }
    } catch (e) { setSplitOrigin(null); }
    setIntroExiting(true);
    if (exitTimer.current) clearTimeout(exitTimer.current);
    // 先跑水滴裂变动画(轻负载, 不被三期构建阔帧), 结束后再启动两侧重建
    exitTimer.current = setTimeout(() => { setIntroExiting(false); setPhase('building'); }, 1700);
  };

  const enterDetail = (side: any) => setPhase(side);
  const handleClear = () => { setPlaying(false); setPhase('init'); };
  // “更新”: 采集最新数据 → 重新跑一遍左右两侧的构建过程
  const handleRefresh = () => { setIsRefreshing(true); setPhase('building'); };

  const physBadge = interactive ? '5 现场异常' : playing ? '扫描中' : '5 现场异常';
  const digiBadge = interactive ? '7 项待修复' : playing ? '分析中' : '7 项待修复';

  return (
    <div ref={rootRef} style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minHeight: 0, position: 'relative' }}>
      {(phase === 'init' || introExiting) && <TwinWorldInit onBuild={handleBuild} exiting={introExiting} />}
      {introExiting && <TwinSplitOverlay origin={splitOrigin} />}
      {showViz && (
        <div className={`tw-shell tw-shell--${layout}${interactive ? ' interactive' : ''}${introExiting ? ' tw-shell-enter' : ''}`}>
          <TwinShellBar
            visible={phase === 'built' || phase === 'physical' || phase === 'digital'}
            phase={phase}
            setPhase={setPhase}
            onRefresh={handleRefresh}
            onClear={handleClear}
            isRefreshing={isRefreshing}
            physCount={5}
            digiCount={7}
          />
          <div className="tw-shell-body">
            <div
              className="tw-half tw-half-phys"
              onClick={interactive ? () => enterDetail('physical') : undefined}
              role={interactive ? 'button' : undefined}
              tabIndex={interactive ? 0 : undefined}
              onKeyDown={interactive ? (e: any) => { if (e.key === 'Enter') enterDetail('physical'); } : undefined}
            >
              {phase !== 'physical' && (
                <div className="tw-half-head">
                  <span className="tw-half-label">物理孪生</span>
                  <span className="tw-half-badge">{physBadge}</span>
                </div>
              )}
              <div className="tw-half-viz" style={phase === 'physical' ? { padding: 0 } : undefined}>
                {PhysicalTwin3D
                  ? <PhysicalTwin3D key={phase === 'physical' ? 'phys-detail' : 'phys-compact'} compact={phase !== 'physical'} instant={phase !== 'building'} />
                  : <PhysicalViz playing={playing} />}
              </div>
              {phase !== 'physical' && (
                <div className="tw-half-foot">{interactive ? <span className="tw-enter">进入机房孪生视图 <i>→</i></span> : '正在构建物理映射…'}</div>
              )}
            </div>
            <div
              className="tw-half tw-half-digi"
              onClick={interactive ? () => enterDetail('digital') : undefined}
              role={interactive ? 'button' : undefined}
              tabIndex={interactive ? 0 : undefined}
              onKeyDown={interactive ? (e: any) => { if (e.key === 'Enter') enterDetail('digital'); } : undefined}
            >
              {phase !== 'digital' && (
                <div className="tw-half-head">
                  <span className="tw-half-label">数字孪生</span>
                  <span className="tw-half-badge warn">{digiBadge}</span>
                </div>
              )}
              <div className="tw-half-viz" style={phase === 'digital' ? { padding: 0 } : undefined}>
                {phase === 'digital'
                  ? (TW_DIGITAL_SRCDOC
                      ? <iframe key="digi-frame" className="tw-digi-frame" srcDoc={TW_DIGITAL_SRCDOC} title="数字孪生 · 本体决策系统" />
                      : <iframe key="digi-frame" className="tw-digi-frame" src="/twin/digital-twin.html?instant=1&v=okl7" title="数字孪生 · 本体决策系统" />)
                  : (DigitalTwinOntology
                    ? <DigitalTwinOntology key="digi-compact" compact={true} instant={phase !== 'building'} />
                    : <DigitalViz playing={playing} />)}
              </div>
              {phase !== 'digital' && (
                <div className="tw-half-foot">{interactive ? <span className="tw-enter">进入配置分析视图 <i>→</i></span> : '正在解析交付预案…'}</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export { TwinWorld };
