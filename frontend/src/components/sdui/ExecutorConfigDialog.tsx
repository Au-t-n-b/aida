/**
 * ExecutorConfigDialog — 大盘旁路配置调测执行机（IP + SK），不经过 LangGraph 步骤 7。
 */
import { useEffect, useState } from 'react';
import { Button } from '@/components/primitives';

export interface ExecutorConfigDialogProps {
  open: boolean;
  initialIp?: string;
  initialSk?: string;
  saving?: boolean;
  error?: string | null;
  onSave: (ip: string, sk: string) => void;
  onClose: () => void;
}

export function ExecutorConfigDialog({
  open,
  initialIp = '',
  initialSk = '',
  saving = false,
  error = null,
  onSave,
  onClose,
}: ExecutorConfigDialogProps) {
  const [ip, setIp] = useState(initialIp);
  const [sk, setSk] = useState(initialSk);

  useEffect(() => {
    if (open) {
      setIp(initialIp);
      setSk(initialSk);
    }
  }, [open, initialIp, initialSk]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="executor-config-title"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1200,
        display: 'grid',
        placeItems: 'center',
        background: 'rgba(15, 23, 42, 0.35)',
        padding: 16,
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 400,
          background: 'var(--c-surface, #fff)',
          border: '1px solid var(--c-border, #e2e8f0)',
          borderRadius: 10,
          boxShadow: '0 12px 40px rgba(15, 23, 42, 0.12)',
          padding: '16px 18px 14px',
        }}
        onClick={e => e.stopPropagation()}
      >
        <div
          id="executor-config-title"
          style={{ fontSize: 14, fontWeight: 650, color: 'var(--c-text-1, #0f172a)', marginBottom: 4 }}
        >
          配置执行机
        </div>
        <div style={{ fontSize: 12, color: 'var(--c-text-muted, #64748b)', marginBottom: 14, lineHeight: 1.5 }}>
          保存后写入 ProjectData/plan/RunTime/toolkit_executor.json，不影响当前主线进度。
        </div>

        <label style={{ display: 'block', marginBottom: 10 }}>
          <span style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4, color: '#334155' }}>IP</span>
          <input
            type="text"
            value={ip}
            onChange={e => setIp(e.target.value)}
            placeholder="100.100.166.137"
            autoComplete="off"
            style={{
              width: '100%',
              boxSizing: 'border-box',
              padding: '8px 10px',
              fontSize: 13,
              borderRadius: 6,
              border: '1px solid var(--c-border, #e2e8f0)',
              fontFamily: 'var(--font-mono)',
            }}
          />
        </label>

        <label style={{ display: 'block', marginBottom: 12 }}>
          <span style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4, color: '#334155' }}>SK</span>
          <input
            type="password"
            value={sk}
            onChange={e => setSk(e.target.value)}
            placeholder="secret_key"
            autoComplete="off"
            style={{
              width: '100%',
              boxSizing: 'border-box',
              padding: '8px 10px',
              fontSize: 13,
              borderRadius: 6,
              border: '1px solid var(--c-border, #e2e8f0)',
              fontFamily: 'var(--font-mono)',
            }}
          />
        </label>

        {error ? (
          <div style={{ marginBottom: 10, fontSize: 12, color: '#b45309' }}>{error}</div>
        ) : null}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <Button variant="secondary" size="sm" onClick={onClose} disabled={saving}>
            取消
          </Button>
          <Button
            variant="primary"
            size="sm"
            disabled={saving || !ip.trim() || !sk.trim()}
            onClick={() => onSave(ip.trim(), sk.trim())}
          >
            {saving ? '保存中…' : '保存'}
          </Button>
        </div>
      </div>
    </div>
  );
}
