'use client';

import { useEffect, useState } from 'react';
import { ensureAgentBase } from '@/lib/agentBase';

export type ZhgkFiveValues = {
  满足: number;
  不满足: number;
  不涉及: number;
  未勘测: number;
  无法识别: number;
};

export type ZhgkRoomCatalogItem = {
  room_id: string;
  room_name: string;
  pod_count: number;
  rack_count: number;
  pod_names?: string[];
  status: 'pending' | 'active' | 'assessed' | 'done';
  status_label: string;
  five_values: ZhgkFiveValues;
  total: number;
  survey_round?: number | null;
  issue_count?: number;
};

export type ZhgkRoomCatalog = {
  rooms: ZhgkRoomCatalogItem[];
  source: string;
  logical_path: string;
  rack_table_path?: string | null;
};

const FIVE_COLS: { key: keyof ZhgkFiveValues; label: string; cls: string }[] = [
  { key: '满足', label: '满足', cls: 'ok' },
  { key: '不满足', label: '不满足', cls: 'danger' },
  { key: '不涉及', label: '不涉及', cls: 'muted' },
  { key: '未勘测', label: '未勘测', cls: 'pending' },
  { key: '无法识别', label: '无法识别', cls: 'warn' },
];

const STATUS_CHIP: Record<string, string> = {
  pending: 'pending',
  active: '',
  assessed: 'assessed',
  done: 'done',
};

export async function fetchZhgkRoomCatalog(skillId = 'zhgk'): Promise<ZhgkRoomCatalog> {
  const base = await ensureAgentBase(skillId);
  const res = await fetch(`${base}/agent/${skillId}/room-catalog`);
  if (!res.ok) {
    const text = await res.text();
    try {
      const j = JSON.parse(text) as { detail?: string };
      throw new Error(j.detail ?? text);
    } catch {
      throw new Error(text || `HTTP ${res.status}`);
    }
  }
  return res.json() as Promise<ZhgkRoomCatalog>;
}

const ROOM_PICKER_STYLE_ID = 'zhgk-room-picker-styles-v3';
const ROOM_SCALE = 1.3;

function roomPickerStyleText() {
  return `
    .zhgk-room-grid {
      --zhgk-room-scale: ${ROOM_SCALE};
      width: 100%;
      max-width: calc(640px * var(--zhgk-room-scale));
      margin-bottom: calc(8px * var(--zhgk-room-scale));
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(calc(168px * var(--zhgk-room-scale)), 1fr));
      gap: calc(12px * var(--zhgk-room-scale));
    }
    .zhgk-room-grid.full {
      max-width: none;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: calc(16px * var(--zhgk-room-scale));
      align-items: stretch;
    }
    .zhgk-room-card {
      text-align: left; cursor: pointer; border: 1px solid #dde3ef;
      border-radius: calc(10px * var(--zhgk-room-scale));
      background: #fff;
      padding: calc(12px * var(--zhgk-room-scale)) calc(12px * var(--zhgk-room-scale)) calc(10px * var(--zhgk-room-scale));
      box-shadow: 0 1px 3px rgba(15,23,42,.04);
      transition: border-color .14s, box-shadow .14s, transform .1s;
      font-family: var(--font-sans);
    }
    .zhgk-room-card:hover:not(:disabled) {
      border-color: #3551d8; box-shadow: 0 4px 14px rgba(53,81,216,.12); transform: translateY(-1px);
    }
    .zhgk-room-card.active {
      border-color: #3551d8; box-shadow: 0 0 0 1px #3551d8, 0 4px 14px rgba(53,81,216,.1);
    }
    .zhgk-room-card:disabled { opacity: .65; cursor: wait; }
    .zhgk-room-head {
      display: flex; align-items: center; justify-content: space-between;
      gap: calc(8px * var(--zhgk-room-scale));
      margin-bottom: calc(6px * var(--zhgk-room-scale));
    }
    .zhgk-room-name { font-size: calc(13px * var(--zhgk-room-scale)); font-weight: 650; color: #0f172a; }
    .zhgk-room-meta {
      font-size: calc(10px * var(--zhgk-room-scale)); color: #64748b;
      margin-bottom: calc(8px * var(--zhgk-room-scale));
    }
    .zhgk-room-chip {
      font-size: calc(9.5px * var(--zhgk-room-scale)); font-weight: 600;
      padding: calc(2px * var(--zhgk-room-scale)) calc(7px * var(--zhgk-room-scale));
      border-radius: 99px; white-space: nowrap;
      background: #eff6ff; color: #1d4ed8; display: inline-flex; align-items: center;
      gap: calc(4px * var(--zhgk-room-scale));
    }
    .zhgk-room-chip.pending { background: #f1f5f9; color: #64748b; }
    .zhgk-room-chip.assessed { background: #fef3c7; color: #92400e; }
    .zhgk-room-chip.done { background: #f0fdf4; color: #15803d; }
    .zhgk-room-chip .dot {
      width: calc(5px * var(--zhgk-room-scale)); height: calc(5px * var(--zhgk-room-scale));
      border-radius: 50%; background: currentColor; opacity: .85;
    }
    .zhgk-room-five {
      display: grid; grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: calc(6px * var(--zhgk-room-scale));
      margin-bottom: calc(8px * var(--zhgk-room-scale));
    }
    .zhgk-room-five .cell {
      text-align: center; min-width: 0;
      background: #f1f5f9; border-radius: calc(6px * var(--zhgk-room-scale));
      padding: calc(6px * var(--zhgk-room-scale)) calc(4px * var(--zhgk-room-scale)) calc(5px * var(--zhgk-room-scale));
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      gap: calc(2px * var(--zhgk-room-scale));
    }
    .zhgk-room-five .v { font-size: calc(12px * var(--zhgk-room-scale)); font-weight: 700; line-height: 1.2; }
    .zhgk-room-five .l {
      font-size: calc(9px * var(--zhgk-room-scale)); color: #64748b; line-height: 1.25;
      white-space: normal; overflow: visible; text-overflow: unset; max-width: 100%;
    }
    .zhgk-room-five .v.ok { color: #15803d; }
    .zhgk-room-five .v.danger { color: #b91c1c; }
    .zhgk-room-five .v.muted { color: #94a3b8; }
    .zhgk-room-five .v.pending { color: #64748b; }
    .zhgk-room-five .v.warn { color: #b45309; }
    .zhgk-room-foot { font-size: calc(9.5px * var(--zhgk-room-scale)); color: #94a3b8; }
    .zhgk-room-empty, .zhgk-room-err {
      width: 100%; max-width: calc(420px * var(--zhgk-room-scale));
      padding: calc(12px * var(--zhgk-room-scale)) calc(14px * var(--zhgk-room-scale));
      border-radius: calc(10px * var(--zhgk-room-scale));
      font-size: calc(12px * var(--zhgk-room-scale));
      text-align: center; margin-bottom: calc(16px * var(--zhgk-room-scale));
    }
    .zhgk-room-empty { background: #fff; border: 1px dashed #c8d1e6; color: #64748b; }
    .zhgk-room-err { background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; }
    .zhgk-room-legend {
      width: 100%; max-width: calc(640px * var(--zhgk-room-scale));
      font-size: calc(9.5px * var(--zhgk-room-scale)); color: #94a3b8;
      text-align: center; margin-top: calc(4px * var(--zhgk-room-scale));
    }
    .zhgk-room-grid.full + .zhgk-room-legend { max-width: none; }
  `;
}

