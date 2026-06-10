"""agent API（spec §4）。"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from mailgw.api.auth import current_caller
from mailgw.service import submit_send

router = APIRouter()


class SendRequest(BaseModel):
    to: list[str]
    cc: list[str] = []
    subject: str
    body: str
    body_html: str | None = None
    attachments: list[str] = []


@router.post("/send")
def send_email(req: SendRequest, request: Request, caller: str = Depends(current_caller)):
    state = request.app.state
    return submit_send(db=state.db, config=state.config, sender=state.sender,
                       caller=caller, to=req.to, cc=req.cc, subject=req.subject,
                       body_text=req.body, body_html=req.body_html,
                       attachments=req.attachments)


@router.get("/send/{task_id}")
def check_send_status(task_id: str, request: Request,
                      caller: str = Depends(current_caller)):
    task = request.app.state.db.get_outbox_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task_id 不存在")
    return {"task_id": task["id"], "status": task["status"],
            "created_at": task["created_at"], "sent_at": task["sent_at"],
            "reject_reason": task["reject_reason"], "last_error": task["last_error"]}
