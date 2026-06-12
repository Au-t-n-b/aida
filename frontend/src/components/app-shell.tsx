'use client';

import React, { useState, useEffect, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import Link from '@/compat/link';
import { useLogout } from '@/lib/use-logout';
import { useCurrentProject } from '@/lib/current-project';
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
  roles: ProjectRoleChip[];
};
const PROJECT_LIST_MINI: ProjectMini[] = [
  {
    id: 'K1903', name: '京东三期',
    roles: [
      { role: 'PD',  name: '李伟' },
      { role: 'TD',  name: '何博' },
      { role: 'PCM', name: '王婷' },
      { role: 'OCC', name: '黎芳' },
    ],
  },
  {
    id: 'A1',    name: 'A1 智算集群一期',
    roles: [
      { role: 'PD',  name: '李伟' },
      { role: 'TD',  name: '王明' },
      { role: 'TL',  name: '调试组 K' },
    ],
  },
  {
    id: 'B2',    name: 'B2 智算中心',
    roles: [
      { role: 'PD',  name: '李伟' },
      { role: 'TD',  name: '赵丹' },
      { role: 'TL',  name: '施工队 07' },
    ],
  },
  {
    id: 'C3',    name: 'C3 算力底座扩容',
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
  const navigate = useNavigate();
  const doLogout = useLogout();
  const { project, selectProject } = useCurrentProject();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [projOpen, setProjOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const unread = WELINK_MSGS.length;
  const currentId = project?.id ?? PROJECT_LIST_MINI[0]!.id;
  const currentName = project?.name
    ?? PROJECT_LIST_MINI.find((p) => p.id === currentId)?.name
    ?? PROJECT_LIST_MINI[0]!.name;

  const switchProject = (p: (typeof PROJECT_LIST_MINI)[number]) => {
    selectProject({ id: p.id, name: p.name });
    setProjOpen(false);
    navigate('/cockpit');
  };

  return (
    <header className="topbar">
      {/* 项目下拉 · G-3 · 当前项目右侧紧贴展示 PD/TD/PCM 多角色 chip */}
      <div className="topbar-project" onClick={() => setProjOpen(o => !o)}>
        <span className="topbar-project-name">{currentName}</span>
        <span className="topbar-project-caret">▾</span>
        {projOpen && (
          <div className="topbar-project-pop" onMouseLeave={() => setProjOpen(false)}>
            {PROJECT_LIST_MINI.map(p => (
              <button
                key={p.id}
                type="button"
                className={`topbar-project-row${p.id === currentId ? ' on' : ''}`}
                onClick={() => switchProject(p)}
              >
                <span className="topbar-project-row-name">{p.name}</span>
                {p.id === currentId && <span className="topbar-project-check">✓</span>}
              </button>
            ))}
            <Link href="/landing" className="topbar-project-row" onClick={() => setProjOpen(false)}>
              <span className="topbar-project-row-name">全部项目…</span>
            </Link>
          </div>
        )}
      </div>

      <div className="topbar-spacer" />

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
              <button
                type="button"
                className="topbar-project-row"
                style={{ width: '100%', border: 'none', background: 'none', cursor: 'pointer', textAlign: 'left' }}
                onClick={() => {
                  setUserOpen(false);
                  void doLogout();
                }}
              >
                <span>退出登录</span>
                <span style={{ marginLeft: 'auto', color: 'var(--c-text-muted)' }}>⏎</span>
              </button>
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
  const { project } = useCurrentProject();
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
        <strong>DEMO</strong> · {project?.id ?? '—'} · 智算 Q3
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
