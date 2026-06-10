/**
 * SduiFilePicker — HITL 文件上传卡
 *
 * 交互流程：
 *   1. 用户点击区域 → 打开系统文件选择器
 *   2. 选完文件 → 显示文件列表 + 「上传并继续」按钮
 *   3. 点击按钮 → 上传中（spinner）→ 成功/失败提示
 *
 * 不再「选完立即上传」：给用户确认机会，也避免把后端 resume 和前端状态更新搞成竞态。
 */
import { useRef, useState } from 'react';
import { useSduiRuntime } from './SduiContext';
import type { SduiFilePickerNode } from '@/lib/sdui';

type Props = Omit<SduiFilePickerNode, 'type' | 'id' | 'flex'>;

type UploadStatus = 'idle' | 'uploading' | 'success' | 'error';

export function SduiFilePicker({
  purpose,
  label,
  helpText,
  accept = '*/*',
  multiple = true,
  stepId,
}: Props) {
  const { onUpload } = useSduiRuntime();
  const inputRef = useRef<HTMLInputElement>(null);
  const [pending, setPending] = useState<File[]>([]);
  const [status, setStatus] = useState<UploadStatus>('idle');
  const [errMsg, setErrMsg] = useState('');

  // ── 选择文件（不自动上传，只暂存）─────────────────────────────────────────
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files ?? []);
    if (selected.length > 0) {
      setPending(selected);
      setStatus('idle');
      setErrMsg('');
    }
    // 清空 input.value，使同一文件可以重复选择
    e.target.value = '';
  };

  // ── 点「上传并继续」───────────────────────────────────────────────────────
  const handleConfirm = async () => {
    if (!pending.length) return;
    setStatus('uploading');
    setErrMsg('');
    try {
      // 把 File[] 转成 FileList-like：构造 DataTransfer（浏览器支持）
      const dt = new DataTransfer();
      for (const f of pending) dt.items.add(f);
      await onUpload(dt.files, purpose ?? 'hitl', stepId);
      setStatus('success');
    } catch (e) {
      setStatus('error');
      setErrMsg(e instanceof Error ? e.message : '上传失败，请重试');
    }
  };

  const isUploading = status === 'uploading';
  const isDone = status === 'success';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* 标题 */}
      {label && (
        <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-primary)' }}>
          {label}
        </div>
      )}

      {/* 说明文字 */}
      {helpText && (
        <div style={{
          fontSize: 'var(--text-xs)', color: 'var(--text-secondary)',
          whiteSpace: 'pre-line', lineHeight: 1.6,
          padding: '8px 10px',
          background: 'var(--zinc-50)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border)',
        }}>
          {helpText}
        </div>
      )}

      {/* 拖放/点击区域 */}
      {!isDone && (
        <div
          onClick={() => !isUploading && inputRef.current?.click()}
          style={{
            border: `2px dashed ${pending.length ? 'var(--blue-400)' : 'var(--border)'}`,
            borderRadius: 'var(--radius-lg)',
            padding: '18px 16px',
            textAlign: 'center',
            cursor: isUploading ? 'not-allowed' : 'pointer',
            background: pending.length ? 'var(--blue-50)' : 'var(--surface)',
            transition: 'all .15s',
            opacity: isUploading ? 0.6 : 1,
          }}
        >
          {pending.length === 0 ? (
            <>
              <div style={{ fontSize: '20px', marginBottom: 6 }}>📂</div>
              <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                点击选择文件
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginTop: 3 }}>
                {multiple ? '可多选' : '单文件'} · {accept === '*/*' ? '所有格式' : accept}
              </div>
            </>
          ) : (
            <>
              <div style={{ fontSize: '16px', marginBottom: 4 }}>📄</div>
              <div style={{ fontSize: 'var(--text-sm)', fontWeight: 500, color: 'var(--blue-700)' }}>
                已选 {pending.length} 个文件
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: 3 }}>
                {pending.map(f => f.name).join('、')}
              </div>
              {!isUploading && (
                <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginTop: 4 }}>
                  点此更换文件
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* 隐藏 input */}
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        style={{ display: 'none' }}
        onChange={handleChange}
      />

      {/* 成功态 */}
      {isDone && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '10px 14px',
          borderRadius: 'var(--radius-md)',
          background: 'var(--green-50)',
          border: '1px solid var(--green-200)',
          fontSize: 'var(--text-sm)', color: 'var(--green-700)',
        }}>
          <span>✅</span>
          <span>文件已上传，正在继续工勘流程…</span>
        </div>
      )}

      {/* 错误提示 */}
      {status === 'error' && (
        <div style={{
          padding: '8px 12px',
          borderRadius: 'var(--radius-md)',
          background: 'var(--red-50)',
          border: '1px solid var(--red-200)',
          fontSize: 'var(--text-xs)', color: 'var(--red-700)',
        }}>
          ⚠️ {errMsg}
        </div>
      )}

      {/* 确认按钮 */}
      {!isDone && pending.length > 0 && (
        <button
          onClick={() => void handleConfirm()}
          disabled={isUploading}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            padding: '9px 18px',
            borderRadius: 'var(--radius-md)',
            border: 'none',
            background: isUploading ? 'var(--zinc-300)' : 'var(--blue-600)',
            color: isUploading ? 'var(--text-tertiary)' : '#fff',
            fontSize: 'var(--text-sm)', fontWeight: 600,
            cursor: isUploading ? 'not-allowed' : 'pointer',
            transition: 'background .15s',
          }}
        >
          {isUploading ? (
            <>
              <span style={{
                display: 'inline-block', width: 14, height: 14,
                borderRadius: '50%',
                border: '2px solid rgba(255,255,255,0.4)',
                borderTopColor: '#fff',
                animation: 'spin 0.8s linear infinite',
              }} />
              上传中…
            </>
          ) : (
            `上传 ${pending.length} 个文件并继续`
          )}
        </button>
      )}

      {/* spin 动画（如果全局 CSS 没有则这里注入） */}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
