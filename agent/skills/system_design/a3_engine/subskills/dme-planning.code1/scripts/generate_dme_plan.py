#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Standalone deterministic DME deployment planner."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd


OUTPUT_COLUMNS = [
    "设备名称",
    "网络平面",
    "接口名称",
    "IP地址",
    "掩码",
    "网关",
    "VLAN",
    "Bond模式",
    "目的网段",
    "目的掩码",
]

SUPPORTED_NODE_COUNTS = {1, 3, 5, 8}


class SkillError(RuntimeError):
    """Raised for user-correctable planning errors."""


class State(str, Enum):
    INIT = "INIT"
    LOAD_INPUTS = "LOAD_INPUTS"
    VALIDATE_INPUTS = "VALIDATE_INPUTS"
    RESOLVE_CONTEXT = "RESOLVE_CONTEXT"
    PLAN_DME_NETWORKS = "PLAN_DME_NETWORKS"
    WRITE_OUTPUT = "WRITE_OUTPUT"
    DONE = "DONE"
    FAILED = "FAILED"


@dataclass
class EventLog:
    events: list[dict[str, str]] = field(default_factory=list)

    def emit(self, state: State, action: str, event: str, message: str = "") -> None:
        self.events.append(
            {
                "state": state.value,
                "action": action,
                "event": event,
                "message": message,
            }
        )


@dataclass
class PlaneResource:
    key: str
    label: str
    ip_pool: str
    mask_raw: str
    vlan: str

    @property
    def gateway(self) -> ipaddress.IPv4Address:
        start_ip, _ = parse_ip_pool(self.ip_pool)
        return start_ip

    @property
    def network(self) -> ipaddress.IPv4Network:
        start_ip, _ = parse_ip_pool(self.ip_pool)
        return ipaddress.IPv4Network(f"{start_ip}/{prefix_len(self.mask_raw)}", strict=False)

    @property
    def dotted_mask(self) -> str:
        return str(ipaddress.IPv4Network(f"0.0.0.0/{prefix_len(self.mask_raw)}").netmask)


@dataclass
class PlanningContext:
    devices: list[str]
    oob: PlaneResource | None
    ib: PlaneResource | None
    service: PlaneResource | None
    dataturbo: bool
    mlag: bool

    @property
    def bond_mode(self) -> str:
        return "mode4" if self.mlag else "mode1"

    @property
    def service_enabled(self) -> bool:
        return self.dataturbo and self.service is not None

    @property
    def scenario(self) -> str:
        if self.oob and self.ib and self.service_enabled:
            return "A 带外+带内+数据"
        if self.oob and not self.ib and self.service_enabled:
            return "B 带外+数据"
        if not self.oob and self.ib and self.service_enabled:
            return "C 带内+数据"
        if self.oob and self.ib:
            return "带外+带内"
        if self.oob:
            return "仅带外"
        if self.ib:
            return "仅带内"
        return "未识别"


def normalize_name(value: Any) -> str:
    return str(value).strip().lower().replace("*", "").replace(" ", "")


def is_nonempty(value: Any) -> bool:
    if pd.isna(value):
        return False
    return str(value).strip() not in {"", "nan", "NaN", "None", "NONE"}


def truthy(value: Any) -> bool | None:
    if not is_nonempty(value):
        return None
    text = str(value).strip().lower()
    true_values = {"true", "yes", "y", "1", "是", "启用", "开启", "开", "支持", "有"}
    false_values = {"false", "no", "n", "0", "否", "不启用", "关闭", "关", "不支持", "无"}
    if text in true_values:
        return True
    if text in false_values:
        return False
    return None


def first_nonempty(row: pd.Series, candidates: list[str]) -> str:
    norm_to_col = {normalize_name(col): col for col in row.index}
    for candidate in candidates:
        normalized = normalize_name(candidate)
        col = norm_to_col.get(normalized)
        if col is None:
            for norm_col, original in norm_to_col.items():
                if normalized and normalized in norm_col:
                    col = original
                    break
        if col is None:
            continue
        value = row[col]
        if is_nonempty(value):
            return str(value).strip()
    return ""


