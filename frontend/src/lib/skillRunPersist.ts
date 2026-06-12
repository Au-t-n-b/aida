/** 模块页 run_id 会话级持久化（刷新后尝试恢复 SDUI，失效则清除） */

const prefix = 'aida:skill-run:';

export function persistSkillRunId(skillId: string, runId: string): void {
  if (typeof sessionStorage === 'undefined') return;
  sessionStorage.setItem(`${prefix}${skillId}`, runId);
}

export function readSkillRunId(skillId: string): string | null {
  if (typeof sessionStorage === 'undefined') return null;
  return sessionStorage.getItem(`${prefix}${skillId}`);
}

export function clearPersistedSkillRun(skillId: string): void {
  if (typeof sessionStorage === 'undefined') return;
  sessionStorage.removeItem(`${prefix}${skillId}`);
}
