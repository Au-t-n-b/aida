import { useState, type FormEvent } from 'react';
import { registerToClawManager } from '@/lib/claw-manager-client';

interface RegisterModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess?: (username: string) => void;
}

export function RegisterModal({ open, onClose, onSuccess }: RegisterModalProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  if (!open) return null;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setSuccess('');
    const name = username.trim();
    const pass = password.trim();
    const pass2 = confirm.trim();
    if (!name || !pass) {
      setError('请输入用户名和密码');
      return;
    }
    if (pass.length < 6) {
      setError('密码至少 6 位');
      return;
    }
    if (pass !== pass2) {
      setError('两次输入的密码不一致');
      return;
    }

    setLoading(true);
    try {
      const resp = await registerToClawManager({ username: name, password: pass });
      const msg = `注册成功（${resp.username}），请使用新账号登录`;
      setSuccess(msg);
      console.info('[AIDA register] ok', resp);
      onSuccess?.(resp.username);
      window.setTimeout(() => {
        onClose();
        setUsername('');
        setPassword('');
        setConfirm('');
        setSuccess('');
      }, 1200);
    } catch (err) {
      const message = err instanceof Error ? err.message : '注册失败，请稍后重试';
      setError(message);
      console.error('[AIDA register] failed', { username: name, message, err });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="lg-modal-mask" role="presentation" onClick={onClose}>
      <div
        className="lg-modal"
        role="dialog"
        aria-labelledby="lg-register-title"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="lg-modal-head">
          <h3 id="lg-register-title">申请注册</h3>
          <button type="button" className="lg-modal-close" onClick={onClose} aria-label="关闭">
            ✕
          </button>
        </div>
        <p className="lg-modal-desc">创建平台账号后即可登录 AIDA（由数据中心统一建档）。</p>
        <form onSubmit={(e) => void handleSubmit(e)}>
          <div className="lg-field">
            <label htmlFor="lg-reg-user">用户名</label>
            <div className="lg-input-wrap">
              <input
                id="lg-reg-user"
                type="text"
                autoComplete="username"
                placeholder="全局唯一登录名"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={loading}
              />
            </div>
          </div>
          <div className="lg-field">
            <label htmlFor="lg-reg-pass">密码</label>
            <div className="lg-input-wrap">
              <input
                id="lg-reg-pass"
                type="password"
                autoComplete="new-password"
                placeholder="至少 6 位"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading}
              />
            </div>
          </div>
          <div className="lg-field">
            <label htmlFor="lg-reg-pass2">确认密码</label>
            <div className="lg-input-wrap">
              <input
                id="lg-reg-pass2"
                type="password"
                autoComplete="new-password"
                placeholder="再次输入密码"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                disabled={loading}
              />
            </div>
          </div>
          {error ? (
            <div className="lg-error" role="alert">
              {error}
            </div>
          ) : null}
          {success ? (
            <div className="lg-success" role="status">
              {success}
            </div>
          ) : null}
          <button type="submit" className={`lg-submit${loading ? ' loading' : ''}`} disabled={loading}>
            <span className="spin" />
            <span className="label">{loading ? '提交中…' : '提交注册'}</span>
          </button>
        </form>
      </div>
    </div>
  );
}
