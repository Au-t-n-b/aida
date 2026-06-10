'use client';

import { useState } from 'react';
import { PROPOSAL_VERSION_HISTORY, type SnapKey } from './proposal-data';

const STATUS_LABEL: Record<'published' | 'draft', string> = {
  published: '已发布',
  draft: '草稿',
};

export function VersionDropdown({
  snapKey,
  onSelect,
}: {
  snapKey: SnapKey;
  onSelect: (key: SnapKey) => void;
}) {
  const [open, setOpen] = useState(false);
  const current =
    PROPOSAL_VERSION_HISTORY.find((v) => v.snapKey === snapKey) ?? PROPOSAL_VERSION_HISTORY[0];
  if (!current) return null;

  return (
    <div className="proposal-version-dropdown">
      <button
        type="button"
        className={`proposal-version-trigger tone-${current.tone}`}
        onClick={() => setOpen((o) => !o)}
      >
        <span className={`proposal-snap-dot tone-${current.tone}`} />
        <span className="proposal-version-label">{current.label}</span>
        <span className={`proposal-version-status is-${current.status}`}>
          {STATUS_LABEL[current.status]}
        </span>
        <span className="proposal-version-caret">▾</span>
      </button>
      {open && (
        <div className="proposal-version-pop" onMouseLeave={() => setOpen(false)}>
          <div className="proposal-version-section">
            <span>版本历史</span>
          </div>
          {PROPOSAL_VERSION_HISTORY.map((v) => (
            <button
              key={v.snapKey}
              type="button"
              className={`proposal-version-row tone-${v.tone}${snapKey === v.snapKey ? ' on' : ''}`}
              onClick={() => {
                onSelect(v.snapKey);
                setOpen(false);
              }}
            >
              <span className={`proposal-snap-dot tone-${v.tone}`} />
              <div className="proposal-version-row-main">
                <span className="proposal-version-row-label">{v.label}</span>
                <span className={`proposal-version-status is-${v.status}`}>
                  {STATUS_LABEL[v.status]}
                </span>
              </div>
              {snapKey === v.snapKey && <span className="proposal-version-check">✓</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
