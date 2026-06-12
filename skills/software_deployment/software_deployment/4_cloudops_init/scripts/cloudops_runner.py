"""
第 4 步编排：解析 LLD / 模板路径 → 调用 LldToCloudOpsConfig → 落盘。
"""
from __future__ import annotations

import glob
import io
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Callable

from .lld_to_cloudops import AgentFileContentError, LldToCloudOpsConfig


@dataclass
class CloudOpsInitResult:
    ok: bool
    message: str
    output_path: str = ""
    output_bytes_len: int = 0
    lld_source: str = ""
    template_source: str = ""
    logs: list[str] = field(default_factory=list)


def _template_is_feature_new_schema(path: str) -> bool:
    """新模板服务器 sheet 须含 主机名称 + IBMC-IP地址（非旧版 设备名称 / IBMC-IPV4地址）。"""
    if not path or not os.path.isfile(path):
        return False
    try:
        import pandas as pd

        cols = {str(c).strip() for c in pd.read_excel(path, sheet_name=0, nrows=0).columns}
        return "主机名称" in cols and "IBMC-IP地址" in cols
    except Exception:
        return False


def bundled_template_path(skill_dir: str) -> str:
    """步骤 4 自带空模板路径（``software_deployment/4_cloudops_init/templates/``）。"""
    root = os.path.abspath(skill_dir)
    return os.path.join(
        root,
        "software_deployment",
        "4_cloudops_init",
        "templates",
        "cloud_ops_config_template.xlsx",
    )


def default_template_path(skill_dir: str) -> str:
    """Skill 自带 CloudOps 空模板；可用环境变量 ``SD_CLOUDOPS_TEMPLATE_PATH`` 覆盖。"""
    custom = os.environ.get("SD_CLOUDOPS_TEMPLATE_PATH", "").strip()
    if not custom:
        custom = os.environ.get("DNT_CLOUDOPS_TEMPLATE_PATH", "").strip()
    if custom and os.path.isfile(custom):
        return custom
    return bundled_template_path(skill_dir)


def validate_cloudops_template(path: str) -> tuple[bool, str]:
    """校验模板存在且为 feature_new 列结构；失败时返回可读说明。"""
    if not path or not os.path.isfile(path):
        return (
            False,
            f"CloudOps 模板不存在: {path}。"
            "请将 cloud_ops_config_template.xlsx 置于 "
            "software_deployment/4_cloudops_init/templates/ 目录。",
        )
    if not _template_is_feature_new_schema(path):
        return (
            False,
            f"CloudOps 模板列结构过旧: {path}。"
            "服务器信息 sheet 须包含「主机名称」「IBMC-IP地址」。",
        )
    return True, ""


def resolve_lld_local_path(skill_dir: str, explicit: str = "") -> tuple[str, str]:
    """返回 (path, source_label)。优先 plan_dispatch（与第 3 步下发一致）。"""
    if explicit and os.path.isfile(explicit):
        return explicit, "config:lld_local_path"
    for key in ("DNT_LLD_LOCAL_PATH", "LLD_LOCAL_PATH", "SD_LLD_LOCAL_PATH"):
        env_p = os.environ.get(key, "").strip()
        if env_p and os.path.isfile(env_p):
            return env_p, f"env:{key}"
    try:
        from pathlib import Path

        root = Path(skill_dir).resolve()
        rt = root / "runtime"
        if str(rt) not in sys.path:
            sys.path.insert(0, str(rt))
        from sd_script_import import import_sd_script  # noqa: WPS433

        lld = import_sd_script(root, "3_plan_dispatch", "lld_resolve")
        p = lld.resolve_lld_path(root)
        if p:
            return p, "plan_dispatch:LLD设计"
    except Exception:
        pass
    for sub in ("plan_dispatch", "cloudops", ""):
        base = os.path.join(skill_dir, "ProjectData", "input", sub) if sub else os.path.join(
            skill_dir, "ProjectData", "input"
        )
        if not os.path.isdir(base):
            continue
        for pat in ("*LLD设计*.xlsx", "*LLD*.xlsx", "lld/*LLD设计*.xlsx"):
            hits = sorted(glob.glob(os.path.join(base, pat)))
            if hits:
                return hits[0], f"input/{sub or 'root'}:{os.path.basename(hits[0])}"
    return "", ""


