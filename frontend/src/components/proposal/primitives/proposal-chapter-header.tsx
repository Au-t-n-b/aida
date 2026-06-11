'use client';

import { cn } from '../../../lib/cn';

/** 一级章节 Ghost 标题（无卡片背景） */
export function ProposalChapterHeader({
  title,
  id,
  className,
}: {
  title: string;
  id?: string;
  className?: string;
}) {
  return (
    <h2
      id={id}
      className={cn(
        'mb-4 mt-8 scroll-mt-24 text-xl font-bold text-slate-800 first:mt-4',
        className,
      )}
    >
      {title}
    </h2>
  );
}
