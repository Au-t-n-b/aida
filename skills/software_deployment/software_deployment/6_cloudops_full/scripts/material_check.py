# -*- coding: utf-8 -*-
"""步骤 6b：CloudOps 导入前材料检查（ZTP / 测试参数）。

这一步只做材料探测、登记和提醒；不阻塞后续导入 CloudOps 完整配置。
"""
from __future__ import annotations

import glob
import os
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PARAMS_CANONICAL_BASENAME = "CloudOps_task_params_latest.xlsx"
ZTP_CANONICAL_BASENAME = "ZTP文件_latest.zip"


@dataclass
class ZtpProbeResult:
    present: bool
    local_path: str = ""
    source: str = ""
    file_name: str = ""
    message: str = ""


@dataclass
class ZtpUploadResult:
    ok: bool
    message: str
    local_path: str = ""
    workspace_rel: str = ""
    source: str = ""
    logs: list[str] = field(default_factory=list)


@dataclass
class ParamsProbeResult:
    present: bool
    local_path: str = ""
    file_name: str = ""
    message: str = ""


@dataclass
class ParamsUploadResult:
    ok: bool
    message: str
    local_path: str = ""
    workspace_rel: str = ""
    logs: list[str] = field(default_factory=list)


def cloudops_input_dir(skill_dir: str) -> str:
    return os.path.join(os.path.abspath(skill_dir), "ProjectData", "input", "cloudops")


def default_params_canonical_path(skill_dir: str) -> str:
    return os.path.join(cloudops_input_dir(skill_dir), PARAMS_CANONICAL_BASENAME)


def default_ztp_canonical_path(skill_dir: str) -> str:
    return os.path.join(cloudops_input_dir(skill_dir), ZTP_CANONICAL_BASENAME)


def scene_requires_ztp(scene: dict[str, Any] | None) -> bool:
    """A3 场景在 Agent 侧通常必须提供 ZTP（灵衢配置检查）。"""
    if not scene:
        return True
    ps = str(
        scene.get("productSpecification")
        or scene.get("product_specification")
        or scene.get("product_spec")
        or "A3"
    ).strip().upper()
    return ps == "A3"


def _is_ztp_zip_name(name: str) -> bool:
    bn = (name or "").strip()
    if not bn.lower().endswith(".zip"):
        return False
    low = bn.lower()
    if "cloudops" in low and "task_params" in low:
        return False
    return "ztp" in low or "ZTP" in bn


def discover_latest_ztp_zip(skill_dir: str) -> str:
    best = ""
    best_mtime = 0.0
    folder = cloudops_input_dir(skill_dir)
    if not os.path.isdir(folder):
        return ""
    for pat in ("ZTP*.zip", "*ZTP*.zip", "ZTP文件*.zip"):
        for p in glob.glob(os.path.join(folder, pat)):
            if not os.path.isfile(p):
                continue
            if not _is_ztp_zip_name(os.path.basename(p)):
                continue
            m = os.path.getmtime(p)
            if m >= best_mtime:
                best_mtime = m
                best = p
    return best


def _is_params_xlsx_name(name: str) -> bool:
    bn = (name or "").strip()
    if not bn.lower().endswith(".xlsx"):
        return False
    low = bn.lower()
    return "task_params" in low or "测试参数" in bn or "上传测试参数" in bn


def discover_latest_params_xlsx(skill_dir: str) -> str:
    folder = cloudops_input_dir(skill_dir)
    if not os.path.isdir(folder):
        return ""
    best = ""
    best_mtime = 0.0
    patterns = (
        "CloudOps_task_params*.xlsx",
        "*task_params*.xlsx",
        "*测试参数*.xlsx",
        "*上传测试参数*.xlsx",
    )
    for pat in patterns:
        for p in glob.glob(os.path.join(folder, pat)):
            if not os.path.isfile(p):
                continue
            name = os.path.basename(p)
            if name.startswith("~$") or not _is_params_xlsx_name(name):
                continue
            mtime = os.path.getmtime(p)
            if mtime >= best_mtime:
                best_mtime = mtime
                best = p
    return best


def _normalize_uploads(result_obj: Any) -> list[dict[str, Any]]:
    if not isinstance(result_obj, dict):
        return []
    ups = result_obj.get("uploads")
    if isinstance(ups, list):
        return [u for u in ups if isinstance(u, dict)]
    one = result_obj.get("upload")
    if isinstance(one, dict):
        return [one]
    return []


