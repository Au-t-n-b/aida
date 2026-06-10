'use client';

import React, { useState, useEffect, useRef, type ReactNode } from 'react';
import Link from '@/compat/link';
import { SYSTEM_INTEGRATIONS } from '../data/journey-data';
import { LeftNavFdy } from './left-nav-fdy';
type AppShellProps = {
  children: ReactNode;
  breadcrumbs?: string[];
  withClaw?: boolean;
  clawRail?: ReactNode;
};
type TopBarProps = { breadcrumbs?: string[] };

/* ── tiny inline SVG glyphs matching aida-delivery/data.jsx Icon set ── */
const IcBell = () => (
  <svg width={14} height={14} viewBox="0 0 14 14" fill="none">
    <path d="M7 2 C9 2 10.5 3.5 10.5 5.5 L10.5 8 L12 10 L2 10 L3.5 8 L3.5 5.5 C3.5 3.5 5 2 7 2 Z" stroke="currentColor" strokeWidth="1" fill="none" />
    <path d="M5.5 11.5 C5.5 12.5 6.2 13 7 13 C7.8 13 8.5 12.5 8.5 11.5" stroke="currentColor" strokeWidth="1" fill="none" />
  </svg>
);
/* ── 全局系统状态徽章 ──
 * 会议结论"每个模块加断网灯"的全局版：聚合 8 个上游/下游集成的健康度。
 * - overall=ok:   绿点 · "系统在线"
 * - overall=warn: 黄点 · "1 项降级"
 * - overall=down: 红点闪烁 · "X 项离线"
 * 点击展开下拉，逐项显示集成名称 / 方向 / 时延 / 状态。
 */
