# -*- coding: utf-8 -*-
"""subsystem_test 业务参数运行时填充（对齐 Agent api_params_handler）。

从 runtime/params_template_sheets.json 读取页签，补全 execute body 中空字段。
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

_HCCL_MODE_MAP = {"单次性能测试": "single", "长稳性能测试": "long-term"}
_HCCS_DISABLE_MAP = {"开": "FALSE", "关": "TRUE"}
_CLUSTER_MIRROR_MAP = {"复合镜像": "1", "独立镜像": "0"}
_CLUSTER_TEST_MAP = {"单次性能测试": "single", "长稳性能测试": "long-term"}

def _skill_root(skill_dir: str | Path) -> Path:
    return Path(skill_dir).resolve()


def _load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _sheet_first_row(skill_dir: str | Path, sheet_name: str) -> dict[str, str]:
    data = _load_json(_skill_root(skill_dir) / "runtime" / "params_template_sheets.json")
    rows = data.get(sheet_name) if isinstance(data, dict) else None
    if not isinstance(rows, list) or len(rows) < 2:
        return {}
    header = [str(c or "").strip() for c in rows[0]]
    values = rows[1]
    return {
        header[i]: str(values[i] or "").strip()
        for i in range(min(len(header), len(values)))
        if header[i]
    }


def _deep_update(dst: dict[str, Any], src: dict[str, Any]) -> None:
    for key, val in src.items():
        if isinstance(val, dict) and isinstance(dst.get(key), dict):
            _deep_update(dst[key], val)
        else:
            dst[key] = copy.deepcopy(val)


def _cluster_infer_image_config(skill_dir: str | Path, image_type: str) -> dict[str, Any]:
    skill = _skill_root(skill_dir)
    candidates = [
        skill
        / "software_deployment"
        / "9_commission"
        / "shared"
        / "subsystem_params"
        / "config"
        / "cluster_infer"
        / f"{image_type}.json",
        skill / "runtime" / "params" / "cluster_infer" / f"{image_type}.json",
    ]
    for path in candidates:
        data = _load_json(path)
        if isinstance(data, dict):
            return data
    return {}


def enrich_hccl_execute_body(
    skill_dir: str | Path,
    body: dict[str, Any],
    *,
    device_count: int,
) -> dict[str, Any]:
    row = _sheet_first_row(skill_dir, "集合通信")
    hccl = body.setdefault("hcclBaseParam", {})
    if not str(hccl.get("hcclSocketIfname") or "").strip():
        hccl["hcclSocketIfname"] = row.get("HCCL_SOCKET_IFNAME") or "bond0.2"
    body["groupElementSize"] = _resolve_group_size(row.get("GROUP_SIZE"), device_count)
    if row.get("测试方式"):
        hccl["testType"] = _HCCL_MODE_MAP.get(row["测试方式"], hccl.get("testType") or "single")
    if row.get("长稳时长（小时）"):
        hccl["hours"] = row["长稳时长（小时）"]
    if row.get("集合通信算子"):
        hccl["hcclMethod"] = row["集合通信算子"]
    hccs = row.get("HCCS通信开关", "")
    if hccs:
        hccl["hcclInterHccsDisable"] = _HCCS_DISABLE_MAP.get(hccs, hccl.get("hcclInterHccsDisable") or "")
    return body


def _resolve_group_size(raw: Any, device_count: int) -> int:
    try:
        group_size = int(raw or 0)
    except ValueError:
        group_size = 0
    if group_size <= 1:
        return max(device_count, 1)
    if group_size > device_count or device_count % group_size != 0:
        return max(device_count, 1)
    return group_size


def enrich_cluster_train_execute_body(
    skill_dir: str | Path,
    body: dict[str, Any],
    *,
    device_count: int,
) -> dict[str, Any]:
    row = _sheet_first_row(skill_dir, "集群模型")
    body["groupElementSize"] = _resolve_group_size(row.get("分组大小"), device_count)

    image_path = row.get("镜像文件路径（不带文件名）") or "/home/hwtest"
    train = body.setdefault("trainConfigParam", {})
    if not str(train.get("imagePath") or "").strip():
        train["imagePath"] = image_path
    if row.get("测试方式"):
        train["testType"] = _CLUSTER_TEST_MAP.get(row["测试方式"], train.get("testType") or "single")
    if row.get("长稳时长（小时）"):
        try:
            train["hours"] = int(row["长稳时长（小时）"])
        except ValueError:
            pass

    storage = body.setdefault("storageConfigParam", {})
    if row.get("模型名称"):
        storage["imageType"] = row["模型名称"]
    if row.get("AI模型"):
        storage["aiFramework"] = row["AI模型"]
    if row.get("镜像类型"):
        storage["mirrorType"] = _CLUSTER_MIRROR_MAP.get(row["镜像类型"], storage.get("mirrorType") or "0")
    if not str(storage.get("imagePath") or "").strip():
        storage["imagePath"] = image_path
    if not str(storage.get("imageSavePath") or "").strip():
        storage["imageSavePath"] = image_path
    return body


def enrich_cluster_infer_execute_body(skill_dir: str | Path, body: dict[str, Any]) -> dict[str, Any]:
    row = _sheet_first_row(skill_dir, "集群推理")
    image_type = row.get("imageType") or body.get("storageConfigParam", {}).get("imageType") or "llama1-7b"
    try:
        body["groupElementSize"] = int(row.get("group_size") or body.get("groupElementSize") or 2)
    except ValueError:
        body["groupElementSize"] = 2
    body.setdefault("storageConfigParam", {})["imageType"] = image_type
    extra = _cluster_infer_image_config(skill_dir, image_type)
    if extra:
        _deep_update(body, extra)
    return body


def enrich_subsystem_execute_body(
    skill_dir: str | Path,
    task_type: str,
    body: dict[str, Any],
    *,
    device_count: int,
) -> dict[str, Any]:
    if task_type in ("hccl_test_single_pod", "hccl_test"):
        return enrich_hccl_execute_body(skill_dir, body, device_count=device_count)
    if task_type in ("cluster_train_single_pod", "cluster_model_test"):
        return enrich_cluster_train_execute_body(skill_dir, body, device_count=device_count)
    if task_type == "cluster_infer_single_pod":
        body = enrich_cluster_infer_execute_body(skill_dir, body)
        try:
            ges = int(body.get("groupElementSize") or 2)
        except ValueError:
            ges = 2
        body["groupElementSize"] = _resolve_group_size(ges, device_count)
        return body
    return body
