"""用户档案辅助（避免 session_resolve ↔ auth 循环导入）。"""
from __future__ import annotations

from typing import Any


def primary_role(profile: dict[str, Any]) -> str:
    if profile.get("isAdmin"):
        return "admin"
    global_roles = profile.get("globalRoles") or []
    if global_roles:
        first = global_roles[0]
        if isinstance(first, dict) and first.get("roleCode"):
            return str(first["roleCode"])
    project_roles = profile.get("projectRoles") or []
    if project_roles:
        first = project_roles[0]
        if isinstance(first, dict) and first.get("roleCode"):
            return str(first["roleCode"])
    return "user"
