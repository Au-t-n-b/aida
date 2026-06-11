/**
 * SduiPreviewModal — 产物/上传文件在线预览
 *
 * 接 SDUI 的 open_preview action：根据扩展名在浏览器侧渲染——
 *   xlsx/xls → SheetJS（多 sheet tab） · docx → mammoth → HTML
 *   pdf/png/jpg → blob <embed>/<img> · 其它 → 下载兜底
 *
 * 文件经后端 GET /agent/{skillId}/artifact?path=<rel> 取（已限定 ProjectData/ 子树）。
 * xlsx / mammoth 走动态 import，不进主包；仅预览时按需加载。
 * 设计沿用 aida 浅色 token，不照搬 nanobot 深色主题。
 */
import { useEffect, useState } from 'react';

const AGENT_BASE = import.meta.env.VITE_AGENT_BASE || 'http://127.0.0.1:7401';

// 仅声明本组件实际调用的 API，避免依赖 xlsx/mammoth 自带类型（库未安装时也能编译）。
interface XlsxLike {
  read(data: ArrayBuffer, opts: { type: 'array' }): { SheetNames: string[]; Sheets: Record<string, unknown> };
  utils: { sheet_to_html(ws: unknown): string };
}
interface MammothLike {
  convertToHtml(input: { arrayBuffer: ArrayBuffer }): Promise<{ value: string }>;
}

type Props = {
  skillId: string;
  /** 相对 work_root 的产物路径（如 ProjectData/Output/工勘报告.docx）；null = 关闭 */
  path: string | null;
  onClose: () => void;
};

type Status = 'loading' | 'ready' | 'error' | 'unsupported';

function artifactUrl(skillId: string, path: string): string {
  return `${AGENT_BASE}/agent/${skillId}/artifact?path=${encodeURIComponent(path)}`;
}

