from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from agent.schedule.api import router as schedule_router
from agent.schedule.contracts.api import ErrorResponse
from agent.schedule.store import PlanVersionStore


def create_app(
    *,
    store: PlanVersionStore | None = None,
    db_path: str | Path | None = None,
) -> FastAPI:
    app = FastAPI(title="AIDA Schedule API", version="0.1.0")
    configure_schedule_state(app, store=store, db_path=db_path)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_request, _exc):
        error = ErrorResponse(
            code="VALIDATION_ERROR",
            message="请求字段不符合接口契约。",
        )
        return JSONResponse(status_code=400, content=error.model_dump(mode="json"))

    app.include_router(schedule_router)
    return app


def configure_schedule_state(
    app: FastAPI,
    *,
    store: PlanVersionStore | None = None,
    db_path: str | Path | None = None,
) -> None:
    app.state.schedule_plan_store = store
    app.state.schedule_plan_store_path = Path(db_path or _default_db_path())


def _default_db_path() -> Path:
    configured = os.environ.get("SCHEDULE_DB_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent / ".local" / "schedule.sqlite3"


app = create_app()
