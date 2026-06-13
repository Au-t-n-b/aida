# -*- coding: utf-8 -*-
"""生成 contingency-decision-runtime.html 对象层全量图数据。

读 schema/object-types.json + schema/link-types.json，产出
ontology/contingency-ontology-data.js（window.ONTOLOGY_FULL）。

约束：
- DOMAIN_MAP 必须与 object-types.json 的键集合精确一致（缺/多都报错退出），
  新增对象类型时强制在此显式选择业务域，杜绝手抄枚举漂移。
- 输出确定性：相同 schema 输入 → 字节级相同输出（无时间戳，源指纹用内容 sha1）。

用法（仓库根，无第三方依赖）：
    python ontology/scripts/gen_contingency_graph_data.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # ontology/
OBJECT_TYPES = ROOT / "schema" / "object-types.json"
LINK_TYPES = ROOT / "schema" / "link-types.json"
OUT = ROOT / "contingency-ontology-data.js"

# 业务域（key 与运行大图五列对齐：net/dev/svc/acc/pln；另三域为列外聚簇）
DOMAINS = [
    {"key": "net", "name": "组网①", "color": "#0891b2"},
    {"key": "dev", "name": "设备②", "color": "#d97706"},
    {"key": "svc", "name": "服务③", "color": "#059669"},
    {"key": "acc", "name": "验收④", "color": "#e11d48"},
    {"key": "pln", "name": "计划⑤·排期", "color": "#4f46e5"},
    {"key": "res", "name": "资源·队伍", "color": "#65a30d"},
    {"key": "ctg", "name": "预案·决策", "color": "#7c3aed"},
    {"key": "base", "name": "基础·供应·文档", "color": "#64748b"},
]

# apiName → 域 key。决策绑定的 17 个对象沿用大图五列归属（聚簇贴近各自泳道）。
DOMAIN_MAP = {
    # —— 组网①（4）
    "SoftwareConfig": "net",
    "NetworkConfig": "net",
    "IntegrationVerificationRequirement": "net",
    "ClusterDeviceInventory": "net",
    # —— 设备②（6）
    "EquipmentConfig": "dev",
    "ComponentConfig": "dev",
    "MachineRoomConfig": "dev",
    "EquipmentRoom": "dev",
    "EquipmentArrivalItem": "dev",
    "PodCabinetLayout": "dev",
    # —— 服务③（4）
    "ServiceConfig": "svc",
    "MaintenancePolicy": "svc",
    "SlaRequirement": "svc",
    "ResponsibilityMatrixItem": "svc",
    # —— 验收④（2）
    "AcceptanceStrategy": "acc",
    "TestCase": "acc",
    # —— 计划⑤·排期（12）
    "Milestone": "pln",
    "DeliveryPlanRow": "pln",
    "AdjustmentRequest": "pln",
    "ReworkEvent": "pln",
    "DeliveryBatch": "pln",
    "DeliveryScenario": "pln",
    "SchedulePlanOption": "pln",
    "SchedulePlanVersion": "pln",
    "ScheduleRisk": "pln",
    "PlanScheduleSnapshot": "pln",
    "WorkCalendar": "pln",
    "CalendarException": "pln",
    # —— 资源·队伍（6）
    "ProjectParticipant": "res",
    "ResourceTeam": "res",
    "TeamCapabilityProfile": "res",
    "ActivityTemplate": "res",
    "ActivityResourceAssignment": "res",
    "ActivitySlaEstimate": "res",
    # —— 预案·决策（15）
    "ContingencyPlan": "ctg",
    "PlanUseCase": "ctg",
    "ContingencyChapter": "ctg",
    "ContingencyOutline": "ctg",
    "ChapterNarrative": "ctg",
    "DecisionPoint": "ctg",
    "DecisionRecord": "ctg",
    "EvidenceSource": "ctg",
    "DeliverabilityAssessment": "ctg",
    "GapItem": "ctg",
    "RemediationTask": "ctg",
    "RiskItem": "ctg",
    "AssumptionItem": "ctg",
    "PlanVersionLog": "ctg",
    "RiskRule": "ctg",
    # —— 基础·供应·文档（9）
    "DeliveryProject": "base",
    "DeliveryPod": "base",
    "SupplierCompany": "base",
    "ChangeOrder": "base",
    "ProjectRequirement": "base",
    "ParsedDocumentSection": "base",
    "ConfigurationFile": "base",
    "ContractInfo": "base",
    "ProjectBasicInfo": "base",
}


def first_sentence(text: str, limit: int = 90) -> str:
    text = " ".join((text or "").split())
    for sep in ("。", "；", "."):
        i = text.find(sep)
        if 0 < i < limit:
            return text[: i + 1]
    return text[:limit] + ("…" if len(text) > limit else "")


def summarize_data_type(data_type: object) -> str:
    if not isinstance(data_type, dict):
        return "unknown"

    kind = str(data_type.get("type") or data_type.get("valueType") or "unknown")
    if kind in {"array", "list", "set"}:
        item_type = data_type.get("items") or data_type.get("elementType") or {}
        return f"{kind}<{summarize_data_type(item_type)}>"
    return kind


def summarize_property(name: str, spec: object) -> dict[str, object]:
    if not isinstance(spec, dict):
        return {
            "api": name,
            "name": name,
            "type": "unknown",
            "required": False,
        }

    display_metadata = spec.get("displayMetadata") or {}
    if not isinstance(display_metadata, dict):
        display_metadata = {}
    api_name = str(spec.get("apiName") or name)
    return {
        "api": api_name,
        "name": str(display_metadata.get("displayName") or api_name),
        "type": summarize_data_type(spec.get("dataType") or {}),
        "required": bool(spec.get("required")),
    }


def main() -> int:
    obj_types = json.loads(OBJECT_TYPES.read_text(encoding="utf-8"))
    link_types = json.loads(LINK_TYPES.read_text(encoding="utf-8"))

    schema_keys = set(obj_types)
    mapped_keys = set(DOMAIN_MAP)
    missing = sorted(schema_keys - mapped_keys)
    stale = sorted(mapped_keys - schema_keys)
    if missing or stale:
        if missing:
            print(f"[FAIL] DOMAIN_MAP 缺少 {len(missing)} 个对象类型: {', '.join(missing)}")
        if stale:
            print(f"[FAIL] DOMAIN_MAP 含已不存在的键 {len(stale)} 个: {', '.join(stale)}")
        return 1

    domain_keys = {d["key"] for d in DOMAINS}
    bad_domain = sorted({v for v in DOMAIN_MAP.values() if v not in domain_keys})
    if bad_domain:
        print(f"[FAIL] DOMAIN_MAP 引用未定义域: {', '.join(bad_domain)}")
        return 1

    nodes = []
    for api, spec in obj_types.items():
        dm = spec.get("displayMetadata", {})
        nodes.append(
            {
                "api": api,
                "name": dm.get("displayName") or api,
                "domain": DOMAIN_MAP[api],
                "status": spec.get("status", "ACTIVE"),
                "props": len(spec.get("properties", {})),
                "properties": [
                    summarize_property(name, prop)
                    for name, prop in (spec.get("properties") or {}).items()
                ],
                "desc": first_sentence(dm.get("description") or spec.get("description") or ""),
            }
        )

    links = []
    bad_ref = []
    for api, spec in link_types.items():
        src, dst = spec.get("objectTypeApiName"), spec.get("linkedObjectTypeApiName")
        if src not in schema_keys or dst not in schema_keys:
            bad_ref.append(f"{api}({src}->{dst})")
            continue
        links.append(
            {
                "api": api,
                "name": spec.get("displayMetadata", {}).get("displayName") or api,
                "from": src,
                "to": dst,
                "card": spec.get("cardinality", ""),
                "model": spec.get("relationshipModel", ""),
                "status": spec.get("status", "ACTIVE"),
            }
        )
    if bad_ref:
        print(f"[FAIL] link-types 引用未知对象类型: {', '.join(bad_ref)}")
        return 1

    fingerprint = hashlib.sha1(
        OBJECT_TYPES.read_bytes() + LINK_TYPES.read_bytes()
    ).hexdigest()[:12]

    payload = {
        "source": f"schema/object-types.json + link-types.json @ sha1:{fingerprint}",
        "domains": DOMAINS,
        "nodes": nodes,
        "links": links,
    }
    body = json.dumps(payload, ensure_ascii=False, indent=1)
    out_text = (
        "/* 由 ontology/scripts/gen_contingency_graph_data.py 生成，勿手改；"
        "schema 变更后重跑该脚本。 */\n"
        f"window.ONTOLOGY_FULL = {body};\n"
    )
    OUT.write_text(out_text, encoding="utf-8", newline="\n")
    print(
        f"[OK] {OUT.name}: nodes={len(nodes)} links={len(links)} "
        f"domains={len(DOMAINS)} source=sha1:{fingerprint}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
