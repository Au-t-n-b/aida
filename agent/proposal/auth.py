"""RBAC for proposal module — align 00-第8章 §6."""
from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import Header

from agent.config import PROPOSAL_READ_ROLES, PROPOSAL_WRITE_ROLES
from agent.proposal.errors import ProposalApiError

# 暂时 mock 页头「创建人 / 最后修改人」展示名；接入真实用户体系后替换
PROPOSAL_MOCK_OPERATOR_NAME = "何博"


def _debug_log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    # region agent log
    try:
        payload = {
            "sessionId": "f94a50",
            "runId": "pre-fix",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        Path("debug-f94a50.log").open("a", encoding="utf-8").write(
            json.dumps(payload, ensure_ascii=False) + "\n"
        )
    except Exception:
        pass
    # endregion


def proposal_operator_display_name(_session: ProposalSession | None = None) -> str:
    session = _session
    account = (session.account if session else "") or ""
    account = account.strip()
    _debug_log(
        "H3",
        "agent/proposal/auth.py:proposal_operator_display_name",
        "resolve operator display name",
        {
            "sessionRole": session.role if session else None,
            "sessionAccount": account or None,
            "fallbackName": PROPOSAL_MOCK_OPERATOR_NAME,
        },
    )
    if account and account != "frontend":
        return account
    return PROPOSAL_MOCK_OPERATOR_NAME


class ProposalSession:
    def __init__(self, role: str, account: str = "dev") -> None:
        self.role = role.lower()
        self.account = account


def _parse_session(
    x_user_role: str | None,
    x_user_account: str | None,
) -> ProposalSession | None:
    _debug_log(
        "H2",
        "agent/proposal/auth.py:_parse_session",
        "parse proposal session from headers",
        {
            "xUserRole": x_user_role,
            "xUserAccount": x_user_account,
        },
    )
    if not x_user_role:
        return None
    return ProposalSession(role=x_user_role, account=x_user_account or "dev")


def _check_access(session: ProposalSession | None, *, verb: str) -> ProposalSession:
    if session is None:
        raise ProposalApiError(403, "FORBIDDEN", "无权限访问交付预案")

    allowed = PROPOSAL_WRITE_ROLES if verb in ("write", "release") else PROPOSAL_READ_ROLES
    if session.role not in allowed:
        raise ProposalApiError(403, "FORBIDDEN", "无权限访问交付预案")
    return session


def require_proposal_read(
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_user_account: str | None = Header(default=None, alias="X-User-Account"),
) -> ProposalSession:
    return _check_access(_parse_session(x_user_role, x_user_account), verb="read")


def require_proposal_write(
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_user_account: str | None = Header(default=None, alias="X-User-Account"),
) -> ProposalSession:
    return _check_access(_parse_session(x_user_role, x_user_account), verb="write")


def require_proposal_release(
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_user_account: str | None = Header(default=None, alias="X-User-Account"),
) -> ProposalSession:
    return _check_access(_parse_session(x_user_role, x_user_account), verb="release")