def plan_output_dir(skill_dir: str) -> str:
    return os.path.join(os.path.abspath(skill_dir), "ProjectData", "plan", "Output")


def run_cloudops_init_from_lld(
    *,
    lld_path: str,
    template_path: str,
    product_specification: str,
    cooling: str = "",
    output_path: str,
    on_progress: Callable[[str], None] | None = None,
) -> CloudOpsInitResult:
    logs: list[str] = []

    def _log(m: str) -> None:
        logs.append(m)
        if on_progress:
            on_progress(m)

    if not lld_path or not os.path.isfile(lld_path):
        return CloudOpsInitResult(ok=False, message=f"LLD 文件不存在: {lld_path}", logs=logs)
    tpl_ok, tpl_msg = validate_cloudops_template(template_path)
    if not tpl_ok:
        return CloudOpsInitResult(ok=False, message=tpl_msg, logs=logs)
    if not product_specification:
        return CloudOpsInitResult(
            ok=False,
            message="缺少 product_specification（A2/A3），请确认 plan/RunTime/scene.json 已同步。",
            logs=logs,
        )

    try:
        with open(lld_path, "rb") as f:
            lld_bytes = f.read()
        engine = LldToCloudOpsConfig(
            product_specification=product_specification,
            cooling=cooling,
            on_progress=_log,
        )
        out_bytes = engine.generate(
            io.BytesIO(lld_bytes),
            lld_file_name=os.path.basename(lld_path),
            template_path=template_path,
        )
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as out:
            out.write(out_bytes)
        _log(f"已写入 {output_path}（{len(out_bytes)} 字节）")
        return CloudOpsInitResult(
            ok=True,
            message="CloudOps 初始配置已生成",
            output_path=output_path,
            output_bytes_len=len(out_bytes),
            lld_source=lld_path,
            template_source=template_path,
            logs=logs,
        )
    except AgentFileContentError as e:
        return CloudOpsInitResult(
            ok=False, message=e.report_message or str(e), logs=logs
        )
    except PermissionError:
        return CloudOpsInitResult(
            ok=False,
            message=(
                f"无法写入「{os.path.basename(output_path)}」：文件可能被 Excel/WPS 打开占用。"
                f"请关闭该文件后重试。路径：{output_path}"
            ),
            logs=logs,
        )
    except OSError as e:
        if getattr(e, "errno", None) == 13:
            return CloudOpsInitResult(
                ok=False,
                message=(
                    f"无法写入「{os.path.basename(output_path)}」：权限被拒绝（常见原因：Excel 正在打开该文件）。"
                    f"请关闭后重试。路径：{output_path}"
                ),
                logs=logs,
            )
        return CloudOpsInitResult(ok=False, message=str(e), logs=logs)
    except Exception as e:
        return CloudOpsInitResult(ok=False, message=str(e), logs=logs)


def run_cloudops_init_for_project(
    *,
    skill_dir: str,
    product_specification: str = "",
    cooling: str = "",
    lld_local_path: str = "",
    template_path: str = "",
    output_path: str = "",
) -> CloudOpsInitResult:
    """Skill 第 4 步入口：仅使用本地 LLD 与模板。"""
    logs: list[str] = []
    tpl = template_path or default_template_path(skill_dir)
    out = output_path or os.path.join(plan_output_dir(skill_dir), "CloudOps初始配置.xlsx")

    lld_path, lld_src = resolve_lld_local_path(skill_dir, lld_local_path)
    if not lld_path:
        return CloudOpsInitResult(
            ok=False,
            message=(
                "未找到 LLD：请将 LLD设计*.xlsx 放入 ProjectData/input/plan_dispatch，"
                "或设置环境变量 SD_LLD_LOCAL_PATH / DNT_LLD_LOCAL_PATH。"
            ),
            logs=logs,
        )

    result = run_cloudops_init_from_lld(
        lld_path=lld_path,
        template_path=tpl,
        product_specification=product_specification,
        cooling=cooling,
        output_path=out,
        on_progress=lambda m: logs.append(m),
    )
    result.lld_source = lld_src or lld_path
    result.template_source = tpl
    result.logs = logs + result.logs
    return result
