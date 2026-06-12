"""ZTP CloudOps API 请求体构建 — 对齐 generated_ztp_api.ZTPConfigConverter（本地 Excel）。"""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any

import pandas as pd

API_STRUCTURE: dict[str, Any] = {
    "ztpInputConfig": {
        "ccPackageName": None,
        "patchPackageName": None,
        "ntpAuthenKtyId": None,
        "ntpAuthenMode": None,
        "ntpAuthenPassword": None,
        "ntpServerIp": None,
        "ntpServerIpBack": None,
        "ntpServerDomain": None,
        "sshLocalUser": None,
        "sshLocalUserPassword": None,
        "netconfUser": None,
        "netconfUserPassword": None,
        "grpcUser": None,
        "grpcUserPassword": None,
        "bmcUserPassword": None,
        "snmpVersion": "v3",
        "snmpUserGroup": None,
        "snmpUser": None,
        "snmpAuthenMode": None,
        "snmpPrivacyMode": None,
        "snmpTargetHostIp": None,
        "authKey": None,
        "privKey": None,
        "radiusSharedKey": None,
        "radiusServerIp": None,
        "radiusServerIpBack": None,
        "telemetryDestIp": None,
        "telemetryDestPort": None,
        "syslogServerIp": None,
        "syslogServerPort": None,
        "roomParas": [
            {
                "roomName": "",
                "superSize": "",
                "topoName": "",
                "isTypical": True,
            }
        ],
        "isToEnablePortDes": False,
        "isGenerateNTP": False,
        "isGenerateUserAccount": False,
        "isGenerateBMCManagement": False,
        "isGenerateSNMP": False,
        "isGenerateRadius": False,
        "isGenerateTelemetry": False,
        "isGenerateLogAnalysis": False,
    },
    "ztpConfigList": [],
    "userAccount": "",
    "clusterType": "training",
    "serverModel": "Atlas 900 RCK A3",
    "passWord": "",
}

VARIABLE_MAPPING: dict[str, str] = {
    "ccPackageName": "ccPackageName",
    "patchPackageName": "patchPackageName",
    "sshLocalUser": "sshLocalUser",
    "sshLocalUserPassword": "sshLocalUserPassword",
    "netconfUser": "netconfUser",
    "netconfUserPassword": "netconfUserPassword",
    "grpcUser": "grpcUser",
    "grpcUserPassword": "grpcUserPassword",
    "bmcUserPassword": "bmcUserPassword",
    "snmpUserGroup": "snmpUserGroup",
    "snmpUser": "snmpUser",
    "snmpAuthenMode": "snmpAuthenMode",
    "snmpPrivacyMode": "snmpPrivacyMode",
    "snmpTargetHostIp": "snmpTargetHostIp",
    "authKey": "authKey",
    "privKey": "privKey",
    "radiusSharedKey": "radiusSharedKey",
    "radiusServerIp": "radiusServerIp",
    "radiusServerIpBack": "radiusServerIpBack",
    "telemetryDestIp": "telemetryDestIp",
    "telemetryDestPort": "telemetryDestPort",
    "syslogServerIp": "syslogServerIp",
    "syslogServerPort": "syslogServerPort",
    "superSize": "superSize",
    "topoName": "topoName",
    "isToEnablePortDes": "isToEnablePortDes",
    "isGenerateNTP": "isGenerateNTP",
    "isGenerateUserAccount": "isGenerateUserAccount",
    "isGenerateSNMP": "isGenerateSNMP",
    "isGenerateRadius": "isGenerateRadius",
    "isGenerateTelemetry": "isGenerateTelemetry",
    "isGenerateLogAnalysis": "isGenerateLogAnalysis",
    "超节点ID": "superNode",
    "交换机ID": "switchId",
    "交换机名称": "switchName",
    "L1/L2平面": "switchLevel",
    "deviceModel": "deviceModel",
    "ESN": "esn",
    "LoopBack起始IP": "lookBackStartIp",
    "LoopBack结束IP": "lookBackEndIp",
    "BGP AS号": "bgpAs",
    "网关": "dhcpGateway",
    "管理面IP": "dhcpIp",
    "柜内位置": "rackLocation",
    "机房名称": "roomName",
    "机柜编号": "rackNum",
    "VLAN ID": "vlanId",
    "portDesDefineRules": "portDesDefineRules",
    "isTypical": "isTypical",
    "ntpAuthenKtyId": "ntpAuthenKtyId",
    "ntpAuthenMode": "ntpAuthenMode",
    "ntpAuthenPassword": "ntpAuthenPassword",
    "ntpServerIp": "ntpServerIp",
    "ntpServerIpBack": "ntpServerIpBack",
    "ntpServerDomain": "ntpServerDomain",
    "userAccount": "userAccount",
    "clusterType": "clusterType",
    "serverModel": "serverModel",
    "passWord": "passWord",
}

