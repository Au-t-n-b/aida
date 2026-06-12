"""
交付预案 · 独立 API 服务器（不依赖 agent 主流程）

启动：
    cd D:\\my_rag\\aida
    python -m uvicorn agent.proposal_server:app --host 127.0.0.1 --port 7401 --reload
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .proposal_routes import router as proposal_router

app = FastAPI(title="AIDA Proposal API", version="0.1.0")

app.include_router(proposal_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("proposal_server:app", host="127.0.0.1", port=7401, reload=True)