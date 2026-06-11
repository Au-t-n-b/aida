/**
 * SduiArtifactGrid — 文件卡网格（移植自 survey-agent.tsx ArtifactGrid + ArtifactCard）
 */
import { useSduiRuntime } from './SduiContext';
import type { SduiArtifactItem, SduiArtifactKind } from '@/lib/sdui';

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

function ArtifactCard({ item, output, index }: { item: SduiArtifactItem; output: boolean; index: number }) {
  const { onAction } = useSduiRuntime();
  const label = kindToExt(item.kind, item.label);
  const isGenerating = item.status === 'generating';
  // 产物卡错开滑入：新产物依次出现（最多 5 项参与错开，之后同步入场）
  const staggerDelay = `${Math.min(index, 5) * 0.06}s`;

  return (
    <div
      title={item.label}
      onClick={() => item.path && !isGenerating && onAction({ kind: 'open_preview', path: item.path })}
      style={{
        display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px',
        background: 'var(--zinc-100)', borderRadius: 'var(--radius-md)',
        borderLeft: output ? '2px solid var(--blue-600)' : '2px solid transparent',
        cursor: item.path && !isGenerating ? 'pointer' : 'default',
        opacity: isGenerating ? 0.6 : 1,
        transition: 'background .12s',
        animation: `sdui-node-in .2s ease-out ${staggerDelay} both`,
      }}
    >
      <div style={{
        width: 24, height: 24, borderRadius: 'var(--radius-sm)',
        background: output ? 'var(--blue-600)' : 'var(--zinc-500)', color: '#fff',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '8px', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '-.02em', flexShrink: 0,
      }}>
        {label}
      </div>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ fontSize: 'var(--text-xs)', fontWeight: 500, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {item.label}
        </div>
        {isGenerating && (
          <div style={{ fontSize: '10px', color: 'var(--text-tertiary)' }}>生成中…</div>
        )}
      </div>
      {output && !isGenerating && (
        <span style={{ fontSize: '10px', color: 'var(--blue-600)', flexShrink: 0 }}>产物</span>
      )}
    </div>
  );
}

export function SduiArtifactGrid({ artifacts, mode, title }: Props) {
  const output = mode === 'output';
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {title && (
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
          <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600, color: 'var(--text-secondary)' }}>{title}</span>
          <span style={{ fontSize: '10px', color: 'var(--text-tertiary)' }}>{artifacts.length} 个</span>
        </div>
      )}
      {artifacts.length === 0 ? (
        <div style={{ padding: '14px 12px', color: 'var(--text-tertiary)', fontSize: 'var(--text-xs)' }}>
          暂无文件
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 8 }}>
          {artifacts.map((item, i) => (
            <ArtifactCard key={item.id ?? item.path ?? i} item={item} output={output} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}
