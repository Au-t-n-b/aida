"""Run a single chat integration case: python integration_chat_one.py A|B|C|D"""
from __future__ import annotations

import json
import sys
import threading
import urllib.request

BASE = "http://127.0.0.1:7401"
CASES = {
    "A": ("基础对话", "你好，一句话回复", lambda t: "token" in t and "done" in t),
    "B": ("zhgk 触发", "帮我启动智慧工勘，工程编号 K1903", lambda t: "skill_launch" in t),
    "C": ("工具审批", "给 test@example.com 发一封测试邮件", lambda t: "tool_approval_required" in t),
    "D": ("网络工具", "搜索最新大模型新闻", lambda t: any(
        e.get("type") == "tool_call" and e.get("name") == "web_search" for e in t
    ) if isinstance(t, list) else "tool_call" in t),
}


def _parse_line(line: bytes, events: list[dict], tokens: list[str]) -> bool:
    if not line.startswith(b"data:"):
        return False
    raw = line[5:].strip()
    if not raw:
        return False
    ev = json.loads(raw)
    events.append(ev)
    if ev.get("type") == "token":
        tokens.append(ev.get("text", ""))
    return ev.get("type") in ("done", "error")


def stream(message: str, auto_approve: bool = False, stop_on: set[str] | None = None) -> tuple[list[str], list[dict]]:
    req = urllib.request.Request(
        f"{BASE}/agent/chat/stream",
        data=json.dumps({"message": message, "conv_id": "", "context": {}}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    events: list[dict] = []
    tokens: list[str] = []
    approved: set[str] = set()

    def maybe_approve(ev: dict) -> None:
        if not auto_approve or ev.get("type") != "tool_approval_required":
            return
        aid = ev.get("approval_id", "")
        if not aid or aid in approved:
            return
        approved.add(aid)
        body = json.dumps({"approval_id": aid, "approved": True}).encode()
        approve_req = urllib.request.Request(
            f"{BASE}/agent/chat/approve-tool",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(approve_req, timeout=30) as r:
            r.read()

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
                if ev.get("type") == "token":
                    tokens.append(ev.get("text", ""))
                if auto_approve:
                    threading.Thread(target=maybe_approve, args=(ev,), daemon=True).start()
                if stop_on and ev.get("type") in stop_on:
                    return tokens, events
                if ev.get("type") in ("done", "error"):
                    return tokens, events
    return tokens, events


def main() -> int:
    key = sys.argv[1].upper() if len(sys.argv) > 1 else "A"
    if key not in CASES:
        print(f"Unknown case {key!r}, use A/B/C/D")
        return 2
    name, msg, check = CASES[key]
    print(f"=== {key} {name} ===")
    print(f"Prompt: {msg}")
    tokens, events = stream(
        msg,
        auto_approve=False,
        stop_on={"tool_approval_required"} if key == "C" else None,
    )
    types = [e.get("type") for e in events]
    ok = check(types if key != "D" else events)
    print("Events:", types)
    if tokens:
        print("Reply :", "".join(tokens)[:200])
    for e in events:
        if e.get("type") not in ("token", "heartbeat", "done"):
            print("Extra:", json.dumps(e, ensure_ascii=False)[:300])
    err = next((e.get("message") for e in events if e.get("type") == "error"), None)
    if err:
        print("Error:", err)
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
