"""Bearer token 认证：返回 caller 名（spec §4）。"""
import secrets

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)


def current_caller(request: Request,
                   cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    if cred is not None:
        for name, token in request.app.state.config.tokens.items():
            if secrets.compare_digest(cred.credentials, token):
                return name
    raise HTTPException(status_code=401, detail="无效或缺失的 API token")
