"""
将机房机柜信息表同步到项目演示数据目录（孪生输出 · 规范路径）。

用法（仓库根目录）：
  python agent/scripts/sync_room_rack_catalog.py
  python agent/scripts/sync_room_rack_catalog.py --src "D:\\path\\机房机柜信息表.xlsx"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SRC = Path.home() / "Desktop" / "机房机柜信息表.xlsx"

sys.path.insert(0, str(REPO_ROOT))
from agent.skills.zhgk.demo_assets import (  # noqa: E402
    DEFAULT_DEMO_PROJECT_ID,
    ROOM_RACK_FILENAME,
    room_rack_manifest_path,
    room_rack_project_path,
)
from agent.skills.zhgk.services.room_catalog import LOGICAL_PATH  # noqa: E402


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_manifest(dest: Path) -> None:
    manifest = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "files": [{
            "name": ROOM_RACK_FILENAME,
            "logical_path": LOGICAL_PATH,
            "module_code": "twin-foundation",
            "file_stage": "output",
            "checksum_sha256": _sha256(dest),
        }],
    }
    manifest_path = room_rack_manifest_path(project_id=DEFAULT_DEMO_PROJECT_ID)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"manifest → {manifest_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="同步机房机柜信息表到项目演示目录")
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC, help="源 xlsx 路径")
    parser.add_argument("--project-id", default=DEFAULT_DEMO_PROJECT_ID)
    args = parser.parse_args()

    src: Path = args.src.expanduser().resolve()
    if not src.is_file():
        raise SystemExit(f"源文件不存在: {src}")

    dest = room_rack_project_path(project_id=args.project_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(src.read_bytes())
    print(f"已写入 {dest}")
    _write_manifest(dest)


if __name__ == "__main__":
    main()
