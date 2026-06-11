"""
_intent_guard · 意图路由守卫

各 step 调用 should_skip(step_key, project) 决定本步骤是否跳过。
state["project"]["intent"] 由 intent_select step 写入，之后保持不变。

意图枚举（与 services/types.py Intent 对齐）:
    scene_suggest  — 场景建议（快速给出勘测场景推荐，不建表不评估）
    survey_work    — 全流程工勘（建表 → 勘测 → 评估 → 问题清单 → 复勘门控）
    supplement     — 补充勘测（用户已有结果表，追加数据或自定义条目）
    report_gen     — 报告生成（基于已完成的勘测结果表生成三件套 + Word 报告）
"""
from __future__ import annotations

# ── 步骤 → 适用意图 映射 ───────────────────────────────────────────────────────
# 未在此表的 step 默认不受意图过滤（internal step 或新增 step 未配置时安全回退）。
STEP_INTENTS: dict[str, frozenset[str]] = {
    # ─── 全意图共有 ───
    "intent_select":    frozenset({"scene_suggest", "survey_work", "supplement", "report_gen"}),
    # ─── 单意图专属 ───
    "scene_suggest_run": frozenset({"scene_suggest"}),
    "supplement_run":    frozenset({"supplement"}),
    # ─── survey_work + supplement + report_gen + scene_suggest ───
    # scene_suggest_run 需要 generation_cooling，必须经过 determine_gen
    "determine_gen":     frozenset({"survey_work", "supplement", "report_gen", "scene_suggest"}),
    # ─── survey_work 专属 ───
    "filter_build":      frozenset({"survey_work"}),
    "method_split":      frozenset({"survey_work"}),
    "data_append":       frozenset({"survey_work"}),
    "confirm_table":     frozenset({"survey_work"}),
    "task_dispatch":     frozenset({"survey_work"}),
    "wait_survey":       frozenset({"survey_work"}),
    "resurvey_gate":     frozenset({"survey_work"}),
    # ─── survey_work + report_gen ───
    "assess":            frozenset({"survey_work", "report_gen"}),
    "issue_list":        frozenset({"survey_work", "report_gen"}),
    # ─── report_gen 专属 ───
    "report_gen_run":    frozenset({"report_gen"}),
    "report_distribute": frozenset({"report_gen"}),
}


def should_skip(step_key: str, project: dict) -> bool:
    """
    返回 True 表示本步骤应跳过（意图不适用）。

    逻辑：
      - 未设置 intent → 不跳过（安全回退：preflight 等早期步骤需要全意图运行）
      - step_key 不在映射表 → 不跳过（internal 步骤或未注册步骤）
      - intent 在 STEP_INTENTS[step_key] 里 → 不跳过
      - intent 不在 STEP_INTENTS[step_key] 里 → 跳过
    """
    intent: str = (project or {}).get("intent", "")
    if not intent:
        return False
    allowed = STEP_INTENTS.get(step_key)
    if allowed is None:
        return False
    return intent not in allowed
