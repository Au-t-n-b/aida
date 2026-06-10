"""审批页（spec §5.4）：HTTP Basic，待审列表 + 通过/驳回。"""
import secrets
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from jinja2 import Environment, FileSystemLoader, select_autoescape

router = APIRouter()
_basic = HTTPBasic()
_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html"]),
)


def current_admin(request: Request,
                  cred: HTTPBasicCredentials = Depends(_basic)) -> str:
    ok = (secrets.compare_digest(cred.username, "admin") and
          secrets.compare_digest(cred.password, request.app.state.config.admin_password))
    if not ok:
        raise HTTPException(status_code=401, detail="认证失败",
                            headers={"WWW-Authenticate": "Basic"})
    return cred.username


@router.get("/admin", response_class=HTMLResponse)
def pending_page(request: Request, admin: str = Depends(current_admin)):
    db = request.app.state.db
    template = _env.get_template("pending.html")
    return template.render(pending=db.list_outbox_by_status("pending_approval"),
                           recent=db.list_outbox_recent(limit=50))


def _load_pending(request: Request, task_id: str) -> dict:
    task = request.app.state.db.get_outbox_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task_id 不存在")
    if task["status"] != "pending_approval":
        raise HTTPException(status_code=409, detail=f"任务已处于 {task['status']} 状态")
    return task


@router.post("/admin/approve/{task_id}")
def approve(task_id: str, request: Request, admin: str = Depends(current_admin)):
    from mailgw.service import deliver_task  # 局部导入避免循环依赖

    state = request.app.state
    _load_pending(request, task_id)
    state.db.update_outbox(task_id, approved_by=admin,
                           approved_at=datetime.now(timezone.utc).isoformat())
    deliver_task(db=state.db, sender=state.sender, task_id=task_id)
    state.db.add_audit(actor=admin, action="approved", detail={"task_id": task_id})
    return RedirectResponse("/admin", status_code=303)


@router.post("/admin/reject/{task_id}")
def reject(task_id: str, request: Request, reason: str = Form(...),
           admin: str = Depends(current_admin)):
    state = request.app.state
    _load_pending(request, task_id)
    state.db.update_outbox(task_id, status="rejected", reject_reason=reason)
    state.db.add_audit(actor=admin, action="rejected",
                       detail={"task_id": task_id, "reason": reason})
    return RedirectResponse("/admin", status_code=303)