def parse_ip_pool(ip_pool: str) -> tuple[ipaddress.IPv4Address, ipaddress.IPv4Address]:
    parts = [part.strip() for part in str(ip_pool).split("-", 1)]
    if len(parts) != 2:
        raise SkillError(f"地址池格式错误，应为 起始IP-结束IP: {ip_pool}")
    start_ip = ipaddress.IPv4Address(parts[0])
    end_ip = ipaddress.IPv4Address(parts[1])
    if start_ip > end_ip:
        raise SkillError(f"地址池起始 IP 不能大于结束 IP: {ip_pool}")
    return start_ip, end_ip


def prefix_len(mask_raw: str) -> int:
    text = str(mask_raw).strip()
    if "." in text and re.fullmatch(r"\d{1,2}\.0", text):
        text = text.split(".")[0]
    if re.fullmatch(r"\d{1,2}", text):
        value = int(text)
        if 0 <= value <= 32:
            return value
    try:
        return ipaddress.IPv4Network(f"0.0.0.0/{text}").prefixlen
    except ValueError as exc:
        raise SkillError(f"掩码必须为 0-32 前缀或点分掩码，当前为: {mask_raw}") from exc


def parse_vlan(value: str) -> str:
    text = str(value).strip()
    if not text or text in {"nan", "NaN", "None"}:
        return ""
    if "-" in text:
        start, end = [part.strip() for part in text.split("-", 1)]
        if not start.isdigit() or not end.isdigit() or int(start) > int(end):
            raise SkillError(f"VLAN 范围格式错误，应为 start-end: {value}")
        return start
    if not text.isdigit():
        raise SkillError(f"VLAN 必须为数字或数字范围: {value}")
    return text


def read_excel_sheet(path: Path, sheet_name: str | int = 0, header: int | None = 0) -> pd.DataFrame:
    try:
        return pd.read_excel(path, sheet_name=sheet_name, header=header)
    except ValueError:
        return pd.DataFrame()
    except FileNotFoundError as exc:
        raise SkillError(f"输入文件不存在: {path}") from exc


def extract_device_switch_info(port_file: Path, sheet_name: str) -> pd.DataFrame:
    raw = read_excel_sheet(port_file, sheet_name=sheet_name, header=None)
    if raw.empty:
        return pd.DataFrame(columns=["计算服务器", "接入交换机"])

    header_row_idx = None
    for idx, row in raw.iterrows():
        if row.astype(str).str.contains("设备命名", case=False, na=False).any():
            header_row_idx = idx
            break

    if header_row_idx is None:
        raise SkillError(f"Sheet '{sheet_name}' 未找到包含'设备命名'的表头行")

    data = raw.iloc[header_row_idx + 1 :].reset_index(drop=True)
    if data.empty:
        return pd.DataFrame(columns=["计算服务器", "接入交换机"])

    result = pd.DataFrame(
        {
            "计算服务器": data.iloc[:, 0],
            "接入交换机": data.iloc[:, -1],
        }
    )
    result = result[result["计算服务器"].apply(is_nonempty)].copy()
    return result


def load_dme_devices(port_file: Path) -> list[str]:
    sheet_names = ["计算带外管理面端口互联", "存储带外管理面端口互联"]
    frames = [extract_device_switch_info(port_file, sheet) for sheet in sheet_names]
    merged = pd.concat([frame for frame in frames if not frame.empty], ignore_index=True)
    if merged.empty:
        raise SkillError("未从端口互联表找到 DME 设备信息")

    devices = (
        merged["计算服务器"]
        .astype(str)
        .str.strip()
        .loc[lambda values: values.str.contains("DME", case=False, na=False)]
        .drop_duplicates()
        .tolist()
    )
    devices = sorted(device for device in devices if device)
    if not devices:
        raise SkillError("未找到名称包含 DME 的设备，请检查端口互联表")
    if len(devices) not in SUPPORTED_NODE_COUNTS:
        raise SkillError(f"DME 节点数仅支持 1/3/5/8，当前识别到 {len(devices)} 个: {devices}")
    return devices


def load_resource_frame(resource_file: Path) -> pd.DataFrame:
    df = read_excel_sheet(resource_file, sheet_name=0, header=0)
    if df.empty:
        raise SkillError("网络资源/项目信息收集表为空")
    if "网络平面" not in df.columns:
        raise SkillError("网络资源表缺少必需列: 网络平面")
    return df