DEVICE_MODEL_PATTERNS = {
    "AT900A3": "Atlas 900 RCK A3",
    "AT800TA3": "Atlas 800T A3",
    "AT800IA3": "Atlas 800I A3",
    "LQS": "Ling Qu 630 V1",
}

# 项目表「配置项」中文名 → VARIABLE_MAPPING 键（变量列为空时使用）
CONFIG_ITEM_ALIASES: dict[str, str] = {
    "配置CC大包名称": "ccPackageName",
    "配置补丁包名称": "patchPackageName",
    "是否启用端口描述": "isToEnablePortDes",
    "超节点规模": "superSize",
    "机房名称": "roomName",
}

# 项目表「变量」列非标准名 → VARIABLE_MAPPING 键
VAR_NAME_ALIASES: dict[str, str] = {
    "topoType": "isTypical",
    "ntp": "isGenerateNTP",
    "account": "isGenerateUserAccount",
    "snmp": "isGenerateSNMP",
    "radius": "isGenerateRadius",
    "telemetry": "isGenerateTelemetry",
    "info-center": "isGenerateLogAnalysis",
    "NtpAuthenKtyId": "ntpAuthenKtyId",
    "NtpAuthenMode": "ntpAuthenMode",
    "NtpAuthenPassword": "ntpAuthenPassword",
    "NtpServerIp": "ntpServerIp",
    "NtpServerIpBack": "ntpServerIpBack",
    "SNMPUserGroup": "snmpUserGroup",
    "SNMPUser": "snmpUser",
    "SNMPAuthenMode": "snmpAuthenMode",
    "SNMPPrivacyMode": "snmpPrivacyMode",
    "SNMPTargetHostIp": "snmpTargetHostIp",
    "RadiusSharedKey": "radiusSharedKey",
    "RadiusServerIp": "radiusServerIp",
    "RadiusServerIpBack": "radiusServerIpBack",
    "SyslogServerIp": "syslogServerIp",
    "SyslogServerPort": "syslogServerPort",
}


