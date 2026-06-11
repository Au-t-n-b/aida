'use client';

/* 项目孪生 · 下发追踪（DispatchTracker）
 *
 * 定位：项目孪生 = as-is vs should-be 对照。可交付性研判产生的风险/任务下发到人后，
 *       在这里追踪「让 as-is 回归 should-be 的纠偏动作」的闭环状态。
 *       不是第二个任务库（增删改归档仍回 /plan?view=risk|task），而是监盘镜头。
 *
 * TD 进来只回答三问：① 收到了/开干了吗 ② 哪些要逾期 ③ 干完真把偏差缩小了吗
 *
 * 三镜头（默认 = 闭环板）：
 *   board  闭环状态板：逾期/升级专区置顶 + 待接收/已接收/处理中/已完成 四泳道
 *   people 责任人镜头：按 owner 分组，看谁过载/谁在拖
 *   twin   孪生空间叠加：按机房分组，把未闭环项锚定到物理空间
 *
 * 视觉：沿用 /cockpit (dashboard.tsx) 的 primitives 世界 token —— 不引入 --c-* / jn-*。
 */

import { useState } from 'react';
import type { ReactNode } from 'react';
import type {
  DispatchItem,
  DispatchKind,
  DispatchStatus,
} from '../types/domain';
import { DISPATCH_ITEMS, DISPATCH_RUN } from '../data/dispatch-data';
import { Badge, Button, Panel } from './primitives';
import {
  IconAlert, IconCheck, IconChevron, IconBranch,
  IconExternal, IconBell, IconUser,
} from './icons';

type Lens = 'board' | 'people' | 'twin';
type KindFilter = 'all' | DispatchKind;
type BadgeTone = 'default' | 'blue' | 'accent' | 'green' | 'red' | 'purple' | 'amber';

interface StatusMeta {
  label: string;
  color: string;
  tone: BadgeTone;
}

const STATUS_META: Record<DispatchStatus, StatusMeta> = {
  'pending-ack': { label: '待接收', color: 'var(--text-tertiary)', tone: 'default' },
  acked:         { label: '已接收', color: 'var(--blue-600)',     tone: 'blue' },
  'in-progress': { label: '处理中', color: 'var(--accent)',       tone: 'accent' },
  done:          { label: '已完成', color: 'var(--green-600)',    tone: 'green' },
  overdue:       { label: '逾期',   color: 'var(--red-600)',      tone: 'red' },
  escalated:     { label: '已升级', color: 'var(--purple-600)',   tone: 'purple' },
};

/* 闭环板泳道顺序（逾期/升级不在此列，抽到顶部专区） */
const LANES: { key: DispatchStatus; label: string }[] = [
  { key: 'pending-ack', label: '待接收' },
  { key: 'acked', label: '已接收' },
  { key: 'in-progress', label: '处理中' },
  { key: 'done', label: '已完成' },
];

const KIND_LABEL: Record<DispatchKind, string> = { risk: '风险', task: '任务' };
const KIND_TONE: Record<DispatchKind, BadgeTone> = { risk: 'red', task: 'blue' };

function isAlert(s: DispatchStatus): boolean {
  return s === 'overdue' || s === 'escalated';
}

function nowLabel(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, '0');
  return `${p(d.getHours())}:${p(d.getMinutes())}`;
}

/* ════════════ 头像 ════════════ */
function Avatar({ text, dim = false }: { text: string; dim?: boolean }) {
  return (
    <span style={{
      width: 22, height: 22, borderRadius: '50%', flexShrink: 0,
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      fontSize: 9, fontWeight: 700, letterSpacing: '-.02em',
      background: dim ? 'var(--zinc-100)' : 'var(--accent-muted)',
      color: dim ? 'var(--text-tertiary)' : 'var(--accent)',
      fontFamily: 'var(--font-mono)',
    }}>{text}</span>
  );
}

