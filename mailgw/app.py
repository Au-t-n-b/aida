"""应用组装：依赖注入，便于测试替换 db/sender/receiver。"""
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from mailgw.admin.routes import router as admin_router
from mailgw.api.routes import router as api_router
from mailgw.config import AppConfig
from mailgw.core.receiver import MailReceiver, Pop3Receiver
from mailgw.core.sender import SmtpSender
from mailgw.service import refresh_inbox
from mailgw.store.db import Database


def build_app(config: AppConfig, *, db: Database | None = None,
              sender: SmtpSender | None = None,
              receiver: MailReceiver | None = None) -> FastAPI:
    config.data_dir.mkdir(parents=True, exist_ok=True)
    stop_event = threading.Event()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        thread = None
        if config.pop3.poll_interval > 0:
            def _poll():
                while not stop_event.wait(config.pop3.poll_interval):
                    try:
                        refresh_inbox(db=app.state.db, receiver=app.state.receiver,
                                      data_dir=config.data_dir)
                    except Exception as exc:  # noqa: BLE001 —— 轮询失败不拖垮服务
                        app.state.db.add_audit(actor="system", action="poll_error",
                                               detail={"error": str(exc)})
            thread = threading.Thread(target=_poll, daemon=True)
            thread.start()
        yield
        stop_event.set()
        if thread:
            thread.join(timeout=5)

    app = FastAPI(title="mailgw", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.config = config
    app.state.db = db or Database(config.data_dir / "mailgw.db")
    app.state.sender = sender or SmtpSender(config.smtp)
    app.state.receiver = receiver or Pop3Receiver(config.pop3)
    app.include_router(api_router, prefix="/api")
    app.include_router(admin_router)
    return app
