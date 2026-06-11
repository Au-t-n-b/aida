"""Quick smoke test for /agent/chat/stream SSE endpoint."""
import urllib.request
import json

req = urllib.request.Request(
    "http://127.0.0.1:7401/agent/chat/stream",
    data=json.dumps({"message": "你好，一句话回复我", "conv_id": "", "context": {}}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)

events: list[str] = []
texts: list[str] = []
stop = False

try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        buf = b""
        while not stop:
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
                try:
                    ev = json.loads(raw)
                    t = ev.get("type", "?")
                    events.append(t)
                    if t == "token":
                        texts.append(ev.get("text", ""))
                    if t == "error":
                        print(f"[error] {ev.get('message', ev)}")
                    if t in ("done", "error"):
                        stop = True
                        break
                except Exception:
                    pass
except Exception as exc:
    print(f"ERROR: {exc}")
    raise SystemExit(1)

print("Events :", events)
print("Reply  :", "".join(texts)[:300])
ok = any(e in ("token", "done") for e in events)
print("RESULT :", "PASS" if ok else "FAIL: no token/done event")
raise SystemExit(0 if ok else 1)
