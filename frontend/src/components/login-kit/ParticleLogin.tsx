import { useEffect } from 'react';
import particleHtml from './particle-login.html?raw';

/* ──────────────────────────────────────────────────────────────────────────
   ParticleLogin —「粒子」风格登录页
   ----------------------------------------------------------------------------
   由自包含的 HTML 单文件（AIDA 登录 · claw-delivery-ui）整体嵌入：用隔离的
   <iframe srcDoc> 承载，其 html/body 全局样式与 canvas 动画完全沙箱化，不污染
   主应用。登录动作通过 postMessage 桥接回 React：iframe 内表单/SSO 提交后向父窗口
   发 { type: 'aida-particle-login' }，这里转交给容器的 onSubmit（负责鉴权 + 跳转）。
   ────────────────────────────────────────────────────────────────────────── */

interface ParticleLoginProps {
  /** 提交账号密码（容器负责真正的鉴权 + 跳转） */
  onSubmit: (account: string, password: string) => void | Promise<void>;
  /** 兼容旧接口：本风格无管理员入口，保留以免容器报错 */
  onAdmin?: () => void;
}

export function ParticleLogin({ onSubmit }: ParticleLoginProps) {
  useEffect(() => {
    function onMessage(e: MessageEvent) {
      const data = e.data;
      if (data && data.type === 'aida-particle-login') {
        void onSubmit(String(data.account ?? ''), String(data.password ?? ''));
      }
    }
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [onSubmit]);

  return (
    <iframe
      title="AIDA 登录"
      srcDoc={particleHtml}
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