def find_resource(df: pd.DataFrame, pattern: str, label: str, key: str) -> PlaneResource | None:
    matched = df[df["网络平面"].astype(str).str.contains(pattern, case=False, na=False, regex=True)]
    if matched.empty:
        return None

    for _, row in matched.iterrows():
        ip_pool = first_nonempty(row, ["地址池*", "地址池", "ip_pool"])
        if not ip_pool:
            continue
        mask_raw = first_nonempty(row, ["最小规划掩码", "掩码", "MASK", "mask"])
        if not mask_raw:
            raise SkillError(f"{label} 缺少掩码/最小规划掩码")
        vlan = parse_vlan(first_nonempty(row, ["VLAN*", "VLAN", "vlan_pool", "vlan"]))
        resource = PlaneResource(key=key, label=label, ip_pool=ip_pool, mask_raw=mask_raw, vlan=vlan)
        validate_resource(resource)
        return resource
    return None


def validate_resource(resource: PlaneResource) -> None:
    start_ip, end_ip = parse_ip_pool(resource.ip_pool)
    network = resource.network
    if start_ip not in network:
        raise SkillError(f"{resource.label} 地址池起始 IP 不在掩码对应网段内: {resource.ip_pool}/{resource.mask_raw}")
    if end_ip not in network:
        raise SkillError(f"{resource.label} 地址池结束 IP 不在掩码对应网段内: {resource.ip_pool}/{resource.mask_raw}")


def parse_bool_arg(value: str, name: str) -> bool | None:
    if value == "auto":
        return None
    parsed = truthy(value)
    if parsed is None:
        raise SkillError(f"{name} 参数仅支持 true/false/auto，当前为: {value}")
    return parsed


def parse_context_bool_from_table(df: pd.DataFrame, names: list[str]) -> bool | None:
    normalized_names = [normalize_name(name) for name in names]

    for col in df.columns:
        if any(name in normalize_name(col) for name in normalized_names):
            for value in df[col].tolist():
                parsed = truthy(value)
                if parsed is not None:
                    return parsed

    pattern = re.compile(
        r"(dataturbo|data\s*turbo|数据加速|mlag|堆叠|跨框|跨设备)\s*[:：=]?\s*(true|false|yes|no|是|否|启用|不启用|开启|关闭|有|无|1|0)",
        re.IGNORECASE,
    )
    for value in df.astype(str).to_numpy().flatten().tolist():
        match = pattern.search(value)
        if not match:
            continue
        key = normalize_name(match.group(1))
        if any(name in key for name in normalized_names):
            parsed = truthy(match.group(2))
            if parsed is not None:
                return parsed
    return None


def usable_ips(resource: PlaneResource, used_global: set[ipaddress.IPv4Address]) -> list[ipaddress.IPv4Address]:
    start_ip, end_ip = parse_ip_pool(resource.ip_pool)
    gateway = resource.gateway
    out: list[ipaddress.IPv4Address] = []
    for ip in resource.network.hosts():
        if ip < start_ip or ip > end_ip:
            continue
        if ip == gateway or ip in used_global:
            continue
        out.append(ip)
    return out


def allocate(resource: PlaneResource, count: int, used_global: set[ipaddress.IPv4Address]) -> list[str]:
    selected: list[ipaddress.IPv4Address] = []
    for ip in usable_ips(resource, used_global):
        selected.append(ip)
        used_global.add(ip)
        if len(selected) == count:
            break
    if len(selected) < count:
        raise SkillError(f"{resource.label} 地址池不足：需要 {count} 个，可分配 {len(selected)} 个")
    return [str(ip) for ip in selected]


def row(
    name: str,
    plane: str,
    iface: str,
    ip: str,
    mask: str,
    gateway: str,
    vlan: str,
    bond: str,
    dest_net: str,
    dest_mask: str,
) -> dict[str, str]:
    return {
        "设备名称": name,
        "网络平面": plane,
        "接口名称": iface,
        "IP地址": ip,
        "掩码": mask,
        "网关": gateway,
        "VLAN": vlan,
        "Bond模式": bond,
        "目的网段": dest_net,
        "目的掩码": dest_mask,
    }


