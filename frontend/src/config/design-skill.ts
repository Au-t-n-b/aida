/** 系统设计模块后端 skill_id：system_design（完整交付流，默认）| xtsj（dispatch PoC） */
export const DESIGN_SKILL = (import.meta.env.VITE_DESIGN_SKILL ?? 'system_design') as 'xtsj' | 'system_design';

export const designSkillId = DESIGN_SKILL === 'xtsj' ? 'xtsj' : 'system_design';

export const isSystemDesignFull = DESIGN_SKILL !== 'xtsj';
