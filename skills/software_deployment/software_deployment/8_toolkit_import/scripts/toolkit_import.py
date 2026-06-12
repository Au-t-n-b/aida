# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from .cloudops_client import CloudOpsClient, GatewayEnv


def _skill_root(skill_dir: str) -> Path:
    root = Path(skill_dir).resolve()
    os.environ.setdefault("SD_SKILL_ROOT", str(root))
    return root


def _plan_dir(skill_dir: str) -> Path:
    return _skill_root(skill_dir) / "ProjectData" / "plan"


def _output_dir(skill_dir: str) -> Path:
    return _plan_dir(skill_dir) / "Output"


def _cloudops_input_dir(skill_dir: str) -> Path:
    return _skill_root(skill_dir) / "ProjectData" / "input" / "cloudops"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_executor_config(skill_dir: str) -> dict[str, Any]:
    return _load_json(_plan_dir(skill_dir) / "RunTime" / "toolkit_executor.json")


def gateway_config_path(skill_dir: str) -> Path:
    return _plan_dir(skill_dir) / "RunTime" / "gateway.json"


def load_gateway_config_file(skill_dir: str) -> dict[str, str]:
    raw = _load_json(gateway_config_path(skill_dir))
    return {
        "apigw_url": str(raw.get("apigw_url") or "").strip(),
        "gateway_key": str(raw.get("gateway_key") or "").strip(),
        "hw_app_id": str(raw.get("hw_app_id") or "").strip(),
    }


def load_chain(skill_dir: str) -> dict[str, Any]:
    return _load_json(_plan_dir(skill_dir) / "RunTime" / "deploy_chain.json")

def _runtime_dir(skill_dir: str) -> Path:
    return _plan_dir(skill_dir) / "RunTime"


def _base_table_path(skill_dir: str) -> Path:
    return _output_dir(skill_dir) / "device_base_table.json"


def summarize_base_table_status(skill_dir: str) -> dict[str, Any]:
    """
    汇总底表状态，供完成卡展示。

    - byTaskStatus: 任务行维度计数
    - byDeviceInit: 设备维度计数（只区分 INIT_DONE / UN_INIT）
    """
    base = _load_json(_base_table_path(skill_dir))
    tasks = base.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return {"taskRows": 0, "deviceCount": 0, "byTaskStatus": {}, "byDeviceInit": {}}

    by_task: dict[str, int] = {}
    device_best: dict[str, str] = {}
    for row in tasks:
        if not isinstance(row, dict):
            continue
        st = str(row.get("taskStatus") or "").strip() or "UN_INIT"
        by_task[st] = by_task.get(st, 0) + 1
        dn = str(row.get("deviceName") or "").strip()
        if not dn:
            continue
        dev_st = "INIT_DONE" if st == "INIT_DONE" else "UN_INIT"
        if dn not in device_best:
            device_best[dn] = dev_st
        else:
            if device_best[dn] != "INIT_DONE" and dev_st == "INIT_DONE":
                device_best[dn] = "INIT_DONE"

    by_dev: dict[str, int] = {"UN_INIT": 0, "INIT_DONE": 0}
    for st in device_best.values():
        by_dev["INIT_DONE" if st == "INIT_DONE" else "UN_INIT"] += 1

    return {
        "taskRows": sum(by_task.values()),
        "deviceCount": len(device_best),
        "byTaskStatus": by_task,
        "byDeviceInit": by_dev,
    }


def save_import_receipt(
    *,
    skill_dir: str,
    config_file: str,
    executor: dict[str, Any],
    gateway: GatewayEnv,
    import_response: dict[str, Any],
    refresh: dict[str, Any] | None = None,
) -> Path:
    """落盘导入回执，便于排障与审计。"""
    payload: dict[str, Any] = {
        "schemaVersion": 1,
        "configFile": config_file,
        "executor": {
            "base_url_ip": str(executor.get("base_url_ip") or ""),
            "base_url_port": str(executor.get("base_url_port") or "28880"),
        },
        "gateway": {
            "apigw_url": gateway.apigw_url,
            "hw_app_id": gateway.hw_app_id,
        },
        "importResponse": import_response,
    }
    if isinstance(refresh, dict):
        payload["refresh"] = refresh
    out = _runtime_dir(skill_dir) / "toolkit_import.json"
    _save_json(out, payload)
    return out


def resolve_cloudops_full_path(skill_dir: str, chain: dict[str, Any]) -> Path:
    out_dir = _output_dir(skill_dir)
    prefer = str(chain.get("step6_cloudops_full_path") or "").strip().replace("\\", "/")
    if prefer:
        ws_root = _skill_root(skill_dir).resolve().parent.parent
        rel = prefer.removeprefix("workspace/").lstrip("/")
        candidate = (ws_root / rel).resolve()
        if candidate.is_file():
            return candidate
    return out_dir / "CloudOps完整配置文件.xlsx"


