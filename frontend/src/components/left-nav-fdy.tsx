'use client';

import React, { useState, useRef, useLayoutEffect, useEffect, type ComponentType, type RefObject } from 'react';
import { motion, LayoutGroup } from 'framer-motion';
import {
  Network,
  ClipboardList,
  Hexagon,
  FolderKanban,
  Cpu,
  History,
  FolderOpen,
  ChevronDown,
  ChevronRight,
  Sun,
  Moon,
} from 'lucide-react';
import Link from '@/compat/link';
import { useNavPath } from '@/compat/navigation';
import { MODULE_STATUS } from '../data/journey-data';
import {
  NAV_TWIN,
  NAV_EARLY,
  NAV_PLAN,
  NAV_OPS,
  NAV_DOCS,
  isNavSubActive,
  type NavSubItem,
} from '../data/left-nav-items';
import { getLeftNavScrollTop, setLeftNavScrollTop, restoreLeftNavScroll } from '@/lib/left-nav-scroll';
import {
  type NavExpandedState,
  applyRouteRequiredExpand,
  readInitialExpanded,
  persistExpanded,
} from '@/lib/left-nav-expanded';
import { type LeftNavTheme, readLeftNavTheme, persistLeftNavTheme } from '@/lib/left-nav-theme';
import brandLogoUrl from '@/assets/brand-logo.svg';
import brandLogoLightUrl from '@/assets/brand-logo-light.svg';
import wordmarkUrl from '@/assets/aida-wordmark.svg';

type FdySubItem = NavSubItem & {
  status?: string;
  statusLabel?: string;
  disabled?: boolean;
  n?: string;
  active?: boolean;
};

type NavGroupConfig = {
  id: string;
  label: string;
  icon: ComponentType<{ size?: number; strokeWidth?: number }>;
  tone: string;
  active: boolean;
  sub: FdySubItem[];
  hrefPrefix?: string;
  disabled?: boolean;
};

const iconMotion = {
  hover: { scale: 1.1, rotate: [0, -8, 6, -3, 0] as number[], transition: { duration: 0.5 } },
  active: { scale: [1, 1.08, 1] as number[], filter: 'brightness(1.1)', transition: { repeat: Infinity, duration: 4, ease: 'easeInOut' as const } },
  rest: { scale: 1, rotate: 0, filter: 'brightness(1)' },
};

function BrandLogo({ size = 22, light = false }: { size?: number; light?: boolean }) {
  return (
    <img
      src={light ? brandLogoLightUrl : brandLogoUrl}
      alt="AIDA"
      width={size}
      height={size}
      className="fdy-brand-logo-img"
      draggable={false}
    />
  );
}

function BrandWordmark({ height = 22 }: { height?: number }) {
  return (
    <img
      src={wordmarkUrl}
      alt="AIDA"
      height={height}
      className="fdy-brand-wordmark-img"
      draggable={false}
    />
  );
}

/** wordmark 首字 A · 展开 -90°（向左）、收起 +90°（向右） */
const WORDMARK_A_POINTS =
  '0,120 42.658,36.574 57.342,36.574 100,120 86.522,120 50,48.574 13.478,120';

function NavCollapseIcon({ collapsed }: { collapsed: boolean }) {
  return (
    <svg
      viewBox="0 0 100 120"
      className={`fdy-collapse-a-icon${collapsed ? ' is-collapsed' : ''}`}
      aria-hidden
    >
      <polygon fill="currentColor" points={WORDMARK_A_POINTS} />
    </svg>
  );
}

function isSubActive(navPath: string, s: FdySubItem, hrefPrefix?: string): boolean {
  if (s.active) return true;
  return isNavSubActive(navPath, s, hrefPrefix);
}

const FDY_SUB_ACTIVE_LAYOUT_ID = 'fdyActiveSubIndicator';

