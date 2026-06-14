/**
 * SduiArtifactGrid — 文件卡网格
 *  - input 模式：紧凑卡片（点击预览）
 *  - output 模式：对齐设计稿 OutputsPanel 行卡 —— 文件名 + 预览 / 下载 / 上传覆盖
 */
import { useRef } from 'react';
import { useSduiRuntime } from './SduiContext';
import type { SduiArtifactItem, SduiArtifactKind } from '@/lib/sdui';

import { agentBaseSync } from '@/lib/agentBase';

const AGENT_BASE = agentBaseSync();

type Props = {
  artifacts: SduiArtifactItem[];
  mode?: 'input' | 'output';
  title?: string;
};

function extLabel(name: string): string {
  const e = (name.split('.').pop() ?? '').toUpperCase();
  return e.slice(0, 4) || 'FILE';
}

function kindToExt(kind?: SduiArtifactKind, label?: string): string {
  if (kind && kind !== 'other') return kind.toUpperCase();
  return extLabel(label ?? '');
}

function artifactUrl(skillId: string | undefined, path: string): string {
  return `${AGENT_BASE}/agent/${skillId ?? ''}/artifact?path=${encodeURIComponent(path)}`;
}

// ── input 模式：紧凑卡 ──────────────────────────────────────────────────────────
function InputCard({ item, index }: { item: SduiArtifactItem; index: number }) {
  const { onAction } = useSduiRuntime();
  const label = kindToExt(item.kind, item.label);
  const isGenerating = item.status === 'generating';
  const staggerDelay = `${Math.min(index, 5) * 0.06}s`;
  return (
    <div
      title={item.label}
      onClick={() => item.path && !isGenerating && onAction({ kind: 'open_preview', path: item.path })}
      style={{
        display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px',
        background: 'var(--zinc-100)', borderRadius: 'var(--radius-md)',
        borderLeft: '2px solid transparent',
        cursor: item.path && !isGenerating ? 'pointer' : 'default',
        opacity: isGenerating ? 0.6 : 1, transition: 'background .12s',
        animation: `sdui-node-in .2s ease-out ${staggerDelay} both`,
      }}
    >
      <div style={{
        width: 24, height: 24, borderRadius: 'var(--radius-sm)',
        background: 'var(--zinc-500)', color: '#fff',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '8px', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '-.02em', flexShrink: 0,
      }}>
        {label}
      </div>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 500, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {item.label}
        </div>
        {isGenerating && <div style={{ fontSize: '10px', color: 'var(--text-tertiary)' }}>生成中…</div>}
      </div>
    </div>
  );
}

// ── output 模式：行卡（预览 / 下载 / 上传覆盖）──────────────────────────────────
const OVERRIDE_MARK = '已覆盖';

function OutputRow({ item, index }: { item: SduiArtifactItem; index: number }) {
  const { onAction, onUpload, skillId } = useSduiRuntime();
  const fileRef = useRef<HTMLInputElement>(null);
  const ext = kindToExt(item.kind, item.label);
  const isGenerating = item.status === 'generating';
  const highlighted = !!item.highlight;
  const staggerDelay = `${Math.min(index, 5) * 0.06}s`;
  const overridden =
    item.badge === OVERRIDE_MARK || item.label.endsWith(` · ${OVERRIDE_MARK}`);
  const fileLabel = overridden
    ? item.label.replace(new RegExp(` · ${OVERRIDE_MARK}$`), '')
    : item.label;
  const canOverride = skillId !== 'system_design' || !!item.path;

  const btn: React.CSSProperties = {
    padding: '4px 11px', fontSize: 12, borderRadius: 5, border: '1px solid var(--border)',
    background: 'var(--surface)', color: 'var(--text-secondary)', cursor: 'pointer', whiteSpace: 'nowrap',
  };
  const btnPrimary: React.CSSProperties = {
    ...btn, border: '1px solid #3551d8', background: '#3551d8', color: '#fff', fontWeight: 500,
    textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4,
  };

  const onPicked = (e: React.ChangeEvent<HTMLInputElement>) => {
    const fs = e.target.files;
    if (fs && fs.length) {
      if (skillId === 'system_design' && item.path) {
        onUpload(fs, `override:${item.path}`);
      } else {
        onUpload(fs, `override_${item.id ?? item.label}`);
      }
    }
    e.target.value = '';
  };

  return (
    <div
      data-art-id={item.id}
      style={{
      display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', borderRadius: 8,
      border: highlighted ? '1px solid #3551d8' : '1px solid var(--border)',
      borderLeft: '3px solid var(--blue-600)',
      background: highlighted ? 'var(--c-bg-soft, #eef4ff)' : 'var(--surface)',
      opacity: isGenerating ? 0.6 : 1,
      animation: highlighted
        ? 'sd-out-pulse 1.5s ease-out infinite'
        : `sdui-stagger .18s ease-out ${staggerDelay} both`,
    }}>
      <input ref={fileRef} type="file" accept=".xlsx,.xls,.csv,.pdf,.docx,.zip" style={{ display: 'none' }} onChange={onPicked} />
      <div style={{
        width: 26, height: 26, borderRadius: 6, background: 'var(--blue-600)', color: '#fff',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '8px', fontWeight: 700, fontFamily: 'var(--font-mono)', flexShrink: 0,
      }}>
        {ext}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{fileLabel}</span>
          {overridden ? (
            <span style={{
              flexShrink: 0, fontSize: 10, fontWeight: 600,
              color: 'var(--c-success-text)', background: 'var(--c-success-soft)',
              borderRadius: 4, padding: '1px 6px',
            }}>
              {OVERRIDE_MARK}
            </span>
          ) : item.badge ? (
            <span style={{
              flexShrink: 0, fontSize: 10, fontWeight: 600, color: '#3551d8',
              background: '#e8edfc', borderRadius: 4, padding: '1px 6px',
            }}>
              {item.badge}
            </span>
          ) : null}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>
          {isGenerating ? '生成中…' : (item.kind ?? 'file').toUpperCase()}
        </div>
      </div>
      {!isGenerating && (
        <div style={{ flexShrink: 0, display: 'flex', gap: 6 }}>
          {item.path && (
            <button style={btn} onClick={() => onAction({ kind: 'open_preview', path: item.path })}>预览</button>
          )}
          <button style={btn} disabled={!canOverride} onClick={() => canOverride && fileRef.current?.click()}>上传覆盖</button>
          {item.path && (
            <a style={btnPrimary} href={artifactUrl(skillId, item.path)} download={item.label}>下载</a>
          )}
        </div>
      )}
    </div>
  );
}

export function SduiArtifactGrid({ artifacts, mode, title }: Props) {
  const output = mode === 'output';
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {title && (
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
          <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)' }}>{title}</span>
          <span style={{ fontSize: '10px', color: 'var(--text-tertiary)' }}>{artifacts.length} 个</span>
        </div>
      )}
      {artifacts.length === 0 ? (
        <div style={{ padding: '14px 12px', color: 'var(--text-tertiary)', fontSize: 'var(--text-xs)' }}>暂无文件</div>
      ) : output ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {artifacts.map((item, i) => (
            <OutputRow key={item.id ?? item.path ?? i} item={item} index={i} />
          ))}
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 8 }}>
          {artifacts.map((item, i) => (
            <InputCard key={item.id ?? item.path ?? i} item={item} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}
