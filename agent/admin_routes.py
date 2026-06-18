"""
Admin 路由 · skill 热加载（P4）

提供 `POST /admin/skills/reload`：不重启进程即可让新增 / 改动的 skill 生效。
做三层缓存失效（① registry 工厂表 ② registry 实例缓存 ③ graph 编译图），
配合 P3 的目录发现——把 skill 目录放进 `agent/skills/` 或 `AIDA_SKILLS_PATH` 后调用本端点即可上线。

**红线边界**：本路由是**附加**的横切运维端点，独立成 router、经 `main.py` 一行 `include_router` 挂载；
不触碰 `main.py` / `graph.py` 的泛化路由与 `build_graph` 构图逻辑（`/agent/{skill}/*` 一行不动）。

**鉴权（fail-closed）**：
- 设了环境变量 `AIDA_ADMIN_TOKEN` → 必须带匹配的 `X-Admin-Token` 头；
- 未设 → 仅放行本机（127.0.0.1/::1），远程一律拒绝。

**进行中 run**：已持有旧编译图引用，reload 不影响、自然跑完（见 graph.invalidate 说明）。
**已知限制（P4.1 待办）**：reload 改变了 step 结构后再 resume 旧 run，checkpoint 可能不兼容；
当前未做「run 版本钉住」，建议在两次 run 之间 reload，或结构性变更后重启。
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/admin", tags=["admin"])


class ReloadReq(BaseModel):
    names: list[str] | None = None   # None = 全量重发现（含新增/删除目录）


def _check_admin_auth(request: Request, x_admin_token: str | None) -> None:
    """管理端点鉴权：配置了 token 走 token；否则仅放行本机。"""
    token = os.environ.get("AIDA_ADMIN_TOKEN", "").strip()
    if token:
        if (x_admin_token or "").strip() == token:
            return
        raise HTTPException(status_code=403, detail="admin token 无效")
    client = (request.client.host if request.client else "") or ""
    if client in ("127.0.0.1", "::1", "localhost"):
        return
    raise HTTPException(
        status_code=403,
        detail="reload 仅限本机；远程调用请配置 AIDA_ADMIN_TOKEN 并带 X-Admin-Token 头",
    )


@router.post("/skills/reload")
async def reload_skills(
    req: ReloadReq,
    request: Request,
    x_admin_token: str | None = Header(default=None),
):
    """热加载 skill：重发现目录 + 三层缓存失效，返回变更与最新 skill 列表。"""
    _check_admin_auth(request, x_admin_token)

    from . import graph
    from .skills import registry

    result = registry.reload(req.names)   # ①②：工厂表 + 实例缓存
    touched = set(result["reloaded"]) | set(result["added"]) | set(result["removed"])
    if touched:
        for name in touched:
            graph.invalidate(name)        # ③：编译图缓存
    elif req.names is None:
        graph.invalidate(None)            # 全量但无变化也清一次，确保一致

    return {
        "ok": not result["errors"],
        **result,
        "skills": registry.list_metadata(),
    }
