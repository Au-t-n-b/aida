"""
device_install dc_io · 数据中心 API 同步包装 + 本地 scratch + 挂载盘降级。

《数据中心 API 调用规范》§6「一切数据读写走 API」：上游读取 / 产物写出统一经
DataCenterClient（语义寻址，token 可选 §1.5）。DC 不可达时降级到挂载盘
{AIDA_BUSINESS_ROOT}/project/<域>/<模块>/<阶段>/，二者都失败才报缺料。

本地 scratch（业务树之外，agent/runtime/scratch/device_install/<run_id>/）仅作：
  - openpyxl 读写缓冲（下载的上游 / 待上传的产物）
  - 运行态 JSON（tasks_state/sn_pool/sn_tables），不进数据中心
"""
from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Awaitable, Callable, TypeVar

from shared.datacenter.client import DataCenterClient
from shared.datacenter.errors import DataCenterError
from shared.datacenter.logging_utils import LOG

from .bridge import get_scratch_root
from .dc_paths import (
    DcLoc,
    artifact_key,
    artifact_key_name,
    install_output_loc,
    resolve_project_id,
)

_T = TypeVar("_T")

_XLSX_SUFFIXES = (".xlsx", ".xlsm")
_SKIP_PREFIXES = ("~$", ".~")


# ── 同步运行 async（step 在 worker 线程；路由可能在事件循环线程）────────────────

def _run_async(coro_factory: Callable[[], Awaitable[_T]]) -> _T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory())
    # 当前线程已有事件循环：另起线程跑独立循环，避免 "loop already running"
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(coro_factory())).result()


# ── DC 可用性 / token ─────────────────────────────────────────────────────────

def _dc_configured() -> bool:
    from shared.datacenter.config import datacenter_base
    try:
        return bool(datacenter_base())
    except RuntimeError:
        return False


def _dc_token() -> str | None:
    for key in ("DATA_CENTER_TOKEN", "AIDA_DATACENTER_TOKEN", "DC_TOKEN"):
        v = os.environ.get(key, "").strip()
        if v:
            return v
    return None


# ── scratch 目录 ──────────────────────────────────────────────────────────────

def scratch_for_run(work_root: Path | str, run_id: str) -> Path:
    base = Path(work_root) if work_root else get_scratch_root()
    rid = (run_id or "default").replace("/", "_").replace("\\", "_")
    p = (base / rid).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _subdir(ctx, name: str) -> Path:
    p = scratch_for_run(ctx.work_root, ctx.run_id) / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def input_dir(ctx) -> Path:
    """上游下载 + HITL 上传缓冲。"""
    return _subdir(ctx, "inbox")


def output_dir(ctx) -> Path:
    """产物生成缓冲（生成后 publish_output 上传 DC）。"""
    return _subdir(ctx, "out")


def runtime_dir(ctx) -> Path:
    """运行态 JSON（tasks_state/sn_pool/sn_tables）。"""
    return _subdir(ctx, "state")


def images_dir(ctx) -> Path:
    return _subdir(ctx, "images")


def shared_uploads_dir(work_root: Path | str, sub: str = "inbox") -> Path:
    """HITL 上传落点（与 run 无关，/upload 无 run_id）。run 内 fetch 会一并扫描。"""
    base = Path(work_root) if work_root else get_scratch_root()
    p = (base / "_uploads" / sub).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def runtime_dir_for(work_root: Path | str, run_id: str) -> Path:
    """go_back / run_patch（持 work_root + run_state.run_id）定位运行态目录。"""
    p = scratch_for_run(work_root, run_id) / "state"
    p.mkdir(parents=True, exist_ok=True)
    return p


def output_dir_for(work_root: Path | str, run_id: str) -> Path:
    p = scratch_for_run(work_root, run_id) / "out"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── 文件名匹配 ────────────────────────────────────────────────────────────────

def _skip(name: str) -> bool:
    n = (name or "").strip()
    return any(n.startswith(p) for p in _SKIP_PREFIXES)


def _match(name: str, keywords: tuple[str, ...], exclude: tuple[str, ...]) -> bool:
    low = name.lower()
    if keywords and not any(k.lower() in low for k in keywords):
        return False
    if exclude and any(e.lower() in low for e in exclude):
        return False
    return True