class ZTPConfigConverter:
    def __init__(self) -> None:
        self.api_structure = copy.deepcopy(API_STRUCTURE)
        self.variable_mapping = VARIABLE_MAPPING

    @staticmethod
    def _resolve_var_column(df: pd.DataFrame) -> str:
        for col in ("CloudOps变量", "变量"):
            if col in df.columns:
                return col
        raise ValueError("Excel文件中缺少变量列（CloudOps变量 或 变量）")

    @staticmethod
    def _canonical_config_key(raw_name: str) -> str | None:
        if raw_name in CONFIG_ITEM_ALIASES:
            return CONFIG_ITEM_ALIASES[raw_name]
        if raw_name in VAR_NAME_ALIASES:
            return VAR_NAME_ALIASES[raw_name]
        if raw_name in VARIABLE_MAPPING:
            return raw_name
        lower_map = {k.lower(): k for k in VARIABLE_MAPPING}
        return lower_map.get(raw_name.lower())

    def read_project_config_excel(self, excel_file_path: Path, sheet: str = "ZTP配置") -> dict[str, Any]:
        df = pd.read_excel(excel_file_path, sheet_name=sheet)
        if "规划值" not in df.columns:
            raise ValueError("Excel文件中缺少必要的列: 规划值")
        var_col = self._resolve_var_column(df)
        has_item_col = "配置项" in df.columns
        has_default_col = "默认配置" in df.columns
        config_data: dict[str, Any] = {}
        for _, row in df.iterrows():
            var_value = row["规划值"]
            if pd.isna(var_value) and has_default_col:
                var_value = row["默认配置"]
            if pd.isna(var_value):
                continue
            var_name: str | None = None
            if pd.notna(row.get(var_col)):
                var_name = self._canonical_config_key(str(row[var_col]).strip())
            elif has_item_col and pd.notna(row.get("配置项")):
                var_name = self._canonical_config_key(str(row["配置项"]).strip())
            if var_name:
                config_data[var_name] = var_value
        return config_data

    def read_ztp_lld_excel(self, excel_file_path: Path, sheet: str = "网络IP规划") -> list[dict[str, Any]]:
        df = pd.read_excel(excel_file_path, sheet_name=sheet).fillna("")
        devices: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            devices.append({str(col): row[col] for col in df.columns})
        return devices

    @staticmethod
    def get_device_model(device_name: str) -> str:
        for pattern, model in DEVICE_MODEL_PATTERNS.items():
            if pattern in str(device_name):
                return model
        return ""

    @staticmethod
    def parse_list_string(s: str) -> Any:
        s = str(s).strip()
        if not s.startswith("["):
            s = f"[{s}]"
        try:
            return json.loads(s)
        except Exception:
            try:
                return ast.literal_eval(s)
            except Exception:
                return []

    @staticmethod
    def get_non_empty_value(config: dict, keys: list[str]) -> str:
        for key in keys:
            value = config.get(key, "")
            if value and str(value).strip():
                return str(value)
        return ""

    def map_variables(
        self,
        project_config: dict[str, Any],
        device_configs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        device_configs = device_configs or []
        mapped: dict[str, Any] = {}
        for excel_key, api_key in self.variable_mapping.items():
            if excel_key in project_config:
                mapped[api_key] = project_config[excel_key]
                if "是" in str(project_config[excel_key]):
                    mapped[api_key] = True
                elif "否" in str(project_config[excel_key]):
                    mapped[api_key] = False
                if excel_key == "isTypical":
                    mapped[api_key] = project_config.get("isTypical", "") == "typical"
                if excel_key == "portDesDefineRules":
                    mapped[api_key] = self.parse_list_string(project_config[excel_key])
            elif device_configs and excel_key in device_configs[0]:
                mapped[api_key] = device_configs[0][excel_key]
        return mapped

    def convert_to_api_request(
        self,
        project_config_file: Path,
        ztp_lld_file: Path | None = None,
        *,
        project_sheet: str = "ZTP配置",
        lld_sheet: str = "网络IP规划",
    ) -> dict[str, Any]:
        project_config = self.read_project_config_excel(project_config_file, project_sheet)
        device_configs: list[dict[str, Any]] = []
        if ztp_lld_file:
            device_configs = self.read_ztp_lld_excel(ztp_lld_file, lld_sheet)

        mapped_config = self.map_variables(project_config, device_configs)
        api_body = copy.deepcopy(self.api_structure)
        ztp_input_config = api_body["ztpInputConfig"]

        fields_to_set = [
            "ccPackageName",
            "patchPackageName",
            "isGenerateNTP",
            "ntpAuthenKtyId",
            "ntpAuthenMode",
            "ntpAuthenPassword",
            "ntpServerIp",
            "ntpServerIpBack",
            "ntpServerDomain",
            "isGenerateUserAccount",
            "sshLocalUser",
            "sshLocalUserPassword",
            "netconfUser",
            "netconfUserPassword",
            "grpcUser",
            "grpcUserPassword",
            "isGenerateBMCManagement",
            "bmcUserPassword",
            "isGenerateSNMP",
            "snmpVersion",
            "snmpUserGroup",
            "snmpUser",
            "snmpAuthenMode",
            "snmpPrivacyMode",
            "snmpTargetHostIp",
            "authKey",
            "privKey",
            "isGenerateRadius",
            "radiusSharedKey",
            "radiusServerIp",
            "radiusServerIpBack",
            "isGenerateTelemetry",
            "telemetryDestIp",
            "telemetryDestPort",
            "isGenerateLogAnalysis",
            "syslogServerIp",
            "syslogServerPort",
            "isToEnablePortDes",
            "portDesDefineRules",
            "roomParas",
        ]
        for field in fields_to_set:
            if field in mapped_config:
                ztp_input_config[field] = mapped_config[field]

        if device_configs:
            api_body["ztpConfigList"] = []
            for device_config in device_configs:
                switch_name = device_config.get("交换机名称", "")
                api_body["ztpConfigList"].append(
                    {
                        "superNode": device_config.get("超节点ID", ""),
                        "switchId": device_config.get("交换机ID", ""),
                        "switchName": switch_name,
                        "switchLevel": device_config.get("L1/L2平面", ""),
                        "deviceModel": self.get_device_model(switch_name),
                        "esn": device_config.get("ESN", ""),
                        "lookBackStartIp": self.get_non_empty_value(
                            device_config, ["LoopBack起始IP", "loopBack0"]
                        ),
                        "lookBackEndIp": self.get_non_empty_value(
                            device_config, ["LoopBack结束IP", "loopBack6", "loopBack1"]
                        ),
                        "bgpAs": device_config.get("BGP AS号", ""),
                        "dhcpGateway": device_config.get("网关", ""),
                        "dhcpIp": device_config.get("管理面IP", ""),
                        "rackLocation": device_config.get("柜内位置", ""),
                        "roomName": device_config.get("机房名称", ""),
                        "rackNum": device_config.get("机柜编号", ""),
                        "superSize": device_config.get("超节点规模", ""),
                        "vlanId": device_config.get("VLAN ID", ""),
                    }
                )

        if "roomName" in mapped_config and "superSize" in mapped_config and "topoName" in mapped_config:
            ztp_input_config["roomParas"][0]["roomName"] = mapped_config["roomName"]
            ztp_input_config["roomParas"][0]["superSize"] = mapped_config["superSize"]
            ztp_input_config["roomParas"][0]["topoName"] = mapped_config["topoName"]
            ztp_input_config["roomParas"][0]["isTypical"] = mapped_config["isTypical"]

        for field in ("userAccount", "clusterType", "serverModel", "passWord"):
            if field in mapped_config:
                api_body[field] = mapped_config[field]

        return api_body