/* ════════════ 状态点 ════════════ */
function StatusDot({ status }: { status: DispatchStatus }) {
  const m = STATUS_META[status];
  return <span style={{ width: 7, height: 7, borderRadius: '50%', background: m.color, flexShrink: 0 }} />;
}

/* ════════════ SLA / 倒计时 chip ════════════ */
function DueChip({ item }: { item: DispatchItem }) {
  const overdue = item.status === 'overdue';
  return (
    <span style={{
      fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 600,
      color: overdue ? 'var(--red-600)' : 'var(--text-tertiary)',
      whiteSpace: 'nowrap',
    }}>
      {overdue && item.overdueBy ? `逾期 ${item.overdueBy}` : item.due}
    </span>
  );
}

/* ════════════ 单张下发卡（可展开） ════════════ */
interface CardProps {
  item: DispatchItem;
  expanded: boolean;
  onToggle: () => void;
  onUrge: () => void;
  onEscalate: () => void;
  onDone: () => void;
}

function DispatchCard({ item, expanded, onToggle, onUrge, onEscalate, onDone }: CardProps) {
  const m = STATUS_META[item.status];
  const alert = isAlert(item.status);
  return (
    <div style={{
      borderRadius: 'var(--radius-md)',
      border: `1px solid ${alert ? 'var(--red-100)' : 'var(--border)'}`,
      background: alert ? 'var(--red-50)' : 'var(--surface)',
      overflow: 'hidden',
    }}>
      {/* 收起态：类型 + 标题 + owner + SLA + 状态点 */}
      <div
        onClick={onToggle}
        style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 9px', cursor: 'pointer' }}
      >
        <Badge tone={KIND_TONE[item.kind]} size="xs">{KIND_LABEL[item.kind]}</Badge>
        <span style={{
          flex: 1, minWidth: 0, fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-primary)',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>{item.title}</span>
        <Avatar text={item.owner.avatar} />
        <DueChip item={item} />
        <StatusDot status={item.status} />
        <span style={{ display: 'flex', color: 'var(--text-tertiary)', transform: expanded ? 'rotate(180deg)' : 'none', transition: 'transform .15s' }}>
          <IconChevron size={12} direction="down" />
        </span>
      </div>

      {/* 展开态：溯源链 + 影响 + 回执历史 + 动作 */}
      {expanded && (
        <div style={{ padding: '2px 10px 10px', borderTop: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <Row label="责任人">
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-primary)' }}>
              {item.owner.name} · {item.owner.role}
            </span>
            <Badge tone={m.tone} size="xs">{m.label}</Badge>
          </Row>

          <Row label="溯源">
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: 'var(--text-secondary)' }}>
              <IconBranch size={11} color="var(--text-tertiary)" />
              研判 #{item.source.deliverability}
              {item.parentRiskId && <>{' → '}风险 {item.parentRiskId}</>}
              {item.source.proposalRef && <>{' → '}{item.source.proposalRef}</>}
            </span>
          </Row>

          <Row label="影响">
            <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{item.impact.route}</span>
            <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>· {item.impact.drift}</span>
            {item.impact.room && (
              <Badge tone="default" size="xs">{item.impact.room}{item.impact.pod ? ` · ${item.impact.pod}` : ''}</Badge>
            )}
          </Row>

          {/* 回执历史 */}
          <Row label="回执">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                {item.dispatchedAt} 下发 · {item.channel}
              </span>
              {(item.acks ?? []).map((a, i) => (
                <span key={i} style={{ fontSize: 10, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                  {a.ts} · {a.actor} · {a.note}
                </span>
              ))}
            </div>
          </Row>

          {/* 闭环回流提示：完成的项明确写出缩小了多少偏差 */}
          {item.status === 'done' && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6,
              fontSize: 11, color: 'var(--green-700)',
              background: 'var(--green-50)', border: '1px solid var(--green-100)',
              borderRadius: 'var(--radius-sm)', padding: '5px 8px',
            }}>
              <IconCheck size={12} color="var(--green-600)" />
              已闭环 · {item.impact.drift}
            </div>
          )}

          {/* 动作 */}
          {item.status !== 'done' && (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <Button variant="ghost" size="sm" icon={<IconBell size={12} />} onClick={onUrge}>催办</Button>
              {item.status !== 'escalated' && (
                <Button variant="danger" size="sm" icon={<IconAlert size={12} />} onClick={onEscalate}>升级 PD</Button>
              )}
              <Button variant="secondary" size="sm" icon={<IconCheck size={12} />} onClick={onDone}>标记完成</Button>
              <a
                href="/plan?view=risk"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: 'var(--accent)', textDecoration: 'none', marginLeft: 'auto', alignSelf: 'center' }}
              >
                档案库 <IconExternal size={11} color="var(--accent)" />
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
      <span style={{ flexShrink: 0, width: 40, fontSize: 10, color: 'var(--text-tertiary)', fontWeight: 600, paddingTop: 2 }}>{label}</span>
      <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>{children}</div>
    </div>
  );
}

/* ════════════ 回执条（一眼健康度） ════════════ */
function ReceiptBar({ items }: { items: DispatchItem[] }) {
  const counts: Record<DispatchStatus, number> = {
    'pending-ack': 0, acked: 0, 'in-progress': 0, done: 0, overdue: 0, escalated: 0,
  };
  for (const it of items) counts[it.status] += 1;
  const people = new Set(items.map(i => i.owner.name)).size;
  const ackTotal = items.reduce((s, i) => s + (i.acks?.length ?? 0), 0);

  const order: DispatchStatus[] = ['pending-ack', 'acked', 'in-progress', 'done', 'overdue', 'escalated'];
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', fontSize: 'var(--text-xs)' }}>
      {order.filter(k => counts[k] > 0).map(k => {
        const m = STATUS_META[k];
        return (
          <span key={k} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: 'var(--text-secondary)' }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: m.color }} />
            {m.label}
            <b style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{counts[k]}</b>
          </span>
        );
      })}
      <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 5, color: 'var(--text-tertiary)' }}>
        <IconUser size={12} color="var(--text-tertiary)" />
        覆盖 {people} 人 · 回执 {ackTotal} 次
      </span>
    </div>
  );
}