def _scan_local(directory: Path, keywords: tuple[str, ...], exclude: tuple[str, ...]) -> Path | None:
    if not directory.is_dir():
        return None
    for p in sorted(directory.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in _XLSX_SUFFIXES:
            continue
        if _skip(p.name):
            continue
        if _match(p.name, keywords, exclude):
            return p.resolve()
    return None


# ── 上游读取（DC → 挂载盘降级）──────────────────────────────────────────────────

def fetch_to_scratch(
    ctx,
    loc: DcLoc,
    *,
    keywords: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
    file_name: str | None = None,
) -> Path | None:
    """定位并取得上游文件到本地：scratch 上传 → DC → 挂载盘降级。返回本地可读路径或 None。"""
    inbox = input_dir(ctx)

    # 1) scratch inbox（既有下载）+ 共享上传区（HITL /upload）优先
    for d in (inbox, shared_uploads_dir(ctx.work_root, "inbox")):
        hit = _scan_local(d, keywords, exclude)
        if hit:
            return hit

    project_id = resolve_project_id(ctx.project)

    # 2) 数据中心
    if _dc_configured():
        try:
            return _run_async(
                lambda: _dc_download(loc, project_id, keywords, exclude, file_name, inbox)
            )
        except DataCenterError as e:
            LOG.warning("device_install fetch DC error loc=%s: %s", loc.describe(), e)
        except Exception as e:  # noqa: BLE001
            LOG.warning("device_install fetch DC unexpected loc=%s: %s", loc.describe(), e)

    # 3) 挂载盘降级
    disk_hit = _scan_local(loc.disk_dir(), keywords, exclude)
    if disk_hit:
        return disk_hit
    return None


async def _dc_download(
    loc: DcLoc,
    project_id: str,
    keywords: tuple[str, ...],
    exclude: tuple[str, ...],
    file_name: str | None,
    inbox: Path,
) -> Path | None:
    client = DataCenterClient(_dc_token())
    ref = loc.ref(project_id, file_name=file_name)
    chosen_name = file_name
    if not chosen_name:
        data = await client.list_files(ref)
        items = data.get("list") or []
        for item in items:
            name = str(item.get("fileName") or "")
            if name and name.lower().endswith(_XLSX_SUFFIXES) and _match(name, keywords, exclude):
                chosen_name = name
                break
        if not chosen_name:
            return None
        ref = loc.ref(project_id, file_name=chosen_name)
    content = await client.download_file(ref)
    dest = inbox / chosen_name
    dest.write_bytes(content)
    return dest.resolve()


def upstream_exists(loc: DcLoc, project: dict[str, Any] | None, *, keywords: tuple[str, ...] = ()) -> tuple[bool, str]:
    """上游文件存在性（DC list → 挂载盘 glob）。返回 (found, 人读位置)。"""
    project_id = resolve_project_id(project)
    if _dc_configured():
        try:
            found = _run_async(lambda: _dc_exists(loc, project_id, keywords))
            return found, loc.describe()
        except Exception as e:  # noqa: BLE001
            LOG.info("device_install upstream_exists DC unavailable loc=%s: %s", loc.describe(), e)
    disk_hit = _scan_local(loc.disk_dir(), keywords, ())
    return bool(disk_hit), str(disk_hit or loc.disk_dir())


async def _dc_exists(loc: DcLoc, project_id: str, keywords: tuple[str, ...]) -> bool:
    client = DataCenterClient(_dc_token())
    data = await client.list_files(loc.ref(project_id))
    for item in (data.get("list") or []):
        name = str(item.get("fileName") or "")
        if name and _match(name, keywords, ()):
            return True
    return False


# ── 产物写出（DC → 挂载盘降级）──────────────────────────────────────────────────

def publish_output(ctx, local_path: Path | str, *, display_name: str | None = None) -> str:
    """生成的产物上传 ops-install/输出结果（DC 失败降级写挂载盘）。返回稳定逻辑键。"""
    p = Path(local_path)
    name = p.name
    key = artifact_key(name)
    try:
        content = p.read_bytes()
    except OSError as e:
        LOG.warning("device_install publish read failed %s: %s", p, e)
        return key

    project_id = resolve_project_id(ctx.project)
    if _dc_configured():
        try:
            _run_async(lambda: _dc_upload(project_id, content, name, display_name))
            return key
        except DataCenterError as e:
            LOG.warning("device_install publish DC error %s: %s", name, e)
        except Exception as e:  # noqa: BLE001
            LOG.warning("device_install publish DC unexpected %s: %s", name, e)

    # 挂载盘降级
    disk_dir = install_output_loc().disk_dir()
    disk_dir.mkdir(parents=True, exist_ok=True)
    (disk_dir / name).write_bytes(content)
    return key


async def _dc_upload(project_id: str, content: bytes, name: str, display_name: str | None) -> None:
    client = DataCenterClient(_dc_token())
    ref = install_output_loc(name).ref(project_id, file_name=name)
    await client.upload_file(ref, content, name, file_display_name=display_name or name)


def fetch_output_by_name(work_root: Path | str, file_name: str, project: dict[str, Any] | None = None) -> Path | None:
    """产物预览/下载解析：scratch out → DC → 挂载盘。返回本地可读路径或 None。"""
    name = artifact_key_name(file_name)
    if not name:
        return None
    base = Path(work_root) if work_root else get_scratch_root()

    # 1) scratch（本会话刚生成，最快）：扫所有 run 的 out/
    candidates = sorted(base.glob(f"*/out/{name}"), key=lambda p: p.stat().st_mtime, reverse=True)
    for c in candidates:
        if c.is_file():
            return c.resolve()

    project_id = resolve_project_id(project)
    # 2) 数据中心 → 下载到预览缓存
    if _dc_configured():
        try:
            cache = (base / "_preview")
            cache.mkdir(parents=True, exist_ok=True)
            return _run_async(lambda: _dc_download_named(project_id, name, cache))
        except Exception as e:  # noqa: BLE001
            LOG.info("device_install preview DC unavailable %s: %s", name, e)

    # 3) 挂载盘降级
    disk = install_output_loc().disk_dir() / name
    if disk.is_file():
        return disk.resolve()
    return None


async def _dc_download_named(project_id: str, name: str, cache: Path) -> Path | None:
    client = DataCenterClient(_dc_token())
    ref = install_output_loc(name).ref(project_id, file_name=name)
    content = await client.download_file(ref)
    dest = cache / name
    dest.write_bytes(content)
    return dest.resolve()


def list_output_names(work_root: Path | str, project: dict[str, Any] | None = None) -> list[str]:
    """已产出产物文件名（scratch out ∪ DC ∪ 挂载盘）。供 SDUI 补扫。"""
    names: set[str] = set()
    base = Path(work_root) if work_root else get_scratch_root()
    for c in base.glob("*/out/*"):
        if c.is_file() and not _skip(c.name):
            names.add(c.name)

    project_id = resolve_project_id(project)
    if _dc_configured():
        try:
            for n in _run_async(lambda: _dc_list_names(project_id)):
                names.add(n)
        except Exception as e:  # noqa: BLE001
            LOG.info("device_install list_output DC unavailable: %s", e)

    disk_dir = install_output_loc().disk_dir()
    if disk_dir.is_dir():
        for p in disk_dir.iterdir():
            if p.is_file() and not _skip(p.name):
                names.add(p.name)
    return sorted(names)


async def _dc_list_names(project_id: str) -> list[str]:
    client = DataCenterClient(_dc_token())
    data = await client.list_files(install_output_loc().ref(project_id))
    return [str(i.get("fileName") or "") for i in (data.get("list") or []) if i.get("fileName")]


# ── 运行态 JSON（纯本地 scratch）────────────────────────────────────────────────

def tasks_state_path(ctx) -> Path:
    return runtime_dir(ctx) / "tasks_state.json"


def sn_pool_path(ctx) -> Path:
    return runtime_dir(ctx) / "sn_pool.json"


def sn_tables_path(ctx) -> Path:
    return runtime_dir(ctx) / "sn_tables.json"


# ── 清理（reset / go_back · 仅本地 scratch + 挂载盘降级目录）────────────────────

def clear_run_scratch(work_root: Path | str, run_id: str, *, subdirs: tuple[str, ...] = ("out", "state", "images")) -> list[str]:
    removed: list[str] = []
    run_dir = scratch_for_run(work_root, run_id)
    for sub in subdirs:
        d = run_dir / sub
        if not d.is_dir():
            continue
        for p in list(d.iterdir()):
            if p.is_file() and not _skip(p.name):
                try:
                    p.unlink()
                    removed.append(p.name)
                except OSError:
                    pass
    return removed


def clear_output_patterns(work_root: Path | str, run_id: str, patterns: tuple[str, ...]) -> int:
    """删下游产物（scratch out + 挂载盘 输出结果）。DC 无删除接口，重传覆盖即可。"""
    n = 0
    out = output_dir_for(work_root, run_id)
    disk = install_output_loc().disk_dir()
    for base in (out, disk):
        if not base.is_dir():
            continue
        for pat in patterns:
            for f in base.glob(pat):
                try:
                    f.unlink()
                    n += 1
                except OSError:
                    pass
    return n
