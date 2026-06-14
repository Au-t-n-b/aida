"""Manager HTTP 异常构造（结构化 detail 供前端排障）。"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from shared.datacenter.errors import DataCenterError


def dc_http_exception(e: DataCenterError) -> HTTPException:
    if e.debug:
        detail: dict[str, Any] = {
            "message": str(e),
            "code": e.code,
            **e.debug,
        }
        return HTTPException(status_code=e.status_code, detail=detail)
    return HTTPException(status_code=e.status_code, detail=str(e))
