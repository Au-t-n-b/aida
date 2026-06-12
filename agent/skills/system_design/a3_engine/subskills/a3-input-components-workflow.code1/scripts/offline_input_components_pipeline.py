#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Offline deterministic workflow for a3_input_components.py."""

from __future__ import annotations

import argparse
import csv
import json
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

FILE_CONFIG = OrderedDict(
    [
        (
            "设备信息概览",
            {
                "tag": "Device_Info",
                "filename": "建模仿真输出文档001-设备信息表.xlsx",
            },
        ),
        (
            "设备位置信息",
            {
                "tag": "Location_Information",
                "filename": "建模仿真输出文档004-设备位置表.xlsx",
            },
        ),
        (
            "端口互联关系",
            {
                "tag": "Interconnection_Relationship",
                "filename": "建模仿真输出文档007-端口连线表.xlsx",
            },
        ),
    ]
)


def load_manifest(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return normalize_json_manifest(data)
    if suffix == ".csv":
        return load_csv_manifest(path)
    raise ValueError("manifest 仅支持 JSON 或 CSV")


def normalize_json_manifest(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        if isinstance(data.get("files"), list):
            return normalize_json_manifest(data["files"])
        return dict(data)

    if isinstance(data, list):
        manifest: dict[str, Any] = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            tag = item.get("tag") or item.get("file_tag") or item.get("fileTag")
            value = item.get("path") or item.get("file_path") or item.get("filename") or item.get("name")
            if tag:
                manifest[str(tag)] = value
        return manifest

    raise ValueError("JSON manifest 必须是对象、文件列表，或包含 files 列表的对象")


def load_csv_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        rows = csv.DictReader(csv_file)
        manifest: dict[str, Any] = {}
        for row in rows:
            tag = row.get("tag") or row.get("file_tag") or row.get("fileTag")
            value = row.get("path") or row.get("file_path") or row.get("filename") or row.get("name")
            if tag:
                manifest[str(tag)] = value
        return manifest


def tag_exists(manifest: dict[str, Any], tag: str) -> bool:
    value = manifest.get(tag)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def query_input_components(manifest: dict[str, Any]) -> str:
    """Align with a3_input_components.py: build Markdown table of found standard filenames."""
    content: list[str] = []
    for business_name, config in FILE_CONFIG.items():
        if not tag_exists(manifest, config["tag"]):
            # 线上仅写日志，不进入展示表
            continue
        content.append(config["filename"])

    content_df = pd.DataFrame(content, columns=["文件名称"])
    return content_df.to_markdown(index=False)


def discover_manifest_from_dir(directory: Path) -> dict[str, Any]:
    """Map present standard filenames to tags (equivalent to tag query returning a path)."""
    manifest: dict[str, Any] = {}
    for config in FILE_CONFIG.values():
        file_path = directory / config["filename"]
        if file_path.is_file():
            manifest[config["tag"]] = str(file_path.resolve())
    return manifest


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    manifest: dict[str, Any] = {}
    if args.manifest:
        manifest.update(load_manifest(Path(args.manifest)))
    scan_dir = Path(args.scan_dir) if args.scan_dir else None
    if scan_dir:
        manifest.update(discover_manifest_from_dir(scan_dir))
    for tag in args.tag:
        manifest[tag] = tag
    if not manifest and not args.manifest and not args.tag:
        manifest.update(discover_manifest_from_dir(Path.cwd()))
    return manifest


def write_output(markdown: str, out_dir: Path) -> Path:
    run_dir = out_dir  # 产物直接落在 Output（不再加 run_<时间戳> 子目录）
    run_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = run_dir / "查询输入件.md"
    markdown_path.write_text(markdown + "\n", encoding="utf-8")
    return run_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline A3 查询输入件 deterministic workflow")
    parser.add_argument("--manifest", help="JSON/CSV manifest mapping tag to a non-empty file value")
    parser.add_argument(
        "--scan-dir",
        help="Scan directory for standard filenames (001/004/007); default cwd when no manifest/tag",
    )
    parser.add_argument("--tag", action="append", default=[], help="Mark a tag as found; can be repeated")
    parser.add_argument("--out-dir", default="output", help="Output directory")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = build_manifest(args)
    markdown = query_input_components(manifest)
    run_dir = write_output(markdown, Path(args.out_dir))

    print(markdown)
    print(f"\n输出目录: {run_dir}")


if __name__ == "__main__":
    main()