def _load_gateway_config(skill_dir: str) -> tuple[bool, str, GatewayEnv | None]:
    """JSON（plan/RunTime/gateway.json）为默认；环境变量 CLOUDOPS_* 可覆盖。"""
    cfg = load_gateway_config_file(skill_dir)
    apigw_url = str(os.environ.get("CLOUDOPS_APIGW_URL") or cfg["apigw_url"]).strip()
    gateway_key = str(os.environ.get("CLOUDOPS_GATEWAY_KEY") or cfg["gateway_key"]).strip()
    hw_app_id = str(os.environ.get("CLOUDOPS_HW_APP_ID") or cfg["hw_app_id"]).strip()
    if not apigw_url or not gateway_key or not hw_app_id:
        return (
            False,
            "缺少 APIGW 网关配置：请编辑 `ProjectData/plan/RunTime/gateway.json`（推荐），"
            "或设置环境变量 `CLOUDOPS_APIGW_URL` / `CLOUDOPS_GATEWAY_KEY` / `CLOUDOPS_HW_APP_ID`（优先于 JSON）。",
            None,
        )
    return True, "", GatewayEnv(apigw_url=apigw_url, gateway_key=gateway_key, hw_app_id=hw_app_id)


def preflight_step8(skill_dir: str) -> tuple[bool, list[str]]:
    chain = load_chain(skill_dir)
    missing: list[str] = []
    if not str(chain.get("step6_cloudops_full_at") or "").strip():
        missing.append("缺少步骤 6 产物：请先完成 **CloudOps 完整配置**。")
    if not str(chain.get("step7_executor_config_at") or "").strip():
        missing.append("缺少步骤 7：请先 **设置调测设备（执行机 IP/SK）**。")
    ok_env, msg, _ = _load_gateway_config(skill_dir)
    if not ok_env:
        missing.append(msg)

    ex = load_executor_config(skill_dir)
    if not str(ex.get("base_url_ip") or "").strip():
        missing.append("执行机配置缺少 `base_url_ip`（步骤 7）。")
    if not str(ex.get("secret_key") or "").strip():
        missing.append("执行机配置缺少 `secret_key`（步骤 7）。")

    cfg = resolve_cloudops_full_path(skill_dir, chain)
    if not cfg.is_file():
        missing.append("未找到 `plan/Output/CloudOps完整配置文件.xlsx`（请先完成步骤 6）。")

    return len(missing) == 0, missing


@dataclass
class Step8Result:
    ok: bool
    message: str
    toolkit_imported: bool = False
    import_response: dict[str, Any] = field(default_factory=dict)
    refreshed_rows: int = 0
    refreshed_devices: int = 0
    checklist_used: str = ""
    logs: list[str] = field(default_factory=list)


def _read_install_checklist_pairs(path: Path) -> set[tuple[str, str]]:
    df = pd.read_excel(path, sheet_name=0, dtype=str).fillna("")
    cols = {str(c).strip(): c for c in df.columns}
    name_col = cols.get("设备名称") or cols.get("deviceName") or cols.get("device_name")
    esn_col = cols.get("ESN") or cols.get("esn") or cols.get("设备SN") or cols.get("SN") or cols.get("sn") or cols.get("序列号")
    if name_col is None or esn_col is None:
        return set()
    out: set[tuple[str, str]] = set()
    for _, row in df.iterrows():
        dn = str(row.get(name_col) or "").strip()
        esn = str(row.get(esn_col) or "").strip()
        if dn and esn:
            out.add((dn, esn))
    return out


def discover_install_checklist(skill_dir: str) -> Path | None:
    inbox = _cloudops_input_dir(skill_dir)
    if not inbox.is_dir():
        return None
    # 优先明确命名的清单
    candidates: list[Path] = []
    for pat in ("*设备安装完工清单*.xlsx", "*完工清单*.xlsx"):
        candidates.extend([Path(p) for p in inbox.glob(pat) if p.is_file() and not p.name.startswith("~$")])
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def refresh_base_table_init_status(
    *,
    skill_dir: str,
    install_checklist_path: Path,
    init_done_status: str = "INIT_DONE",
) -> tuple[int, int, str]:
    """
    9c：用 (设备名称, ESN) 对齐底表，UN_INIT → INIT_DONE，并重新导出宽表。
    返回 (refresh_rows, refresh_devices, checklist_name)。
    """
    out_dir = _output_dir(skill_dir)
    base_path = out_dir / "device_base_table.json"
    base = _load_json(base_path)
    tasks = base.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return (0, 0, install_checklist_path.name)

    pairs = _read_install_checklist_pairs(install_checklist_path)
    if not pairs:
        return (0, 0, install_checklist_path.name)

    refreshed_rows = 0
    refreshed_devices: set[str] = set()

    for row in tasks:
        if not isinstance(row, dict):
            continue
        dn = str(row.get("deviceName") or "").strip()
        # 底表当前无 ESN 字段，刷新只依赖“清单已提供该设备的 ESN”，即认为已完成初始化
        if not dn:
            continue
        if any(dn == p[0] for p in pairs):
            if str(row.get("taskStatus") or "").strip() in {"UN_INIT", "未初始化", ""}:
                row["taskStatus"] = init_done_status
                refreshed_rows += 1
                refreshed_devices.add(dn)

    if refreshed_rows:
        base["schemaVersion"] = int(base.get("schemaVersion") or 1)
        base["tasks"] = tasks
        _save_json(base_path, base)

        # 重新导出宽表
        from checklist_export import export_device_checklist_xlsx, load_scene, resolve_project_display_name  # noqa: WPS433

        scene = load_scene(_skill_root(skill_dir))
        display = resolve_project_display_name(scene=scene, skill_root=_skill_root(skill_dir))
        export_device_checklist_xlsx(
            device_tasks=[t for t in tasks if isinstance(t, dict)],
            scene=scene,
            output_dir=out_dir,
            project_display_name=display,
        )

    return (refreshed_rows, len(refreshed_devices), install_checklist_path.name)


