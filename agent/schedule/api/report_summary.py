from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from agent.schedule.llm import (
    BailianChatClient,
    LlmCallError,
    LlmConfigurationError,
    LlmTimeoutError,
    generate_report_summary_text,
)
from agent.schedule.contracts.api import API_PREFIX, ErrorResponse
from agent.schedule.contracts.report_summary import ReportSummaryRequest, ReportSummaryResponse

router = APIRouter(prefix=API_PREFIX, tags=["schedule"])


@router.post(
    "/report-summary",
    response_model=ReportSummaryResponse,
    responses={
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
)
def report_summary(payload: ReportSummaryRequest, request: Request):
    try:
        client = _get_client(request)
        return generate_report_summary_text(payload, client)
    except LlmConfigurationError as exc:
        return _error_response(503, "LLM_CONFIG_MISSING", str(exc))
    except LlmTimeoutError as exc:
        return _error_response(504, "LLM_TIMEOUT", str(exc))
    except LlmCallError as exc:
        return _error_response(502, "LLM_CALL_FAILED", str(exc))


def _get_client(request: Request):
    injected = getattr(request.app.state, "report_summary_client", None)
    if injected is not None:
        return injected
    return BailianChatClient.from_env()


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    error = ErrorResponse(code=code, message=message)
    return JSONResponse(status_code=status_code, content=error.model_dump(mode="json"))
