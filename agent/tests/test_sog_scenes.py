"""工勘孪生 · 场景列表与训练中状态单元测试。"""
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


if __name__ == "__main__":
    unittest.main()