def _resolve_logical_path(skill_dir: str, logical: str) -> str:
    p = (logical or "").strip().replace("\\", "/")
    if not p:
        return ""
    if p.startswith("workspace/"):
        p = p[len("workspace/") :]
    ws = os.path.abspath(os.path.join(os.path.abspath(skill_dir), os.pardir))
    full = os.path.join(ws, p.replace("/", os.sep))
    return full if os.path.isfile(full) else ""


def _pick_uploaded_params(uploads: list[dict[str, Any]], skill_dir: str) -> str:
    candidates: list[str] = []
    ws = os.path.abspath(os.path.join(os.path.abspath(skill_dir), os.pardir))
    inbox = cloudops_input_dir(skill_dir)
    for it in uploads:
        for key in ("path", "savedPath", "filePath", "logicalPath", "name", "fileName"):
            v = str(it.get(key) or "").strip()
            if not v or not v.lower().endswith(".xlsx"):
                continue
            if not _is_params_xlsx_name(os.path.basename(v.replace("\\", "/").split("/")[-1])):
                continue
            if os.path.isabs(v) and os.path.isfile(v):
                candidates.append(v)
                continue
            resolved = _resolve_logical_path(skill_dir, v)
            if resolved:
                candidates.append(resolved)
                continue
            for base in (inbox, ws):
                p = os.path.join(base, v.replace("/", os.sep).lstrip("/"))
                if os.path.isfile(p):
                    candidates.append(p)
                    break
    if candidates:
        return candidates[0]
    return discover_latest_params_xlsx(skill_dir)


def _pick_uploaded_zip(uploads: list[dict[str, Any]], skill_dir: str) -> str:
    candidates: list[str] = []
    ws = os.path.abspath(os.path.join(os.path.abspath(skill_dir), os.pardir))
    inbox = cloudops_input_dir(skill_dir)
    for it in uploads:
        for key in ("path", "savedPath", "filePath", "logicalPath", "name", "fileName"):
            v = str(it.get(key) or "").strip()
            if not v or not v.lower().endswith(".zip"):
                continue
            if not _is_ztp_zip_name(os.path.basename(v.replace("\\", "/").split("/")[-1])):
                continue
            if os.path.isabs(v) and os.path.isfile(v):
                candidates.append(v)
                continue
            resolved = _resolve_logical_path(skill_dir, v)
            if resolved:
                candidates.append(resolved)
                continue
            for base in (inbox, ws):
                p = os.path.join(base, v.replace("/", os.sep).lstrip("/"))
                if os.path.isfile(p):
                    candidates.append(p)
                    break
    if candidates:
        return candidates[0]
    return discover_latest_ztp_zip(skill_dir)


def _validate_zip(path: str) -> tuple[bool, str]:
    if not zipfile.is_zipfile(path):
        return False, "文件不是有效的 zip 格式"
    try:
        with zipfile.ZipFile(path, "r") as zf:
            if zf.testzip() is not None:
                return False, "zip 包 CRC 校验失败，请重新打包上传"
    except Exception as e:
        return False, f"无法读取 zip：{e}"
    return True, ""


def probe_ztp(*, skill_dir: str, chain: dict[str, Any]) -> ZtpProbeResult:
    rel = str(chain.get("step6_ztp_path") or "").strip()
    if rel:
        ws = os.path.abspath(os.path.join(os.path.abspath(skill_dir), os.pardir))
        p = os.path.join(ws, rel.replace("/", os.sep))
        if os.path.isfile(p):
            return ZtpProbeResult(
                present=True,
                local_path=p,
                source=str(chain.get("step6_ztp_source") or "deployment_local"),
                file_name=os.path.basename(p),
                message="已登记步骤 6 材料 ZTP 文件",
            )
    local = discover_latest_ztp_zip(skill_dir)
    if local:
        return ZtpProbeResult(
            present=True,
            local_path=local,
            source="deployment_local",
            file_name=os.path.basename(local),
            message=f"本地 input/cloudops 已存在 ZTP：`{os.path.basename(local)}`",
        )
    return ZtpProbeResult(present=False, message="未检测到 ZTP 文件（zip）")


