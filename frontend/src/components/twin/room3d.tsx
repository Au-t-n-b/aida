// @ts-nocheck
import React from 'react';
import * as THREE from 'three';
import { ROOM104_DATA } from '@/data/twin/room104';
import { useState as useState3D, useEffect as useEffect3D, useRef as useRef3D } from 'react';

/* AIDA · 物理孪生 — D01 一层机房 3D 仿真
   数据来源: DXF图纸解析报告.md + 机柜位置与桥架安装明细.md (CAD mm → m)
   渲染: Three.js (UMD 全局 THREE)
   交互: 左键拖拽旋转 · 滚轮缩放 · 点击选中机柜
 */

/* ── 机房工勘问题清单 (液冷改造前期工勘 · 针对机房本体) ──
   layer: 问题所属图层 (liquid液冷 / bridge桥架 / equipment结构), 图层开关时问题点跟随显隐
   pos:  3D 世界锚点 (room 坐标系 · 单位 m, 与 items.x/y 同一参考系), 标记跟随机房一起旋转 */
const ROOM_ISSUES = [
  {
    id: 'cooling-roof', severity: 'danger', layer: 'liquid', markerText: '冷却塔屋面冲突',
    pos: { x: 7.335, y: 1.056, z: 4.2 },
    title: '闭式冷却塔与水力模块屋面部署冲突',
    scope: '液冷散热 · 屋面',
    summary: '液冷节点的闭式冷却塔与水力模块屋面部署位置，与现有太阳能光伏板冲突。',
    detail: '屋面可用区域已被光伏板占用，闭式冷却塔与水力模块缺少落位空间。需设计考量是占用还是拆除部分太阳能光伏板，并核算发电量损失与屋面结构荷载。',
    impact: '制约液冷散热侧落地，影响整列液冷节点上线节奏。',
    next: ['复核屋面结构荷载与可用面积', '评估占用 vs 拆除光伏方案', '出具光伏迁改与发电损失测算'],
  },
  {
    id: 'shaft-pipe', severity: 'danger', layer: 'liquid', markerText: '管井穿管不足',
    pos: { x: 3.135, y: 3.956, z: 2.0 },
    title: '机房侧管井穿管不满足液冷',
    scope: '液冷管路 · 管井',
    summary: '原管井按行级空调铜管设计，孔径与下线空间不满足液冷节点管路穿管。',
    detail: '既有管井是按行级空调铜管管径预留的，液冷供回水主管管径更大、数量更多，穿管与下线空间不足。需重新设计管井开孔、穿管路由与下线空间。',
    impact: '影响液冷供回水主管入室，阻塞液冷管路施工。',
    next: ['复测管井现状开孔与净空', '重算液冷主管管径与数量', '重新设计穿管路由与下线空间'],
  },
  {
    id: 'door-size', severity: 'danger', layer: 'equipment', markerText: '门高/坡道受限',
    pos: { x: 10.935, y: 3.956, z: 1.3 },
    title: '机房门尺寸不满足液冷机柜运输',
    scope: '搬运通道 · 机房门',
    summary: '机房门高度与门后斜坡宽度不满足带节点液冷机柜的运输与转弯要求。',
    detail: '液冷机柜带节点整体偏高偏重，机房门高度不足，进入门后的斜坡宽度也影响机柜转弯。现场门洞墙体已有破损，说明此前已发生设备搬运与墙体干扰。',
    impact: '阻塞液冷整机柜进场运输，存在二次破损与工期风险。',
    next: ['实测门洞净高与斜坡净宽', '复核液冷机柜运输包络尺寸', '制定门洞/坡道改造与搬运方案'],
  },
  {
    id: 'tray-conflict', severity: 'warn', layer: 'bridge', markerText: '桥架层位冲突',
    pos: { x: 6.736, y: 3.956, z: 3.82 },
    title: '既有桥架层位与液冷节点冲突',
    scope: '强弱电桥架 · 6# 机房',
    summary: '6# 机房现有 2 层弱电桥架 + 1 层电缆桥架，位置与未来液冷节点难以匹配。',
    detail: '当前已部署 2 层弱电桥架和 1 层电缆桥架，标高与路由是按风冷布局设计的，和液冷节点的管路、机柜上线位置冲突。强弱电线槽、小母线的位置需重新设计排布。',
    impact: '影响液冷节点上线与强弱电布线，需桥架改造配合。',
    next: ['梳理现有桥架层位与占用', '重新规划强弱电线槽路由', '复核小母线安装位与液冷间距'],
  },
  {
    id: 'floor-level', severity: 'warn', layer: 'equipment', markerText: '地面不平·底座',
    pos: { x: 9.735, y: 1.056, z: 0.12 },
    title: '机房地面不平 · 机柜底座容差',
    scope: '机柜底座 · 土建',
    summary: '机房内地面不平整，预制机柜底座需做容差设计。',
    detail: '机房现浇地面存在不平整，直接安装预制机柜会产生高差与应力。要求后期预制机柜前在机房内实地取点，按实测高差做机柜底座的容差与调平设计。',
    impact: '影响机柜垂直度与列内对齐，存在底座应力风险。',
    next: ['预制前机房内实地取点测高', '按实测高差设计可调底座', '复核列内机柜垂直度与对齐'],
  },
];

/* ── 机房模型 (基于 room104.json 解析生成的数据, 单位 m) ── */
const ROOM = (function buildRoomModel() {
  const raw = ROOM104_DATA || { items: [], bridges: [], liquidLines: [] };
  const cleanTag = (tag) => String(tag || '').replace(/^(104机房-|D01-)/, '');
  const items = (raw.items || []).map((it) => {
    const tag = cleanTag(it.tag);
    return { ...it, tag, fullTag: it.tag, status: 'ok', issue: null, issueLayer: null, issueId: null };
  });
  const bridges = raw.bridges || [];
  const liquidLines = raw.liquidLines || [];

  let minX = 1e9, maxX = -1e9, minY = 1e9, maxY = -1e9;
  const addXY = (x, y) => {
    if (!Number.isFinite(x) || !Number.isFinite(y)) return;
    minX = Math.min(minX, x); maxX = Math.max(maxX, x);
    minY = Math.min(minY, y); maxY = Math.max(maxY, y);
  };
  items.forEach((it) => {
    addXY(it.x - it.w / 2, it.y - it.d / 2);
    addXY(it.x + it.w / 2, it.y + it.d / 2);
  });
  bridges.forEach((b) => { addXY(b.x1, b.y1); addXY(b.x2, b.y2); });
  liquidLines.forEach((l) => { addXY(l.x1, l.y1); addXY(l.x2, l.y2); });
  if (!Number.isFinite(minX)) { minX = -8; maxX = 8; minY = -4; maxY = 10; }
  const mX = 1.4, mY = 1.4;
  const bounds = { minX: minX - mX, maxX: maxX + mX, minY: minY - mY, maxY: maxY + mY };
  const center = { x: (bounds.minX + bounds.maxX) / 2, y: (bounds.minY + bounds.maxY) / 2 };
  return { items, bridges, liquidLines, bounds, center, meta: raw.meta || {} };
})();

/* ── 2D CAD 平面图 (俯视 · 进入时显示, 随后躺下) ── */
function RoomCadPlan() {
  const { items, bridges, liquidLines, bounds, meta } = ROOM;
  const W = bounds.maxX - bounds.minX, H = bounds.maxY - bounds.minY;
  const S = 22;
  const pad = 14;
  const vw = W * S + pad * 2, vh = H * S + pad * 2;
  const px = (x) => (x - bounds.minX) * S + pad;
  const py = (y) => (bounds.maxY - y) * S + pad;
  const color = (st) => (st === 'danger' ? '#ef4444' : st === 'warn' ? '#f59e0b' : '#ff4d4d');
  const installed = meta.installedRacks || items.filter((it) => it.kind === 'rack' && it.phase === 'installed').length;
  return (
    <svg className="r3-cad-svg" viewBox={`0 0 ${vw} ${vh}`} preserveAspectRatio="xMidYMid meet">
      <defs>
        <pattern id="r3CadGrid" width={S} height={S} patternUnits="userSpaceOnUse">
          <path d={`M ${S} 0 L 0 0 0 ${S}`} fill="none" stroke="rgba(43,113,216,.10)" strokeWidth=".6" />
        </pattern>
      </defs>
      <rect x={pad} y={pad} width={W * S} height={H * S} fill="#eef3f8" />
      <rect x={pad} y={pad} width={W * S} height={H * S} fill="url(#r3CadGrid)" />
      <rect x={pad} y={pad} width={W * S} height={H * S} fill="none" stroke="#2b71d8" strokeWidth="1.4" opacity=".7" />
      {liquidLines.filter((l) => l.type && l.type.includes('主管')).map((l) => (
        <line key={l.tag} x1={px(l.x1)} y1={py(l.y1)} x2={px(l.x2)} y2={py(l.y2)}
          stroke="#10b981" strokeWidth="1.6" opacity=".45" strokeLinecap="round" />
      ))}
      {bridges.filter((b) => b.layer !== 'fiber').map((b) => (
        <line key={b.tag} x1={px(b.x1)} y1={py(b.y1)} x2={px(b.x2)} y2={py(b.y2)}
          stroke="#8a9a8a" strokeWidth="0.9" opacity=".4" strokeLinecap="round" />
      ))}
      {bridges.filter((b) => b.layer === 'fiber').map((b) => (
        <line key={b.tag} x1={px(b.x1)} y1={py(b.y1)} x2={px(b.x2)} y2={py(b.y2)}
          stroke="#7c9cb4" strokeWidth="1.4" opacity=".65" strokeLinecap="round" />
      ))}
      {items.map((it) => {
        const isRack = it.kind === 'rack';
        const isFuture = it.phase === 'future';
        const stroke = isRack
          ? (it.status !== 'ok' ? color(it.status) : isFuture ? 'rgba(255,100,100,.35)' : '#ff3b3b')
          : it.kind === 'cdu' ? '#1de9b6' : it.kind === 'odf' ? '#a78bfa' : it.kind === 'cooling' ? '#38bdf8' : '#f59e0b';
        return (
          <rect key={it.fullTag || it.tag}
            x={px(it.x) - (it.w * S) / 2} y={py(it.y) - (it.d * S) / 2}
            width={it.w * S} height={it.d * S}
            fill={isFuture ? 'rgba(255,255,255,.03)' : 'none'}
            stroke={stroke} strokeWidth={isRack ? (isFuture ? 0.7 : 1) : 1.1}
            strokeDasharray={isFuture ? '3 2' : undefined}
            opacity={isRack && isFuture ? .45 : isRack ? .85 : .9} />
        );
      })}
      <text x={vw / 2} y={pad + 16} textAnchor="middle" fill="rgba(43,113,216,.78)" fontSize="12" fontFamily="var(--font-mono)" letterSpacing="1">D01 数据中心 · 一层机房</text>
      <text x={pad + 4} y={vh - 6} fill="rgba(90,107,124,.6)" fontSize="8" fontFamily="var(--font-mono)">DXF · {items.filter((it) => it.kind === 'rack').length} 机柜位 · 本期 {installed} · 1:100</text>
    </svg>
  );
}

const R3_LAYER_KEYS = ['equipment', 'bridge', 'liquid'];

function normalizeActiveLayers(layers) {
  if (!layers) return [...R3_LAYER_KEYS];
  if (layers === 'all') return [...R3_LAYER_KEYS];
  const list = Array.isArray(layers) ? layers : [layers];
  return R3_LAYER_KEYS.filter((k) => list.includes(k));
}

function isAllLayersActive(layers) {
  const set = new Set(normalizeActiveLayers(layers));
  return R3_LAYER_KEYS.every((k) => set.has(k));
}

