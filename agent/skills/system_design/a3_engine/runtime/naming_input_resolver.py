"""Resolve ZTP / device-naming inputs from ProjectData."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import pandas as pd


def _newest(paths: list[Path]) -> Optional[Path]:
    files = [p for p in paths if p.is_file() and not p.name.startswith("~$")]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def find_ztp_lld(skill_root: Path) -> Optional[Path]:
    bases = [
        skill_root / "ProjectData" / "Output",
        skill_root / "ProjectData" / "Work",
        skill_root / "ProjectData" / "Input",
    ]
    cands: list[Path] = []
    for base in bases:
        if not base.is_dir():
            continue
        for path in base.rglob("*.xlsx"):
            name = path.name.upper()
            if "ZTP" in name and "LLD" in name:
                cands.append(path)
    return _newest(cands)


def find_device_list(skill_root: Path) -> Optional[Path]:
    bases = [
        skill_root / "ProjectData" / "Output",
        skill_root / "ProjectData" / "Work",
        skill_root / "ProjectData" / "Input",
    ]
    cands: list[Path] = []
    for base in bases:
        if not base.is_dir():
            continue
        for path in base.rglob("*.xlsx"):
            if "设备清单" in path.name:
                cands.append(path)
    return _newest(cands)


def find_name_mapping(skill_root: Path) -> Optional[Path]:
    bases = [
        skill_root / "ProjectData" / "Input",
        skill_root / "ProjectData" / "Output",
        skill_root / "ProjectData" / "Work",
    ]
    cands: list[Path] = []
    for base in bases:
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.name.startswith("~$"):
                continue
            lower = path.name.lower()
            if path.suffix.lower() not in {".csv", ".xlsx", ".xls"}:
                continue
            if (
                "devicename-mapping" in lower
                or "映射" in path.name
                or ("mapping" in lower and "run_meta" not in lower)
            ):
                cands.append(path)
    return _newest(cands)


def mapping_from_device_list(device_list: Path, out_csv: Path) -> Optional[Path]:
    try:
        df = pd.read_excel(device_list, sheet_name="设备信息", dtype=str)
    except Exception:
        try:
            df = pd.read_excel(device_list, dtype=str)
        except Exception:
            return None
    if "设备名称" not in df.columns or "客户定义设备名称" not in df.columns:
        return None
    sub = df.copy()
    sub["设备名称"] = sub["设备名称"].astype(str).str.strip()
    sub["客户定义设备名称"] = sub["客户定义设备名称"].fillna("").astype(str).str.strip()
    sub = sub[sub["客户定义设备名称"] != ""]
    if sub.empty:
        return None
    mapping = sub.rename(columns={"设备名称": "source", "客户定义设备名称": "target"})[
        ["source", "target"]
    ]
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    mapping.to_csv(out_csv, index=False, encoding="utf-8-sig")
    return out_csv


def mapping_from_ztp_identity(ztp_lld: Path, out_csv: Path) -> Optional[Path]:
    """Fallback: map each switch name to itself (allows pipeline smoke test)."""
    try:
        df = pd.read_excel(ztp_lld, sheet_name="网络IP规划", dtype=str)
    except Exception:
        return None
    if "交换机名称" not in df.columns:
        return None
    names = df["交换机名称"].dropna().astype(str).str.strip()
    names = names[names != ""].drop_duplicates()
    if names.empty:
        return None
    mapping = pd.DataFrame({"source": names, "target": names})
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    mapping.to_csv(out_csv, index=False, encoding="utf-8-sig")
    return out_csv


def find_lld_design(skill_root: Path) -> Optional[Path]:
    bases = [
        skill_root / "ProjectData" / "Output",
        skill_root / "ProjectData" / "Work",
        skill_root / "ProjectData" / "Input",
    ]
    cands: list[Path] = []
    for base in bases:
        if not base.is_dir():
            continue
        for path in base.rglob("*.xlsx"):
            name = path.name
            upper = name.upper()
            lower = name.lower()
            if "设备清单" in name or "_REPLACED" in upper:
                continue
            if "ZTP" in upper:
                continue
            if "_ztp" in lower:
                continue
            if "LLD" in upper or "lld" in lower:
                cands.append(path)
    return _newest(cands)


def find_location(skill_root: Path) -> Optional[Path]:
    bases = [
        skill_root / "ProjectData" / "Input",
        skill_root / "ProjectData" / "Output",
        skill_root / "ProjectData" / "Work",
    ]
    cands: list[Path] = []
    for base in bases:
        if not base.is_dir():
            continue
        for path in base.rglob("*.xlsx"):
            name = path.name
            if "设备位置" in name or "文档004" in name or "输出文档004" in name:
                cands.append(path)
    return _newest(cands)


def _copy_into(work_dir: Path, src: Path, dest_name: Optional[str] = None) -> Path:
    import shutil

    work_dir.mkdir(parents=True, exist_ok=True)
    dst = work_dir / (dest_name or src.name)
    if src.resolve() != dst.resolve():
        shutil.copy2(src, dst)
    return dst


def ensure_device_list(skill_root: Path, work_dir: Path) -> Optional[Path]:
    existing = find_device_list(skill_root)
    if existing is not None:
        return _copy_into(work_dir, existing, "设备清单表.xlsx")

    location = find_location(skill_root)
    if location is None:
        return None

    from skill_root import resolve_capability_root

    capability_root = resolve_capability_root(skill_root)
    scripts = capability_root / "a3-device-naming-workflow.code1" / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))

    from device_list_generator import generate_device_list

    loc_copy = _copy_into(work_dir, location)
    try:
        return generate_device_list(location_path=loc_copy, out_dir=work_dir, restrict_to_cwd=True)
    except Exception:
        return None


def resolve_lld_replace_inputs(skill_root: Path, work_dir: Path) -> dict[str, Path]:
    """Return lld_design + device_list paths under work_dir when possible."""
    resolved: dict[str, Path] = {}
    lld = find_lld_design(skill_root)
    if lld is None:
        return resolved
    resolved["lld_design"] = _copy_into(work_dir, lld)

    device_list = ensure_device_list(skill_root, work_dir)
    if device_list is not None:
        resolved["device_list"] = device_list
    return resolved


def resolve_generate_list_inputs(skill_root: Path, work_dir: Path) -> dict[str, Path]:
    location = find_location(skill_root)
    if location is None:
        return {}
    return {"location_004": _copy_into(work_dir, location)}


def resolve_ztp_replace_inputs(skill_root: Path, work_dir: Path) -> dict[str, Path]:
    """Return ztp_lld + name_mapping paths (under work_dir where possible)."""
    resolved: dict[str, Path] = {}
    ztp = find_ztp_lld(skill_root)
    if ztp is None:
        return resolved

    work_dir.mkdir(parents=True, exist_ok=True)
    ztp_dst = work_dir / "ZTP_LLD.xlsx"
    if ztp.resolve() != ztp_dst.resolve():
        import shutil

        shutil.copy2(ztp, ztp_dst)
    resolved["ztp_lld"] = ztp_dst

    mapping = find_name_mapping(skill_root)
    if mapping is not None:
        map_dst = work_dir / mapping.name
        if mapping.resolve() != map_dst.resolve():
            import shutil

            shutil.copy2(mapping, map_dst)
        resolved["name_mapping"] = map_dst
        return resolved

    device_list = find_device_list(skill_root)
    if device_list is not None:
        built = mapping_from_device_list(device_list, work_dir / "devicename-mapping.csv")
        if built is not None:
            resolved["name_mapping"] = built
            return resolved

    built = mapping_from_ztp_identity(ztp_dst, work_dir / "devicename-mapping.csv")
    if built is not None:
        resolved["name_mapping"] = built
    return resolved
