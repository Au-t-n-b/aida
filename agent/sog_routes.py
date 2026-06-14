"""实景孪生 · FastAPI 路由（/api/sog/* 与 /data/sog-assets/*）。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .sog_assets import SogAssetStore, SogSceneStore, validate_asset_id

router = APIRouter(tags=["sog"])
_store = SogAssetStore()
_scene_store = SogSceneStore()


def _invalid_asset_id() -> HTTPException:
    return HTTPException(status_code=400, detail="invalid asset id")


class SogSceneUpdateReq(BaseModel):
    name: str


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
        return _store.read_settings(asset_id)
    except ValueError as exc:
        raise _invalid_asset_id() from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
