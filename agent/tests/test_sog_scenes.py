"""实景孪生 · 场景列表与训练中状态单元测试。"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from agent.sog_assets import SogSceneStore


class SogScenesTest(unittest.TestCase):
    def test_default_scenes_include_channel1_ready_record(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "channel1").mkdir(parents=True)
            (root / "channel1" / "scene.sog").write_bytes(b"sog")

            store = SogSceneStore(asset_root=root, scenes_path=root / "scenes.json")
            scenes = store.list_scenes()

            self.assertEqual(len(scenes), 1)
            self.assertEqual(scenes[0]["id"], "channel1")
            self.assertEqual(scenes[0]["name"], "通道1历史建模")
            self.assertEqual(scenes[0]["status"], "ready")
            self.assertEqual(scenes[0]["assetId"], "channel1")
            self.assertTrue(scenes[0]["sceneExists"])

    def test_create_training_scene_persists_uploaded_video_metadata(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SogSceneStore(asset_root=root, scenes_path=root / "scenes.json")

            scene = store.create_training_scene("现场视频.mp4")
            scenes = store.list_scenes()

            self.assertEqual(scene["status"], "training")
            self.assertEqual(scene["sourceVideoName"], "现场视频.mp4")
            self.assertIsNone(scene["assetId"])
            self.assertFalse(scene["sceneExists"])
            self.assertIn("uploadedAt", scene)
            self.assertEqual(scenes[-1]["id"], scene["id"])

            raw = json.loads((root / "scenes.json").read_text(encoding="utf-8"))
            self.assertEqual(raw[-1]["sourceVideoName"], "现场视频.mp4")

    def test_ready_scene_reports_missing_scene_file_without_failing(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scenes_path = root / "scenes.json"
            scenes_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "channel1",
                            "name": "通道1历史建模",
                            "status": "ready",
                            "uploadedAt": "2026-06-05T15:57:31+08:00",
                            "assetId": "channel1",
                            "sourceVideoName": "通道1.mp4",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            store = SogSceneStore(asset_root=root, scenes_path=scenes_path)
            scene = store.get_scene("channel1")

            self.assertEqual(scene["status"], "ready")
            self.assertFalse(scene["sceneExists"])

    def test_ready_scene_includes_valid_camera_config(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "channel1").mkdir(parents=True)
            (root / "channel1" / "scene.sog").write_bytes(b"sog")
            scenes_path = root / "scenes.json"
            scenes_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "channel1",
                            "name": "通道1历史建模",
                            "status": "ready",
                            "uploadedAt": "2026-06-05T15:57:31+08:00",
                            "assetId": "channel1",
                            "sourceVideoName": "通道1.mp4",
                            "camera": {
                                "position": [2, 1.6, -8],
                                "target": [0, 1, 0],
                                "fov": 55,
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            store = SogSceneStore(asset_root=root, scenes_path=scenes_path)
            scene = store.get_scene("channel1")

            self.assertEqual(
                scene["camera"],
                {"position": [2, 1.6, -8], "target": [0, 1, 0], "fov": 55},
            )
            self.assertEqual(store.get_camera_for_asset("channel1"), scene["camera"])

    def test_invalid_scene_camera_is_omitted(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scenes_path = root / "scenes.json"
            scenes_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "channel1",
                            "name": "通道1历史建模",
                            "status": "ready",
                            "uploadedAt": "2026-06-05T15:57:31+08:00",
                            "assetId": "channel1",
                            "sourceVideoName": "通道1.mp4",
                            "camera": {"position": [1, 2], "target": [0, 0, 0]},
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            store = SogSceneStore(asset_root=root, scenes_path=scenes_path)
            scene = store.get_scene("channel1")

            self.assertNotIn("camera", scene)
            self.assertIsNone(store.get_camera_for_asset("channel1"))

    def test_update_scene_name_persists_trimmed_display_name(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SogSceneStore(asset_root=root, scenes_path=root / "scenes.json")

            updated = store.update_scene_name("channel1", "  主通道实景  ")
            scenes = store.list_scenes()

            self.assertEqual(updated["name"], "主通道实景")
            self.assertEqual(scenes[0]["name"], "主通道实景")

            raw = json.loads((root / "scenes.json").read_text(encoding="utf-8"))
            self.assertEqual(raw[0]["name"], "主通道实景")

    def test_update_scene_name_rejects_blank_name(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SogSceneStore(asset_root=root, scenes_path=root / "scenes.json")

            with self.assertRaises(ValueError):
                store.update_scene_name("channel1", "   ")

    def test_delete_scene_removes_scene_from_list(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scenes_path = root / "scenes.json"
            scenes_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "channel1",
                            "name": "通道1历史建模",
                            "status": "ready",
                            "uploadedAt": "2026-06-05T15:57:31+08:00",
                            "assetId": "channel1",
                            "sourceVideoName": "通道1.mp4",
                        },
                        {
                            "id": "scene-training",
                            "name": "训练中",
                            "status": "training",
                            "uploadedAt": "2026-06-14T15:57:31+08:00",
                            "assetId": None,
                            "sourceVideoName": "训练中.mp4",
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            store = SogSceneStore(asset_root=root, scenes_path=scenes_path)

            deleted = store.delete_scene("scene-training")
            scenes = store.list_scenes()

            self.assertEqual(deleted, {"id": "scene-training", "deleted": True})
            self.assertEqual([scene["id"] for scene in scenes], ["channel1"])

            raw = json.loads(scenes_path.read_text(encoding="utf-8"))
            self.assertEqual([scene["id"] for scene in raw], ["channel1"])

    def test_delete_scene_raises_when_scene_missing(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = SogSceneStore(asset_root=root, scenes_path=root / "scenes.json")

            with self.assertRaises(FileNotFoundError):
                store.delete_scene("missing-scene")

    def test_delete_last_scene_leaves_empty_scene_list(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scenes_path = root / "scenes.json"
            scenes_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "channel1",
                            "name": "通道1历史建模",
                            "status": "ready",
                            "uploadedAt": "2026-06-05T15:57:31+08:00",
                            "assetId": "channel1",
                            "sourceVideoName": "通道1.mp4",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            store = SogSceneStore(asset_root=root, scenes_path=scenes_path)

            store.delete_scene("channel1")

            self.assertEqual(store.list_scenes(), [])


if __name__ == "__main__":
    unittest.main()
