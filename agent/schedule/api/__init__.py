from __future__ import annotations

from fastapi import APIRouter

from agent.schedule.api.changes import router as changes_router
from agent.schedule.api.schedule import router as schedule_router

router = APIRouter()
router.include_router(schedule_router)
router.include_router(changes_router)

__all__ = ["router"]
