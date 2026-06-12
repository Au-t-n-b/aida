# -*- coding: utf-8 -*-
"""下发调测 · 公共设备范围解析：结构化意图 → 设备 IP 列表（三模块共用）。

意图（由 LLM 层从单条命令解析后传入，见 shared/device_scope/SKILL.md）：
    scope: all | pod | exclude | include | param_file | prev_failed | prev_passed | prev_same
    pod_ids: list[int]          # POD 过滤（superpodId）
    devices: list[str]          # exclude/include 的设备（IP 或设备名）
    task_no: str                # prev_* / prev_same：上次任务号（taskId 或 taskName）
    only_installed: bool        # 与「已初始化(已装)」设备取交集

设备来源由命令规格的 device_kind 决定：
    server → 设备底表 device_base_table.json ∩ 完整配置《服务器信息》
    switch → CloudOps 完整配置《交换机信息》表 + 底表 superpodId（按 IP 合并，对齐 Agent SUPERPOD_ID）
server 双重门禁（对齐 Agent）：
    ① taskStatus != 未初始化（完工清单刷过 INIT；query_all_devices，兼容中英文状态）
    ② IP ∈ 完整配置《服务器信息》《交换机信息》第0列（compare_with_cloudops_config，确保已导入 ops）
    读不到完整配置则跳过 ②，不误杀。
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _find_runtime_dir(start: Path) -> Path | None:
    for parent in start.resolve().parents:
        cand = parent / "runtime"
        if cand.is_dir() and (cand / "task_results.py").is_file():
            return cand
    return None


_RUNTIME_DIR = _find_runtime_dir(Path(__file__))
if _RUNTIME_DIR and str(_RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNTIME_DIR))

try:
    from task_results import latest_run, results_root  # noqa: E402
except Exception:  # pragma: no cover
    latest_run = None  # type: ignore
    results_root = None  # type: ignore

# 「已装/可测」判定对齐 Agent：query_all_devices 的 SQL 为 `TASK_STATUS != '未初始化'`，
# 即只要不是未初始化（含已完成初始化、执行中、已完成、未通过…）即视为可下发测试。
# 用黑名单而非白名单，避免回写后状态变「未通过」的设备被错误排除在后续命令之外。
# 同时兼容英文（9c 写 INIT_DONE/UN_INIT）与中文（回写写 TaskStatus 中文值）两套状态。
UNINSTALLED_STATUSES = {"UN_INIT", "未初始化", "PENDING_DISPATCHED", "待派发", ""}
PASS_TOKENS = {"pass", "通过", "success", "ok", "正常"}
FAIL_TOKENS = {"fail", "失败", "未通过", "error", "异常", "execute_fail"}

VALID_SCOPES = {
    "all",
    "pod",
    "exclude",
    "include",
    "param_file",
    "prev_failed",
    "prev_passed",
    "prev_same",
}


@dataclass
class Device:
    ip: str
    name: str = ""
    pod_id: int = 0
    installed: bool = False


@dataclass
class ResolveResult:
    ok: bool
    ips: list[str] = field(default_factory=list)
    devices: list[Device] = field(default_factory=list)
    source: str = ""
    message: str = ""
    pod_ids: list[int] = field(default_factory=list)
    task_no: str = ""


def _skill_root(skill_dir: str | Path) -> Path:
    return Path(skill_dir).resolve()


def _load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_base_devices(skill_dir: str | Path) -> list[Device]:
    """底表去重到设备维度：同 IP 多行（多三级任务），只要有一行已初始化即视为已装。"""
    base = _load_json(_skill_root(skill_dir) / "ProjectData" / "plan" / "Output" / "device_base_table.json")
    rows = base.get("tasks") if isinstance(base, dict) else None
    if not isinstance(rows, list):
        return []
    by_ip: dict[str, Device] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ip = str(row.get("deviceIp") or "").strip()
        if not ip:
            continue
        name = str(row.get("deviceName") or "").strip()
        try:
            pod = int(row.get("superpodId") or 0)
        except (TypeError, ValueError):
            pod = 0
        status = str(row.get("taskStatus") or "").strip()
        installed = status.upper() not in UNINSTALLED_STATUSES and status not in UNINSTALLED_STATUSES
        if ip not in by_ip:
            by_ip[ip] = Device(ip=ip, name=name, pod_id=pod, installed=installed)
        else:
            dev = by_ip[ip]
            if installed:
                dev.installed = True
            if not dev.name and name:
                dev.name = name
    return list(by_ip.values())


def _superpod_by_ip_from_base(skill_dir: str | Path) -> dict[str, int]:
    """底表按 IP 取 superpodId（对齐 Agent 设备底表 SUPERPOD_ID）。"""
    base = _load_json(_skill_root(skill_dir) / "ProjectData" / "plan" / "Output" / "device_base_table.json")
    rows = base.get("tasks") if isinstance(base, dict) else None
    if not isinstance(rows, list):
        return {}
    out: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ip = str(row.get("deviceIp") or "").strip()
        if not ip:
            continue
        try:
            pod = int(row.get("superpodId") or 0)
        except (TypeError, ValueError):
            pod = 0
        if pod and (ip not in out or not out[ip]):
            out[ip] = pod
        elif ip not in out:
            out[ip] = pod
    return out


def _full_config_path(skill_dir: str | Path) -> Path:
    root = _skill_root(skill_dir)
    chain = _load_json(root / "ProjectData" / "plan" / "RunTime" / "deploy_chain.json")
    prefer = ""
    if isinstance(chain, dict):
        prefer = str(chain.get("step6_cloudops_full_path") or "").strip().replace("\\", "/")
    if prefer:
        ws_root = root.parent.parent  # workspace 根（skills 的上两级）
        rel = prefer[len("workspace/"):] if prefer.startswith("workspace/") else prefer.lstrip("/")
        cand = (ws_root / rel).resolve()
        if cand.is_file():
            return cand
    return root / "ProjectData" / "plan" / "Output" / "CloudOps完整配置文件.xlsx"


def load_switch_devices(skill_dir: str | Path) -> list[Device]:
    """从完整配置《交换机信息》读交换机；pod_id 按 IP 合并底表 superpodId（scope=pod 用）。"""
    try:
        from openpyxl import load_workbook
    except Exception:
        return []
    path = _full_config_path(skill_dir)
    if not path.is_file():
        return []
    try:
        wb = load_workbook(filename=str(path), read_only=True, data_only=True)
    except Exception:
        return []
    try:
        sheet_name = None
        for cand in ("交换机信息", "灵衢交换机信息"):
            if cand in wb.sheetnames:
                sheet_name = cand
                break
        if not sheet_name:
            return []
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        header = [str(c or "").strip() for c in rows[0]]
        idx = {name: i for i, name in enumerate(header) if name}

        def col(*names: str) -> int:
            for n in names:
                if n in idx:
                    return idx[n]
            return -1

        ip_i = col("设备IP", "管理网IP", "设备ID*（主键）")
        name_i = col("设备名称")
        user_i = col("管理网用户名", "用户名")
        pwd_i = col("密码")
        pod_by_ip = _superpod_by_ip_from_base(skill_dir)
        by_ip: dict[str, Device] = {}
        for r in rows[1:]:
            vals = list(r)
            if ip_i < 0 or ip_i >= len(vals):
                continue
            ip = str(vals[ip_i] or "").strip()
            if not ip:
                continue
            name = str(vals[name_i] or "").strip() if 0 <= name_i < len(vals) else ""
            user = str(vals[user_i] or "").strip() if 0 <= user_i < len(vals) else ""
            pwd = str(vals[pwd_i] or "").strip() if 0 <= pwd_i < len(vals) else ""
            installed = bool(user and pwd)
            pod_id = pod_by_ip.get(ip, 0)
            if ip not in by_ip:
                by_ip[ip] = Device(ip=ip, name=name, pod_id=pod_id, installed=installed)
        return list(by_ip.values())
    finally:
        wb.close()


def load_full_config_device_ids(skill_dir: str | Path) -> set[str]:
    """读完整配置《服务器信息》《交换机信息》第 0 列（设备ID*（主键）= IP）。

    对齐 Agent ``device_manager.compare_with_cloudops_config``：该集合 = ops 实际已导入
    可下发的设备。返回空集表示「读不到完整配置」——调用方据此决定是否跳过门禁（不误杀）。
    """
    try:
        from openpyxl import load_workbook
    except Exception:
        return set()
    path = _full_config_path(skill_dir)
    if not path.is_file():
        return set()
    try:
        wb = load_workbook(filename=str(path), read_only=True, data_only=True)
    except Exception:
        return set()
    ids: set[str] = set()
    try:
        for sheet_name in ("服务器信息", "交换机信息"):
            if sheet_name not in wb.sheetnames:
                continue
            ws = wb[sheet_name]
            first = True
            for row in ws.iter_rows(values_only=True):
                if first:  # 跳过表头
                    first = False
                    continue
                if not row:
                    continue
                val = str(row[0] or "").strip()  # 第 0 列 = 设备ID*（主键）
                if val:
                    ids.add(val)
    finally:
        wb.close()
    return ids


def _match(dev: Device, token: str) -> bool:
    t = str(token or "").strip()
    return bool(t) and (t == dev.ip or t == dev.name)


def _filter_pod(devices: list[Device], pod_ids: list[int]) -> list[Device]:
    if not pod_ids:
        return devices
    want = set(pod_ids)
    return [d for d in devices if d.pod_id in want]


def _load_prev_result_devices(
    skill_dir: str | Path,
    task_no: str,
    *,
    task_type: str = "",
) -> tuple[list[str], list[str], str]:
    """返回 (通过IP, 失败IP, 命中的任务名)。任务号匹配 taskId 或 taskName；空则取最近一次。"""
    if results_root is None:
        return [], [], ""
    idx = _load_json(results_root(skill_dir) / "index.json")
    runs = idx.get("runs") if isinstance(idx, dict) else None
    if not isinstance(runs, list):
        return [], [], ""
    target = None
    tn = str(task_no or "").strip()
    tt = str(task_type or "").strip()
    for entry in reversed(runs):
        if not isinstance(entry, dict):
            continue
        if tt and str(entry.get("taskType") or "") != tt:
            continue
        if not tn or entry.get("taskId") == tn or entry.get("taskName") == tn:
            target = entry
            break
    if target is None:
        return [], [], ""
    result_path = str(target.get("resultPath") or "").strip()
    passed: list[str] = []
    failed: list[str] = []
    parsed = _load_json(Path(result_path)) if result_path else None
    if isinstance(parsed, dict):
        devices = parsed.get("devices")
        if isinstance(devices, list):
            for item in devices:
                if not isinstance(item, dict):
                    continue
                ip = str(item.get("ip") or item.get("deviceIp") or item.get("bmc_ip") or "").strip()
                if not ip:
                    continue
                res = str(item.get("result") or item.get("Result") or "").strip().lower()
                collect_ok = item.get("collectOk")
                if collect_ok is True or res in PASS_TOKENS:
                    passed.append(ip)
                elif collect_ok is False or res in FAIL_TOKENS:
                    failed.append(ip)
                else:
                    passed.append(ip)
    elif isinstance(parsed, list):
        for item in parsed:
            if not isinstance(item, dict):
                continue
            ip = str(item.get("bmc_ip") or item.get("deviceIp") or item.get("ip") or "").strip()
            if not ip:
                continue
            res = str(item.get("Result") or item.get("result") or "").strip().lower()
            if res in PASS_TOKENS:
                passed.append(ip)
            elif res in FAIL_TOKENS:
                failed.append(ip)
            else:
                err = item.get("ConnectionError") or item.get("failNum") or 0
                (failed if _to_int(err) > 0 else passed).append(ip)
    return passed, failed, str(target.get("taskName") or target.get("taskId") or "")


def _load_prev_range(
    skill_dir: str | Path,
    task_no: str,
    *,
    task_type: str = "",
) -> tuple[list[str], str]:
    """上次任务设定的设备范围：读 receipt.executeBody 的设备字段。"""
    if results_root is None:
        return [], ""
    idx = _load_json(results_root(skill_dir) / "index.json")
    runs = idx.get("runs") if isinstance(idx, dict) else None
    if not isinstance(runs, list):
        return [], ""
    tn = str(task_no or "").strip()
    tt = str(task_type or "").strip()
    for entry in reversed(runs):
        if not isinstance(entry, dict):
            continue
        if tt and str(entry.get("taskType") or "") != tt:
            continue
        if not tn or entry.get("taskId") == tn or entry.get("taskName") == tn:
            receipt = _load_json(Path(str(entry.get("receiptPath") or "")))
            body = receipt.get("executeBody") if isinstance(receipt, dict) else {}
            ids: list[str] = []
            if isinstance(body, dict):
                for fld in ("serviceDeviceIds", "switchesDeviceIds", "deviceIds"):
                    val = body.get(fld)
                    if isinstance(val, list):
                        ids.extend(str(x).strip() for x in val if str(x).strip())
            return ids, str(entry.get("taskName") or entry.get("taskId") or "")
    return [], ""


def _to_int(v: Any) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _param_file_devices(skill_dir: str | Path) -> list[str]:
    """参数文件指定设备（best-effort）：读 RunTime/param_devices.json 的 deviceIds。"""
    p = _skill_root(skill_dir) / "ProjectData" / "plan" / "RunTime" / "param_devices.json"
    data = _load_json(p)
    if isinstance(data, dict):
        ids = data.get("deviceIds") or data.get("devices")
        if isinstance(ids, list):
            return [str(x).strip() for x in ids if str(x).strip()]
    return []


def resolve_devices(
    skill_dir: str | Path,
    *,
    scope: str = "all",
    pod_ids: list[int] | None = None,
    devices: list[str] | None = None,
    task_no: str = "",
    only_installed: bool = True,
    device_kind: str = "server",
    task_type: str = "",
) -> ResolveResult:
    scope = str(scope or "all").strip()
    device_kind = str(device_kind or "server").strip()
    pod_ids = [int(p) for p in (pod_ids or []) if str(p).strip() != ""]
    devices = [str(d).strip() for d in (devices or []) if str(d).strip()]

    if scope not in VALID_SCOPES:
        return ResolveResult(ok=False, message=f"未知 scope: {scope}（可选 {sorted(VALID_SCOPES)}）")

    if device_kind == "switch":
        base = load_switch_devices(skill_dir)
        empty_hint = "完整配置《交换机信息》表无交换机，请检查 CloudOps 完整配置文件。"
    else:
        base = load_base_devices(skill_dir)
        empty_hint = "设备底表为空，请先完成步骤 3/9（下发底表 + 导入刷新）。"
    if not base and scope not in {"prev_failed", "prev_passed", "prev_same"}:
        return ResolveResult(ok=False, message=empty_hint)

    installed_ips = {d.ip for d in base if d.installed}
    by_ip = {d.ip: d for d in base}
    selected: list[Device]
    source: str

    pool_label = "交换机全量" if device_kind == "switch" else "底表全量"
    if scope == "all":
        selected = list(base)
        source = pool_label
    elif scope == "pod":
        if not pod_ids:
            return ResolveResult(ok=False, message="scope=pod 需提供 pod_ids。")
        selected = _filter_pod(base, pod_ids)
        source = f"POD {pod_ids} 全量"
    elif scope == "exclude":
        pool = _filter_pod(base, pod_ids) if pod_ids else list(base)
        excl = [d for d in pool if any(_match(d, t) for t in devices)]
        excl_keys = {d.ip for d in excl}
        selected = [d for d in pool if d.ip not in excl_keys]
        source = f"{'POD ' + str(pod_ids) + ' ' if pod_ids else ''}排除 {len(excl)} 台"
    elif scope == "include":
        if not devices:
            return ResolveResult(ok=False, message="scope=include 需提供 devices。")
        selected = [d for d in base if any(_match(d, t) for t in devices)]
        found = {d.name for d in selected} | {d.ip for d in selected}
        for t in devices:
            if t not in found:
                selected.append(Device(ip=t, name="", pod_id=0, installed=t in installed_ips))
        source = f"指定 {len(devices)} 台"
    elif scope == "param_file":
        ids = _param_file_devices(skill_dir)
        if not ids:
            return ResolveResult(ok=False, message="未找到参数文件指定设备（RunTime/param_devices.json）。")
        selected = [by_ip.get(x) or Device(ip=x, installed=x in installed_ips) for x in ids]
        source = f"参数文件指定 {len(ids)} 台"
    elif scope in {"prev_failed", "prev_passed"}:
        passed, failed, hit = _load_prev_result_devices(skill_dir, task_no, task_type=task_type)
        pick = failed if scope == "prev_failed" else passed
        if not hit:
            return ResolveResult(ok=False, message=f"未找到任务 `{task_no or '(最近)'}` 的结果记录。")
        selected = [by_ip.get(x) or Device(ip=x, installed=x in installed_ips) for x in pick]
        kind = "未通过" if scope == "prev_failed" else "已通过"
        source = f"任务 {hit} 的{kind}设备 {len(pick)} 台"
    else:  # prev_same
        ids, hit = _load_prev_range(skill_dir, task_no, task_type=task_type)
        if not hit:
            return ResolveResult(ok=False, message=f"未找到任务 `{task_no or '(最近)'}` 的设备范围。")
        selected = [by_ip.get(x) or Device(ip=x, installed=x in installed_ips) for x in ids]
        source = f"复用任务 {hit} 的设备范围 {len(ids)} 台"

    skipped_uninstalled: list[str] = []
    if only_installed:
        kept: list[Device] = []
        for d in selected:
            if d.ip in installed_ips or (d.ip not in by_ip and d.installed):
                kept.append(d)
            else:
                skipped_uninstalled.append(d.ip)
        selected = kept
        source += "（∩已初始化）"

    # 门禁：确保设备确实已导入 ops（对齐 Agent compare_with_cloudops_config）。
    # 仅 server 类需要——switch 类的 base 已直接取自完整配置《交换机信息》。
    # 读不到完整配置（空集）则跳过门禁，不误杀。
    skipped_not_in_config: list[str] = []
    if device_kind != "switch":
        cfg_ids = load_full_config_device_ids(skill_dir)
        if cfg_ids:
            kept_cfg: list[Device] = []
            for d in selected:
                if d.ip in cfg_ids:
                    kept_cfg.append(d)
                else:
                    skipped_not_in_config.append(d.ip)
            selected = kept_cfg
            source += "（∩完整配置）"

    seen: set[str] = set()
    final: list[Device] = []
    for d in selected:
        if d.ip and d.ip not in seen:
            seen.add(d.ip)
            final.append(d)

    if not final:
        msg = "解析后设备范围为空。"
        if skipped_uninstalled:
            msg += f" 有 {len(skipped_uninstalled)} 台未初始化被过滤。"
        if skipped_not_in_config:
            msg += f" 有 {len(skipped_not_in_config)} 台不在 CloudOps 完整配置内（未导入 ops）被过滤。"
        return ResolveResult(ok=False, message=msg, source=source, pod_ids=pod_ids, task_no=task_no)

    res = ResolveResult(
        ok=True,
        ips=[d.ip for d in final],
        devices=final,
        source=source,
        pod_ids=pod_ids,
        task_no=task_no,
    )
    notes: list[str] = []
    if skipped_uninstalled:
        notes.append(f"已过滤 {len(skipped_uninstalled)} 台未初始化设备")
    if skipped_not_in_config:
        notes.append(f"已过滤 {len(skipped_not_in_config)} 台不在完整配置内的设备")
    if notes:
        res.message = "；".join(notes) + "。"
    return res
