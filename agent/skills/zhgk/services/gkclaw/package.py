"""
gkclaw package · ZIP 包构建与解析（契约 §8/§9）

构建：manifest.json + payload + assets，全文件 sha256 进 manifest.checksum。
解析：五道校验 —— manifest 可解析 / schema_version·必填 / package_type↔payload 匹配 /
checksum 防篡改 / 路径安全（拒绝 ..·绝对路径）。manifest 未列出的文件：
evidence/ 下仅 warning（现场证据宽容），其余视为违规（防夹带）。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import ids, schema

# 包类型 → (zip 文件名前缀, payload 文件名)（契约 §8）
PACKAGE_LAYOUT: dict[str, tuple[str, str]] = {
    "task.dispatch":   ("task",   "task.json"),
    "task.import_ack": ("ack",    "ack.json"),
    "task.result":     ("result", "result.json"),
    "task.error":      ("error",  "error.json"),
}


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path | str) -> str:
    return sha256_bytes(Path(path).read_bytes())


def build_package(
    *,
    package_type: str,
    task_id: str,
    project: dict[str, Any],
    payload: dict[str, Any],
    assets: dict[str, bytes] | None = None,
    out_dir: Path | str,
    source: str = "back-agent",
    target: str = "front-agent",
    package_id: str | None = None,
) -> Path:
    """构建 gkclaw.mail.v1 ZIP，返回 zip 路径。assets 键 = ZIP 内相对路径。"""
    import zipfile

    prefix, payload_name = PACKAGE_LAYOUT[package_type]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    zip_path = out / f"{prefix}-{task_id}.zip"

    payload_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    checksum: dict[str, str] = {payload_name: sha256_bytes(payload_bytes)}
    for arcname, data in (assets or {}).items():
        if not ids.is_safe_zip_path(arcname):
            raise ValueError(f"资产路径不安全: {arcname!r}")
        checksum[arcname] = sha256_bytes(data)

    manifest = {
        "schema_version": schema.SCHEMA_VERSION,
        "package_id": package_id or ids.new_package_id(),
        "package_type": package_type,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "source": source,
        "target": target,
        "task_id": task_id,
        "project_id": str((project or {}).get("project_id", "")),
        "project_code": str((project or {}).get("project_code", "")),
        "checksum": checksum,
    }
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr(payload_name, payload_bytes)
        for arcname, data in (assets or {}).items():
            zf.writestr(arcname, data)
    return zip_path


def parse_package(zip_path: Path | str) -> dict[str, Any]:
    """解析并校验入站 ZIP。返回:
    {ok, errors[], warnings[], manifest, payload, payload_name, files[]}"""
    import zipfile

    result: dict[str, Any] = {"ok": False, "errors": [], "warnings": [],
                              "manifest": None, "payload": None,
                              "payload_name": "", "files": []}
    errors: list[str] = result["errors"]
    try:
        zf = zipfile.ZipFile(zip_path)
    except Exception as e:  # noqa: BLE001
        errors.append(f"ZIP 无法打开: {e}")
        return result

    with zf:
        names = zf.namelist()
        result["files"] = names
        # 1. 路径安全（目录项以 / 结尾的跳过内容校验但仍查安全）
        for n in names:
            check = n[:-1] if n.endswith("/") else n
            if check and not ids.is_safe_zip_path(check):
                errors.append(f"ZIP 含不安全路径: {n!r}")
        if errors:
            return result

        # 2. manifest 存在且可解析
        if "manifest.json" not in names:
            errors.append("缺 manifest.json")
            return result
        try:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            errors.append(f"manifest.json 解析失败: {e}")
            return result
        result["manifest"] = manifest
        errors.extend(schema.validate_manifest(manifest))
        if errors:
            return result

        # 3. package_type ↔ payload 文件匹配
        package_type = manifest["package_type"]
        payload_name = PACKAGE_LAYOUT[package_type][1]
        result["payload_name"] = payload_name
        if payload_name not in names:
            errors.append(f"包类型 {package_type} 缺 payload 文件 {payload_name}")
            return result

        # 4. checksum 防篡改（manifest 列出的每个文件都必须存在且匹配）
        checksum: dict[str, str] = manifest["checksum"]
        if payload_name not in checksum:
            errors.append(f"manifest.checksum 未覆盖 payload {payload_name}")
        for arcname, expected in checksum.items():
            if arcname not in names:
                errors.append(f"manifest 声明的文件不存在: {arcname}")
                continue
            actual = sha256_bytes(zf.read(arcname))
            if actual != expected:
                errors.append(f"checksum 不匹配: {arcname}")

        # 5. 未列入 manifest 的文件：evidence/ 宽容（warning），其余拒绝
        listed = set(checksum) | {"manifest.json"}
        for n in names:
            if n.endswith("/") or n in listed:
                continue
            if n.startswith("evidence/"):
                result["warnings"].append(f"evidence 文件未列入 manifest（放行）: {n}")
            else:
                errors.append(f"未列入 manifest 的文件: {n}")
        if errors:
            return result

        # 6. 解析 payload
        try:
            result["payload"] = json.loads(zf.read(payload_name).decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            errors.append(f"{payload_name} 解析失败: {e}")
            return result

    result["ok"] = True
    return result


def extract_files(zip_path: Path | str, names: list[str], dest_dir: Path | str) -> list[Path]:
    """把 ZIP 内指定文件按相对路径解出到 dest_dir（路径已经 parse 校验过仍二次防御）。"""
    import zipfile

    dest = Path(dest_dir)
    saved: list[Path] = []
    with zipfile.ZipFile(zip_path) as zf:
        for n in names:
            if not ids.is_safe_zip_path(n):
                raise ValueError(f"拒绝解出不安全路径: {n!r}")
            target = dest / Path(*n.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(n))
            saved.append(target)
    return saved
