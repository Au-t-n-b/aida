"""admin/reload · 运行时热插拔 skill 的受控端点（Bearer token · fail-closed）

    POST /agent/admin/reload?skill=<name>   热重载单个 skill（缺=全量重扫）

⚠ 安全：reload = 重新 import 任意 Python = RCE 面。**fail-closed**——未配置
AIDA_ADMIN_TOKEN 则端点禁用（503），杜绝"忘配 token 就开了后门"。
本地启用：agent/.env 加一行 `AIDA_ADMIN_TOKEN=任意串`，调用带 `Authorization: Bearer <串>`。
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException, Query

router = APIRouter(prefix="/agent/admin", tags=["admin"])


def _require_admin(authorization: str | None) -> None:
    token = os.environ.get("AIDA_ADMIN_TOKEN", "").strip()
    if not token:
        raise HTTPException(
            503,
            "AIDA_ADMIN_TOKEN 未配置 → reload 端点已禁用（fail-closed；agent/.env 加一行启用）",
        )
    got = (authorization or "").removeprefix("Bearer ").strip()
    if got != token:
        raise HTTPException(401, "缺少或无效 admin token（Authorization: Bearer <AIDA_ADMIN_TOKEN>）")


@router.post("/reload")
def reload_endpoint(
    skill: str | None = Query(default=None, description="要热重载的 skill 名；省略=全量重扫 agent/skills/"),
    authorization: str | None = Header(default=None),
):
    """放置/修改 skill 目录包后调此端点，零重启生效。需 Bearer admin token。"""
    _require_admin(authorization)
    from agent.skills.hotreload import reload_skill, rescan
    return reload_skill(skill) if skill else rescan()
