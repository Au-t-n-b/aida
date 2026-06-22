"""Datacenter I/O facade for proposal module (ContextVar-bound per request)."""
from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterator

from shared.datacenter import DataCenterClient, DataCenterError
from shared.datacenter.types import SemanticFileRef

from agent.proposal.errors import ProposalApiError
from agent.services.dc_path_mapper import map_project_relative

_dc_project_id: ContextVar[str | None] = ContextVar("proposal_dc_project_id", default=None)
_dc_token: ContextVar[str | None] = ContextVar("proposal_dc_token", default=None)


def get_dc_project_id() -> str | None:
    return _dc_project_id.get()


def get_dc_token() -> str | None:
    return _dc_token.get()


def set_dc_context(project_id: str, token: str | None) -> tuple[Any, Any]:
    return (
        _dc_project_id.set(project_id),
        _dc_token.set(token),
    )


def reset_dc_context(tokens: tuple[Any, Any]) -> None:
    _dc_project_id.reset(tokens[0])
    _dc_token.reset(tokens[1])


@contextmanager
def proposal_dc_context(project_id: str, token: str | None) -> Iterator[None]:
    tokens = set_dc_context(project_id, token)
    try:
        yield
    finally:
        reset_dc_context(tokens)


def _require_token() -> str:
    token = get_dc_token()
    if not token:
        raise ProposalApiError(
            401,
            "DC_TOKEN_REQUIRED",
            "需要 Authorization: Bearer <token> 访问数据中心",
        )
    return token


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


async def read_bytes_async(ref: SemanticFileRef, token: str | None = None) -> bytes | None:
    tok = token or _require_token()
    try:
        return await DataCenterClient(tok).download_file(ref)
    except DataCenterError as exc:
        if exc.status_code == 404:
            return None
        raise ProposalApiError(
            exc.status_code or 502,
            "DC_READ_ERROR",
            str(exc.message or exc),
        ) from exc


async def write_bytes_async(
    ref: SemanticFileRef,
    content: bytes,
    filename: str,
    token: str | None = None,
) -> dict[str, Any]:
    tok = token or _require_token()
    if not ref.file_name:
        ref = SemanticFileRef(
            project_id=ref.project_id,
            module_code=ref.module_code,
            file_stage=ref.file_stage,
            folder_sub_path=ref.folder_sub_path,
            file_name=filename,
        )
    try:
        return await DataCenterClient(tok).upload_file(ref, content, filename)
    except DataCenterError as exc:
        raise ProposalApiError(
            exc.status_code or 502,
            "DC_WRITE_ERROR",
            str(exc.message or exc),
        ) from exc


async def exists_async(ref: SemanticFileRef, token: str | None = None) -> bool:
    tok = token or _require_token()
    if not ref.file_name:
        return False
    try:
        data = await DataCenterClient(tok).list_files(ref)
        items = data.get("list") or []
        return any(item.get("fileName") == ref.file_name for item in items)
    except DataCenterError as exc:
        if exc.status_code == 404:
            return False
        raise ProposalApiError(
            exc.status_code or 502,
            "DC_LIST_ERROR",
            str(exc.message or exc),
        ) from exc


def read_bytes(ref: SemanticFileRef, token: str | None = None) -> bytes | None:
    return _run_async(read_bytes_async(ref, token))


def write_bytes(
    ref: SemanticFileRef,
    content: bytes,
    filename: str,
    token: str | None = None,
) -> dict[str, Any]:
    return _run_async(write_bytes_async(ref, content, filename, token))


def exists(ref: SemanticFileRef, token: str | None = None) -> bool:
    return _run_async(exists_async(ref, token))


def path_to_ref(project_id: str, path: Path) -> SemanticFileRef:
    from agent.proposal.draft_store import physical_project_root

    rel = path.relative_to(physical_project_root(project_id)).as_posix()
    mapped = map_project_relative(project_id, rel)
    if mapped is None or mapped.ref.file_name is None:
        raise ValueError(f"cannot map path to file ref: {rel}")
    return mapped.ref


def load_json_at(project_id: str, relative: str, default: Any) -> Any:
    mapped = map_project_relative(project_id, relative)
    if mapped is None or mapped.ref.file_name is None:
        return default
    raw = read_bytes(mapped.ref)
    if raw is None:
        return default
    return json.loads(raw.decode("utf-8"))


def save_json_at(project_id: str, relative: str, data: Any) -> None:
    mapped = map_project_relative(project_id, relative)
    if mapped is None or mapped.ref.file_name is None:
        raise ValueError(f"cannot map path for save: {relative}")
    content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    write_bytes(mapped.ref, content, mapped.ref.file_name)


def path_exists(project_id: str, path: Path) -> bool:
    try:
        ref = path_to_ref(project_id, path)
    except ValueError:
        return False
    return exists(ref)


async def list_file_names_async(
    ref: SemanticFileRef,
    token: str | None = None,
) -> set[str]:
    tok = token or _require_token()
    try:
        data = await DataCenterClient(tok).list_files(ref)
    except DataCenterError as exc:
        if exc.status_code == 404:
            return set()
        raise ProposalApiError(
            exc.status_code or 502,
            "DC_LIST_ERROR",
            str(exc.message or exc),
        ) from exc
    return {
        str(item.get("fileName") or "").strip()
        for item in (data.get("list") or [])
        if str(item.get("fileName") or "").strip()
    }


def list_file_names(ref: SemanticFileRef, token: str | None = None) -> set[str]:
    return _run_async(list_file_names_async(ref, token))
