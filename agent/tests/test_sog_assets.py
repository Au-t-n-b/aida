"""工勘孪生 · SOG 资产存储单元测试。"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from agent.sog_assets import SogAssetStore, create_default_settings, normalize_hotspots


class SogAssetsTest(unittest.TestCase):
    def test_normalize_hotspots_filters_invalid_and_fills_defaults(self) -> None:
        hotspots = normalize_hotspots(
            [
                {"id": "a", "title": "A", "text": "B", "position": [1, 2, 3]},
                {"id": "bad", "title": "Bad", "text": "Bad", "position": [1, 2]},
                {"position": [4, 5, 6]},
            ]
        )
        self.assertEqual(len(hotspots), 2)
        self.assertEqual(hotspots[1]["title"], "未命名热点")
        self.assertEqual(hotspots[1]["text"], "")
        self.assertEqual(hotspots[1]["mode"], "normal")
        self.assertEqual(hotspots[1]["statusLabel"], "正常")

    def test_create_default_settings_maps_annotations(self) -> None:
        settings = create_default_settings(
            [
                {
                    "id": "hotspot-1",
                    "title": "标题",
                    "text": "说明",
                    "mode": "abnormal",
                    "statusLabel": "故障",
                    "position": [4, 5, 6],
                }
            ]
        )
        self.assertEqual(settings["version"], 2)
        self.assertEqual(len(settings["annotations"]), 1)
        self.assertEqual(settings["annotations"][0]["position"], [4, 5, 6])
        self.assertEqual(settings["annotations"][0]["camera"]["initial"]["target"], [4, 5, 6])
        self.assertEqual(
            settings["annotations"][0]["extras"],
            {"id": "hotspot-1", "mode": "abnormal", "statusLabel": "故障"},
        )

    def test_read_hotspots_strips_bom(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            asset_dir = Path(tmp) / "channel1"
            asset_dir.mkdir(parents=True)
            (asset_dir / "hotspots.json").write_bytes(b"\xef\xbb\xbf[]\n")
            store = SogAssetStore(Path(tmp))
            self.assertEqual(store.read_hotspots("channel1"), [])

    def test_save_and_read_hotspots_roundtrip(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            store = SogAssetStore(Path(tmp))
            saved = store.save_hotspots(
                "channel1",
                [
                    {
                        "id": "hotspot-1",
                        "title": "一盆绿植",
                        "text": "只是一盆绿植",
                        "mode": "normal",
                        "statusLabel": "正常",
                        "position": [1, 2, 3],
                    }
                ],
            )
            self.assertEqual(saved[0]["title"], "一盆绿植")
            self.assertEqual(store.read_hotspots("channel1"), saved)
            raw = (Path(tmp) / "channel1" / "hotspots.json").read_text(encoding="utf-8")
            self.assertEqual(json.loads(raw)[0]["id"], "hotspot-1")


if __name__ == "__main__":
    unittest.main()