def title_row(title: str) -> dict[str, str]:
    return row(title, "网络平面", "接口名称", "IP地址", "子网掩码", "网关", "VLAN", "Bond模式", "目的网段", "目的掩码")


def build_plan(ctx: PlanningContext) -> pd.DataFrame:
    if not ctx.oob and not ctx.ib:
        raise SkillError("DME 带外管理面和带内管理面均缺失，无法规划")

    used_global: set[ipaddress.IPv4Address] = set()
    rows: list[dict[str, str]] = []
    allocations: dict[str, list[str]] = {}

    if ctx.oob:
        allocations["oob_nodes"] = allocate(ctx.oob, len(ctx.devices), used_global)
    if ctx.ib:
        allocations["ib_nodes"] = allocate(ctx.ib, len(ctx.devices), used_global)
    if ctx.service_enabled and ctx.service:
        allocations["service_nodes"] = allocate(ctx.service, len(ctx.devices) * 2, used_global)

    for index, device in enumerate(ctx.devices):
        if ctx.oob:
            rows.append(
                row(
                    device,
                    "带外管理面网络",
                    "bond0",
                    allocations["oob_nodes"][index],
                    ctx.oob.dotted_mask,
                    str(ctx.oob.gateway),
                    ctx.oob.vlan,
                    ctx.bond_mode,
                    "0.0.0.0",
                    "0.0.0.0",
                )
            )
        if ctx.ib:
            rows.append(
                row(
                    device,
                    "带内管理面网络",
                    "bond1",
                    allocations["ib_nodes"][index],
                    ctx.ib.dotted_mask,
                    str(ctx.ib.gateway),
                    ctx.ib.vlan,
                    ctx.bond_mode,
                    "",
                    "",
                )
            )
        if ctx.service_enabled and ctx.service:
            service_ips = allocations["service_nodes"]
            rows.append(
                row(
                    device,
                    "业务面网络1",
                    "",
                    service_ips[index * 2],
                    ctx.service.dotted_mask,
                    str(ctx.service.gateway),
                    ctx.service.vlan,
                    "",
                    "",
                    "",
                )
            )
            rows.append(
                row(
                    device,
                    "业务面网络2",
                    "",
                    service_ips[index * 2 + 1],
                    ctx.service.dotted_mask,
                    str(ctx.service.gateway),
                    ctx.service.vlan,
                    "",
                    "",
                    "",
                )
            )

    if ctx.oob:
        rows.append({column: "" for column in OUTPUT_COLUMNS})
        rows.append(title_row("网络用途_DME"))
        floating_oob = allocate(ctx.oob, 3, used_global)
        for purpose, ip in zip(["带外南向浮动IP", "带外北向浮动IP", "带外负载均衡IP"], floating_oob):
            rows.append(
                row(
                    purpose,
                    "带外管理面网络",
                    "bond0",
                    ip,
                    ctx.oob.dotted_mask,
                    str(ctx.oob.gateway),
                    ctx.oob.vlan,
                    ctx.bond_mode,
                    "0.0.0.0",
                    "0.0.0.0",
                )
            )
        if ctx.ib:
            floating_ib = allocate(ctx.ib, 1, used_global)
            rows.append(
                row(
                    "带内南向浮动IP",
                    "带内管理面网络",
                    "bond1",
                    floating_ib[0],
                    ctx.ib.dotted_mask,
                    str(ctx.ib.gateway),
                    ctx.ib.vlan,
                    ctx.bond_mode,
                    "",
                    "",
                )
            )

    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS).fillna("")


def dataframe_preview(df: pd.DataFrame, rows: int) -> str:
    try:
        return df.head(rows).to_markdown(index=False)
    except ImportError:
        return df.head(rows).to_string(index=False)


def write_output(df: pd.DataFrame, output_dir: Path, output_name: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_name
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="DME部署方案", index=False)
        worksheet = writer.sheets["DME部署方案"]
        for column_cells in worksheet.columns:
            values = [str(cell.value) if cell.value is not None else "" for cell in column_cells]
            width = min(max(len(value) for value in values) + 2, 40)
            worksheet.column_dimensions[column_cells[0].column_letter].width = width
    return output_path