export function SduiPreviewModal({ skillId, path, onClose }: Props) {
  const [status, setStatus] = useState<Status>('loading');
  const [docHtml, setDocHtml] = useState('');
  const [sheets, setSheets] = useState<Array<{ name: string; html: string }>>([]);
  const [activeSheet, setActiveSheet] = useState(0);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [errMsg, setErrMsg] = useState('');

  const fileName = path ? (path.split('/').pop() ?? path) : '';
  const ext = (fileName.split('.').pop() ?? '').toLowerCase();
  const isImage = ext === 'png' || ext === 'jpg' || ext === 'jpeg' || ext === 'gif' || ext === 'webp';

  // ── 加载 + 解析 ──────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    let createdUrl: string | null = null;
    setStatus('loading');
    setDocHtml('');
    setSheets([]);
    setActiveSheet(0);
    setBlobUrl(null);
    setErrMsg('');

    void (async () => {
      try {
        const res = await fetch(artifactUrl(skillId, path));
        if (!res.ok) throw new Error(`加载失败 (${res.status})`);

        if (ext === 'xlsx' || ext === 'xls') {
          const buf = await res.arrayBuffer();
          const XLSX = (await import('xlsx')) as unknown as XlsxLike;
          const wb = XLSX.read(buf, { type: 'array' });
          const out = wb.SheetNames.map((name: string) => ({
            name,
            html: XLSX.utils.sheet_to_html(wb.Sheets[name]),
          }));
          if (!cancelled) { setSheets(out); setStatus('ready'); }
        } else if (ext === 'docx') {
          const buf = await res.arrayBuffer();
          const mammoth = (await import('mammoth')) as unknown as MammothLike;
          const r = await mammoth.convertToHtml({ arrayBuffer: buf });
          if (!cancelled) { setDocHtml(r.value); setStatus('ready'); }
        } else if (ext === 'pdf' || isImage) {
          const blob = await res.blob();
          createdUrl = URL.createObjectURL(blob);
          if (!cancelled) { setBlobUrl(createdUrl); setStatus('ready'); }
        } else {
          if (!cancelled) setStatus('unsupported');
        }
      } catch (e) {
        if (!cancelled) {
          setStatus('error');
          setErrMsg(e instanceof Error ? e.message : '加载失败');
        }
      }
    })();

    return () => {
      cancelled = true;
      if (createdUrl) URL.revokeObjectURL(createdUrl);
    };
  }, [skillId, path, ext, isImage]);

  // ── Esc 关闭 ─────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!path) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [path, onClose]);

  if (!path) return null;

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 900,
        background: 'rgba(15,23,42,.45)', backdropFilter: 'blur(3px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        animation: 'sdui-preview-fade .16s ease-out both',
      }}
    >
      <style>{`
        @keyframes sdui-preview-fade { from { opacity: 0 } to { opacity: 1 } }
        @keyframes sdui-preview-pop { from { opacity:0; transform:translateY(8px) scale(.99) } to { opacity:1; transform:none } }
        .sdui-xlsx-pane table { width:100%; border-collapse:collapse; font-size:12px; }
        .sdui-xlsx-pane td, .sdui-xlsx-pane th { border:1px solid var(--border); padding:5px 9px; color:var(--text-secondary); white-space:nowrap; }
        .sdui-xlsx-pane tr:first-child td { background:var(--c-surface-2,#f1f5f9); font-weight:600; color:var(--text-primary); position:sticky; top:0; }
        .sdui-docx-pane { line-height:1.8; color:var(--text-primary); font-size:13px; }
        .sdui-docx-pane h1,.sdui-docx-pane h2,.sdui-docx-pane h3 { margin:16px 0 8px; color:var(--text-primary); }
        .sdui-docx-pane p { margin:6px 0; }
        .sdui-docx-pane table { width:100%; border-collapse:collapse; margin:10px 0; }
        .sdui-docx-pane td,.sdui-docx-pane th { border:1px solid var(--border); padding:5px 9px; }
      `}</style>

      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: '90vw', maxWidth: 960, height: '82vh',
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)', display: 'flex', flexDirection: 'column',
          boxShadow: '0 24px 64px rgba(15,23,42,.28)', overflow: 'hidden',
          animation: 'sdui-preview-pop .2s cubic-bezier(.2,.65,.4,1) both',
        }}
      >
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '12px 16px', borderBottom: '1px solid var(--border)', flexShrink: 0,
        }}>
          <span style={{
            fontSize: '9px', fontWeight: 700, fontFamily: 'var(--font-mono)',
            padding: '2px 6px', borderRadius: 4, color: '#fff',
            background: ext === 'docx' ? 'var(--blue-600)' : ext === 'xlsx' ? '#0a7d46' : 'var(--zinc-500)',
            flexShrink: 0, letterSpacing: '.02em',
          }}>
            {(ext || 'file').toUpperCase()}
          </span>
          <span style={{
            flex: 1, fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-primary)',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {fileName}
          </span>
          <a
            href={artifactUrl(skillId, path)}
            download={fileName}
            style={{
              padding: '5px 12px', borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border)', background: 'var(--c-surface-2,#f1f5f9)',
              color: 'var(--text-secondary)', fontSize: 'var(--text-xs)', fontWeight: 600,
              textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 5,
            }}
          >
            ⬇ 下载
          </a>
          <button
            onClick={onClose}
            style={{
              border: 'none', background: 'transparent', cursor: 'pointer',
              fontSize: 18, lineHeight: 1, color: 'var(--text-tertiary)', padding: '2px 6px',
            }}
          >
            ✕
          </button>
        </div>

        {/* xlsx sheet tabs */}
        {status === 'ready' && sheets.length > 1 && (
          <div style={{
            display: 'flex', gap: 0, borderBottom: '1px solid var(--border)',
            flexShrink: 0, overflowX: 'auto', padding: '0 12px',
          }}>
            {sheets.map((s, i) => (
              <button
                key={s.name}
                onClick={() => setActiveSheet(i)}
                style={{
                  padding: '8px 16px', fontSize: '12px', whiteSpace: 'nowrap',
                  border: 'none', background: 'transparent', cursor: 'pointer',
                  color: i === activeSheet ? 'var(--blue-600)' : 'var(--text-tertiary)',
                  borderBottom: `2px solid ${i === activeSheet ? 'var(--blue-600)' : 'transparent'}`,
                  fontWeight: i === activeSheet ? 600 : 400,
                }}
              >
                {s.name}
              </button>
            ))}
          </div>
        )}

        {/* Body */}
        <div style={{ flex: 1, overflow: 'auto', padding: '16px 18px', background: 'var(--surface)' }}>
          {status === 'loading' && (
            <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, color: 'var(--text-tertiary)' }}>
              <span style={{
                width: 26, height: 26, borderRadius: '50%',
                border: '3px solid var(--border)', borderTopColor: 'var(--blue-600)',
                animation: 'spin .8s linear infinite', display: 'block',
              }} />
              <span style={{ fontSize: 'var(--text-xs)' }}>加载中…</span>
              <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
            </div>
          )}

          {status === 'error' && (
            <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10, color: 'var(--text-tertiary)' }}>
              <div style={{ fontSize: 32 }}>⚠️</div>
              <div style={{ fontSize: 'var(--text-sm)' }}>{errMsg}</div>
            </div>
          )}

          {status === 'unsupported' && (
            <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, color: 'var(--text-tertiary)' }}>
              <div style={{ fontSize: 32 }}>📁</div>
              <div style={{ fontSize: 'var(--text-sm)' }}>该类型暂不支持在线预览，请点「下载」查看</div>
            </div>
          )}

          {status === 'ready' && sheets.length > 0 && (
            <div className="sdui-xlsx-pane" dangerouslySetInnerHTML={{ __html: sheets[activeSheet]?.html ?? '' }} />
          )}

          {status === 'ready' && docHtml && (
            <div className="sdui-docx-pane" dangerouslySetInnerHTML={{ __html: docHtml }} />
          )}

          {status === 'ready' && blobUrl && ext === 'pdf' && (
            <embed src={blobUrl} type="application/pdf" style={{ width: '100%', height: '100%', border: 'none', borderRadius: 6, background: '#fff' }} />
          )}

          {status === 'ready' && blobUrl && isImage && (
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <img src={blobUrl} alt={fileName} style={{ maxWidth: '100%', borderRadius: 6 }} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
