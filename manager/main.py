"""
AIDA Manager · FastAPI 入口

UX 协调层：鉴权代理数据中心，会话管理，后续扩展容器调度。

启动：
    cd <repo>
    source agent/.venv/bin/activate
    uvicorn manager.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from manager.config import aida_agent_base, datacenter_base
from manager.routes import auth, chat

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(title="AIDA Manager", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)


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