/* ── Three.js 3D 机房 ── */
function useRoomScene(mountRef, { onSelect, onHover, started, compact, instant, activeLayers, onGrowDone }) {
  const stateRef = useRef3D(null);
  const onSelectRef = useRef3D(onSelect);
  const onHoverRef = useRef3D(onHover);
  const onGrowDoneRef = useRef3D(onGrowDone);
  const compactRef = useRef3D(compact);
  const activeLayersRef = useRef3D(normalizeActiveLayers(activeLayers));

  useEffect3D(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  useEffect3D(() => {
    onHoverRef.current = onHover;
  }, [onHover]);

  useEffect3D(() => {
    onGrowDoneRef.current = onGrowDone;
  }, [onGrowDone]);

  useEffect3D(() => {
    compactRef.current = compact;
    if (stateRef.current) stateRef.current.setCompact(compact);
  }, [compact]);

  useEffect3D(() => {
    activeLayersRef.current = normalizeActiveLayers(activeLayers);
    if (stateRef.current) stateRef.current.setLayers(activeLayersRef.current);
  }, [activeLayers]);

  useEffect3D(() => {
    if (!started || !mountRef.current || typeof THREE === 'undefined') return;
    const mount = mountRef.current;
    const W0 = mount.clientWidth || 800, H0 = mount.clientHeight || 500;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x565d68);
    scene.fog = new THREE.Fog(0x565d68, 32, 100);

    const camera = new THREE.PerspectiveCamera(42, W0 / H0, 0.1, 400);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(W0, H0);
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    mount.appendChild(renderer.domElement);
    renderer.domElement.style.display = 'block';
    renderer.domElement.style.touchAction = 'none';

    // Lights — 写实机房照明 (整体调暗一档)
    scene.add(new THREE.HemisphereLight(0xdfe7f0, 0x848d99, 0.22));
    scene.add(new THREE.AmbientLight(0xffffff, 0.04));
    const key = new THREE.DirectionalLight(0xffffff, 0.72);
    const _kb = ROOM.bounds, _kw = _kb.maxX - _kb.minX, _kd = _kb.maxY - _kb.minY;
    key.position.set(_kw * 0.4, 22, -_kd * 0.3);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    key.shadow.bias = -0.0004;
    key.shadow.normalBias = 0.03;
    {
      const sc = key.shadow.camera, r = Math.max(_kw, _kd) * 0.62;
      sc.left = -r; sc.right = r; sc.top = r; sc.bottom = -r;
      sc.near = 1; sc.far = 70; sc.updateProjectionMatrix();
    }
    scene.add(key);
    scene.add(key.target);
    const fillLt = new THREE.DirectionalLight(0xdfe7f0, 0.14);
    fillLt.position.set(-_kw * 0.4, 12, _kd * 0.4);
    scene.add(fillLt);
    // 反射环境 (竖向渐变) — 让铁皮/金属产生柔和高光与追光感
    try {
      const pmrem = new THREE.PMREMGenerator(renderer);
      const envCv = document.createElement('canvas'); envCv.width = 16; envCv.height = 64;
      const eg = envCv.getContext('2d'); const grd = eg.createLinearGradient(0, 0, 0, 64);
      grd.addColorStop(0, '#f4f7fb'); grd.addColorStop(0.12, '#aab4c0'); grd.addColorStop(0.5, '#5e6873'); grd.addColorStop(1, '#343b44');
      eg.fillStyle = grd; eg.fillRect(0, 0, 16, 64);
      const envTex = new THREE.CanvasTexture(envCv); envTex.mapping = THREE.EquirectangularReflectionMapping;
      const envRT = pmrem.fromEquirectangular(envTex);
      scene.environment = envRT.texture;
      envTex.dispose(); pmrem.dispose();
    } catch (e) {}

    const { items, bridges, liquidLines, bounds, center } = ROOM;
    const RX = (x) => x - center.x;
    const RZ = (y) => y - center.y;
    const FW = bounds.maxX - bounds.minX, FD = bounds.maxY - bounds.minY;

    const world = new THREE.Group();
    scene.add(world);
    const equipmentGroup = new THREE.Group();
    const bridgeGroup = new THREE.Group();
    const liquidGroup = new THREE.Group();
    world.add(equipmentGroup, bridgeGroup, liquidGroup);
    bridgeGroup.userData.baseOpacity = 1;
    liquidGroup.userData.baseOpacity = 1;

    // Floor — 明亮架空地板 (程序化地砖纹理, 每块 0.6m, 投影接收)
    function makeFloorTex() {
      const s = 128, cv = document.createElement('canvas'); cv.width = cv.height = s;
      const g = cv.getContext('2d');
      g.fillStyle = '#bcc3cb'; g.fillRect(0, 0, s, s);
      g.strokeStyle = '#9aa3ad'; g.lineWidth = 3; g.strokeRect(1.5, 1.5, s - 3, s - 3);
      g.strokeStyle = '#adb6bf'; g.lineWidth = 1; g.strokeRect(5, 5, s - 10, s - 10);
      g.fillStyle = '#8b95a0';
      for (const [x, y] of [[18, 18], [s - 18, 18], [18, s - 18], [s - 18, s - 18]]) { g.beginPath(); g.arc(x, y, 3, 0, 7); g.fill(); }
      const t = new THREE.CanvasTexture(cv); t.anisotropy = 8;
      if ('sRGBEncoding' in THREE) t.encoding = THREE.sRGBEncoding;
      t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(FW / 0.6, FD / 0.6);
      return t;
    }
    // polygonOffset: 把地面深度略微后推，避免机柜底面(生成动画里与地面共面)产生 z-fighting 闪烁
    const floorMat = new THREE.MeshStandardMaterial({ color: 0xffffff, map: makeFloorTex(), roughness: 0.82, metalness: 0.05, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(FW, FD), floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.position.set(0, 0, 0);
    floor.receiveShadow = true;
    world.add(floor);
    // 架空地板侧边 / 结构地面体块
    const FLOOR_H = 0.8;
    const fbase = new THREE.Mesh(new THREE.BoxGeometry(FW, FLOOR_H, FD), new THREE.MeshStandardMaterial({ color: 0xdbe2e9, roughness: 0.9, metalness: 0 }));
    fbase.position.set(0, -FLOOR_H / 2 - 0.06, 0);
    world.add(fbase);

    // 行/列定位细网格 (淡蓝灰)
    const grid = new THREE.GridHelper(Math.max(FW, FD), Math.round(Math.max(FW, FD)), 0xb9c6d4, 0xd4dde6);
    grid.position.y = 0.012;
    grid.material.opacity = 0.5; grid.material.transparent = true;
    world.add(grid);

    // 墙体已移除 (四周不画透明墙)
    // 地面描边 (淡蓝)
    const obPts = [
      new THREE.Vector3(-FW / 2, 0.02, -FD / 2), new THREE.Vector3(FW / 2, 0.02, -FD / 2),
      new THREE.Vector3(FW / 2, 0.02, FD / 2), new THREE.Vector3(-FW / 2, 0.02, FD / 2),
      new THREE.Vector3(-FW / 2, 0.02, -FD / 2),
    ];
    const outline = new THREE.Line(new THREE.BufferGeometry().setFromPoints(obPts), new THREE.LineBasicMaterial({ color: 0x9fb3c7, transparent: true, opacity: 0.55 }));
    world.add(outline);

    // Shared geometries
    const boxGeo = new THREE.BoxGeometry(1, 1, 1);
    const edgeGeo = new THREE.EdgesGeometry(boxGeo);

    // ── 设备表面纹理 (明亮·灰度, 由材质 color 着色 — 与 room3d.html 一致) ──
    const _texCache = {};
    function deviceTexture(kind) {
      // louver(竖百叶) 用于 cdu/列间空调/恒湿机; patch(配线/断路器) 用于 odf/列头柜
      const louver = (kind === 'cdu' || kind === 'cooling' || kind === 'humidifier');
      const key = louver ? 'louver' : 'patch';
      if (_texCache[key]) return _texCache[key];
      const s = 128, cv = document.createElement('canvas'); cv.width = cv.height = s;
      const g = cv.getContext('2d');
      if (louver) {
        g.fillStyle = '#dde3e9'; g.fillRect(0, 0, s, s);
        for (let i = 6; i < s; i += 11) { g.fillStyle = '#b7c0c9'; g.fillRect(i, 8, 5, s - 16); g.fillStyle = '#cfd6dd'; g.fillRect(i, 8, 1, s - 16); }
        g.strokeStyle = '#aab4bd'; g.lineWidth = 2; g.strokeRect(3, 3, s - 6, s - 6);
      } else {
        g.fillStyle = '#dfe4ea'; g.fillRect(0, 0, s, s);
        for (let y = 10; y < s - 8; y += 18) { g.fillStyle = '#c2cad2'; g.fillRect(8, y, s - 16, 11); g.fillStyle = '#9aa3ac'; for (let bx = 12; bx < s - 12; bx += 13) { g.fillRect(bx, y + 2, 7, 7); } }
      }
      const t = new THREE.CanvasTexture(cv); t.anisotropy = 8;
      if ('sRGBEncoding' in THREE) t.encoding = THREE.sRGBEncoding;
      _texCache[key] = t; return t;
    }

    // ── 设备铁皮纹理：door=正/背门(冲孔通风网+把手+顶部LED)，panel=侧板(拉丝金属)。white=白色铁皮(ODF) ──
    function rackShell(variant, future, white) {
      const key = 'shell_' + variant + (future ? '_f' : '') + (white ? '_w' : '');
      if (_texCache[key]) return _texCache[key];
      const W = 256, H = 512;
      const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
      const x = cv.getContext('2d');
      const F = future ? 0.6 : 1;
      const L = white
        ? (v => { const c = Math.min(255, ((188 + v) * (future ? 0.92 : 1)) | 0); return `rgb(${c},${c},${Math.min(255, c + 2)})`; })
        : (v => { const c = ((v + 80) * F) | 0; return `rgba(${c},${c},${Math.min(255, c + 2)},1)`; }); // 灰色金属
      // 金属底 + 竖向渐变
      const grd = x.createLinearGradient(0, 0, W, 0);
      grd.addColorStop(0, L(10)); grd.addColorStop(0.5, L(22)); grd.addColorStop(1, L(12));
      x.fillStyle = grd; x.fillRect(0, 0, W, H);
      // 拉丝细纹
      const brush = white ? 'rgba(0,0,0,' : 'rgba(255,255,255,';
      for (let i = 0; i < W; i += 2) { x.strokeStyle = brush + (0.012 + Math.random() * 0.012) + ')'; x.beginPath(); x.moveTo(i, 0); x.lineTo(i, H); x.stroke(); }
      // 外框
      x.strokeStyle = L(6); x.lineWidth = 6; x.strokeRect(5, 5, W - 10, H - 10);
      x.strokeStyle = white ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.05)'; x.lineWidth = 1; x.strokeRect(9, 9, W - 18, H - 18);
      if (variant === 'door') {
        // 冲孔通风网（蜂窝点阵）
        const top = 54, bot = H - 40, left = 26, right = W - 26;
        for (let r = 0; (top + r * 11) < bot; r++) {
          const cy = top + r * 11, off = (r % 2) ? 5.5 : 0;
          for (let cx = left + off; cx < right; cx += 11) {
            x.beginPath(); x.arc(cx, cy, 2.7, 0, 7);
            x.fillStyle = white ? 'rgba(40,46,54,0.5)' : 'rgba(0,0,0,0.72)'; x.fill();
            x.beginPath(); x.arc(cx - 0.7, cy - 0.7, 1.5, 0, 7);
            x.fillStyle = white ? 'rgba(255,255,255,0.55)' : `rgba(255,255,255,${0.05 * F})`; x.fill();
          }
        }
        // 顶部标牌条 + 状态 LED
        x.fillStyle = L(16); x.fillRect(16, 16, W - 32, 30);
        x.fillStyle = future ? 'rgba(120,140,160,0.5)' : 'rgba(90,200,140,0.95)';
        x.beginPath(); x.arc(34, 31, 5, 0, 7); x.fill();
        if (!future) { x.shadowColor = 'rgba(90,200,140,0.9)'; x.shadowBlur = 9; x.beginPath(); x.arc(34, 31, 5, 0, 7); x.fill(); x.shadowBlur = 0; }
        x.fillStyle = future ? 'rgba(90,110,130,0.4)' : 'rgba(80,170,255,0.85)';
        x.beginPath(); x.arc(52, 31, 5, 0, 7); x.fill();
        // 竖向把手
        x.fillStyle = L(40); x.fillRect(W - 40, 70, 12, H - 150);
        x.fillStyle = white ? 'rgba(0,0,0,0.08)' : `rgba(255,255,255,${0.10 * F})`; x.fillRect(W - 40, 70, 4, H - 150);
      } else {
        // 侧板：两道凹陷接缝 + 角铆钉
        x.strokeStyle = white ? 'rgba(0,0,0,0.22)' : 'rgba(0,0,0,0.5)'; x.lineWidth = 3;
        [W * 0.34, W * 0.66].forEach(px => { x.beginPath(); x.moveTo(px, 18); x.lineTo(px, H - 18); x.stroke(); });
        x.strokeStyle = white ? 'rgba(255,255,255,0.55)' : `rgba(255,255,255,${0.04 * F})`; x.lineWidth = 1;
        [W * 0.34 + 2, W * 0.66 + 2].forEach(px => { x.beginPath(); x.moveTo(px, 18); x.lineTo(px, H - 18); x.stroke(); });
        x.fillStyle = L(34);
        [[20, 20], [W - 20, 20], [20, H - 20], [W - 20, H - 20]].forEach(([cx, cy]) => { x.beginPath(); x.arc(cx, cy, 4, 0, 7); x.fill(); });
      }
      const t = new THREE.CanvasTexture(cv); t.anisotropy = 8; t.needsUpdate = true;
      if ('sRGBEncoding' in THREE) t.encoding = THREE.sRGBEncoding;
      _texCache[key] = t; return t;
    }
    // ── 机柜顶面: 灰色铁皮 + 四角光纤/网线开孔 ──
    function rackTopTex() {
      const key = 'rackTop';
      if (_texCache[key]) return _texCache[key];
      const W = 256, H = 256, cv = document.createElement('canvas'); cv.width = W; cv.height = H;
      const x = cv.getContext('2d');
      const grd = x.createLinearGradient(0, 0, W, H);
      grd.addColorStop(0, 'rgb(104,107,113)'); grd.addColorStop(0.5, 'rgb(120,123,130)'); grd.addColorStop(1, 'rgb(102,105,111)');
      x.fillStyle = grd; x.fillRect(0, 0, W, H);
      for (let i = 0; i < W; i += 2) { x.strokeStyle = `rgba(0,0,0,${0.012 + Math.random() * 0.012})`; x.beginPath(); x.moveTo(i, 0); x.lineTo(i, H); x.stroke(); }
      x.strokeStyle = 'rgba(0,0,0,0.4)'; x.lineWidth = 6; x.strokeRect(5, 5, W - 10, H - 10);
      x.strokeStyle = 'rgba(255,255,255,0.06)'; x.lineWidth = 1; x.strokeRect(9, 9, W - 18, H - 18);
      function rr(X, Y, w, h, r) { x.beginPath(); x.moveTo(X + r, Y); x.arcTo(X + w, Y, X + w, Y + h, r); x.arcTo(X + w, Y + h, X, Y + h, r); x.arcTo(X, Y + h, X, Y, r); x.arcTo(X, Y, X + w, Y, r); x.closePath(); }
      const m = 30, sz = 52;
      const corners = [[m, m], [W - m - sz, m], [m, H - m - sz], [W - m - sz, H - m - sz]];
      corners.forEach(([cx, cy]) => {
        rr(cx - 4, cy - 4, sz + 8, sz + 8, 10); x.fillStyle = 'rgba(58,61,66,1)'; x.fill();              // 开孔翻边
        rr(cx - 4, cy - 4, sz + 8, sz + 8, 10); x.lineWidth = 2; x.strokeStyle = 'rgba(150,156,164,0.55)'; x.stroke(); // 高光圈
        rr(cx, cy, sz, sz, 7); x.fillStyle = 'rgba(9,10,12,1)'; x.fill();                                // 开孔(暗)
        x.fillStyle = 'rgba(0,0,0,0.55)'; rr(cx + 5, cy + 5, sz - 10, sz - 10, 5); x.fill();              // 内部进线深度
      });
      const t = new THREE.CanvasTexture(cv); t.anisotropy = 8; if ('sRGBEncoding' in THREE) t.encoding = THREE.sRGBEncoding;
      _texCache[key] = t; return t;
    }
    // ── 恒湿机出气口: 黑铁皮 + 横向百叶窗 ──
    function louverVentTex() {
      const key = 'humLouver';
      if (_texCache[key]) return _texCache[key];
      const W = 256, H = 512, cv = document.createElement('canvas'); cv.width = W; cv.height = H;
      const x = cv.getContext('2d');
      const grd = x.createLinearGradient(0, 0, W, 0);
      grd.addColorStop(0, 'rgb(96,99,105)'); grd.addColorStop(0.5, 'rgb(112,115,122)'); grd.addColorStop(1, 'rgb(98,101,107)');
      x.fillStyle = grd; x.fillRect(0, 0, W, H);
      x.strokeStyle = 'rgba(0,0,0,0.6)'; x.lineWidth = 6; x.strokeRect(5, 5, W - 10, H - 10);
      const left = 30, right = W - 30, top = 44, bot = H * 0.66, gap = 17;
      x.fillStyle = 'rgba(6,6,8,0.95)'; x.fillRect(left - 4, top - 4, (right - left) + 8, (bot - top) + 8); // 凹陷腔体
      for (let y = top; y < bot; y += gap) {
        x.fillStyle = 'rgba(31,33,37,0.96)'; x.fillRect(left, y, right - left, gap - 5);             // 斜向百叶片
        x.fillStyle = 'rgba(122,130,140,0.5)'; x.fillRect(left, y + gap - 6, right - left, 2);        // 叶片亮边
        x.fillStyle = 'rgba(0,0,0,0.7)'; x.fillRect(left, y + gap - 4, right - left, 3);              // 叶片下缝阴影
      }
      x.strokeStyle = 'rgba(74,80,88,0.55)'; x.lineWidth = 3; x.strokeRect(left - 4, top - 4, (right - left) + 8, (bot - top) + 8);
      x.fillStyle = 'rgba(22,23,27,1)'; x.fillRect(left, bot + 22, right - left, 40);                 // 下部标牌
      x.fillStyle = 'rgba(90,200,140,0.95)'; x.beginPath(); x.arc(left + 22, bot + 42, 6, 0, 7); x.fill();
      x.fillStyle = 'rgba(80,170,255,0.85)'; x.beginPath(); x.arc(left + 44, bot + 42, 6, 0, 7); x.fill();
      const t = new THREE.CanvasTexture(cv); t.anisotropy = 8; if ('sRGBEncoding' in THREE) t.encoding = THREE.sRGBEncoding;
      _texCache[key] = t; return t;
    }
    // 明亮配色: 设备外壳深金属, 仅正面纹理用低彩度色着色 (与 room3d.html 一致)
    const BODY = 0x363b42, TOPC = 0x3e444c, BASEC = 0x5f6a76;
    const palette = {
      rack: { tint: 0x39434f, edge: 0xaebccb },
      rackFuture: { tint: 0x8aa0b5, edge: 0xb6c4d2 },
      cdu: { tint: 0x5bbfb2, edge: 0x7ec9bf },
      odf: { tint: 0xe8a85c, edge: 0xe8bd8a },
      ktpd: { tint: 0xb491d8, edge: 0xc7b0e2 },
      cooling: { tint: 0x6aa6e8, edge: 0x96c0ef },
      humidifier: { tint: 0x7cc79a, edge: 0xa3d9ba },
      power: { tint: 0xe0a64a, edge: 0xe8c184 },
      warn: { tint: 0xf0b44d, edge: 0xffb44d },
      danger: { tint: 0xef6a78, edge: 0xff5a6a },
    };

    const racks = [];
    // 照片贴图: 本期机柜(计算/网络 正/背) + 设备(CDU/列间空调/列头柜 正面)
    const _photoTL = new THREE.TextureLoader();
    const _photoCache = {};
    function cabPhoto(url) { if (_photoCache[url]) return _photoCache[url]; const src = (typeof window !== 'undefined' && window.TWIN_ASSETS && window.TWIN_ASSETS[url]) || url; const t = _photoTL.load(src, () => { try { renderer.render(scene, camera); } catch (e) {} }); if ('sRGBEncoding' in THREE) t.encoding = THREE.sRGBEncoding; t.anisotropy = 8; _photoCache[url] = t; return t; }
    function photoMat(url, op) { const m = new THREE.MeshStandardMaterial({ color: 0xffffff, map: cabPhoto(url), roughness: 0.62, metalness: 0.22, transparent: op < 1, opacity: op }); m.userData.baseOpacity = op; return m; }
    const CAB_PHOTO = {
      compute: { front: '/twin/assets/cab_compute_front.png', back: '/twin/assets/cab_compute_back.png' },
      net: { front: '/twin/assets/cab_net_front.png', back: '/twin/assets/cab_net_back.png' },
    };
    const EQ_PHOTO = {
      cdu: { front: '/twin/assets/cdu_front.png', back: '/twin/assets/cdu_front.png' },
      cooling: { front: '/twin/assets/ac_front.png', back: '/twin/assets/ac_back.png' },
      ktpd: { front: '/twin/assets/ktpd_front.png', back: '/twin/assets/ktpd_front.png' },
      odf: { front: '/twin/assets/odf_front.png', back: '/twin/assets/odf_front.png' },
    };
    // 本期机柜类型 (计算柜/网络柜) — 决定整柜照片贴图
    const CAB_TYPE = {
      A03: 'net', A05: 'net', A15: 'net', A09: 'compute', A10: 'compute', A12: 'compute', A13: 'compute',
      B12: 'net', B13: 'net', B15: 'net',
      B02: 'compute', B04: 'compute', B05: 'compute', B06: 'compute', B08: 'compute', B09: 'compute', B11: 'compute',
    };
    // 列朝向: A/B 正面相对、C/D 正面相对 → 隔列翻转 (B、D 列旋转 180°)
    const _rowY = {};
    items.forEach((it) => { if (it.kind === 'rack' && it.row) { (_rowY[it.row] = _rowY[it.row] || []).push(it.y); } });
    const ROW_CENTER = Object.keys(_rowY).map((r) => [r, _rowY[r].reduce((s, v) => s + v, 0) / _rowY[r].length]).sort((a, b) => a[1] - b[1]);
    const FLIP = new Set(ROW_CENTER.filter((_, i) => i % 2 === 1).map((x) => x[0]));
    function rowOf(it) { if (it.row) return it.row; if (!ROW_CENTER.length) return null; let best = ROW_CENTER[0][0], bd = 1e9; for (const [r, y] of ROW_CENTER) { const d = Math.abs(it.y - y); if (d < bd) { bd = d; best = r; } } return best; }
    const STD_D = (items.find((it) => it.kind === 'rack') || {}).d || 1.4; // 标准机柜深度
    const rowCenterMap = Object.fromEntries(ROW_CENTER); // 行 -> 机柜中心 Y
    const cabHoleGeo = new THREE.CircleGeometry(0.05, 20);
    const cabHoleRimGeo = new THREE.RingGeometry(0.05, 0.066, 20);
    const cabHoleMat = new THREE.MeshStandardMaterial({ color: 0x0b0c0e, roughness: 0.7, metalness: 0.3 });
    const cabHoleRimMat = new THREE.MeshStandardMaterial({ color: 0x8a9098, roughness: 0.35, metalness: 0.7, envMapIntensity: 1.4 });
    items.forEach((it) => {
      const isFuture = it.phase === 'future';
      const isRack = it.kind === 'rack';
      if (isRack && isFuture) return; // 去掉每列远期机柜的虚框/幽灵柜
      const dEff = it.kind === 'cooling' ? STD_D : it.d; // 列间空调用标准深度, 与机柜行同深
      let zCenter = it.y;
      if (it.kind === 'cooling') { const ys = _rowY[rowOf(it)]; if (ys && ys.length) { let best = ys[0], bd = 1e9; for (const y of ys) { const d = Math.abs(it.y - y); if (d < bd) { bd = d; best = y; } } zCenter = best; } } // 对齐最近的机柜行线, 前后两面齐平
      const pal = (isRack && isFuture ? palette.rackFuture : (palette[it.kind] || palette.rack));
      const baseOp = isFuture ? 0.16 : 1;
      const bodyMat = (c) => { const m = new THREE.MeshStandardMaterial({ color: c, roughness: 0.38, metalness: 0.6, envMapIntensity: 1.5, transparent: isFuture, opacity: baseOp }); m.userData.baseOpacity = baseOp; return m; };

      let mats;
      if (isRack) {
        if (isFuture) {
          const gm = new THREE.MeshStandardMaterial({ color: 0x8aa0b5, transparent: true, opacity: baseOp, roughness: 0.9, metalness: 0, depthWrite: false });
          gm.userData.baseOpacity = baseOp;
          mats = [gm, gm, gm, gm, gm, gm];
        } else {
          const panel = new THREE.MeshStandardMaterial({ color: 0xffffff, map: rackShell('panel', false), roughness: 0.3, metalness: 0.72, envMapIntensity: 1.6 });
          panel.userData.baseOpacity = 1;
          const type = CAB_TYPE[it.tag];
          if (type && CAB_PHOTO[type]) {
            const fz = photoMat(CAB_PHOTO[type].front, 1), bz = photoMat(CAB_PHOTO[type].back, 1);
            mats = [panel, panel.clone(), panel.clone(), panel.clone(), fz, bz];
          } else {
            const door = new THREE.MeshStandardMaterial({ color: 0xffffff, map: rackShell('door', false), roughness: 0.32, metalness: 0.66, envMapIntensity: 1.6 });
            door.userData.baseOpacity = 1;
            mats = [panel, panel.clone(), panel.clone(), panel.clone(), door, door.clone()];
          }
        }
      } else {
        // 所有设备统一铁皮包裹：ODF 白色铁皮，其余黑色铁皮；有照片的正/背面贴照片
        const white = it.kind === 'odf';
        const panel = new THREE.MeshStandardMaterial({ color: 0xffffff, map: rackShell('panel', false, white), roughness: white ? 0.44 : 0.3, metalness: white ? 0.34 : 0.72, envMapIntensity: white ? 1.1 : 1.6, transparent: isFuture, opacity: baseOp });
        panel.userData.baseOpacity = baseOp;
        const top = bodyMat(white ? 0xccd0d4 : 0x70767d);
        let fz, bz;
        const mkDoor = () => { const m = new THREE.MeshStandardMaterial({ color: 0xffffff, map: rackShell('door', false, white), roughness: white ? 0.44 : 0.32, metalness: white ? 0.34 : 0.66, envMapIntensity: white ? 1.1 : 1.6, transparent: isFuture, opacity: baseOp }); m.userData.baseOpacity = baseOp; return m; };
        if (EQ_PHOTO[it.kind]) {
          fz = photoMat(EQ_PHOTO[it.kind].front, baseOp); fz.transparent = isFuture; fz.opacity = baseOp;
          // 列间空调正/背面都有照片; CDU/列头柜/ODF 仅正面照片, 背面用原铁皮
          bz = (it.kind === 'cooling') ? photoMat(EQ_PHOTO[it.kind].back, baseOp) : mkDoor();
          bz.transparent = isFuture; bz.opacity = baseOp;
        } else if (it.kind === 'humidifier') {
          // 恒湿机: 黑铁皮, 正面百叶窗出气口, 其余面平板黑铁皮
          fz = new THREE.MeshStandardMaterial({ color: 0xffffff, map: louverVentTex(), roughness: 0.4, metalness: 0.62, envMapIntensity: 1.5, transparent: isFuture, opacity: baseOp }); fz.userData.baseOpacity = baseOp;
          bz = new THREE.MeshStandardMaterial({ color: 0xffffff, map: rackShell('panel', false), roughness: 0.3, metalness: 0.7, envMapIntensity: 1.6, transparent: isFuture, opacity: baseOp }); bz.userData.baseOpacity = baseOp;
        } else {
          fz = mkDoor(); bz = mkDoor();
        }
        mats = [panel, panel.clone(), top, top.clone(), fz, bz];
      }
      const mesh = new THREE.Mesh(boxGeo, mats);
      mesh.scale.set(it.w, it.h, dEff);
      mesh.position.set(RX(it.x), it.h / 2, RZ(zCenter));
      mesh.userData = it;
      mesh.rotation.y = FLIP.has(rowOf(it)) ? Math.PI : 0;
      mesh.castShadow = !isFuture;
      mesh.receiveShadow = !isFuture;

      const edges = new THREE.LineSegments(edgeGeo, new THREE.LineBasicMaterial({
        color: pal.edge, transparent: true,
        opacity: it.status === 'ok' ? (isFuture ? 0.45 : 0.1) : 0.7,
      }));
      edges.scale.copy(mesh.scale);
      edges.position.copy(mesh.position);

      // group for grow anim
      const g = new THREE.Group();
      g.add(mesh); g.add(edges);
      g.userData = { it, mesh, edges, baseY: it.h / 2, baseScaleY: it.h };
      // 机柜顶面四角圆形开孔 (进光纤/网线) — 单独叠加, 不改变顶板本身
      if (isRack) {
        const hw = it.w / 2 - 0.09, hd = dEff / 2 - 0.13, hy = it.h + 0.005, hx = RX(it.x), hz = RZ(zCenter);
        for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
          const rim = new THREE.Mesh(cabHoleRimGeo, cabHoleRimMat); rim.rotation.x = -Math.PI / 2; rim.position.set(hx + sx * hw, hy, hz + sz * hd); g.add(rim);
          const hole = new THREE.Mesh(cabHoleGeo, cabHoleMat); hole.rotation.x = -Math.PI / 2; hole.position.set(hx + sx * hw, hy - 0.001, hz + sz * hd); g.add(hole);
        }
      }
      // 列头柜/列间空调等设备装入标准机柜: 不足标准高度的部分用黑色(ODF白色)铁皮挡板封顶, 使每列高度统一
      const STD_H = 2.5;
      if (!isRack && it.h < STD_H - 0.02) {
        const capH = STD_H - it.h;
        const capWhite = it.kind === 'odf';
        const capMat = new THREE.MeshStandardMaterial({ color: 0xffffff, map: rackShell('panel', false, capWhite), roughness: capWhite ? 0.44 : 0.3, metalness: capWhite ? 0.34 : 0.72, envMapIntensity: capWhite ? 1.1 : 1.6, transparent: isFuture, opacity: baseOp });
        capMat.userData.baseOpacity = baseOp;
        const cap = new THREE.Mesh(boxGeo, capMat);
        cap.scale.set(it.w, capH, dEff);
        cap.position.set(RX(it.x), it.h + capH / 2, RZ(zCenter));
        cap.rotation.y = mesh.rotation.y;
        cap.castShadow = !isFuture; cap.receiveShadow = !isFuture;
        g.add(cap);
      }
      equipmentGroup.add(g);
      racks.push(g);
    });

    // ── 每列机柜排头的列号标牌 (A/B/C/D) ──
    (function addRowLabels() {
      const agg = {};
      let westX = 1e9; // 当期设备最西缘 (含 CDU)
      items.forEach((it) => {
        const isFut = it.phase === 'future';
        if (it.kind === 'rack' && it.row) { (agg[it.row] = agg[it.row] || { zs: [] }).zs.push(RZ(it.y)); } // 含远期, 保证 A/B/C/D 都有列号
        if (!isFut) westX = Math.min(westX, RX(it.x) - it.w / 2);
      });
      function makeRowLabel(text) {
        const c = document.createElement('canvas'); c.width = c.height = 128; const g = c.getContext('2d');
        g.fillStyle = 'rgba(43,113,216,0.82)'; g.beginPath(); g.arc(64, 64, 46, 0, 7); g.fill();
        g.fillStyle = '#fff'; g.font = 'bold 60px sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(text, 64, 67);
        const t = new THREE.CanvasTexture(c); if ('sRGBEncoding' in THREE) t.encoding = THREE.sRGBEncoding; t.anisotropy = 4;
        const mesh = new THREE.Mesh(new THREE.PlaneGeometry(0.82, 0.82), new THREE.MeshBasicMaterial({ map: t, transparent: true, depthWrite: false }));
        mesh.rotation.x = -Math.PI / 2; // 平铺在地面
        return mesh;
      }
      Object.keys(agg).forEach((r) => {
        const a = agg[r], z = a.zs.reduce((s, v) => s + v, 0) / a.zs.length;
        const sp = makeRowLabel(r); sp.position.set(westX - 0.7, 0.03, z); sp.renderOrder = 3;
        equipmentGroup.add(sp);
      });
    })();

    function setGroupOpacity(group, factor) {
      group.traverse((obj) => {
        if (obj.material) {
          const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
          mats.forEach((m) => {
            const base = m.userData.baseOpacity == null ? 1 : m.userData.baseOpacity;
            if (factor >= 0.999) {
              // 完全显现: 实体桥架写深度, 避免重叠半透明产生重影; 仅刻意半透明(智能化槽)保留透明
              m.opacity = base;
              m.transparent = !!m.userData.wantTransparent;
              m.depthWrite = true;
            } else {
              m.opacity = factor * base;
              m.transparent = true;
              m.depthWrite = false;
            }
          });
        }
      });
    }

    const overviewBridgeLimit = 14;
    const overviewBridgeSet = new Set(
      bridges
        .filter((b) => b.layer === 'fiber' || (b.type && (b.type.includes('上层') || b.type.includes('主干'))))
        .sort((a, b) => (b.length || 0) - (a.length || 0))
        .slice(0, overviewBridgeLimit)
        .map((b) => b.tag)
    );

    function addTraySegment(line, mainOnly) {
      const x1 = RX(line.x1), z1 = RZ(line.y1), x2 = RX(line.x2), z2 = RZ(line.y2);
      const dx = x2 - x1, dz = z2 - z1;
      const len = Math.max(0.04, Math.hypot(dx, dz));
      if (mainOnly && line.layer === 'fiber' && !overviewBridgeSet.has(line.tag)) return; // 概览: 光纤只留主干; 走线架(关键方向)始终显示
      const isFiber = line.layer === 'fiber' || (line.type && line.type.includes('光纤'));
      const isTray = line.layer === 'tray' || (line.type && line.type.includes('走线架'));
      if (!isFiber && !isTray) return;
      if (isTray) {
        // 只保留中间横纵的主走线架, 去掉贴边/外侧的几条
        const KEEP_TRAY = new Set(['tray-2', 'tray-3', 'tray-4', 'tray-5', 'tray-6']);
        if (!KEEP_TRAY.has(line.tag)) return;
        // 钢制主走线架: 灰色金属托盘 + 两侧立边 (架在光纤槽上方)
        const ux = dx / len, uz = dz / len, pxn = -uz, pzn = ux;
        const profH = Math.max(0.05, line.h || 0.09);
        const profW = Math.max(0.16, line.w || 0.3);
        const zL = line.installZ || 3.85;
        const cx = (x1 + x2) / 2, cz = (z1 + z2) / 2, rotY = len > 0.001 ? -Math.atan2(dz, dx) : 0;
        const trayMat = new THREE.MeshStandardMaterial({ color: 0x9fb0bf, roughness: 0.5, metalness: 0.5, transparent: true, opacity: 0.98 });
        trayMat.userData.baseOpacity = 0.98; trayMat.userData.wantTransparent = false;
        const baseT = new THREE.Mesh(new THREE.BoxGeometry(len, profH * 0.34, profW), trayMat);
        baseT.position.set(cx, zL + profH * 0.17, cz); baseT.rotation.y = rotY; baseT.castShadow = true; bridgeGroup.add(baseT);
        const railMat = trayMat.clone(); railMat.color.set(0x7f8e9d); railMat.userData.baseOpacity = 0.98; railMat.userData.wantTransparent = false;
        [-1, 1].forEach((sgn) => {
          const rail = new THREE.Mesh(new THREE.BoxGeometry(len, profH, 0.028), railMat);
          rail.position.set(cx + pxn * sgn * profW / 2, zL + profH / 2, cz + pzn * sgn * profW / 2);
          rail.rotation.y = rotY; bridgeGroup.add(rail);
        });
        return;
      }
      const zLevel = line.installZ || line.z1 || 3.45;
      let color = 0xd4a017, emissive = 0x3a2a06, opacity = 0.96, emInt = 0.22; // 金黄色桥架
      const mat = new THREE.MeshStandardMaterial({
        color, roughness: 0.42, metalness: 0.28,
        transparent: true, opacity, emissive, emissiveIntensity: emInt,
      });
      mat.userData.baseOpacity = opacity;
      mat.userData.wantTransparent = false; // 实体桥架, 不重影
      // 截面: 高=install高度方向, 宽=240/600 水平展宽 (沿路径法向)
      const profH = Math.max(0.04, line.h || (isFiber ? 0.10 : 0.08));
      const profW = Math.max(0.05, line.w || (isFiber ? 0.24 : 0.3));
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(len, profH, profW), mat);
      mesh.position.set((x1 + x2) / 2, zLevel + profH / 2, (z1 + z2) / 2);
      mesh.rotation.y = len > 0.001 ? -Math.atan2(dz, dx) : 0;
      bridgeGroup.add(mesh);
      if (isFiber) {
        const lipMat = mat.clone();
        lipMat.color.set(0xfbbf24);
        lipMat.emissive.set(0x422006);
        lipMat.opacity = 0.96;
        lipMat.userData.baseOpacity = 0.96;
        lipMat.userData.wantTransparent = false;
        const lip = new THREE.Mesh(new THREE.BoxGeometry(len, 0.012, profW + 0.02), lipMat);
        lip.position.set(mesh.position.x, zLevel + profH + 0.006, mesh.position.z);
        lip.rotation.y = mesh.rotation.y;
        bridgeGroup.add(lip);
      }
    }
    bridges.forEach((b) => addTraySegment(b, false)); // 始终渲染全部桥架/走线架, 生成过程中不丢失

    function addPipeSegment(line) {
      const p1 = new THREE.Vector3(RX(line.x1), line.z1 || 0.25, RZ(line.y1));
      const p2 = new THREE.Vector3(RX(line.x2), line.z2 || 0.25, RZ(line.y2));
      const dir = p2.clone().sub(p1);
      const len = dir.length();
      if (len < 0.02) return;
      const isReturn = line.type && line.type.includes('回');
      const mat = new THREE.MeshStandardMaterial({
        color: isReturn ? 0x22d3ee : 0x10b981,
        roughness: 0.35,
        metalness: 0.25,
        emissive: isReturn ? 0x064e5f : 0x065f46,
        emissiveIntensity: 0.25,
      });
      mat.userData.baseOpacity = 1;
      const mesh = new THREE.Mesh(new THREE.CylinderGeometry(Math.max(0.006, line.diameter || 0.012), Math.max(0.006, line.diameter || 0.012), len, 8), mat);
      mesh.position.copy(p1.clone().add(p2).multiplyScalar(0.5));
      mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.normalize());
      liquidGroup.add(mesh);
    }
    liquidLines.forEach(addPipeSegment);
    if (!instant) {
      setGroupOpacity(bridgeGroup, 0);
      setGroupOpacity(liquidGroup, 0); // 相位1 才淡入
    } else {
      // 直接进入详情/概览: 桥架与液冷已就位, 实体显现(不残留半透明重影)
      setGroupOpacity(liquidGroup, 1);
      setGroupOpacity(bridgeGroup, 1);
    }

    // ── 问题点标记: 3D 世界锚点徽章 (在 world 组内 · 随机房一起旋转, billboard 朝向相机) ──
    function roundRectPath(x, X, Y, w, h, r) { x.beginPath(); x.moveTo(X + r, Y); x.arcTo(X + w, Y, X + w, Y + h, r); x.arcTo(X + w, Y + h, X, Y + h, r); x.arcTo(X, Y + h, X, Y, r); x.arcTo(X, Y, X + w, Y, r); x.closePath(); }
    function makeBadge(issue) {
      const danger = issue.severity === 'danger';
      const col = danger ? '#ff5a6a' : '#ffb44d';
      const tagTxt = danger ? '阻塞' : '风险';
      const W = 512, H = 150;
      const c = document.createElement('canvas'); c.width = W; c.height = H;
      const x = c.getContext('2d');
      x.fillStyle = 'rgba(255,255,255,0.95)'; x.strokeStyle = col; x.lineWidth = 4;
      roundRectPath(x, 6, 6, W - 12, H - 34, 26); x.fill(); x.stroke();
      x.beginPath(); x.moveTo(W / 2 - 17, H - 32); x.lineTo(W / 2 + 17, H - 32); x.lineTo(W / 2, H - 6); x.closePath();
      x.fillStyle = 'rgba(255,255,255,0.95)'; x.fill();
      x.fillStyle = col; roundRectPath(x, 28, 26, 94, 42, 12); x.fill();
      x.fillStyle = '#ffffff'; x.font = '700 30px sans-serif'; x.textBaseline = 'middle'; x.textAlign = 'center';
      x.fillText(tagTxt, 75, 48);
      x.fillStyle = '#26313d'; x.font = '700 36px sans-serif'; x.textAlign = 'left';
      x.fillText(issue.markerText, 138, 48);
      x.fillStyle = '#6b7888'; x.font = '400 25px sans-serif';
      x.fillText(issue.scope || '', 30, 98);
      const tex = new THREE.CanvasTexture(c); tex.anisotropy = 4;
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false, depthWrite: false }));
      const bh = 1.05; sp.scale.set(bh * (W / H), bh, 1);
      sp.userData.issueId = issue.id;
      return sp;
    }
    function makeAnchorDot(sev) {
      const c = document.createElement('canvas'); c.width = 64; c.height = 64;
      const ctx = c.getContext('2d');
      const col = sev === 'danger' ? [255, 90, 106] : [255, 180, 77];
      const rgba = (a) => `rgba(${col[0]},${col[1]},${col[2]},${a})`;
      const g = ctx.createRadialGradient(32, 32, 1, 32, 32, 30);
      g.addColorStop(0, rgba(0.95)); g.addColorStop(0.35, rgba(0.45)); g.addColorStop(1, rgba(0));
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(32, 32, 30, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = rgba(0.95); ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(32, 32, 9, 0, Math.PI * 2); ctx.stroke();
      ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(32, 32, 4.5, 0, Math.PI * 2); ctx.fill();
      const tex = new THREE.CanvasTexture(c); tex.anisotropy = 4;
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false, depthWrite: false }));
      sp.scale.set(0.52, 0.52, 1);
      return sp;
    }

    const markerBadges = [];
    const markerEntries = ROOM_ISSUES.map((issue) => {
      const ax = RX(issue.pos.x), az = RZ(issue.pos.y), abz = issue.pos.z;
      const dot = makeAnchorDot(issue.severity);
      dot.position.set(ax, abz, az);
      dot.renderOrder = 6;
      world.add(dot);
      if (compact) {
        // 概览缩略图: 仅闪烁亮点, 无徽章/连线/文字
        dot.material.userData.baseOpacity = 1;
        dot.material.opacity = instant ? 1 : 0;
        return { issue, badge: null, dot, stem: null, layer: issue.layer, mats: [dot.material], blink: true };
      }
      const lift = 1.25;
      const badge = makeBadge(issue);
      badge.position.set(ax, abz + lift + 0.55, az);
      const stemMat = new THREE.LineBasicMaterial({ color: issue.severity === 'danger' ? 0xff5a6a : 0xffb44d, transparent: true, opacity: 0.8, depthTest: false });
      const stem = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(ax, abz, az), new THREE.Vector3(ax, abz + lift, az)]), stemMat);
      stem.renderOrder = 5; badge.renderOrder = 7;
      world.add(stem); world.add(badge);
      const mats = [badge.material, dot.material, stemMat];
      mats.forEach((m) => { m.userData.baseOpacity = (m.opacity == null ? 1 : m.opacity); m.opacity = instant ? m.userData.baseOpacity : 0; });
      markerBadges.push(badge);
      return { issue, badge, dot, stem, layer: issue.layer, mats, blink: false };
    });

    // ── Orbit control (custom) ──
    function cameraRadius(isCompact) {
      return Math.max(FW, FD) * (isCompact ? 1.72 : 1.15);
    }
    function finalView() {
      return { phi: compactRef.current ? 0.5 : 0.92, theta: 0.78, radius: cameraRadius(compactRef.current) };
    }
    // 生长阶段: 俯视正对 (近似 CAD 躺下后的角度) → 生长完成后抬升到等距视角
    const ctrl = instant
      ? { theta: 0.78, phi: compact ? 0.5 : 0.92, radius: cameraRadius(compact), target: new THREE.Vector3(0, 1.0, 0), auto: true, goal: null }
      : { theta: 0.0, phi: 0.5, radius: cameraRadius(true) * 1.02, target: new THREE.Vector3(0, 1.0, 0), auto: false, goal: null };
    function applyCam() {
      const { theta, phi, radius, target } = ctrl;
      camera.position.set(
        target.x + radius * Math.sin(phi) * Math.sin(theta),
        target.y + radius * Math.cos(phi),
        target.z + radius * Math.sin(phi) * Math.cos(theta),
      );
      camera.lookAt(target);
    }
    function easeInOutCubic(t) {
      return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    }
    function tweenTo(view, done, duration) {
      ctrl.goal = {
        phi: view.phi,
        theta: view.theta,
        radius: view.radius,
        fromPhi: ctrl.phi,
        fromTheta: ctrl.theta,
        fromRadius: ctrl.radius,
        start: performance.now(),
        duration: duration || 2200,
        done: done || null,
      };
    }
    applyCam();

    // 孪生概览(compact 即时进入): 每次进入都做一次「边旋转边下压」入场, 增加动态
    if (instant && compact) {
      ctrl.auto = false; ctrl.goal = null;
      ctrl.phi = 0.42; ctrl.theta = 0.12; ctrl.radius = cameraRadius(true) * 1.06; applyCam();
      tweenTo({ phi: 0.9, theta: ctrl.theta + 0.85, radius: cameraRadius(true) * 0.92 }, () => { ctrl.auto = true; }, 2600);
    }

    // ── 漫游(第一人称) · 仅详情视图 ──
    const eyeH = 1.62;
    const roam = { active: false, yaw: 0, pitch: -0.02, pos: new THREE.Vector3(0, eyeH, 0), keys: { f: 0, b: 0, l: 0, r: 0, sp: 0 }, last: 0, auto: true, lastManual: 0, path: null, seg: 0, dist: 0 };
    const avgArr = (a) => a.reduce((s, v) => s + v, 0) / a.length;
    function buildPatrol() {
      const rk = items.filter((it) => it.kind === 'rack'); // 含远期 C/D, 巡航覆盖 A B C D 全部列间通道
      if (!rk.length) { roam.path = [new THREE.Vector3(0, eyeH, -FD * 0.3), new THREE.Vector3(0, eyeH, FD * 0.3)]; return; }
      let xmin = 1e9, xmax = -1e9; const byRow = {};
      rk.forEach((it) => { const x = RX(it.x); xmin = Math.min(xmin, x); xmax = Math.max(xmax, x); (byRow[it.row] = byRow[it.row] || []).push(RZ(it.y)); });
      const rows = Object.keys(byRow).map((r) => avgArr(byRow[r])).sort((a, b) => a - b);
      const aisles = [];
      for (let i = 0; i < rows.length - 1; i++) aisles.push((rows[i] + rows[i + 1]) / 2); // 只走列间通道, 不从 A 列之外开始
      if (!aisles.length) aisles.push(rows[0]);
      const xL = xmin - 0.5, xR = xmax + 0.5, p = [];
      aisles.forEach((z, i) => { if (i % 2 === 0) { p.push(new THREE.Vector3(xL, eyeH, z), new THREE.Vector3(xR, eyeH, z)); } else { p.push(new THREE.Vector3(xR, eyeH, z), new THREE.Vector3(xL, eyeH, z)); } });
      roam.path = p;
    }
    function snapNearest() {
      if (!roam.path) return; let best = 0, bd = 1e9, bdist = 0;
      for (let i = 0; i < roam.path.length; i++) {
        const a = roam.path[i], b = roam.path[(i + 1) % roam.path.length], ab = b.clone().sub(a), L2 = ab.lengthSq() || 1;
        let t = roam.pos.clone().sub(a).dot(ab) / L2; t = Math.max(0, Math.min(1, t));
        const d = a.clone().add(ab.clone().multiplyScalar(t)).distanceTo(roam.pos);
        if (d < bd) { bd = d; best = i; bdist = t * Math.sqrt(L2); }
      }
      roam.seg = best; roam.dist = bdist;
    }
    function startRoam() {
      roam.active = true; ctrl.auto = false; ctrl.goal = null;
      if (!roam.path) buildPatrol();
      roam.auto = true; roam.seg = 0; roam.dist = 0; roam.pos.copy(roam.path[0]);
      const nx = roam.path[1].clone().sub(roam.path[0]); roam.yaw = Math.atan2(nx.x, nx.z); roam.pitch = -0.02; roam.last = performance.now();
    }
    function stopRoam() {
      roam.active = false; const v = finalView();
      ctrl.theta = v.theta; ctrl.phi = v.phi; ctrl.radius = v.radius; ctrl.target.set(0, 1, 0);
      ctrl.auto = true; ctrl.goal = null; applyCam();
    }
    function pauseAuto() { if (roam.active) { roam.auto = false; roam.lastManual = performance.now(); } }
    function onKey(e, v) {
      switch (e.code) {
        case 'KeyW': case 'ArrowUp': roam.keys.f = v; break;
        case 'KeyS': case 'ArrowDown': roam.keys.b = v; break;
        case 'KeyA': case 'ArrowLeft': roam.keys.l = v; break;
        case 'KeyD': case 'ArrowRight': roam.keys.r = v; break;
        case 'ShiftLeft': case 'ShiftRight': roam.keys.sp = v; break;
        default: return;
      }
      if (roam.active) { e.preventDefault(); if (v) pauseAuto(); }
    }
    const kd = (e) => onKey(e, 1), ku = (e) => onKey(e, 0);
    window.addEventListener('keydown', kd);
    window.addEventListener('keyup', ku);

    let dragging = false, lastX = 0, lastY = 0, moved = 0, idleT = 0;
    const dom = renderer.domElement;
    const onDown = (e) => { dragging = true; moved = 0; lastX = e.clientX; lastY = e.clientY; ctrl.auto = false; ctrl.goal = null; dom.setPointerCapture && dom.setPointerCapture(e.pointerId); };
    const onMove = (e) => {
      if (!dragging) return;
      const dx = e.clientX - lastX, dy = e.clientY - lastY;
      lastX = e.clientX; lastY = e.clientY; moved += Math.abs(dx) + Math.abs(dy);
      if (roam.active) {
        pauseAuto();
        roam.yaw -= dx * 0.005;
        roam.pitch = Math.min(1.2, Math.max(-1.2, roam.pitch - dy * 0.005));
      } else {
        ctrl.theta -= dx * 0.006;
        ctrl.phi = Math.min(1.45, Math.max(0.18, ctrl.phi - dy * 0.006));
        applyCam();
      }
    };
    const onUp = (e) => {
      dragging = false; idleT = performance.now();
      if (moved < 6) pick(e);
    };
    const onWheel = (e) => {
      e.preventDefault();
      if (roam.active) return;
      ctrl.radius = Math.min(FD * 2.6, Math.max(5, ctrl.radius * (1 + Math.sign(e.deltaY) * 0.08)));
      ctrl.auto = false; idleT = performance.now(); applyCam();
    };
    dom.addEventListener('pointerdown', onDown);
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    dom.addEventListener('wheel', onWheel, { passive: false });

    // Picking
    const ray = new THREE.Raycaster();
    const ndc = new THREE.Vector2();
    let selected = null;
    function pick(e) {
      const rect = dom.getBoundingClientRect();
      ndc.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      ndc.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      ray.setFromCamera(ndc, camera);
      // 先判定问题徽章 (可点击定位问题)
      if (markerBadges.length) {
        const bvis = markerBadges.filter((b) => b.visible);
        const bh = ray.intersectObjects(bvis, false);
        if (bh.length) { onSelectRef.current && onSelectRef.current({ __issueId: bh[0].object.userData.issueId }); return; }
      }
      const meshes = racks.map((g) => g.userData.mesh);
      const hits = ray.intersectObjects(meshes, false);
      if (selected) { selected.edges.material.opacity = selected.it.status === 'ok' ? 0.28 : 0.7; selected = null; }
      if (hits.length) {
        const g = racks.find((gg) => gg.userData.mesh === hits[0].object);
        if (g) { g.userData.edges.material.opacity = 1; g.userData.edges.material.color.set(0xffffff); selected = g.userData; onSelectRef.current && onSelectRef.current(g.userData.it); }
      } else { onSelectRef.current && onSelectRef.current(null); }
    }

    // Hover: 悬浮机柜/设备显示编号 (仅大页面)
    let hoveredMesh = null;
    function hover(e) {
      if (compactRef.current || dragging || !onHoverRef.current) return;
      const rect = dom.getBoundingClientRect();
      ndc.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      ndc.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      ray.setFromCamera(ndc, camera);
      const meshes = racks.map((g) => g.userData.mesh);
      const hits = ray.intersectObjects(meshes, false);
      if (hits.length) {
        const g = racks.find((gg) => gg.userData.mesh === hits[0].object);
        if (g) {
          hoveredMesh = hits[0].object;
          dom.style.cursor = 'pointer';
          onHoverRef.current({ it: g.userData.it, x: e.clientX, y: e.clientY });
          return;
        }
      }
      if (hoveredMesh) { hoveredMesh = null; dom.style.cursor = ''; onHoverRef.current(null); }
    }
    dom.addEventListener('pointermove', hover);
    const onLeave = () => { if (onHoverRef.current) onHoverRef.current(null); hoveredMesh = null; dom.style.cursor = ''; };
    dom.addEventListener('pointerleave', onLeave);

    // ── Render loop + grow animation ──
    const startBase = performance.now();
    let raf, growStart = startBase + (instant ? 0 : 220);
    // 构建相位(ms): ① 液冷管线+列间空调 → ② 机柜/ODF/CDU → ③ 线缆桥架 → ④ 统计HUD/问题点
    const PH1_LIQUID = 780;   // 相位1: 液冷+空调 生长窗口
    const GROW_DUR = 560;
    function ROW_DELAY(it) {
      const row = String(it.tag || '').match(/^([A-F])/)?.[1];
      const map = { A: 0, B: 90, C: 180, D: 300, E: 420, F: 540 };
      return map[row] || 0;
    }
    racks.forEach((g, i) => {
      const it = g.userData.it;
      let delay;
      if (it.kind === 'cooling') {
        delay = 40 + (i % 8) * 48;                       // 相位1: 列间空调与液冷管同步出现
      } else {
        // 相位2: 机柜/CDU/ODF/电源, 按行序生长, 远期机柜更晚
        delay = PH1_LIQUID + 200 + ROW_DELAY(it) + (it.phase === 'future' ? 620 : 0);
      }
      g.userData.delay = delay;
      g.scale.y = instant ? 1 : 0.001;
    });
    const easeOut = (t) => 1 - Math.pow(1 - t, 3);
    let maxDelay = 0; racks.forEach((g) => { maxDelay = Math.max(maxDelay, g.userData.delay); });
    const liquidStart = growStart; // 相位1 液冷+空调
    const growDoneAt = instant ? startBase : growStart + maxDelay + GROW_DUR + 120;
    let growReported = false;
    let revealAt = instant ? startBase : Infinity;
    let revealReported = instant;
    let bridgeRevealAt = instant ? startBase : Infinity;
    let bridgeShown = instant;
    let cameraLiftAt = instant ? startBase : Infinity;
    let cameraLiftStarted = instant;
    let autoVel = 0; // 自转角速度 (缓动, 避免补间结束瞬间的速度跳变)

    function frame(now) {
      raf = requestAnimationFrame(frame);
      // 在渲染前同步应用待处理的尺寸变化 (与相机过渡同帧, 不闪屏)
      if (pendingResize) {
        const { w, h } = pendingResize; pendingResize = null;
        camera.aspect = w / h; camera.updateProjectionMatrix();
        renderer.setSize(w, h); // updateStyle=true: 同步画布 CSS 尺寸, 否则首屏未就绪时捕获的错误宽度会一直残留导致横向压缩
      }
      // grow
      if (!instant) {
        racks.forEach((g) => {
          const t = (now - growStart - g.userData.delay) / GROW_DUR;
          const p = t <= 0 ? 0 : t >= 1 ? 1 : easeOut(t);
          g.scale.y = Math.max(0.001, p);
          g.position.y = 0; // children carry baseY; scale group from floor
        });
      }
      // grow complete → 先在俯视态显现桥架, 再进入最后的问题点/HUD 弹出阶段
      if (!growReported && now >= growDoneAt) {
        growReported = true;
        // 连续衔接: 生长一结束就让桥架淡入并随即抬升镜头, 中间不留静止空档
        bridgeRevealAt = now + 80;
        cameraLiftAt = now + 240;
        if (instant) { ctrl.auto = true; }
      }
      if (!cameraLiftStarted && now >= cameraLiftAt) {
        cameraLiftStarted = true;
        tweenTo(finalView(), () => {
          revealAt = performance.now() + 200;
          if (compactRef.current) {
            // 机房生成完成后: 顺着当前方位把观测角度下压, 并继续旋转, 增加动态变化
            tweenTo({ phi: 0.9, theta: ctrl.theta + 0.55, radius: cameraRadius(true) * 0.92 }, () => { ctrl.auto = true; }, 2800);
          } else {
            ctrl.auto = true;
          }
        }, 1900);
      }
      if (!revealReported && now >= revealAt) {
        revealReported = true;
        onGrowDoneRef.current && onGrowDoneRef.current();
      }
      if (!bridgeShown && now >= bridgeRevealAt) bridgeShown = true;
      if (!instant) {
        const lo = Math.min(1, Math.max(0, (now - liquidStart) / PH1_LIQUID));
        setGroupOpacity(liquidGroup, lo); // 相位1: 液冷管线淡入
        const bo = bridgeShown ? Math.min(1, Math.max(0, (now - bridgeRevealAt) / 700)) : 0;
        setGroupOpacity(bridgeGroup, bo);
      }
      // 最后一拍: 问题点与 HUD 信息框同步浮出 + 脉冲
      // 最后一拍: 问题点徽章浮出 (3D 锚点, 随机房旋转)
      const so = instant ? 1 : (revealReported ? Math.min(1, Math.max(0, (now - revealAt) / 650)) : 0);
      const MK_REF = cameraRadius(false);   // 参考距离：标记按距离反比缩放 → 屏幕尺寸恒定，放大/漫游不跟随变大
      markerEntries.forEach((mk, i) => {
        const k = 1 + Math.sin(now * 0.005 + i) * 0.16;
        const sf = Math.max(0.18, camera.position.distanceTo(mk.dot.position) / MK_REF);
        mk.dot.scale.set(0.52 * k * sf, 0.52 * k * sf, 1);
        if (mk.badge) { const bh = 1.05 * sf; mk.badge.scale.set(bh * (512 / 150), bh, 1); }
        // 概览缩略图的亮点做闪烁; 详情徽章稳定显示
        const blink = mk.blink ? (0.45 + 0.55 * (0.5 + 0.5 * Math.sin(now * 0.006 + i * 1.7))) : 1;
        mk.mats.forEach((m) => { m.opacity = so * (m.userData.baseOpacity == null ? 1 : m.userData.baseOpacity) * blink; });
      });
      // camera tween / auto-rotate（roam 模式接管相机）
      if (roam.active) {
        const dt = Math.min(0.05, (now - roam.last) / 1000); roam.last = now;
        if (!roam.auto && now - roam.lastManual > 6000) { snapNearest(); roam.auto = true; }
        if (roam.auto && roam.path && roam.path.length > 1) {
          let p0 = roam.path[roam.seg], p1 = roam.path[(roam.seg + 1) % roam.path.length];
          let seg = p1.clone().sub(p0), segLen = seg.length();
          roam.dist += 1.6 * dt;
          let guard = 0;
          while (segLen > 0 && roam.dist >= segLen && guard++ < roam.path.length + 2) { roam.dist -= segLen; roam.seg = (roam.seg + 1) % roam.path.length; p0 = roam.path[roam.seg]; p1 = roam.path[(roam.seg + 1) % roam.path.length]; seg = p1.clone().sub(p0); segLen = seg.length(); }
          const f = segLen > 0 ? roam.dist / segLen : 0;
          roam.pos.copy(p0).lerp(p1, f);
          const heading = Math.atan2(seg.x, seg.z);
          let d = heading - roam.yaw; while (d > Math.PI) d -= 2 * Math.PI; while (d < -Math.PI) d += 2 * Math.PI;
          roam.yaw += d * 0.06;
          roam.pitch += (-0.02 - roam.pitch) * 0.05;
        } else {
          const sp = (roam.keys.sp ? 5.2 : 2.6) * dt;
          const fwd = new THREE.Vector3(Math.sin(roam.yaw), 0, Math.cos(roam.yaw));
          const rgt = new THREE.Vector3(Math.cos(roam.yaw), 0, -Math.sin(roam.yaw));
          if (roam.keys.f) roam.pos.addScaledVector(fwd, sp);
          if (roam.keys.b) roam.pos.addScaledVector(fwd, -sp);
          if (roam.keys.r) roam.pos.addScaledVector(rgt, -sp);
          if (roam.keys.l) roam.pos.addScaledVector(rgt, sp);
        }
        roam.pos.x = Math.max(-FW / 2 + 0.4, Math.min(FW / 2 - 0.4, roam.pos.x));
        roam.pos.z = Math.max(-FD / 2 + 0.4, Math.min(FD / 2 - 0.4, roam.pos.z));
        roam.pos.y = eyeH;
        camera.position.copy(roam.pos);
        const dir = new THREE.Vector3(Math.sin(roam.yaw) * Math.cos(roam.pitch), Math.sin(roam.pitch), Math.cos(roam.yaw) * Math.cos(roam.pitch));
        camera.lookAt(roam.pos.x + dir.x, roam.pos.y + dir.y, roam.pos.z + dir.z);
      } else if (ctrl.goal) {
        const p = Math.min(1, Math.max(0, (now - ctrl.goal.start) / ctrl.goal.duration));
        const e = easeInOutCubic(p);
        ctrl.phi = ctrl.goal.fromPhi + (ctrl.goal.phi - ctrl.goal.fromPhi) * e;
        ctrl.theta = ctrl.goal.fromTheta + (ctrl.goal.theta - ctrl.goal.fromTheta) * e;
        ctrl.radius = ctrl.goal.fromRadius + (ctrl.goal.radius - ctrl.goal.fromRadius) * e;
        applyCam();
        if (p >= 1) {
          const d = ctrl.goal.done; ctrl.goal = null; d && d();
        }
      } else if (ctrl.auto) { autoVel += (0.0016 - autoVel) * 0.03; ctrl.theta += autoVel; applyCam(); }
      else { autoVel = 0; if (!dragging && performance.now() - idleT > 5000) { ctrl.auto = true; } }
      renderer.render(scene, camera);
    }
    // Grow group from floor: set group origin at floor by offsetting children up, then scaling group.y
    racks.forEach((g) => {
      const { mesh, edges, baseY } = g.userData;
      mesh.position.y = baseY; edges.position.y = baseY;
      g.position.y = 0;
    });
    // To scale from bottom, scale the group's y while keeping base at 0: children at y=baseY, group scaled → child world y = baseY*scaleY. Good (bottom stays at 0).
    raf = requestAnimationFrame(frame);
    applyCam();
    renderer.render(scene, camera);   // 同步首帧, 避免 rAF 节流时白屏

    // Resize — 仅记录尺寸, 真正的 setSize 放到渲染帧内同步执行, 避免与相机过渡同时改尺寸导致闪屏
    let pendingResize = null;
    const ro = new ResizeObserver(() => {
      const w = mount.clientWidth, h = mount.clientHeight;
      if (!w || !h) return;
      pendingResize = { w, h };
    });
    ro.observe(mount);

    function applyLayers(layers) {
      const set = new Set(normalizeActiveLayers(layers));
      equipmentGroup.visible = set.has('equipment');
      bridgeGroup.visible = set.has('bridge');
      liquidGroup.visible = set.has('liquid');
      markerEntries.forEach((mk) => {
        const on = set.has(mk.layer);
        if (mk.badge) mk.badge.visible = on;
        mk.dot.visible = on;
        if (mk.stem) mk.stem.visible = on;
      });
    }
    applyLayers(activeLayersRef.current);

    stateRef.current = {
      reset() { const v = finalView(); ctrl.goal = null; ctrl.theta = v.theta; ctrl.phi = v.phi; ctrl.radius = v.radius; ctrl.target.set(0, 1, 0); ctrl.auto = true; applyCam(); },
      toggleAuto() { ctrl.auto = !ctrl.auto; ctrl.goal = null; idleT = performance.now(); return ctrl.auto; },
      setLayers(layers) { activeLayersRef.current = normalizeActiveLayers(layers); applyLayers(activeLayersRef.current); },
      setLayer(layer) { this.setLayers(layer); },
      setCompact(isCompact) {
        compactRef.current = isCompact;
        const v = finalView();
        ctrl.goal = null;
        ctrl.radius = v.radius;
        ctrl.phi = v.phi;
        ctrl.target.set(0, 1, 0);
        applyCam();
      },
      setViewMode(mode) { if (mode === 'roam') startRoam(); else stopRoam(); return mode; },
      toggleRoamAuto() { roam.auto = !roam.auto; if (!roam.auto) roam.lastManual = performance.now(); else snapNearest(); return roam.auto; },
    };

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      dom.removeEventListener('pointerdown', onDown);
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('keydown', kd);
      window.removeEventListener('keyup', ku);
      dom.removeEventListener('wheel', onWheel);
      dom.removeEventListener('pointermove', hover);
      dom.removeEventListener('pointerleave', onLeave);
      scene.traverse((o) => {
        if (o.geometry) o.geometry.dispose();
        if (o.material) { (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => { if (m.map) m.map.dispose(); m.dispose(); }); }
      });
      renderer.dispose();
      if (renderer.domElement.parentNode) renderer.domElement.parentNode.removeChild(renderer.domElement);
    };
  }, [started]);

  return stateRef;
}

