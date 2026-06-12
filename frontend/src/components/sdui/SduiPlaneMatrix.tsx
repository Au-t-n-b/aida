'use client';

import React, { useEffect, useMemo, useState } from 'react';
import type { SduiPlaneCell } from '@/lib/sdui';

const GROUP_META: Record<string, { id: string; tone: string }> = {
  '计算面': { id: 'compute', tone: 'brand' },
  '网络面': { id: 'network', tone: 'info' },
  '存储面': { id: 'storage', tone: 'violet' },
  '管理 / 衍生件': { id: 'manage', tone: 'amber' },
  '管理/衍生件': { id: 'manage', tone: 'amber' },
};

type ItemStatus = 'done' | 'running' | 'pending' | 'error';

function normKey(s: string) {
  return String(s).replace(/\s/g, '');
}

function groupMeta(title: string) {
  return GROUP_META[title] ?? { id: normKey(title) || '_', tone: 'brand' };
}

function itemStatus(st: string | undefined): ItemStatus {
  if (st === 'done') return 'done';
  if (st === 'running') return 'running';
  if (st === 'error') return 'error';
  return 'pending';
}

function statusClass(st: ItemStatus) {
  if (st === 'done') return 'done';
  if (st === 'running') return 'running';
  if (st === 'error') return 'failed';
  return 'later';
}

export function SduiPlaneMatrix({ cells }: { cells: SduiPlaneCell[] }) {
  const groups = useMemo(() => {
    const order: string[] = [];
    const map = new Map<string, SduiPlaneCell[]>();
    for (const c of cells) {
      const g = c.group ?? '';
      if (!map.has(g)) {
        map.set(g, []);
        order.push(g);
      }
      map.get(g)!.push(c);
    }
    return order.map((title) => ({
      title,
      meta: groupMeta(title),
      items: map.get(title) ?? [],
    }));
  }, [cells]);

  const [active, setActive] = useState(groups[0]?.meta.id ?? 'compute');

  useEffect(() => {
    const running = groups.find((g) =>
      g.items.some((it) => itemStatus(it.status) === 'running'),
    );
    if (running) setActive(running.meta.id);
  }, [groups]);

  const activeGroup = groups.find((g) => g.meta.id === active) ?? groups[0];

  return (
    <div className="sd-plan-graph">
      <div className="spg-legend">
        <span><i className="later" />待执行</span>
        <span><i className="running" />执行中</span>
        <span><i className="done" />已完成</span>
        <span><i className="failed" />失败</span>
      </div>

      <div className="sd-progress-modules">
        {groups.map((g) => {
          const total = g.items.length;
          const doneN = g.items.filter((it) => itemStatus(it.status) === 'done').length;
          const isOpen = g.meta.id === active;
          const groupRunning = g.items.some((it) => itemStatus(it.status) === 'running');
          const groupDone = total > 0 && doneN === total;
          const groupFailed = g.items.some((it) => itemStatus(it.status) === 'error');
          return (
            <div
              key={g.meta.id}
              className={[
                'sd-progress-plane',
                isOpen ? 'is-expanded' : '',
                groupRunning ? 'is-active' : '',
                groupDone ? 'is-done' : '',
              ].filter(Boolean).join(' ')}
            >
              <button
                type="button"
                className="sd-progress-plane-head"
                onClick={() => setActive(g.meta.id)}
                aria-expanded={isOpen}
              >
                <span className={`sd-matrix-dot tone-${g.meta.tone}`} />
                <span className="sd-progress-plane-title">{g.title}</span>
                <span className="sd-matrix-count num">{doneN}/{total}</span>
                {groupFailed ? <span className="sd-chip-alert" aria-label="存在失败项">!</span> : null}
              </button>
            </div>
          );
        })}
      </div>

      {activeGroup && (
        <div className="sd-scatter-deck">
          <div className="sd-plane-scatter">
            <div className="sd-plane-scatter-head">
              <span className={`sd-matrix-dot tone-${activeGroup.meta.tone}`} />
              {activeGroup.title}
              <span className="sd-matrix-count num">
                {activeGroup.items.filter((it) => itemStatus(it.status) === 'done').length}
                /{activeGroup.items.length} 项
              </span>
            </div>
            <div className="sd-plane-scatter-field">
              {activeGroup.items.map((it) => {
                const st = itemStatus(it.status);
                const cls = statusClass(st);
                return (
                  <span
                    key={it.label}
                    className={`sd-scatter-node sd-scatter-node-${cls}`}
                    title={it.note ? `${it.label} — ${it.note}` : it.label}
                  >
                    <span className="sd-scatter-dot" aria-hidden />
                    <span className="sd-scatter-key">{it.label}</span>
                    {st === 'error' ? <span className="sd-scatter-alert" aria-hidden>!</span> : null}
                  </span>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