def run(args: argparse.Namespace) -> dict[str, Any]:
    log = EventLog()
    try:
        log.emit(State.INIT, "detect_trigger", "TRIGGER_ACCEPTED" if args.trigger == "DME规划" else "TRIGGER_REJECTED")
        if args.trigger != "DME规划":
            raise SkillError(f"触发词必须为 DME规划，当前为: {args.trigger}")

        port_file = Path(args.port_file)
        resource_file = Path(args.resource_file)
        output_dir = Path(args.output_dir)
        if not port_file.exists():
            raise SkillError(f"端口互联关系文件不存在: {port_file}")
        if not resource_file.exists():
            raise SkillError(f"网络资源/项目信息收集表不存在: {resource_file}")

        devices = load_dme_devices(port_file)
        resource_df = load_resource_frame(resource_file)
        log.emit(State.LOAD_INPUTS, "load_excel_inputs", "INPUTS_LOADED", f"loaded {len(devices)} DME devices")

        oob = find_resource(resource_df, "DME带外管理", "DME带外管理", "dme_oob")
        ib = find_resource(resource_df, "DME带内管理", "DME带内管理", "dme_ib")
        service = find_resource(resource_df, "DME业务|DME数据", "DME数据网络", "dme_service")
        if not oob and not ib:
            raise SkillError("网络资源表中未找到 DME 带外管理或 DME 带内管理地址池")
        log.emit(State.VALIDATE_INPUTS, "validate_required_fields", "INPUTS_VALID")

        dataturbo = parse_bool_arg(args.dataturbo, "dataturbo")
        if dataturbo is None:
            dataturbo = parse_context_bool_from_table(resource_df, ["dataturbo", "data turbo", "数据加速"])
        if dataturbo is None:
            raise SkillError("DataTurbo 未提供且无法从输入表解析，请使用 --dataturbo true/false")

        mlag = parse_bool_arg(args.mlag, "mlag")
        if mlag is None:
            mlag = parse_context_bool_from_table(resource_df, ["mlag", "堆叠", "跨框", "跨设备"])
        if mlag is None:
            mlag = False

        ctx = PlanningContext(devices=devices, oob=oob, ib=ib, service=service, dataturbo=dataturbo, mlag=mlag)
        log.emit(State.RESOLVE_CONTEXT, "resolve_scenario_dataturbo_mlag", "CONTEXT_RESOLVED", ctx.scenario)

        plan_df = build_plan(ctx)
        log.emit(State.PLAN_DME_NETWORKS, "allocate_node_and_floating_ips", "PLAN_BUILT", f"{len(plan_df)} rows")

        output_path = write_output(plan_df, output_dir, args.output_name)
        log.emit(State.WRITE_OUTPUT, "write_excel_and_preview", "OUTPUT_WRITTEN", str(output_path))
        log.emit(State.DONE, "return_result_summary", "SKILL_COMPLETED")

        return {
            "status": "success",
            "output_file": str(output_path),
            "sheet": "DME部署方案",
            "row_count": int(len(plan_df)),
            "scenario": ctx.scenario,
            "dataturbo": ctx.dataturbo,
            "mlag": ctx.mlag,
            "preview": dataframe_preview(plan_df, args.preview_rows),
            "events": log.events,
        }
    except Exception as exc:
        log.emit(State.FAILED, "return_error_report", "SKILL_FAILED", str(exc))
        return {
            "status": "failed",
            "error": str(exc),
            "events": log.events,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate deterministic DME deployment planning Excel.")
    parser.add_argument("--trigger", required=True, help="Stage trigger. Must be DME规划.")
    parser.add_argument("--port-file", required=True, help="Path to 端口互联关系.xlsx.")
    parser.add_argument("--resource-file", required=True, help="Path to 网络资源/项目信息收集表.xlsx.")
    parser.add_argument("--output-dir", required=True, help="Directory for generated Excel.")
    parser.add_argument("--dataturbo", default="auto", help="true, false, or auto. Auto must be parseable from input.")
    parser.add_argument("--mlag", default="auto", help="true, false, or auto. Auto defaults to false when unparseable.")
    parser.add_argument("--output-name", default="A3DME部署规划.xlsx", help="Output Excel filename.")
    parser.add_argument("--preview-rows", type=int, default=20, help="Rows included in markdown preview.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
