"""
Manual + 完工清单 → CloudOps 完整配置。

逻辑对齐 CPCIA ``ChecklistToCloudOpsConfig``（``checklist_file_handler.py``），
无对话 / DB / EDM / work_process 副作用；与 ``lld_to_cloudops.py`` 同为 Skill 内 vendored 实现。
"""
from __future__ import annotations

import io
import os
import re
from typing import Any, Callable

import pandas as pd
from openpyxl import load_workbook

import os
import sys
from pathlib import Path


def _co_constants():
    root = Path(os.environ.get("SD_SKILL_ROOT", Path.cwd())).resolve()
    rt = root / "runtime"
    if str(rt) not in sys.path:
        sys.path.insert(0, str(rt))
    from sd_script_import import import_sd_script  # noqa: WPS433

    c = import_sd_script(root, "4_cloudops_init", "constants")
    u = import_sd_script(root, "4_cloudops_init", "lld_utils")
    return c, u


_c, _u = _co_constants()
CloudopsConfigColumns = _c.CloudopsConfigColumns
CloudopsConfigSheets = _c.CloudopsConfigSheets
DeviceCheckListColumns = _c.DeviceCheckListColumns
SERVER_EXPORT_COLUMNS = _c.SERVER_EXPORT_COLUMNS
SWITCH_EXPORT_COLUMNS = _c.SWITCH_EXPORT_COLUMNS
clear_excel_sheet = _u.clear_excel_sheet
write_data_to_workbook = _u.write_data_to_workbook


def _normalize_device_name(name: str) -> str:
    """Normalize device name for checklist/manual matching.

    The Agent-side logic is tolerant to common naming variants (e.g. `-1` vs `-01`).
    We apply a lightweight normalization so Skill output matches Agent behavior.
    """
    s = str(name or "").strip()
    if not s:
        return ""
    # normalize whitespace and punctuation variants
    s = re.sub(r"\s+", "", s)
    s = s.replace("（", "(").replace("）", ")")
    # normalize trailing numeric segment: `...-01` -> `...-1`
    # only when the last token is purely digits
    m = re.match(r"^(.*?)-(\d+)$", s)
    if m:
        prefix, num = m.group(1), m.group(2)
        try:
            s = f"{prefix}-{int(num)}"
        except Exception:
            pass
    return s


def _resolve_device_name_col(df: pd.DataFrame) -> str | None:
    """Resolve device/switch name column (交换机 sheet 等)。"""
    if df is None or df.empty:
        return None
    candidates = (
        str(CloudopsConfigColumns.DEVICE_NAME),
        str(DeviceCheckListColumns.DEVICE_NAME),
        "设备名称",
    )
    for c in candidates:
        if c in df.columns:
            return c
    for c in df.columns:
        cs = str(c)
        if ("设备" in cs and "名" in cs) or ("device" in cs.lower() and "name" in cs.lower()):
            return str(c)
    return None


def _resolve_server_host_col(df: pd.DataFrame) -> str | None:
    """Resolve server host column（对齐 Agent：主机名称；兼容旧版 设备名称）。"""
    if df is None or df.empty:
        return None
    host_candidates = (
        str(CloudopsConfigColumns.HOST_NAME),
        "主机名称",
        str(CloudopsConfigColumns.DEVICE_NAME_LEGACY_SERVER),
        "设备名称",
    )
    for c in host_candidates:
        if c in df.columns:
            return c
    for c in df.columns:
        cs = str(c)
        if "主机" in cs and "名" in cs:
            return str(c)
        if "设备" in cs and "名" in cs:
            return str(c)
    return None


