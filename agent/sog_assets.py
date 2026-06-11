"""工勘孪生 · SOG 资产存储与热点/settings 生成（移植自 sog-hotspot-viewer/server/asset-store.mjs）。"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SOG_FILE_NAME = "scene.sog"
HOTSPOTS_FILE_NAME = "hotspots.json"
META_FILE_NAME = "meta.json"
SOG_DATA_ROOT = Path(__file__).resolve().parents[1] / "data" / "sog-assets"
ASSET_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


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
        title = raw_title.strip() if isinstance(raw_title, str) and raw_title.strip() else "未命名热点"
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


def create_default_settings(hotspots: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    normalized = normalize_hotspots(hotspots or [])
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
        "cameras": [{"initial": {"position": [0, 1, -7], "target": [0, 0, 0], "fov": 60}}],
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

    def read_settings(self, asset_id: str) -> dict[str, Any]:
        return create_default_settings(self.read_hotspots(asset_id))

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
