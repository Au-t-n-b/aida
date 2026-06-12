"""对外 API：按所选平面生成结果，支持覆盖写入或项目兼容的按平面合并。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from oob_interconnect.l2_engine import run_l2_core
from oob_interconnect.l3_engine import run_l3_core
from oob_interconnect.merge_output import merge_output_by_plane, write_output
from oob_interconnect.plane_config import load_plane_config
from oob_interconnect.trunk_assign import build_used_trunks_per_device

logger = logging.getLogger(__name__)


def _resolve_plane_config(
    plane_config: Optional[dict[str, dict[str, str]]],
    plane_config_path: Optional[str | Path],
) -> dict[str, dict[str, str]]:
    if plane_config:
        return plane_config
    return load_plane_config(plane_config_path)


def resolve_plane_name(cfg: dict[str, dict[str, str]], name: str) -> str:
    """兼容按规划名称或按旧 sheet 名指定平面。"""
    if name in cfg:
        return name
    matches = [plan for plan, val in cfg.items() if val.get("sheet_name") == name]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"'{name}' 对应多个规划名称，请直接指定其中之一: {matches}")
    raise ValueError(f"平面 '{name}' 不在平面配置中。")


def run_l2(
    topology_path: str | Path,
    sheet_name: str,
    resource_path: str | Path,
    output_path: str | Path,
    plane_config: Optional[dict[str, dict[str, str]]] = None,
    plane_config_path: Optional[str | Path] = None,
    access_plan_path: Optional[str | Path] = None,
    trunk_history_path: Optional[str | Path] = None,
    merge_existing: bool = False,
) -> pd.DataFrame:
    """二层互联规划：默认覆盖写入；``merge_existing`` 为 True 时按网络平面替换合并。"""
    cfg = _resolve_plane_config(plane_config, plane_config_path)
    sheet_name = resolve_plane_name(cfg, sheet_name)
    df = run_l2_core(
        str(topology_path),
        sheet_name,
        str(resource_path),
        plane_config=cfg,
        interconnect_history_path=trunk_history_path,
        access_plan_path=access_plan_path,
        trunk_by_device=None,
    )
    if merge_existing:
        df = merge_output_by_plane(output_path, df)
    else:
        write_output(output_path, df)
    logger.info("L2 写入 %s", output_path)
    return df


def run_l3(
    topology_path: str | Path,
    sheet_name: str,
    resource_path: str | Path,
    output_path: str | Path,
    plane_config: Optional[dict[str, dict[str, str]]] = None,
    plane_config_path: Optional[str | Path] = None,
    merge_existing: bool = False,
) -> pd.DataFrame:
    """三层互联规划：默认覆盖写入；``merge_existing`` 为 True 时按网络平面替换合并。"""
    cfg = _resolve_plane_config(plane_config, plane_config_path)
    sheet_name = resolve_plane_name(cfg, sheet_name)
    df = run_l3_core(str(topology_path), sheet_name, str(resource_path), plane_config=cfg)
    if merge_existing:
        df = merge_output_by_plane(output_path, df)
    else:
        write_output(output_path, df)
    logger.info("L3 写入 %s", output_path)
    return df


def _iter_sheets(
    cfg: dict[str, dict[str, str]],
    sheets: Optional[Iterable[str]],
) -> list[str]:
    if not sheets:
        return list(cfg.keys())
    return [resolve_plane_name(cfg, s) for s in sheets]


def run_l2_multi(
    topology_path: str | Path,
    resource_path: str | Path,
    output_path: str | Path,
    sheets: Optional[Iterable[str]] = None,
    plane_config: Optional[dict[str, dict[str, str]]] = None,
    plane_config_path: Optional[str | Path] = None,
    access_plan_path: Optional[str | Path] = None,
    trunk_history_path: Optional[str | Path] = None,
    merge_existing: bool = False,
) -> pd.DataFrame:
    """二层多平面：内存生成并共享 Trunk 占用；可选按平面替换合并旧输出。"""
    cfg = _resolve_plane_config(plane_config, plane_config_path)
    sheet_list = _iter_sheets(cfg, sheets)
    shared = build_used_trunks_per_device(trunk_history_path, access_plan_path)
    parts: list[pd.DataFrame] = []
    for sn in sheet_list:
        parts.append(
            run_l2_core(
                str(topology_path),
                sn,
                str(resource_path),
                plane_config=cfg,
                interconnect_history_path=None,
                access_plan_path=None,
                trunk_by_device=shared,
            )
        )
    merged = pd.concat(parts, axis=0, ignore_index=True)
    if merge_existing:
        merged = merge_output_by_plane(output_path, merged)
    else:
        write_output(output_path, merged)
    logger.info("L2 多平面写入 %s (%d 个)", output_path, len(sheet_list))
    return merged


def run_l3_multi(
    topology_path: str | Path,
    resource_path: str | Path,
    output_path: str | Path,
    sheets: Optional[Iterable[str]] = None,
    plane_config: Optional[dict[str, dict[str, str]]] = None,
    plane_config_path: Optional[str | Path] = None,
    merge_existing: bool = False,
) -> pd.DataFrame:
    """三层多平面：内存合并所选平面；可选按平面替换合并旧输出。"""
    cfg = _resolve_plane_config(plane_config, plane_config_path)
    sheet_list = _iter_sheets(cfg, sheets)
    parts = [
        run_l3_core(str(topology_path), sn, str(resource_path), plane_config=cfg)
        for sn in sheet_list
    ]
    merged = pd.concat(parts, axis=0, ignore_index=True)
    if merge_existing:
        merged = merge_output_by_plane(output_path, merged)
    else:
        write_output(output_path, merged)
    logger.info("L3 多平面写入 %s (%d 个)", output_path, len(sheet_list))
    return merged
