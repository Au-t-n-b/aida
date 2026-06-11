"""
zhgk 收件人 / 角色配置（模块内自包含默认）。

接入契约 §0 自包含 + §11 资产落点：收件人本属「组织/项目资产」，目标态应由数据中心
挂载目录下发（recipients.json）。当前阶段先**内联一份默认收件人**，使本模块脱离对
「工作区 path_config.py + sys.path 注入」的依赖，满足自包含红线（拷到干净机器即可 import）。

字段形状与历史工作区 path_config.get_recipients 保持一致：list[{"role","name","email"}]，
角色常量名（ROLE_*）也保持一致，故 step 侧 `getattr(模块, 角色名)` 的解析逻辑零改即生效。

后续接挂载文件时：让 get_recipients 优先读 ctx 数据目录下的 recipients.json，回落本默认即可，
step 侧无需再改。
"""
from __future__ import annotations

# ── 角色常量（与历史工作区 path_config 对齐；值为角色 key）──
ROLE_ALL_STAKEHOLDERS = "all_stakeholders"
ROLE_PROJECT_TEAM = "project_team"
ROLE_PD_TD_EXPERT = "pd_td_expert"
ROLE_EXPERT = "expert"

# ── 内联默认收件人（demo · 目标态由数据中心挂载覆盖）──
# 每个 recipient: {"role", "name", "email"}
_DEFAULT_RECIPIENTS: dict[str, list[dict]] = {
    ROLE_ALL_STAKEHOLDERS: [
        {"role": "项目经理", "name": "张工", "email": "pm@example.com"},
        {"role": "客户接口人", "name": "李工", "email": "customer@example.com"},
        {"role": "PD/TD 专家", "name": "王专家", "email": "expert@example.com"},
    ],
    ROLE_PROJECT_TEAM: [
        {"role": "项目经理", "name": "张工", "email": "pm@example.com"},
        {"role": "勘测工程师", "name": "赵工", "email": "surveyor@example.com"},
    ],
    ROLE_PD_TD_EXPERT: [
        {"role": "PD/TD 专家", "name": "王专家", "email": "expert@example.com"},
    ],
    ROLE_EXPERT: [
        {"role": "评审专家", "name": "孙专家", "email": "reviewer@example.com"},
    ],
}


def get_recipients(role: str) -> list[dict]:
    """按角色取收件人（内联默认）。未知角色 → []。

    返回 list[{"role","name","email"}]，与历史工作区 path_config.get_recipients 同形。
    """
    return [dict(r) for r in _DEFAULT_RECIPIENTS.get(role, [])]
