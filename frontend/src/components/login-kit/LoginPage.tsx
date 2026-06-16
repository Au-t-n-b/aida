import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { GatewayLogin } from './GatewayLogin';
import { GlassLogin } from './GlassLogin';
import { StyleSwitch, type LoginStyle } from './StyleSwitch';
import { useAidaSession } from '@/lib/aida-session';
import { ApiRequestError } from '@/lib/api-error';

const DEFAULT_STYLE: LoginStyle = 'gateway';

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
      await login(account, password);
      navigate(from === '/login' ? '/landing' : from, { replace: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : '登录失败，请重试';
      console.error('[AIDA login] 鉴权失败', { account, message, err });
      if (err instanceof ApiRequestError) throw err;
      throw err instanceof Error ? err : new Error('登录失败，请重试');
    }
  }

  return (
    <>
      {style === 'gateway' ? (
        <GatewayLogin key="gateway" onSubmit={handleLogin} />
      ) : (
        <GlassLogin key="glass" onSubmit={handleLogin} />
      )}
      <StyleSwitch value={style} onChange={setStyle} />
    </>
  );
}
