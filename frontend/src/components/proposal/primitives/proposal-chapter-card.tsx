'use client';

import type { ReactNode } from 'react';
import { cn } from '../../../lib/cn';

export type ProposalChapterCardVariant = 'default' | 'secondary';

export type ProposalChapterCardProps = {
  id?: string;
  title?: ReactNode;
  subtitle?: ReactNode;
  variant?: ProposalChapterCardVariant;
  className?: string;
  headerExtra?: ReactNode;
  children?: ReactNode;
};

/**
 * 统一章节容器
 * scroll-mt-24：大纲跳转时标题不被 Topbar 遮挡
 */
export function ProposalChapterCard({
  id,
  title,
  subtitle,
  variant = 'default',
  className,
  headerExtra,
  children,
}: ProposalChapterCardProps) {
  const isSecondary = variant === 'secondary';

  return (
    <section
      id={id}
      className={cn(
        'mb-8 scroll-mt-24 rounded-xl border border-slate-200/80 p-6',
        isSecondary ? 'bg-slate-50 shadow-none' : 'bg-white shadow-sm',
        className,
      )}
    >
      {(title || subtitle || headerExtra) && (
        <header className={cn('flex flex-wrap items-baseline gap-x-3 gap-y-1', children != null ? 'mb-4' : undefined)}>
          {title && (
            <h2
              className={cn(
                'text-base font-semibold text-slate-900',
                isSecondary && 'text-sm',
              )}
            >
              {title}
            </h2>
          )}
          {subtitle && (
            <span className="text-xs font-normal text-slate-500">{subtitle}</span>
          )}
          {headerExtra && <span className="ml-auto shrink-0">{headerExtra}</span>}
        </header>
      )}
      {children}
    </section>
  );
}
