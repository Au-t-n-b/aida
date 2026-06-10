'use client';

/**
 * Drawer — right-side Slide-over panel
 *
 * Usage:
 *   <Drawer isOpen={open} onClose={() => setOpen(false)} title="PoD 级钻取">
 *     <YourContent />
 *   </Drawer>
 */

import { useEffect, type ReactNode } from 'react';

export interface DrawerProps {
  /** controls open / closed state */
  isOpen: boolean;
  /** called when backdrop or × is clicked, or Escape is pressed */
  onClose: () => void;
  /** header title text */
  title: ReactNode;
  /** optional subtitle below the title */
  subtitle?: ReactNode;
  /** panel width: 'default' = 45%/max-2xl, 'wide' = 62%/max-5xl (for wide tables) */
  size?: 'default' | 'wide';
  /** drawer body content */
  children: ReactNode;
}

export default function Drawer({ isOpen, onClose, title, subtitle, size = 'default', children }: DrawerProps) {
  const widthCls = size === 'wide' ? 'w-[62%] max-w-5xl' : 'w-[45%] max-w-2xl';
  /* ── Keyboard: Escape closes the drawer ── */
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [isOpen, onClose]);

  /* ── Scroll-lock: prevent body scroll while open ── */
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [isOpen]);

  return (
    <>
      {/* ── Backdrop ── */}
      <div
        aria-hidden="true"
        onClick={onClose}
        className={[
          'fixed inset-0 bg-zinc-900/20 z-40',
          'transition-opacity duration-300 ease-in-out',
          isOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none',
        ].join(' ')}
        style={{ backdropFilter: 'blur(4px)', WebkitBackdropFilter: 'blur(4px)' }}
      />

      {/* ── Panel ── */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === 'string' ? title : undefined}
        /* 位移用内联 transform —— 本项目关闭了 @tailwind base，
           translate-x-* 依赖的 --tw-translate-* 变量未初始化会失效 */
        className={[
          'fixed inset-y-0 right-0 z-50 flex flex-col',
          widthCls, 'bg-white shadow-2xl',
        ].join(' ')}
        style={{
          transform: isOpen ? 'translateX(0)' : 'translateX(100%)',
          transition: 'transform 300ms ease-in-out',
        }}
      >
        {/* ── Header ── */}
        <div className="flex items-start justify-between px-6 py-5 border-b border-zinc-100 shrink-0">
          <div className="min-w-0 pr-4">
            <h2 className="text-[15px] font-semibold text-zinc-900 leading-snug truncate">
              {title}
            </h2>
            {subtitle && (
              <p className="mt-0.5 text-[12px] text-zinc-400 leading-none">
                {subtitle}
              </p>
            )}
          </div>

          {/* × close button */}
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭"
            className="shrink-0 w-7 h-7 flex items-center justify-center rounded-md text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 transition-colors duration-150"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <path d="M1 1l12 12M13 1L1 13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {/* ── Content slot ── */}
        <div className="flex-1 overflow-y-auto overscroll-contain">
          {children}
        </div>
      </div>
    </>
  );
}
