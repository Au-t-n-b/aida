"""Claw 容器注册表：routing_key / 端口池 / 会话绑定。"""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field


def sanitize_project_id(project_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", project_id.strip())
    return (cleaned[:12] or "default").lower()


def project_filesystem_id(project_id: str) -> str:
    """数据中心 business/projects/ 目录名（完整 UUID32，不截断）。"""
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", project_id.strip())
    if not cleaned:
        raise ValueError("invalid project_id")
    return cleaned.lower()


def sanitize_username(username: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", (username or "").strip().lower())
    return (cleaned[:16] or "user")


def routing_key(user_id: int, project_id: str) -> str:
    return f"{user_id}-{sanitize_project_id(project_id)}"


def container_name(user_id: int, project_id: str, username: str = "") -> str:
    """Docker 容器名：含用户名 + user_id。例 aida-claw-admin-u1-p9aef7388。"""
    uid = max(int(user_id), 0)
    user_slug = sanitize_username(username) if username else f"user{uid}"
    pid = sanitize_project_id(project_id)
    name = f"aida-claw-{user_slug}-u{uid}-p{pid}"
    if len(name) > 63:
        fixed = len(f"aida-claw--u{uid}-p{pid}")
        budget = max(63 - fixed, 4)
        user_slug = user_slug[:budget]
        name = f"aida-claw-{user_slug}-u{uid}-p{pid}"
    return name


def parse_container_identity(name: str) -> tuple[int, str] | None:
    """从容器名解析 (user_id, project_slug)。兼容新旧命名。"""
    n = (name or "").lstrip("/")
    m = re.match(r"^aida-claw-.+-u(\d+)-p([a-z0-9]+)$", n)
    if m:
        return int(m.group(1)), m.group(2)
    for prefix in ("aida-claw-user", "claw-u"):
        if not n.startswith(prefix):
            continue
        rest = n[len(prefix) :]
        if "-p" not in rest:
            return None
        uid_s, _, pid = rest.partition("-p")
        try:
            return int(uid_s), pid
        except ValueError:
            return None
    return None


def container_name_prefix_for_user(user_id: int, username: str = "") -> str:
    uid = max(int(user_id), 0)
    user_slug = sanitize_username(username) if username else f"user{uid}"
    return f"aida-claw-{user_slug}-u{uid}-p"


@dataclass
class ClawAllocation:
    routing_key: str
    user_id: int
    project_id: str
    project_code: str
    host_port: int
    container_id: str
    container_name: str
    session_id: str | None = None
    last_heartbeat: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)


class ClawRegistry:
    def __init__(self, port_start: int, port_end: int) -> None:
        if port_end < port_start:
            raise ValueError("port pool invalid")
        self._lock = threading.Lock()
        self._by_key: dict[str, ClawAllocation] = {}
        self._by_session: dict[str, str] = {}
        self._free_ports = list(range(port_start, port_end + 1))

    def get(self, key: str) -> ClawAllocation | None:
        with self._lock:
            return self._by_key.get(key)

    def get_by_session(self, session_id: str) -> ClawAllocation | None:
        with self._lock:
            key = self._by_session.get(session_id)
            return self._by_key.get(key) if key else None

    def allocate_port(self) -> int:
        with self._lock:
            if not self._free_ports:
                raise RuntimeError("Claw 端口池耗尽")
            return self._free_ports.pop(0)

    def release_port(self, port: int) -> None:
        with self._lock:
            if port not in self._free_ports:
                self._free_ports.append(port)
                self._free_ports.sort()

    def register(self, alloc: ClawAllocation) -> ClawAllocation:
        with self._lock:
            old = self._by_key.get(alloc.routing_key)
            if old and old.host_port != alloc.host_port:
                if old.host_port in self._free_ports:
                    pass
                elif old.host_port not in [a.host_port for a in self._by_key.values()]:
                    self._free_ports.append(old.host_port)
                    self._free_ports.sort()
            self._by_key[alloc.routing_key] = alloc
            if alloc.session_id:
                self._by_session[alloc.session_id] = alloc.routing_key
            if alloc.host_port in self._free_ports:
                self._free_ports.remove(alloc.host_port)
            return alloc

    def bind_session(self, session_id: str, key: str) -> ClawAllocation | None:
        with self._lock:
            self._by_session[session_id] = key
            alloc = self._by_key.get(key)
            if alloc:
                alloc.session_id = session_id
                alloc.last_heartbeat = time.time()
            return alloc

    def touch_heartbeat(self, session_id: str) -> bool:
        with self._lock:
            key = self._by_session.get(session_id)
            if not key:
                return False
            alloc = self._by_key.get(key)
            if not alloc:
                return False
            alloc.last_heartbeat = time.time()
            return True

    def unbind_session(self, session_id: str) -> ClawAllocation | None:
        with self._lock:
            key = self._by_session.pop(session_id, None)
            if not key:
                return None
            alloc = self._by_key.get(key)
            if alloc:
                alloc.session_id = None
            return alloc

    def remove(self, routing_key: str) -> ClawAllocation | None:
        with self._lock:
            alloc = self._by_key.pop(routing_key, None)
            if not alloc:
                return None
            if alloc.session_id:
                self._by_session.pop(alloc.session_id, None)
            self._free_ports.append(alloc.host_port)
            self._free_ports.sort()
            return alloc

    def list_allocations(self) -> list[ClawAllocation]:
        with self._lock:
            return list(self._by_key.values())

    def reattach_port(self, port: int) -> None:
        """Manager 重启后从运行中容器恢复端口占用。"""
        with self._lock:
            if port in self._free_ports:
                self._free_ports.remove(port)


_REGISTRY: ClawRegistry | None = None


def get_registry(port_start: int, port_end: int) -> ClawRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ClawRegistry(port_start, port_end)
    return _REGISTRY
