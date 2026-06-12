"""
CloudOps 初配文件下载入口（Phase 1: 本机 /api/file；预留 EDM pre_download）。

Phase 2b 内置在线编辑页路径见 ``EDITOR_WORKSPACE_PATH``（deploymentandtest/ui/）。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from .supplement import INIT_FILE_BASENAME, resolve_init_download_path

# nanobot 内置补充编辑页（2b）；HTML 落地后可在 dashboard iframe 或新标签打开
EDITOR_WORKSPACE_PATH = "skills/deploymentandtest/ui/cloudops_supplement_editor.html"

DEFAULT_INIT_WORKSPACE_REL = (
    "skills/deploymentandtest/ProjectData/Output/CloudOps初始配置.xlsx"
)


@dataclass(frozen=True)
class InitDownloadOffer:
    """一条可展示的下载/获取方式。"""

    source: str  # local | edm
    label: str
    href: str = ""
    workspace_path: str = ""
    available: bool = True
    note: str = ""


def _workspace_root(skill_dir: str) -> str:
    return os.path.abspath(os.path.join(os.path.abspath(os.path.join(skill_dir, os.pardir)), os.pardir))


def abs_path_to_workspace_rel(abs_path: str, skill_dir: str) -> str:
    """绝对路径 → ``workspace/`` 下相对路径（用于 /api/file）。"""
    if not abs_path:
        return ""
    ws = _workspace_root(skill_dir)
    try:
        rel = os.path.relpath(os.path.abspath(abs_path), ws)
    except ValueError:
        return ""
    if rel.startswith(".."):
        return ""
    return rel.replace("\\", "/")


def workspace_file_href(workspace_rel: str) -> str:
    rel = (workspace_rel or "").strip().replace("\\", "/").lstrip("/")
    if not rel:
        return ""
    return f"/api/file?path={quote(rel)}"


def workspace_file_download_href(workspace_rel: str, download_filename: str = "") -> str:
    """``download=1`` 触发浏览器保存为附件，避免仅打开右侧只读预览。"""
    rel = (workspace_rel or "").strip().replace("\\", "/").lstrip("/")
    if not rel:
        return ""
    q = f"path={quote(rel)}&download=1"
    name = (download_filename or os.path.basename(rel) or INIT_FILE_BASENAME).strip()
    if name:
        q += f"&filename={quote(name)}"
    return f"/api/file?{q}"


def resolve_init_download_offers(
    *,
    skill_dir: str,
    chain: dict[str, Any],
) -> list[InitDownloadOffer]:
    """
    解析第 5 步可用的初配下载方式。

    - ``local``：第 4 步落盘文件，GET ``/api/file?path=...``
    """
    offers: list[InitDownloadOffer] = []

    abs_path = resolve_init_download_path(skill_dir, chain)
    rel_chain = str(chain.get("step4_cloudops_output_path") or "").strip().replace("\\", "/")
    workspace_rel = rel_chain or abs_path_to_workspace_rel(abs_path, skill_dir)
    if not workspace_rel and abs_path:
        workspace_rel = abs_path_to_workspace_rel(abs_path, skill_dir)
    if not workspace_rel:
        workspace_rel = DEFAULT_INIT_WORKSPACE_REL

    local_ok = bool(abs_path and os.path.isfile(abs_path))
    if not local_ok and workspace_rel:
        candidate = os.path.join(_workspace_root(skill_dir), workspace_rel.replace("/", os.sep))
        local_ok = os.path.isfile(candidate)
        if local_ok:
            abs_path = candidate

    if local_ok:
        offers.append(
            InitDownloadOffer(
                source="local",
                label="下载 CloudOps 初始配置（本机）",
                href=workspace_file_download_href(workspace_rel, INIT_FILE_BASENAME),
                workspace_path=workspace_rel,
                available=True,
            )
        )

    return offers


def format_init_download_markdown(offers: list[InitDownloadOffer]) -> str:
    """
    生成指引正文（纯文本列表）。

    注意：``chat.guidance`` 的 ``context`` 在宿主 UI 中**不渲染 Markdown 链接**，
    可点击下载须用 ``build_init_download_guidance_actions`` 中 **「下载 CloudOps 初始配置」** 按钮（``open_url`` + ``download=1``）。
    """
    if not offers:
        return (
            "- 未找到可下载的初始配置文件。请先完成 **第 4 步** 生成，"
            f"或确认 `{DEFAULT_INIT_WORKSPACE_REL}` 存在。"
        )
    lines: list[str] = []
    for o in offers:
        if o.source == "local" and o.available:
            lines.append(f"- {o.label}（请点下方 **「下载 CloudOps 初始配置」**，勿用「预览」代替下载）")
            if o.workspace_path:
                lines.append(f"  - workspace 路径：`{o.workspace_path}`")
        elif o.source == "edm":
            lines.append(f"- {o.label}")
            if o.note:
                lines.append(f"  - {o.note}")
        elif o.note:
            lines.append(f"- {o.label}：{o.note}")
    return "\n".join(lines)


def build_init_download_guidance_actions(
    offers: list[InitDownloadOffer],
    *,
    skill_dir: str,
) -> list[dict[str, object]]:
    """生成 GuidanceCard 可点击动作：下载（attachment）+ 可选预览 + 内置编辑页。"""
    actions: list[dict[str, Any]] = []
    for o in offers:
        if o.source == "local" and o.available and o.workspace_path:
            fname = os.path.basename(o.workspace_path) or INIT_FILE_BASENAME
            actions.append(
                {
                    "label": "下载 CloudOps 初始配置",
                    "verb": "open_url",
                    "payload": {
                        "url": workspace_file_download_href(o.workspace_path, fname),
                        "filename": fname,
                    },
                }
            )
            actions.append(
                {
                    "label": "预览",
                    "verb": "open_preview",
                    "payload": {"path": o.workspace_path},
                }
            )
    ws = _workspace_root(skill_dir)
    editor_abs = os.path.join(ws, EDITOR_WORKSPACE_PATH.replace("/", os.sep))
    if os.path.isfile(editor_abs):
        actions.append(
            {
                "label": "打开在线编辑页",
                "verb": "open_preview",
                "payload": {"path": EDITOR_WORKSPACE_PATH},
            }
        )
    return actions


def supplement_editor_href() -> str:
    """Phase 2b：内置编辑页 URL（HTML 存在时可打开）。"""
    return workspace_file_href(EDITOR_WORKSPACE_PATH)


def format_supplement_editor_note(*, skill_dir: str) -> str:
    """第 5 步指引中关于内置在线编辑的说明（2b）。"""
    ws = _workspace_root(skill_dir)
    html_abs = os.path.join(ws, EDITOR_WORKSPACE_PATH.replace("/", os.sep))
    if os.path.isfile(html_abs):
        return (
            "1b. **在线编辑**（nanobot 内置页）：请点下方 "
            "「打开在线编辑页」→ 编辑后 **保存**，再点 **「完成上传并继续」** 登记第 5 步。"
        )
    return (
        "1b. **在线编辑**（nanobot 内置页，开发中）："
        f"将使用 `{EDITOR_WORKSPACE_PATH}`；当前请先点「下载」后在 Excel 中编辑。"
    )
