from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from event_builder import dumps_event, guidance
from orchestrator import run


def _skill_root(req: dict[str, Any]) -> Path:
    explicit = str(req.get("skill_root") or "").strip()
    if explicit:
        path = Path(explicit).resolve()
        return path.parent if path.name == "runtime" else path
    cwd = Path(os.getcwd()).resolve()
    if (cwd / "module.json").is_file():
        return cwd
    return Path(__file__).resolve().parent.parent


def _ids(req: dict[str, Any]) -> tuple[str, str]:
    thread_id = str(req.get("thread_id") or req.get("threadId") or "").strip() or "thread-unknown"
    run_id = str(req.get("skillRunId") or req.get("request_id") or req.get("requestId") or "").strip() or "run"
    return thread_id, run_id


def _print_event(event: dict[str, Any]) -> None:
    sys.stdout.buffer.write(dumps_event(event))
    sys.stdout.buffer.flush()


def main() -> int:
    skill_root = os.getcwd()
    path_config = os.path.join(skill_root, "path_config.py")
    if not os.path.isfile(path_config):
        thread_id, run_id = "thread-unknown", "run"
        _print_event(
            guidance(
                "未检测到 path_config.py，请在 a3-intelligent-network-opening skill 根目录下运行 driver。",
                thread_id=thread_id,
                run_id=run_id,
                card_id="a3-opening:path-config-missing",
            )
        )
        return 0

    sys.path.insert(0, skill_root)
    from path_config import ensure_dirs  # noqa: E402

    ensure_dirs()

    try:
        raw = os.environ.get("NANOBOT_REQUEST_JSON")
        if not raw and not sys.stdin.isatty():
            raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        req = json.loads(raw or "{}")
        if not isinstance(req, dict):
            req = {}
    except Exception:
        req = {}

    root = _skill_root(req)
    try:
        events = run(req, skill_root=root)
        for event in events:
            _print_event(event)
    except Exception as exc:
        thread_id, run_id = _ids(req)
        _print_event(
            guidance(
                f"A3 智能网络开局总控 Skill 执行异常：{exc}",
                thread_id=thread_id,
                run_id=run_id,
                card_id="a3-opening:driver-exception",
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