def run_step8_import_and_refresh(
    *,
    skill_dir: str,
) -> Step8Result:
    logs: list[str] = []
    ok, missing = preflight_step8(skill_dir)
    if not ok:
        return Step8Result(ok=False, message="\n".join([f"- {m}" for m in missing]), logs=logs)

    chain = load_chain(skill_dir)
    ex = load_executor_config(skill_dir)
    ok_env, _, gw = _load_gateway_config(skill_dir)
    assert ok_env and gw is not None

    cfg_path = resolve_cloudops_full_path(skill_dir, chain)
    file_bytes = cfg_path.read_bytes()
    size_kb = len(file_bytes) // 1024
    logs.append(f"使用完整配置：{cfg_path}（约 {size_kb} KB）")
    from .cloudops_client import default_upload_timeout_s  # noqa: WPS433

    timeout_s = default_upload_timeout_s()
    logs.append(f"上传超时设置：{timeout_s}s（可用 CLOUDOPS_UPLOAD_TIMEOUT_S 调整）")
    client = CloudOpsClient(
        gateway=gw,
        base_url_ip=str(ex.get("base_url_ip") or ""),
        base_url_port=str(ex.get("base_url_port") or "28880"),
        secret_key=str(ex.get("secret_key") or ""),
        timeout_s=timeout_s,
    )

    try:
        resp = client.upload_config_file(file_bytes=file_bytes, filename=cfg_path.name)
    except Exception as e:
        hint = ""
        if "504" in str(e):
            hint = (
                "\n\n**排查建议**：504 为 APIGW/nginx 网关超时，不是本地脚本逻辑错误。"
                "文件较大或地端导入慢时常见；可隔几分钟重试，或让网关侧加大超时。"
                "也可用 workbench 包在同一环境试 `upload_config_file` 对比。"
            )
        return Step8Result(ok=False, message=f"Toolkit 导入失败：{e}{hint}", logs=logs)

    logs.append("Toolkit 导入完成。")

    checklist = discover_install_checklist(skill_dir)
    if not checklist:
        save_import_receipt(
            skill_dir=skill_dir,
            config_file=str(cfg_path.name),
            executor=ex,
            gateway=gw,
            import_response=resp if isinstance(resp, dict) else {},
            refresh={"skipped": True, "reason": "missing_install_checklist"},
        )
        return Step8Result(
            ok=True,
            message="Toolkit 导入完成；但未找到设备安装完工清单，跳过 9c 底表初始化刷新。",
            toolkit_imported=True,
            import_response=resp if isinstance(resp, dict) else {},
            logs=logs,
        )

    try:
        rows, devices, used = refresh_base_table_init_status(skill_dir=skill_dir, install_checklist_path=checklist)
    except Exception as e:
        save_import_receipt(
            skill_dir=skill_dir,
            config_file=str(cfg_path.name),
            executor=ex,
            gateway=gw,
            import_response=resp if isinstance(resp, dict) else {},
            refresh={"ok": False, "error": str(e), "checklist": str(checklist.name)},
        )
        return Step8Result(
            ok=False,
            message=f"Toolkit 导入完成，但 9c 底表刷新失败：{e}",
            toolkit_imported=True,
            import_response=resp if isinstance(resp, dict) else {},
            logs=logs,
        )

    msg = f"Toolkit 导入完成；9c 已刷新底表：{devices} 台设备、{rows} 行任务状态。"
    if rows == 0:
        msg = "Toolkit 导入完成；9c 未刷新任何行（可能清单缺列、或设备名称未匹配底表）。"

    status_summary = summarize_base_table_status(skill_dir)
    save_import_receipt(
        skill_dir=skill_dir,
        config_file=str(cfg_path.name),
        executor=ex,
        gateway=gw,
        import_response=resp if isinstance(resp, dict) else {},
        refresh={
            "ok": True,
            "rowsRefreshed": int(rows),
            "devicesRefreshed": int(devices),
            "checklist": str(used),
            "baseTableSummary": status_summary,
        },
    )

    return Step8Result(
        ok=True,
        message=msg,
        toolkit_imported=True,
        import_response=resp if isinstance(resp, dict) else {},
        refreshed_rows=rows,
        refreshed_devices=devices,
        checklist_used=used,
        logs=logs,
    )

