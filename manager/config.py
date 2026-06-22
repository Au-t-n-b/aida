"""Manager 配置（环境变量 / agent/.env）。"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


_AIDA_ROOT = _repo_root()
if str(_AIDA_ROOT) not in sys.path:
    sys.path.insert(0, str(_AIDA_ROOT))


def _load_agent_env() -> None:
    env_path = _repo_root() / "agent" / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


_load_agent_env()


def datacenter_base() -> str:
    url = (
        os.environ.get("DATA_CENTER_BASE_URL")
        or os.environ.get("AIDA_DATACENTER_BASE")
    )
    if not url:
        raise RuntimeError(
            "DATA_CENTER_BASE_URL 未配置：请在 agent/.env 中设置远端数据中心 API 地址"
            "（例：DATA_CENTER_BASE_URL=http://10.143.2.231:8000）"
        )
    return url.rstrip("/")


def aida_agent_base() -> str:
    return os.environ.get("AIDA_AGENT_BASE_URL", "http://127.0.0.1:7401").rstrip("/")


def manager_host() -> str:
    return os.environ.get("MANAGER_HOST", "0.0.0.0")


def manager_port() -> int:
    return int(os.environ.get("MANAGER_PORT", "8081"))


def business_root() -> Path:
    """项目业务数据根目录（与 agent AIDA_BUSINESS_ROOT 对齐）。"""
    raw = os.environ.get("AIDA_BUSINESS_ROOT", "").strip()
    if raw:
        return Path(raw).resolve()
    linux_default = Path("/opt/aida/aida-data/business")
    if linux_default.is_dir():
        return linux_default.resolve()
    return (_repo_root() / "data").resolve()


def _is_local_host(url: str) -> bool:
    from urllib.parse import urlparse

    host = (urlparse(url).hostname or "").lower()
    return host in ("127.0.0.1", "localhost", "::1")


def _is_private_datacenter_host(url: str) -> bool:
    """内网数据中心 IP 必须直连；走企业 HTTP_PROXY 常被网关 504。"""
    from urllib.parse import urlparse
    import ipaddress

    host = (urlparse(url).hostname or "").lower()
    if _is_local_host(url):
        return True
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


def http_proxy() -> str | None:
    base = datacenter_base()
    if _is_private_datacenter_host(base):
        return None
    return (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("http_proxy")
        or None
    )


def ssl_verify() -> bool:
    v = os.environ.get("ZHIPU_SSL_VERIFY", "").strip().lower()
    if v in ("1", "true", "yes"):
        return True
    if v in ("0", "false", "no"):
        return False
    return http_proxy() is None


def claw_orchestration_enabled() -> bool:
    return os.environ.get("AIDA_CLAW_ORCHESTRATION", "").strip().lower() in ("1", "true", "yes")


def claw_image() -> str:
    return os.environ.get("CLAW_IMAGE", "aida/claw_liwen:dev").strip()


def claw_data_mount() -> str:
    return os.environ.get("CLAW_DATA_MOUNT", "/opt/aida/aida-data").strip()


def claw_port_pool_start() -> int:
    return int(os.environ.get("CLAW_PORT_POOL_START", "17501"))


def claw_port_pool_end() -> int:
    return int(os.environ.get("CLAW_PORT_POOL_END", "17600"))


def claw_edge_base() -> str:
    return os.environ.get("CLAW_EDGE_BASE_URL", "http://10.143.2.231").rstrip("/")


def claw_edge_mode() -> str:
    """port = 直连 host port；path = nginx /claw/{key}/"""
    return os.environ.get("CLAW_EDGE_MODE", "port").strip().lower()


def claw_idle_seconds() -> int:
    return int(os.environ.get("CLAW_IDLE_SECONDS", "1800"))


def nginx_conf_dir() -> Path | None:
    raw = os.environ.get("NGINX_CONF_DIR", "").strip()
    if not raw:
        return None
    return Path(raw)


def nginx_reload_cmd() -> str | None:
    return os.environ.get("NGINX_RELOAD_CMD", "nginx -s reload").strip() or None


def container_endpoint_url(routing_key: str, host_port: int) -> str:
    if claw_edge_mode() == "path":
        return f"{claw_edge_base()}/claw/{routing_key}/"
    return f"{claw_edge_base()}:{host_port}/"


def claw_checkpoint_path(user_id: int, project_id: str) -> str:
    from manager.registry import sanitize_project_id

    pid = sanitize_project_id(project_id)
    mount = claw_data_mount()
    return f"{mount}/runtime/checkpoints/u{user_id}-p{pid}.db"


def claw_org_assets_bind() -> str:
    return f"{claw_data_mount()}/business/org-assets"


def claw_container_project_bind() -> str:
    return f"{claw_data_mount()}/business/project"


def claw_host_project_path(project_id: str) -> str:
    from manager.registry import project_filesystem_id

    pid = project_filesystem_id(project_id)
    return f"{claw_data_mount()}/business/projects/{pid}"


def claw_skills_host_bind() -> str:
    return os.environ.get("CLAW_SKILLS_HOST", f"{claw_data_mount()}/skill/org").strip()


def claw_skills_container_bind() -> str:
    return os.environ.get("CLAW_SKILLS_CONTAINER", "/app/agent/skills").strip()


def aida_repo_root() -> str:
    return os.environ.get("AIDA_REPO_ROOT", "/opt/aida_liwen").strip()


def claw_legacy_skill_volumes() -> dict[str, dict[str, str]]:
    """挂载仍依赖 skills/<name>/ 原始工作区的 skill（如 software_deployment runtime/ProjectData）。"""
    root = aida_repo_root()
    out: dict[str, dict[str, str]] = {}
    for name in ("software_deployment",):
        host = f"{root}/skills/{name}"
        container = f"/app/skills/{name}"
        out[host] = {"bind": container, "mode": "rw"}
    return out


def claw_container_volumes(project_id: str) -> dict[str, dict[str, str]]:
    """Claw bind-mount：org-assets、项目目录、checkpoint、skill/org → /app/agent/skills。"""
    mount = claw_data_mount()
    org = claw_org_assets_bind()
    host_proj = claw_host_project_path(project_id)
    container_proj = claw_container_project_bind()
    checkpoints = f"{mount}/runtime/checkpoints"
    skills_host = claw_skills_host_bind()
    skills_container = claw_skills_container_bind()
    volumes = {
        org: {"bind": org, "mode": "rw"},
        host_proj: {"bind": container_proj, "mode": "rw"},
        checkpoints: {"bind": checkpoints, "mode": "rw"},
        skills_host: {"bind": skills_container, "mode": "rw"},
    }
    volumes.update(claw_legacy_skill_volumes())
    return volumes


def claw_env_for_container(user_id: int, project_id: str, checkpoint_db: str) -> dict[str, str]:
    from manager.registry import project_filesystem_id

    mount = claw_data_mount()
    org_root = claw_org_assets_bind()
    proj_root = claw_container_project_bind()
    env: dict[str, str] = {
        "AIDA_BUSINESS_ROOT": f"{mount}/business",
        "AIDA_CHECKPOINT_DB": checkpoint_db,
        "AIDA_PROJECT_ID": project_filesystem_id(project_id),
        "ORG_ROOT": org_root,
        "PROJ_ROOT": proj_root,
        "AIDA_USE_NANOBOT_LLM": "1",
        "AIDA_CHAT_VIA_NANOBOT": "1",
        "NANOBOT_API_URL": "http://127.0.0.1:8900",
        "NO_PROXY": "127.0.0.1,localhost,host.docker.internal",
        "no_proxy": "127.0.0.1,localhost,host.docker.internal",
    }
    for key in (
        "ZHIPU_API_KEY",
        "ZHIPU_BASE_URL",
        "ZHIPU_MODEL",
        "DATA_CENTER_BASE_URL",
        "MAILGW_BASE_URL",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_HOST",
        "HTTP_PROXY",
        "HTTPS_PROXY",
    ):
        val = os.environ.get(key, "").strip()
        if val:
            env[key] = val
    dc = env.get("DATA_CENTER_BASE_URL", "")
    if dc and "host.docker.internal" not in dc and _is_local_host(dc):
        env["DATA_CENTER_BASE_URL"] = dc.replace("127.0.0.1", "host.docker.internal").replace(
            "localhost", "host.docker.internal"
        )
    mg = env.get("MAILGW_BASE_URL", "")
    if mg and _is_local_host(mg):
        env["MAILGW_BASE_URL"] = mg.replace("127.0.0.1", "host.docker.internal").replace(
            "localhost", "host.docker.internal"
        )
    return env
