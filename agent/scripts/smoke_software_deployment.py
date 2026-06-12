"""Smoke E2E for software_deployment LangGraph skill (HTTP start → stream → resume)."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any

BASE = "http://127.0.0.1:7401"
SKILL = "software_deployment"
MAX_RESUME_ROUNDS = 20
STREAM_TIMEOUT_S = 900
EXPECTED_STEPS = [
    "plan_receive", "plan_split", "plan_dispatch",
    "cloudops_init", "cloudops_supplement", "cloudops_full",
    "toolkit_executor", "toolkit_import",
    "connection", "lq_connection", "weak_light", "hccs_weak_light",
    "commission_report",
]


def _get(path: str) -> Any:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post(path: str, body: dict | None = None) -> Any:
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _consume_stream(run_id: str) -> dict[str, Any]:
    url = f"{BASE}/agent/{SKILL}/stream/{run_id}"
    events: list[dict[str, Any]] = []
    final: dict[str, Any] = {"events": events, "hitl": None, "error": None, "done": False}
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
    started = time.time()
    with urllib.request.urlopen(req, timeout=STREAM_TIMEOUT_S) as resp:
        buf = ""
        while True:
            if time.time() - started > STREAM_TIMEOUT_S:
                final["error"] = "stream timeout"
                break
            chunk = resp.read(1)
            if not chunk:
                break
            buf += chunk.decode("utf-8", errors="replace")
            while "\n\n" in buf:
                block, buf = buf.split("\n\n", 1)
                ev_type = "message"
                data_raw = ""
                for line in block.splitlines():
                    if line.startswith("event:"):
                        ev_type = line.split(":", 1)[1].strip()
                    elif line.startswith("data:"):
                        data_raw = line.split(":", 1)[1].strip()
                if not data_raw:
                    continue
                try:
                    data = json.loads(data_raw)
                except json.JSONDecodeError:
                    data = {"raw": data_raw}
                events.append({"event": ev_type, "data": data})
                if ev_type == "error":
                    final["error"] = data
                if ev_type == "done":
                    final["done"] = True
                if ev_type in ("node_update", "sdui"):
                    st = _get(f"/agent/{SKILL}/status/{run_id}")
                    hitl = (st.get("hitl") or {}) if isinstance(st, dict) else {}
                    if hitl.get("step"):
                        final["hitl"] = hitl
                        return final
                if ev_type == "done":
                    st = _get(f"/agent/{SKILL}/status/{run_id}")
                    final["state"] = st
                    return final
    st = _get(f"/agent/{SKILL}/status/{run_id}")
    final["state"] = st
    hitl = (st.get("hitl") or {}) if isinstance(st, dict) else {}
    if hitl.get("step"):
        final["hitl"] = hitl
    return final


def _resume_payload(hitl: dict[str, Any]) -> dict[str, Any]:
    step = str(hitl.get("step") or "")
    need_inputs = hitl.get("need_inputs") or []
    if step == "toolkit_executor":
        return {
            "base_url_ip": "100.100.166.137",
            "base_url_port": "28880",
            "secret_key": "src3ek07LgaoMcr0W3Whm4pAGvuWJ26wEyQip4Q2XP5akW5RQNuJHt6L9WXUMrLvL5cJhhRCAI1MOv9AM18jedV8Nko9zfDSpMJaUWrBT10Ungx9JlnqmHGnILW2TPdZ",
        }
    if need_inputs:
        first = need_inputs[0] if isinstance(need_inputs[0], dict) else {}
        opts = first.get("options") or []
        if opts and isinstance(opts[0], dict):
            return {"choice": opts[0].get("value") or "confirm"}
        return {"choice": "confirm"}
    return {"choice": "confirm"}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("[1] GET /agent/skills")
    skills = _get("/agent/skills")
    names = [s.get("name") for s in skills.get("skills") or []]
    if SKILL not in names:
        print(f"FAIL: {SKILL} not registered, got {names}")
        return 1
    print(f"    OK · registered: {names}")

    print("[2] POST /agent/software_deployment/start")
    start = _post(f"/agent/{SKILL}/start", {})
    run_id = start.get("run_id")
    if not run_id:
        print(f"FAIL: no run_id: {start}")
        return 1
    print(f"    run_id={run_id}")

    for round_i in range(1, MAX_RESUME_ROUNDS + 1):
        print(f"[3.{round_i}] stream …")
        chunk = _consume_stream(run_id)
        if chunk.get("error"):
            print(f"    ERROR event: {chunk['error']}")
            st = chunk.get("state") or _get(f"/agent/{SKILL}/status/{run_id}")
            print(f"    last step: {(st.get('steps') or [])[-3:]}")
            print(f"    state error: {st.get('error')}")
            return 1
        hitl = chunk.get("hitl")
        if hitl and hitl.get("step"):
            step = hitl["step"]
            payload = _resume_payload(hitl)
            print(f"    HITL @ {step} → resume {payload}")
            res = _post(f"/agent/{SKILL}/resume", {"run_id": run_id, "payload": payload, "from_step": step})
            print(f"    resume: {res.get('mode')} {res.get('message','')[:80]}")
            continue
        if chunk.get("done"):
            st = chunk.get("state") or {}
            steps = st.get("steps") or []
            ok_steps = [s.get("key") for s in steps if s.get("status") == "completed"]
            print(f"    DONE · completed steps ({len(ok_steps)}): {ok_steps}")
            err = st.get("error")
            if err:
                print(f"    state error: {err}")
                return 1
            print("SMOKE_OK")
            return 0
        st = _get(f"/agent/{SKILL}/status/{run_id}")
        ok_steps = [
            s.get("key") for s in (st.get("steps") or [])
            if s.get("status") == "completed"
        ]
        if not st.get("error") and set(EXPECTED_STEPS).issubset(set(ok_steps)):
            print(f"    stream ended early but all {len(EXPECTED_STEPS)} steps completed")
            print("SMOKE_OK")
            return 0
        print("    stream ended without hitl/done")
        break

    st = _get(f"/agent/{SKILL}/status/{run_id}")
    print(f"FAIL: incomplete · hitl={st.get('hitl')} error={st.get('error')}")
    print(f"    steps: {[(s.get('key'), s.get('status')) for s in (st.get('steps') or [])]}")
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.URLError as e:
        print(f"FAIL: cannot reach backend {BASE}: {e}")
        raise SystemExit(1)
