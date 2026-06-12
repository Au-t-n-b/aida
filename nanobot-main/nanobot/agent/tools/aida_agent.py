"""AIDA 交付 Skill 工具 — 通过本地 AIDA Agent API 启动/查询业务场景 Skill。"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request

from pydantic import Field

from nanobot.agent.tools.base import Tool, tool_parameters
from nanobot.agent.tools.schema import StringSchema, tool_parameters_schema
from nanobot.config.schema import Base


class AidaAgentToolConfig(Base):
    enable: bool = True
    base_url: str = "http://127.0.0.1:7401"


@tool_parameters(
    tool_parameters_schema(
        required=["action"],
        action=StringSchema(
            "Action: list_skills | start_skill | health",
            enum=["list_skills", "start_skill", "health"],
        ),
        skill_id=StringSchema(
            "AIDA skill id, e.g. zhgk, guihua, xtsj, device_install",
            nullable=True,
        ),
        project_json=StringSchema(
            "JSON object for start payload (project_code, project_name, etc.)",
            nullable=True,
        ),
    )
)
class AidaAgentTool(Tool):
    """Call the local AIDA LangGraph agent (delivery skills with SDUI)."""

    config_key = "aida_agent"
    _scopes = {"core", "subagent"}

    @classmethod
    def config_cls(cls):
        return AidaAgentToolConfig

    @classmethod
    def enabled(cls, ctx: Any) -> bool:
        return ctx.config.tools.aida_agent.enable

    @classmethod
    def create(cls, ctx: Any) -> Tool:
        cfg = ctx.config.tools.aida_agent
        return cls(base_url=cfg.base_url.rstrip("/"))

    def __init__(self, *, base_url: str | None = None) -> None:
        self.base_url = (base_url or os.environ.get("AIDA_AGENT_BASE", "http://127.0.0.1:7401")).rstrip("/")

    @property
    def name(self) -> str:
        return "aida_agent"

    @property
    def description(self) -> str:
        return (
            "Interact with the AIDA delivery agent API: list registered business skills "
            "(zhgk/guihua/xtsj/device_install), start a LangGraph workflow run, or check health. "
            "Use start_skill then poll stream via the AIDA frontend or API."
        )

    def _get(self, path: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        req = request.Request(url, method="GET")
        with request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8")
        req = request.Request(
            url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))

    async def execute(
        self,
        action: str,
        skill_id: str | None = None,
        project_json: str | None = None,
    ) -> str:
        try:
            if action == "health":
                return json.dumps(self._get("/healthz"), ensure_ascii=False, indent=2)
            if action == "list_skills":
                return json.dumps(self._get("/agent/skills"), ensure_ascii=False, indent=2)
            if action == "start_skill":
                if not skill_id:
                    return "Error: skill_id is required for start_skill"
                payload: dict[str, Any] = {}
                if project_json:
                    payload = json.loads(project_json)
                result = self._post(f"/agent/{skill_id}/start", payload)
                return json.dumps(result, ensure_ascii=False, indent=2)
            return f"Error: unknown action {action!r}"
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return f"HTTP {exc.code}: {body[:500]}"
        except Exception as exc:
            return f"Error: {type(exc).__name__}: {exc}"
