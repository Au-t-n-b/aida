"""
AIDA Manager · FastAPI 入口

UX 协调层：鉴权代理数据中心，会话管理，后续扩展容器调度。

启动：
    cd <repo>
    source agent/.venv/bin/activate
    uvicorn manager.main:app --host 0.0.0.0 --port 8081
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from manager.config import aida_agent_base, claw_idle_seconds, claw_orchestration_enabled, datacenter_base
from manager.routes import auth, chat, projects, session

logger = logging.getLogger("aida.manager")


async def _idle_reaper_loop() -> None:
    from manager.orchestrator import idle_reap

    while True:
        await asyncio.sleep(60)
        if not claw_orchestration_enabled():
            continue
        try:
            n = await asyncio.to_thread(idle_reap, claw_idle_seconds())
            if n:
                logger.info("idle reaped %s claw container(s)", n)
        except Exception as e:
            logger.warning("idle reaper error: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from manager.orchestrator import reconcile_on_startup

    reconcile_on_startup()
    task = asyncio.create_task(_idle_reaper_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="AIDA Manager", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(projects.router)
app.include_router(session.router)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logging.getLogger("aida.manager.dc").setLevel(logging.INFO)
logging.getLogger("aida.datacenter").setLevel(logging.INFO)


@app.get("/health")
async def health() -> dict:
    return {
        "ok": True,
        "service": "aida-manager",
        "datacenter_base": datacenter_base(),
        "aida_agent_base": aida_agent_base(),
    }


@app.get("/healthz")
async def healthz() -> dict:
    return await health()
