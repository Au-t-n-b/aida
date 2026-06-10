'use client';

import { useState } from 'react';
import ParticleBg from '../particle-bg';

// --------------------------------------------------------------------------
// Sub-components
// --------------------------------------------------------------------------

interface FieldProps {
  label: string;
  type: string;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
}

function Field({ label, type, placeholder, value, onChange }: FieldProps) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <span style={{ fontSize: 13, fontWeight: 500, color: '#3f3f46', letterSpacing: '.01em' }}>
        {label}
      </span>
      <input
        type={type}
        placeholder={placeholder}
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{
          height: 44, padding: '0 16px', fontSize: 15, color: '#18181b',
          border: '1px solid #e4e4e7', borderRadius: 8, outline: 'none',
          background: '#ffffff',
          transition: 'border-color .15s, box-shadow .15s',
        }}
        onFocus={e => {
          e.target.style.borderColor = '#18181b';
          e.target.style.boxShadow  = '0 0 0 1px #18181b';
        }}
        onBlur={e => {
          e.target.style.borderColor = '#e4e4e7';
          e.target.style.boxShadow  = 'none';
        }}
      />
    </label>
  );
}

function Remember({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      style={{
        display: 'flex', alignItems: 'center', gap: 8,
        background: 'none', border: 'none', padding: 0,
        cursor: 'pointer', color: '#3f3f46', fontSize: 13, fontFamily: 'inherit',
      }}
    >
      <span style={{
        width: 18, height: 18, borderRadius: 4,
        display: 'grid', placeItems: 'center',
        border: on ? '1px solid #18181b' : '1px solid #d4d4d8',
        background: on ? '#18181b' : '#ffffff',
        transition: 'background .18s ease, border-color .18s ease',
        flexShrink: 0,
      }}>
        <svg
          width="11" height="11" viewBox="0 0 12 12" fill="none"
          style={{
            opacity: on ? 1 : 0,
            transform: on ? 'scale(1)' : 'scale(0.5)',
            transition: 'opacity .18s ease, transform .18s ease',
          }}
        >
          <path d="M2.5 6.3 L5 8.7 L9.5 3.5" stroke="#fff" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      记住我
    </button>
  );
}

// --------------------------------------------------------------------------
// AidaMark – transparent logo + wordmark (floats over particles)
// --------------------------------------------------------------------------

function AidaMark({ size = 60, gap = 14 }: { size?: number; gap?: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap }}>
      <div style={{
        position: 'relative', width: size, height: size,
        flex: '0 0 auto', display: 'grid', placeItems: 'center',
      }}>
        {/* whisper-blur halo keeps the mark legible over particles */}
        <div style={{
          position: 'absolute', inset: -6, borderRadius: 18,
          backdropFilter: 'blur(3px)', WebkitBackdropFilter: 'blur(3px)',
          background: 'radial-gradient(62% 62% at 50% 44%, rgba(255,255,255,0.5), transparent 76%)',
        }} />
        <img
          src="/logo-aida-mark.png"
          alt="AIDA"
          style={{
            position: 'relative', display: 'block',
            width: '100%', height: '100%', objectFit: 'contain',
            filter: 'drop-shadow(0 4px 10px rgba(15,23,42,0.12))',
          }}
        />
      </div>
      <span style={{ fontSize: size * 0.34, fontWeight: 700, letterSpacing: '0.04em', color: '#18181b' }}>
        AIDA
      </span>
    </div>
  );
}

// --------------------------------------------------------------------------
// Main screen
// --------------------------------------------------------------------------

