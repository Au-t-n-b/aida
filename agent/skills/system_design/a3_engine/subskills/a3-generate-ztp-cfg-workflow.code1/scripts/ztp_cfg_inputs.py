"""ZTP 配置文件 skill 输入件扫描。"""

from __future__ import annotations

from pathlib import Path

LABELS = {
    "ztp_lld": "ZTP_LLD.xlsx（或名称含 ZTP+LLD）",
    "resource": "项目信息收集表.xlsx",
}

ZTP_LLD_OUTPUT_NAMES = ("ZTP_LLD.xlsx",)
RESOURCE_NAME_KEYWORD = "项目信息收集"


def find_ztp_lld(scan_dir: Path) -> Path | None:
    for path in sorted(scan_dir.glob("*.xlsx")):
        if path.name.startswith("~$"):
            continue
        upper = path.name.upper()
        if "ZTP_LLD" in upper or ("ZTP" in upper and "LLD" in upper):
            return path
    return None


def find_resource(scan_dir: Path) -> Path | None:
    for path in sorted(scan_dir.glob("*.xlsx")):
        if path.name.startswith("~$"):
            continue
        if RESOURCE_NAME_KEYWORD in path.name:
            return path
    return None
