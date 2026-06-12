# -*- coding: utf-8 -*-
"""下发调测 · 通用执行引擎（三模块所有命令共用）。

骨架（与命令无关）：
    门禁 → 解析命令规格 → 解析设备范围 → 填请求体 → 下发 → 轮询 → 导出 → 统一存储+标签
命令差异全在「数据」：task_catalog 的一条 TaskSpec + 命令目录下的 config/{execute,query}.json。
driver 只调用 run_command(...)，加新命令不改本文件。
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve()
_COMMISSION_ROOT = _HERE.parents[3]          # .../9_commission
_SHARED = _COMMISSION_ROOT / "shared"


def _find_runtime_dir(start: Path) -> Path | None:
    for parent in start.parents:
        cand = parent / "runtime"
        if cand.is_dir() and (cand / "task_results.py").is_file():
            return cand
    return None


_RUNTIME_DIR = _find_runtime_dir(_HERE)
_TASK_RUNNER_ROOT = _SHARED / "task_runner"
for _p in (
    str(_SHARED / "device_scope" / "scripts"),
    str(_SHARED / "task_catalog" / "scripts"),
    str(_SHARED / "traffic_config" / "scripts"),
    str(_SHARED / "subsystem_params" / "scripts"),
    str(_TASK_RUNNER_ROOT),
    str(_TASK_RUNNER_ROOT / "hooks"),
    str(_TASK_RUNNER_ROOT / "parsers"),
    str(_RUNTIME_DIR) if _RUNTIME_DIR else "",
):
    if _p and _p not in sys.path:
        sys.path.insert(0, _p)

from device_resolver import resolve_devices  # noqa: E402
from task_catalog import TaskSpec, resolve_task  # noqa: E402
from toolkit_client import CloudOpsClientError, build_client, preflight_toolkit  # noqa: E402
from task_results import save_task_result  # noqa: E402
from traffic_config_builder import enrich_traffic_execute_body  # noqa: E402
from subsystem_params_builder import enrich_subsystem_execute_body  # noqa: E402

try:
    from collect_switch_info import CollectArtifact, collect_switch_info, merge_collect_xlsx  # noqa: E402
except ImportError:
    CollectArtifact = None  # type: ignore
    collect_switch_info = None  # type: ignore
    merge_collect_xlsx = None  # type: ignore

try:
    from hccs_weak_light_report import parse_report as parse_hccs_weak_light_report  # noqa: E402
except ImportError:
    parse_hccs_weak_light_report = None  # type: ignore

try:
    from check_all_devices_failed import check_all_devices_failed  # noqa: E402
except ImportError:
    check_all_devices_failed = None  # type: ignore

try:
    from lq_health_check_report import parse_report as parse_lq_health_check_report  # noqa: E402
except ImportError:
    parse_lq_health_check_report = None  # type: ignore

try:
    from lq_config_check_report import parse_report as parse_lq_config_check_report  # noqa: E402
except ImportError:
    parse_lq_config_check_report = None  # type: ignore

try:
    from paginate_node_results import paginate_node_results  # noqa: E402
except ImportError:
    paginate_node_results = None  # type: ignore

try:
    from params_loader import merge_template_id, preflight_cloudops_params  # noqa: E402
except ImportError:
    merge_template_id = None  # type: ignore
    preflight_cloudops_params = None  # type: ignore

try:
    from device_store import build_device_results, writeback_task_result  # noqa: E402
except ImportError:
    build_device_results = None  # type: ignore
    writeback_task_result = None  # type: ignore

_POST_POLL_HOOKS = {
    "collect_switch_info": collect_switch_info,
    "paginate_node_results": paginate_node_results,
}
_POST_POLL_ERROR_HOOKS = {
    "check_all_devices_failed": check_all_devices_failed,
}
_POST_EXPORT_HOOKS = {
    "merge_collect_xlsx": merge_collect_xlsx,
}
_REPORT_PARSERS = {
    "hccs_weak_light_report": parse_hccs_weak_light_report,
    "lq_health_check_report": parse_lq_health_check_report,
    "lq_config_check_report": parse_lq_config_check_report,
}


@dataclass
class RunResult:
    ok: bool
    message: str
    task_id: str = ""
    result_dir: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


def _skill_root(skill_dir: str | Path) -> Path:
    return Path(skill_dir).resolve()


def _load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _config_dir(spec: TaskSpec) -> Path:
    return _COMMISSION_ROOT / "commands" / spec.module / spec.config_dir / "config"


def _load_template(spec: TaskSpec, name: str) -> dict[str, Any]:
    data = _load_json(_config_dir(spec) / name)
    return data if isinstance(data, dict) else {}


def _scenario(skill_dir: str | Path) -> str:
    scene = _load_json(_skill_root(skill_dir) / "ProjectData" / "plan" / "RunTime" / "scene.json")
    val = ""
    if isinstance(scene, dict):
        val = str(scene.get("train_infer_scene") or scene.get("trainInferScene") or "").strip()
    return "inferenceServer" if val == "infer" else "trainingServer"


def _resolve_ztp(skill_dir: str | Path) -> tuple[bytes, str, str]:
    root = _skill_root(skill_dir)
    chain = _load_json(root / "ProjectData" / "plan" / "RunTime" / "deploy_chain.json")
    candidates: list[Path] = []
    if isinstance(chain, dict):
        for key in ("step6_ztp_path", "step7_ztp_path"):
            rel = str(chain.get(key) or "").strip()
            if rel:
                p = Path(rel)
                candidates.append(p if p.is_absolute() else root / p)
    candidates.append(root / "ProjectData" / "input" / "cloudops" / "ZTP文件_latest.zip")
    input_dir = root / "ProjectData" / "input" / "cloudops"
    if input_dir.is_dir():
        candidates.extend(sorted(input_dir.glob("ZTP*.zip"), key=lambda p: p.stat().st_mtime, reverse=True))

    seen: set[Path] = set()
    for path in candidates:
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        if resolved in seen:
            continue
        seen.add(resolved)
        if path.is_file():
            return path.read_bytes(), path.name, str(path)
    raise FileNotFoundError(
        "请先完成步骤 6 材料检查并上传 ZTP，或放置 `ProjectData/input/cloudops/ZTP*.zip`。"
    )


def _report_suffix(spec: TaskSpec) -> str:
    if spec.export_suffix:
        return spec.export_suffix
    fmt = str(spec.export_format or "zip").strip()
    return fmt if fmt else "zip"


_ASCEND_POLL_STEPS = (
    "executeAscendInstall",
    "executeRestartServer",
    "npuParamNetConfig",
    "hcclClusterInfoCollectPortConfig",
    "configInfoCollection",
)


def _int_field(data: dict[str, Any], *keys: str, default: int = 999) -> int:
    for key in keys:
        if key in data and data[key] is not None:
            return int(data[key])
    return default


def _build_execute_body(skill_dir: str | Path, spec: TaskSpec, ips: list[str], task_name: str) -> dict[str, Any]:
    body = _load_template(spec, spec.execute_template) or {}
    if not spec.omit_task_name:
        body["taskName"] = task_name
    if "scenario" in body:
        body["scenario"] = _scenario(skill_dir)
    body[spec.device_field] = list(ips)
    return body


def _task_finished(data: Any, *, rule: str = "") -> bool:
    if not isinstance(data, dict):
        return False
    if rule == "report_end_only":
        return bool(data.get("reportEnd"))
    if rule == "lq_config_check":
        total = int(data.get("totalNums") or 0)
        processing_raw = data.get("processingNum")
        if processing_raw is None:
            processing_raw = data.get("processingCount")
        processing = int(processing_raw or 0) if processing_raw is not None else 0
        waiting_raw = data.get("waitingNum")
        waiting = int(waiting_raw or 0) if waiting_raw is not None else 0
        return total > 0 and processing == 0 and waiting == 0 and bool(data.get("reportEnd", True))
    if not data.get("reportEnd"):
        return False
    processing = _int_field(data, "processingNum", "processingCount", default=0)
    waiting = _int_field(data, "waitingNum", default=0)
    return processing == 0 and waiting == 0


def _task_finished_ascend(data: Any) -> bool:
    if not isinstance(data, list):
        return False
    by_step: dict[str, dict[str, Any]] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        step = str(item.get("stepName") or "").strip()
        if step:
            by_step[step] = item
    for step in _ASCEND_POLL_STEPS:
        row = by_step.get(step)
        if row is None:
            return False
        if int(row.get("processingNum") or 0) != 0:
            return False
        if int(row.get("pendingNum") or 0) != 0:
            return False
    return True


def _task_finished_traffic_array(data: Any) -> bool:
    if not isinstance(data, list):
        return False
    if not data:
        return False
    return all(str(item.get("optResult") or "") != "0" for item in data if isinstance(item, dict))


def _task_finished_hccl_count(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    processing = _int_field(data, "processingCount", "processingNum")
    end_nums = _int_field(data, "endCount", default=0)
    success_nums = _int_field(data, "successCount", default=0)
    failed_nums = _int_field(data, "failedCount", default=0)
    node_nums = _int_field(data, "nodeCount", default=0)
    if processing == 0:
        return True
    if node_nums > 0 and (end_nums + success_nums + failed_nums) == node_nums:
        return True
    return False


def _task_finished_cluster_train(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    if data.get("reportEnd"):
        return _task_finished(data)
    result_data = data.get("resultData")
    if isinstance(result_data, dict):
        if _int_field(result_data, "processingNum", "processingCount") == 0:
            return True
    return _task_finished(data)


_PRBS_ACTIVE_STATES = frozenset(
    {"Starting", "Stress testing", "Collecting Result", "Stopping", "Recovering"}
)


def _prbs_stress_list_done(data: dict[str, Any]) -> bool:
    items = data.get("listData")
    if not isinstance(items, list) or not items:
        return True
    for item in items:
        if not isinstance(item, dict):
            continue
        state = item.get("stressTestState")
        if state and state in _PRBS_ACTIVE_STATES:
            return False
    return True


def _poll_step_finished(spec: TaskSpec, data: Any, *, step_name: str) -> bool:
    if not isinstance(data, dict):
        return False
    processing = _int_field(data, "processingNum", "processingCount")
    waiting = _int_field(data, "waitingNum", default=0)
    if processing != 0 or waiting != 0:
        return False
    if step_name == "prbsStressTest" and not _prbs_stress_list_done(data):
        return False
    return True


def _poll_prbs_multi_step(
    client: Any,
    spec: TaskSpec,
    task_id: str,
    poll_interval: int,
) -> tuple[bool, dict[str, Any]]:
    steps = (
        ("query_select_nodes.json", "selectNodes", 20),
        ("query_prbs_stress.json", "prbsStressTest", spec.poll_max),
        ("query_recover.json", "recoverDevice", 60),
    )
    last_payload: dict[str, Any] = {}
    for template_name, step_name, max_attempts in steps:
        query_tmpl = _load_template(spec, template_name) or _load_template(spec, spec.query_template) or {}
        for _ in range(max_attempts):
            query_body = dict(query_tmpl)
            query_body["taskId"] = task_id
            if "stepName" not in query_body:
                query_body["stepName"] = step_name
            payload = client.query_task(work_stage=spec.work_stage, body=query_body)
            last_payload = payload
            if _poll_step_finished(spec, payload.get("data"), step_name=step_name):
                break
            time.sleep(poll_interval)
        else:
            return False, last_payload
        time.sleep(poll_interval)
    return True, last_payload


def _task_finished_for_spec(spec: TaskSpec, data: Any) -> bool:
    if spec.poll_mode == "ascend_multi_step":
        return _task_finished_ascend(data)
    if spec.poll_mode == "traffic_array":
        return _task_finished_traffic_array(data)
    if spec.poll_mode == "hccl_count":
        return _task_finished_hccl_count(data)
    if spec.poll_mode == "cluster_train":
        return _task_finished_cluster_train(data)
    return _task_finished(data, rule=spec.poll_finished_rule)


def _poll_data_finished(spec: TaskSpec, data: Any) -> bool:
    if spec.poll_mode:
        return _task_finished_for_spec(spec, data)
    return _task_finished(data, rule=spec.poll_finished_rule)


def _export_report_bytes(client: Any, spec: TaskSpec, task_id: str) -> bytes:
    if spec.export_mode == "health_report_list":
        report_time = client.query_report_history(
            work_stage=spec.work_stage,
            task_id=task_id,
            check_type="server",
        )
        if not report_time:
            raise CloudOpsClientError("健康检查 ReportQuery 未返回 createTime，无法导出")
        return client.export_report(
            work_stage=spec.work_stage,
            task_id=task_id,
            report_list=[report_time],
        )
    return client.export_report(work_stage=spec.work_stage, task_id=task_id)


def run_command(
    skill_dir: str | Path,
    command: str,
    *,
    scope: str = "all",
    pod_ids: list[int] | None = None,
    devices: list[str] | None = None,
    task_no: str = "",
    only_installed: bool = True,
) -> RunResult:
    spec = resolve_task(command)
    if spec is None:
        return RunResult(ok=False, message=f"未识别命令：{command}")
    if not spec.implemented:
        return RunResult(
            ok=False,
            message=f"命令「{spec.labels[0]}」尚未接入（留位）。补 config/{spec.execute_template} 与 SKILL.md 后启用。",
        )

    ok, missing = preflight_toolkit(skill_dir)
    if not ok:
        return RunResult(ok=False, message="；".join(missing))

    if spec.require_cloudops_params:
        if preflight_cloudops_params is None:
            return RunResult(ok=False, message="引擎缺少 preflight_cloudops_params，无法执行本命令。")
        ok_params, msg_params = preflight_cloudops_params(skill_dir, sheet=spec.params_sheet)
        if not ok_params:
            return RunResult(ok=False, message=msg_params)

    rr = resolve_devices(
        skill_dir,
        scope=scope,
        pod_ids=pod_ids,
        devices=devices,
        task_no=task_no,
        only_installed=only_installed,
        device_kind=spec.device_kind,
        task_type=spec.task_type,
    )
    if not rr.ok:
        return RunResult(ok=False, message=f"设备范围解析失败：{rr.message}")

    poll_max = int(os.environ.get("CLOUDOPS_POLL_MAX") or spec.poll_max)
    poll_interval = int(os.environ.get("CLOUDOPS_POLL_INTERVAL_S") or spec.poll_interval_s)
    report_wait = int(os.environ.get("CLOUDOPS_REPORT_WAIT_S") or spec.report_wait_s)

    try:
        client = build_client(skill_dir)
    except CloudOpsClientError as e:
        return RunResult(ok=False, message=str(e))

    task_name = f"{spec.task_type}_{int(time.time())}"
    body = _build_execute_body(skill_dir, spec, rr.ips, task_name)
    if spec.params_sheet and merge_template_id is not None:
        body = merge_template_id(body, skill_dir, sheet=spec.params_sheet)
    if spec.task_type == "traffic_test":
        body = enrich_traffic_execute_body(skill_dir, body, devices=rr.devices, ips=rr.ips)
        if not body.get("trafficTestConfigs"):
            return RunResult(
                ok=False,
                message="打流测试 trafficTestConfigs 为空：请确认 CloudOps《服务器信息》含管理网 IP，且设备数≥2（跨节点打流）",
            )
    elif spec.task_type in (
        "hccl_test_single_pod",
        "hccl_test",
        "cluster_train_single_pod",
        "cluster_infer_single_pod",
    ):
        body = enrich_subsystem_execute_body(
            skill_dir, spec.task_type, body, device_count=len(rr.ips)
        )
        hccl_ifname = (body.get("hcclBaseParam") or {}).get("hcclSocketIfname")
        if spec.task_type in ("hccl_test_single_pod", "hccl_test") and not str(hccl_ifname or "").strip():
            return RunResult(ok=False, message="HCCL hcclSocketIfname 为空：请检查参数页签「集合通信」HCCL_SOCKET_IFNAME")

    ztp_info: tuple[bytes, str, str] | None = None
    if spec.create_mode == "multipart_ztp":
        try:
            ztp_info = _resolve_ztp(skill_dir)
        except FileNotFoundError as e:
            return RunResult(ok=False, message=str(e))

    try:
        if spec.create_mode == "multipart_ztp":
            if ztp_info is None:
                return RunResult(ok=False, message="未解析到 ZTP 文件。")
            ztp_bytes, ztp_name, _ztp_path = ztp_info
            task_id = client.create_task_multipart_ztp(
                work_stage=spec.work_stage,
                config_check_req=body,
                ztp_bytes=ztp_bytes,
                ztp_filename=ztp_name,
            )
        else:
            task_id = client.create_task(work_stage=spec.work_stage, body=body)
    except CloudOpsClientError as e:
        return RunResult(ok=False, message=f"任务下发失败：{e}")

    dispatch_only = str(os.environ.get("CLOUDOPS_DISPATCH_ONLY") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if dispatch_only:
        detail = {
            "taskId": task_id,
            "taskName": task_name,
            "module": spec.module,
            "deviceCount": len(rr.ips),
            "source": rr.source,
            "dispatchOnly": True,
        }
        return RunResult(
            ok=True,
            message=(
                f"✅ {spec.labels[0]} 已下发至执行机\n"
                f"- UI任务名称：`{task_name}`（Toolkit 列表搜这个）\n"
                f"- 后端 taskId：`{task_id}`\n"
                f"- 设备：**{len(rr.ips)} 台**（{rr.source}）\n"
                f"- 模式：dispatch_only（未轮询/未导出）"
            ),
            task_id=task_id,
            detail=detail,
        )

    finished = False
    last_payload: dict[str, Any] = {}
    try:
        if spec.poll_mode == "prbs_multi_step":
            time.sleep(poll_interval)
            finished, last_payload = _poll_prbs_multi_step(client, spec, task_id, poll_interval)
        else:
            query_tmpl = _load_template(spec, spec.query_template) or {}
            for _ in range(poll_max):
                query_body = dict(query_tmpl)
                query_body["taskId"] = task_id
                payload = client.query_task(work_stage=spec.work_stage, body=query_body)
                last_payload = payload
                if _poll_data_finished(spec, payload.get("data")):
                    finished = True
                    break
                time.sleep(poll_interval)
    except CloudOpsClientError as e:
        return RunResult(ok=False, message=f"轮询失败：{e}", task_id=task_id)

    if not finished:
        mode_hint = spec.poll_mode or spec.poll_finished_rule or "default"
        return RunResult(
            ok=False,
            message=f"轮询超时（mode={mode_hint}，{poll_max}×{poll_interval}s），taskId={task_id}",
            task_id=task_id,
        )

    poll_err_fn = _POST_POLL_ERROR_HOOKS.get(spec.post_poll_hook or "")
    if poll_err_fn:
        err = poll_err_fn(last_payload)
        if err:
            return RunResult(ok=False, message=err, task_id=task_id)

    artifact = None
    poll_fn = _POST_POLL_HOOKS.get(spec.post_poll_hook or "")
    if poll_fn:
        try:
            if spec.post_poll_hook == "paginate_node_results":
                query_tmpl = _load_template(spec, spec.query_template) or {}
                artifact = poll_fn(
                    client=client,
                    work_stage=spec.work_stage,
                    task_id=task_id,
                    query_template=query_tmpl,
                    device_count=len(rr.ips),
                )
            else:
                artifact = poll_fn(last_payload)
        except CloudOpsClientError as e:
            return RunResult(ok=False, message=f"节点结果分页查询失败：{e}", task_id=task_id)

    time.sleep(max(0, report_wait))
    try:
        report_bytes = _export_report_bytes(client, spec, task_id)
    except CloudOpsClientError as e:
        return RunResult(ok=False, message=f"报告导出失败：{e}", task_id=task_id)

    export_fn = _POST_EXPORT_HOOKS.get(spec.post_export_hook or "")
    if export_fn and artifact is not None:
        report_bytes = export_fn(report_bytes, artifact)

    parsed = None
    parser_fn = _REPORT_PARSERS.get(spec.report_parser or "")
    if parser_fn:
        parsed = parser_fn(report_bytes, artifact)

    report_ext = _report_suffix(spec)
    saved = save_task_result(
        skill_dir=skill_dir,
        task_type=spec.task_type,
        task_name=task_name,
        task_id=task_id,
        work_stage=spec.work_stage,
        execute_body=body,
        last_query=last_payload,
        report_bytes=report_bytes,
        report_filename=f"report.{report_ext}",
        parsed_result=parsed,
        extract_zip=report_ext == "zip",
        extra={
            "module": spec.module,
            "scope": scope,
            "deviceSource": rr.source,
            "podIds": rr.pod_ids,
            "deviceCount": len(rr.ips),
            "deviceIps": rr.ips,
            "ztpSource": ztp_info[2] if ztp_info else "",
        },
    )

    raw_data = last_payload.get("data")
    data = raw_data if isinstance(raw_data, dict) else {}

    # 回写设备底表 taskStatus（对标 Agent status_manager.update_task_status）。
    # 失败不阻断主流程——调测已成功，回写仅刷新底表/宽表展示。
    writeback: dict[str, Any] = {}
    if build_device_results is not None and writeback_task_result is not None:
        try:
            device_results, decision = build_device_results(
                task_type=spec.task_type,
                ips=rr.ips,
                last_query=last_payload,
                parsed=parsed,
                ok=True,
            )
            writeback = writeback_task_result(
                skill_dir=skill_dir,
                task_type=spec.task_type,
                device_results=device_results,
            )
            writeback["decision"] = decision
        except Exception as e:  # noqa: BLE001
            writeback = {"error": str(e)}

    detail = {
        "taskId": task_id,
        "taskName": task_name,
        "module": spec.module,
        "deviceCount": len(rr.ips),
        "source": rr.source,
        "successNum": data.get("successNum"),
        "failNum": data.get("failNum"),
        "resultDir": str(saved.dir),
        "writeback": writeback,
    }
    return RunResult(
        ok=True,
        message=_format_result(spec, rr, detail, data, artifact=artifact, parsed=parsed),
        task_id=task_id,
        result_dir=str(saved.dir),
        detail=detail,
    )


def _writeback_line(detail: dict[str, Any]) -> str:
    """把底表回写摘要渲染成一行（无回写或被跳过则返回空串）。"""
    wb = detail.get("writeback")
    if not isinstance(wb, dict) or not wb:
        return ""
    if wb.get("error"):
        return f"- 底表回写：⚠️ 失败（{wb['error']}）"
    if wb.get("skipped"):
        return f"- 底表回写：跳过（{wb['skipped']}）"
    rows = wb.get("rowsUpdated", 0)
    matched = wb.get("devicesMatched", 0)
    unmatched = wb.get("devicesUnmatched", 0)
    by = wb.get("byStatus") or {}
    by_txt = "、".join(f"{k} {v}" for k, v in by.items()) if by else ""
    line = f"- 底表回写：更新 **{rows}** 行（匹配 {matched} 台"
    if by_txt:
        line += f"：{by_txt}"
    line += "）"
    if unmatched:
        line += f"；**{unmatched}** 台未落底表（IP 与底表不一致）"
    if not wb.get("checklistReexported") and rows:
        line += "；宽表未重导"
    return line


def _format_result(
    spec: TaskSpec,
    rr,
    detail: dict[str, Any],
    data: dict[str, Any],
    *,
    artifact=None,
    parsed: dict[str, Any] | None = None,
) -> str:
    if spec.result_message == "dual" and artifact is not None:
        lines = [
            f"✅ {spec.labels[0]} 完成",
            f"- 任务号：`{detail['taskId']}`",
            f"- 设备范围：**{detail['deviceCount']} 台**（来源：{rr.source}）",
        ]
        if rr.pod_ids:
            lines.append(f"- POD：{rr.pod_ids}")
        if rr.message:
            lines.append(f"- 备注：{rr.message}")
        lines.append(f"- 结果目录：`{detail['resultDir']}`")
        md = getattr(artifact, "markdown", "") or ""
        if md:
            lines.append("")
            lines.append(md)
        if isinstance(parsed, dict):
            sheet_counts = parsed.get("sheetCounts") or {}
            if sheet_counts:
                lines.append("")
                lines.append("### 光链路报告摘要（前 3 Sheet 行数）")
                for name, count in sheet_counts.items():
                    lines.append(f"- {name}：**{count}** 条")
            report_file = parsed.get("reportFile")
            if report_file:
                lines.append(f"- 报告文件：`{report_file}`")
        wb_line = _writeback_line(detail)
        if wb_line:
            lines.append(wb_line)
        return "\n".join(lines)

    if spec.result_message == "markdown":
        lines = [
            f"✅ {spec.labels[0]} 完成",
            f"- 任务号：`{detail['taskId']}`",
            f"- 设备范围：**{detail['deviceCount']} 台**（来源：{rr.source}）",
        ]
        if rr.pod_ids:
            lines.append(f"- POD：{rr.pod_ids}")
        succ = data.get("successNum")
        fail = data.get("failNum")
        if succ is not None or fail is not None:
            lines.append(f"- 结果：通过 {succ if succ is not None else '?'} / 失败 {fail if fail is not None else '?'}")
        if rr.message:
            lines.append(f"- 备注：{rr.message}")
        report_name = f"report.{_report_suffix(spec)}"
        lines.append(f"- 结果目录：`{detail['resultDir']}`（{report_name} + receipt.json）")
        if isinstance(parsed, dict):
            report_file = parsed.get("reportFile")
            if report_file:
                lines.append(f"- 报告文件：`{report_file}`")
            md = parsed.get("markdown") or ""
            if md:
                lines.append("")
                lines.append(md)
        wb_line = _writeback_line(detail)
        if wb_line:
            lines.append(wb_line)
        return "\n".join(lines)

    lines = [
        f"✅ {spec.labels[0]} 完成",
        f"- 任务号：`{detail['taskId']}`",
        f"- 设备范围：**{detail['deviceCount']} 台**（来源：{rr.source}）",
    ]
    if rr.pod_ids:
        lines.append(f"- POD：{rr.pod_ids}")
    succ = data.get("successNum")
    fail = data.get("failNum")
    if succ is not None or fail is not None:
        lines.append(f"- 结果：通过 {succ if succ is not None else '?'} / 失败 {fail if fail is not None else '?'}")
    if rr.message:
        lines.append(f"- 备注：{rr.message}")
    report_name = f"report.{_report_suffix(spec)}"
    lines.append(f"- 结果目录：`{detail['resultDir']}`（{report_name} + receipt.json）")
    if rr.devices:
        lines.append("")
        lines.append("设备清单（前 20）：")
        for d in rr.devices[:20]:
            tag = "已初始化" if d.installed else "未初始化"
            pod = f" POD{d.pod_id}" if d.pod_id else ""
            nm = f" {d.name}" if d.name else ""
            lines.append(f"  - {d.ip}{nm}{pod} · {tag}")
        if len(rr.devices) > 20:
            lines.append(f"  - …共 {len(rr.devices)} 台")
    wb_line = _writeback_line(detail)
    if wb_line:
        lines.append(wb_line)
    return "\n".join(lines)
