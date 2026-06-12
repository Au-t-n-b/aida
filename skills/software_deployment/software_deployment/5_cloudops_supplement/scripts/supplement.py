"""
第 5 步：补充 CloudOps 初始配置（对齐 Agent upload_files.handle_cloudops_config_manual_file_uploading）。

本步无 LLM 自动改写 Excel：用户下载 CloudOps_Config_Init → 线下补账号/版本/OS/磁盘/路由 →
上传为 CloudOps_Config_Manual（文件名建议含「CloudOps配置_手工补充」）。
"""
from __future__ import annotations

import glob
import os
import shutil
from dataclasses import dataclass, field
from typing import Any

MANUAL_FILE_BASENAME = "CloudOps配置_手工补充.xlsx"
INIT_FILE_BASENAME = "CloudOps初始配置.xlsx"


@dataclass
class SupplementUploadResult:
    ok: bool
    message: str
    local_manual_path: str = ""
    checklist_present: bool = False
    checklist_source: str = ""
    can_proceed_full_config: bool = False
    logs: list[str] = field(default_factory=list)


def _skills_root(skill_dir: str) -> str:
    return os.path.abspath(os.path.join(skill_dir, os.pardir))


def _plan_output(skill_dir: str) -> str:
    return os.path.join(os.path.abspath(skill_dir), "ProjectData", "plan", "Output")


def default_init_output_path(skill_dir: str) -> str:
    return os.path.join(_plan_output(skill_dir), INIT_FILE_BASENAME)


def default_manual_output_path(skill_dir: str) -> str:
    return os.path.join(_plan_output(skill_dir), MANUAL_FILE_BASENAME)


def resolve_init_download_path(skill_dir: str, chain: dict[str, Any]) -> str:
    rel = str(chain.get("step4_cloudops_output_path") or "").strip()
    if rel:
        ws = os.path.abspath(os.path.join(_skills_root(skill_dir), os.pardir))
        candidate = os.path.join(ws, rel.replace("/", os.sep))
        if os.path.isfile(candidate):
            return candidate
    return default_init_output_path(skill_dir)


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
    ws = os.path.abspath(os.path.join(_skills_root(skill_dir), os.pardir))
    full = os.path.join(ws, p.replace("/", os.sep))
    return full if os.path.isfile(full) else ""


def _manual_input_dirs(skill_dir: str) -> list[str]:
    root = os.path.abspath(skill_dir)
    return [
        os.path.join(root, "ProjectData", "input", "cloudops"),
        os.path.join(root, "ProjectData", "input"),
        os.path.join(root, "ProjectData", "Input", "cloudops"),
        os.path.join(root, "ProjectData", "Input"),
    ]


def _is_manual_supplement_basename(name: str) -> bool:
    bn = name or ""
    if not bn.lower().endswith((".xlsx", ".xls")):
        return False
    if "完整配置" in bn or "完工清单" in bn:
        return False
    if "手工" in bn or "手工补充" in bn or "补充" in bn:
        return True
    if "CloudOps" in bn and "初始配置" not in bn:
        return True
    return False


def discover_latest_manual_supplement_xlsx(skill_dir: str) -> str:
    """HITL 落盘或用户手工放入 ``input/cloudops`` 后，登记步骤 5 时兜底发现文件。"""
    best = ""
    best_mtime = 0.0
    for folder in _manual_input_dirs(skill_dir):
        if not os.path.isdir(folder):
            continue
        for pat in ("*.xlsx", "*.xls"):
            for p in glob.glob(os.path.join(folder, pat)):
                if not os.path.isfile(p):
                    continue
                bn = os.path.basename(p)
                if not _is_manual_supplement_basename(bn):
                    continue
                m = os.path.getmtime(p)
                if m >= best_mtime:
                    best_mtime = m
                    best = p
    return best


def _pick_uploaded_xlsx(uploads: list[dict[str, Any]], skill_dir: str) -> str:
    candidates: list[str] = []
    ws = os.path.abspath(os.path.join(_skills_root(skill_dir), os.pardir))
    for it in uploads:
        for key in ("path", "savedPath", "filePath", "logicalPath", "name", "fileName"):
            v = str(it.get(key) or "").strip()
            if not v:
                continue
            if not v.lower().endswith((".xlsx", ".xls")):
                continue
            if os.path.isabs(v) and os.path.isfile(v):
                candidates.append(v)
                continue
            resolved = _resolve_logical_path(skill_dir, v)
            if resolved:
                candidates.append(resolved)
                continue
            for base in (
                *_manual_input_dirs(skill_dir),
                ws,
            ):
                p = os.path.join(base, v.replace("/", os.sep).lstrip("/"))
                if os.path.isfile(p):
                    candidates.append(p)
                    break
    if candidates:
        return candidates[0]
    manual_out = default_manual_output_path(skill_dir)
    if os.path.isfile(manual_out):
        return manual_out
    discovered = discover_latest_manual_supplement_xlsx(skill_dir)
    if discovered:
        return discovered
    upload_glob = os.path.join(ws, "uploads", "**", "*.xlsx")
    for h in sorted(glob.glob(upload_glob, recursive=True), key=os.path.getmtime, reverse=True):
        if _is_manual_supplement_basename(os.path.basename(h)):
            return h
    return ""