def process_ztp_upload(*, skill_dir: str, result_obj: Any) -> ZtpUploadResult:
    logs: list[str] = []
    src = _pick_uploaded_zip(_normalize_uploads(result_obj), skill_dir)
    if not src or not os.path.isfile(src):
        inbox = cloudops_input_dir(skill_dir)
        return ZtpUploadResult(
            ok=False,
            message=(
                "未找到 ZTP zip 文件。\n"
                f"- 请上传至 `{inbox}`（文件名须为 ZTP*.zip）\n"
                "- 上传卡内请点击 **「完成上传并刷新材料检查」**"
            ),
            logs=logs,
        )
    ok_zip, zip_msg = _validate_zip(src)
    if not ok_zip:
        return ZtpUploadResult(ok=False, message=zip_msg, logs=logs)
    logs.append(f"收到：{src}")

    os.makedirs(cloudops_input_dir(skill_dir), exist_ok=True)
    dest = default_ztp_canonical_path(skill_dir)
    shutil.copy2(src, dest)
    logs.append(f"已落盘：{dest}")

    rel = f"skills/{Path(skill_dir).resolve().name}/ProjectData/input/cloudops/{ZTP_CANONICAL_BASENAME}"
    return ZtpUploadResult(
        ok=True,
        message=f"ZTP 文件已登记（{os.path.basename(dest)}），后续灵衢配置检查将使用本步骤上传的包。",
        local_path=dest,
        workspace_rel=rel,
        source="deployment_local",
        logs=logs,
    )


def probe_params(*, skill_dir: str, chain: dict[str, Any]) -> ParamsProbeResult:
    rel = str(chain.get("step6_params_path") or "").strip()
    if rel:
        ws = os.path.abspath(os.path.join(os.path.abspath(skill_dir), os.pardir))
        p = os.path.join(ws, rel.replace("/", os.sep))
        if os.path.isfile(p):
            return ParamsProbeResult(
                present=True,
                local_path=p,
                file_name=os.path.basename(p),
                message="已登记 CloudOps 上传测试参数文件",
            )
    local = discover_latest_params_xlsx(skill_dir)
    if local:
        return ParamsProbeResult(
            present=True,
            local_path=local,
            file_name=os.path.basename(local),
            message=f"本地 input/cloudops 已存在测试参数：`{os.path.basename(local)}`",
        )
    return ParamsProbeResult(present=False, message="未检测到 CloudOps 上传测试参数 xlsx")


def process_params_upload(*, skill_dir: str, result_obj: Any) -> ParamsUploadResult:
    logs: list[str] = []
    src = _pick_uploaded_params(_normalize_uploads(result_obj), skill_dir)
    if not src or not os.path.isfile(src):
        inbox = cloudops_input_dir(skill_dir)
        return ParamsUploadResult(
            ok=False,
            message=(
                "未找到 CloudOps 上传测试参数 xlsx。\n"
                f"- 请上传至 `{inbox}`（文件名建议含 `CloudOps_task_params` 或「测试参数」）\n"
                "- 上传卡内请点击 **「完成上传并刷新材料检查」**"
            ),
            logs=logs,
        )

    os.makedirs(cloudops_input_dir(skill_dir), exist_ok=True)
    dest = default_params_canonical_path(skill_dir)
    if os.path.abspath(src) != os.path.abspath(dest):
        shutil.copy2(src, dest)
    logs.append(f"收到：{src}")
    logs.append(f"已登记：{dest}")

    rel = f"skills/{Path(skill_dir).resolve().name}/ProjectData/input/cloudops/{PARAMS_CANONICAL_BASENAME}"
    return ParamsUploadResult(
        ok=True,
        message=f"CloudOps 上传测试参数文件已登记（{os.path.basename(dest)}）。",
        local_path=dest,
        workspace_rel=rel,
        logs=logs,
    )


def build_step6_material_markdown(
    *,
    full_detail: str,
    requires_ztp: bool,
    ztp_present: bool,
    ztp_message: str,
    params_present: bool,
    params_message: str,
) -> str:
    ztp_state = "已上传" if ztp_present else ("未上传（A3 建议补充）" if requires_ztp else "未上传（可选）")
    params_state = "已上传" if params_present else "未上传（执行 Toolkit API 任务前建议补充）"
    lines = [
        full_detail.strip(),
        "",
        "**导入前材料检查（不阻塞导入 CloudOps 配置）**",
        f"- ZTP 文件：{ztp_state}。{ztp_message}",
        f"- 测试参数文件：{params_state}。{params_message}",
        "",
        "说明：ZTP 供后续 **灵衢配置检查** 使用；测试参数供后续 CloudOps Toolkit 具体 API 任务按需解析。",
        "即使两项未齐，也可以先继续配置调测设备并导入 CloudOps 完整配置。",
    ]
    return "\n".join(lines)
