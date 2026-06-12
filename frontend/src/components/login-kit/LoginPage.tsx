import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ParticleLogin } from './ParticleLogin';
import { GlassLogin } from './GlassLogin';
import { StyleSwitch, type LoginStyle } from './StyleSwitch';
import { useAidaSession } from '@/lib/aida-session';

/* ──────────────────────────────────────────────────────────────────────────
   LoginPage — 双风格登录页容器（由 aida-auth-kit / DS-X 迁移）
   ----------------------------------------------------------------------------
   · 默认 3D 粒子风格，底部段控件可切到玻璃拟态。
   · 任一风格登录成功 → 跳转项目选择落地页 /landing（沿用原登录的去向）。
   · 粒子页右上「管理员入口」→ /admin?role=admin。
   切换 key 强制重新挂载，确保每次切到玻璃都完整重播入场动画。
   ────────────────────────────────────────────────────────────────────────── */

const DEFAULT_STYLE: LoginStyle = 'glass';

export function LoginPage() {
  const [style, setStyle] = useState<LoginStyle>(DEFAULT_STYLE);
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAidaSession();
  const from =
    typeof location.state === 'object' &&
    location.state &&
    'from' in location.state &&
    typeof (location.state as { from?: unknown }).from === 'string'
      ? (location.state as { from: string }).from
      : '/landing';

  async function handleLogin(account: string, password: string) {
    try {
      await login(account, password, 'K1903');
      navigate(from === '/login' ? '/landing' : from, { replace: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : '登录失败，请重试';
      console.error('[AIDA login] 鉴权失败', { account, message, err });
      throw new Error(message);
    }
  }

  return (
    <>
      {style === 'particle' ? (
        <ParticleLogin
          key="particle"
          onSubmit={handleLogin}
          onAdmin={() => navigate('/admin?role=admin')}
        />
      ) : (
        <GlassLogin key="glass" onSubmit={handleLogin} />
      )}
      <StyleSwitch value={style} onChange={setStyle} />
    </>
  );
}
