import type { ClawUserProfile } from './claw-manager-client';

export type SessionUserView = {
  userId: string;
  username: string;
  displayName: string;
  roleLabel: string;
  avatarInitials: string;
  chatMetaPrefix: string;
  profileHeadline: string;
};

export type SessionUserInput = {
  user?: ClawUserProfile | null;
  role?: string | null;
};

/** 从显示名生成头像缩写（中文取前两字，英文取前两字母大写） */
export function avatarInitialsFromName(name: string): string {
  const s = (name || '').trim();
  if (!s) return 'U';
  if (/[\u4e00-\u9fff]/.test(s)) return s.slice(0, 2);
  return s.slice(0, 2).toUpperCase();
}

export function resolveSessionUser(input: SessionUserInput | null | undefined): SessionUserView {
  const user = input?.user;
  const username = (user?.username || '').trim();
  const userId = (user?.user_id || username || '').trim();
  const displayName = (user?.display_name || '').trim() || username || userId || '用户';
  const roleLabel =
    user?.global_roles?.[0]?.roleName?.trim()
    || (input?.role || '').trim()
    || '交付成员';
  const avatarInitials = avatarInitialsFromName(displayName);
  const chatMetaPrefix = `${displayName} · `;
  const profileHeadline = userId && userId !== displayName
    ? `${displayName} · ${roleLabel} · ${userId}`
    : `${displayName} · ${roleLabel}`;
  return {
    userId,
    username,
    displayName,
    roleLabel,
    avatarInitials,
    chatMetaPrefix,
    profileHeadline,
  };
}

const MOCK_CURRENT_USER_NAMES = new Set(['何博']);

/** 将 mock 当前用户占位名替换为真实登录用户展示名 */
export function substituteMockUserName(name: string, displayName: string): string {
  return MOCK_CURRENT_USER_NAMES.has(name) ? displayName : name;
}

/** 将文本中的 mock 当前用户（含「何博 00623478」「TD 何博」等）替换为真实登录用户 */
export function substituteMockUserInText(
  text: string,
  sessionUser: Pick<SessionUserView, 'displayName' | 'userId'>,
): string {
  if (!text) return text;
  for (const mock of MOCK_CURRENT_USER_NAMES) {
    if (!text.includes(mock)) continue;
    const escaped = mock.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    if (sessionUser.userId) {
      const withId = new RegExp(`${escaped}\\s+[\\w\\d]+`, 'g');
      if (withId.test(text)) {
        return text.replace(withId, `${sessionUser.displayName} ${sessionUser.userId}`);
      }
    }
    return text.replaceAll(mock, sessionUser.displayName);
  }
  return text;
}
