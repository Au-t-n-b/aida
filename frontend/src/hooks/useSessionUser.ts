import { useMemo } from 'react';
import { useAidaSession } from '@/lib/aida-session';
import { resolveSessionUser, type SessionUserView } from '@/lib/session-user';

export function useSessionUser(): SessionUserView {
  const { session } = useAidaSession();
  return useMemo(() => resolveSessionUser(session), [session]);
}
