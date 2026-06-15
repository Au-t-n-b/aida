from __future__ import annotations

from fastapi import FastAPI

from agent.schedule.api import router
from agent.schedule.app_main import configure_schedule_state
from agent.schedule.store import PlanVersionStore


def configure_schedule(
    app: FastAPI,
    *,
    store: PlanVersionStore | None = None,
) -> None:
    configure_schedule_state(app, store=store)


__all__ = ["configure_schedule", "router"]
