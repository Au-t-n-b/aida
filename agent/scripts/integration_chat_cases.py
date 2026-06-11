"""Integration tests for /agent/chat/stream — cases A/B/C/D."""
from __future__ import annotations

import json
import sys
import urllib.request
from typing import Any

BASE = "http://127.0.0.1:7401/agent/chat/stream"
TIMEOUT = 120


def stream_chat(message: str, conv_id: str = "") -> dict[str, Any]:
    req = urllib.request.Request(
        BASE,
        data=json.dumps({"message": message, "conv_id": conv_id, "context": {}}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    events: list[dict] = []
    tokens: list[str] = []
    stop = False
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        buf = b""
        while not stop:
            chunk = resp.read(512)
            if not chunk:
                break
            buf += chunk
            parts = buf.split(b"\n\n")
            buf = parts[-1]
            for block in parts[:-1]:
                for line in block.split(b"\n"):
                    if not line.startswith(b"data:"):
                        continue
                    raw = line[5:].strip()
                    if not raw:
                        continue
                    ev = json.loads(raw)
                    events.append(ev)
                    t = ev.get("type")
                    if t == "token":
                        tokens.append(ev.get("text", ""))
                    if t in ("done", "error"):
                        stop = True
                        break
    types = [e.get("type") for e in events]
    return {
        "types": types,
        "text": "".join(tokens),
        "events": events,
        "error": next((e.get("message") for e in events if e.get("type") == "error"), None),
    }


def main() -> int:
    cases = [
        ("A 基础对话", "你好，一句话回复", lambda r: "token" in r["types"] and "done" in r["types"]),
        ("B zhgk 触发", "帮我启动智慧工勘，工程编号 K1903", lambda r: "skill_launch" in r["types"]),
        ("C 工具审批", "给 test@example.com 发一封测试邮件", lambda r: "tool_approval_required" in r["types"]),
        ("D 网络工具", "搜索最新大模型新闻", lambda r: "tool_call" in r["types"] and any(
            e.get("name") == "web_search" for e in r["events"] if e.get("type") == "tool_call"
        )),
    ]
    failed = 0
    for name, msg, check in cases:
        print(f"\n=== {name} ===")
        print(f"Prompt: {msg}")
        try:
            r = stream_chat(msg)
            ok = check(r)
            print(f"Events: {r['types'][:20]}{'...' if len(r['types'])>20 else ''}")
            if r["text"]:
                print(f"Reply : {r['text'][:120]}")
            if r["error"]:
                print(f"Error : {r['error']}")
            for e in r["events"]:
                if e.get("type") in ("skill_launch", "tool_approval_required", "tool_call", "tool_result"):
                    print(f"  -> {e.get('type')}: {json.dumps(e, ensure_ascii=False)[:200]}")
            print(f"RESULT: {'PASS' if ok else 'FAIL'}")
            if not ok:
                failed += 1
        except Exception as exc:
            print(f"RESULT: FAIL ({exc})")
            failed += 1
    print(f"\n{'='*40}\nTotal: {len(cases)-failed}/{len(cases)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
