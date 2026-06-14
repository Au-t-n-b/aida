"""Unified request/response logging for proposal HTTP routes."""
from __future__ import annotations

import logging
import os
import time
import uuid
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException as StarletteHTTPException

from agent.proposal.errors import ProposalApiError

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LOG_DIR = Path(os.environ.get("AIDA_LOG_DIR", str(_PROJECT_ROOT / "logs"))).resolve()
_SENSITIVE_QUERY_KEYS = frozenset({"access_token", "authorization", "password", "token"})


def _proposal_request_logger() -> logging.Logger:
    logger = logging.getLogger("aida.proposal.requests")
    if getattr(logger, "_aida_file_handler_ready", False):
        return logger

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = TimedRotatingFileHandler(
        _LOG_DIR / "proposal_requests.log",
        when="midnight",
        backupCount=14,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    setattr(logger, "_aida_file_handler_ready", True)
    return logger


def _safe_query(request: Request) -> str:
    pairs = [
        (key, "***" if key.lower() in _SENSITIVE_QUERY_KEYS else value)
        for key, value in parse_qsl(request.url.query, keep_blank_values=True)
    ]
    return urlencode(pairs)


def _project_id(request: Request) -> str:
    return str(request.path_params.get("project_id") or request.path_params.get("projectId") or "-")


class ProposalLoggingRoute(APIRoute):
    """Log proposal frontend requests and backend responses without sensitive bodies."""

    def get_route_handler(self):
        original_route_handler = super().get_route_handler()

        async def logged_route_handler(request: Request) -> Response:
            logger = _proposal_request_logger()
            request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
            started = time.perf_counter()
            common = (
                f"request_id={request_id} method={request.method} path={request.url.path} "
                f"query={_safe_query(request) or '-'} project={_project_id(request)} "
                f"client={request.client.host if request.client else '-'} "
                f"origin={request.headers.get('origin') or '-'}"
            )
            logger.info("frontend_request %s", common)
            try:
                response = await original_route_handler(request)
            except ProposalApiError as exc:
                duration_ms = round((time.perf_counter() - started) * 1000, 2)
                logger.warning(
                    "backend_response %s status=%s duration_ms=%s",
                    common,
                    exc.status,
                    duration_ms,
                )
                raise
            except RequestValidationError:
                duration_ms = round((time.perf_counter() - started) * 1000, 2)
                logger.warning("backend_response %s status=422 duration_ms=%s", common, duration_ms)
                raise
            except StarletteHTTPException as exc:
                duration_ms = round((time.perf_counter() - started) * 1000, 2)
                exc.headers = {**(exc.headers or {}), "X-Request-ID": request_id}
                logger.warning(
                    "backend_response %s status=%s duration_ms=%s",
                    common,
                    exc.status_code,
                    duration_ms,
                )
                raise
            except Exception:
                duration_ms = round((time.perf_counter() - started) * 1000, 2)
                logger.exception("backend_response %s status=500 duration_ms=%s", common, duration_ms)
                raise

            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "backend_response %s status=%s duration_ms=%s",
                common,
                response.status_code,
                duration_ms,
            )
            return response

        return logged_route_handler
