import { useEffect, useRef } from 'react';

interface GatewayLoginProps {
  /** 提交账号密码；失败应 throw，成功后再由容器跳转 */
  onSubmit: (account: string, password: string) => Promise<void>;
}

/**
 * GatewayLogin — AIDA-login-page-package 登录页
 * 通过 iframe 加载 public/login-gateway/index.html，表单经 postMessage 桥接回 React。
 */
export function GatewayLogin({ onSubmit }: GatewayLoginProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    function onMessage(e: MessageEvent) {
      const data = e.data;
      if (!data || data.type !== 'aida-gateway-login') return;

      const account = String(data.account ?? '');
      const password = String(data.password ?? '');
      const frame = iframeRef.current?.contentWindow;

      void (async () => {
        try {
          await onSubmit(account, password);
        } catch (err) {
          const message = err instanceof Error ? err.message : '登录失败，请重试';
          frame?.postMessage({ type: 'aida-gateway-login-error', message }, '*');
        }
      })();
    }

    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [onSubmit]);

  return (
    <iframe
      ref={iframeRef}
      title="AIDA 登录"
      src="/login-gateway/index.html"
      style={{
        position: 'fixed',
        inset: 0,
        width: '100vw',
        height: '100vh',
        border: 'none',
        display: 'block',
      }}
    />
  );
}
