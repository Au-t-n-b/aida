/** 模块页 run_id / task_id 会话级持久化（刷新后尝试恢复，失效则清除） */

const runPrefix = 'aida:skill-run:';
const taskPrefix = 'aida:skill-task:';

export function persistSkillRunId(skillId: string, runId: string): void {
  if (typeof sessionStorage === 'undefined') return;
  sessionStorage.setItem(`${runPrefix}${skillId}`, runId);
}

export function readSkillRunId(skillId: string): string | null {
  if (typeof sessionStorage === 'undefined') return null;
  return sessionStorage.getItem(`${runPrefix}${skillId}`);
}

export function persistSkillTaskId(skillId: string, taskId: string): void {
  if (typeof sessionStorage === 'undefined') return;
  sessionStorage.setItem(`${taskPrefix}${skillId}`, taskId);
}

export function readSkillTaskId(skillId: string): string | null {
  if (typeof sessionStorage === 'undefined') return null;
  return sessionStorage.getItem(`${taskPrefix}${skillId}`);
}

export function clearPersistedSkillRun(skillId: string): void {
  if (typeof sessionStorage === 'undefined') return;
  sessionStorage.removeItem(`${runPrefix}${skillId}`);
}

export function clearPersistedSkillTask(skillId: string): void {
  if (typeof sessionStorage === 'undefined') return;
  sessionStorage.removeItem(`${taskPrefix}${skillId}`);
}

/** 清除该 skill 在浏览器 session 中的 run + task 指针。*/
export function clearPersistedSkill(skillId: string): void {
  clearPersistedSkillRun(skillId);
  clearPersistedSkillTask(skillId);
}
