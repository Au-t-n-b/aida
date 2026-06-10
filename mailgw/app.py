"""应用组装：依赖注入，便于测试替换 db/sender/receiver。"""
from fastapi import FastAPI

from mailgw.api.routes import router as api_router
from mailgw.config import AppConfig
from mailgw.core.receiver import MailReceiver, Pop3Receiver
from mailgw.core.sender import SmtpSender
from mailgw.store.db import Database


def build_app(config: AppConfig, *, db: Database | None = None,
              sender: SmtpSender | None = None,
              receiver: MailReceiver | None = None) -> FastAPI:
    config.data_dir.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title="mailgw", docs_url=None, redoc_url=None)
    app.state.config = config
    app.state.db = db or Database(config.data_dir / "mailgw.db")
    app.state.sender = sender or SmtpSender(config.smtp)
    app.state.receiver = receiver or Pop3Receiver(config.pop3)
    app.include_router(api_router, prefix="/api")
    return app