def probe_checklist(*, skill_dir: str) -> tuple[bool, str]:
    """探测是否有可用完工清单（与第 6 步同步前发现逻辑一致）。"""
    from .file_sync import probe_checklist as _probe  # noqa: WPS433

    return _probe(skill_dir=skill_dir)


def process_manual_supplement_upload(
    *,
    skill_dir: str,
    result_obj: Any,
) -> SupplementUploadResult:
    logs: list[str] = []
    uploads = _normalize_uploads(result_obj)
    src = _pick_uploaded_xlsx(uploads, skill_dir)
    if not src or not os.path.isfile(src):
        inbox = os.path.join(os.path.abspath(skill_dir), "ProjectData", "input", "cloudops")
        return SupplementUploadResult(
            ok=False,
            message=(
                "未找到 CloudOps 手工补充 xlsx。\n"
                f"- 请先在上传卡提交，或将文件放入：`{inbox}`\n"
                f"- 建议文件名含「手工补充」或「CloudOps配置_手工补充」\n"
                "- 上传卡内请点击 **「完成上传并继续」**（不要只点引导卡上的登记按钮）"
            ),
            logs=logs,
        )
    logs.append(f"收到上传：{src}")

    dest = default_manual_output_path(skill_dir)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(src, dest)
    logs.append(f"已落盘：{dest}")

    checklist_ok, checklist_src = probe_checklist(skill_dir=skill_dir)
    if checklist_ok:
        logs.append(f"完工清单：已检测到（{checklist_src}）")
    else:
        logs.append("完工清单：未检测到（第 6 步完整配置前须上传设备安装完工清单）")

    can_full = checklist_ok
    if can_full:
        msg = "手工补充配置已登记（SUPPLY_INFO 等价完成），可继续生成 CloudOps 完整配置。"
    else:
        msg = (
            "手工补充配置已登记，但尚未检测到完工清单。"
            "请先上传设备安装完工清单，再执行第 6 步「生成 CloudOps 完整配置」。"
        )

    return SupplementUploadResult(
        ok=True,
        message=msg,
        local_manual_path=dest,
        checklist_present=checklist_ok,
        checklist_source=checklist_src,
        can_proceed_full_config=can_full,
        logs=logs,
    )


def build_step5_guidance_markdown(
    *,
    skill_dir: str,
    chain: dict[str, Any],
    checklist_ok: bool,
    checklist_src: str,
    init_path: str = "",
) -> str:
    from .download_links import (  # noqa: WPS433
        format_init_download_markdown,
        format_supplement_editor_note,
        resolve_init_download_offers,
    )

    if not init_path:
        init_path = resolve_init_download_path(skill_dir, chain)
    offers = resolve_init_download_offers(skill_dir=skill_dir, chain=chain)
    download_block = format_init_download_markdown(offers)
    editor_note = format_supplement_editor_note(skill_dir=skill_dir)

    lines = [
        "**⑤ 补充 CloudOps 初始配置**",
        "",
        "本步**不会自动改写** Excel，请按下列顺序操作：",
        "",
        "1. **获取/下载**第 4 步生成的初始配置（`CloudOps_Config_Init`）",
        download_block,
        editor_note,
        "",
    ]
    if init_path:
        lines.append(f"   - 本机绝对路径：`{init_path}`")
    lines.extend(
        [
        "2. **编辑**，补全模板中 LLD 未填写的字段，例如：",
        "   - 账号 / 密码",
        "   - 版本信息、OS 配置、磁盘分区、路由等",
        "",
        "3. **上传**编辑后的文件到 `ProjectData/input/cloudops/`",
        f"   - 建议文件名含：**{MANUAL_FILE_BASENAME.replace('.xlsx', '')}**",
        "   - 使用下方 **「上传 CloudOps 手工补充文件」** 按钮",
        "",
        ]
    )
    if checklist_ok:
        lines.append(f"4. 完工清单：**已就绪**（{checklist_src}），上传补充文件后可进入第 6 步。")
    else:
        lines.append(
            "4. 完工清单：**尚未检测到**。上传补充文件后，还须上传「设备安装完工清单」，"
            "才能执行「生成 CloudOps 完整配置文件」。"
        )
    return "\n".join(lines)