function ensureRoomPickerStyles() {
  if (typeof document === 'undefined') return;
  document.getElementById('zhgk-room-picker-styles')?.remove();
  document.getElementById('zhgk-room-picker-styles-v2')?.remove();
  let el = document.getElementById(ROOM_PICKER_STYLE_ID);
  if (!el) {
    el = document.createElement('style');
    el.id = ROOM_PICKER_STYLE_ID;
    document.head.appendChild(el);
  }
  el.textContent = roomPickerStyleText();
}

type Props = {
  loading?: boolean;
  activeRoomName?: string | null;
  layout?: 'centered' | 'full';
  onSelect: (room: ZhgkRoomCatalogItem) => void;
};

export function ZhgkRoomPicker({ loading, activeRoomName, layout = 'centered', onSelect }: Props) {
  const [catalog, setCatalog] = useState<ZhgkRoomCatalog | null>(null);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    ensureRoomPickerStyles();
    let cancelled = false;
    void (async () => {
      setFetching(true);
      setError(null);
      try {
        const data = await fetchZhgkRoomCatalog();
        if (!cancelled) setCatalog(data);
      } catch (e) {
        if (!cancelled) {
          const raw = e instanceof Error ? e.message : '加载机房列表失败';
          const hint = raw.includes('Not Found')
            ? 'Agent 未加载 room-catalog 接口，请重启 Agent（scripts/reset_local_dev.ps1 或重启 :7401）后刷新页面'
            : raw;
          setError(hint);
        }
      } finally {
        if (!cancelled) setFetching(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (fetching) {
    return <div className="zhgk-room-empty">正在读取机房机柜信息表…</div>;
  }
  if (error) {
    return <div className="zhgk-room-err">{error}</div>;
  }
  if (!catalog?.rooms?.length) {
    return (
      <div className="zhgk-room-empty">
        未找到机房数据。请将「机房机柜信息表.xlsx」放入
        <br />
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{catalog?.logical_path ?? '孪生世界/算力底座孪生/输出结果/机房机柜信息表'}</span>
      </div>
    );
  }

  const busy = !!loading;

  return (
    <>
      <div className={`zhgk-room-grid${layout === 'full' ? ' full' : ''}`}>
        {catalog.rooms.map(room => {
          const chipCls = STATUS_CHIP[room.status] ?? '';
          const fv = room.five_values;
          const isActive = !!activeRoomName && room.room_name === activeRoomName;
          return (
            <button
              key={room.room_id}
              type="button"
              className={`zhgk-room-card${isActive ? ' active' : ''}`}
              disabled={busy}
              onClick={() => onSelect(room)}
            >
              <div className="zhgk-room-head">
                <span className="zhgk-room-name">{room.room_name} 机房</span>
                <span className={`zhgk-room-chip ${chipCls}`}>
                  <span className="dot" aria-hidden />
                  {room.status_label}
                </span>
              </div>
              <div className="zhgk-room-meta">
                {room.pod_count} PoD · {room.rack_count} 机柜
              </div>
              <div className="zhgk-room-five">
                {FIVE_COLS.map(col => (
                  <div key={col.key} className="cell">
                    <div className={`v ${col.cls}`}>{fv[col.key] ?? 0}</div>
                    <div className="l">{col.label}</div>
                  </div>
                ))}
              </div>
              <div className="zhgk-room-foot">
                {room.survey_round ? `R${room.survey_round} 轮` : '尚未建表'}
                {room.issue_count ? ` · ${room.issue_count} 问题` : ''}
              </div>
            </button>
          );
        })}
      </div>
      <div className="zhgk-room-legend">
        五值：满足 · 不满足 · 不涉及 · 未勘测 · 无法识别
      </div>
    </>
  );
}