/* ════════════ 镜头 1：闭环状态板（默认） ════════════ */
function BoardLens({ items, expanded, setExpanded, handlers }: LensProps) {
  const alerts = items.filter(i => isAlert(i.status));
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* 逾期 / 升级专区：抽到最顶 */}
      {alerts.length > 0 && (
        <div style={{
          border: '1px solid var(--red-100)', borderRadius: 'var(--radius-md)',
          background: 'var(--red-50)', padding: 10,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            <IconAlert size={13} color="var(--red-600)" />
            <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--red-700)' }}>
              需要你处理（{alerts.length}）
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {alerts.map(it => (
              <DispatchCard
                key={it.id} item={it}
                expanded={expanded === it.id}
                onToggle={() => setExpanded(expanded === it.id ? null : it.id)}
                {...handlers(it)}
              />
            ))}
          </div>
        </div>
      )}

      {/* 四泳道 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, alignItems: 'start' }}>
        {LANES.map(lane => {
          const laneItems = items.filter(i => i.status === lane.key);
          const m = STATUS_META[lane.key];
          return (
            <div key={lane.key} style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingBottom: 4, borderBottom: `2px solid ${m.color}` }}>
                <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--text-primary)' }}>{lane.label}</span>
                <span style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>{laneItems.length}</span>
              </div>
              {laneItems.length === 0
                ? <div style={{ fontSize: 10, color: 'var(--text-tertiary)', padding: '6px 2px' }}>—</div>
                : laneItems.map(it => (
                  <DispatchCard
                    key={it.id} item={it}
                    expanded={expanded === it.id}
                    onToggle={() => setExpanded(expanded === it.id ? null : it.id)}
                    {...handlers(it)}
                  />
                ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ════════════ 镜头 2：责任人 ════════════ */
function PeopleLens({ items, expanded, setExpanded, handlers }: LensProps) {
  const byOwner = new Map<string, DispatchItem[]>();
  for (const it of items) {
    const arr = byOwner.get(it.owner.name) ?? [];
    arr.push(it);
    byOwner.set(it.owner.name, arr);
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {Array.from(byOwner.entries()).map(([name, list]) => {
        const owner = list[0]?.owner;
        const done = list.filter(i => i.status === 'done').length;
        const overdue = list.filter(i => isAlert(i.status)).length;
        const pct = Math.round((done / list.length) * 100);
        return (
          <div key={name} style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', background: 'var(--surface)', padding: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <Avatar text={owner?.avatar ?? '??'} />
              <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-primary)' }}>{name}</span>
              <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{owner?.role}</span>
              <span style={{ marginLeft: 'auto', display: 'inline-flex', gap: 8, alignItems: 'center' }}>
                {overdue > 0 && <Badge tone="red" size="xs">逾期 {overdue}</Badge>}
                <span style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
                  完成 {done}/{list.length}
                </span>
              </span>
            </div>
            {/* 完成度条（仅由下发项派生，不杜撰负载） */}
            <div style={{ height: 4, borderRadius: 4, background: 'var(--zinc-100)', overflow: 'hidden', marginBottom: 8 }}>
              <div style={{ height: '100%', width: `${pct}%`, background: overdue > 0 ? 'var(--red-600)' : 'var(--green-600)', transition: 'width .4s ease' }} />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {list.map(it => (
                <DispatchCard
                  key={it.id} item={it}
                  expanded={expanded === it.id}
                  onToggle={() => setExpanded(expanded === it.id ? null : it.id)}
                  {...handlers(it)}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ════════════ 镜头 3：孪生空间叠加 ════════════ */
function TwinLens({ items, expanded, setExpanded, handlers }: LensProps) {
  const byRoom = new Map<string, DispatchItem[]>();
  for (const it of items) {
    const room = it.impact.room ?? '未关联机房';
    const arr = byRoom.get(room) ?? [];
    arr.push(it);
    byRoom.set(room, arr);
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
        按机房锚定未闭环下发项 · 点击展开该位置相关项（与 3D 底座孪生红叉点位对齐）
      </div>
      {Array.from(byRoom.entries()).map(([room, list]) => {
        const open = list.filter(i => i.status !== 'done');
        const hasAlert = list.some(i => isAlert(i.status));
        return (
          <div key={room} style={{
            border: `1px solid ${hasAlert ? 'var(--red-100)' : 'var(--border)'}`,
            borderRadius: 'var(--radius-md)',
            background: hasAlert ? 'var(--red-50)' : 'var(--surface)', padding: 10,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <span style={{ fontSize: 'var(--text-sm)', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{room}</span>
              {open.length > 0
                ? <Badge tone={hasAlert ? 'red' : 'amber'} size="xs">未闭环 {open.length}</Badge>
                : <Badge tone="green" size="xs">已闭环</Badge>}
              <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-tertiary)' }}>共 {list.length} 项</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {list.map(it => (
                <DispatchCard
                  key={it.id} item={it}
                  expanded={expanded === it.id}
                  onToggle={() => setExpanded(expanded === it.id ? null : it.id)}
                  {...handlers(it)}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

interface LensProps {
  items: DispatchItem[];
  expanded: string | null;
  setExpanded: (id: string | null) => void;
  handlers: (it: DispatchItem) => { onUrge: () => void; onEscalate: () => void; onDone: () => void };
}

/* ════════════ 主组件 ════════════ */
export function DispatchTracker() {
  const [items, setItems] = useState<DispatchItem[]>(
    () => DISPATCH_ITEMS.map(d => ({ ...d, acks: d.acks ? [...d.acks] : [] })),
  );
  const [lens, setLens] = useState<Lens>('board');
  const [kind, setKind] = useState<KindFilter>('all');
  const [expanded, setExpanded] = useState<string | null>(null);

  const visible = items.filter(it => (kind === 'all' ? true : it.kind === kind));

  function patch(id: string, fn: (it: DispatchItem) => DispatchItem) {
    setItems(prev => prev.map(it => (it.id === id ? fn(it) : it)));
  }
  const handlers = (it: DispatchItem) => ({
    onUrge: () => patch(it.id, x => ({ ...x, acks: [...(x.acks ?? []), { ts: nowLabel(), actor: '何博 · TD', note: '已催办' }] })),
    onEscalate: () => patch(it.id, x => ({ ...x, status: 'escalated', acks: [...(x.acks ?? []), { ts: nowLabel(), actor: '何博 · TD', note: '已升级至 PD' }] })),
    onDone: () => patch(it.id, x => ({ ...x, status: 'done', acks: [...(x.acks ?? []), { ts: nowLabel(), actor: x.owner.name, note: '已标记完成' }] })),
  });

  const lensProps: LensProps = { items: visible, expanded, setExpanded, handlers };
  const LENS_TABS: { key: Lens; label: string }[] = [
    { key: 'board', label: '闭环板' },
    { key: 'people', label: '按人' },
    { key: 'twin', label: '孪生叠加' },
  ];
  const KIND_TABS: { key: KindFilter; label: string }[] = [
    { key: 'all', label: '全部' },
    { key: 'risk', label: '只风险' },
    { key: 'task', label: '只任务' },
  ];

  return (
    <Panel
      title="下发追踪 · TD 视角"
      subtitle={`研判 #${DISPATCH_RUN.id}（${DISPATCH_RUN.proposalVersion}）· ${items.length} 项 · 经 WeLink 下发`}
      action={
        <Link2 href="/plan?view=task" label="任务档案库 →" />
      }
      style={{ marginBottom: 'var(--sp-4)' }}
    >
      {/* 回执条 */}
      <div style={{ marginBottom: 10 }}>
        <ReceiptBar items={visible} />
      </div>

      {/* 镜头切换 + 类型筛选 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
        <SegTabs<Lens> tabs={LENS_TABS} value={lens} onChange={setLens} primary />
        <span style={{ width: 1, height: 16, background: 'var(--border)' }} />
        <SegTabs<KindFilter> tabs={KIND_TABS} value={kind} onChange={setKind} />
      </div>

      {/* 镜头内容 */}
      {lens === 'board' && <BoardLens {...lensProps} />}
      {lens === 'people' && <PeopleLens {...lensProps} />}
      {lens === 'twin' && <TwinLens {...lensProps} />}
    </Panel>
  );
}

/* 小工具：分段 tab（泛型，复用于镜头/类型） */
function SegTabs<T extends string>({ tabs, value, onChange, primary = false }: {
  tabs: { key: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
  primary?: boolean;
}) {
  return (
    <div style={{ display: 'inline-flex', gap: 4 }}>
      {tabs.map(t => {
        const on = t.key === value;
        return (
          <button
            key={t.key}
            onClick={() => onChange(t.key)}
            style={{
              padding: '3px 10px', borderRadius: 'var(--radius-full)',
              fontSize: 'var(--text-xs)', fontWeight: 500, cursor: 'pointer',
              border: on ? 'none' : '1px solid var(--border)',
              background: on ? (primary ? 'var(--accent)' : 'var(--zinc-800)') : 'transparent',
              color: on ? '#fff' : 'var(--text-secondary)',
              transition: 'background .12s',
            }}
          >{t.label}</button>
        );
      })}
    </div>
  );
}

/* 小工具：纯文字外链（Panel action 用，避免引入 next/link 到本组件） */
function Link2({ href, label }: { href: string; label: string }) {
  return (
    <a href={href} style={{ fontSize: 'var(--text-xs)', color: 'var(--accent)', textDecoration: 'none', whiteSpace: 'nowrap' }}>
      {label}
    </a>
  );
}