function FdySubMenu({
  sub,
  hrefPrefix,
  collapsed,
  scrollRef,
}: {
  sub: FdySubItem[];
  hrefPrefix?: string;
  collapsed: boolean;
  scrollRef: RefObject<HTMLDivElement | null>;
}) {
  const navPath = useNavPath();

  return (
    <div className="fdy-sub-panel" onClick={(e) => e.stopPropagation()}>
      <div className="fdy-sub-inner">
        <div className="fdy-sub-line" aria-hidden />
        <div className="fdy-sub-list">
          {sub.map((s, i) => {
            const active = isSubActive(navPath, s, hrefPrefix);
            const disabled = s.disabled;
            const href = s.href || (hrefPrefix && s.key ? `${hrefPrefix}/${s.key}` : null);

            const row = (
              <motion.div
                className={`fdy-sub-item${active ? ' active' : ''}${disabled ? ' disabled' : ''}`}
                whileHover={disabled ? undefined : { x: 6 }}
                whileTap={disabled ? undefined : { scale: 0.98 }}
                transition={{ duration: 0.2 }}
                title={disabled ? '一期暂不开放' : undefined}
                onClick={(e) => disabled && e.preventDefault()}
              >
                {active && (
                  <motion.span
                    layoutId={FDY_SUB_ACTIVE_LAYOUT_ID}
                    className="fdy-sub-active-dot"
                    aria-hidden
                    onLayoutAnimationComplete={() => restoreLeftNavScroll(scrollRef.current)}
                  />
                )}
                <span className="n">{s.name}</span>
                {s.n && <span className="c">{s.n}</span>}
              </motion.div>
            );

            if (disabled || !href) {
              return <div key={i}>{row}</div>;
            }
            return (
              <Link
                key={i}
                href={href}
                style={{ textDecoration: 'none' }}
                onClick={(e) => e.stopPropagation()}
              >
                {row}
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function FdyNavGroup({
  config,
  expanded,
  collapsed,
  onToggle,
  onExpandFromCollapsed,
  scrollRef,
}: {
  config: NavGroupConfig;
  expanded: boolean;
  collapsed: boolean;
  onToggle: () => void;
  onExpandFromCollapsed: () => void;
  scrollRef: RefObject<HTMLDivElement | null>;
}) {
  const navPath = useNavPath();
  const { icon: Icon, label, sub, tone, active, hrefPrefix, disabled } = config;
  const hasChildren = sub.length > 0;
  const childActive = sub.some((s) => isSubActive(navPath, s, hrefPrefix));
  const showActive = active || childActive;

  const handleClick = () => {
    if (disabled) return;
    if (hasChildren && collapsed) {
      onExpandFromCollapsed();
      if (!expanded) onToggle();
      return;
    }
    onToggle();
  };

  return (
    <div className="fdy-menu-group">
      {showActive && <div className="fdy-active-indicator" aria-hidden />}

      <motion.button
        type="button"
        layout={false}
        className={`fdy-app fdy-app-v2${showActive ? ' active' : ''}${expanded ? ' expanded' : ''}${collapsed ? ' is-collapsed' : ''}`}
        onClick={handleClick}
        disabled={disabled}
        title={collapsed ? label : undefined}
        initial="rest"
        animate={showActive ? 'active' : 'rest'}
        whileHover={disabled ? undefined : 'hover'}
        whileTap={disabled ? undefined : { scale: 0.98 }}
        variants={{
          hover: { x: collapsed ? 0 : 4, transition: { duration: 0.2 } },
          rest: { x: 0, transition: { duration: 0.2 } },
          active: { x: 0, transition: { duration: 0.2 } },
        }}
      >
        <div className="fdy-app-main">
          <motion.span className={`fdy-icon-tile tone-${tone}`} variants={iconMotion}>
            <Icon size={18} strokeWidth={2} />
          </motion.span>
          {!collapsed && <span className="fdy-label">{label}</span>}
        </div>
        {!collapsed && hasChildren && (
          <span className={`fdy-caret-v2${showActive ? ' on-active' : ''}`}>
            {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          </span>
        )}
      </motion.button>

      {hasChildren && expanded && !collapsed && (
        <FdySubMenu
          sub={sub}
          hrefPrefix={hrefPrefix}
          collapsed={collapsed}
          scrollRef={scrollRef}
        />
      )}
    </div>
  );
}

function FdyNavLeaf({
  href,
  label,
  icon: Icon,
  tone,
  active,
  collapsed,
}: {
  href: string;
  label: string;
  icon: ComponentType<{ size?: number; strokeWidth?: number }>;
  tone: string;
  active: boolean;
  collapsed: boolean;
}) {
  return (
    <div className="fdy-menu-group">
      {active && <div className="fdy-active-indicator" aria-hidden />}
      <Link href={href} style={{ display: 'block', textDecoration: 'none' }}>
        <motion.div
          layout={false}
          className={`fdy-app fdy-app-v2${active ? ' active' : ''}${collapsed ? ' is-collapsed' : ''}`}
          title={collapsed ? label : undefined}
          initial="rest"
          animate={active ? 'active' : 'rest'}
          whileHover="hover"
          whileTap={{ scale: 0.98 }}
          variants={{
            hover: { x: collapsed ? 0 : 4, transition: { duration: 0.2 } },
            rest: { x: 0, transition: { duration: 0.2 } },
            active: { x: 0, transition: { duration: 0.2 } },
          }}
        >
          <div className="fdy-app-main">
            <motion.span className={`fdy-icon-tile tone-${tone}`} variants={iconMotion}>
              <Icon size={18} strokeWidth={2} />
            </motion.span>
            {!collapsed && <span className="fdy-label">{label}</span>}
          </div>
        </motion.div>
      </Link>
    </div>
  );
}

export function LeftNavFdy({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const navPath = useNavPath();
  const pathname = navPath.split('?')[0] ?? navPath;
  const scrollRef = useRef<HTMLDivElement>(null);
  const [navTheme, setNavTheme] = useState<LeftNavTheme>(() => readLeftNavTheme());

  const toggleNavTheme = () => {
    setNavTheme((prev) => {
      const next = prev === 'light' ? 'dark' : 'light';
      persistLeftNavTheme(next);
      return next;
    });
  };

  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const top = getLeftNavScrollTop();
    el.scrollTop = top;
    const raf1 = requestAnimationFrame(() => {
      el.scrollTop = top;
      requestAnimationFrame(() => {
        el.scrollTop = top;
      });
    });
    return () => cancelAnimationFrame(raf1);
  }, [navPath]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    let raf = 0;
    const onScroll = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => setLeftNavScrollTop(el.scrollTop));
    };
    const saveBeforeNav = () => setLeftNavScrollTop(el.scrollTop);
    el.addEventListener('scroll', onScroll, { passive: true });
    el.addEventListener('pointerdown', saveBeforeNav, { capture: true });
    return () => {
      cancelAnimationFrame(raf);
      el.removeEventListener('scroll', onScroll);
      el.removeEventListener('pointerdown', saveBeforeNav, { capture: true });
    };
  }, []);

  const [expanded, setExpanded] = useState<NavExpandedState>(() => readInitialExpanded(navPath));

  /** 进入新路由分区时展开对应分组；同 pathname 下仅 query 变化不强制重开（如 /assets 分类切换） */
  useEffect(() => {
    setExpanded((s) => applyRouteRequiredExpand(s, navPath));
  }, [pathname]);

  useEffect(() => {
    persistExpanded(expanded);
  }, [expanded]);

  const toggle = (k: keyof NavExpandedState) => {
    setExpanded((s) => {
      const next = { ...s, [k]: !s[k] };
      persistExpanded(next);
      return next;
    });
  };
  const expandNav = () => {
    if (collapsed) onToggle();
  };

  const isCockpit = pathname === '/cockpit';
  const isTwin = pathname.startsWith('/twin');
  const isEarly = pathname.startsWith('/preview') || pathname.startsWith('/proposal');
  const isDesign = pathname.startsWith('/design');
  const isPlan =
    pathname.startsWith('/plan') || pathname.startsWith('/plan-init') || pathname.startsWith('/plan-adjust');
  const isModulePath = pathname.startsWith('/module/') || pathname.startsWith('/commissioning');
  const isEvals = pathname.startsWith('/evals');

  const navTwin: FdySubItem[] = NAV_TWIN.map((item) => ({
    ...item,
    ...(item.href === '/twin' ? { status: 'live' as const, statusLabel: '物理 ⇄ 数字' } : {}),
    ...(item.href === '/cockpit'
      ? { status: MODULE_STATUS.cockpit?.state, statusLabel: '看板' }
      : {}),
    ...(item.href === '/twin/survey' ? { status: 'live' as const, statusLabel: 'SOG 通道' } : {}),
  }));
  const navEarly: FdySubItem[] = NAV_EARLY.map((item) => ({
    ...item,
    ...(item.href === '/preview' ? { status: 'ok' as const, statusLabel: '在线' } : {}),
    ...(item.href === '/proposal' ? { status: 'warn' as const, statusLabel: '版本号切换' } : {}),
  }));
  const navPlan: FdySubItem[] = NAV_PLAN.map((item) => ({
    ...item,
    ...(item.href === '/plan?view=info' ? { status: 'ok' as const } : {}),
    ...(item.href === '/plan?view=plan'
      ? { status: MODULE_STATUS.plan?.state, statusLabel: MODULE_STATUS.plan?.label }
      : {}),
    ...(item.href === '/plan?view=task' ? { status: 'ok' as const } : {}),
    ...(item.href === '/plan?view=risk' ? { status: 'alert' as const, statusLabel: '3 红' } : {}),
    ...(item.href === '/plan?view=assumption' ? { status: 'warn' as const, statusLabel: '3 项' } : {}),
    ...(item.href === '/plan?view=issue' ? { status: 'warn' as const, statusLabel: '2 项' } : {}),
    ...(item.href === '/plan?view=change' ? { status: 'ok' as const } : {}),
    ...(item.href === '/plan-init' ? { status: 'ok' as const } : {}),
    ...(item.href === '/plan-adjust' ? { status: 'ok' as const } : {}),
  }));
  const navOps: FdySubItem[] = NAV_OPS.map((item) => ({
    ...item,
    ...(item.key === 'survey'
      ? { status: MODULE_STATUS.survey?.state, statusLabel: MODULE_STATUS.survey?.label }
      : {}),
    ...(item.key === 'modeling'
      ? { status: MODULE_STATUS.modeling?.state, statusLabel: MODULE_STATUS.modeling?.label }
      : {}),
    ...(item.key === 'install'
      ? { status: MODULE_STATUS.install?.state, statusLabel: MODULE_STATUS.install?.label }
      : {}),
    ...(item.href === '/commissioning' ? { status: 'live' as const, statusLabel: '5 步' } : {}),
  }));
  const navDocs: FdySubItem[] = NAV_DOCS.map((item) => ({
    ...item,
    status: 'ok' as const,
    statusLabel:
      item.href === '/assets?cat=mgmt'
        ? 'PD / TD'
        : item.href === '/assets?cat=survey'
          ? 'TL 现场'
          : 'TL 维护',
  }));

  const groups: { key: keyof typeof expanded; config: NavGroupConfig }[] = [
    {
      key: 'twin',
      config: {
        id: 'twin',
        label: '孪生世界',
        icon: Network,
        tone: 'rose',
        active: isCockpit || isTwin,
        sub: navTwin,
      },
    },
    {
      key: 'early',
      config: {
        id: 'early',
        label: '早期介入',
        icon: ClipboardList,
        tone: 'blue',
        active: isEarly,
        sub: navEarly,
      },
    },
    {
      key: 'plan',
      config: {
        id: 'plan',
        label: '项目管理',
        icon: FolderKanban,
        tone: 'amber',
        active: isPlan,
        sub: navPlan,
      },
    },
    {
      key: 'ops',
      config: {
        id: 'ops',
        label: '交付作业',
        icon: Cpu,
        tone: 'teal',
        active: isModulePath,
        sub: navOps,
        hrefPrefix: '/module',
      },
    },
    {
      key: 'docs',
      config: {
        id: 'docs',
        label: '项目文档',
        icon: FolderOpen,
        tone: 'indigo-light',
        active: navPath.startsWith('/assets'),
        sub: navDocs,
      },
    },
  ];

  const isNavLight = navTheme === 'light';

  return (
    <nav
      className={`left-nav-fdy left-nav-fdy-v2 fdy-theme-${navTheme}${collapsed ? ' nav-collapsed' : ''}`}
    >
      <div className="fdy-brand fdy-brand-v2">
        <Link href="/cockpit" className="fdy-brand-link">
          <div className="fdy-brand-mark" title="返回驾驶舱">
            <BrandLogo size={22} light={isNavLight} />
          </div>
          {!collapsed && (
            <div className="fdy-brand-text">
              <div className="b1 fdy-brand-wordmark">
                <BrandWordmark height={22} />
              </div>
            </div>
          )}
        </Link>
        <button
          type="button"
          className="fdy-collapse-btn fdy-collapse-btn-v2"
          onClick={onToggle}
          title={collapsed ? '展开' : '收起'}
        >
          <NavCollapseIcon collapsed={collapsed} />
        </button>
      </div>

      <div ref={scrollRef} className="fdy-scroll-v2">
        <LayoutGroup id="fdy-nav-sub-active">
        <div className="fdy-nav-list">
          {groups.slice(0, 2).map(({ key, config }) => (
            <FdyNavGroup
              key={key}
              config={config}
              expanded={expanded[key]}
              collapsed={collapsed}
              onToggle={() => toggle(key)}
              onExpandFromCollapsed={expandNav}
              scrollRef={scrollRef}
            />
          ))}

          <FdyNavLeaf
            href="/design"
            label="交付方案"
            icon={Hexagon}
            tone="indigo"
            active={isDesign}
            collapsed={collapsed}
          />

          {groups.slice(2).map(({ key, config }) => (
            <FdyNavGroup
              key={key}
              config={config}
              expanded={expanded[key]}
              collapsed={collapsed}
              onToggle={() => toggle(key)}
              onExpandFromCollapsed={expandNav}
              scrollRef={scrollRef}
            />
          ))}

          <FdyNavLeaf
            href="/evals"
            label="评测中心"
            icon={History}
            tone="purple"
            active={isEvals}
            collapsed={collapsed}
          />
        </div>
        </LayoutGroup>
      </div>

      <div className="fdy-nav-theme-foot">
        <button
          type="button"
          className={`fdy-theme-toggle${collapsed ? ' is-collapsed' : ''}`}
          onClick={toggleNavTheme}
          title={isNavLight ? '切换为深色菜单' : '切换为浅色菜单'}
        >
          <span className="fdy-theme-toggle-icon" aria-hidden>
            {isNavLight ? <Moon size={18} strokeWidth={2} /> : <Sun size={18} strokeWidth={2} />}
          </span>
          {!collapsed && (
            <span className="fdy-theme-toggle-label">{isNavLight ? '深色模式' : '浅色模式'}</span>
          )}
        </button>
      </div>
    </nav>
  );
}

export function SideNav({ currentModule: _currentModule }: { currentModule?: string }) {
  return <LeftNavFdy collapsed={false} onToggle={() => {}} />;
}