def _ensure_server_host_column(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure canonical ``主机名称`` exists for server-sheet merge."""
    if df is None or df.empty:
        return df
    if CloudopsConfigColumns.HOST_NAME in df.columns:
        return df
    src = _resolve_server_host_col(df)
    if not src or src == CloudopsConfigColumns.HOST_NAME:
        return df
    out = df.copy()
    out[CloudopsConfigColumns.HOST_NAME] = out[src]
    return out


def _prepare_checklist_for_merge(df: pd.DataFrame) -> pd.DataFrame:
    """Add normalized key column for merge, keeping original `设备名称` intact."""
    if df is None or df.empty:
        return df
    out = df.copy()
    name_col = _resolve_device_name_col(out)
    if name_col:
        out["_sd_device_name_norm"] = out[name_col].map(_normalize_device_name)
    return out


def _prepare_config_for_merge(df: pd.DataFrame) -> pd.DataFrame:
    """Add normalized key column for merge (交换机 sheet：设备名称)。"""
    if df is None or df.empty:
        return df
    out = df.copy()
    name_col = _resolve_device_name_col(out)
    if name_col:
        out["_sd_device_name_norm"] = out[name_col].map(_normalize_device_name)
    return out


def _resolve_merged_checklist_vendor_col(merged: pd.DataFrame) -> str | None:
    """merge 后清单侧「厂家」列（可能与手工表列重名而被加后缀）。"""
    base = DeviceCheckListColumns.VENDOR
    for c in (f"{base}_y", f"{base}__ck", base):
        if c in merged.columns:
            return c
    for c in merged.columns:
        cs = str(c)
        if cs.startswith(str(base)) and cs not in (f"{base}_x",):
            return str(c)
    return None


def _resolve_merged_checklist_name_col(merged: pd.DataFrame) -> str | None:
    """merge 后清单侧「设备名称」列（可能与手工表列重名而被加后缀）。"""
    base = DeviceCheckListColumns.DEVICE_NAME
    for c in (
        f"{base}__ck",
        f"{base}_y",
        base,
    ):
        if c in merged.columns:
            return c
    for c in merged.columns:
        cs = str(c)
        if cs.startswith(str(base)) and cs != f"{base}_x":
            return str(c)
    return None


def _prepare_server_config_for_merge(df: pd.DataFrame) -> pd.DataFrame:
    """Add normalized key for server sheet merge（主机名称 ↔ 清单设备名称）。"""
    if df is None or df.empty:
        return df
    out = _ensure_server_host_column(df.copy())
    host_col = _resolve_server_host_col(out)
    if host_col:
        out["_sd_device_name_norm"] = out[host_col].map(_normalize_device_name)
    return out


def _cell_nonempty(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().ne("") & series.notna()


def _ensure_string_column(df: pd.DataFrame, col: str, default: str = "") -> None:
    """Excel 空列常被 pandas 读成 float64；写入字符串前先统一为 string。"""
    if col not in df.columns:
        df[col] = default
    df[col] = df[col].astype("string").fillna(default)


def _assign_string_series(df: pd.DataFrame, index: pd.Index, col: str, values: pd.Series) -> None:
    _ensure_string_column(df, col)
    df.loc[index, col] = values.astype("string").fillna("").to_list()


def _resolve_ibmc_ip_col(df: pd.DataFrame) -> str | None:
    if df is None or df.empty:
        return None
    for c in (
        str(CloudopsConfigColumns.IBMC_IPV4_ADDRESS),
        str(CloudopsConfigColumns.IBMC_IP_ADDRESS),
        "IBMC-IPV4地址",
        "IBMC-IP地址",
    ):
        if c in df.columns:
            return c
    return None


def _servers_with_credentials(df: pd.DataFrame) -> pd.Series:
    """手工补充已填账号/密码的行（现场实际可调测服务器，不必等全量装机）。"""
    if df is None or df.empty:
        return pd.Series(dtype=bool)
    ibmc_ip = _resolve_ibmc_ip_col(df)
    if not ibmc_ip:
        return pd.Series(False, index=df.index)
    has_ip = _cell_nonempty(df[ibmc_ip])
    user_cols = [CloudopsConfigColumns.IBMC_USERNAME, "IBMC用户名"]
    pwd_cols = [
        CloudopsConfigColumns.IBMC_PASSWORD,
        "IBMC密码",
        CloudopsConfigColumns.MANAGEMENT_PASSWORD,
        "管理网-密码",
    ]
    has_secret = pd.Series(False, index=df.index)
    for c in user_cols + pwd_cols:
        if c in df.columns:
            has_secret = has_secret | _cell_nonempty(df[c])
    return has_ip & has_secret


def _filter_server_rows_for_full_export(df: pd.DataFrame) -> pd.DataFrame:
    """保留：已手工补账号密码的服务器，或已成功填入 SN 的行。"""
    if df is None or df.empty:
        return df
    cred = _servers_with_credentials(df)
    sn_col = CloudopsConfigColumns.SERIAL_NUMBER
    if sn_col in df.columns:
        has_sn = _cell_nonempty(df[sn_col])
        keep = cred | has_sn
    else:
        keep = cred
    return df.loc[keep].copy()


def _filter_switch_rows_for_full_export(df: pd.DataFrame) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype=bool)
    cred = pd.Series(False, index=df.index)
    for c in (CloudopsConfigColumns.PASSWORD, "密码", CloudopsConfigColumns.MANAGEMENT_USERNAME_SWITCH):
        if c in df.columns:
            cred = cred | _cell_nonempty(df[c])
    ip_col = CloudopsConfigColumns.DEVICE_IP
    if ip_col in df.columns:
        cred = cred | _cell_nonempty(df[ip_col])
    sn_col = CloudopsConfigColumns.SERIAL_NUMBER
    if sn_col in df.columns:
        cred = cred | _cell_nonempty(df[sn_col])
    return cred


def _ensure_device_name_column(df: pd.DataFrame, *, col: str = "设备名称") -> pd.DataFrame:
    """Best-effort: ensure the canonical device name column exists.

    Some environments may decode the header in a different encoding, producing mojibake.
    We try to locate a column that contains both '设备' and '名' (or a close variant).
    """
    if df is None or df.empty:
        return df
    if col in df.columns:
        return df
    # heuristic fallback
    for c in df.columns:
        cs = str(c)
        if ("设备" in cs and "名" in cs) or ("device" in cs.lower() and "name" in cs.lower()):
            out = df.copy()
            out[col] = out[c]
            return out
    return df


def get_check_list_df(check_list_paths: list[str]) -> pd.DataFrame:
    """
    合并多份完工清单并去重。

    对齐 CPCIA ``handler/basic_handler/utils.get_check_list_df``（入参改为本地路径列表）。
    跳过缺少「设备名称」「ESN」列的文件（避免把 LLD/CPQ 误当作清单）。
    """
    frames: list[pd.DataFrame] = []
    for path in check_list_paths:
        if not path or not os.path.isfile(path):
            continue
        try:
            df = pd.read_excel(path, sheet_name=0)
        except Exception:
            continue
        if DeviceCheckListColumns.DEVICE_NAME not in df.columns:
            continue
        if DeviceCheckListColumns.SERIAL_NUMBER not in df.columns:
            for alt in ("SN", "sn", "序列号"):
                if alt in df.columns:
                    df = df.rename(columns={alt: DeviceCheckListColumns.SERIAL_NUMBER})
                    break
        if DeviceCheckListColumns.SERIAL_NUMBER not in df.columns:
            continue
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True).drop_duplicates().reset_index(drop=True)
    return out


def _workbook_header_map(ws: Any) -> dict[str, int]:
    header_mapping: dict[str, int] = {}
    for col_idx in range(1, ws.max_column + 1):
        header_value = ws.cell(row=1, column=col_idx).value
        if header_value is not None and str(header_value).strip():
            header_mapping[str(header_value).strip()] = col_idx
    return header_mapping


def _clear_workbook_row(ws: Any, row_idx: int) -> None:
    for col_idx in range(1, ws.max_column + 1):
        ws.cell(row=row_idx, column=col_idx).value = None


def _read_ws_row_credentials_server(ws: Any, row_idx: int, header_map: dict[str, int]) -> bool:
    """按手工表表头读取该行是否已填 iBMC/管理网账号（与 _servers_with_credentials 一致）。"""
    ip_col = None
    for name in (
        str(CloudopsConfigColumns.IBMC_IPV4_ADDRESS),
        str(CloudopsConfigColumns.IBMC_IP_ADDRESS),
        "IBMC-IPV4地址",
        "IBMC-IP地址",
    ):
        if name in header_map:
            ip_col = header_map[name]
            break
    if not ip_col:
        return False
    ip_val = str(ws.cell(row=row_idx, column=ip_col).value or "").strip()
    if not ip_val:
        return False
    user_cols = [CloudopsConfigColumns.IBMC_USERNAME, "IBMC用户名"]
    pwd_cols = [
        CloudopsConfigColumns.IBMC_PASSWORD,
        "IBMC密码",
        CloudopsConfigColumns.MANAGEMENT_PASSWORD,
        "管理网-密码",
    ]
    for names in (user_cols, pwd_cols):
        for ncol in names:
            if ncol in header_map:
                v = str(ws.cell(row=row_idx, column=header_map[ncol]).value or "").strip()
                if v:
                    return True
    return False


def _read_ws_row_credentials_switch(ws: Any, row_idx: int, header_map: dict[str, int]) -> bool:
    for ncol in (CloudopsConfigColumns.PASSWORD, "密码", CloudopsConfigColumns.DEVICE_IP, "设备IP"):
        if ncol in header_map:
            v = str(ws.cell(row=row_idx, column=header_map[ncol]).value or "").strip()
            if v:
                return True
    return False


def _normalize_server_sheet_headers(ws: Any) -> None:
    """将手工表第 1 行表头改为 Agent/Toolkit 识别的列名。"""
    for col_idx in range(1, ws.max_column + 1):
        header = ws.cell(row=1, column=col_idx).value
        if header is None:
            continue
        h = str(header).strip()
        if h == str(CloudopsConfigColumns.IBMC_IPV4_ADDRESS):
            ws.cell(row=1, column=col_idx, value=str(CloudopsConfigColumns.IBMC_IP_ADDRESS))
        elif h in (
            str(CloudopsConfigColumns.DEVICE_NAME_LEGACY_SERVER),
            "设备名称",
        ):
            ws.cell(row=1, column=col_idx, value=str(CloudopsConfigColumns.HOST_NAME))


def _coalesce_column(df: pd.DataFrame, target: str, *sources: str) -> pd.DataFrame:
    """将 sources 中首个非空值合并到 target。"""
    out = df.copy()
    vals: pd.Series | None = None
    for col in (target, *sources):
        if col not in out.columns:
            continue
        s = out[col]
        if vals is None:
            vals = s
            continue
        empty = vals.isna() | vals.astype(str).str.strip().eq("")
        vals = vals.where(~empty, s)
    out[target] = vals if vals is not None else ""
    return out


def _server_df_to_agent_export(df: pd.DataFrame) -> pd.DataFrame:
    """对齐 Agent ``fill_server_info`` 返回列（IBMC-IP地址 / 主机名称）。"""
    if df is None or df.empty:
        return pd.DataFrame(columns=list(SERVER_EXPORT_COLUMNS))
    out = _coalesce_column(
        df,
        str(CloudopsConfigColumns.IBMC_IP_ADDRESS),
        str(CloudopsConfigColumns.IBMC_IPV4_ADDRESS),
        "IBMC-IPV4地址",
        "IBMC-IP地址",
    )
    out = _coalesce_column(
        out,
        str(CloudopsConfigColumns.HOST_NAME),
        str(CloudopsConfigColumns.HOST_NAME),
        str(CloudopsConfigColumns.DEVICE_NAME_LEGACY_SERVER),
        "设备名称",
        "主机名称",
    )
    for col in SERVER_EXPORT_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    return out[list(SERVER_EXPORT_COLUMNS)]


def _switch_df_to_agent_export(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=list(SWITCH_EXPORT_COLUMNS))
    out = df.copy()
    for col in SWITCH_EXPORT_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    return out[list(SWITCH_EXPORT_COLUMNS)]


def _drop_empty_serial_rows(df: pd.DataFrame) -> pd.DataFrame:
    """与 Agent ``dropna(subset=[SN序列号])`` 一致。"""
    if df is None or df.empty:
        return df
    sn = CloudopsConfigColumns.SERIAL_NUMBER
    if sn not in df.columns:
        return df
    mask = _cell_nonempty(df[sn])
    return df.loc[mask].copy()


def _build_export_lookup(
    export_df: pd.DataFrame,
    *,
    primary_key_resolver,
    fallback_key_resolver,
) -> dict[str, dict[str, str]]:
    """primary_key（如 iBMC IP）→ 待写回列值。"""
    if export_df is None or export_df.empty:
        return {}
    pk_col = primary_key_resolver(export_df)
    if not pk_col:
        return {}
    lookup: dict[str, dict[str, str]] = {}
    for _, row in export_df.iterrows():
        key = str(row.get(pk_col) or "").strip()
        if not key:
            fb = fallback_key_resolver(export_df)
            if fb:
                key = str(row.get(fb) or "").strip()
        if not key:
            continue
        payload: dict[str, str] = {}
        sn_col = CloudopsConfigColumns.SERIAL_NUMBER
        if sn_col in export_df.columns:
            payload[sn_col] = str(row.get(sn_col) or "").strip()
        model_col = CloudopsConfigColumns.SERVER_MODEL
        if model_col in export_df.columns:
            payload[model_col] = str(row.get(model_col) or "").strip()
        lookup[key] = payload
    return lookup


def _patch_sheet_preserving_manual_layout(
    workbook: Any,
    sheet_name: str,
    export_df: pd.DataFrame,
    *,
    key_cols: tuple[Any, Any],
) -> None:
    """保留手工 xlsx 第 1 行列结构；仅更新导出行的 SN 等字段，未导出行清空。"""
    if sheet_name not in workbook.sheetnames:
        return
    ws = workbook[sheet_name]
    header_map = _workbook_header_map(ws)
    primary_resolver, fallback_resolver = key_cols
    lookup = _build_export_lookup(
        export_df,
        primary_key_resolver=primary_resolver,
        fallback_key_resolver=fallback_resolver,
    )
    is_server = sheet_name == CloudopsConfigSheets.SERVER_INFO
    ip_header_candidates = (
        str(CloudopsConfigColumns.IBMC_IPV4_ADDRESS),
        str(CloudopsConfigColumns.IBMC_IP_ADDRESS),
        "IBMC-IPV4地址",
        "IBMC-IP地址",
    ) if is_server else (CloudopsConfigColumns.DEVICE_IP, "设备IP")

    for row_idx in range(2, ws.max_row + 1):
        row_cred = (
            _read_ws_row_credentials_server(ws, row_idx, header_map)
            if is_server
            else _read_ws_row_credentials_switch(ws, row_idx, header_map)
        )
        row_key = ""
        for h in ip_header_candidates:
            if h in header_map:
                row_key = str(ws.cell(row=row_idx, column=header_map[h]).value or "").strip()
                if row_key:
                    break
        if not row_key and is_server:
            for h in ("设备名称", "主机名称", str(CloudopsConfigColumns.HOST_NAME)):
                if h in header_map:
                    row_key = str(ws.cell(row=row_idx, column=header_map[h]).value or "").strip()
                    if row_key:
                        break

        if not row_cred and row_key not in lookup:
            _clear_workbook_row(ws, row_idx)
            continue
        if row_key not in lookup:
            if not row_cred:
                _clear_workbook_row(ws, row_idx)
            continue

        payload = lookup.get(row_key, {})
        for col_name, value in payload.items():
            if col_name in header_map and value:
                ws.cell(row=row_idx, column=header_map[col_name]).value = value


class ChecklistToCloudOpsConfig:
    """对齐 CPCIA ``ChecklistToCloudOpsConfig`` 的 SN 填充与写回逻辑。"""

    def __init__(
        self,
        config_file_stream: dict[str, pd.DataFrame],
        *,
        manual_path: str,
        on_progress: Callable[[str], None] | None = None,
    ) -> None:
        self.config_file_stream = config_file_stream
        self.manual_path = manual_path
        self._on_progress = on_progress or (lambda _m: None)

    def _report(self, msg: str) -> None:
        self._on_progress(msg)

    def generate(self, check_list_df: pd.DataFrame) -> bytes:
        """对齐 CPCIA ``fill_serial_number``：填 SN 后按 Agent 列名写回完整配置。"""
        if check_list_df.empty:
            raise ValueError("完工清单中没有数据")

        self._report("正在将设备安装完工清单的 SN 信息填入服务器与交换机 sheet…")
        config_df_server = _server_df_to_agent_export(self.fill_server_info(check_list_df))
        config_df_switch = _switch_df_to_agent_export(self.fill_switch_info(check_list_df))

        filled_sheets = {
            CloudopsConfigSheets.SERVER_INFO: _drop_empty_serial_rows(config_df_server),
            CloudopsConfigSheets.SWITCH_INFO: _drop_empty_serial_rows(config_df_switch),
        }

        output_stream = io.BytesIO()
        workbook = load_workbook(self.manual_path)
        try:
            if CloudopsConfigSheets.SERVER_INFO in workbook.sheetnames:
                _normalize_server_sheet_headers(workbook[CloudopsConfigSheets.SERVER_INFO])
            for sheet_name, config_df in filled_sheets.items():
                clear_excel_sheet(workbook, sheet_name)
                write_data_to_workbook(config_df, workbook, sheet_name)
            workbook.save(output_stream)
        finally:
            workbook.close()

        return output_stream.getvalue()

    def fill_server_info(self, check_list_df: pd.DataFrame) -> pd.DataFrame:
        """合并完工清单 SN（对齐 Agent；设备名规范化以匹配 SP01-1 / SP01-01）。"""
        df = self.config_file_stream.get(CloudopsConfigSheets.SERVER_INFO, pd.DataFrame()).copy()
        if df.empty:
            return df

        work = df.drop(
            columns=[
                CloudopsConfigColumns.SERIAL_NUMBER,
                CloudopsConfigColumns.VENDOR,
                CloudopsConfigColumns.SERVER_TYPE,
            ],
            errors="ignore",
        )
        work = _ensure_server_host_column(work)
        check_list_df = _ensure_device_name_column(
            check_list_df, col=DeviceCheckListColumns.DEVICE_NAME
        )
        ck_cols = [
            c
            for c in (
                DeviceCheckListColumns.DEVICE_NAME,
                DeviceCheckListColumns.SERVER_TYPE,
                DeviceCheckListColumns.VENDOR,
                DeviceCheckListColumns.SERIAL_NUMBER,
                DeviceCheckListColumns.DEVICE_MODEL,
            )
            if c in check_list_df.columns
        ]
        ck = _prepare_checklist_for_merge(check_list_df[ck_cols].copy())
        work = _prepare_server_config_for_merge(work)
        legacy = str(CloudopsConfigColumns.DEVICE_NAME_LEGACY_SERVER)
        if legacy in work.columns and CloudopsConfigColumns.HOST_NAME in work.columns:
            work = work.drop(columns=[legacy], errors="ignore")
        work["_sd_stype"] = "智算"

        merged = pd.merge(
            work,
            ck,
            how="left",
            left_on=["_sd_device_name_norm", "_sd_stype"],
            right_on=["_sd_device_name_norm", DeviceCheckListColumns.SERVER_TYPE],
            suffixes=("", "__ck"),
        )

        esn_col = DeviceCheckListColumns.SERIAL_NUMBER
        if esn_col in merged.columns:
            sn_col = CloudopsConfigColumns.SERIAL_NUMBER
            _assign_string_series(df, merged.index, sn_col, merged[esn_col])
            matched = _cell_nonempty(merged[esn_col])
            ck_name_col = _resolve_merged_checklist_name_col(merged)
            if ck_name_col and matched.any():
                df = _ensure_server_host_column(df)
                _assign_string_series(
                    df,
                    merged.index[matched],
                    CloudopsConfigColumns.HOST_NAME,
                    merged.loc[matched, ck_name_col],
                )
        if DeviceCheckListColumns.DEVICE_MODEL in merged.columns:
            _assign_string_series(
                df,
                merged.index,
                CloudopsConfigColumns.SERVER_MODEL,
                merged[DeviceCheckListColumns.DEVICE_MODEL],
            )
        vendor_col = _resolve_merged_checklist_vendor_col(merged)
        if vendor_col:
            matched_vendor = _cell_nonempty(merged[vendor_col])
            if matched_vendor.any():
                _assign_string_series(
                    df,
                    merged.index[matched_vendor],
                    CloudopsConfigColumns.VENDOR,
                    merged.loc[matched_vendor, vendor_col],
                )
        _ensure_string_column(df, CloudopsConfigColumns.VENDOR)
        _ensure_string_column(df, CloudopsConfigColumns.SERVER_TYPE)
        df.loc[merged.index, CloudopsConfigColumns.SERVER_TYPE] = "智算"

        return df

    def fill_switch_info(self, check_list_df: pd.DataFrame) -> pd.DataFrame:
        df = self.config_file_stream.get(CloudopsConfigSheets.SWITCH_INFO, pd.DataFrame()).copy()
        if df.empty:
            return df

        work = df.drop(columns=[CloudopsConfigColumns.SERIAL_NUMBER], errors="ignore")
        check_list_df = _ensure_device_name_column(check_list_df, col=CloudopsConfigColumns.DEVICE_NAME)
        ck_cols = [
            c
            for c in (
                DeviceCheckListColumns.DEVICE_NAME,
                DeviceCheckListColumns.SERVER_TYPE,
                DeviceCheckListColumns.VENDOR,
                DeviceCheckListColumns.SERIAL_NUMBER,
            )
            if c in check_list_df.columns
        ]
        ck = _prepare_checklist_for_merge(check_list_df[ck_cols].copy())
        work = _prepare_config_for_merge(work)
        work["_sd_stype"] = "交换机"

        merged = pd.merge(
            work,
            ck,
            how="left",
            left_on=["_sd_device_name_norm", "_sd_stype"],
            right_on=["_sd_device_name_norm", DeviceCheckListColumns.SERVER_TYPE],
            suffixes=("", "__ck"),
        )

        esn_col = DeviceCheckListColumns.SERIAL_NUMBER
        if esn_col in merged.columns:
            sn_col = CloudopsConfigColumns.SERIAL_NUMBER
            _assign_string_series(df, merged.index, sn_col, merged[esn_col])
        vendor_col = _resolve_merged_checklist_vendor_col(merged)
        if vendor_col:
            matched_vendor = _cell_nonempty(merged[vendor_col])
            if matched_vendor.any():
                _assign_string_series(
                    df,
                    merged.index[matched_vendor],
                    CloudopsConfigColumns.VENDOR,
                    merged.loc[matched_vendor, vendor_col],
                )
        _ensure_string_column(df, CloudopsConfigColumns.DEVICE_TYPE)
        df.loc[merged.index, CloudopsConfigColumns.DEVICE_TYPE] = "灵衢交换机"

        return df
