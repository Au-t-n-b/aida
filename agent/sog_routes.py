"""实景孪生 · FastAPI 路由（/api/sog/* 与 /data/sog-assets/*）。"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .sog_assets import SogAssetStore, SogSceneStore, validate_asset_id

router = APIRouter(tags=["sog"])
_store = SogAssetStore()
_scene_store = SogSceneStore()
_probe_path = Path(
    os.environ.get(
        "AIDA_SOG_PROBE_EVENTS",
        str(Path(__file__).resolve().parents[1] / "data" / "sog-probe-events.json"),
    )
).resolve()
_probe_lock = threading.Lock()


def _invalid_asset_id() -> HTTPException:
    return HTTPException(status_code=400, detail="invalid asset id")


class SogSceneUpdateReq(BaseModel):
    name: str


class SogProbeEvent(BaseModel):
    event: str
    payload: dict[str, Any] = Field(default_factory=dict)
    sceneId: str | None = None
    assetId: str | None = None
    viewerSrc: str | None = None
    pageStatus: str | None = None
    receivedAt: str | None = None


def _read_probe_events() -> list[dict[str, Any]]:
    if not _probe_path.is_file():
        return []
    try:
        data = json.loads(_probe_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    return data if isinstance(data, list) else []


def _write_probe_events(events: list[dict[str, Any]]) -> None:
    _probe_path.parent.mkdir(parents=True, exist_ok=True)
    _probe_path.write_text(
        json.dumps(events[-500:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@router.get("/api/sog/scenes")
def list_sog_scenes() -> list[dict[str, Any]]:
    return _scene_store.list_scenes()


@router.get("/api/sog/scenes/{scene_id}")
def get_sog_scene_meta(scene_id: str) -> dict[str, Any]:
    try:
        return _scene_store.get_scene(scene_id)
    except ValueError as exc:
        raise _invalid_asset_id() from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="scene not found") from exc


@router.patch("/api/sog/scenes/{scene_id}")
def update_sog_scene(scene_id: str, body: SogSceneUpdateReq) -> dict[str, Any]:
    try:
        return _scene_store.update_scene_name(scene_id, body.name)
    except ValueError as exc:
        message = str(exc)
        if "scene name required" in message:
            raise HTTPException(status_code=400, detail="scene name required") from exc
        raise _invalid_asset_id() from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="scene not found") from exc


@router.delete("/api/sog/scenes/{scene_id}")
def delete_sog_scene(scene_id: str) -> dict[str, Any]:
    try:
        return _scene_store.delete_scene(scene_id)
    except ValueError as exc:
        raise _invalid_asset_id() from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="scene not found") from exc


@router.post("/api/sog/scenes/upload")
async def upload_sog_scene_video(file: UploadFile = File(...)) -> dict[str, Any]:
    filename = (file.filename or "现场视频.mp4").strip() or "现场视频.mp4"
    # 当前仅登记训练任务，训练/转码服务后续接入；读取一小段确保请求体被消费。
    await file.read(1024)
    return _scene_store.create_training_scene(filename)


@router.get("/api/sog/assets/{asset_id}")
def get_sog_asset(asset_id: str) -> dict[str, Any]:
    try:
        validate_asset_id(asset_id)
    except ValueError as exc:
        raise _invalid_asset_id() from exc
    return _store.get_asset(asset_id)


@router.get("/api/sog/assets/{asset_id}/hotspots")
def get_sog_hotspots(asset_id: str) -> list[dict[str, Any]]:
    try:
        return _store.read_hotspots(asset_id)
    except ValueError as exc:
        raise _invalid_asset_id() from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/api/sog/assets/{asset_id}/hotspots")
def put_sog_hotspots(asset_id: str, body: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        return _store.save_hotspots(asset_id, body)
    except ValueError as exc:
        raise _invalid_asset_id() from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/sog/assets/{asset_id}/settings")
def get_sog_settings(asset_id: str) -> dict[str, Any]:
    try:
        return _store.read_settings(asset_id, camera=_scene_store.get_camera_for_asset(asset_id))
    except ValueError as exc:
        raise _invalid_asset_id() from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/sog/probe-events")
def append_sog_probe_event(body: SogProbeEvent) -> dict[str, Any]:
    with _probe_lock:
        events = _read_probe_events()
        item = body.dict()
        item["receivedAt"] = datetime.now(timezone.utc).isoformat()
        events.append(item)
        _write_probe_events(events)
        return {"ok": True, "count": len(events[-500:])}


@router.get("/api/sog/probe-events")
def list_sog_probe_events(limit: int = 120) -> list[dict[str, Any]]:
    safe_limit = max(1, min(500, limit))
    with _probe_lock:
        return _read_probe_events()[-safe_limit:]


@router.delete("/api/sog/probe-events")
def clear_sog_probe_events() -> dict[str, Any]:
    with _probe_lock:
        _write_probe_events([])
    return {"ok": True}


@router.get("/data/sog-assets/{asset_id}/scene.sog")
def get_sog_scene(asset_id: str) -> FileResponse:
    try:
        validate_asset_id(asset_id)
        scene_path = _store.scene_path(asset_id)
    except ValueError as exc:
        raise _invalid_asset_id() from exc

    if not scene_path.is_file():
        raise HTTPException(status_code=404, detail="scene.sog not found")

    return FileResponse(
        path=str(scene_path),
        media_type="application/octet-stream",
        filename=scene_path.name,
    )