export default function LoginScreen() {
  const [account,  setAccount]  = useState('');
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(false);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState('');

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!account || !password) { setError('请填写账号和密码'); return; }
    setError('');
    setLoading(true);
    await new Promise<void>(r => setTimeout(r, 800));
    setLoading(false);
    /* 原生导航 — 在 file:// / localhost / npm run dev 三种模式下都能工作 */
    if (typeof window !== 'undefined') {
      window.location.assign('../landing/');
    }
  }

  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '1.1fr 1fr',
      height: '100vh', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
      color: '#0f172a', background: '#ffffff',
    }}>

      {/* ── Left brand panel ── */}
      <div style={{ position: 'relative', overflow: 'hidden', borderRight: '1px solid #eef2f6' }}>
        <ParticleBg />

        <div style={{
          position: 'relative', zIndex: 1, height: '100%',
          paddingLeft: 64, paddingTop: 64, paddingBottom: 56, paddingRight: 56,
          display: 'flex', flexDirection: 'column', alignItems: 'flex-start',
        }}>
          {/* Hero: logo + headline + subtitle — left-aligned (Linear / Vercel rhythm) */}
          <div style={{
            flex: 1, display: 'flex', flexDirection: 'column',
            alignItems: 'flex-start', justifyContent: 'center',
          }}>
            <AidaMark size={60} />

            <h1 style={{
              margin: '64px 0 0', fontSize: 48, lineHeight: 1.18,
              fontWeight: 600, letterSpacing: '0.03em', color: '#18181b',
            }}>
              让每次交付&nbsp;都精准高效
            </h1>

            <div style={{
              marginTop: 24, fontSize: 14, fontWeight: 600,
              letterSpacing: '0.2em', color: '#a1a1aa',
            }}>
              ICT&nbsp;DELIVERY&nbsp;//&nbsp;AI
            </div>
          </div>

          <div style={{ fontSize: 13, color: '#a1a1aa' }}>
            © 2026 AIDA Engineering · 保留所有权利
          </div>
        </div>
      </div>

      {/* ── Right login form ── */}
      <div style={{ display: 'grid', placeItems: 'center', padding: 32 }}>
        <div style={{ width: '100%', maxWidth: 380 }}>
          <h2 style={{ margin: 0, fontSize: 26, fontWeight: 800, letterSpacing: '-.02em', color: '#18181b' }}>
            欢迎回来
          </h2>
          <p style={{ marginTop: 8, marginBottom: 40, fontSize: 15, color: '#71717a' }}>
            请登录您的企业账户
          </p>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <Field
              label="账户"
              type="text"
              placeholder="name@company.com"
              value={account}
              onChange={setAccount}
            />
            <Field
              label="密码"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={setPassword}
            />

            {/* Fix 2+3: zinc-600 base color, extra top spacing for breathing room */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 13, marginTop: 8 }}>
              <Remember on={remember} onToggle={() => setRemember(v => !v)} />
              <button
                type="button"
                style={{
                  color: '#52525b', background: 'none', border: 'none', padding: 0,
                  cursor: 'pointer', fontWeight: 500, fontSize: 13, fontFamily: 'inherit',
                  transition: 'color .15s',
                }}
                onMouseEnter={e => (e.currentTarget.style.color = '#18181b')}
                onMouseLeave={e => (e.currentTarget.style.color = '#52525b')}
              >
                忘记密码？
              </button>
            </div>

            {error && (
              <div style={{
                fontSize: 13, color: '#dc2626', padding: '8px 12px',
                background: '#fef2f2', borderRadius: 6, border: '1px solid #fecaca',
              }}>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              style={{
                height: 48, marginTop: 4, border: 'none', borderRadius: 8,
                cursor: loading ? 'not-allowed' : 'pointer',
                background: '#18181b', color: '#fafafa',
                fontSize: 15, fontWeight: 600, letterSpacing: '.08em',
                boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.10), 0 1px 2px rgba(0,0,0,0.08)',
                transition: 'background .15s, transform .12s, box-shadow .15s',
                opacity: loading ? 0.7 : 1,
              }}
              onMouseEnter={e => { if (!loading) { e.currentTarget.style.background = '#27272a'; e.currentTarget.style.transform = 'translateY(-1px)'; }}}
              onMouseLeave={e => { e.currentTarget.style.background = '#18181b'; e.currentTarget.style.transform = 'translateY(0)'; }}
              onMouseDown={e => { e.currentTarget.style.background = '#0f0f11'; e.currentTarget.style.transform = 'translateY(0)'; }}
              onMouseUp={e => { e.currentTarget.style.background = '#27272a'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
            >
              {loading ? '登录中…' : '登 录'}
            </button>
          </form>

          {/* Fix 1: single baseline, no ghost border — "还没有账户？ 联系管理员开通 · 管理员登录" */}
          <div style={{ marginTop: 24, fontSize: 13, color: '#52525b', textAlign: 'center' }}>
            还没有账户？{' '}
            <a
              href="#"
              style={{ color: '#18181b', fontWeight: 500, textDecoration: 'none', transition: 'all .15s' }}
              onMouseEnter={e => (e.currentTarget.style.textDecoration = 'underline')}
              onMouseLeave={e => (e.currentTarget.style.textDecoration = 'none')}
            >
              联系管理员开通
            </a>
            <span style={{ margin: '0 8px', color: '#d4d4d8' }}>·</span>
            {/* G-2 · 管理员登录入口 · 走单独通道进入 AdminShell */}
            <button
              type="button"
              onClick={() => {
                if (typeof window !== 'undefined') window.location.assign('../admin/?role=admin');
              }}
              style={{
                fontSize: 13, color: '#52525b',
                background: 'none', border: 'none', padding: 0,
                cursor: 'pointer', fontFamily: 'inherit', fontWeight: 500,
                transition: 'color .15s',
              }}
              onMouseEnter={e => (e.currentTarget.style.color = '#18181b')}
              onMouseLeave={e => (e.currentTarget.style.color = '#52525b')}
              title="以管理员身份登录系统级配置"
            >
              管理员登录
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
