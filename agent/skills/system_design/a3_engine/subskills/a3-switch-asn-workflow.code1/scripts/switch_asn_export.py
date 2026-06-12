"""ASN 汇总导出（严格对齐 a3_switch_asn.a3_switch_loopback_generate 汇总段）。"""

from __future__ import annotations

from typing import Tuple

import pandas as pd

from switch_asn_io import InMemoryGatewayStore, OUTPUT_ASN_SHEET


def _asn_for_excel(value: object):
    """空 ASN 写为 Excel 空单元格（线上导出多为 NaN）。"""
    if value is None:
        return pd.NA
    s = str(value).strip()
    if s == "" or s.upper() == "NA" or s.lower() == "nan":
        return pd.NA
    try:
        return int(s)
    except ValueError:
        return s


def export_asn_dataframe(gateway_store: InMemoryGatewayStore) -> pd.DataFrame:
    gateway_info = gateway_store.query_all()
    filtered_gateway = [record for record in gateway_info if record[6] != "NA"]
    scope = [tpl[3] for tpl in filtered_gateway]
    devices = [tpl[4] for tpl in filtered_gateway]
    asn = [tpl[6] for tpl in filtered_gateway]

    results = []
    for idx, device in enumerate(devices):
        results.append(
            {
                "网络平面": scope[idx],
                "设备名称": device,
                "ASN": _asn_for_excel(asn[idx]),
            }
        )
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(by=["网络平面", "设备名称"], kind="stable").reset_index(drop=True)
    return df


def export_asn_to_excel(df: pd.DataFrame, output_path) -> None:
    df.to_excel(output_path, sheet_name=OUTPUT_ASN_SHEET, index=False)


def _df_to_markdown(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = [
        "| " + " | ".join(str(c) for c in cols) + " |",
        "| " + " | ".join("---" for _ in cols) + " |",
    ]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    return "\n".join(lines)


def markdown_limited(df: pd.DataFrame, max_rows: int = 50) -> Tuple[str, bool]:
    """简易 Markdown 预览（对齐 df_to_markdown_limited 展示语义）。"""
    if df.empty:
        return ("（无 ASN 分配结果）", False)
    exceeded = len(df) > max_rows
    view = df.head(max_rows) if exceeded else df
    return _df_to_markdown(view), exceeded
