"""实景孪生 · SOG 资产存储与标签/settings 生成（移植自 sog-hotspot-viewer/server/asset-store.mjs）。"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

SOG_FILE_NAME = "scene.sog"
HOTSPOTS_FILE_NAME = "hotspots.json"
META_FILE_NAME = "meta.json"
_REPO_DATA_ROOT = Path(__file__).resolve().parents[1] / "data"
SOG_DATA_ROOT = Path(os.environ.get("AIDA_SOG_DATA_ROOT", str(_REPO_DATA_ROOT / "sog-assets"))).resolve()
SOG_SCENES_PATH = Path(os.environ.get("AIDA_SOG_SCENES_PATH", str(_REPO_DATA_ROOT / "sog-scenes.json"))).resolve()
ASSET_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
DEFAULT_CAMERA = {"position": [0, 1, -7], "target": [0, 0, 0], "fov": 60}


def _is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value == value
        and value not in (float("inf"), float("-inf"))
    )


def normalize_camera(input_data: Any) -> dict[str, Any] | None:
    if not isinstance(input_data, dict):
        return None
    position = input_data.get("position")
    target = input_data.get("target")
    if (
        not isinstance(position, list)
        or len(position) != 3
        or not all(_is_finite_number(v) for v in position)
        or not isinstance(target, list)
        or len(target) != 3
        or not all(_is_finite_number(v) for v in target)
    ):
        return None
    raw_fov = input_data.get("fov", 60)
    fov = raw_fov if _is_finite_number(raw_fov) else 60
    return {"position": position, "target": target, "fov": max(30, min(100, fov))}


def validate_asset_id(asset_id: str) -> str:
    if not asset_id or not ASSET_ID_RE.fullmatch(asset_id):
        raise ValueError("invalid asset id")
    return asset_id


def normalize_hotspots(input_data: Any) -> list[dict[str, Any]]:
    if not isinstance(input_data, list):
        return []

    import time

    now = int(time.time() * 1000)
    result: list[dict[str, Any]] = []
    for index, item in enumerate(input_data):
        if not isinstance(item, dict):
            continue
        position = item.get("position")
        if (
            not isinstance(position, list)
            or len(position) != 3
            or not all(_is_finite_number(v) for v in position)
        ):
            continue

        mode = "abnormal" if item.get("mode") == "abnormal" else "normal"
        raw_id = item.get("id")
        hotspot_id = raw_id.strip() if isinstance(raw_id, str) and raw_id.strip() else f"hotspot-{now}-{index}"
        raw_title = item.get("title")
        title = raw_title.strip() if isinstance(raw_title, str) and raw_title.strip() else "未命名标签"
        text = item.get("text") if isinstance(item.get("text"), str) else ""
        raw_label = item.get("statusLabel")
        status_label = (
            raw_label.strip()
            if isinstance(raw_label, str) and raw_label.strip()
            else ("异常" if mode == "abnormal" else "正常")
        )
        result.append(
            {
                "id": hotspot_id,
                "title": title,
                "text": text,
                "mode": mode,
                "statusLabel": status_label,
                "position": position,
            }
        )
    return result


def create_default_settings(
    hotspots: list[dict[str, Any]] | None = None,
    camera: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = normalize_hotspots(hotspots or [])
    initial_camera = normalize_camera(camera) or DEFAULT_CAMERA
    annotations = []
    for hotspot in normalized:
        x, y, z = hotspot["position"]
        annotations.append(
            {
                "position": hotspot["position"],
                "title": hotspot["title"],
                "text": hotspot["text"],
                "extras": {
                    "id": hotspot["id"],
                    "mode": hotspot["mode"],
                    "statusLabel": hotspot["statusLabel"],
                },
                "camera": {
                    "initial": {
                        "position": [x, y + 1, z - 3],
                        "target": hotspot["position"],
                        "fov": 60,
                    }
                },
            }
        )

    return {
        "version": 2,
        "tonemapping": "none",
        "highPrecisionRendering": False,
        "background": {"color": [0.02, 0.024, 0.028]},
        "postEffectSettings": {
            "sharpness": {"enabled": False, "amount": 0},
            "bloom": {"enabled": False, "intensity": 1, "blurLevel": 2},
            "grading": {
                "enabled": False,
                "brightness": 0,
                "contrast": 1,
                "saturation": 1,
                "tint": [1, 1, 1],
            },
            "vignette": {
                "enabled": False,
                "intensity": 0.5,
                "inner": 0.3,
                "outer": 0.75,
                "curvature": 1,
            },
            "fringing": {"enabled": False, "intensity": 0.5},
        },
        "animTracks": [],
        "cameras": [{"initial": initial_camera}],
        "annotations": annotations,
        "startMode": "default",
    }


class SogAssetStore:
    def __init__(self, root_directory: Path | None = None) -> None:
        self.root = root_directory or SOG_DATA_ROOT

    def asset_directory(self, asset_id: str) -> Path:
        validate_asset_id(asset_id)
        return self.root / asset_id

    def hotspots_path(self, asset_id: str) -> Path:
        return self.asset_directory(asset_id) / HOTSPOTS_FILE_NAME

    def scene_path(self, asset_id: str) -> Path:
        return self.asset_directory(asset_id) / SOG_FILE_NAME

    def meta_path(self, asset_id: str) -> Path:
        return self.asset_directory(asset_id) / META_FILE_NAME

    def read_hotspots(self, asset_id: str) -> list[dict[str, Any]]:
        path = self.hotspots_path(asset_id)
        if not path.exists():
            return []
        text = path.read_text(encoding="utf-8").lstrip("\ufeff")
        return normalize_hotspots(json.loads(text))

    def save_hotspots(self, asset_id: str, hotspots: Any) -> list[dict[str, Any]]:
        normalized = normalize_hotspots(hotspots)
        directory = self.asset_directory(asset_id)
        directory.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(normalized, ensure_ascii=False, indent=2) + "\n"
        self.hotspots_path(asset_id).write_text(payload, encoding="utf-8")
        return normalized

    def read_settings(self, asset_id: str, camera: dict[str, Any] | None = None) -> dict[str, Any]:
        return create_default_settings(self.read_hotspots(asset_id), camera=camera)

    def read_meta(self, asset_id: str) -> dict[str, Any]:
        path = self.meta_path(asset_id)
        if path.exists():
            text = path.read_text(encoding="utf-8").lstrip("\ufeff")
            return json.loads(text)
        return {
            "id": asset_id,
            "originalName": f"{asset_id}.sog",
            "fileName": SOG_FILE_NAME,
            "importedAt": None,
        }

    def asset_urls(self, asset_id: str) -> dict[str, str]:
        validate_asset_id(asset_id)
        return {
            "id": asset_id,
            "contentUrl": f"/data/sog-assets/{asset_id}/{SOG_FILE_NAME}",
            "settingsUrl": f"/api/sog/assets/{asset_id}/settings",
            "hotspotsUrl": f"/api/sog/assets/{asset_id}/hotspots",
        }

    def get_asset(self, asset_id: str) -> dict[str, Any]:
        meta = self.read_meta(asset_id)
        urls = self.asset_urls(asset_id)
        scene = self.scene_path(asset_id)
        return {
            **meta,
            **urls,
            "sceneExists": scene.is_file(),
        }


class SogSceneStore:
    """实景孪生场景列表存储。

    当前用于本地演示：已完成场景指向现有 SOG asset，新上传视频登记为 training。
    """

    def __init__(self, asset_root: Path | None = None, scenes_path: Path | None = None) -> None:
        self.asset_store = SogAssetStore(asset_root)
        self.scenes_path = scenes_path or SOG_SCENES_PATH

    def _default_scene(self) -> dict[str, Any]:
        meta = self.asset_store.read_meta("channel1")
        uploaded_at = meta.get("importedAt") or "2026-06-05T15:57:31+08:00"
        return {
            "id": "channel1",
            "name": "通道1历史建模",
            "status": "ready",
            "uploadedAt": uploaded_at,
            "assetId": "channel1",
            "sourceVideoName": "通道1.mp4",
        }

    def _read_raw_scenes(self) -> list[dict[str, Any]]:
        if not self.scenes_path.exists():
            return [self._default_scene()]
        text = self.scenes_path.read_text(encoding="utf-8").lstrip("\ufeff")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return [self._default_scene()]
        if not isinstance(data, list):
            return [self._default_scene()]
        return [item for item in data if isinstance(item, dict)]

    def _write_raw_scenes(self, scenes: list[dict[str, Any]]) -> None:
        self.scenes_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(scenes, ensure_ascii=False, indent=2) + "\n"
        self.scenes_path.write_text(payload, encoding="utf-8")

    def _with_runtime_fields(self, scene: dict[str, Any]) -> dict[str, Any]:
        status = "training" if scene.get("status") == "training" else "ready"
        asset_id = scene.get("assetId") if isinstance(scene.get("assetId"), str) else None
        scene_exists = bool(asset_id and self.asset_store.scene_path(asset_id).is_file())
        out = {
            "id": str(scene.get("id") or ""),
            "name": str(scene.get("name") or scene.get("sourceVideoName") or "未命名场景"),
            "status": status,
            "uploadedAt": str(scene.get("uploadedAt") or ""),
            "assetId": asset_id,
            "sourceVideoName": str(scene.get("sourceVideoName") or ""),
            "sceneExists": scene_exists,
        }
        camera = normalize_camera(scene.get("camera"))
        if camera:
            out["camera"] = camera
        if asset_id:
            asset = self.asset_store.get_asset(asset_id)
            out["contentUrl"] = asset["contentUrl"]
            out["settingsUrl"] = asset["settingsUrl"]
            out["hotspotsUrl"] = asset["hotspotsUrl"]
        return out

    def list_scenes(self) -> list[dict[str, Any]]:
        scenes = self._read_raw_scenes()
        return [self._with_runtime_fields(scene) for scene in scenes]

    def get_scene(self, scene_id: str) -> dict[str, Any]:
        validate_asset_id(scene_id)
        for scene in self.list_scenes():
            if scene["id"] == scene_id:
                return scene
        raise FileNotFoundError(scene_id)

    def get_camera_for_asset(self, asset_id: str) -> dict[str, Any] | None:
        validate_asset_id(asset_id)
        for scene in self.list_scenes():
            if scene.get("assetId") == asset_id or scene.get("id") == asset_id:
                camera = scene.get("camera")
                return camera if isinstance(camera, dict) else None
        return None

    def update_scene_name(self, scene_id: str, name: str) -> dict[str, Any]:
        validate_asset_id(scene_id)
        next_name = (name or "").strip()
        if not next_name:
            raise ValueError("scene name required")
        scenes = self._read_raw_scenes()
        if not scenes:
            scenes = [self._default_scene()]
        for scene in scenes:
            if scene.get("id") == scene_id:
                scene["name"] = next_name
                self._write_raw_scenes(scenes)
                return self._with_runtime_fields(scene)
        raise FileNotFoundError(scene_id)

    def update_scene_camera(self, scene_id: str, camera: dict[str, Any]) -> dict[str, Any]:
        validate_asset_id(scene_id)
        normalized = normalize_camera(camera)
        if not normalized:
            raise ValueError("invalid camera")
        scenes = self._read_raw_scenes()
        if not scenes:
            scenes = [self._default_scene()]
        for scene in scenes:
            if scene.get("id") == scene_id:
                scene["camera"] = normalized
                self._write_raw_scenes(scenes)
                return self._with_runtime_fields(scene)
        raise FileNotFoundError(scene_id)

    def delete_scene(self, scene_id: str) -> dict[str, Any]:
        validate_asset_id(scene_id)
        scenes = self._read_raw_scenes()
        if not scenes:
            scenes = [self._default_scene()]
        remaining = [scene for scene in scenes if scene.get("id") != scene_id]
        if len(remaining) == len(scenes):
            raise FileNotFoundError(scene_id)
        self._write_raw_scenes(remaining)
        return {"id": scene_id, "deleted": True}

    def create_training_scene(self, source_video_name: str) -> dict[str, Any]:
        name = (source_video_name or "").strip() or "现场视频.mp4"
        scenes = self._read_raw_scenes()
        scene = {
            "id": f"scene-{uuid.uuid4().hex[:12]}",
            "name": name,
            "status": "training",
            "uploadedAt": datetime.now().astimezone().isoformat(),
            "assetId": None,
            "sourceVideoName": name,
        }
        scenes.append(scene)
        self._write_raw_scenes(scenes)
        return self._with_runtime_fields(scene)
