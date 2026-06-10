'use client';

/* AdminShell · 系统管理员专属外壳
 *
 * G-1 · 与项目空间分离：
 *   - 不挂左侧业务侧导（项目孪生 / 早期介入 / 交付预案 / 项目管理 / 交付作业 / 项目文档）
 *   - 不挂 ClawRail（管理员只做接通 + 治理，不需要 AI 助手）
 *   - 顶栏右侧不显示当前项目，改为「管理员身份 · 退出」
 *   - 视觉用偏冷的中性灰来区分项目空间（暗黑导航 + 蓝色品牌）
 *
 * 内部仍使用 admin.tsx 的 5 个 tab：系统集成 / 角色权限 / 数据隐私 / AI 路由 / 审计。
 */

import Link from '@/compat/link';
import { usePathname } from '@/compat/navigation';
import type { ReactNode } from 'react';

type AdminNavItem = { key: string; label: string; href: string; sub?: string };
const ADMIN_NAV: AdminNavItem[] = [
  { key: 'integration', label: '系统集成',   href: '/admin?tab=integration', sub: '上游 / 下游接入' },
  { key: 'roles',       label: '角色与权限', href: '/admin?tab=roles',       sub: 'PD / TD / TL / OCC' },
  { key: 'privacy',     label: '数据隐私',   href: '/admin?tab=privacy',     sub: '出境 / 脱敏 / 闸门' },
  { key: 'ai',          label: 'AI 路由',    href: '/admin?tab=ai',          sub: '模型与配额' },
  { key: 'audit',       label: '审计',       href: '/admin?tab=audit',       sub: '操作日志' },
];

function readQueryTab(): string {
  if (typeof window === 'undefined') return 'integration';
  return new URLSearchParams(window.location.search).get('tab') || 'integration';
}

export function AdminShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? '/admin';
  const activeTab = readQueryTab();

  return (
    <div className="admin-shell">
      <aside className="admin-nav">
        <div className="admin-nav-brand">
          <Link href="/admin" className="admin-nav-brand-row">
            <span className="admin-nav-brand-mark">A</span>
            <div>
              <div className="admin-nav-brand-name">AIDA · 控制台</div>
              <div className="admin-nav-brand-sub">系统管理员后台</div>
            </div>
          </Link>
        </div>

        <nav className="admin-nav-list">
          <div className="admin-nav-section">系统级配置</div>
          {ADMIN_NAV.map(it => {
            const on = activeTab === it.key && pathname.startsWith('/admin');
            return (
              <Link key={it.key} href={it.href} className={`admin-nav-item${on ? ' on' : ''}`}>
                <span className="admin-nav-item-dot" />
                <span className="admin-nav-item-meta">
                  <span className="admin-nav-item-label">{it.label}</span>
                  {it.sub && <span className="admin-nav-item-sub">{it.sub}</span>}
                </span>
              </Link>
            );
          })}
        </nav>

        <div className="admin-nav-foot">
          <Link href="/login" className="admin-nav-exit" title="切回项目空间需要重新登录">
            ⏎ 退出 · 回到登录
          </Link>
          <Link href="/cockpit" className="admin-nav-exit alt" title="临时返回项目空间（仅当账号兼职 PD/TD 时可用）">
            ↗ 进入项目空间
          </Link>
        </div>
      </aside>

      <div className="admin-main">
        <header className="admin-topbar">
          <div className="admin-topbar-crumb">
            <Link href="/admin">系统管理员</Link>
            <span className="admin-topbar-sep">/</span>
            <span>{ADMIN_NAV.find(n => n.key === activeTab)?.label || '总览'}</span>
          </div>
          <div className="admin-topbar-right">
            <span className="admin-topbar-tag">管理员身份</span>
            <span className="admin-topbar-user">
              <span className="admin-topbar-av">HE</span>
              <span>何博</span>
            </span>
          </div>
        </header>
        {children}
      </div>
    </div>
  );
}
