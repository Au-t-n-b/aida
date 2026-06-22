#!/usr/bin/env python3
"""Claw 容器 P0 smoke：build（可选）→ run → healthz + /agent/skills → stop。"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "aida/claw_liwen:dev"
CONTAINER = "claw-smoke-test"
HOST_PORT = 17401
HEALTH_URL = f"http://127.0.0.1:{HOST_PORT}/healthz"
SKILLS_URL = f"http://127.0.0.1:{HOST_PORT}/agent/skills"


def _run(cmd: list[str], *, check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    print(f"[smoke] {' '.join(cmd)}")
    run_env = os.environ.copy()
    run_env.setdefault("DOCKER_API_VERSION", "1.42")
    if env:
        run_env.update(env)
    return subprocess.run(cmd, cwd=str(ROOT), check=check, env=run_env)


def _docker_ok() -> bool:
    return shutil.which("docker") is not None


def _env_file() -> Path | None:
    candidate = ROOT / "agent" / ".env"
    if not candidate.is_file():
        return None
    for line in candidate.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("ZHIPU_API_KEY=") and line.partition("=")[2].strip():
            return candidate
    return None


def _data_mount() -> Path:
    d = ROOT / ".data" / "claw-smoke"
    (d / "business").mkdir(parents=True, exist_ok=True)
    (d / "runtime" / "checkpoints").mkdir(parents=True, exist_ok=True)
    return d


def _stop_container() -> None:
    _run(["docker", "rm", "-f", CONTAINER], check=False)


def _wait_health(timeout: int = 180) -> bool:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with opener.open(HEALTH_URL, timeout=5) as resp:
                if resp.status == 200:
                    print(f"[smoke] healthz OK: {resp.read()[:200]!r}")
                    return True
        except Exception as e:
            print(f"[smoke] waiting healthz: {e}")
        time.sleep(3)
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true", help="docker build before run")
    parser.add_argument("--no-stop", action="store_true", help="leave container running")
    args = parser.parse_args()

    if not _docker_ok():
        print("[smoke] docker not found in PATH", file=sys.stderr)
        return 2

    env_file = _env_file()
    if env_file is None:
        print(
            "[smoke] need agent/.env with ZHIPU_API_KEY for bootstrap",
            file=sys.stderr,
        )
        return 2

    if args.build:
        _run([
            "docker", "build",
            "--build-arg", "PYTHON_BASE=python:3.12-slim",
            "-f", "deploy/claw/Dockerfile",
            "-t", IMAGE,
            ".",
        ])

    _stop_container()
    data = _data_mount()
    checkpoint = data / "runtime" / "checkpoints" / "claw-smoke.db"
    skills_src = (ROOT / "agent" / "skills").resolve()

    run_cmd = [
        "docker", "run", "-d",
        "--name", CONTAINER,
        "-p", f"{HOST_PORT}:7401",
        "-v", f"{skills_src}:/app/agent/skills:rw",
        "-v", f"{data.resolve()}/runtime/checkpoints:/opt/aida/aida-data/runtime/checkpoints:rw",
        "--env-file", str(env_file.resolve()),
        "-e", "AIDA_BUSINESS_ROOT=/opt/aida/aida-data/business",
        "-e", f"AIDA_CHECKPOINT_DB=/opt/aida/aida-data/runtime/checkpoints/{checkpoint.name}",
        "--add-host", "host.docker.internal:host-gateway",
        IMAGE,
    ]
    _run(run_cmd)

    try:
        if not _wait_health():
            print("[smoke] healthz timeout", file=sys.stderr)
            _run(["docker", "logs", CONTAINER], check=False)
            return 1

        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(SKILLS_URL, timeout=10) as resp:
            body = json.loads(resp.read().decode())
        skills = body if isinstance(body, list) else body.get("skills", body)
        if not skills:
            print("[smoke] /agent/skills empty", file=sys.stderr)
            return 1
        print(f"[smoke] skills count: {len(skills) if isinstance(skills, list) else 'ok'}")

        # nanobot health inside container
        proc = subprocess.run(
            ["docker", "exec", CONTAINER, "curl", "-sf", "http://127.0.0.1:8900/health"],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            print("[smoke] nanobot /health failed", file=sys.stderr)
            print(proc.stderr, file=sys.stderr)
            return 1
        print(f"[smoke] nanobot health: {proc.stdout.strip()}")

        print("[smoke] OK")
        return 0
    finally:
        if not args.no_stop:
            _stop_container()


if __name__ == "__main__":
    raise SystemExit(main())
