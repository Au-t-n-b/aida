"""subproc · 在 guihua 内以子进程真跑 vendored jmfz 脚本（plan 明确豁免：subprocess 调 py）。

为什么走 subprocess：本次交付要求「真跑」最新 jmfz 业务脚本（run_place_api.py /
run_device_install.py），脚本本身已对仿真 wapi 网关 100.102.191.17:9091 真发请求。
为最快复用现成、已验证的脚本，经用户确认偏离 AGENTS「禁 subprocess 调 py」红线
（技术债：后续可移植成 services 走 sim_api 统一出口）。

run_script：
  - 用 sys.executable（即 agent venv 的 python）执行，保证 requests/openpyxl 可用；
  - 设 cwd = 脚本 skill 根目录（脚本内多用相对路径定位 requests.json / config.json）；
  - 强制 UTF-8（PYTHONIOENCODING/UTF8），避免 Windows 控制台 gbk 解析中文输出报错；
  - 逐行把 stdout/stderr 转 emit（驱动 SSE 实时回流），可选 on_line 回调做进度解析；
  - 返回 {ok, exit_code, lines}。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from .sim_api import DEFAULT_API_BASE

Emit = Callable[[str], None]
OnLine = Callable[[str], None]


def _sim_gateway_no_proxy_env() -> dict[str, str]:
    """为子进程合并 NO_PROXY，避免企业代理拦截内网仿真网关（仅 guihua subproc 路径）。"""
    base = (os.environ.get("SIM_API_BASE") or DEFAULT_API_BASE).strip() or DEFAULT_API_BASE
    host = urlparse(base).hostname or "100.102.191.17"
    extras: dict[str, str] = {}
    for key in ("NO_PROXY", "no_proxy"):
        parts = [p.strip() for p in (os.environ.get(key) or "").split(",") if p.strip()]
        for item in (host, "127.0.0.1", "localhost"):
            if item not in parts:
                parts.append(item)
        extras[key] = ",".join(parts)
    return extras


def _subproc_failure_hint(result: dict) -> str:
    lines = result.get("lines") or []
    tail = "\n".join(lines[-8:])
    code = result.get("exit_code")
    if any(x in tail for x in ("504", "HIS Proxy", "Gateway Time-out", "Gateway Timeout")):
        return (
            f"仿真网关请求被企业代理拦截（exit_code={code}）。"
            "请确认 Agent 环境 NO_PROXY 含仿真网关地址，并以 SIM_API_LIVE=1 重启。"
        )
    err = (result.get("error") or "").strip()
    if err:
        return f"子进程失败：{err}"
    return f"子进程失败（exit_code={code}）"


def run_script(
    workdir: str | Path,
    args: list[str],
    *,
    emit: Emit | None = None,
    on_line: OnLine | None = None,
    extra_env: dict[str, str] | None = None,
    timeout: int | None = 1800,
) -> dict:
    """在 workdir 下用 agent venv 的 python 跑 `args`，逐行回流输出。

    args 例：["scripts/run_place_api.py", "run", "--only-create"]
    """
    workdir = Path(workdir).resolve()

    def _say(msg: str) -> None:
        if emit:
            emit(msg)

    if not workdir.is_dir():
        _say(f"[subproc] ✗ 工作目录不存在：{workdir}")
        return {"ok": False, "exit_code": -1, "lines": [], "error": f"workdir not found: {workdir}"}

    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    env.update(_sim_gateway_no_proxy_env())
    if extra_env:
        env.update(extra_env)

    cmd = [sys.executable, *args]
    _say(f"[subproc] $ {' '.join(args)}  (cwd={workdir.name})")

    lines: list[str] = []
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(workdir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
        )
    except Exception as exc:  # noqa: BLE001
        _say(f"[subproc] ✗ 启动失败：{exc}")
        return {"ok": False, "exit_code": -1, "lines": [], "error": str(exc)}

    try:
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.rstrip("\r\n")
            if not line:
                continue
            lines.append(line)
            _say(line)
            if on_line:
                try:
                    on_line(line)
                except Exception:  # noqa: BLE001
                    pass
        code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        _say(f"[subproc] ✗ 超时（>{timeout}s），已终止")
        return {"ok": False, "exit_code": -1, "lines": lines, "error": "timeout"}

    ok = code == 0
    _say(f"[subproc] {'✓' if ok else '✗'} exit_code={code}")
    return {"ok": ok, "exit_code": code, "lines": lines}
