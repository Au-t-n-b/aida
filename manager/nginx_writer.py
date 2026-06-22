"""nginx 动态 Claw 反代配置（path 模式）。"""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from manager.config import nginx_conf_dir, nginx_reload_cmd

logger = logging.getLogger("aida.manager.nginx")

_TEMPLATE = """# AIDA Claw — auto-generated, do not edit
location ^~ /claw/{routing_key}/ {{
    proxy_pass http://127.0.0.1:{host_port}/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
}}
"""


def _conf_path(routing_key: str) -> Path:
    safe = routing_key.replace("/", "_")
    return nginx_conf_dir() / f"claw-{safe}.conf"


def write_claw_location(routing_key: str, host_port: int) -> None:
    conf_dir = nginx_conf_dir()
    if not conf_dir:
        return
    conf_dir.mkdir(parents=True, exist_ok=True)
    path = _conf_path(routing_key)
    path.write_text(
        _TEMPLATE.format(routing_key=routing_key, host_port=host_port),
        encoding="utf-8",
    )
    _reload_nginx()
    logger.info("nginx claw location %s -> :%s", routing_key, host_port)


def remove_claw_location(routing_key: str) -> None:
    conf_dir = nginx_conf_dir()
    if not conf_dir:
        return
    path = _conf_path(routing_key)
    if path.is_file():
        path.unlink()
        _reload_nginx()
        logger.info("removed nginx claw location %s", routing_key)


def _reload_nginx() -> None:
    cmd = nginx_reload_cmd()
    if not cmd:
        return
    try:
        subprocess.run(cmd, shell=True, check=False, timeout=30)
    except Exception as e:
        logger.warning("nginx reload failed: %s", e)
