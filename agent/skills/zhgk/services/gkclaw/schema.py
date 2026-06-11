"""
gkclaw schema · 四种 payload + manifest 的契约校验（契约 §9-§14/§17/§19）

全部校验函数返回 list[str]（空 = 通过），不抛异常——调用方据此决定拒发/隔离。
按字符串比较 item key（契约 §6「所有引用建议按字符串值比较」）。
"""
from __future__ import annotations

from typing import Any

from .ids import is_valid_task_id, is_safe_zip_path

SCHEMA_VERSION = "gkclaw.mail.v1"
PACKAGE_TYPES = ("task.dispatch", "task.import_ack", "task.result", "task.error")


def _s(d: dict, key: str) -> str:
    v = d.get(key, "")
    return v.strip() if isinstance(v, str) else ""


def validate_manifest(m: dict[str, Any]) -> list[str]:
    v: list[str] = []
    if _s(m, "schema_version") != SCHEMA_VERSION:
        v.append(f"schema_version 不支持: {m.get('schema_version')!r}（期望 {SCHEMA_VERSION}）")
    if _s(m, "package_type") not in PACKAGE_TYPES:
        v.append(f"package_type 非法: {m.get('package_type')!r}")
    for k in ("package_id", "created_at", "source", "target", "task_id"):
        if not _s(m, k):
            v.append(f"manifest 缺必填字段 {k}")
    checksum = m.get("checksum")
    if not isinstance(checksum, dict) or not checksum:
        v.append("manifest 缺 checksum 映射")
    else:
        for path, digest in checksum.items():
            if not is_safe_zip_path(str(path)):
                v.append(f"checksum 含不安全路径: {path!r}")
            if not str(digest).startswith("sha256:"):
                v.append(f"checksum 值须为 sha256:<hex>: {path}")
    return v


def validate_task(t: dict[str, Any]) -> list[str]:
    v: list[str] = []
    if not is_valid_task_id(_s(t, "task_id")):
        v.append(f"task_id 不合契约正则: {t.get('task_id')!r}")
    if not _s(t, "task_name"):
        v.append("task_name 必填")
    project = t.get("project") or {}
    for k in ("project_id", "project_code", "project_name"):
        if not _s(project, k):
            v.append(f"project.{k} 必填")

    assignees = t.get("assignees") or []
    if not assignees:
        v.append("assignees 至少包含一个人员")
    for a in assignees:
        if not _s(a, "surveyor_name") or not _s(a, "surveyor_code"):
            v.append(f"assignees 成员缺 surveyor_name/surveyor_code: {a!r}")

    items = t.get("items") or []
    if not items:
        v.append("items 至少包含一个工勘项")
    keys: list[str] = []
    for it in items:
        key = _s(it, "问题序号")
        if not key:
            v.append(f"工勘项缺 问题序号: {it.get('勘测项', '')!r}")
            continue
        if key in keys:
            v.append(f"问题序号 {key} 不唯一（任务内必须唯一）")
        keys.append(key)
        if not _s(it, "勘测项"):
            v.append(f"工勘项 {key} 缺 勘测项")
        if not isinstance(it.get("选项列表", []), list):
            v.append(f"工勘项 {key} 选项列表须为数组")
        for img in it.get("示例图") or []:
            if not is_safe_zip_path(_s(img, "path")):
                v.append(f"工勘项 {key} 示例图 path 不安全: {img.get('path')!r}")
    key_set = set(keys)

    clusters = t.get("item_clusters") or []
    if not clusters:
        v.append("item_clusters 正式任务必须非空（无分组也要兜底簇）")
    cluster_ids: set[str] = set()
    covered: set[str] = set()
    for c in clusters:
        cid = _s(c, "cluster_id")
        if not cid:
            v.append(f"簇缺 cluster_id: {c!r}")
        elif cid in cluster_ids:
            v.append(f"cluster_id {cid} 重复")
        cluster_ids.add(cid)
        c_keys = c.get("item_keys") or []
        if not c_keys:
            v.append(f"簇 {cid} item_keys 为空")
        for k in c_keys:
            if str(k) not in key_set:
                v.append(f"簇 {cid} 引用不存在的工勘项 {k}")
            covered.add(str(k))
    for k in keys:
        if k not in covered:
            v.append(f"工勘项 {k} 未出现在任何簇中（每项必须至少入一簇）")

    rule_ids: set[str] = set()
    for r in t.get("dependency_rules") or []:
        rid = _s(r, "rule_id")
        if not rid:
            v.append(f"依赖规则缺 rule_id: {r!r}")
        elif rid in rule_ids:
            v.append(f"rule_id {rid} 重复")
        rule_ids.add(rid)
        if not _s(r, "trigger_semantics"):
            v.append(f"规则 {rid} 缺 trigger_semantics（须写自然语言语义）")
        for field in ("trigger_item_keys", "target_item_keys"):
            for k in r.get(field) or []:
                if str(k) not in key_set:
                    v.append(f"规则 {rid} {field} 引用不存在的工勘项 {k}")
        action = r.get("action") or {}
        if action.get("type") != "mark_not_applicable":
            v.append(f"规则 {rid} action.type 仅支持 mark_not_applicable")
    return v


def validate_ack(a: dict[str, Any]) -> list[str]:
    v: list[str] = []
    for k in ("status", "task_id", "web_access_url"):
        if not _s(a, k):
            v.append(f"ack 缺必填字段 {k}")
    return v


def validate_result(r: dict[str, Any]) -> list[str]:
    v: list[str] = []
    if not _s(r, "task_id"):
        v.append("result 缺 task_id")
    session = r.get("session") or {}
    if not _s(session, "status"):
        v.append("result 缺 session.status（最终性唯一权威字段）")
    submitted = r.get("submitted_by") or {}
    if not _s(submitted, "surveyor_code"):
        v.append("result 缺 submitted_by.surveyor_code")
    if not isinstance(r.get("items", []), list):
        v.append("result items 须为数组")
    return v


def validate_error(e: dict[str, Any]) -> list[str]:
    v: list[str] = []
    for k in ("task_id", "code", "message"):
        if not _s(e, k):
            v.append(f"error 缺必填字段 {k}")
    return v
