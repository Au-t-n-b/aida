"""Claw 容器编排（Docker SDK）。"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

from manager.config import (
    claw_checkpoint_path,
    claw_container_project_bind,
    claw_container_volumes,
    claw_edge_base,
    claw_edge_mode,
    claw_env_for_container,
    claw_host_project_path,
    claw_image,
    claw_org_assets_bind,
    claw_orchestration_enabled,
    claw_port_pool_end,
    claw_port_pool_start,
    claw_skills_container_bind,
    claw_skills_host_bind,
    container_endpoint_url,
)
from manager.registry import (
    ClawAllocation,
    ClawRegistry,
    container_name,
    container_name_prefix_for_user,
    get_registry,
    parse_container_identity,
    routing_key,
    sanitize_project_id,
)

logger = logging.getLogger("aida.manager.orchestrator")

_CLIENT: Any = None


def _docker_client():
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    if not claw_orchestration_enabled():
        return None
    try:
        import docker

        os.environ.setdefault("DOCKER_API_VERSION", "1.42")
        _CLIENT = docker.from_env()
        _CLIENT.ping()
        return _CLIENT
    except Exception as e:
        logger.warning("docker unavailable: %s", e)
        return None


def registry() -> ClawRegistry:
    return get_registry(claw_port_pool_start(), claw_port_pool_end())


def reconcile_on_startup() -> None:
    if not claw_orchestration_enabled():
        return
    client = _docker_client()
    if not client:
        return
    reg = registry()
    prefix = "aida-claw"
    legacy_prefix = "claw-u"
    seen: set[str] = set()
    for filt_prefix in (prefix, legacy_prefix):
        for c in client.containers.list(all=True, filters={"name": filt_prefix}):
            name = (c.name or "").lstrip("/")
            if name in seen:
                continue
            seen.add(name)
            parsed = parse_container_identity(name)
            if not parsed:
                continue
            uid, pid_part = parsed
            ports = c.attrs.get("NetworkSettings", {}).get("Ports") or {}
            host_port = None
            for spec in ports.get("7401/tcp") or []:
                if isinstance(spec, dict) and spec.get("HostPort"):
                    host_port = int(spec["HostPort"])
                    break
            if not host_port:
                continue
            reg.reattach_port(host_port)
            key = f"{uid}-{pid_part}"
            alloc = ClawAllocation(
                routing_key=key,
                user_id=uid,
                project_id=pid_part,
                project_code=pid_part,
                host_port=host_port,
                container_id=c.id,
                container_name=name,
                last_heartbeat=time.time(),
            )
            labels = c.labels or {}
            session_label = (labels.get("aida.session_id") or "").strip()
            if session_label:
                alloc.session_id = session_label
            reg.register(alloc)
            if session_label:
                reg.bind_session(session_label, key)
            if claw_edge_mode() == "path":
                from manager.nginx_writer import write_claw_location

                write_claw_location(key, host_port)
            logger.info(
                "reconciled claw container %s port=%s user=%s session=%s",
                name,
                host_port,
                uid,
                session_label[:16] if session_label else "-",
            )


def _container_running(client, name: str):
    try:
        c = client.containers.get(name)
        c.reload()
        return c if c.status == "running" else None
    except Exception:
        return None


def ensure_claw(
    *,
    session_id: str,
    user_id: int,
    project_id: str,
    project_code: str,
    username: str = "",
    wait_ready: bool = False,
) -> tuple[ClawAllocation, bool]:
    """拉起或复用 Claw 容器。wait_ready=False 时仅 docker run，就绪由前端轮询 heartbeat。"""
    if not claw_orchestration_enabled():
        raise RuntimeError("AIDA_CLAW_ORCHESTRATION 未启用")
    if user_id <= 0:
        raise RuntimeError(f"无效 user_id={user_id}，无法编排 Claw 容器")

    client = _docker_client()
    if not client:
        raise RuntimeError("Docker 不可用，无法编排 Claw 容器")

    reg = registry()
    key = routing_key(user_id, project_id)
    name = container_name(user_id, project_id, username)
    existing = reg.get(key)

    if existing:
        running = _container_running(client, existing.container_name)
        if running:
            existing.project_code = project_code or project_id
            reg.bind_session(session_id, key)
            logger.info("reuse claw %s session=%s", existing.container_name, session_id)
            return existing, True

    host_port = existing.host_port if existing else reg.allocate_port()
    checkpoint = claw_checkpoint_path(user_id, project_id)
    env = claw_env_for_container(user_id, project_id, checkpoint)

    # 清理同名残留
    try:
        old = client.containers.get(name)
        old.remove(force=True)
    except Exception:
        pass

    data_mount = claw_host_project_path(project_id)
    host_proj = Path(data_mount)
    if not host_proj.is_dir():
        logger.warning("project data dir missing on host: %s", data_mount)

    volumes = claw_container_volumes(project_id)
    logger.info(
        "claw volumes org=%s host_proj=%s -> container_proj=%s skills=%s -> %s",
        claw_org_assets_bind(),
        data_mount,
        claw_container_project_bind(),
        claw_skills_host_bind(),
        claw_skills_container_bind(),
    )
    env_file = os.environ.get("CLAW_ENV_FILE", "").strip()
    run_kwargs: dict[str, Any] = {
        "image": claw_image(),
        "name": name,
        "detach": True,
        "ports": {"7401/tcp": host_port},
        "volumes": volumes,
        "environment": env,
        "extra_hosts": {"host.docker.internal": "host-gateway"},
        "restart_policy": {"Name": "unless-stopped"},
        "labels": {
            "aida.user_id": str(user_id),
            "aida.project_id": sanitize_project_id(project_id),
            "aida.session_id": session_id[:64],
            **({"aida.username": username[:63]} if username else {}),
        },
    }
    if env_file and os.path.isfile(env_file):
        for line in Path(env_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            run_kwargs["environment"].setdefault(k.strip(), v.strip())
    container = client.containers.run(**run_kwargs)

    alloc = ClawAllocation(
        routing_key=key,
        user_id=user_id,
        project_id=project_id,
        project_code=project_code or project_id,
        host_port=host_port,
        container_id=container.id,
        container_name=name,
        session_id=session_id,
    )
    reg.register(alloc)
    reg.bind_session(session_id, key)

    if claw_edge_mode() == "path":
        from manager.nginx_writer import write_claw_location

        write_claw_location(key, host_port)

    if wait_ready:
        _wait_health(host_port)
    logger.info("started claw %s port=%s session=%s wait_ready=%s", name, host_port, session_id, wait_ready)
    return alloc, False


def is_claw_ready(host_port: int) -> bool:
    import urllib.error
    import urllib.request

    url = f"http://127.0.0.1:{host_port}/healthz/ready"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url, timeout=2) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _wait_health(host_port: int, timeout: int = 120) -> None:
    import urllib.error
    import urllib.request

    url = f"http://127.0.0.1:{host_port}/healthz/ready"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.time() + timeout
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with opener.open(url, timeout=3) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            # 容器启动期常见 Connection reset by peer，需重试而非让请求 500 断连
            last_err = e
            time.sleep(1)
    hint = f" ({last_err})" if last_err else ""
    raise RuntimeError(f"Claw 容器 {host_port} healthz 超时{hint}")


def destroy_for_session(session_id: str) -> bool:
    alloc = registry().get_by_session(session_id)
    if alloc:
        return destroy_allocation(alloc.routing_key)
    # Manager 重启后 session 绑定丢失：按 label 查找
    client = _docker_client()
    if not client:
        return False
    destroyed = False
    for c in client.containers.list(all=True, filters={"label": f"aida.session_id={session_id[:64]}"}):
        name = (c.name or "").lstrip("/")
        try:
            c.remove(force=True)
            destroyed = True
            parsed = parse_container_identity(name)
            if parsed:
                uid, pid = parsed
                registry().remove(f"{uid}-{pid}")
            logger.info("destroyed claw %s by session label", name)
        except Exception as e:
            logger.warning("remove container %s: %s", name, e)
    return destroyed


def destroy_all_for_user(user_id: int, username: str = "") -> int:
    """退出登录：销毁该用户全部 Claw 容器（含 session 未绑定的残留）。"""
    if user_id <= 0:
        return 0
    client = _docker_client()
    if not client:
        return 0
    reg = registry()
    destroyed = 0
    seen: set[str] = set()

    for c in client.containers.list(all=True, filters={"label": f"aida.user_id={user_id}"}):
        cid = c.id
        if cid in seen:
            continue
        seen.add(cid)
        name = (c.name or "").lstrip("/")
        try:
            c.remove(force=True)
            destroyed += 1
            parsed = parse_container_identity(name)
            if parsed:
                reg.remove(f"{parsed[0]}-{parsed[1]}")
            logger.info("destroyed claw %s (logout user_id=%s label)", name, user_id)
        except Exception as e:
            logger.warning("remove container %s: %s", name, e)

    patterns = (
        container_name_prefix_for_user(user_id, username),
        f"aida-claw-user{user_id}-p",
        f"claw-u{user_id}-p",
    )
    for pattern in patterns:
        for c in client.containers.list(all=True, filters={"name": pattern}):
            cid = c.id
            if cid in seen:
                continue
            seen.add(cid)
            name = (c.name or "").lstrip("/")
            try:
                c.remove(force=True)
                destroyed += 1
                parsed = parse_container_identity(name)
                if parsed:
                    uid, pid = parsed
                    reg.remove(f"{uid}-{pid}")
                if claw_edge_mode() == "path" and parsed:
                    from manager.nginx_writer import remove_claw_location

                    remove_claw_location(f"{parsed[0]}-{parsed[1]}")
                logger.info("destroyed claw %s (logout user_id=%s)", name, user_id)
            except Exception as e:
                logger.warning("remove container %s: %s", name, e)
    return destroyed


def destroy_allocation(key: str) -> bool:
    reg = registry()
    alloc = reg.get(key)
    if not alloc:
        return False

    client = _docker_client()
    if client:
        try:
            c = client.containers.get(alloc.container_name)
            c.remove(force=True)
        except Exception as e:
            logger.warning("remove container %s: %s", alloc.container_name, e)

    if claw_edge_mode() == "path":
        from manager.nginx_writer import remove_claw_location

        remove_claw_location(key)

    reg.remove(key)
    logger.info("destroyed claw %s", alloc.container_name)
    return True


def _allocation_has_active_session(alloc: ClawAllocation) -> bool:
    from manager.sessions import has_active_user_project_session

    return has_active_user_project_session(
        alloc.user_id,
        alloc.project_id,
        session_id=alloc.session_id,
    )


def rebind_session_claw(
    *,
    session_id: str,
    user_id: int,
    project_id: str = "",
    project_code: str = "",
    username: str = "",
) -> ClawAllocation | None:
    """Manager 重启或 session 绑定丢失时，按 user+project / Docker label 恢复绑定。"""
    if not claw_orchestration_enabled() or user_id <= 0:
        return None

    reg = registry()
    bound = reg.get_by_session(session_id)
    if bound:
        reg.touch_heartbeat(session_id)
        return bound

    client = _docker_client()
    if not client:
        return None

    if project_id:
        key = routing_key(user_id, project_id)
        alloc = reg.get(key)
        if alloc and _container_running(client, alloc.container_name):
            reg.bind_session(session_id, key)
            if project_code:
                alloc.project_code = project_code
            logger.info("rebound session %s to claw %s (registry)", session_id[:16], alloc.container_name)
            return alloc

        label_pid = sanitize_project_id(project_id)
        for c in client.containers.list(filters={"label": f"aida.user_id={user_id}"}):
            labels = c.labels or {}
            if labels.get("aida.project_id") != label_pid:
                continue
            name = (c.name or "").lstrip("/")
            if c.status != "running":
                continue
            parsed = parse_container_identity(name)
            if not parsed:
                continue
            uid, pid_part = parsed
            key = f"{uid}-{pid_part}"
            if not reg.get(key):
                ports = c.attrs.get("NetworkSettings", {}).get("Ports") or {}
                host_port = None
                for spec in ports.get("7401/tcp") or []:
                    if isinstance(spec, dict) and spec.get("HostPort"):
                        host_port = int(spec["HostPort"])
                        break
                if not host_port:
                    continue
                reg.reattach_port(host_port)
                alloc = ClawAllocation(
                    routing_key=key,
                    user_id=uid,
                    project_id=project_id,
                    project_code=project_code or project_id,
                    host_port=host_port,
                    container_id=c.id,
                    container_name=name,
                    session_id=session_id,
                )
                reg.register(alloc)
            reg.bind_session(session_id, key)
            alloc = reg.get(key)
            if alloc:
                logger.info("rebound session %s to claw %s (docker)", session_id[:16], name)
            return alloc

    for c in client.containers.list(filters={"label": f"aida.session_id={session_id[:64]}"}):
        if c.status != "running":
            continue
        name = (c.name or "").lstrip("/")
        parsed = parse_container_identity(name)
        if not parsed:
            continue
        uid, pid_part = parsed
        key = f"{uid}-{pid_part}"
        if not reg.get(key):
            ports = c.attrs.get("NetworkSettings", {}).get("Ports") or {}
            host_port = None
            for spec in ports.get("7401/tcp") or []:
                if isinstance(spec, dict) and spec.get("HostPort"):
                    host_port = int(spec["HostPort"])
                    break
            if not host_port:
                continue
            reg.reattach_port(host_port)
            alloc = ClawAllocation(
                routing_key=key,
                user_id=uid,
                project_id=pid_part,
                project_code=pid_part,
                host_port=host_port,
                container_id=c.id,
                container_name=name,
                session_id=session_id,
            )
            reg.register(alloc)
        reg.bind_session(session_id, key)
        alloc = reg.get(key)
        if alloc:
            logger.info("rebound session %s to claw %s (label)", session_id[:16], name)
        return alloc

    return None


def idle_reap(idle_seconds: int) -> int:
    """回收超时且无活跃 Manager 会话绑定的孤儿容器。返回销毁数量。"""
    if not claw_orchestration_enabled():
        return 0
    now = time.time()
    reaped = 0
    for alloc in list(registry().list_allocations()):
        if _allocation_has_active_session(alloc):
            continue
        if now - alloc.last_heartbeat < idle_seconds:
            continue
        if destroy_allocation(alloc.routing_key):
            reaped += 1
            logger.info(
                "idle reaped claw %s (no active session, idle %.0fs)",
                alloc.container_name,
                now - alloc.last_heartbeat,
            )
    return reaped


def touch_session_heartbeat(
    session_id: str,
    *,
    user_id: int = 0,
    project_id: str = "",
    project_code: str = "",
    username: str = "",
) -> bool:
    if registry().touch_heartbeat(session_id):
        return True
    alloc = rebind_session_claw(
        session_id=session_id,
        user_id=user_id,
        project_id=project_id,
        project_code=project_code,
        username=username,
    )
    return alloc is not None


def endpoint_for_session(session_id: str) -> str | None:
    alloc = registry().get_by_session(session_id)
    if not alloc:
        return None
    return container_endpoint_url(alloc.routing_key, alloc.host_port)