function SystemStatusBadge() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (ref.current && e.target instanceof Node && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [open]);

  const downs = SYSTEM_INTEGRATIONS.filter(i => i.state === 'down');
  const warns = SYSTEM_INTEGRATIONS.filter(i => i.state === 'warn');
  const overall = downs.length ? 'down' : warns.length ? 'warn' : 'ok';
  const label = overall === 'down' ? `${downs.length} 项离线` : overall === 'warn' ? `${warns.length} 项降级` : '系统在线';
  const live = SYSTEM_INTEGRATIONS.filter(i => i.state === 'live').length;

  return (
    <div className="sys-badge-wrap" ref={ref}>
      <button className={`sys-badge sys-${overall}`} onClick={() => setOpen(v => !v)} title="点击查看 8 个上游/下游集成的健康度">
        <span className="sys-dot" />
        <span className="sys-text">{label}</span>
        <span className="sys-counts">{live} / {SYSTEM_INTEGRATIONS.length}</span>
      </button>
      {open && (
        <div className="sys-pop">
          <div className="sys-pop-head">
            <div>
              <div className="sys-pop-title">系统集成监控</div>
              <div className="sys-pop-sub">{SYSTEM_INTEGRATIONS.length} 个接入 · 上游 6 / 下游 1 / 双向 1 · 实时心跳</div>
            </div>
            <Link href="/admin" className="sys-pop-link">前往系统级配置 →</Link>
          </div>
          <div className="sys-pop-list">
            {SYSTEM_INTEGRATIONS.map(s => (
              <div key={s.id} className={`sys-row sys-${s.state}`}>
                <span className={`sys-row-dot sys-${s.state}`} />
                <div className="sys-row-meta">
                  <div className="sys-row-name">
                    <span>{s.name}</span>
                    <span className="sys-row-dir">{s.dir}</span>
                  </div>
                  <div className="sys-row-desc">{s.desc}</div>
                </div>
                <div className="sys-row-lat">{s.latencyMs} ms</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── TopBar ── */
/* 5.25 M-022 · WeLink 通知 drawer (N-5)
 * 5.25 反复强调"会通过 WeLink 通知"，5.27 早会也提
 * 红点点击 → 右侧 drawer，消息流分类 */
const WELINK_MSGS = [
  { id: 'W-001', type: 'risk',     ts: '11:42', from: 'AIDA',     title: 'B2 配电延期 9 天 · 已置顶到风险预警' },
  { id: 'W-002', type: 'contract', ts: '10:25', from: '陈卓 · 合同系统', title: 'CON-K1903-001 签署完成 · LLD 待补' },
  { id: 'W-003', type: 'change',   ts: '09:08', from: 'PD 李伟',   title: 'CHG-2026-002 顺延 7 天 · 待审批' },
  { id: 'W-004', type: 'invite',   ts: '昨天',  from: 'OCC 黎芳',  title: '"项目 K1903 数据出境复核" 会议邀请' },
  { id: 'W-005', type: 'risk',     ts: '昨天',  from: 'AIDA',     title: 'ConnectX-7 数量冲突 · 已自动登记设计风险' },
];
const WELINK_TONE = {
  risk:     { tone: 'red',    label: '风险' },
  contract: { tone: 'blue',   label: '合同' },
  change:   { tone: 'amber',  label: '变更' },
  invite:   { tone: 'violet', label: '会议' },
};

/* TopBar 项目下拉数据 · 简化为「项目下拉 + 铃铛 + 头像」3 元素
 * G-3 · 每个项目展示 PD / TD / PCM 多角色 chip，让切换时一眼看到协作关系 */
type ProjectRoleChip = { role: 'PD' | 'TD' | 'PCM' | 'TL' | 'OCC'; name: string };
type ProjectMini = {
  id: string;
  name: string;
  current: boolean;
  roles: ProjectRoleChip[];
};
const PROJECT_LIST_MINI: ProjectMini[] = [
  {
    id: 'K1903', name: '京东三期', current: true,
    roles: [
      { role: 'PD',  name: '李伟' },
      { role: 'TD',  name: '何博' },
      { role: 'PCM', name: '王婷' },
      { role: 'OCC', name: '黎芳' },
    ],
  },
  {
    id: 'A1',    name: 'A1 智算集群一期', current: false,
    roles: [
      { role: 'PD',  name: '李伟' },
      { role: 'TD',  name: '王明' },
      { role: 'TL',  name: '调试组 K' },
    ],
  },
  {
    id: 'B2',    name: 'B2 智算中心', current: false,
    roles: [
      { role: 'PD',  name: '李伟' },
      { role: 'TD',  name: '赵丹' },
      { role: 'TL',  name: '施工队 07' },
    ],
  },
  {
    id: 'C3',    name: 'C3 算力底座扩容', current: false,
    roles: [
      { role: 'PD',  name: '周晗' },
      { role: 'TD',  name: '王明' },
    ],
  },
];

const ROLE_CHIP_TONE: Record<ProjectRoleChip['role'], string> = {
  PD:  'amber',
  TD:  'blue',
  PCM: 'violet',
  TL:  'green',
  OCC: 'gray',
};

export function TopBar({ breadcrumbs: _breadcrumbs = [] }: TopBarProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [projOpen, setProjOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const unread = WELINK_MSGS.length;
  const current = PROJECT_LIST_MINI.find((p) => p.current) ?? PROJECT_LIST_MINI[0]!;
  return (
    <header className="topbar">
      {/* 项目下拉 · G-3 · 当前项目右侧紧贴展示 PD/TD/PCM 多角色 chip */}
      <div className="topbar-project" onClick={() => setProjOpen(o => !o)}>
        <span className="topbar-project-name">{current.name}</span>
        <span className="topbar-project-caret">▾</span>
        {projOpen && (
          <div className="topbar-project-pop" onMouseLeave={() => setProjOpen(false)}>
            {PROJECT_LIST_MINI.map(p => (
              <Link key={p.id} href="/landing" className={`topbar-project-row${p.current ? ' on' : ''}`}>
                <span className="topbar-project-row-name">{p.name}</span>
                {p.current && <span className="topbar-project-check">✓</span>}
              </Link>
            ))}
          </div>
        )}
      </div>

      <div className="topbar-spacer" />
      <SystemStatusBadge />

      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <button
          onClick={() => setDrawerOpen(true)}
          title={`WeLink 通知 · ${unread} 未读`}
          style={{ display: 'grid', placeItems: 'center', width: 30, height: 30, borderRadius: 6, background: 'none', cursor: 'pointer', color: 'var(--c-text-muted)', position: 'relative', border: 'none' }}
        >
          <IcBell />
          {unread > 0 && (
            <span style={{ position: 'absolute', top: 4, right: 4, minWidth: 14, height: 14, padding: '0 3px', borderRadius: 7, background: '#dc2626', border: '1.5px solid var(--c-surface)', color: '#fff', fontSize: 9, fontWeight: 700, display: 'grid', placeItems: 'center', fontFamily: 'var(--font-mono)' }}>
              {unread}
            </span>
          )}
        </button>
        <div style={{ position: 'relative' }}>
          <div className="user-chip" onClick={() => setUserOpen(o => !o)}>
            <div className="av">HE</div>
            <span>何博</span>
            <span className="topbar-project-caret">▾</span>
          </div>
          {userOpen && (
            <div
              className="topbar-project-pop"
              style={{ left: 'auto', right: 0, minWidth: 200 }}
              onMouseLeave={() => setUserOpen(false)}
            >
              <div className="topbar-project-pop-head">何博 · 交付经理 · 智算 Q3</div>
              <Link href="/login" className="topbar-project-row" onClick={() => setUserOpen(false)}>
                <span>退出登录</span>
                <span style={{ marginLeft: 'auto', color: 'var(--c-text-muted)' }}>⏎</span>
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* N-5 · WeLink 通知 drawer */}
      {drawerOpen && (
        <div className="welink-drawer-mask" onClick={() => setDrawerOpen(false)}>
          <aside className="welink-drawer" onClick={e => e.stopPropagation()}>
            <div className="welink-drawer-head">
              <span>WeLink 通知 · {WELINK_MSGS.length} 条</span>
              <button onClick={() => setDrawerOpen(false)} className="welink-close">✕</button>
            </div>
            <div className="welink-list">
              {WELINK_MSGS.map(m => {
                const t = WELINK_TONE[m.type as keyof typeof WELINK_TONE] || { tone: 'gray', label: m.type };
                return (
                  <div key={m.id} className="welink-msg">
                    <div className="welink-msg-head">
                      <span className={`welink-msg-tag tone-${t.tone}`}>{t.label}</span>
                      <span className="welink-msg-from">{m.from}</span>
                      <span className="welink-msg-ts">{m.ts}</span>
                    </div>
                    <div className="welink-msg-body">{m.title}</div>
                  </div>
                );
              })}
            </div>
            <div className="welink-drawer-foot">
              所有跨系统通知由 WeLink 统一推送。
            </div>
          </aside>
        </div>
      )}
    </header>
  );
}

function DemoWatermark() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (localStorage.getItem('aida:demo-watermark-hidden') === '1') return;

    const sync = () => {
      const blocked = !!document.querySelector('.action-footer');
      setVisible(!blocked);
    };
    sync();
    const obs = new MutationObserver(sync);
    obs.observe(document.body, { childList: true, subtree: true });
    return () => obs.disconnect();
  }, []);

  if (!visible) return null;

  const dismiss = () => {
    setVisible(false);
    try { localStorage.setItem('aida:demo-watermark-hidden', '1'); } catch { /* ignore */ }
  };

  return (
    <button
      type="button"
      className="aida-demo-watermark"
      title="演示版 · 数据均为 mock · 单击关闭"
      onClick={dismiss}
    >
      <span className="aida-demo-dot" />
      <span className="aida-demo-text">
        <strong>DEMO</strong> · K1903 · 智算 Q3
      </span>
    </button>
  );
}

/* ── AppShell — full three-column layout
 * 5.25 L02:47:13 拍板：「对话框还是放左边，大家习惯左边」
 * 5.27 SVG 多个面板也都把「会话框 / 消息」画在左侧
 * 默认 clawSide = 'left'，会话栏固定左侧（切换按钮已移除）
 * 该偏好仍可从 localStorage 读取（历史用户） */
export function AppShell({ children, breadcrumbs = [], withClaw = false, clawRail }: AppShellProps) {
  const [navCollapsed, setNavCollapsed] = useState(false);
  const [clawSide, setClawSide] = useState('left'); // 'left' | 'right'

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const saved = localStorage.getItem('aida:claw-side');
    if (saved === 'left' || saved === 'right') setClawSide(saved);
  }, []);

  const swapSide = () => {
    setClawSide(s => {
      const next = s === 'left' ? 'right' : 'left';
      try { localStorage.setItem('aida:claw-side', next); } catch { /* ignore */ }
      return next;
    });
  };

  const setClawWidth = (w: number) => {
    if (typeof document !== 'undefined') {
      document.documentElement.style.setProperty('--claw-w', `${w}px`);
    }
  };

  const enrichedClawRail =
    clawRail && React.isValidElement<{ onSwap?: () => void; onResize?: (w: number) => void }>(clawRail)
      ? React.cloneElement(clawRail, { onSwap: swapSide, onResize: setClawWidth })
      : clawRail;

  return (
    <div className={`app-shell claw-${clawSide}${navCollapsed ? ' nav-collapsed' : ''}${!withClaw ? ' no-claw' : ''}`}>
      <LeftNavFdy collapsed={navCollapsed} onToggle={() => setNavCollapsed(c => !c)} />
      <div className="app-workspace">
        <TopBar breadcrumbs={breadcrumbs} />
        <div className="app-body">
          {withClaw && clawSide === 'left' && enrichedClawRail}
          <div className="app-main">
            {children}
          </div>
          {withClaw && clawSide === 'right' && enrichedClawRail}
        </div>
      </div>
      <DemoWatermark />
    </div>
  );
}

export { LeftNavFdy, SideNav } from './left-nav-fdy';
