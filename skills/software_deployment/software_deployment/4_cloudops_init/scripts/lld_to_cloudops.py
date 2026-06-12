"""
将 LLD 设计文件填入 CloudOps 模板，生成「CloudOps初始配置.xlsx」。

逻辑对齐 CPCIA ``LldToCloudOpsConfig.lld_to_cloudops_config``（无对话/DB/EDM 副作用）。
"""
from __future__ import annotations

import io
from typing import Any, BinaryIO, Callable

import pandas as pd
from openpyxl.reader.excel import load_workbook

from .constants import (
    CloudopsConfigColumns,
    CloudopsConfigSheets,
    LldColumns,
    LldSheets,
)
from .lld_utils import (
    find_start_row,
    is_valid_ip,
    locate_invalid_cells,
    split_string_with_num,
    write_data_to_workbook,
)


class AgentFileContentError(ValueError):
    def __init__(self, message: str, *, report_message: str = "") -> None:
        super().__init__(message)
        self.report_message = report_message or message


class LldToCloudOpsConfig:
    def __init__(
        self,
        *,
        product_specification: str,
        cooling: str = "",
        on_progress: Callable[[str], None] | None = None,
    ) -> None:
        self.product_specification = (product_specification or "").strip()
        self.cooling = (cooling or "").strip()
        self._on_progress = on_progress or (lambda _m: None)
        self.lld_file_name = ""
        self.lld_file_buffer: BinaryIO | None = None
        self.management_ip_map: dict[str, str] = {}
        self.lq_ip_map: dict[str, str] = {}
        self.config_dataframes: dict[str, pd.DataFrame] = {}

    def _report(self, msg: str) -> None:
        self._on_progress(msg)

    def generate(
        self,
        lld_stream: BinaryIO,
        *,
        lld_file_name: str,
        template_path: str,
    ) -> bytes:
        """读取 LLD + 本地模板，返回生成的 xlsx 字节流。"""
        if not self.product_specification:
            raise ValueError("缺少产品型号 product_specification（须为 A2 或 A3）")
        if self.product_specification not in ("A2", "A3"):
            raise ValueError(f"不支持的产品型号: {self.product_specification}")

        self.lld_file_buffer = lld_stream
        self.lld_file_name = lld_file_name or "LLD.xlsx"
        self.management_ip_map = {}
        self.lq_ip_map = {}
        self.config_dataframes = {}

        self._report("正在将 LLD 设计文件补充到 CloudOps 原始配置模板…")

        template_sheets = [
            CloudopsConfigSheets.SERVER_INFO,
            CloudopsConfigSheets.SWITCH_INFO,
            CloudopsConfigSheets.CONNECTION_TABLE,
            CloudopsConfigSheets.VERSION_INFO,
            CloudopsConfigSheets.OS_CONFIG_INFO,
            CloudopsConfigSheets.DISK_PARTITION,
            CloudopsConfigSheets.ROUTER,
            CloudopsConfigSheets.NETWORK_PORT_PANEL_DIAGRAM,
            CloudopsConfigSheets.NPU_MULTI_PLANE_PARTITIONING,
            CloudopsConfigSheets.NPU_RoCE_UDP_PORT,
        ]
        for sheet_name in template_sheets:
            try:
                self.config_dataframes[sheet_name] = pd.read_excel(template_path, sheet_name=sheet_name)
            except Exception:
                pass

        self.fill_server_data()
        self.fill_switch_data()
        self.fill_connection_table_data()

        output_buffer = io.BytesIO()
        workbook = load_workbook(template_path)
        for sheet_name, df in self.config_dataframes.items():
            write_data_to_workbook(df, workbook, sheet_name)
        workbook.save(output_buffer)
        workbook.close()
        return output_buffer.getvalue()

    def write_data_to_file(self, df: pd.DataFrame, sheet_name: str) -> None:
        self.config_dataframes[sheet_name] = df

    def fill_server_data(self) -> None:
        self._report("正在填写服务器信息…")
        param_dict = self.read_lld_param_sheet(
            LldSheets.COMPUTE_NODE_PARAMETER_PLANE_ADDRESS.format(self.product_specification)
        )
        service_dict = self.read_lld_sheet(LldSheets.COMPUTE_NODE_SERVICE_PLANE_ADDRESS)
        management_dict = self.read_lld_sheet(LldSheets.SERVER_MANAGEMENT_ADDRESS)
        control_dict = self.read_lld_sheet(LldSheets.SERVER_MANAGEMENT_CONTROL_ADDRESS)
        if not (service_dict or management_dict or control_dict):
            raise ValueError(
                "LLD 中未找到【管理面地址规划】、【业务面地址规划】、【管存面地址规划】页签，请检查"
            )
        out_band_dict = self.read_lld_sheet(LldSheets.SERVER_OUT_OF_BAND_MANAGEMENT_ADDRESS)
        position_dict = self.read_lld_sheet(LldSheets.DEVICE_LOCATION_INFO)

        assert self.lld_file_buffer is not None
        out_band_lld_df = pd.read_excel(
            self.lld_file_buffer, sheet_name=LldSheets.SERVER_OUT_OF_BAND_MANAGEMENT_ADDRESS
        )
        sheet_name = CloudopsConfigSheets.SERVER_INFO
        config_df = self.config_dataframes.get(sheet_name, pd.DataFrame())
        new_rows = []
        for index in out_band_lld_df.index:
            device_name = out_band_lld_df.at[index, LldColumns.DEVICE_NAME]
            param_row = self.fill_param_row(param_dict, device_name)
            management_row = self.fill_management_row(
                service_dict, management_dict, control_dict, device_name
            )
            our_band_row = self.fill_out_band_row(out_band_dict, device_name)
            position_row = self.fill_position_row(position_dict, device_name)
            default_row = self.fill_default_row(device_name)
            new_row = {**default_row, **param_row, **management_row, **our_band_row, **position_row}
            new_rows.append(new_row)
        if new_rows:
            config_df = pd.concat([config_df, pd.DataFrame(new_rows)], ignore_index=True)
        self.write_data_to_file(config_df, sheet_name)

    def fill_switch_data(self) -> None:
        self._report("正在填写交换机信息…")
        out_band_dict = self.read_lld_sheet(LldSheets.LQ_OUT_OF_BAND_MANAGEMENT_ADDRESS)
        position_dict = self.read_lld_sheet(LldSheets.DEVICE_LOCATION_INFO)
        assert self.lld_file_buffer is not None
        out_band_lld_df = pd.read_excel(
            self.lld_file_buffer, sheet_name=LldSheets.LQ_OUT_OF_BAND_MANAGEMENT_ADDRESS, header=0
        )
        sheet_name = CloudopsConfigSheets.SWITCH_INFO
        config_df = self.config_dataframes.get(sheet_name, pd.DataFrame())
        new_rows = []
        for index in out_band_lld_df.index:
            device_name = out_band_lld_df.at[index, LldColumns.DEVICE_NAME]
            device_ip = out_band_dict.get(device_name, {}).get(LldColumns.MANAGEMENT_IP)
            cabinet, counter = split_string_with_num(
                position_dict.get(device_name, {}).get(LldColumns.RACK)
            )
            new_row = {
                CloudopsConfigColumns.DEVICE_ID: device_ip,
                CloudopsConfigColumns.DEVICE_NAME: device_name,
                CloudopsConfigColumns.DEVICE_IP: device_ip,
                CloudopsConfigColumns.MANAGEMENT_USERNAME_SWITCH: "",
                CloudopsConfigColumns.PASSWORD: "",
                CloudopsConfigColumns.SSH_PORT: 22,
                CloudopsConfigColumns.VENDOR: "",
                CloudopsConfigColumns.DEVICE_TYPE: "",
                CloudopsConfigColumns.DATA_CENTER: position_dict.get(device_name, {}).get(
                    LldColumns.DATA_CENTER
                ),
                CloudopsConfigColumns.CABINET: cabinet,
                CloudopsConfigColumns.COUNTER: counter,
                CloudopsConfigColumns.U_POSITION: position_dict.get(device_name, {}).get(
                    LldColumns.START_U
                ),
                CloudopsConfigColumns.U_HEIGHT: "",
                CloudopsConfigColumns.SERIAL_NUMBER: "",
            }
            new_rows.append(new_row)
            if device_ip:
                self.lq_ip_map[device_name] = device_ip
        if new_rows:
            config_df = pd.concat([config_df, pd.DataFrame(new_rows)], ignore_index=True)
        self.write_data_to_file(config_df, sheet_name)

    def load_lld_sheet(self, sheet_name: str) -> pd.DataFrame:
        assert self.lld_file_buffer is not None
        try:
            lld_df = pd.read_excel(self.lld_file_buffer, sheet_name, header=None)
        except ValueError as e:
            if "not found" in str(e):
                return pd.DataFrame()
            return pd.DataFrame()
        start_index = find_start_row(lld_df, LldColumns.DEVICE_NAME)
        if start_index is None:
            return pd.DataFrame()
        header = lld_df.iloc[start_index].tolist()
        lld_df = lld_df.iloc[start_index + 1 :]
        return pd.DataFrame(lld_df.values, columns=header)

    @staticmethod
    def lld_df_to_dict(lld_df: pd.DataFrame, sheet_name: str) -> dict:
        if lld_df.empty:
            return {}
        if lld_df[LldColumns.DEVICE_NAME].duplicated().any():
            duplicates = lld_df[lld_df[LldColumns.DEVICE_NAME].duplicated(keep=False)]
            dup_names = duplicates[LldColumns.DEVICE_NAME].unique()
            raise ValueError(
                f"页签 {sheet_name} 存在重复设备名: {dup_names}，每台设备名称须唯一"
            )
        return lld_df.set_index(LldColumns.DEVICE_NAME).to_dict(orient="index")

    def read_lld_sheet(self, sheet_name: str) -> dict:
        return self.lld_df_to_dict(self.load_lld_sheet(sheet_name), sheet_name)

    def read_lld_param_sheet(self, sheet_name: str) -> dict:
        param_df = self.load_lld_sheet(sheet_name)
        if param_df.empty:
            return {}
        all_valid, invalid_cells = locate_invalid_cells(
            param_df, [LldColumns.PARAMETER_ID_A3, LldColumns.PARAMETER_GATEWAY_A3], is_valid_ip
        )
        if not all_valid:
            raise ValueError(f"{sheet_name} 存在非法 IP 单元格: {invalid_cells}")
        if self.product_specification == "A3":
            param_df = (
                param_df.groupby(LldColumns.DEVICE_NAME)
                .agg(
                    {
                        LldColumns.PARAMETER_ID_A3: lambda x: ",".join(str(v) for v in x),
                        LldColumns.PARAMETER_SUBNET_MASK: "first",
                        LldColumns.PARAMETER_GATEWAY_A3: lambda x: ",".join(str(v) for v in x),
                    }
                )
                .reset_index()
            )
        return self.lld_df_to_dict(param_df, sheet_name)

    def fill_param_row(self, param_dict: dict, device_name: str) -> dict:
        if self.product_specification == "A2":
            try:
                param_gateways = [param_dict.get(device_name, {}).get(LldColumns.PARAMETER_GATEWAY_A2)] * 8
                param_gateway = ",".join(str(x) for x in param_gateways if x is not None)
                param_ips = [
                    param_dict.get(device_name, {}).get(LldColumns.PARAMETER_ID_A2.format(i))
                    for i in range(8)
                ]
                param_ip = ",".join(str(x) for x in param_ips if x is not None)
            except TypeError:
                raise AgentFileContentError(
                    "invalid gateways or param ips for A2",
                    report_message="A2 设备参数面网关或地址填写有误，请检查 LLD",
                )
        else:
            param_gateway = param_dict.get(device_name, {}).get(LldColumns.PARAMETER_GATEWAY_A3)
            param_ip = param_dict.get(device_name, {}).get(LldColumns.PARAMETER_ID_A3)
        param_mask = param_dict.get(device_name, {}).get(LldColumns.PARAMETER_SUBNET_MASK)
        return {
            CloudopsConfigColumns.PARAMETER_IPV4_ADDRESS: param_ip,
            CloudopsConfigColumns.PARAMETER_IPV4_SUBNET_MASK: param_mask,
            CloudopsConfigColumns.PARAMETER_IPV4_GATEWAY: param_gateway,
        }

    def fill_management_row(
        self, service_dict: dict, management_dict: dict, control_dict: dict, device_name: str
    ) -> dict:
        if management_dict:
            address = management_dict.get(device_name, {}).get(LldColumns.SERVER_MANAGEMENT_ADDRESS)
            gateway = management_dict.get(device_name, {}).get(LldColumns.SERVER_MANAGEMENT_GATEWAY)
            subnet_mask = management_dict.get(device_name, {}).get(
                LldColumns.SERVER_MANAGEMENT_SUBNET_MASK
            )
        elif service_dict:
            address = service_dict.get(device_name, {}).get(LldColumns.SERVICE_ADDRESS)
            gateway = service_dict.get(device_name, {}).get(LldColumns.SERVICE_GATEWAY)
            subnet_mask = service_dict.get(device_name, {}).get(LldColumns.SERVICE_SUBNET_MASK)
        elif control_dict:
            address = control_dict.get(device_name, {}).get(LldColumns.MANAGEMENT_CONTROL_ADDRESS)
            gateway = control_dict.get(device_name, {}).get(LldColumns.MANAGEMENT_CONTROL_GATEWAY)
            subnet_mask = control_dict.get(device_name, {}).get(
                LldColumns.MANAGEMENT_CONTROL_SUBNET_MASK
            )
        else:
            raise ValueError(
                "LLD 中未找到【管理面地址规划】、【业务面地址规划】、【管存面地址规划】页签"
            )
        if address:
            self.management_ip_map[device_name] = address
        return {
            CloudopsConfigColumns.MANAGEMENT_IPV4_ADDRESS: address,
            CloudopsConfigColumns.MANAGEMENT_USERNAME: "",
            CloudopsConfigColumns.MANAGEMENT_PASSWORD: "",
            CloudopsConfigColumns.ROOT_PASSWORD: "",
            CloudopsConfigColumns.SSH_SFTP_PORT: 22,
            CloudopsConfigColumns.MANAGEMENT_IPV4_GATEWAY: gateway,
            CloudopsConfigColumns.MANAGEMENT_IPV4_SUBNET_MASK: subnet_mask,
        }

    @staticmethod
    def fill_out_band_row(out_band_dict: dict, device_name: str) -> dict:
        """对齐 Agent ``fill_out_band_row``（IBMC-IP地址，不再写入 IBMC-IPV4地址 列）。"""
        return {
            CloudopsConfigColumns.DEVICE_ID: out_band_dict.get(device_name, {}).get(
                LldColumns.MANAGEMENT_IP
            ),
            CloudopsConfigColumns.IBMC_IP_ADDRESS: out_band_dict.get(device_name, {}).get(
                LldColumns.MANAGEMENT_IP
            ),
            CloudopsConfigColumns.SUPER_NODE_SET_ID: out_band_dict.get(device_name, {}).get(
                LldColumns.SUPER_NODE_ID
            ),
            CloudopsConfigColumns.COMPUTING_SUPER_ID_WITH_SUPER_NODE: out_band_dict.get(
                device_name, {}
            ).get(LldColumns.SWITCH_ID),
            CloudopsConfigColumns.SUPER_NODE_SCALE: out_band_dict.get(device_name, {}).get(
                LldColumns.SUPER_NODE_SCALE
            ),
        }

    @staticmethod
    def fill_position_row(position_dict: dict, device_name: str) -> dict:
        cabinet, counter = split_string_with_num(
            position_dict.get(device_name, {}).get(LldColumns.RACK)
        )
        return {
            CloudopsConfigColumns.DATA_CENTER: position_dict.get(device_name, {}).get(
                LldColumns.DATA_CENTER
            ),
            CloudopsConfigColumns.CABINET: cabinet,
            CloudopsConfigColumns.COUNTER: counter,
            CloudopsConfigColumns.U_POSITION: position_dict.get(device_name, {}).get(
                LldColumns.START_U
            ),
            CloudopsConfigColumns.U_HEIGHT: "",
        }

    @staticmethod
    def fill_default_row(device_name: str) -> dict:
        """对齐 Agent ``fill_default_row``。"""
        return {
            CloudopsConfigColumns.IBMC_IP_ADDRESS: "",
            CloudopsConfigColumns.IBMC_USERNAME: "",
            CloudopsConfigColumns.IBMC_PASSWORD: "",
            CloudopsConfigColumns.IBMC_HTTPS_PORT: 443,
            CloudopsConfigColumns.HOST_NAME: device_name,
            CloudopsConfigColumns.VENDOR: "",
            CloudopsConfigColumns.SERVER_TYPE: "",
            CloudopsConfigColumns.SERVER_MODEL: "",
            CloudopsConfigColumns.SERIAL_NUMBER: "",
        }

    def fill_connection_table_data(self) -> None:
        self._report("正在填写连线表…")
        sheet_name = CloudopsConfigSheets.CONNECTION_TABLE
        config_df = self.config_dataframes.get(sheet_name, pd.DataFrame())
        assert self.lld_file_buffer is not None
        lld_sheets = pd.ExcelFile(self.lld_file_buffer).sheet_names
        required_sheets = [s for s in lld_sheets if "端口互联" in s]
        server_sheets = [
            s for s in required_sheets if "计算" in s or "样本面" in s or "参数面" in s
        ]
        lq_sheets = [s for s in required_sheets if "超平面" in s or "灵衢" in s]

        server_connection_df = self.concat_connection_sheets(server_sheets)
        switch_connection_df = self.concat_connection_sheets(lq_sheets)
        left_column_name = f"{LldColumns.START_INFO}_{LldColumns.DEVICE_NAME_CONNECTION}"

        lld_server_ip = pd.DataFrame(
            self.management_ip_map.items(),
            columns=[LldColumns.DEVICE_NAME, LldColumns.MANAGEMENT_IP],
        )
        server_connection_df = pd.merge(
            server_connection_df,
            lld_server_ip,
            how="left",
            left_on=left_column_name,
            right_on=LldColumns.DEVICE_NAME,
        )
        lld_switch_ip = pd.DataFrame(
            self.lq_ip_map.items(),
            columns=[LldColumns.DEVICE_NAME, LldColumns.MANAGEMENT_IP],
        )
        switch_connection_df = pd.merge(
            switch_connection_df,
            lld_switch_ip,
            how="left",
            left_on=left_column_name,
            right_on=LldColumns.DEVICE_NAME,
        )

        server_config_df = self.fill_connection_table_to_cloudops(config_df, server_connection_df)
        switch_config_df = self.fill_connection_table_to_cloudops(config_df, switch_connection_df)
        config_df = pd.concat([server_config_df, switch_config_df], ignore_index=True)

        required_columns = [
            CloudopsConfigColumns.SERVER_SWITCH_NAME,
            CloudopsConfigColumns.MANAGEMENT_IP,
            CloudopsConfigColumns.SOURCE_INTERFACE_NAME,
            CloudopsConfigColumns.SOURCE_INTERFACE_PHYSICAL_POSITION,
            CloudopsConfigColumns.SOURCE_INTERFACE_PANEL_LAYOUT,
            CloudopsConfigColumns.DESTINATION_SWITCH_NAME,
            CloudopsConfigColumns.DESTINATION_INTERFACE_NAME,
            CloudopsConfigColumns.DESTINATION_INTERFACE_PHYSICAL_POSITION,
            CloudopsConfigColumns.DESTINATION_INTERFACE_PANEL_LAYOUT,
        ]
        config_df = config_df[required_columns]
        self.write_data_to_file(config_df, sheet_name)

    def concat_connection_sheets(self, sheet_names: list[str]) -> pd.DataFrame:
        assert self.lld_file_buffer is not None
        connection_df_list = []
        for sheet in sheet_names:
            index = find_start_row(
                pd.read_excel(self.lld_file_buffer, sheet_name=sheet, header=None),
                LldColumns.START_INFO,
            )
            if index is None:
                continue
            connection_df = pd.read_excel(
                self.lld_file_buffer, sheet_name=sheet, header=[index, index + 1]
            )
            connection_df.columns = ["_".join(str(c).strip() for c in col).strip() for col in connection_df.columns.values]
            connection_df_list.append(
                connection_df[
                    [
                        f"{LldColumns.START_INFO}_{LldColumns.DEVICE_NAME_CONNECTION}",
                        f"{LldColumns.START_INFO}_{LldColumns.INTERFACE_INFO}",
                        f"{LldColumns.END_INFO}_{LldColumns.DEVICE_NAME_CONNECTION}",
                        f"{LldColumns.END_INFO}_{LldColumns.INTERFACE_INFO}",
                    ]
                ]
            )
        if not connection_df_list:
            return pd.DataFrame(
                columns=[
                    f"{LldColumns.START_INFO}_{LldColumns.DEVICE_NAME_CONNECTION}",
                    f"{LldColumns.START_INFO}_{LldColumns.INTERFACE_INFO}",
                    f"{LldColumns.END_INFO}_{LldColumns.DEVICE_NAME_CONNECTION}",
                    f"{LldColumns.END_INFO}_{LldColumns.INTERFACE_INFO}",
                    LldColumns.MANAGEMENT_IP,
                ]
            )
        return pd.concat(connection_df_list)

    @staticmethod
    def fill_connection_table_to_cloudops(config_df: pd.DataFrame, connection_df: pd.DataFrame) -> pd.DataFrame:
        config_df_copy = config_df.copy()
        if connection_df.empty:
            return config_df_copy
        config_df_copy[CloudopsConfigColumns.SERVER_SWITCH_NAME] = connection_df[
            f"{LldColumns.START_INFO}_{LldColumns.DEVICE_NAME_CONNECTION}"
        ]
        config_df_copy[CloudopsConfigColumns.SOURCE_INTERFACE_NAME] = connection_df[
            f"{LldColumns.START_INFO}_{LldColumns.INTERFACE_INFO}"
        ]
        config_df_copy[CloudopsConfigColumns.DESTINATION_SWITCH_NAME] = connection_df[
            f"{LldColumns.END_INFO}_{LldColumns.DEVICE_NAME_CONNECTION}"
        ]
        config_df_copy[CloudopsConfigColumns.DESTINATION_INTERFACE_NAME] = connection_df[
            f"{LldColumns.END_INFO}_{LldColumns.INTERFACE_INFO}"
        ]
        if LldColumns.MANAGEMENT_IP in connection_df.columns:
            config_df_copy[CloudopsConfigColumns.MANAGEMENT_IP] = connection_df[
                LldColumns.MANAGEMENT_IP
            ]
        return config_df_copy
