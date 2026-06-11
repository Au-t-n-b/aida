"""工勘孪生 · FastAPI 路由（/api/sog/* 与 /data/sog-assets/*）。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from .sog_assets import SogAssetStore, validate_asset_id

router = APIRouter(tags=["sog"])
_store = SogAssetStore()


def _invalid_asset_id() -> HTTPException:
    return HTTPException(status_code=400, detail="invalid asset id")


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
