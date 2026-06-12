import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAidaSession } from './aida-session';
import { useCurrentProject } from './current-project';

/** 清除会话并回到登录页（退出按钮统一入口）。 */
export function useLogout() {
  const navigate = useNavigate();
  const { logout, logoutLocal } = useAidaSession();
  const { clearCurrentProject } = useCurrentProject();

  return useCallback(async () => {
    try {
      await logout();
    } catch (err) {
      console.warn('[AIDA logout] 服务端注销失败，已清除本地会话', err);
      logoutLocal();
    }
    clearCurrentProject();
    navigate('/login', { replace: true });
  }, [logout, logoutLocal, clearCurrentProject, navigate]);
}