function PhysicalTwin3D({ compact = false, instant = false }) {
  const mountRef = useRef3D(null);
  const [stage, setStage] = useState3D(instant ? 'live' : 'cad'); // cad → lay → live
  const [selected, setSelected] = useState3D(null);
  const [openIssueId, setOpenIssueId] = useState3D('cooling-roof');
  const [issueRailOpen, setIssueRailOpen] = useState3D(true);
  const [activeLayers, setActiveLayers] = useState3D(() => [...R3_LAYER_KEYS]);
  const [autoOn, setAutoOn] = useState3D(true);
  const [viewMode, setViewMode] = useState3D('god');   // 详情视图：上帝 / 漫游
  const [roamAuto, setRoamAuto] = useState3D(true);    // 漫游：自动巡航
  const [revealed, setRevealed] = useState3D(instant);
  const [hover, setHover] = useState3D(null); // 悬浮机柜编号
  const noThree = typeof THREE === 'undefined';
  const allLayersOn = isAllLayersActive(activeLayers);

  const toggleLayerOption = (key) => {
    if (key === 'all') {
      setActiveLayers([...R3_LAYER_KEYS]);
      return;
    }
    setActiveLayers((prev) => (
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    ));
  };

  useEffect3D(() => {
    if (noThree) return;
    if (instant) {
      setStage('live'); setRevealed(true);
      return;
    }
    setStage('cad'); setRevealed(false);
    const t1 = setTimeout(() => setStage('lay'), 650);
    const t2 = setTimeout(() => setStage('live'), 1550);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [instant]);

  const sceneApi = useRoomScene(mountRef, {
    onSelect: compact ? null : (item) => {
      if (item && item.__issueId) { setOpenIssueId(item.__issueId); setIssueRailOpen(true); return; }
      setSelected(item);
    },
    onHover: compact ? null : setHover,
    started: stage === 'live' && !noThree,
    compact,
    instant,
    activeLayers: compact ? R3_LAYER_KEYS : activeLayers,
    onGrowDone: () => setRevealed(true),
  });

  if (noThree) {
    return (
      <div className="r3-wrap"><div className="r3-fallback">
        3D 渲染需要 Three.js（CDN）。请检查网络后刷新页面。
      </div></div>
    );
  }

  return (
    <div className={`r3-wrap stage-${stage}${compact ? ' compact' : ' detail'}${!compact && !issueRailOpen ? ' rail-collapsed' : ''}${revealed ? ' revealed' : ''}`}>
      <div ref={mountRef} className="r3-canvas" />

      {!compact && hover && (
        <div
          className={`r3-hover-tip${hover.it.issue ? ' has-issue' : ''}`}
          style={{ left: hover.x + 14, top: hover.y + 14 }}
        >
          <b>{hover.it.tag}</b>
          <span>{hover.it.type}</span>
          {hover.it.issue && <em>{hover.it.status === 'danger' ? '阻塞' : '风险'} · {hover.it.issue}</em>}
        </div>
      )}

      <div className="r3-cad-plane">
        <RoomCadPlan />
      </div>

      <div className="r3-hud r3-hud-tl">
        <div className="r3-badge"><span className="r3-dot live" />D01 一层机房 · 实时孪生</div>
        <div className="r3-kpis">
          {compact ? (
            <React.Fragment>
              <div className="r3-kpi"><b>{ROOM.items.filter((it) => it.kind === 'rack').length}</b><span>机柜位</span></div>
              <div className="r3-kpi"><b>{ROOM.meta.installedRacks || ROOM.items.filter((it) => it.phase === 'installed').length}</b><span>本期上线</span></div>
              <div className="r3-kpi alert"><b>{ROOM_ISSUES.length}</b><span>现场异常</span></div>
            </React.Fragment>
          ) : (
            <React.Fragment>
              <div className="r3-kpi"><b>{ROOM.items.filter((it) => it.kind === 'rack').length}</b><span>机柜位</span></div>
              <div className="r3-kpi"><b>{ROOM.meta.installedRacks || ROOM.items.filter((it) => it.phase === 'installed').length}</b><span>本期</span></div>
              <div className="r3-kpi"><b>{ROOM.items.filter((it) => it.kind === 'cdu').length}</b><span>CDU</span></div>
              <div className="r3-kpi"><b>{ROOM.items.filter((it) => it.kind === 'odf').length}</b><span>ODF</span></div>
              <div className="r3-kpi"><b>{ROOM.meta.fiberTrays || ROOM.bridges.filter((b) => b.layer === 'fiber').length}</b><span>光纤槽</span></div>
              <div className="r3-kpi"><b>{ROOM.liquidLines.length}</b><span>液冷管</span></div>
              <div className="r3-kpi alert"><b>{ROOM_ISSUES.length}</b><span>异常</span></div>
            </React.Fragment>
          )}
        </div>
      </div>

      {!compact && <div className="r3-hud r3-hud-tr">
        <div className="r3-viewseg">
          <button type="button" className={viewMode === 'god' ? 'on' : ''} onClick={() => { setViewMode('god'); sceneApi.current && sceneApi.current.setViewMode('god'); }}>上帝视角</button>
          <button type="button" className={viewMode === 'roam' ? 'on' : ''} onClick={() => { setViewMode('roam'); setRoamAuto(true); sceneApi.current && sceneApi.current.setViewMode('roam'); }}>漫游视角</button>
        </div>
        {viewMode === 'god' && (
          <React.Fragment>
            <button type="button" className="r3-ctl" onClick={() => { const on = sceneApi.current && sceneApi.current.toggleAuto(); setAutoOn(on); }}>
              {autoOn ? '暂停自动旋转' : '开启自动旋转'}
            </button>
            <button type="button" className="r3-ctl" onClick={() => sceneApi.current && sceneApi.current.reset()}>复位视角</button>
          </React.Fragment>
        )}
        {viewMode === 'roam' && (
          <button type="button" className="r3-ctl" onClick={() => { const a = sceneApi.current && sceneApi.current.toggleRoamAuto(); setRoamAuto(a); }}>{roamAuto ? '暂停巡航' : '自动巡航'}</button>
        )}
      </div>}

      {!compact && <div className="r3-hint">{viewMode === 'roam' ? (roamAuto ? '自动巡航中 · 拖拽转视角 · WASD 随时接管' : '手动漫游 · WASD/方向键 移动 · 拖拽转视角 · Shift 加速') : '拖拽旋转 · 滚轮缩放 · 点击机柜查看详情'}</div>}

      {!compact && (
        <div className="r3-layer-switch">
          {[
            ['all', '全部'],
            ['equipment', '机柜/设备'],
            ['bridge', '桥架/光纤'],
            ['liquid', '液冷管线'],
          ].map(([key, label]) => {
            const on = key === 'all' ? allLayersOn : activeLayers.includes(key);
            return (
              <button
                type="button"
                key={key}
                className={on ? 'on' : ''}
                aria-pressed={on}
                onClick={() => toggleLayerOption(key)}
              >
                {label}
              </button>
            );
          })}
        </div>
      )}

      {!compact && (
        <aside className={`r3-issue-rail${issueRailOpen ? '' : ' collapsed'}`}>
          <button
            type="button"
            className="r3-rail-toggle"
            onClick={() => setIssueRailOpen((v) => !v)}
            aria-label={issueRailOpen ? '收起问题栏' : '展开问题栏'}
            title={issueRailOpen ? '收起问题栏' : '展开问题栏'}
          >
            <span>{issueRailOpen ? '收起' : '问题'}</span>
            <b>{issueRailOpen ? '›' : '‹'}</b>
          </button>
          <div className="r3-rail-content">
            <div className="r3-issue-head">
              <div>
                <div className="r3-issue-eyebrow">Physical Twin Findings</div>
                <h3>问题清单</h3>
              </div>
              <span>{ROOM_ISSUES.length}</span>
            </div>
            <div className="r3-issue-scroll">
              {ROOM_ISSUES.map((issue) => {
                const open = openIssueId === issue.id;
                return (
                  <button
                    type="button"
                    key={issue.id}
                    className={`r3-issue-card ${issue.severity}${open ? ' open' : ''}`}
                    onClick={() => setOpenIssueId(open ? null : issue.id)}
                  >
                    <div className="r3-issue-card-top">
                      <span className={`r3-sev ${issue.severity}`}>{issue.severity === 'danger' ? '阻塞' : '风险'}</span>
                      <span className="r3-issue-scope">{issue.scope}</span>
                    </div>
                    <div className="r3-issue-title">{issue.title}</div>
                    <div className="r3-issue-summary">{issue.summary}</div>
                    {open && (
                      <div className="r3-issue-detail">
                        <p>{issue.detail}</p>
                        <div className="r3-issue-impact">
                          <span>影响</span>
                          <b>{issue.impact}</b>
                        </div>
                        <div className="r3-next-title">下一步操作</div>
                        <ol>
                          {issue.next.map((n) => <li key={n}>{n}</li>)}
                        </ol>
                        <div className="r3-issue-actions">
                          <span>定位机柜</span>
                          <span>生成处置单</span>
                        </div>
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
            {selected && (
              <div className="r3-selected-mini">
                <span>当前选中</span>
                <b>{selected.tag}</b>
                <em>{selected.type}</em>
              </div>
            )}
          </div>
        </aside>
      )}
    </div>
  );
}

(function injectRoom3DStyles() {
  if (document.getElementById('r3-styles')) return;
  const s = document.createElement('style');
  s.id = 'r3-styles';
  s.textContent = `
    .r3-wrap{position:relative;width:100%;height:100%;border-radius:inherit;overflow:hidden;background:radial-gradient(130% 130% at 50% 12%,#6b7480 0%,#474f5a 74%)}
    .r3-canvas{position:absolute;inset:0;opacity:0;transition:opacity .6s ease,right .32s cubic-bezier(.16,1,.3,1)}
    .r3-wrap.detail .r3-canvas{right:300px}
    .r3-wrap.detail.rail-collapsed .r3-canvas{right:44px}
    .r3-wrap.stage-live .r3-canvas{opacity:1}
    .r3-wrap.compact .r3-canvas{pointer-events:none}

    /* 问题点标记: 锚点光点 + 连线 + 顶部信息框 */
    .r3-mk-overlay{position:absolute;inset:0;pointer-events:none;z-index:8;opacity:0;transition:opacity .4s ease}
    .r3-mk-overlay.compact{display:none}
    .r3-mk-svg{position:absolute;inset:0;width:100%;height:100%;overflow:visible}
    .r3-mk-line{stroke-width:1.3;stroke-dasharray:3 4;opacity:0;transition:opacity .3s ease}
    .r3-mk-line.sev-danger{stroke:#ff5a6a}
    .r3-mk-line.sev-warn{stroke:#ffb44d}
    .r3-mk-end{opacity:0;transition:opacity .3s ease}
    .r3-mk-end.sev-danger{fill:#ff5a6a;stroke:rgba(255,90,106,.35);stroke-width:4}
    .r3-mk-end.sev-warn{fill:#ffb44d;stroke:rgba(255,180,77,.35);stroke-width:4}
    .r3-mk-cards{position:absolute;top:12px;left:0;right:0;display:flex;justify-content:center;flex-wrap:wrap;gap:8px;padding:0 18px}
    .r3-mk-card{pointer-events:auto;cursor:pointer;display:flex;align-items:flex-start;gap:8px;text-align:left;max-width:200px;padding:7px 11px;border-radius:10px;background:rgba(255,255,255,0.86);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.92);box-shadow:0 8px 24px rgba(60,80,110,.18);font-family:inherit;transition:transform .15s ease,border-color .15s ease}
    .r3-mk-card:hover{transform:translateY(-2px)}
    .r3-mk-card i{margin-top:3px;width:9px;height:9px;border-radius:50%;flex:none}
    .r3-mk-card.sev-danger{border-color:rgba(255,90,106,.4)}
    .r3-mk-card.sev-danger i{background:#ff5a6a;box-shadow:0 0 8px rgba(255,90,106,.85)}
    .r3-mk-card.sev-warn{border-color:rgba(255,180,77,.38)}
    .r3-mk-card.sev-warn i{background:#ffb44d;box-shadow:0 0 8px rgba(255,180,77,.7)}
    .r3-mk-txt{display:flex;flex-direction:column;gap:1px;min-width:0}
    .r3-mk-tag{font-family:var(--font-mono);font-size:10px;font-weight:700;color:#5b6b7c;letter-spacing:.5px}
    .r3-mk-card b{font-size:11.5px;font-weight:600;color:#26313d;line-height:1.25}
    .r3-mk-card em{font-style:normal;font-size:9.5px;color:#8593a3;line-height:1.2;margin-top:1px}
    .r3-fallback{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#64748b;font-size:13px;padding:24px;text-align:center}

    /* 机柜悬浮编号 tooltip */
    .r3-hover-tip{position:fixed;z-index:20;pointer-events:none;display:flex;flex-direction:column;gap:2px;padding:7px 10px;border-radius:9px;background:rgba(255,255,255,0.92);border:1px solid rgba(255,255,255,0.92);box-shadow:0 8px 24px rgba(60,80,110,.2);backdrop-filter:blur(10px);max-width:230px;animation:r3TipIn .12s ease both}
    @keyframes r3TipIn{from{opacity:0;transform:translateY(3px)}to{opacity:1;transform:none}}
    .r3-hover-tip b{font-size:13px;font-weight:700;color:#26313d;font-family:var(--font-mono);letter-spacing:.4px;line-height:1.1}
    .r3-hover-tip span{font-size:10.5px;color:#5b6b7c;line-height:1.3}
    .r3-hover-tip em{font-size:10.5px;font-style:normal;color:#dc2626;line-height:1.35;margin-top:3px;padding-top:4px;border-top:1px dashed rgba(60,80,110,.2)}
    .r3-hover-tip.has-issue{border-color:rgba(220,38,38,.4)}

    /* CAD 平面图: 躺下并放大对齐 3D 地面 (不变暗), 3D 接管时交叉淡出 */
    .r3-cad-plane{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;padding:24px;perspective:1200px;pointer-events:none;opacity:1;transition:right .32s cubic-bezier(.16,1,.3,1)}
    .r3-wrap.detail .r3-cad-plane{right:300px}
    .r3-wrap.detail.rail-collapsed .r3-cad-plane{right:44px}
    .r3-cad-svg{max-width:88%;max-height:94%;transform-origin:50% 56%;transform:rotateX(0deg) scale(1);opacity:1;transition:transform .9s cubic-bezier(.42,0,.16,1);filter:drop-shadow(0 12px 30px rgba(60,80,110,.28))}
    .r3-wrap.compact .r3-cad-plane{padding:10px}
    .r3-wrap.compact .r3-cad-svg{max-width:106%;max-height:96%}
    .r3-wrap.stage-lay .r3-cad-svg{transform:rotateX(56deg) scale(1.32)}
    .r3-wrap.stage-live .r3-cad-svg{transform:rotateX(56deg) scale(1.32)}
    .r3-wrap.stage-live .r3-cad-plane{opacity:0;transition:opacity .5s ease}

    /* HUD — 最后一拍与问题点同步显现 (去掉 blur 滤镜过渡避免掉帧) */
    .r3-hud{position:absolute;z-index:6;opacity:0;transform:translateY(-6px);transition:opacity .5s cubic-bezier(.16,1,.3,1),transform .5s cubic-bezier(.16,1,.3,1)}
    .r3-wrap.revealed .r3-hud{opacity:1;transform:none}
    .r3-hud-tl{top:14px;left:16px;display:flex;flex-direction:column;gap:10px}
    .r3-hud-tr{top:14px;right:16px;display:flex;gap:8px}
    .r3-wrap.detail .r3-hud-tr{right:316px}
    .r3-wrap.detail.rail-collapsed .r3-hud-tr{right:60px}
    .r3-wrap.compact .r3-hud-tl{top:10px;left:12px;gap:7px}
    .r3-badge{display:inline-flex;align-items:center;gap:7px;padding:5px 11px;border-radius:999px;background:rgba(255,255,255,0.78);border:1px solid rgba(255,255,255,0.9);color:#3a4654;font-size:11.5px;font-family:var(--font-mono);letter-spacing:.3px;backdrop-filter:blur(12px);box-shadow:0 6px 20px rgba(60,80,110,.12)}
    .r3-wrap.compact .r3-badge{font-size:10.5px;padding:4px 9px}
    .r3-dot{width:7px;height:7px;border-radius:50%}
    .r3-dot.live{background:#0f9d58;box-shadow:0 0 8px #0f9d58;animation:r3pulse 2s ease-out infinite}
    @keyframes r3pulse{0%{box-shadow:0 0 0 0 rgba(15,157,88,.5)}100%{box-shadow:0 0 0 7px rgba(15,157,88,0)}}
    .r3-kpis{display:flex;gap:7px}
    .r3-wrap.compact .r3-kpis{gap:5px;flex-wrap:wrap;max-width:230px}
    .r3-kpi{display:flex;flex-direction:column;gap:1px;padding:6px 11px;border-radius:8px;background:rgba(255,255,255,0.7);border:1px solid rgba(255,255,255,0.88);backdrop-filter:blur(12px);box-shadow:0 6px 18px rgba(60,80,110,.1)}
    .r3-wrap.compact .r3-kpi{padding:5px 8px}
    .r3-kpi b{font-size:15px;font-weight:700;color:#2b3a48;line-height:1.1;font-family:var(--font-mono)}
    .r3-wrap.compact .r3-kpi b{font-size:13px}
    .r3-kpi span{font-size:9.5px;color:#8593a3;letter-spacing:.04em}
    .r3-wrap.compact .r3-kpi span{font-size:9px}
    .r3-kpi.alert b{color:#dc2626}
    .r3-ctl{padding:6px 12px;border-radius:7px;background:rgba(255,255,255,0.78);border:1px solid rgba(255,255,255,0.9);color:#46535f;font-size:11.5px;cursor:pointer;font-family:var(--font-sans);transition:all .14s;backdrop-filter:blur(12px);box-shadow:0 6px 18px rgba(60,80,110,.1)}
    .r3-ctl:hover{border-color:#2b71d8;color:#2b71d8}
    .r3-viewseg{display:flex;gap:2px;padding:3px;border-radius:8px;background:rgba(255,255,255,0.9);border:1px solid rgba(255,255,255,0.95);backdrop-filter:blur(12px);box-shadow:0 6px 18px rgba(20,28,40,.2)}
    .r3-viewseg button{padding:5px 12px;border:0;border-radius:6px;background:transparent;color:#3f4b57;font-size:11.5px;font-weight:650;cursor:pointer;font-family:var(--font-sans);transition:background .15s,color .15s}
    .r3-viewseg button.on{background:#2b71d8;color:#fff;box-shadow:0 2px 8px rgba(43,113,216,.32)}
    .r3-viewseg button:hover:not(.on){color:#2b3a48}

    .r3-hint{position:absolute;bottom:14px;left:50%;transform:translate(-50%,8px) scale(.98);z-index:6;font-size:11px;color:#5b6b7c;background:rgba(255,255,255,0.78);padding:5px 14px;border-radius:999px;border:1px solid rgba(255,255,255,0.9);backdrop-filter:blur(12px);box-shadow:0 6px 18px rgba(60,80,110,.1);opacity:0;transition:opacity .55s cubic-bezier(.16,1,.3,1) .12s,transform .55s cubic-bezier(.16,1,.3,1) .12s;white-space:nowrap}
    .r3-wrap.detail .r3-hint{left:calc((100% - 300px)/2)}
    .r3-wrap.detail.rail-collapsed .r3-hint{left:calc((100% - 44px)/2)}
    .r3-wrap.revealed .r3-hint{opacity:1;transform:translate(-50%,0) scale(1)}

    .r3-layer-switch{position:absolute;z-index:7;left:16px;bottom:46px;display:flex;gap:6px;padding:5px;border-radius:10px;background:rgba(255,255,255,0.74);border:1px solid rgba(255,255,255,0.9);backdrop-filter:blur(14px);box-shadow:0 8px 24px rgba(60,80,110,.12);opacity:0;transform:translateY(8px);transition:opacity .55s cubic-bezier(.16,1,.3,1) .16s,transform .55s cubic-bezier(.16,1,.3,1) .16s}
    .r3-wrap.revealed .r3-layer-switch{opacity:1;transform:none}
    .r3-layer-switch button{height:28px;padding:0 10px;border-radius:7px;border:1px solid transparent;background:transparent;color:#5b6b7c;font-size:11.5px;font-weight:650;font-family:var(--font-sans);cursor:pointer;transition:background .15s,border-color .15s,color .15s}
    .r3-layer-switch button:hover{color:#2b3a48;background:rgba(140,160,180,.14)}
    .r3-layer-switch button.on{color:#2b71d8;background:rgba(43,113,216,.12);border-color:rgba(43,113,216,.28);box-shadow:inset 0 0 0 1px rgba(43,113,216,.1)}

    .r3-issue-rail{position:absolute;top:0;right:0;bottom:0;z-index:8;width:300px;background:rgba(255,255,255,0.82);backdrop-filter:blur(18px) saturate(1.2);border-left:1px solid rgba(255,255,255,0.9);box-shadow:-18px 0 42px rgba(60,80,110,.14);display:flex;flex-direction:column;color:#46535f;transition:width .32s cubic-bezier(.16,1,.3,1),box-shadow .32s cubic-bezier(.16,1,.3,1)}
    .r3-issue-rail.collapsed{width:44px;box-shadow:-10px 0 24px rgba(60,80,110,.1)}
    .r3-rail-toggle{height:38px;margin:10px;border:1px solid rgba(140,160,180,.24);border-radius:9px;background:rgba(255,255,255,0.7);color:#46535f;display:flex;align-items:center;justify-content:center;gap:7px;cursor:pointer;font-family:var(--font-sans);font-size:11.5px;font-weight:650;transition:border-color .16s,background .16s,color .16s}
    .r3-rail-toggle:hover{border-color:rgba(43,113,216,.4);background:#fff;color:#2b71d8}
    .r3-rail-toggle b{font-size:16px;line-height:1;font-weight:500;color:#8593a3}
    .r3-issue-rail.collapsed .r3-rail-toggle{width:24px;height:84px;margin:10px auto;writing-mode:vertical-rl;gap:5px;padding:0}
    .r3-issue-rail.collapsed .r3-rail-toggle b{font-size:14px}
    .r3-rail-content{display:flex;flex:1;min-height:0;flex-direction:column;opacity:1;transition:opacity .18s ease .08s}
    .r3-issue-rail.collapsed .r3-rail-content{opacity:0;pointer-events:none;transition-delay:0s}
    .r3-issue-head{display:flex;align-items:flex-start;justify-content:space-between;padding:16px 16px 12px;border-bottom:1px solid rgba(60,80,110,.1)}
    .r3-issue-eyebrow{font-size:9.5px;color:#8593a3;font-family:var(--font-mono);letter-spacing:.08em;text-transform:uppercase;margin-bottom:4px}
    .r3-issue-head h3{margin:0;font-size:15px;font-weight:700;color:#26313d}
    .r3-issue-head>span{min-width:25px;height:25px;display:grid;place-items:center;border-radius:999px;background:rgba(220,38,38,.1);border:1px solid rgba(220,38,38,.28);color:#dc2626;font-size:12px;font-family:var(--font-mono);font-weight:700}
    .r3-issue-scroll{flex:1;min-height:0;overflow:auto;padding:12px;display:flex;flex-direction:column;gap:10px}
    .r3-issue-scroll::-webkit-scrollbar{width:6px}
    .r3-issue-scroll::-webkit-scrollbar-thumb{background:rgba(60,80,110,.22);border-radius:999px}
    .r3-issue-card{width:100%;text-align:left;border:1px solid rgba(60,80,110,.12);background:rgba(255,255,255,0.7);color:inherit;border-radius:12px;padding:12px;cursor:pointer;font-family:var(--font-sans);transition:border-color .18s,background .18s,transform .18s,box-shadow .18s}
    .r3-issue-card:hover{border-color:rgba(43,113,216,.3);background:#fff;transform:translateY(-1px);box-shadow:0 8px 22px rgba(60,80,110,.1)}
    .r3-issue-card.open{border-color:rgba(43,113,216,.4);box-shadow:0 10px 28px rgba(60,80,110,.14)}
    .r3-issue-card.danger.open{border-color:rgba(220,38,38,.42)}
    .r3-issue-card.warn.open{border-color:rgba(217,119,6,.42)}
    .r3-issue-card-top{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px}
    .r3-sev{font-size:10px;font-weight:700;padding:2px 7px;border-radius:999px}
    .r3-sev.danger{background:rgba(220,38,38,.12);color:#b91c1c}
    .r3-sev.warn{background:rgba(217,119,6,.14);color:#9a5b08}
    .r3-issue-scope{font-size:10.5px;color:#8593a3;white-space:nowrap}
    .r3-issue-title{font-size:13px;font-weight:700;color:#26313d;margin-bottom:6px}
    .r3-issue-summary{font-size:11.5px;line-height:1.55;color:#5b6b7c}
    .r3-issue-detail{margin-top:11px;padding-top:11px;border-top:1px dashed rgba(60,80,110,.18);animation:r3IssueOpen .24s cubic-bezier(.16,1,.3,1) both}
    @keyframes r3IssueOpen{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:none}}
    .r3-issue-detail p{margin:0 0 10px;font-size:11.5px;line-height:1.6;color:#46535f}
    .r3-issue-impact{display:flex;flex-direction:column;gap:4px;padding:8px 9px;border-radius:8px;background:rgba(140,160,180,.1);border:1px solid rgba(60,80,110,.1);margin-bottom:10px}
    .r3-issue-impact span,.r3-next-title{font-size:9.5px;color:#8593a3;text-transform:uppercase;letter-spacing:.06em;font-weight:700}
    .r3-issue-impact b{font-size:11.5px;line-height:1.45;color:#2b3a48;font-weight:600}
    .r3-next-title{margin-bottom:5px}
    .r3-issue-detail ol{margin:0 0 11px;padding-left:17px;color:#46535f;font-size:11.5px;line-height:1.6}
    .r3-issue-actions{display:flex;gap:7px;flex-wrap:wrap}
    .r3-issue-actions span{display:inline-flex;align-items:center;justify-content:center;height:26px;padding:0 9px;border-radius:7px;background:rgba(43,113,216,.1);border:1px solid rgba(43,113,216,.22);color:#2b71d8;font-size:11px;font-weight:650}
    .r3-selected-mini{flex-shrink:0;margin:0 12px 12px;padding:10px 12px;border-radius:10px;background:rgba(255,255,255,0.8);border:1px solid rgba(60,80,110,.12);display:flex;flex-direction:column;gap:2px}
    .r3-selected-mini span{font-size:9.5px;color:#8593a3;text-transform:uppercase;letter-spacing:.06em}
    .r3-selected-mini b{font-size:13px;color:#26313d;font-family:var(--font-mono)}
    .r3-selected-mini em{font-size:11px;color:#5b6b7c;font-style:normal}

    .r3-card{position:absolute;right:16px;bottom:16px;z-index:7;width:240px;padding:14px 15px;border-radius:12px;background:rgba(255,255,255,0.86);border:1px solid rgba(255,255,255,0.92);backdrop-filter:blur(14px);box-shadow:0 12px 32px rgba(60,80,110,.18);animation:r3cardIn .25s cubic-bezier(.16,1,.3,1) both}
    @keyframes r3cardIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
    .r3-card-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px}
    .r3-card-tag{font-size:15px;font-weight:700;color:#26313d;font-family:var(--font-mono)}
    .r3-card-st{font-size:10px;font-weight:600;padding:2px 8px;border-radius:999px}
    .r3-card-st.ok{background:rgba(15,157,88,.14);color:#0a7d46}
    .r3-card-st.warn{background:rgba(217,119,6,.14);color:#9a5b08}
    .r3-card-st.danger{background:rgba(220,38,38,.12);color:#b91c1c}
    .r3-card-type{font-size:11.5px;color:#5b6b7c;margin-bottom:10px}
    .r3-card-meta{display:flex;gap:18px;margin-bottom:10px}
    .r3-card-meta>div{display:flex;flex-direction:column;gap:2px}
    .r3-card-meta span{font-size:9.5px;color:#8593a3;text-transform:uppercase;letter-spacing:.04em}
    .r3-card-meta b{font-size:12px;color:#2b3a48;font-family:var(--font-mono);font-weight:600}
    .r3-card-issue{font-size:11px;line-height:1.5;padding:7px 9px;border-radius:7px}
    .r3-card-issue.danger{background:rgba(220,38,38,.1);color:#b91c1c;border:1px solid rgba(220,38,38,.3)}
    .r3-card-issue.warn{background:rgba(217,119,6,.1);color:#9a5b08;border:1px solid rgba(217,119,6,.3)}
  `;
  document.head.appendChild(s);
})();

export { PhysicalTwin3D };
