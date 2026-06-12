import { useEffect, useRef, useState, type FormEvent } from 'react';
import { initDecisionGraph } from './anim/decisionGraph.ts';
import { initGlassIntro } from './anim/glassIntro.ts';
import { RegisterModal } from './RegisterModal';
import './glass-login.css';

interface GlassLoginProps {
  /** 提交账号密码；失败应 throw，成功后再由容器跳转 */
  onSubmit: (account: string, password: string) => Promise<void>;
}

/** AIDA 玻璃 logo（内联 SVG）。 */
function AidaGlassLogo() {
  return (
    <span className="lg-logo">
      <svg viewBox="0 0 120 120" fill="none" aria-label="AIDA">
        <defs>
          <linearGradient id="aidaNavy" x1="60" y1="14" x2="60" y2="104" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#1d3d85" />
            <stop offset="1" stopColor="#0a1c45" />
          </linearGradient>
          <linearGradient id="aidaCyan" x1="37" y1="83" x2="63" y2="96" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#36bfea" />
            <stop offset="1" stopColor="#0d82bb" />
          </linearGradient>
        </defs>
        <path d="M60 14 L104 104 L80 104 L60 56 L40 104 L16 104 Z" fill="url(#aidaNavy)" />
        <path d="M44 83 L63 83 L57 96 L38 96 Z" fill="url(#aidaCyan)" />
      </svg>
    </span>
  );
}

export function GlassLogin({ onSubmit }: GlassLoginProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');
  const [registerOpen, setRegisterOpen] = useState(false);
  const [prefillUser, setPrefillUser] = useState('');

  // 挂载入场编排：决策图 + 光晕点/logo 飞入，二者共用一拍
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const canvas = root.querySelector<HTMLCanvasElement>('#lg-graph');
    const host = root.querySelector<HTMLElement>('.lg-visual');
    let graphDestroy = () => {};
    let startGraph = () => {};
    if (canvas && host) {
      const graph = initDecisionGraph(canvas, host);
      graphDestroy = graph.destroy;
      startGraph = () => graph.start(0);
    }
    const introCleanup = initGlassIntro(root, { startGraph });
    return () => {
      introCleanup();
      graphDestroy();
    };
  }, []);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (loading) return;
    const form = e.currentTarget;
    const account = (form.elements.namedItem('lg-account') as HTMLInputElement).value.trim();
    const password = (form.elements.namedItem('lg-pass') as HTMLInputElement).value.trim();
    if (!account || !password) {
      setError('请输入账号和密码');
      return;
    }

    setError('');
    setDone(false);
    setLoading(true);
    try {
      await onSubmit(account, password);
      setDone(true);
    } catch (err) {
      const message = err instanceof Error ? err.message : '登录失败，请重试';
      setError(message);
      setDone(false);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="lg-root" ref={rootRef}>
      <div className="lg-bg" />
      <div className="lg-bg-scrim" />
      <canvas id="lg-spark" />

      <div className="lg-stage">
        <div className="lg-card" id="lg-card">
          {/* Left: interactive decision-graph visual */}
          <section className="lg-visual">
            <div className="lg-brand">
              <AidaGlassLogo />
              <div>
                <div className="lg-brand-name">AIDA</div>
                <div className="lg-brand-sub">Delivery Intelligence</div>
              </div>
            </div>

            <div className="lg-graph-wrap">
              <canvas id="lg-graph" />
            </div>
            <div className="lg-graph-hint">
              <span className="pip" />
              实时推理 · 决策路径
            </div>
          </section>

          {/* Right: login form */}
          <section className="lg-form-panel">
            <div className="lg-form-head">
              <h2>欢迎回来</h2>
              <p>登录以进入交付态势驾驶舱</p>
            </div>

            <form id="lg-form" autoComplete="off" noValidate onSubmit={handleSubmit}>
              <div className="lg-field">
                <label htmlFor="lg-account">账号 / 邮箱</label>
                <div className="lg-input-wrap">
                  <input
                    id="lg-account"
                    name="lg-account"
                    type="text"
                    placeholder="name@aida.cloud"
                    defaultValue={prefillUser}
                    key={prefillUser || 'lg-account-empty'}
                  />
                  <span className="ic">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                      <path d="M4 6h16v12H4z" stroke="currentColor" strokeWidth="1.5" />
                      <path d="m4 7 8 6 8-6" stroke="currentColor" strokeWidth="1.5" />
                    </svg>
                  </span>
                </div>
              </div>

              <div className="lg-field">
                <label htmlFor="lg-pass">密码</label>
                <div className="lg-input-wrap">
                  <input id="lg-pass" name="lg-pass" type="password" placeholder="••••••••••" />
                  <span className="ic">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                      <rect x="4" y="10" width="16" height="10" rx="2" stroke="currentColor" strokeWidth="1.5" />
                      <path d="M8 10V7a4 4 0 0 1 8 0v3" stroke="currentColor" strokeWidth="1.5" />
                    </svg>
                  </span>
                </div>
              </div>

              <div className="lg-row">
                <label className="lg-check"><input type="checkbox" id="lg-remember" />保持登录</label>
                <button type="button" className="lg-link">忘记密码？</button>
              </div>

              {error ? (
                <div className="lg-error" role="alert">
                  {error}
                </div>
              ) : null}

              <button
                type="submit"
                className={`lg-submit${loading ? ' loading' : ''}${error ? ' lg-submit-error' : ''}`}
                id="lg-submit"
                disabled={loading}
              >
                <span className="spin" />
                <span className="label">{done ? '已进入 ✓' : loading ? '验证中…' : '登录'}</span>
              </button>

              <div className="lg-divider">或</div>

              <button type="button" className="lg-sso" onClick={() => onSubmit('sso@aida.cloud', '')}>
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none">
                  <path d="M12 2 4 6v6c0 5 3.4 8.5 8 10 4.6-1.5 8-5 8-10V6l-8-4Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
                </svg>
                使用企业 SSO 登录
              </button>

              <div className="lg-foot">
                还没有账号？{' '}
                <button type="button" className="lg-link" onClick={() => setRegisterOpen(true)}>
                  申请注册
                </button>
              </div>
            </form>
          </section>
        </div>
      </div>
      <RegisterModal
        open={registerOpen}
        onClose={() => setRegisterOpen(false)}
        onSuccess={(name) => {
          setPrefillUser(name);
          setError('');
        }}
      />
    </div>
  );
}
