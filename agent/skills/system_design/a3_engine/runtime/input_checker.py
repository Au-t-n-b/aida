from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class InputFile:
    tag: str
    label: str
    path: Path
    status: str = "ready"


BASE_REQUIRED_INPUTS: tuple[str, ...] = ("007", "resource", "001", "004")


INPUT_DEFS: dict[str, tuple[str, tuple[str, ...]]] = {
    "001": ("001 设备信息表", ("001", "设备信息")),
    "004": ("004 设备位置表", ("文档004", "输出文档004", "设备位置")),
    "007": ("007 端口连线表", ("007", "端口连线", "端口互联")),
    "resource": ("项目信息收集表", ("项目信息收集", "信息收集表", "资源")),
    "access_plan": ("A3 网络设备接入规划", ("网络设备接入规划",)),
    "ztp_lld": ("ZTP_LLD", ("ztp_lld",)),
    "name_mapping": ("设备名称映射表", ("devicename-mapping", "映射", "mapping")),
    "device_list": ("设备清单表", ("设备清单",)),
    "lld_design": ("LLD 设计", ("lld设计", "-lld设计-", "lld")),
}


def _as_str(value: Any) -> str:
    return str(value or "").strip()


def _candidate_paths_from_result(result: dict[str, Any], skill_root: Path) -> list[Path]:
    paths: list[Path] = []
    files: list[Any] = []
    for key in ("files", "uploads"):
        value = result.get(key)
        if isinstance(value, list):
            files.extend(value)
    upload = result.get("upload")
    if isinstance(upload, dict):
        files.append(upload)
    file_obj = result.get("file")
    if isinstance(file_obj, dict):
        files.append(file_obj)
    if not files:
        return paths

    for item in files:
        if not isinstance(item, dict):
            continue
        for key in ("path", "logicalPath", "uri", "absolutePath", "absPath"):
            raw = _as_str(item.get(key))
            if not raw:
                continue
            normalized = raw.replace("\\", "/")
            if normalized.startswith("workspace/skills/a3-intelligent-network-opening/"):
                rel = normalized.split("workspace/skills/a3-intelligent-network-opening/", 1)[1]
                paths.append(skill_root / rel)
            elif normalized.startswith("skills/a3-intelligent-network-opening/"):
                rel = normalized.split("skills/a3-intelligent-network-opening/", 1)[1]
                paths.append(skill_root / rel)
            elif Path(raw).is_absolute():
                paths.append(Path(raw))
            else:
                paths.append(skill_root.parent.parent / normalized)

        name = _as_str(item.get("name"))
        saved_dir = _as_str(item.get("savedDir") or item.get("saveRelativeDir"))
        if name:
            if saved_dir:
                normalized = saved_dir.replace("\\", "/")
                if normalized.startswith("skills/a3-intelligent-network-opening/"):
                    rel = normalized.split("skills/a3-intelligent-network-opening/", 1)[1]
                    paths.append(skill_root / rel / name)
                elif normalized.startswith("workspace/skills/a3-intelligent-network-opening/"):
                    rel = normalized.split("workspace/skills/a3-intelligent-network-opening/", 1)[1]
                    paths.append(skill_root / rel / name)
                elif normalized.startswith("skills/"):
                    paths.append(skill_root.parent.parent / normalized / name)
                else:
                    paths.append(skill_root / "ProjectData" / "Input" / name)
            else:
                paths.append(skill_root / "ProjectData" / "Input" / name)
    return paths


def _scan_input_dir(skill_root: Path) -> list[Path]:
    paths: list[Path] = []
    for sub in ("Input", "Output", "Work"):
        base = skill_root / "ProjectData" / sub
        if base.is_dir():
            paths.extend(p for p in base.rglob("*") if p.is_file())
    return paths


def _classify(path: Path) -> str | None:
    name = path.name.lower()
    if "ztp" in name and "lld" in name:
        return "ztp_lld"
    if "设备清单" in path.name:
        return "device_list"
    upper = path.name.upper()
    lower = path.name.lower()
    if ("LLD" in upper or "lld" in lower) and "ZTP" not in upper and "_ztp" not in lower:
        if "设备清单" not in path.name and "_replaced" not in lower:
            return "lld_design"
    if (
        "devicename-mapping" in name
        or "映射" in path.name
        or ("mapping" in name and "run_meta" not in name)
    ):
        return "name_mapping"
    for tag, (_label, keywords) in INPUT_DEFS.items():
        if tag in {"ztp_lld", "name_mapping", "device_list", "lld_design"}:
            continue
        if any(keyword.lower() in name for keyword in keywords):
            return tag
    return None


def collect_inputs(skill_root: Path, result: dict[str, Any] | None = None) -> dict[str, InputFile]:
    candidates = _scan_input_dir(skill_root)
    if isinstance(result, dict):
        candidates.extend(_candidate_paths_from_result(result, skill_root))

    found: dict[str, InputFile] = {}
    for path in candidates:
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        if not resolved.is_file():
            continue
        if resolved.name.startswith("~$"):
            continue
        tag = _classify(resolved)
        if not tag or tag in found:
            continue
        label = INPUT_DEFS[tag][0]
        found[tag] = InputFile(tag=tag, label=label, path=resolved)
    return found


def status_items(found: dict[str, InputFile]) -> list[dict[str, str]]:
    return [
        {"key": label, "value": "✓" if tag in found else "○", "color": "success" if tag in found else "subtle"}
        for tag, (label, _keywords) in INPUT_DEFS.items()
    ]


def missing_required(found: dict[str, InputFile], required: tuple[str, ...]) -> list[str]:
    return [tag for tag in required if tag not in found]


def describe_missing(missing: list[str]) -> str:
    labels = [INPUT_DEFS[tag][0] for tag in missing if tag in INPUT_DEFS]
    return "、".join(labels)
