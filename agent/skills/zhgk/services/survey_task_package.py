"""
survey_task_package · 勘测任务包构建（v4 · 视频勘测/现场勘测下发件）

设计文档 意图B Step 7a/7b：表确认后生成「勘测任务包」供工程师下载，
带到现场或下发手机端视频勘测 App。任务包 = 全量勘测结果表 + 任务清单 manifest。

回传走原有 wait_survey 上传合并通道，无需在此处理。
纯文件构建，无 LLM、无网络。
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any


def build_survey_task_package(
    survey_table_path: str,
    output_dir: str,
    *,
    project_name: str = "",
    room_name: str = "",
    activity_id: str = "",
    on_site_items: list[dict] | None = None,
) -> str:
    """
    打包勘测任务包 zip：全量勘测结果表 + manifest.json（任务说明 + 现场勘测条目）。

    返回生成的 zip 绝对路径。
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    prefix = "_".join(p for p in (activity_id, project_name, room_name) if p) or "勘测任务包"
    zip_path = out / f"{prefix}_勘测任务包.zip"

    manifest: dict[str, Any] = {
        "type": "survey_task_package",
        "version": "v4",
        "project_name": project_name,
        "room_name": room_name,
        "activity_id": activity_id,
        "survey_table": Path(survey_table_path).name,
        "instructions": (
            "1. 视频勘测：用手机端 App 导入本任务包，按条目逐项拍摄/记录；\n"
            "2. 现场勘测：打印或下载全量勘测结果表，逐项填写「最新检查结果」列；\n"
            "3. 完成后将填好的表另存为「已填写_全量勘测结果表.xlsx」回传上传。"
        ),
        "on_site_items": on_site_items or [],
        "on_site_count": len(on_site_items or []),
    }

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # 主表
        tp = Path(survey_table_path)
        if tp.is_file():
            zf.write(tp, arcname=tp.name)
        # 任务清单
        zf.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )

    return str(zip_path)


def collect_on_site_items(survey_table_path: str) -> list[dict]:
    """从全量勘测结果表提取「现场勘测」条目（供任务包 manifest 用）。"""
    try:
        from .survey_table_builder import read_survey_table
    except Exception:
        return []
    try:
        rows = read_survey_table(survey_table_path)
    except Exception:
        return []
    items: list[dict] = []
    for row in rows:
        if (row.get("勘测方法") or "") == "现场勘测":
            items.append({
                "序号": row.get("序号"),
                "细分场景": row.get("细分场景", ""),
                "勘测要素": row.get("勘测要素", ""),
                "项目": row.get("项目", ""),
                "检查内容": row.get("检查内容", ""),
            })
    return items
