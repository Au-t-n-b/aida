#!/usr/bin/env python3
"""
AIDA + nanobot 融合启动器。

1. bootstrap nanobot workspace / config.json
2. 启动 nanobot serve (:8900) — 自由聊天引擎
3. 启动 AIDA FastAPI (:7401) — LangGraph + SDUI，聊天代理到 nanobot
4. 启动 Manager (:8081) — UX 鉴权，代理数据中心
5. 启动 mailgw 团队邮箱 (:8025) — GKCLAW 邮件网关（需 mailgw/config.yaml）
6. 启动 ontology backend_app (:8011) — 数据中心 / 本体 API
7. 启动前端静态服务 (:8080)

ontology 手工等价命令（服务器 ontology 目录下）：
  nohup python3 -m uvicorn backend_app:app --host 0.0.0.0 --port 8011 &
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NANOBOT_DIR = ROOT / "nanobot-main"
MAILGW_DIR = ROOT / "mailgw"


def _ontology_dir() -> Path:
    """本体后端工作目录，默认 {repo}/ontology，服务器为 /opt/aida_liwen/ontology。"""
    raw = os.environ.get("ONTOLOGY_DIR", "").strip()
    if raw:
        return Path(raw).resolve()
    return (ROOT / "ontology").resolve()


def _venv_python() -> str:
    venv = ROOT / "agent" / ".venv" / "bin" / "python3"
    if venv.exists():
        return str(venv)
    venv_win = ROOT / "agent" / ".venv" / "Scripts" / "python.exe"
    if venv_win.exists():
        return str(venv_win)
    return sys.executable


def _load_agent_env() -> None:
    """把 agent/.env 注入当前进程环境，供子进程继承（代理 / LLM 等）。"""
    env_path = ROOT / "agent" / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


def _nanobot_python() -> str:
    """nanobot 专用 venv（需 Python 3.11+）。"""
    for candidate in [
        NANOBOT_DIR / ".venv" / "bin" / "python3",
        NANOBOT_DIR / ".venv" / "Scripts" / "python.exe",
        Path("/usr/bin/python3.11"),
        Path("/usr/local/bin/python3.11"),
    ]:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def bootstrap() -> None:
    _load_agent_env()
    sys.path.insert(0, str(ROOT))
    subprocess.run([sys.executable, str(ROOT / "scripts" / "remove_nanobot_builtin_skills.py")], check=True)
    from agent.nanobot_integration.bootstrap import bootstrap_nanobot_workspace
    cfg = bootstrap_nanobot_workspace()
    os.environ["NANOBOT_CONFIG"] = str(cfg)
    os.environ["AIDA_USE_NANOBOT_LLM"] = "1"
    os.environ["AIDA_CHAT_VIA_NANOBOT"] = "1"
    os.environ["NANOBOT_API_URL"] = "http://127.0.0.1:8900"
    # 本机 nanobot 不走企业代理（避免 Cntlm 502）
    os.environ["NO_PROXY"] = "127.0.0.1,localhost"
    os.environ["no_proxy"] = "127.0.0.1,localhost"
    print(f"[bootstrap] nanobot config: {cfg}")


def _popen(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None, log_name: str) -> subprocess.Popen:
    log = Path(f"/var/log/{log_name}")
    env = env or os.environ.copy()
    print(f"[start] {' '.join(cmd)}")
    if log.parent.exists():
        f = open(log, "a", encoding="utf-8")
        return subprocess.Popen(
            cmd, cwd=str(cwd or ROOT), env=env, stdout=f, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return subprocess.Popen(cmd, cwd=str(cwd or ROOT), env=env, start_new_session=True)


def start_nanobot_serve() -> subprocess.Popen | None:
    nb_py = _nanobot_python()
    env = os.environ.copy()
    env["NANOBOT_CONFIG"] = env.get("NANOBOT_CONFIG", str(Path.home() / ".nanobot" / "config.json"))
    # 优先 nanobot venv 里的 CLI
    nb_venv = NANOBOT_DIR / ".venv" / "bin" / "nanobot"
    if nb_venv.exists():
        cmd = [str(nb_venv), "serve", "--host", "127.0.0.1", "--port", "8900"]
    else:
        cmd = [nb_py, "-m", "nanobot.cli.commands", "serve", "--host", "127.0.0.1", "--port", "8900"]
    try:
        return _popen(cmd, cwd=ROOT, env=env, log_name="aida-nanobot-serve.log")
    except Exception as e:
        print(f"[nanobot serve] failed: {e}")
        return None


def _mailgw_port() -> str:
    return os.environ.get("MAILGW_PORT", "8025")


def _mailgw_python() -> str:
    for candidate in [
        MAILGW_DIR / ".venv" / "bin" / "python3",
        MAILGW_DIR / ".venv" / "Scripts" / "python.exe",
    ]:
        if candidate.exists():
            return str(candidate)
    return _venv_python()


def start_mailgw() -> subprocess.Popen | None:
    config = MAILGW_DIR / "config.yaml"
    if not config.is_file():
        print("[mailgw] config.yaml not found, skip")
        return None
    env_file = MAILGW_DIR / ".env"
    py = _mailgw_python()
    port = _mailgw_port()
    host = os.environ.get("MAILGW_HOST", "127.0.0.1")
    cmd = [
        py, "-m", "mailgw",
        "--config", str(config),
        "--env", str(env_file),
        "--host", host,
        "--port", port,
    ]
    try:
        return _popen(cmd, cwd=MAILGW_DIR, log_name="aida-mailgw.log")
    except Exception as e:
        print(f"[mailgw] failed: {e}")
        return None


def _manager_port() -> str:
    return os.environ.get("MANAGER_PORT", "8081")


def start_manager() -> subprocess.Popen:
    py = _venv_python()
    env = os.environ.copy()
    port = _manager_port()
    env.setdefault("AIDA_AGENT_BASE_URL", "http://127.0.0.1:7401")
    env.setdefault("MANAGER_HOST", "0.0.0.0")
    env.setdefault("MANAGER_PORT", port)
    cmd = [
        py, "-m", "uvicorn", "manager.main:app",
        "--host", env.get("MANAGER_HOST", "0.0.0.0"),
        "--port", port,
        "--workers", "1",
    ]
    return _popen(cmd, env=env, log_name="aida-manager.log")


def start_aida() -> subprocess.Popen:
    py = _venv_python()
    env = os.environ.copy()
    env["AIDA_USE_NANOBOT_LLM"] = "1"
    env["AIDA_CHAT_VIA_NANOBOT"] = "1"
    env["NANOBOT_API_URL"] = "http://127.0.0.1:8900"
    env["NO_PROXY"] = "127.0.0.1,localhost"
    env["no_proxy"] = "127.0.0.1,localhost"
    cmd = [py, "-m", "uvicorn", "agent.main:app", "--host", "0.0.0.0", "--port", "7401", "--workers", "1"]
    return _popen(cmd, env=env, log_name="aida-liwen-agent.log")


def _backend_app_port() -> str:
    return os.environ.get("BACKEND_APP_PORT", "8011")


def _ontology_python() -> str:
    """本体 backend_app 使用 ontology 目录下的 python3，勿复用 agent venv。"""
    ont_dir = _ontology_dir()
    candidates: list[Path] = []
    if sys.platform == "win32":
        candidates.extend([
            ont_dir / ".venv" / "Scripts" / "python.exe",
            Path("python"),
        ])
    else:
        candidates.extend([
            ont_dir / ".venv" / "bin" / "python3",
            Path("/usr/bin/python3"),
            Path("/usr/local/bin/python3"),
        ])
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return "python3"


def start_backend_app() -> subprocess.Popen | None:
    """ontology 数据中心 API（:8011），须在 ontology 目录下启动 backend_app。"""
    ont_dir = _ontology_dir()
    if not (ont_dir / "backend_app.py").is_file():
        print(f"[backend_app] {ont_dir}/backend_app.py not found, skip")
        return None
    py = _ontology_python()
    port = _backend_app_port()
    cmd = [
        py, "-m", "uvicorn", "backend_app:app",
        "--host", "0.0.0.0", "--port", port,
    ]
    try:
        print(f"[start] cd {ont_dir} && {' '.join(cmd)}")
        return _popen(cmd, cwd=ont_dir, log_name="aida-ontology-backend.log")
    except Exception as e:
        print(f"[backend_app] failed: {e}")
        return None


def start_frontend() -> subprocess.Popen | None:
    dist = ROOT / "frontend" / "dist"
    if not dist.exists():
        print("[frontend] dist/ not found, skip")
        return None
    py = _venv_python()
    cmd = [py, "-m", "http.server", "8080", "--bind", "0.0.0.0", "--directory", str(dist)]
    return _popen(cmd, log_name="aida-liwen-frontend.log")


def verify(*, mailgw_started: bool = False) -> bool:
    import urllib.error
    import urllib.request

    # 本机健康检查不走 HTTP_PROXY（与 nanobot_chat 一致）
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    ok = True
    checks = [
        ("manager", f"http://127.0.0.1:{_manager_port()}/health"),
        ("nanobot", "http://127.0.0.1:8900/health"),
        ("backend", "http://127.0.0.1:7401/healthz"),
        ("ontology", f"http://127.0.0.1:{_backend_app_port()}/api/v2/ontologies"),
        ("frontend", "http://127.0.0.1:8080/"),
    ]
    if mailgw_started:
        checks.insert(3, ("mailgw", f"http://127.0.0.1:{_mailgw_port()}/admin"))
    for name, url in checks:
        try:
            with opener.open(url, timeout=10) as r:
                print(f"[verify] {name}: HTTP {r.status}")
        except urllib.error.HTTPError as e:
            # mailgw /admin 需 Basic 认证，401 表示服务已就绪
            if name == "mailgw" and e.code == 401:
                print(f"[verify] {name}: HTTP {e.code} (auth required, ok)")
            elif name == "ontology" and e.code in (401, 403):
                print(f"[verify] {name}: HTTP {e.code} (auth required, ok)")
            else:
                print(f"[verify] {name} FAIL: HTTP {e.code}")
                if name not in ("frontend",):
                    ok = False
        except Exception as e:
            print(f"[verify] {name} FAIL: {e}")
            if name not in ("frontend", "ontology"):
                ok = False
    return ok


def stop_old() -> None:
    patterns = [
        "uvicorn manager.main",
        "uvicorn agent.main",
        "uvicorn backend_app",
        "http.server 8080",
        "nanobot serve",
        "nanobot.cli.commands serve",
        "python -m mailgw",
    ]
    for p in patterns:
        subprocess.run(["pkill", "-9", "-f", p], check=False)
    for port in (8001, 8011, 8900, 7401, 8080, int(_mailgw_port())):
        subprocess.run(
            ["bash", "-c", f"ss -lptn 'sport = :{port}' | grep -oP 'pid=\\K[0-9]+' | xargs -r kill -9"],
            check=False,
        )
    time.sleep(2)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-frontend", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--no-stop", action="store_true")
    args = parser.parse_args()

    if args.verify_only:
        return 0 if verify() else 1

    if not args.no_stop:
        stop_old()

    bootstrap()
    procs: list[subprocess.Popen] = []

    nb = start_nanobot_serve()
    if nb:
        procs.append(nb)
        time.sleep(5)

    procs.append(start_aida())
    time.sleep(3)

    procs.append(start_manager())
    time.sleep(2)

    ba = start_backend_app()
    if ba:
        procs.append(ba)
        time.sleep(2)

    mg = start_mailgw()
    mailgw_started = mg is not None
    if mg:
        procs.append(mg)
        time.sleep(2)

    if not args.no_frontend:
        fe = start_frontend()
        if fe:
            procs.append(fe)

    time.sleep(2)
    if not verify(mailgw_started=mailgw_started):
        for p in procs:
            p.terminate()
        return 1

    print("[ok] running PIDs:", [p.pid for p in procs])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
