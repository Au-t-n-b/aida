"""Case C two-turn: choices confirm -> send_mail -> tool_approval_required"""
import json
import sys
import threading
import urllib.request

BASE = "http://127.0.0.1:7401"


def read_stream(message: str, history=None, stop_on=None, auto_approve=False):
    body = {"message": message, "conv_id": "", "context": {}, "history": history or []}
    req = urllib.request.Request(
        f"{BASE}/agent/chat/stream",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    events = []
    approved = set()

    def approve(aid):
        if aid in approved:
            return
        approved.add(aid)
        r = urllib.request.Request(
            f"{BASE}/agent/chat/approve-tool",
            data=json.dumps({"approval_id": aid, "approved": True}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(r, timeout=30) as resp:
            resp.read()

    with urllib.request.urlopen(req, timeout=180) as resp:
        buf = b""
        while True:
            chunk = resp.read(256)
            if not chunk:
                break
            buf += chunk
            lines = buf.split(b"\n")
            buf = lines[-1]
            for line in lines[:-1]:
                if not line.startswith(b"data:"):
                    continue
                raw = line[5:].strip()
                if not raw:
                    continue
                ev = json.loads(raw)
                events.append(ev)
                if auto_approve and ev.get("type") == "tool_approval_required":
                    threading.Thread(target=approve, args=(ev["approval_id"],), daemon=True).start()
                if stop_on and ev.get("type") in stop_on:
                    return events
                if ev.get("type") in ("done", "error"):
                    return events
    return events


def main():
    msg1 = "给 test@example.com 发一封测试邮件，主题「测试」，正文「Hello」"
    e1 = read_stream(msg1, stop_on={"choices", "tool_approval_required", "error"})
    types1 = [e["type"] for e in e1]
    print("Turn1:", types1)
    for e in e1:
        if e["type"] != "token":
            print(" ", json.dumps(e, ensure_ascii=False)[:200])

    history = [
        {"role": "user", "content": msg1},
        {"role": "assistant", "content": next((e.get("question") for e in e1 if e["type"] == "choices"), "请确认是否发送邮件？")},
    ]
    e2 = read_stream("确认发送", history=history, stop_on={"tool_approval_required", "error"})
    types2 = [e["type"] for e in e2]
    print("Turn2:", types2)
    for e in e2:
        if e["type"] != "token":
            print(" ", json.dumps(e, ensure_ascii=False)[:200])

    ok = "tool_approval_required" in types2 or "tool_approval_required" in types1
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
