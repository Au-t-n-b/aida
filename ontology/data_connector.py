from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from datasource_bindings import load_datasource_bindings, supported_runtime_object_types
from llm_openrouter_backschedule import parse_date
from preview_branch import (
    PreviewBranchUnavailableError,
    apply_object_update_to_dolt,
    get_current_preview_branch,
    get_object_as_of_for_branch,
    get_object_data_for_branch,
    get_object_diff_for_branch,
    get_object_history_for_branch,
    read_delivery_plan_source_rows,
    writeback_overlay_enabled,
)
from schedule_ontology import LocalScheduleOntology


BASE_DIR = Path(__file__).parent
SCHEMA_DIR = BASE_DIR / "schema"
OBJECT_TYPES_PATH = SCHEMA_DIR / "object-types.json"
ACTION_TYPES_PATH = SCHEMA_DIR / "action-types.json"
VALUE_TYPES_PATH = SCHEMA_DIR / "value-types.json"
FUNCTION_TYPES_PATH = SCHEMA_DIR / "function-types.json"
AUTOMATION_TYPES_PATH = SCHEMA_DIR / "automation-types.json"

ZJYD_SOURCE_FILE = "ZJYD 测试项目汪伟_交付计划_20260415171001.csv"
OTT10_SOURCE_FILE = "JD_A3_delivery_plan_20260610.csv"
MILESTONE_SOURCE_FILE = "Milestone.csv"

DELIVERY_PROJECT_OBJECT_TYPE = "DeliveryProject"
DELIVERY_POD_OBJECT_TYPE = "DeliveryPod"
DELIVERY_PLAN_ROW_OBJECT_TYPE = "DeliveryPlanRow"
MILESTONE_OBJECT_TYPE = "Milestone"
ACTIVITY_SLA_ESTIMATE_OBJECT_TYPE = "ActivitySlaEstimate"
SUPPORTED_OBJECT_TYPES = supported_runtime_object_types()


@dataclass(frozen=True)
class ProjectSource:
    project_id: str
    file_name: str
    project_key: str

    @property
    def path(self) -> Path:
        return BASE_DIR / self.file_name


def _project_sources_from_bindings() -> dict[str, ProjectSource]:
    sources: dict[str, ProjectSource] = {}
    for source in load_datasource_bindings().project_sources():
        sources[source.project_id] = ProjectSource(
            source.project_id,
            source.file_name,
            source.project_key,
        )
    return sources


@dataclass(frozen=True)
class ForwardManualOverrideRecord:
    row: Any
    field: str
    original_date: str
    new_date: date
    start_date: date
    end_date: date


class ScheduleMutationSet:
    def __init__(self) -> None:
        self.mutations: list[dict[str, Any]] = []
        self.locked_overrides: set[tuple[str, str]] = set()

    def add_update(
        self,
        target_id: str,
        field: str,
        value: Any,
        *,
        original_date: Any,
        reason: str,
        is_manual_override: bool = False,
    ) -> bool:
        lock_key = (str(target_id), str(field))
        if not is_manual_override and lock_key in self.locked_overrides:
            return False

        self.mutations.append(
            {
                "milestoneId": str(target_id),
                "rowKey": str(target_id),
                "field": str(field),
                "originalDate": str(original_date or ""),
                "newDate": value.isoformat() if isinstance(value, date) else str(value or ""),
                "changeType": _date_change_type(str(field)),
                "reason": reason,
            }
        )
        if is_manual_override:
            self.locked_overrides.add(lock_key)
        return True


PROJECT_SOURCES: dict[str, ProjectSource] = _project_sources_from_bindings()

MILESTONE_TARGET_RULES: dict[str, dict[str, Any]] = {
    "POWER_ON": {
        "name_substrings": ["上电"],
        "match_all": True,
    },
    "ARRIVAL": {
        "name_substrings": ["到货"],
        "pick": "max_end",
    },
    "CLUSTER_DEBUG": {
        "name_substrings": ["集群性能调优"],
        "match_all": True,
    },
}

FORWARD_MILESTONE_TARGET_RULES: dict[str, dict[str, Any]] = {
    "ROOM_IMPLEMENTATION_DONE": {
        "name_substrings": ["机房改造实施"],
        "match_all": True,
    },
    "ARRIVAL": {
        "name_substrings": ["到货"],
        "match_all": True,
    },
}

MILESTONE_COMPRESSION_TARGET_ROLE = "MILESTONE_COMPRESSION_TARGET"
DEFAULT_COMPRESSION_BASELINE_MILESTONE_TYPES = ["ARRIVAL"]
LLM_SEMANTIC_PAYLOAD_VERSION = "v1"
STRATEGY_ID_SUPPLY_FRONTLOAD = "supply_frontload"
STRATEGY_ID_TOP3_SLACK = "duration_top3_slack"
STRATEGY_ID_GLOBAL_PROPORTIONAL = "duration_global_proportional"
PLAN_COMPRESSION_STRATEGY_IDS = [
    STRATEGY_ID_SUPPLY_FRONTLOAD,
    STRATEGY_ID_TOP3_SLACK,
    STRATEGY_ID_GLOBAL_PROPORTIONAL,
]
PLAN_COMPRESSION_TOOL_NAMES = {
    STRATEGY_ID_SUPPLY_FRONTLOAD: "preview_plan_supply_shift",
    STRATEGY_ID_TOP3_SLACK: "preview_plan_top3_slack_compression",
    STRATEGY_ID_GLOBAL_PROPORTIONAL: "preview_plan_global_proportional_compression",
}
STRATEGY_CHAR_LIMIT = 1800


def get_unified_backing_data():
    """Return the union of raw project CSV files.

    Pandas is used here when installed to preserve the original helper's shape.
    The API implementation below does not depend on this function.
    """
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("pandas is required for get_unified_backing_data().") from exc

    frames = []
    for source in PROJECT_SOURCES.values():
        frame = pd.read_csv(source.path)
        frame["sourceFile"] = source.file_name
        if "project_id" not in frame.columns:
            frame["project_id"] = source.project_id
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def get_object_data(object_type: str, project_id: str | None = None) -> list[dict[str, Any]]:
    """Read object data through the local ontology facade."""
    _ensure_supported_object_type(object_type)
    registry = load_datasource_bindings()
    binding = registry.object_type(object_type)
    preview_context = get_current_preview_branch()
    # Serve backing object types from Dolt when on a preview branch, or on main when
    # the Foundry-style writeback overlay is enabled (Dolt main = pipeline ⊕ edits).
    if binding.has_backing_data and (not preview_context.is_main or writeback_overlay_enabled()):
        project_key = _select_sources(project_id)[0].project_key if project_id else None
        rows = get_object_data_for_branch(preview_context, object_type, project_key=project_key)
        if object_type == DELIVERY_PLAN_ROW_OBJECT_TYPE:
            return _apply_effective_sla_to_plan_row_items(rows, project_id)
        return rows
    if binding.reader == "metadata_only":
        # Writable metadata_only objects are run-record types (e.g. RiskItem/GapItem materialized
        # by writeback:run_record Actions): serve their run-record overlay so adopted records are
        # queryable. Pure metadata objects have no overlay file and stay empty.
        if not binding.writable:
            return []
        overlay = _read_contingency_runrecord(object_type)
        key = str(project_id or "").strip()
        return [row for row in overlay if str(row.get("projectKey") or "").strip() == key] if key else overlay
    if binding.reader == "derived_project":
        return _get_delivery_project_data(project_id)
    if binding.reader == "derived_pod":
        return _get_delivery_pod_data(project_id)
    if binding.reader == "csv_table" and object_type == MILESTONE_OBJECT_TYPE:
        return _get_milestone_data(project_id)
    if binding.reader == "json_sections":
        return _get_json_section_data(registry.sources_for_object_type(object_type), project_id)
    if binding.reader == "json_rows":
        return _get_json_rows_data(registry.sources_for_object_type(object_type), project_id)
    if binding.reader == "csv_table":
        return _get_csv_table_data(object_type, registry.sources_for_object_type(object_type), project_id)
    if binding.reader == "dolt_rows":
        # Dolt is the single source of truth: read rows straight from the Dolt table (+ run-record
        # overlay), no committed CSV/JSON in the read path. Degrades to [] when Dolt is unreachable
        # (read_dolt_object_rows), so offline/CI never errors. Project-scoped rows are filtered here
        # when a project_id is supplied; otherwise all rows flow through (derive filters downstream).
        rows = contingency_object_data(object_type)
        key = str(project_id or "").strip()
        return _filter_rows_by_project_key(rows, key) if key else rows
    if binding.reader != "csv_plan_rows":
        raise NotImplementedError(f"Datasource reader `{binding.reader}` is not implemented for `{object_type}`.")

    sources = _select_sources(project_id)

    rows: list[dict[str, Any]] = []
    for source in sources:
        ontology = _load_ontology(source, use_effective_sla=(object_type == DELIVERY_PLAN_ROW_OBJECT_TYPE))
        for row in ontology.objects.DeliveryPlanRow.all():
            item = _json_safe(row.to_schema_object())
            item["sourceFile"] = source.file_name
            rows.append(item)
    return rows


def read_dolt_object_rows(object_type: str, object_schema: dict[str, Any]) -> list[dict[str, Any]]:
    """Read all rows for a metadata-only ontology ObjectType from its Dolt table.

    This is the read path for non-default (metadata-only) ontologies whose data was
    loaded into Dolt out-of-band — e.g. the delivery-contingency-plan proposal output
    tables loaded by bak/load_excel_to_dolt.py. Degrades to [] when Dolt is unreachable
    or the backing table is absent, so the API never errors just because the substrate
    is offline (mirrors the graceful behaviour of the default readers).
    """
    try:
        from dolt_schema_sync import (
            _resolve_engine,
            _sql_text,
            object_type_table_name,
            quote_ident,
        )

        engine = _resolve_engine(None)
        if engine is None:
            return []
        table_name = object_type_table_name(object_type, object_schema)
        with engine.connect() as conn:
            result = conn.execute(_sql_text(f"SELECT * FROM {quote_ident(table_name)}"))
            mappings = result.mappings().all()
        return [_json_safe(dict(row)) for row in mappings]
    except Exception:
        return []


def _require_dolt_history_context(object_type: str) -> Any:
    """Resolve the Dolt branch context for a history / time-travel read.

    History only exists on the Dolt path. Two ObjectType classes qualify, mirroring the
    read routing in ``get_object_data``:
      * Dolt-backed writable objects (ChangeOrder / SupplierCompany) live in Dolt
        unconditionally — available on any context.
      * Backing objects (DeliveryPlanRow / Milestone / ...) resolve to Dolt only on a
        preview branch, or on main with the writeback overlay enabled; otherwise they
        are read from CSV, which has no version history.
    Anything else raises the same unavailable error the writeback path uses (surfaced as
    a clear 503 by the route layer).
    """
    _ensure_supported_object_type(object_type)
    context = get_current_preview_branch()
    if _is_dolt_backed_writable(object_type):
        return context
    binding = load_datasource_bindings().object_type(object_type)
    if binding.has_backing_data and (not context.is_main or writeback_overlay_enabled()):
        return context
    raise PreviewBranchUnavailableError(
        f"Object type `{object_type}` has no Dolt-backed history on this context: send a "
        "Preview-Branch-Id header or enable DOLT_WRITEBACK_OVERLAY (CSV-backed reads have "
        "no version history)."
    )


def _history_project_key(project_id: str | None) -> str | None:
    return _select_sources(project_id)[0].project_key if project_id else None


def get_object_history(
    object_type: str,
    primary_key: dict[str, Any],
    *,
    project_id: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Every committed version of one object, newest first (Dolt history read side)."""
    context = _require_dolt_history_context(object_type)
    return get_object_history_for_branch(
        context,
        object_type,
        primary_key,
        project_key=_history_project_key(project_id),
        limit=limit,
    )


def get_object_as_of(
    object_type: str,
    ref: str,
    *,
    primary_key: dict[str, Any] | None = None,
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """Object rows as of a commit / timestamp / branch ref (Dolt time-travel)."""
    context = _require_dolt_history_context(object_type)
    return get_object_as_of_for_branch(
        context,
        object_type,
        ref,
        primary_key=primary_key,
        project_key=_history_project_key(project_id),
    )


def get_object_diff(
    object_type: str,
    from_ref: str,
    to_ref: str,
    primary_key: dict[str, Any],
    *,
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """Field-level diff of one object between two refs (Dolt commit-diff)."""
    context = _require_dolt_history_context(object_type)
    return get_object_diff_for_branch(
        context,
        object_type,
        from_ref,
        to_ref,
        primary_key,
        project_key=_history_project_key(project_id),
    )


def _acting_user_author(payload: dict[str, Any]) -> str | None:
    """Map an Action's acting user to a Dolt ``--author`` string, or None.

    The user is injected by the route layer from the ``X-Acting-User`` header. Dolt
    expects ``"Name <email>"``; a value already in that form is used as-is, a bare name
    is wrapped with a synthetic address so the committer is still attributable.
    """
    raw = str(payload.get("actingUser") or payload.get("_acting_user") or "").strip()
    if not raw:
        return None
    if "<" in raw and ">" in raw:
        return raw
    return f"{raw} <{raw}@ontology.local>"


def get_linked_object_data(
    object_type: str,
    primary_key: str,
    link_type: str,
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """Resolve local ontology Link Types into linked object payloads."""
    _ensure_supported_object_type(object_type)
    if link_type != "PlanRowDependencies":
        raise NotImplementedError(f"Link traversal is not implemented for `{link_type}`.")
    if object_type != DELIVERY_PLAN_ROW_OBJECT_TYPE:
        raise ValueError(f"Link `{link_type}` must start from DeliveryPlanRow.")

    source = _source_for_object_key(object_type, primary_key, project_id)
    ontology = _load_ontology(source, use_effective_sla=True)
    row = ontology.objects.DeliveryPlanRow.get_or_none(primary_key)
    if row is None:
        raise KeyError(f"DeliveryPlanRow rowKey not found: {primary_key}")

    linked: list[dict[str, Any]] = []
    for dependency in row.depends_on():
        item = _json_safe(dependency.to_schema_object())
        item["sourceFile"] = source.file_name
        linked.append(item)
    return linked


def _safe_parse_date(value: str) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return parse_date(text)
    except (ValueError, TypeError):
        return None


def project_plan_summary(project_id: str) -> dict[str, Any]:
    """Read-only derived Function: high-level metrics for one delivery project.

    Pure and deterministic — computed from current object data, not stored. This is
    the kind of derived logic that previously only lived inside skills; here it is a
    registered ontology Function executable by name through the generic executor.
    """
    project_key = str(project_id or "").strip()
    if not project_key:
        raise ValueError("project_id is required.")

    plan_rows = get_object_data(DELIVERY_PLAN_ROW_OBJECT_TYPE, project_key)
    milestones = get_object_data(MILESTONE_OBJECT_TYPE, project_key)
    pods = get_object_data(DELIVERY_POD_OBJECT_TYPE, project_key)

    scheduled = 0
    start_dates: list[date] = []
    end_dates: list[date] = []
    for row in plan_rows:
        start_text = str(row.get("startDate") or "").strip()
        end_text = str(row.get("endDate") or "").strip()
        if start_text and end_text:
            scheduled += 1
        parsed_start = _safe_parse_date(start_text)
        if parsed_start is not None:
            start_dates.append(parsed_start)
        parsed_end = _safe_parse_date(end_text)
        if parsed_end is not None:
            end_dates.append(parsed_end)

    activity_count = len(plan_rows)
    return {
        "projectId": project_key,
        "activityCount": activity_count,
        "milestoneCount": len(milestones),
        "podCount": len(pods),
        "scheduledActivityCount": scheduled,
        "unscheduledActivityCount": activity_count - scheduled,
        "planStartDate": min(start_dates).isoformat() if start_dates else "",
        "planEndDate": max(end_dates).isoformat() if end_dates else "",
    }


def _milestone_is_met(milestone: dict[str, Any]) -> bool:
    return str(milestone.get("actualDate") or "").strip() != ""


def project_decision_points(project_id: str) -> dict[str, Any]:
    """Derived decision layer: DecisionPoints as a *view* over Milestone gates.

    Palantir-first / derive-don't-hand-author: there is no decision-types.json table.
    A DecisionPoint is computed from each Milestone plus its dependencyMilestoneTypes
    over the existing typed substrate. gateStatus is MET (milestone has actualDate),
    OPEN (no unmet upstream), or BLOCKED (upstream gate(s) missing/not met).
    """
    project_key = str(project_id or "").strip()
    if not project_key:
        raise ValueError("project_id is required.")

    milestones = get_object_data(MILESTONE_OBJECT_TYPE, project_key)
    by_type: dict[str, list[dict[str, Any]]] = {}
    for milestone in milestones:
        by_type.setdefault(str(milestone.get("milestoneType", "")).strip(), []).append(milestone)

    points: list[dict[str, Any]] = []
    status_counts = {"MET": 0, "OPEN": 0, "BLOCKED": 0}
    for milestone in milestones:
        dependency_types = [
            part.strip()
            for part in re.split(r"[,，]", str(milestone.get("dependencyMilestoneTypes") or ""))
            if part.strip()
        ]
        blockers: list[dict[str, Any]] = []
        for dependency_type in dependency_types:
            upstream = by_type.get(dependency_type) or []
            if not upstream:
                blockers.append({"dependencyType": dependency_type, "reason": "missing"})
            elif not all(_milestone_is_met(item) for item in upstream):
                blockers.append({"dependencyType": dependency_type, "reason": "not_met"})

        if _milestone_is_met(milestone):
            gate_status = "MET"
        elif blockers:
            gate_status = "BLOCKED"
        else:
            gate_status = "OPEN"
        status_counts[gate_status] += 1

        points.append(
            {
                "decisionPointKey": f"DP::{milestone.get('milestoneKey', '')}",
                "milestoneKey": milestone.get("milestoneKey", ""),
                "milestoneType": milestone.get("milestoneType", ""),
                "milestoneName": milestone.get("milestoneName", ""),
                "scopeType": milestone.get("scopeType", ""),
                "scopeKey": milestone.get("scopeKey", ""),
                "gateDependencyTypes": dependency_types,
                "gateStatus": gate_status,
                "blockers": blockers,
                "plannedDate": milestone.get("plannedDate", ""),
                "actualDate": milestone.get("actualDate", ""),
            }
        )

    return {
        "projectId": project_key,
        "decisionPointCount": len(points),
        "statusCounts": status_counts,
        "actionableGateKeys": [p["decisionPointKey"] for p in points if p["gateStatus"] == "OPEN"],
        "decisionPoints": points,
    }


def project_emergent_risks(project_id: str) -> dict[str, Any]:
    """Derived Emergent layer: surface candidate risks from the typed substrate.

    Read-only suggestions (建议值, user adopts/dismisses), not stored decisions:
    blocked gates from the derived decision points + unscheduled activities.
    """
    project_key = str(project_id or "").strip()
    if not project_key:
        raise ValueError("project_id is required.")

    decision = project_decision_points(project_key)
    risks: list[dict[str, Any]] = []
    for point in decision["decisionPoints"]:
        if point["gateStatus"] == "BLOCKED":
            dependency_text = ", ".join(b["dependencyType"] for b in point["blockers"]) or "上游未满足"
            risks.append(
                {
                    "type": "BLOCKED_GATE",
                    "severity": "HIGH",
                    "milestoneKey": point["milestoneKey"],
                    "message": f"闸门「{point['milestoneName']}」被阻塞，待上游：{dependency_text}。",
                }
            )

    plan_rows = get_object_data(DELIVERY_PLAN_ROW_OBJECT_TYPE, project_key)
    unscheduled = sum(
        1
        for row in plan_rows
        if not (str(row.get("startDate") or "").strip() and str(row.get("endDate") or "").strip())
    )
    if unscheduled:
        risks.append(
            {
                "type": "UNSCHEDULED_ACTIVITIES",
                "severity": "MEDIUM",
                "count": unscheduled,
                "message": f"{unscheduled} 条活动尚未排程（缺开始或结束日期）。",
            }
        )

    return {"projectId": project_key, "riskCount": len(risks), "risks": risks}


# Lifecycle risk points, mirroring the EODS 售前风险识别 rule_point vocabulary. All four lifecycle
# lanes are wired to predicates: EquipmentConfig carries the GA/TR5/EOM/EOS/ESS milestone dates
# (Dolt-backed, single source of truth) and fires EOM/TR5/EOS/ESS; MaintenancePolicy (EOS) and
# ComponentConfig (ESS) remain as additional fact sources for the same risk points.
CONTINGENCY_RISK_POINTS = ("EOM风险", "TR5风险", "EOS风险", "ESS风险")

# ACC-CHK-01 (04 §19.3 验收④): an acceptance-strategy decision rule forward-ported alongside the
# EODS lifecycle lanes. AcceptanceStrategy is a global reusable asset (not ProjectScoped), matched
# against the global RiskRule library by this riskPoint (see RiskRule seed RR-ACC-CHK-01 + the
# RiskPoint value-type enum).
ACCEPTANCE_ARRIVAL_RISK_POINT = "验收到货里程碑缺失风险"

# SVC-WB-01 (04 §19.3 服务③ · 重大): 产品 GA 晚于维保开始日期。 First lane whose facts join two
# substrate types: EquipmentConfig.gaDate × MaintenancePolicy.startDate, matched model ↔
# productModel (the 维保 sheet suffixes a category — 「TaiShan 200 服务器」 — hence prefix match).
GA_MAINTENANCE_RISK_POINT = "产品GA晚于维保开始风险"

# 任务跟踪类 (04 §19.3 TRK · 非阻塞 → 任务列表): standing tracking suggestions. They surface in the
# risks list and the core aggregation (带风险通过 semantics) but bind NO chapter, so no sub-decision
# deliverability index is polluted by a cross-domain tracking item. TRK-04 光模块丢失 is the only
# wired lane (适用范围=所有智算, no precondition); the other four await project attributes (P2/P3).
TRACKING_RISK_POINT_OPTICAL = "光模块丢失风险"
CONTINGENCY_TRACKING_RISK_POINTS = frozenset(
    {
        "海外伙伴维护技能不足风险",
        "首个智算验收标准未确认风险",
        "海外伙伴交付能力不足风险",
        TRACKING_RISK_POINT_OPTICAL,
        "分包商能力不足风险",
    }
)
_ACCEPTANCE_ARRIVAL_CATEGORY = "到货"
# Milestone values treated as empty (18_验收策略表 uses 「—」 as a no-value placeholder).
_EMPTY_MILESTONE_TOKENS = {"", "—", "-", "/", "无", "n/a", "na"}


def _coerce_truthy(value: Any) -> bool:
    """Tolerant truthiness for substrate booleans that may arrive as bool/str/number."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "y", "是", "超eos", "已超eos"}


def _date_fire_evidence(
    row: dict[str, Any],
    field: str,
    threshold: str,
    threshold_label: str,
    comparator: str,
    what: str,
) -> dict[str, Any] | None:
    """Shared date-window fire check → provenance evidence (or None when not fired).

    Evidence shape: {field, value, comparator, threshold, thresholdLabel, reason} — the reason is a
    human-readable 中文 sentence reproducing exactly the comparison the rule engine made, so the
    UI 溯源下钻 can show 为什么命中 without re-deriving. Date strings are ISO (YYYY-MM-DD) so
    lexical comparison matches chronological order.
    """
    value = str(row.get(field) or "").strip()
    if not value:
        return None
    if not (value < threshold if comparator == "<" else value > threshold):
        return None
    relation = "早于" if comparator == "<" else "晚于"
    return {
        "field": field,
        "value": value,
        "comparator": comparator,
        "threshold": threshold,
        "thresholdLabel": threshold_label,
        "reason": f"{what} {value} {relation}{threshold_label} {threshold}",
    }


def _maintenance_policy_eos_evidence(
    policy: dict[str, Any], reference_iso: str
) -> dict[str, Any] | None:
    """EOS evidence over a MaintenancePolicy fact (delivery-contingency ontology).

    Faithful to the EODS rule "产品 EOS 早于需覆盖到的时间即为风险", but expressed on
    ontology-native fields: the pre-computed isOverEos flag is authoritative; otherwise the EOS
    date is compared against the maintenance end date (or, lacking it, the reference day).
    Returns fire evidence (see _date_fire_evidence) or None when the policy does not fire.
    """
    if _coerce_truthy(policy.get("isOverEos")):
        return {
            "field": "isOverEos",
            "value": str(policy.get("isOverEos")),
            "comparator": "=",
            "threshold": "真",
            "thresholdLabel": "预计算超期标志",
            "reason": "数据源预判定 isOverEos=真（维保期内产品已超 EOS）",
        }
    end_date = str(policy.get("endDate") or "").strip()
    return _date_fire_evidence(
        policy,
        "eosDate",
        end_date or reference_iso,
        "维保结束日" if end_date else "基准日",
        "<",
        "EOS 日期",
    )


def _risk_subject_label(policy: dict[str, Any]) -> str:
    """Display label for a fired subject, mirroring EODS offering_name(offering_no)."""
    for key in ("productModel", "policyName", "maintenancePolicyId"):
        value = str(policy.get(key) or "").strip()
        if value:
            return value
    return "未命名产品"


def _shift_iso_months(reference_iso: str, months: int) -> str:
    """Return an ISO date shifted by N months (day clamped); EODS system_time_2months analogue."""
    import calendar

    try:
        base = date.fromisoformat(str(reference_iso))
    except (ValueError, TypeError):
        return str(reference_iso)
    total = base.month - 1 + months
    year = base.year + total // 12
    month = total % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return date(year, month, day).isoformat()


def _equipment_eom_evidence(equipment: dict[str, Any], horizon_iso: str) -> dict[str, Any] | None:
    """EOM evidence: product EOM plan falls before the 2-month horizon (EODS eom_time < +2mo)."""
    return _date_fire_evidence(equipment, "eomDate", horizon_iso, "基准日+2月", "<", "EOM 计划")


def _equipment_tr5_evidence(equipment: dict[str, Any], horizon_iso: str) -> dict[str, Any] | None:
    """TR5 evidence: product TR5 plan lies beyond the 2-month horizon (EODS tr5_time > +2mo)."""
    return _date_fire_evidence(equipment, "tr5Date", horizon_iso, "基准日+2月", ">", "TR5 计划")


def _equipment_eos_evidence(equipment: dict[str, Any], reference_iso: str) -> dict[str, Any] | None:
    """EOS evidence over EquipmentConfig: product EOS plan already lies before the reference day."""
    return _date_fire_evidence(equipment, "eosDate", reference_iso, "基准日", "<", "EOS 计划")


def _equipment_ess_evidence(equipment: dict[str, Any], reference_iso: str) -> dict[str, Any] | None:
    """ESS evidence over EquipmentConfig: product ESS (spare-parts/extended support) plan already past."""
    return _date_fire_evidence(equipment, "essDate", reference_iso, "基准日", "<", "ESS 计划")


def _component_ess_evidence(component: dict[str, Any], reference_iso: str) -> dict[str, Any] | None:
    """ESS evidence: component is over its service/support window (EODS parts-lifecycle hit)."""
    if _coerce_truthy(component.get("isOverEss")):
        return {
            "field": "isOverEss",
            "value": str(component.get("isOverEss")),
            "comparator": "=",
            "threshold": "真",
            "thresholdLabel": "预计算超期标志",
            "reason": "数据源预判定 isOverEss=真（部件已超服务/支持窗口）",
        }
    return _date_fire_evidence(component, "eosDate", reference_iso, "基准日", "<", "EOS 日期")


def _policy_matches_equipment_model(policy: dict[str, Any], model: str) -> bool:
    """维保策略 ↔ 设备型号匹配：维保表型号常带类别后缀（「TaiShan 200 服务器」），故等值或前缀命中。"""
    product_model = str(policy.get("productModel") or "").strip()
    return bool(product_model and model) and (
        product_model == model or product_model.startswith(model)
    )


def _equipment_subject_label(equipment: dict[str, Any]) -> str:
    for key in ("equipmentName", "model", "equipmentId"):
        value = str(equipment.get(key) or "").strip()
        if value:
            return value
    return "未命名设备"


def _component_subject_label(component: dict[str, Any]) -> str:
    for key in ("componentName", "componentCode", "componentId"):
        value = str(component.get(key) or "").strip()
        if value:
            return value
    return "未命名部件"


def _acceptance_arrival_evidence(strategy: dict[str, Any]) -> dict[str, Any] | None:
    """ACC-CHK-01 evidence: an AcceptanceStrategy categorised 「到货」 with an empty milestone.

    Faithful to 04 §19.3 验收④ "验收策略分类=到货的验收里程碑为空". AcceptanceStrategy.category is
    free text (not a closed enum), so 「到货」 is matched by normalised equality; the milestone counts
    as empty when blank or a 「—」-style placeholder.
    """
    category = str(strategy.get("category") or "").strip()
    if category != _ACCEPTANCE_ARRIVAL_CATEGORY:
        return None
    milestone = str(strategy.get("acceptanceMilestone") or "").strip()
    if milestone.lower() not in _EMPTY_MILESTONE_TOKENS:
        return None
    return {
        "field": "acceptanceMilestone",
        "value": milestone or "（空）",
        "comparator": "=",
        "threshold": "空",
        "thresholdLabel": "到货类验收必填里程碑",
        "reason": "验收策略分类=到货，但验收里程碑为空（无法形成签收闭环）",
    }


def _subject_key_value(row: dict[str, Any], *keys: str) -> str:
    """First non-empty identifying value of a fired source row (links provenance → 源数据行)."""
    for key in keys:
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _acceptance_subject_label(strategy: dict[str, Any]) -> str:
    for key in ("acceptancePlan", "acceptanceName", "acceptanceStrategyId"):
        value = str(strategy.get(key) or "").strip()
        if value:
            return value
    return "未命名验收方案"


# Properties never surfaced as chapter columns when a chapter declares no explicit fieldOrder
# (primary keys / project scoping / audit / source trace are infrastructure, not report content).
_CHAPTER_FIELD_SYSTEM_EXCLUDE = {
    "projectKey",
    "status",
    "updatedAt",
    "createdAt",
    "updatedBy",
    "createdBy",
    "sourceFile",
    "isSelected",
}


def _derive_chapter_fields_from_schema(
    object_type: str,
    field_order: Any = None,
    field_exclude: Any = None,
) -> list[dict[str, Any]]:
    """Derive a chapter's field projection from its ObjectType schema (name/note from the ontology).

    The single source of truth for a chapter's columns is the bound ObjectType: each field's label
    (`name`) is the property's displayName and its `note` is the property's description — no longer
    hand-authored in contingency_chapters.json. `field_order` (a list of property apiNames) curates
    which columns show and in what order; without it, all non-system properties surface in declaration
    order. `field_exclude` drops extra apiNames. Returns [] when the schema is unavailable, so the
    chapter degrades to its skeleton without a data table.
    """
    schema = _contingency_object_schema(object_type)
    props = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(props, dict):
        return []
    pk = ""
    pks = schema.get("primaryKeyPropertyApiNames")
    if isinstance(pks, list) and pks:
        pk = str(pks[0])
    exclude = set(str(x) for x in (field_exclude or [])) | _CHAPTER_FIELD_SYSTEM_EXCLUDE
    if pk:
        exclude.add(pk)

    def _field(api: str) -> dict[str, Any] | None:
        prop = props.get(api)
        if not isinstance(prop, dict):
            return None
        display = prop.get("displayMetadata") or {}
        return {
            "name": str(display.get("displayName") or api),
            "key": str(api),
            "note": str(display.get("description") or ""),
        }

    fields: list[dict[str, Any]] = []
    if field_order:
        for api in field_order:
            field = _field(str(api))
            if field:
                fields.append(field)
    else:
        for api in props:
            if str(api) in exclude:
                continue
            field = _field(str(api))
            if field:
                fields.append(field)
    return fields


def _contingency_chapter_markers() -> list[dict[str, Any]]:
    """Scan the ontology schema for ObjectTypes that declare a `contingencyChapter` marker.

    Palantir-first / 本体灵活生成: a chapter can live *in the ontology* — an ObjectType carrying a
    `contingencyChapter` block (id/no/decisionId/lane/layout/fieldOrder …) becomes a chapter, so
    adding/marking an ObjectType adds a chapter with no edit to the directory file or this code. Returns
    [] when the schema file is unavailable.
    """
    path = BASE_DIR / _CONTINGENCY_SCHEMA_DIRNAME / "object-types.json"
    try:
        schemas = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    markers: list[dict[str, Any]] = []
    for api_name, schema in (schemas or {}).items():
        if not isinstance(schema, dict):
            continue
        marker = schema.get("contingencyChapter")
        if not isinstance(marker, dict):
            continue
        entry = dict(marker)
        entry["objectType"] = api_name
        entry.setdefault("title", str((schema.get("displayMetadata") or {}).get("displayName") or api_name))
        markers.append(entry)
    return markers


def _chapter_sort_key(entry: dict[str, Any]) -> tuple[int, int]:
    """Directory order: 元数据章首位，其余按 no 升序（与历史目录顺序一致）。"""
    no = str(entry.get("no") or "").strip()
    if no.isdigit():
        return (1, int(no))
    return (0, 0)  # 元数据 / 空序号置顶


def _load_contingency_chapter_directory() -> list[dict[str, Any]]:
    """Build the 交付预案 chapter directory from the ontology (skeleton + schema-derived projection).

    Two sources, merged by chapter id: (1) the ContingencyChapter placement table (reader: json_rows
    over data/contingency/contingency_chapters.json) — a thin skeleton (id/no/title/objectType/
    decisionId/lane/layout + an optional fieldOrder), and (2) any ObjectType that declares a
    `contingencyChapter` marker in object-types.json (so marking a type adds a chapter). For every
    chapter bound to an ObjectType, the field projection is *derived from that ObjectType's schema*
    (_derive_chapter_fields_from_schema) rather than hand-authored — the labels/notes come from the
    ontology. Markers win on overlapping keys. Degrades to [] when both sources are unavailable.
    """
    try:
        rows = [row for row in get_object_data("ContingencyChapter") if isinstance(row, dict)]
    except (OSError, ValueError, KeyError):
        rows = []
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        cid = str(row.get("id") or "").strip()
        if cid:
            by_id[cid] = dict(row)
    # Ontology-resident chapters (marker) augment / add to the placement table (marker wins).
    for marker in _contingency_chapter_markers():
        cid = str(marker.get("id") or "").strip()
        if not cid:
            continue
        if cid in by_id:
            by_id[cid].update({k: v for k, v in marker.items() if v is not None})
        else:
            by_id[cid] = dict(marker)
    directory: list[dict[str, Any]] = []
    for entry in by_id.values():
        object_type = str(entry.get("objectType") or "").strip()
        if object_type:
            derived = _derive_chapter_fields_from_schema(
                object_type, entry.get("fieldOrder"), entry.get("fieldExclude")
            )
            if derived:
                entry["fields"] = derived
        directory.append(entry)
    directory.sort(key=_chapter_sort_key)
    return directory


# --------------------------------------------------------------------- ad-hoc chapters (doc-ot-*)

# 临时章：拖拽组装器把任意业务 ObjectType 拖入章节目录时使用 id = doc-ot-<apiName>。骨架
# （title/desc/字段投影）按 id 读时现场派生（与 marker 章同源 _derive_chapter_fields_from_schema），
# 持久层只有 ContingencyOutline.include/order 里的 id 本身 —— materialize 是 id 的纯函数，无独立状态。
_ADHOC_CHAPTER_PREFIX = "doc-ot-"

# 原则：章是「业务事实的投影」，运行时/机制/元类型不作章。RiskItem 虽形似业务类型，但设计口径
# 已弃用（风险建议移交下游风险管理模块）；PlanVersionLog 属预案文档元数据（元数据章已删，不再回流成章）。
_ADHOC_OBJECT_TYPE_DENYLIST = {
    "ContingencyChapter",        # 章节骨架本身
    "ContingencyOutline",        # 裁剪 overlay
    "ContingencyPlan",           # 预案实例 run-record
    "ChapterNarrative",          # 章节正文 run-record
    "DeliverabilityAssessment",  # 可交付性评估 run-record
    "DecisionPoint",             # 决策模型
    "DecisionRecord",            # 决策留痕
    "RiskRule",                  # 风险规则库（机制）
    "RiskItem",                  # 设计已弃用：风险建议移交下游风险管理模块
    "EvidenceSource",            # 推导溯源机制
    "ParsedDocumentSection",     # 文档解析中间产物
    "PlanScheduleSnapshot",      # 排期快照机制
    "PlanVersionLog",            # 预案版本台账（文档元数据）
}


def _adhoc_object_type(chapter_id: str) -> str:
    """doc-ot-<apiName> → apiName；非临时章 id 返回 ''。"""
    cid = str(chapter_id or "").strip()
    if cid.startswith(_ADHOC_CHAPTER_PREFIX):
        return cid[len(_ADHOC_CHAPTER_PREFIX):]
    return ""


def _directory_bound_object_types(directory: list[dict[str, Any]] | None = None) -> set[str]:
    """ObjectTypes already projected by a directory chapter (those re-enter via their own chapter id)."""
    entries = directory if directory is not None else _load_contingency_chapter_directory()
    return {
        str(entry.get("objectType") or "").strip()
        for entry in entries
        if str(entry.get("objectType") or "").strip()
    }


def _adhoc_eligible(api_name: str, bound_types: set[str]) -> bool:
    """该 ObjectType 是否可拖入成临时章：在 schema 里声明、非机制类型、未被目录章绑定。"""
    if not api_name or api_name in _ADHOC_OBJECT_TYPE_DENYLIST or api_name in bound_types:
        return False
    return bool(_contingency_object_schema(api_name))


def _adhoc_chapter_from_object_type(api_name: str) -> dict[str, Any]:
    """Materialize an ad-hoc chapter entry from an ObjectType schema (read-time, stateless).

    No decisionId/lane → global input: it joins the report with its schema-projected fact table but
    does not bind lane risks nor enter sub-decision aggregation. structural stays False (has an
    objectType, no consolidatesRisks) so the composer can drag it out again.
    """
    schema = _contingency_object_schema(api_name)
    display = (schema.get("displayMetadata") or {}) if isinstance(schema, dict) else {}
    entry: dict[str, Any] = {
        "id": f"{_ADHOC_CHAPTER_PREFIX}{api_name}",
        "no": "",
        "title": str(display.get("displayName") or api_name),
        "objectType": api_name,
        "decisionId": "",
        "decisionPoint": "global",
        "decisionLabel": "全局输入 · 本体类型库",
        "desc": str(display.get("description") or ""),
        "adhoc": True,
    }
    derived = _derive_chapter_fields_from_schema(api_name)
    if derived:
        entry["fields"] = derived
    return entry


def _outline_adhoc_chapters(
    project_key: str | None, directory: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Materialize the ad-hoc chapters this project's outline references (doc-ot-* in include∪order∪groups).

    Degrades to [] when the assembly overlay is unavailable; ineligible ids (denylist / unknown type /
    meanwhile bound by a directory chapter) are skipped, so a stale outline never breaks the derive.
    Group members (groups[*].members) are scanned too — an ad-hoc chapter folded into a fusion group
    must still be materialized so apply_outline can resolve it when collapsing the group.
    """
    try:
        from contingency_assembly import store as _outline_store

        outline = _outline_store.read_outline(project_key)
    except Exception:
        return []
    if not outline:
        return []
    ids = [str(x) for x in (outline.get("include") or [])]
    ids += [str(x) for x in (outline.get("order") or [])]
    groups = outline.get("groups")
    if isinstance(groups, dict):
        for group in groups.values():
            if isinstance(group, dict):
                ids += [str(x) for x in (group.get("members") or [])]
    bound = _directory_bound_object_types(directory)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for cid in ids:
        api = _adhoc_object_type(cid)
        if not api or api in seen:
            continue
        seen.add(api)
        if _adhoc_eligible(api, bound):
            out.append(_adhoc_chapter_from_object_type(api))
    return out


def _lane_for_contingency_risk_point(risk_point: str) -> str:
    """Map a derived risk's riskPoint to one of the 4 deliverability lanes.

    Mirrors the frontend laneForRiskPoint (src/lib/contingency-view.ts) so server-side chapter
    binding and the brain-map slots stay consistent: EOS/GA→network(维保) · EOM/TR5→device(设备) ·
    ESS→service(部件) · 其余→acceptance(验收兜底). 任务跟踪类 (CONTINGENCY_TRACKING_RISK_POINTS)
    never reaches this mapping — the chapter binder skips them before lane assignment.
    """
    rp = risk_point or ""
    if "EOS" in rp or "GA" in rp:
        return "network"
    if "EOM" in rp or "TR5" in rp:
        return "device"
    if "ESS" in rp:
        return "service"
    return "acceptance"


def _resolve_chapter_columns(fields: Any, object_type: str) -> list[dict[str, Any]]:
    """Resolve a chapter's curated fields to {key,label,note} columns over its ObjectType rows.

    key = the property whose displayName (or sourceColumnName) equals the curated field name,
    falling back to the field name itself. The substrate rows are keyed by property apiName, so
    this lets the chapter table show raw Dolt rows under the curated Chinese labels without
    hand-authoring the label→apiName map (derived from the ObjectType schema instead).
    """
    schema = _contingency_object_schema(object_type)
    props = schema.get("properties", {}) if isinstance(schema, dict) else {}
    label_to_api: dict[str, str] = {}
    if isinstance(props, dict):
        for api_name, prop in props.items():
            if not isinstance(prop, dict):
                continue
            display = str((prop.get("displayMetadata") or {}).get("displayName") or "").strip()
            source_col = str(prop.get("sourceColumnName") or "").strip()
            for label in (display, source_col):
                if label:
                    label_to_api.setdefault(label, str(api_name))
    columns: list[dict[str, Any]] = []
    for field in fields or []:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or "").strip()
        if not name:
            continue
        # Explicit apiName/key wins (lets a curated chapter use the proposal's column
        # label while binding to the right ObjectType property when label≠displayName);
        # otherwise resolve the label against the schema, falling back to the label itself.
        explicit = str(field.get("apiName") or field.get("key") or "").strip()
        key = explicit or label_to_api.get(name, name)
        columns.append({"key": key, "label": name, "note": field.get("note") or ""})
    return columns


def _contingency_primary_key(object_type: str) -> str:
    """First primaryKey apiName of a contingency ObjectType ('' when schema unavailable)."""
    schema = _contingency_object_schema(object_type)
    pks = schema.get("primaryKeyPropertyApiNames") if isinstance(schema, dict) else None
    return str(pks[0]) if isinstance(pks, list) and pks else ""


def _chapter_risk_evidence(
    bound_risks: list[dict[str, Any]], object_type: str
) -> tuple[list[str], list[dict[str, Any]]]:
    """Evidence the bound risks fired on this chapter's ObjectType → (fields, cells).

    默认精简、命中追加: the chapter's curated column set stays lean; only the properties the rule
    engine actually compared (provenance.subjects[].evidence.field) surface as extra columns, so
    溯源跳章 always lands on a visible value without hand-curating 10 lifecycle dates per chapter.
    fields = evidence apiNames in first-fired order; cells = one {rowKey/field/riskId/reason}
    per fired (row, field) so the UI can tint the exact cell and jump back to the risk card.
    """
    fields: list[str] = []
    cells: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for risk in bound_risks:
        provenance = risk.get("provenance") if isinstance(risk, dict) else None
        subjects = provenance.get("subjects") if isinstance(provenance, dict) else None
        for subject in subjects or []:
            if not isinstance(subject, dict) or subject.get("objectType") != object_type:
                continue
            evidence = subject.get("evidence") or {}
            field = str(evidence.get("field") or "").strip()
            if not field:
                continue
            if field not in fields:
                fields.append(field)
            row_key = str(subject.get("keyValue") or "").strip()
            if not row_key or (row_key, field) in seen:
                continue
            seen.add((row_key, field))
            cells.append(
                {
                    "rowKey": row_key,
                    "field": field,
                    "riskId": str(risk.get("riskId") or ""),
                    "reason": str(subject.get("reason") or ""),
                }
            )
    return fields, cells


def _chapter_narrative_index(
    project_key: str | None, plan_id: str | None
) -> dict[str, dict[str, Any]]:
    """Load ChapterNarrative overlay rows for a project, indexed by chapterId. {} on any failure.

    Lazy-imports contingency_narrative so importing data_connector never pulls langgraph; the
    narrative feature is optional, so a missing package / empty overlay degrades to no narratives
    (the report falls back to the static chapter desc).
    """
    try:
        from contingency_narrative import store as _narr_store
    except Exception:
        return {}
    try:
        rows = _narr_store.read_all_narratives(project_key)
    except Exception:
        return {}
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        cid = str(row.get("chapterId") or "")
        if cid:
            index[cid] = row
    return index


def _attach_chapter_narrative(
    chapter: dict[str, Any], narrative_index: dict[str, dict[str, Any]]
) -> None:
    """Merge a chapter's generated/edited narrative onto the chapter dict (display + merge state).

    Keeps the static `desc` (short caption) untouched; the long-form prose goes to `narrative`, with
    the fields the report needs to render edit/regenerate/compare/version controls. No-op when the
    chapter has no narrative row yet (the report then shows only the skeleton desc).
    """
    narr = narrative_index.get(str(chapter.get("id") or ""))
    if not narr:
        return
    edited = str(narr.get("editedText") or "").strip()
    display = edited or str(narr.get("generatedText") or "")
    if display:
        chapter["narrative"] = display
    chapter["narrativeStatus"] = narr.get("status") or "ai_draft"
    if narr.get("generatedText"):
        chapter["narrativeGenerated"] = narr.get("generatedText")
    if narr.get("editedText"):
        chapter["narrativeEdited"] = narr.get("editedText")
    if narr.get("pendingGenerated"):
        chapter["pendingGenerated"] = narr.get("pendingGenerated")
    if narr.get("mergeCandidate"):
        chapter["mergeCandidate"] = narr.get("mergeCandidate")
    if narr.get("generatedModel"):
        chapter["narrativeModel"] = narr.get("generatedModel")
    if narr.get("editedAt"):
        chapter["narrativeEditedAt"] = narr.get("editedAt")
    versions = narr.get("versions")
    if isinstance(versions, list) and versions:
        chapter["versions"] = versions


def _build_contingency_chapters(
    risks: list[dict[str, Any]],
    object_rows: dict[str, list[dict[str, Any]]] | None = None,
    project_key: str | None = None,
    plan_id: str | None = None,
) -> list[dict[str, Any]]:
    """Generate the chapter-structured 预案 from the ontology chapter directory + derived risks.

    Each chapter carries the real directory skeleton plus the bound risk ids: a lane chapter binds
    the derived risks whose lane matches; the §9 风险&假设 chapter (consolidatesRisks) binds all.
    state = 'gap' when the chapter has bound risks, else 'ok'. A chapter that declares an objectType
    additionally carries the real fact-substrate it projects (`rows` = the ObjectType's Dolt rows,
    `columns` = curated fields resolved to those rows' property keys), so the brain-map lists the
    multiple devices/components/… — not just derived risks. Table chapters follow 默认精简+命中追加:
    evidence fields fired by the bound risks join `columns` (marked derived), and `riskCells` +
    `rowKeyField` let the UI tint the exact fired cells (see _chapter_risk_evidence). Returns []
    when the directory is unavailable, so the caller still returns risks and the brain-map degrades
    gracefully.
    """
    directory = _load_contingency_chapter_directory()
    if not directory:
        return []
    object_rows = object_rows or {}
    # 拖拽组装新增的临时章（doc-ot-*）：按本项目 outline 现场派生骨架并入目录，行投影/列解析与
    # 正式章走同一条流水线；其 ObjectType 行不在 object_rows 时按需补读（live 与 list 共用此点）。
    adhoc_entries = _outline_adhoc_chapters(project_key, directory)
    if adhoc_entries:
        directory = directory + adhoc_entries
        for entry in adhoc_entries:
            adhoc_type = str(entry.get("objectType") or "")
            if adhoc_type in object_rows:
                continue
            try:
                adhoc_rows = get_object_data(adhoc_type, project_id=project_key or None)
                if not adhoc_rows and project_key:
                    unscoped = get_object_data(adhoc_type)
                    if _rows_are_global_reference(unscoped):
                        adhoc_rows = unscoped
                object_rows[adhoc_type] = adhoc_rows
            except Exception:
                object_rows[adhoc_type] = []
    narrative_index = _chapter_narrative_index(project_key, plan_id)
    by_lane: dict[str, list[str]] = {"network": [], "device": [], "service": [], "acceptance": []}
    all_ids: list[str] = []
    risks_by_id: dict[str, dict[str, Any]] = {}
    for risk in risks:
        if not isinstance(risk, dict):
            continue
        risk_id = str(risk.get("riskId") or "").strip()
        if not risk_id:
            continue
        all_ids.append(risk_id)
        risks_by_id[risk_id] = risk
        risk_point = str(risk.get("riskPoint") or "")
        if risk_point in CONTINGENCY_TRACKING_RISK_POINTS:
            # 任务跟踪类（§19.4 非阻塞）：入全量清单/汇总章，但不绑泳道章，不扣子决策指数。
            continue
        lane = _lane_for_contingency_risk_point(risk_point)
        by_lane.setdefault(lane, []).append(risk_id)

    chapters: list[dict[str, Any]] = []
    for entry in directory:
        chapter = dict(entry)
        lane = str(entry.get("lane") or "").strip()
        if entry.get("consolidatesRisks"):
            risk_ids = list(all_ids)
        elif lane:
            risk_ids = list(by_lane.get(lane, []))
        else:
            risk_ids = []
        chapter["riskIds"] = risk_ids
        chapter["state"] = "gap" if risk_ids else "ok"
        object_type = str(entry.get("objectType") or "").strip()
        if object_type:
            rows = object_rows.get(object_type) or []
            if rows:
                columns = _resolve_chapter_columns(entry.get("fields"), object_type)
                if str(entry.get("layout") or "").strip() == "detail":
                    # Single-object narrative chapter (e.g. 项目背景): project the first row's curated
                    # fields as label→value pairs so the report renders a vertical detail block for
                    # long-form text (客户项目背景/目标/范围/计划), not a wide one-row table.
                    first = rows[0]
                    chapter["detailRows"] = [
                        {"label": col["label"], "value": first.get(col["key"]), "note": col.get("note")}
                        for col in columns
                    ]
                else:
                    chapter["rows"] = rows
                    # 默认精简 + 命中追加：本章绑定风险在本 ObjectType 上比较过的证据字段，自动
                    # 成为可见列（插在首列后保证不被横向滚动埋掉）；已是 curated 列的（如 §8 维保章
                    # 静态 eosDate/isOverEos）按 key 去重不重复。riskCells 让前端给命中单元格着色
                    # 并回跳风险卡；无风险时两者皆缺省，表格保持精简（预制演示同样自然降级）。
                    bound = [risks_by_id[rid] for rid in risk_ids if rid in risks_by_id]
                    evidence_fields, risk_cells = _chapter_risk_evidence(bound, object_type)
                    shown = {str(col.get("key")) for col in columns}
                    extra = [field for field in evidence_fields if field not in shown]
                    if extra:
                        derived_cols = [
                            {
                                "key": field["key"],
                                "label": field["name"],
                                "note": field.get("note") or "",
                                "derived": True,
                            }
                            for field in _derive_chapter_fields_from_schema(object_type, extra)
                        ]
                        columns = columns[:1] + derived_cols + columns[1:]
                    if risk_cells:
                        chapter["riskCells"] = risk_cells
                        row_key_field = _contingency_primary_key(object_type)
                        if row_key_field:
                            chapter["rowKeyField"] = row_key_field
                    chapter["columns"] = columns
        _attach_chapter_narrative(chapter, narrative_index)
        chapters.append(chapter)
    return chapters


def _apply_contingency_outline(
    chapters: list[dict[str, Any]], project_key: str | None
) -> list[dict[str, Any]]:
    """Tailor the chapter directory by a project's cached ContingencyOutline overlay (filter+reorder).

    Applies the decision produced by assembleContingencyChapters via the pure
    contingency_assembly.store.apply_outline (no LLM, no langgraph pulled into the import graph). No
    overlay (or empty selection) returns the full directory unchanged — so deriveContingencyRisks
    degrades gracefully before any tailoring has run. Imported lazily to keep data_connector free of
    the assembly stack at import time.
    """
    try:
        from contingency_assembly import store as _outline_store
    except Exception:
        return chapters
    try:
        outline = _outline_store.read_outline(project_key)
        return _outline_store.apply_outline(chapters, outline)
    except Exception:
        return chapters


def _load_contingency_decision_points() -> list[dict[str, Any]]:
    """Load the 预案 decision model (DecisionPoint): core 方案可交付性 + 4 sub-decisions, from Dolt.

    DecisionPoint is Dolt-backed (binding `dolt_rows`): read via get_object_data without a project_id
    so all rows flow (the 决策点 are global, plan-agnostic templates with no projectKey, like RiskRule).
    Dolt is the single source of truth — no committed JSON in the read path; degrades to [] when Dolt
    is offline (like RiskRule). Sourced from《03-预案章节目录与子决策点映射》§三决策点信息.
    """
    rows = get_object_data("DecisionPoint")
    return [row for row in rows if isinstance(row, dict)]


def _decision_chapters_fk() -> tuple[str, str]:
    """(chapter_fk_field, decision_pk_field) from the Decision_Chapters Link Type.

    Sourcing the join keys from the declared ontology Link makes the Link the single source of truth
    for the chapter↔decision binding (replacing the old chapter.decisionPoint==domain string match).
    Falls back to the known FK when link-types.json is unavailable.
    """
    try:
        link_types = json.loads((BASE_DIR / "schema" / "link-types.json").read_text(encoding="utf-8"))
        fk = (link_types.get("Decision_Chapters") or {}).get("foreignKey") or {}
        src = str(fk.get("sourcePropertyApiName") or "").strip()
        tgt = str(fk.get("targetPropertyApiName") or "").strip()
        if src and tgt:
            return src, tgt
    except (OSError, ValueError):
        pass
    return "decisionId", "decisionId"


def _build_contingency_decision_points(
    chapters: list[dict[str, Any]], risks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Generate the 4 sub-decision-points (+ core) as DecisionPoint records, bound to chapters/risks.

    Palantir-first / derive-don't-hand-author: the decision structure (core 方案可交付性 → 4 子决策点)
    is reference data; deliverability is *derived* here by aggregating each sub-decision's chapters
    (bound via the Decision_Chapters Link — chapter.decisionId == DecisionPoint.decisionId, the FK,
    not a decisionPoint/domain string match) and the risks those chapters carry, then concluding
    可交付/存在风险 with a 0–100 可交付指数. The core decision aggregates all risks. Returns [] when the
    decision model is unavailable, so chapters/risks still flow and the brain-map degrades gracefully.
    """
    defs = _load_contingency_decision_points()
    if not defs:
        return []
    by_id = {str(r.get("riskId") or ""): r for r in risks if isinstance(r, dict)}
    all_ids = [str(r.get("riskId") or "").strip() for r in risks if isinstance(r, dict) and r.get("riskId")]

    # Bind chapters to decisions via the Decision_Chapters Link FK (chapter.decisionId →
    # DecisionPoint.decisionId), sourced from the declared Link Type. Chapters without a decisionId
    # (global inputs) bind to no sub-decision, matching the prior behavior.
    chapter_fk, decision_pk = _decision_chapters_fk()
    chapters_by_decision: dict[str, list[dict[str, Any]]] = {}
    for chapter in chapters:
        decision_id = str(chapter.get(chapter_fk) or "").strip()
        if decision_id:
            chapters_by_decision.setdefault(decision_id, []).append(chapter)

    def _index_and_conclusion(risk_ids: list[str]) -> tuple[int, str]:
        if not risk_ids:
            return 100, "可交付"
        penalty = 0
        for risk_id in risk_ids:
            severity = str((by_id.get(risk_id) or {}).get("severity") or "")
            # 重大（§19.3 SVC-WB-01）至少与「高」同权重——惩罚词表只认 高/中 时它曾误落最低档。
            penalty += 30 if ("高" in severity or "重大" in severity) else 18 if "中" in severity else 10
        return max(40, 100 - penalty), "存在风险"

    points: list[dict[str, Any]] = []
    for definition in defs:
        point = dict(definition)
        if str(definition.get("decisionLevel") or "") == "core":
            risk_ids = list(all_ids)
            point["chapterIds"] = []
            point["anchorChapterId"] = "doc-overall"
        else:
            bound_chapters = chapters_by_decision.get(str(definition.get(decision_pk) or "").strip(), [])
            risk_ids = []
            for chapter in bound_chapters:
                for risk_id in chapter.get("riskIds") or []:
                    if risk_id and risk_id not in risk_ids:
                        risk_ids.append(risk_id)
            point["chapterIds"] = [c.get("id") for c in bound_chapters]
            point["anchorChapterId"] = bound_chapters[0].get("id") if bound_chapters else ""
        index, conclusion = _index_and_conclusion(risk_ids)
        point["riskIds"] = risk_ids
        point["riskCount"] = len(risk_ids)
        point["deliverabilityIndex"] = index
        point["conclusion"] = conclusion
        points.append(point)
    return points


def derive_contingency_risks(
    maintenance_policies: list[dict[str, Any]],
    risk_rules: list[dict[str, Any]],
    plan_id: str | None = None,
    assessment_id: str | None = None,
    reference_date: str | None = None,
    equipment_configs: list[dict[str, Any]] | None = None,
    component_configs: list[dict[str, Any]] | None = None,
    acceptance_strategies: list[dict[str, Any]] | None = None,
    project_key: str | None = None,
    chapter_object_rows: dict[str, list[dict[str, Any]]] | None = None,
    apply_outline: bool = True,
) -> dict[str, Any]:
    """Derived Emergent layer for the delivery-contingency-plan ontology.

    Forward-ports the EODS 售前风险识别 decision engine onto the contingency ontology: gather the
    subjects that fire each risk point from the typed substrate, then map each matching RiskRule
    into a fully-populated RiskItem-shaped suggestion (建议值 — the user adopts/dismisses; nothing is
    written back). Same gather→match→emit shape as the default ontology's project_emergent_risks.
    Lifecycle lanes are live over EquipmentConfig (EOM/TR5/EOS/ESS via its GA/TR5/EOM/EOS/ESS
    milestone dates, Dolt-backed) with MaintenancePolicy (EOS) and ComponentConfig (ESS) as
    additional fact sources, plus ACC-CHK-01 over AcceptanceStrategy (04 §19.3 验收④ — a global
    reusable asset, so it participates unfiltered like the RiskRule library), SVC-WB-01 over
    EquipmentConfig×MaintenancePolicy (GA 晚于维保开始, joined model↔productModel), and the
    standing TRK-04 tracking suggestion anchored on ProjectRequirement (no chapter binding).

    Each derived risk carries a `provenance` block (rule row + fired subject records with
    field-level evidence + reference dates) so the UI can drill from a risk down to the exact
    ontology rows and comparisons that produced it — 推导溯源, no engine replay needed.
    """
    reference_iso = str(reference_date or "").strip() or date.today().isoformat()
    horizon_2m_iso = _shift_iso_months(reference_iso, 2)  # EODS system_time_2months

    # Fired-subject records carry the full provenance chain (来源行 + 触发证据), not just a display
    # label: 溯源下钻 renders 规则 → 主体 → 证据 from these, and `subjects` (labels) stays derived
    # from them so the description / narrative payloads are unchanged.
    fired_subjects: dict[str, list[dict[str, Any]]] = {
        point: [] for point in CONTINGENCY_RISK_POINTS
    }
    _type_labels: dict[str, str] = {}

    def _type_label(object_type: str) -> str:
        if object_type not in _type_labels:
            schema = _contingency_object_schema(object_type)
            display = schema.get("displayMetadata") or {}
            _type_labels[object_type] = str(display.get("displayName") or object_type)
        return _type_labels[object_type]

    def _fire(
        point: str, label: str, object_type: str, key_value: str, evidence: dict[str, Any]
    ) -> None:
        record = dict(evidence)
        reason = str(record.pop("reason", ""))
        fired_subjects.setdefault(point, []).append(
            {
                "label": label,
                "objectType": object_type,
                "objectTypeLabel": _type_label(object_type),
                "keyValue": key_value,
                "reason": reason,
                "evidence": record,
            }
        )

    for policy in maintenance_policies or []:
        if not isinstance(policy, dict):
            continue
        evidence = _maintenance_policy_eos_evidence(policy, reference_iso)
        if evidence:
            _fire(
                "EOS风险",
                _risk_subject_label(policy),
                "MaintenancePolicy",
                _subject_key_value(policy, "maintenancePolicyId"),
                evidence,
            )
    for equipment in equipment_configs or []:
        if not isinstance(equipment, dict):
            continue
        label = _equipment_subject_label(equipment)
        key_value = _subject_key_value(equipment, "equipmentId")
        for point, evidence in (
            ("EOM风险", _equipment_eom_evidence(equipment, horizon_2m_iso)),
            ("TR5风险", _equipment_tr5_evidence(equipment, horizon_2m_iso)),
            ("EOS风险", _equipment_eos_evidence(equipment, reference_iso)),
            ("ESS风险", _equipment_ess_evidence(equipment, reference_iso)),
        ):
            if evidence:
                _fire(point, label, "EquipmentConfig", key_value, evidence)
    for component in component_configs or []:
        if not isinstance(component, dict):
            continue
        evidence = _component_ess_evidence(component, reference_iso)
        if evidence:
            _fire(
                "ESS风险",
                _component_subject_label(component),
                "ComponentConfig",
                _subject_key_value(component, "componentId"),
                evidence,
            )
    for strategy in acceptance_strategies or []:
        if not isinstance(strategy, dict):
            continue
        evidence = _acceptance_arrival_evidence(strategy)
        if evidence:
            _fire(
                ACCEPTANCE_ARRIVAL_RISK_POINT,
                _acceptance_subject_label(strategy),
                "AcceptanceStrategy",
                _subject_key_value(strategy, "acceptanceStrategyId"),
                evidence,
            )
    # SVC-WB-01 (服务③ · 重大): GA 计划晚于该产品维保开始 —— 维保已计时而产品未 GA。
    for equipment in equipment_configs or []:
        if not isinstance(equipment, dict):
            continue
        model = str(equipment.get("model") or "").strip()
        if not model:
            continue
        for policy in maintenance_policies or []:
            if not isinstance(policy, dict) or not _policy_matches_equipment_model(policy, model):
                continue
            start_date = str(policy.get("startDate") or "").strip()
            if not start_date:
                continue
            evidence = _date_fire_evidence(
                equipment, "gaDate", start_date, "维保开始日期", ">", "GA 计划"
            )
            if evidence:
                _fire(
                    GA_MAINTENANCE_RISK_POINT,
                    _equipment_subject_label(equipment),
                    "EquipmentConfig",
                    _subject_key_value(equipment, "equipmentId"),
                    evidence,
                )
    # TRK-04 (任务跟踪 · 非阻塞): 适用范围=所有智算 → 常驻跟踪建议，锚定真实项目背景行；
    # live 入口经 chapter_object_rows 传入 ProjectRequirement，纯离线调用缺省即不触发。
    for requirement in (chapter_object_rows or {}).get("ProjectRequirement") or []:
        if not isinstance(requirement, dict):
            continue
        label = str(
            requirement.get("projectName") or requirement.get("requirementName") or "智算项目"
        ).strip()
        _fire(
            TRACKING_RISK_POINT_OPTICAL,
            label,
            "ProjectRequirement",
            _subject_key_value(requirement, "requirementId"),
            {
                "field": "deliveryScope",
                "value": str(requirement.get("deliveryScope") or "智算底座交付").strip()[:80],
                "comparator": "∈",
                "threshold": "所有智算项目",
                "thresholdLabel": "适用范围（§19.3 任务跟踪类）",
                "reason": "智算交付常驻跟踪：光模块/光纤在转运与装配环节存在丢失风险，建议列入任务跟踪",
            },
        )

    plan_key = str(plan_id or "").strip()
    assessment_key = str(assessment_id or "").strip()
    project_key_val = str(project_key or "").strip()
    risks: list[dict[str, Any]] = []
    for rule in risk_rules or []:
        if not isinstance(rule, dict):
            continue
        risk_point = str(rule.get("riskPoint") or "").strip()
        fired = fired_subjects.get(risk_point, [])
        subjects = sorted({record["label"] for record in fired if record["label"]})
        if not subjects:
            continue
        # 溯源主体按 (label, reason) 去重排序：同一行事实在一条风险下只出现一次，顺序稳定。
        seen_records: set[tuple[str, str]] = set()
        subject_records: list[dict[str, Any]] = []
        for record in sorted(fired, key=lambda r: (r["label"], r["reason"])):
            signature = (record["label"], record["reason"])
            if signature in seen_records:
                continue
            seen_records.add(signature)
            subject_records.append(record)
        sub_category = str(rule.get("riskSubCategory") or risk_point).strip()
        risk_id = "_".join(part for part in (plan_key or "PLAN", sub_category, risk_point) if part)
        risks.append(
            {
                "riskId": risk_id,
                "planId": plan_key,
                "projectKey": project_key_val,
                "assessmentId": assessment_key,
                "riskName": str(rule.get("ruleName") or risk_point).strip(),
                "riskPoint": risk_point,
                "riskType": str(rule.get("riskCategory") or "").strip(),
                "severity": str(rule.get("riskLevel") or "").strip(),
                "owner": str(rule.get("owner") or "").strip(),
                "mitigationPlan": str(rule.get("responseMeasure") or "").strip(),
                "impact": str(rule.get("impact") or "").strip(),
                "description": f"{'、'.join(subjects)}存在{risk_point}",
                "state": "处理中",
                "status": "处理中",
                "source": "售前风险",
                "sourceSummary": "由 deriveContingencyRisks 在维保策略事实上按规则库派生（建议值）。",
                "identifiedAt": reference_iso,
                "subjects": subjects,
                # 推导溯源：规则（RiskRule 行）× 触发主体（事实行 + 证据）→ 本条风险。
                # 前端溯源下钻据此渲染「为什么有这条风险」，无需重放引擎。
                "provenance": {
                    "engine": "deriveContingencyRisks",
                    "referenceDate": reference_iso,
                    "horizonDate": horizon_2m_iso,
                    "rule": {
                        "ruleId": str(rule.get("riskRuleId") or "").strip(),
                        "ruleName": str(rule.get("ruleName") or risk_point).strip(),
                        "riskPoint": risk_point,
                        "riskCategory": str(rule.get("riskCategory") or "").strip(),
                        "riskSubCategory": sub_category,
                        "riskLevel": str(rule.get("riskLevel") or "").strip(),
                        "owner": str(rule.get("owner") or "").strip(),
                        "source": "RiskRule 规则库（§19 售前风险识别）",
                    },
                    "subjects": subject_records,
                },
            }
        )

    # Substrate for chapter row-projection: the 4 typed risk inputs are already project-filtered;
    # the live entry may pass chapter_object_rows for the remaining chapters' ObjectTypes too.
    object_rows: dict[str, list[dict[str, Any]]] = dict(chapter_object_rows or {})
    object_rows.setdefault("EquipmentConfig", equipment_configs or [])
    object_rows.setdefault("ComponentConfig", component_configs or [])
    object_rows.setdefault("MaintenancePolicy", maintenance_policies or [])
    object_rows.setdefault("AcceptanceStrategy", acceptance_strategies or [])
    chapters = _build_contingency_chapters(
        risks, object_rows, project_key=project_key_val, plan_id=plan_key
    )
    # Decision points aggregate over the FULL directory (deliverability must see every risk),
    # then the displayed chapter set is tailored per the project's cached ContingencyOutline overlay
    # (assembleContingencyChapters). apply_outline=False yields the un-tailored directory — used by the
    # assembly graph's gather so a re-tailor can re-expand previously dropped chapters.
    decision_points = _build_contingency_decision_points(chapters, risks)
    if apply_outline:
        chapters = _apply_contingency_outline(chapters, project_key_val)
        # Fusion-group composites are synthesized during folding — i.e. AFTER _build_contingency_chapters
        # attached per-chapter narratives — so attach their fused narrative here (keyed by the group id,
        # like any chapter). Members' own narratives are irrelevant to the group's single fused prose.
        group_chapters = [c for c in chapters if isinstance(c, dict) and c.get("isGroup")]
        if group_chapters:
            narrative_index = _chapter_narrative_index(project_key_val, plan_key)
            for group_chapter in group_chapters:
                _attach_chapter_narrative(group_chapter, narrative_index)
    return {
        "planId": plan_key,
        "projectKey": project_key_val,
        "assessmentId": assessment_key,
        "riskCount": len(risks),
        "risks": risks,
        "chapters": chapters,
        "decisionPoints": decision_points,
    }


# Contingency object/value types + the run-record overlay live in the default `schema/` ontology.
# (Reference seed data moved out to `data/contingency/` as declared json_rows datasources; this
# dirname now only locates object-types.json / value-types.json and the runtime/ overlay store.)
_CONTINGENCY_SCHEMA_DIRNAME = "schema"


def _contingency_object_schema(object_type: str) -> dict[str, Any]:
    """Load one ObjectType schema from the delivery-contingency-plan ontology files."""
    path = BASE_DIR / _CONTINGENCY_SCHEMA_DIRNAME / "object-types.json"
    try:
        schemas = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    schema = schemas.get(object_type)
    return schema if isinstance(schema, dict) else {}


def contingency_object_data(object_type: str) -> list[dict[str, Any]]:
    """Read a contingency ObjectType's rows from Dolt plus the local run-record overlay.

    Dolt is the system-of-record once data is loaded out-of-band (Excel→Dolt). The local
    run-record overlay (adopted run records, e.g. RiskItems created by AdoptDerivedRisk) is
    unioned on top by primary key, so newly persisted objects are immediately queryable. Same
    graceful-degradation spirit as the default readers (empty when the substrate is offline).

    Reference inputs that used to fall back to a committed seed here (RiskRule / EquipmentConfig /
    ComponentConfig / MaintenancePolicy) are now declared JSON datasources read via get_object_data
    (reader: json_rows); this path serves the remaining Dolt/run-record objects (ContingencyPlan,
    AcceptanceStrategy).
    """
    base = read_dolt_object_rows(object_type, _contingency_object_schema(object_type))
    overlay = _read_contingency_runrecord(object_type)
    if not overlay:
        return base
    return _merge_contingency_rows(base, overlay, _contingency_pk_field(object_type))


def _filter_rows_by_project_key(rows: list[dict[str, Any]], project_key: str) -> list[dict[str, Any]]:
    """Keep only rows whose projectKey matches — project-scoped derivation after the ontology merge."""
    return [
        row
        for row in rows
        if isinstance(row, dict) and str(row.get("projectKey") or "").strip() == project_key
    ]


def _rows_are_global_reference(rows: list[dict[str, Any]]) -> bool:
    """Rows without a projectKey are reusable reference facts, not project-scoped facts."""
    return bool(rows) and all(
        isinstance(row, dict) and not str(row.get("projectKey") or "").strip()
        for row in rows
    )


def _project_requirement_rows_for_tracking(
    rows: list[dict[str, Any]], project_key: str
) -> list[dict[str, Any]]:
    """Rows used by standing tracking risks such as TRK-04.

    ProjectRequirement originates from project-background inputs that may be loaded without
    projectKey. TRK-04 is a default tracking risk for the current 智算 project, so a missing
    projectKey on a single background row must not make the frontend's project_key call drop it.
    """
    if not project_key:
        return rows
    scoped = _filter_rows_by_project_key(rows, project_key)
    if scoped:
        return scoped
    unscoped = [row for row in rows if isinstance(row, dict) and not str(row.get("projectKey") or "").strip()]
    if len(unscoped) == 1:
        row = dict(unscoped[0])
        row["projectKey"] = project_key
        return [row]
    if not rows:
        return [
            {
                "requirementId": f"{project_key}::project_requirement",
                "projectKey": project_key,
                "requirementName": project_key,
                "deliveryScope": "智算底座交付",
            }
        ]
    return []


def _resolve_plan_project_key(plan_id: str) -> str:
    """Best-effort ContingencyPlan.planId -> projectKey lookup (empty when the plan is unknown offline)."""
    for plan in contingency_object_data("ContingencyPlan"):
        if isinstance(plan, dict) and str(plan.get("planId") or "").strip() == plan_id:
            return str(plan.get("projectKey") or "").strip()
    return ""


def _fetch_chapter_object_rows(
    project_key: str, prefetched: dict[str, list[dict[str, Any]]]
) -> dict[str, list[dict[str, Any]]]:
    """Read every chapter's backing ObjectType rows for table projection (project-scoped).

    So the brain-map can list the real fact substrate per chapter (not just derived risks). The
    risk-derivation substrate (EquipmentConfig/ComponentConfig/MaintenancePolicy/AcceptanceStrategy)
    is reused from `prefetched` (already fetched + project-filtered); any other ObjectType a chapter
    declares is read via get_object_data, which returns [] for metadata_only tables — so those
    chapters light up automatically once their Dolt table is loaded and the binding flips to
    dolt_rows. Degrades to {} / [] without raising when the directory or a table is unavailable.
    """
    object_rows: dict[str, list[dict[str, Any]]] = {}
    for entry in _load_contingency_chapter_directory():
        object_type = str(entry.get("objectType") or "").strip()
        if not object_type or object_type in object_rows:
            continue
        if object_type in prefetched:
            object_rows[object_type] = prefetched[object_type] or []
            continue
        try:
            rows = get_object_data(object_type, project_id=project_key or None)
            if not rows and project_key:
                unscoped_rows = get_object_data(object_type)
                if _rows_are_global_reference(unscoped_rows):
                    rows = unscoped_rows
            object_rows[object_type] = rows
        except Exception:
            object_rows[object_type] = []
    return object_rows


def derive_contingency_risks_for_plan(
    plan_id: str | None = None,
    assessment_id: str | None = None,
    reference_date: str | None = None,
    project_key: str | None = None,
    apply_outline: bool = True,
) -> dict[str, Any]:
    """Live entry for the deriveContingencyRisks Function: fetch the substrate, then derive.

    Self-fetching counterpart of the pure derive_contingency_risks — mirrors how
    project_emergent_risks takes only an id and reads its own object data. After the contingency
    ontology was merged into `default`, the typed substrate (MaintenancePolicy / EquipmentConfig /
    ComponentConfig) is project-scoped: when a projectKey is given (directly, or resolved from the
    plan) only that project's rows participate, so multi-project data in one store stays isolated.
    The RiskRule library is global and always participates; plan_id/projectKey stamp the derived
    suggestions (and the riskId prefix).
    """
    key = str(project_key or "").strip()
    if not key and str(plan_id or "").strip():
        key = _resolve_plan_project_key(str(plan_id).strip())
    # Reference inputs are JSON-datasource-backed (reader: json_rows) — read via the generic path.
    # No project_id is passed so all rows flow through; per-project isolation is applied below by
    # _filter_rows_by_project_key on each row's projectKey.
    policies = get_object_data("MaintenancePolicy")
    rules = get_object_data("RiskRule")
    equipment = get_object_data("EquipmentConfig")
    components = get_object_data("ComponentConfig")
    project_requirements = get_object_data("ProjectRequirement")
    # AcceptanceStrategy has no JSON datasource: still served from Dolt + run-record overlay.
    acceptance = contingency_object_data("AcceptanceStrategy")
    if key:
        policies = _filter_rows_by_project_key(policies, key)
        equipment = _filter_rows_by_project_key(equipment, key)
        components = _filter_rows_by_project_key(components, key)
        project_requirements = _project_requirement_rows_for_tracking(project_requirements, key)
    # AcceptanceStrategy is a global reusable asset (no projectKey) → like the RiskRule library it is
    # not project-filtered; it always participates in the derivation.
    # Project the real substrate into each chapter as a data table: reuse the 4 already-fetched risk
    # inputs, and read every other chapter's ObjectType (empty until its Dolt table is loaded).
    chapter_object_rows = _fetch_chapter_object_rows(
        key,
        {
            "EquipmentConfig": equipment,
            "ComponentConfig": components,
            "MaintenancePolicy": policies,
            "AcceptanceStrategy": acceptance,
        },
    )
    # TRK-04 is a standing tracking suggestion anchored on ProjectRequirement, but it is not a
    # visible chapter dependency. Keep it available even when chapter tailoring drops global inputs.
    chapter_object_rows["ProjectRequirement"] = project_requirements
    return derive_contingency_risks(
        policies,
        rules,
        plan_id=plan_id,
        assessment_id=assessment_id,
        reference_date=reference_date,
        equipment_configs=equipment,
        component_configs=components,
        acceptance_strategies=acceptance,
        project_key=key,
        chapter_object_rows=chapter_object_rows,
        apply_outline=apply_outline,
    )


def derive_eods_presales_risks_for_plan(
    plan_id: str | None = None,
    assessment_id: str | None = None,
    reference_date: str | None = None,
    project_key: str | None = None,
    apply_outline: bool = True,
) -> dict[str, Any]:
    """EODS pre-sales risk adapter over the local ontology SDK facade.

    Reuses the existing ontology-native derivation engine, which already reads RiskRule and fact
    ObjectTypes through get_object_data()/contingency_object_data(). The companion
    eods_presales_risk module carries deterministic ports of EODS Python nodes for table/array/LLM
    output formatting; this function is the read-only Function binding for callers that want the
    EODS-oriented entrypoint name.
    """
    from eods_presales_risk import mark_ontology_result

    return mark_ontology_result(
        derive_contingency_risks_for_plan(
            plan_id=plan_id,
            assessment_id=assessment_id,
            reference_date=reference_date,
            project_key=project_key,
            apply_outline=apply_outline,
        )
    )


def publish_contingency_findings_action(
    payload: dict[str, Any] | None = None,
    *,
    write: bool = True,
    **kwargs: Any,
) -> dict[str, Any]:
    """Publish derived contingency findings into the project's existing Excel workbooks.

    Side-effect Action adapter for PublishContingencyFindings. The derivation remains read-only;
    this function explicitly bridges the generated suggestions into project-management files.
    """
    raw = dict(payload or {})
    raw.update(kwargs)
    plan_id = str(raw.get("planId") or raw.get("plan_id") or "").strip()
    project_key = str(raw.get("projectKey") or raw.get("project_key") or "").strip()
    assessment_id = str(raw.get("assessmentId") or raw.get("assessment_id") or "").strip()
    reference_date = raw.get("referenceDate")
    if reference_date is None:
        reference_date = raw.get("reference_date")
    reference_date_text = str(reference_date).strip() if reference_date is not None else None
    if not plan_id:
        raise ValueError("payload.planId is required.")
    if not project_key:
        raise ValueError("payload.projectKey is required.")
    if not assessment_id:
        raise ValueError("payload.assessmentId is required.")

    generation = derive_contingency_risks_for_plan(
        plan_id=plan_id,
        project_key=project_key,
        assessment_id=assessment_id,
        reference_date=reference_date_text or None,
    )
    generation.setdefault("planId", plan_id)
    generation.setdefault("projectKey", project_key)
    generation.setdefault("assessmentId", assessment_id)

    from project_management_excel import publish_findings_to_project_management_excel

    return publish_findings_to_project_management_excel(generation, write=write)


# --------------------------------------------------------------------------- contingency chapter narratives
# Thin bindings for the chapter-narrative Functions (function-types.json binds module=data_connector).
# Implementation lives in the contingency_narrative package (small LangGraph + run-record overlay
# store); imported lazily so the data_connector import stays free of langgraph.


def generate_contingency_narratives(
    plan_id: str | None = None,
    project_key: str | None = None,
    scope: str = "all",
    chapter_id: str | None = None,
    mode: str = "only_empty",
    apply: Any = False,
    reference_date: str | None = None,
) -> dict[str, Any]:
    from contingency_narrative import graph as _narr_graph

    return _narr_graph.run_generation(
        plan_id=plan_id,
        project_key=project_key,
        scope=scope,
        chapter_id=chapter_id,
        mode=mode,
        apply=apply,
        reference_date=reference_date,
    )


def edit_chapter_narrative(
    project_key: str, chapter_id: str, text: str, edited_by: str | None = None
) -> dict[str, Any]:
    from contingency_narrative import store as _narr_store

    return _narr_store.edit_chapter_narrative(project_key, chapter_id, text, edited_by=edited_by)


def accept_chapter_merge(
    project_key: str, chapter_id: str, choice: str, edited_by: str | None = None
) -> dict[str, Any]:
    from contingency_narrative import store as _narr_store

    return _narr_store.accept_chapter_merge(project_key, chapter_id, choice, edited_by=edited_by)


def save_contingency_plan_version(
    project_key: str,
    version_label: str,
    plan_id: str | None = None,
    created_by: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    from contingency_narrative import store as _narr_store

    return _narr_store.save_contingency_plan_version(
        project_key, version_label, plan_id=plan_id, created_by=created_by, note=note
    )


def list_contingency_plan_versions(project_key: str | None = None) -> dict[str, Any]:
    from contingency_narrative import store as _narr_store

    return _narr_store.list_contingency_plan_versions(project_key)


def diff_chapter_narrative_versions(
    project_key: str | None,
    from_version: str,
    to_version: str,
) -> dict[str, Any]:
    from contingency_narrative import store as _narr_store

    return _narr_store.diff_chapter_narrative_versions(project_key, from_version, to_version)


def restore_chapter_narrative_version(
    project_key: str,
    chapter_id: str,
    seq: str | None = None,
    version_label: str | None = None,
    edited_by: str | None = None,
) -> dict[str, Any]:
    from contingency_narrative import store as _narr_store

    return _narr_store.restore_chapter_narrative_version(
        project_key, chapter_id, seq=seq, version_label=version_label, edited_by=edited_by
    )


# --------------------------------------------------------------------------- contingency chapter assembly
# Thin bindings for the chapter-assembly (tailoring) Functions (function-types.json binds
# module=data_connector). Implementation lives in the contingency_assembly package (small LangGraph +
# ContingencyOutline run-record overlay); imported lazily so data_connector import stays langgraph-free.


def assemble_contingency_chapters(
    plan_id: str | None = None,
    project_key: str | None = None,
    mode: str = "only_empty",
    reference_date: str | None = None,
    persist: Any = True,
) -> dict[str, Any]:
    from contingency_assembly import graph as _assembly_graph

    # persist may arrive as a JSON string via the Function executor — coerce to bool.
    if isinstance(persist, str):
        persist = persist.strip().lower() not in ("false", "0", "no", "")
    return _assembly_graph.run_assembly(
        plan_id=plan_id,
        project_key=project_key,
        mode=mode,
        reference_date=reference_date,
        persist=bool(persist),
    )


def pin_contingency_chapter(
    project_key: str, chapter_id: str, action: str, edited_by: str | None = None
) -> dict[str, Any]:
    from contingency_assembly import store as _outline_store

    return _outline_store.pin_chapter(project_key, chapter_id, action, edited_by=edited_by)


def _chapter_row_count(chapter: dict[str, Any]) -> int:
    rows = chapter.get("rows")
    if isinstance(rows, list) and rows:
        return len(rows)
    detail = chapter.get("detailRows")
    if isinstance(detail, list) and detail:
        return len(detail)
    return 0


def list_contingency_chapters(project_key: str | None = None) -> dict[str, Any]:
    """List the full ontology-derived chapter directory as selectable 本体要素 (for the drag composer).

    Read-only, no LLM: derive the un-tailored directory (apply_outline=False) and trim each chapter to
    the fields the picker needs (objectType / decision grouping / schema-derived fields / data+risk
    counts + structural flag), plus the project's current `include` (every chapter when no overlay
    exists yet, so the composer starts with the full set selected). Also returns `candidates` — every
    eligible business ObjectType not yet projected by a chapter, as draggable doc-ot-* 临时章候选
    (本体类型库：全集皆可组装，rowCount 标注当前项目的事实行数，0 行也可拖入得到字段骨架)。
    """
    derived = derive_contingency_risks_for_plan(project_key=project_key, apply_outline=False)
    elements: list[dict[str, Any]] = []
    for chapter in derived.get("chapters") or []:
        if not isinstance(chapter, dict) or not chapter.get("id"):
            continue
        object_type = str(chapter.get("objectType") or "").strip()
        elements.append(
            {
                "id": chapter.get("id"),
                "no": chapter.get("no"),
                "title": chapter.get("title"),
                "objectType": object_type,
                "decisionId": chapter.get("decisionId") or "",
                "decisionPoint": chapter.get("decisionPoint") or "",
                "decisionLabel": chapter.get("decisionLabel") or "",
                "fields": chapter.get("fields") or [],
                "rowCount": _chapter_row_count(chapter),
                "riskCount": len(chapter.get("riskIds") or []),
                "consolidatesRisks": bool(chapter.get("consolidatesRisks")),
                "structural": (not object_type) or bool(chapter.get("consolidatesRisks")),
                "adhoc": bool(chapter.get("adhoc")),
            }
        )
    from contingency_assembly import store as _outline_store

    outline = _outline_store.read_outline(project_key)
    include = (
        [str(x) for x in (outline.get("include") or [])]
        if outline and outline.get("include")
        else [str(entry["id"]) for entry in elements]
    )
    return {
        "elements": elements,
        "include": include,
        "candidates": _adhoc_chapter_candidates(project_key, elements),
        "groups": (outline.get("groups") if outline else {}) or {},
    }


def _adhoc_chapter_candidates(
    project_key: str | None, elements: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """本体类型库候选：全部可成章但尚未入目录/outline 的业务 ObjectType（按事实行数降序）。

    Element-shaped so the composer renders them with the same chip component; `candidate: True`
    marks them as not-yet-included. rowCount reads the project-scoped rows (global reference data
    falls back unscoped, mirroring _fetch_chapter_object_rows); 0-row types stay listed — the
    ontology's full breadth is draggable, an empty type just yields a schema-skeleton chapter.
    """
    try:
        path = BASE_DIR / _CONTINGENCY_SCHEMA_DIRNAME / "object-types.json"
        schemas = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(schemas, dict):
        return []
    bound = _directory_bound_object_types()
    present = {str(e.get("objectType") or "").strip() for e in elements}
    candidates: list[dict[str, Any]] = []
    for api_name in schemas:
        if api_name in present or not _adhoc_eligible(api_name, bound):
            continue
        try:
            rows = get_object_data(api_name, project_id=project_key or None)
            if not rows and project_key:
                unscoped = get_object_data(api_name)
                if _rows_are_global_reference(unscoped):
                    rows = unscoped
        except Exception:
            rows = []
        entry = _adhoc_chapter_from_object_type(api_name)
        candidates.append(
            {
                "id": entry["id"],
                "no": "",
                "title": entry["title"],
                "objectType": api_name,
                "decisionId": "",
                "decisionPoint": "global",
                "decisionLabel": entry["decisionLabel"],
                "desc": entry.get("desc") or "",
                "fields": entry.get("fields") or [],
                "rowCount": len(rows),
                "riskCount": 0,
                "consolidatesRisks": False,
                "structural": False,
                "adhoc": True,
                "candidate": True,
            }
        )
    candidates.sort(key=lambda c: (-int(c.get("rowCount") or 0), str(c.get("title") or "")))
    return candidates


def set_contingency_chapters(
    project_key: str,
    chapter_ids: list[str] | None = None,
    groups: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministically set the chapter selection from the drag composer (preserve order, no LLM).

    Validates ids against the real directory (drops unknown), additionally accepting ad-hoc chapter
    ids `doc-ot-<ObjectType>` for any eligible business type (本体类型库拖入 —— 骨架由 derive 读时
    现场派生，这里只需让 id 进 include/order)。Force-includes structural chapters (no objectType /
    consolidatesRisks — 计划占位章 can't be dropped by mistake), and writes `include`+`order` in the
    **given drag order** via store.set_include. deriveContingencyRisks then filters+reorders the
    report by exactly this selection.

    Fusion groups: `groups` maps a `doc-grp-*` id → {title, members, decisionPoint}. Each group's
    members are validated (real directory / eligible ad-hoc; structural chapters can never be merged)
    and a member belongs to at most one group. A group needs ≥2 valid members to survive; with exactly
    1 it degrades (its group id in chapter_ids is replaced by that lone member id); with 0 it vanishes.
    Members owned by a surviving group are never written as standalone include ids (the group owns them).
    """
    directory = _load_contingency_chapter_directory()
    dir_ids = [str(entry.get("id") or "") for entry in directory if entry.get("id")]
    valid = set(dir_ids)
    bound_types = _directory_bound_object_types(directory)
    structural = {
        str(entry.get("id") or "")
        for entry in directory
        if entry.get("id")
        and (not str(entry.get("objectType") or "").strip() or entry.get("consolidatesRisks"))
    }

    def _valid_member(cid: str) -> bool:
        # A mergeable member is a real directory chapter or an eligible ad-hoc type — never structural.
        if cid in structural:
            return False
        if cid in valid:
            return True
        adhoc_type = _adhoc_object_type(cid)
        return bool(adhoc_type and _adhoc_eligible(adhoc_type, bound_types))

    # 1. Clean the fusion groups: drop invalid/duplicate members, dedupe a member to one group,
    #    keep groups with ≥2 members, degrade 1-member groups, drop empty ones.
    raw_groups = groups if isinstance(groups, dict) else {}
    clean_groups: dict[str, dict[str, Any]] = {}
    group_degrade: dict[str, str] = {}  # gid -> lone surviving member id
    member_owned: set[str] = set()
    for gid, group in raw_groups.items():
        gid = str(gid)
        if not gid.startswith("doc-grp-") or not isinstance(group, dict):
            continue
        members: list[str] = []
        seen_m: set[str] = set()
        for m in group.get("members") or []:
            ms = str(m)
            if ms in seen_m or ms in member_owned or not _valid_member(ms):
                continue
            seen_m.add(ms)
            members.append(ms)
        if len(members) >= 2:
            clean_group = {
                "title": str(group.get("title") or ""),
                "members": members,
                "decisionPoint": str(group.get("decisionPoint") or ""),
            }
            # 人工改名标记透传（titleBy='human' 时叙事图生成不覆盖标题）；缺省/其它值不写，保持 auto。
            if str(group.get("titleBy") or "") == "human":
                clean_group["titleBy"] = "human"
            clean_groups[gid] = clean_group
            member_owned.update(members)
        elif len(members) == 1:
            group_degrade[gid] = members[0]
        # 0 members -> group vanishes entirely

    # 2. Build the ordered include from chapter_ids (group ids allowed; members of surviving groups
    #    are dropped from the top level; degraded groups become their lone member).
    requested: list[str] = []
    seen: set[str] = set()
    for cid in chapter_ids or []:
        s = str(cid)
        if s in seen:
            continue
        if s in clean_groups:
            requested.append(s)
            seen.add(s)
        elif s in group_degrade:
            lone = group_degrade[s]
            if lone not in seen and lone not in member_owned:
                requested.append(lone)
                seen.add(lone)
        elif s.startswith("doc-grp-"):
            continue  # unknown / emptied group id
        elif s in member_owned:
            continue  # owned by a surviving group -> not standalone
        elif _valid_member(s) or s in structural:
            requested.append(s)
            seen.add(s)
    # defensive: a structural chapter must never be dropped — append any missing in directory order.
    for cid in dir_ids:
        if cid in structural and cid not in seen:
            requested.append(cid)
            seen.add(cid)
    from contingency_assembly import store as _outline_store

    return _outline_store.set_include(
        project_key, requested, groups=clean_groups, edited_by="数字孪生决策台"
    )


def reset_contingency_chapters(project_key: str | None = None) -> dict[str, Any]:
    """还原默认章节目录：清空本项目的 ContingencyOutline overlay → 报告回到全量本体目录。"""
    from contingency_assembly import store as _outline_store

    return _outline_store.reset_outline(project_key)


def _contingency_pk_field(object_type: str) -> str:
    """Primary-key property apiName for a contingency ObjectType, or '' if undeclared."""
    schema = _contingency_object_schema(object_type)
    keys = schema.get("primaryKeyPropertyApiNames") if isinstance(schema, dict) else None
    if isinstance(keys, list) and keys:
        return str(keys[0])
    return ""


def _contingency_value_types() -> dict[str, Any]:
    """Load the delivery-contingency-plan ontology Value Type definitions."""
    path = BASE_DIR / _CONTINGENCY_SCHEMA_DIRNAME / "value-types.json"
    try:
        value_types = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value_types if isinstance(value_types, dict) else {}


def _contingency_property_value_type_map(object_type: str) -> dict[str, str]:
    """Map a contingency ObjectType's property apiName -> bound Value Type apiName."""
    schema = _contingency_object_schema(object_type)
    properties = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(properties, dict):
        return {}
    return {
        api_name: str(prop["valueType"])
        for api_name, prop in properties.items()
        if isinstance(prop, dict) and prop.get("valueType")
    }


def _contingency_runrecord_path(object_type: str) -> Path:
    """Local run-record overlay store for a writable contingency ObjectType.

    The metadata-only contingency ontology has no CSV; adopted run records (e.g. RiskItems
    materialized from derived suggestions) are persisted here until/unless an external pipeline
    loads them into Dolt. Mirrors the template(read-only) vs run-record(writable) split declared
    in the contingency datasource bindings.
    """
    return BASE_DIR / _CONTINGENCY_SCHEMA_DIRNAME / "runtime" / f"{object_type}.json"


def _read_contingency_runrecord(object_type: str) -> list[dict[str, Any]]:
    path = _contingency_runrecord_path(object_type)
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _write_contingency_runrecord(object_type: str, rows: list[dict[str, Any]]) -> None:
    path = _contingency_runrecord_path(object_type)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def _merge_contingency_rows(
    base: list[dict[str, Any]], overlay: list[dict[str, Any]], pk_field: str
) -> list[dict[str, Any]]:
    """Union base rows with the run-record overlay; overlay wins on primary-key collision."""
    if not pk_field:
        return list(base) + list(overlay)
    overlay_by_key = {str(row.get(pk_field)): row for row in overlay if isinstance(row, dict)}
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in base:
        key = str(row.get(pk_field))
        merged.append(overlay_by_key.get(key, row))
        seen.add(key)
    for row in overlay:
        key = str(row.get(pk_field))
        if key not in seen:
            merged.append(row)
            seen.add(key)
    return merged


def _resolve_create_object_record(
    action_schema: dict[str, Any], payload: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    """Resolve a CREATE_OBJECT edit's propertyUpdates into a concrete object record.

    Substitutes ${param} templates from the Action payload and keeps literal values; omits
    properties whose ${param} is absent/blank so schema defaults and required-field checks apply.
    """
    edits = action_schema.get("edits", []) if isinstance(action_schema, dict) else []
    for edit in edits:
        if not isinstance(edit, dict) or edit.get("type") != "CREATE_OBJECT":
            continue
        object_type = str(edit.get("objectTypeApiName") or "").strip()
        record: dict[str, Any] = {}
        for field, template in (edit.get("propertyUpdates") or {}).items():
            if isinstance(template, str) and template.startswith("${") and template.endswith("}"):
                param = template[2:-1]
                value = payload.get(param)
                if value is None or (isinstance(value, str) and value.strip() == ""):
                    continue
                record[str(field)] = value
            else:
                record[str(field)] = template
        return object_type, record
    raise ValueError("Action has no CREATE_OBJECT edit to materialize.")


def _resolve_followon_lifecycle_edits(
    action_schema: dict[str, Any], payload: dict[str, Any]
) -> list[tuple[dict[str, Any], str, str, dict[str, Any]]]:
    """Resolve MODIFY_OBJECT edits riding behind a CREATE_OBJECT edit (lifecycle bumps).

    A create Action may declare follow-on MODIFY_OBJECT edits that advance the lifecycle
    state of an *anchor* object the new record attaches to (e.g. CreateDeliverabilityAssessment
    bumps its ContingencyPlan DRAFT -> ASSESSING; GenerateRemediationTask with gapId moves that
    GapItem OPEN -> IN_PROGRESS). Each edit locates its target row by `lookupBy`
    ({pkField: "${param}"}): a blank/absent lookup parameter skips the edit (optional linkage),
    while a supplied key must resolve to a real row at validation time. Returns
    (edit, object_type, object_key, changes) tuples for the edits that apply.
    """
    edits = action_schema.get("edits", []) if isinstance(action_schema, dict) else []
    resolved: list[tuple[dict[str, Any], str, str, dict[str, Any]]] = []
    for edit in edits:
        if not isinstance(edit, dict) or edit.get("type") != "MODIFY_OBJECT":
            continue
        object_type = str(edit.get("objectTypeApiName") or "").strip()
        lookup = edit.get("lookupBy")
        if not object_type or not isinstance(lookup, dict) or not lookup:
            raise ValueError(
                "Follow-on MODIFY_OBJECT edits in a CREATE action require objectTypeApiName and lookupBy."
            )
        pk_field = _contingency_pk_field(object_type)
        object_key = ""
        skip = False
        for field, template in lookup.items():
            value: Any = template
            if isinstance(template, str) and template.startswith("${") and template.endswith("}"):
                value = payload.get(template[2:-1])
            text = str(value or "").strip()
            if not text:
                skip = True  # optional linkage not supplied -> lifecycle bump does not apply
                break
            if str(field) == pk_field:
                object_key = text
        if skip:
            continue
        if not object_key:
            raise ValueError(
                f"Follow-on edit for `{object_type}` lookupBy must include its primary key `{pk_field}`."
            )
        changes: dict[str, Any] = {}
        for field, template in (edit.get("propertyUpdates") or {}).items():
            if isinstance(template, str) and template.startswith("${") and template.endswith("}"):
                value = payload.get(template[2:-1])
                if value is None or (isinstance(value, str) and value.strip() == ""):
                    continue
                changes[str(field)] = value
            else:
                changes[str(field)] = template
        if changes:
            resolved.append((edit, object_type, object_key, changes))
    return resolved


def _validate_followon_lifecycle_edit(
    action_name: str,
    edit: dict[str, Any],
    object_type: str,
    object_key: str,
    changes: dict[str, Any],
) -> dict[str, Any]:
    """Validate one follow-on lifecycle edit; returns the target's current row.

    Mirrors the modify-path guards: the target row must exist (Dolt ∪ overlay), the changed
    fields must be declared properties passing their Value Types, and the edit's own inline
    `stateTransitions` spec governs the from->to move (so a CLOSED gap or an APPROVED plan
    rejects the bump instead of silently regressing).
    """
    _ensure_supported_object_type(object_type)
    pk_field = _contingency_pk_field(object_type)
    if not pk_field:
        raise ValueError(f"Object type `{object_type}` declares no primary key.")
    property_names = _object_property_names(object_type)
    invalid_fields = sorted(field for field in changes if field not in property_names)
    if invalid_fields:
        raise ValueError(f"Unsupported field(s): {', '.join(invalid_fields)}")
    _validate_action_value_type_changes(object_type, changes)
    current_row = next(
        (row for row in contingency_object_data(object_type) if str(row.get(pk_field)) == object_key),
        None,
    )
    if current_row is None:
        raise KeyError(
            f"{object_type} {pk_field} not found: {object_key} "
            f"(required by `{action_name}` follow-on lifecycle edit)"
        )
    _validate_state_transition_spec(
        action_name, edit.get("stateTransitions"), current_row, changes, object_type
    )
    return current_row


def _write_followon_lifecycle_edit(
    object_type: str, object_key: str, current_row: dict[str, Any], changes: dict[str, Any]
) -> dict[str, Any]:
    """Persist one validated follow-on lifecycle edit into the run-record overlay."""
    pk_field = _contingency_pk_field(object_type)
    updated = {**current_row, **changes}
    rows = [
        row
        for row in _read_contingency_runrecord(object_type)
        if str(row.get(pk_field)) != object_key
    ]
    rows.append(updated)
    _write_contingency_runrecord(object_type, rows)
    return updated


def create_contingency_object(
    action_name: str, action_schema: dict[str, Any], payload: dict[str, Any], *, write: bool = True
) -> dict[str, Any]:
    """Materialize a `writeback: run_record` CREATE_OBJECT Action into the run-record overlay.

    Two validation layers fire on the new record (the create-time subset of the Action engine):
    required-field presence and Value Type constraints (e.g. RiskItem.severity ∈ RiskLevel).
    State-transition and submissionCriteria layers are modify-time guards and do not apply to
    the fresh record itself — but follow-on MODIFY_OBJECT edits (lifecycle bumps on anchor
    objects, located via lookupBy) DO run their own inline stateTransitions spec, and are
    validated before anything is written so a blocked bump rejects the whole action. On write
    the object is upserted by primary key into the run-record overlay, then the lifecycle
    bumps are applied.
    """
    object_type, record = _resolve_create_object_record(action_schema, payload)
    if not object_type:
        raise ValueError(f"Action `{action_name}` CREATE_OBJECT edit is missing objectTypeApiName.")
    schema = _contingency_object_schema(object_type)
    pk_field = _contingency_pk_field(object_type)

    record.setdefault("identifiedAt", date.today().isoformat())
    if pk_field and not str(record.get(pk_field) or "").strip():
        # Default key: plan scope + the most specific discriminator the payload carries
        # (riskPoint for risk-shaped creates, decisionId for decision/assessment-shaped ones).
        record[pk_field] = "_".join(
            part
            for part in (
                str(payload.get("planId") or "PLAN"),
                str(payload.get("riskPoint") or payload.get("decisionId") or object_type),
            )
            if part
        )

    # Thread the cross-cutting ProjectScoped key from the payload when the ObjectType declares it
    # but the Action's edit didn't map it — keeps run-record creates project-scoped (multi-project).
    if "projectKey" in (schema.get("properties") or {}) and not str(record.get("projectKey") or "").strip():
        project_key_val = str(payload.get("projectKey") or "").strip()
        if project_key_val:
            record["projectKey"] = project_key_val

    # Layer 1 — required fields declared on the ObjectType schema.
    missing = sorted(
        api_name
        for api_name, prop in (schema.get("properties") or {}).items()
        if isinstance(prop, dict) and prop.get("required") and not str(record.get(api_name) or "").strip()
    )
    if missing:
        raise ValueError(f"Action `{action_name}` is missing required field(s): {', '.join(missing)}")

    # Layer 2 — Value Type constraints on the resolved property values.
    value_types = _contingency_value_types()
    for api_name, value_type_name in _contingency_property_value_type_map(object_type).items():
        value = record.get(api_name)
        if value is None or (isinstance(value, str) and value.strip() == ""):
            continue
        value_type_def = value_types.get(value_type_name)
        if isinstance(value_type_def, dict):
            _validate_value_against_type(value, value_type_name, value_type_def, f"{object_type}.{api_name}")

    # Layer 3 — follow-on lifecycle edits (anchor-object bumps), validated BEFORE any write
    # so an illegal transition or missing anchor rejects the create as a whole.
    followons = [
        (edit, followon_type, object_key, changes,
         _validate_followon_lifecycle_edit(action_name, edit, followon_type, object_key, changes))
        for edit, followon_type, object_key, changes in _resolve_followon_lifecycle_edits(action_schema, payload)
    ]

    if not write:
        validated: dict[str, Any] = {
            "success": True,
            "actionName": action_name,
            "objectType": object_type,
            "validatedObject": record,
        }
        if followons:
            validated["lifecycleEdits"] = [
                {
                    "objectType": followon_type,
                    _contingency_pk_field(followon_type): object_key,
                    "validatedChanges": dict(changes),
                }
                for _, followon_type, object_key, changes, _row in followons
            ]
        return validated

    rows = [
        row
        for row in _read_contingency_runrecord(object_type)
        if not (pk_field and str(row.get(pk_field)) == str(record.get(pk_field)))
    ]
    rows.append(record)
    _write_contingency_runrecord(object_type, rows)

    result: dict[str, Any] = {
        "success": True,
        "actionName": action_name,
        "objectType": object_type,
        "data": record,
    }
    if pk_field:
        result[pk_field] = record.get(pk_field)
    if followons:
        result["lifecycleEdits"] = [
            {
                "objectType": followon_type,
                _contingency_pk_field(followon_type): object_key,
                "data": _write_followon_lifecycle_edit(followon_type, object_key, current_row, changes),
            }
            for _, followon_type, object_key, changes, current_row in followons
        ]
    return result


def _resolve_modify_object_changes(
    action_schema: dict[str, Any], payload: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    """Resolve a MODIFY_OBJECT edit's propertyUpdates into concrete field changes.

    Mirrors _resolve_create_object_record: substitutes ${param} templates from the Action
    payload, keeps literal values (e.g. status: "APPROVED"), and omits properties whose
    ${param} is absent/blank so partial updates stay partial.
    """
    edits = action_schema.get("edits", []) if isinstance(action_schema, dict) else []
    for edit in edits:
        if not isinstance(edit, dict) or edit.get("type") != "MODIFY_OBJECT":
            continue
        target_parameter = str(edit.get("targetParameter") or "").strip()
        changes: dict[str, Any] = {}
        for field, template in (edit.get("propertyUpdates") or {}).items():
            if isinstance(template, str) and template.startswith("${") and template.endswith("}"):
                param = template[2:-1]
                value = payload.get(param)
                if value is None or (isinstance(value, str) and value.strip() == ""):
                    continue
                changes[str(field)] = value
            else:
                changes[str(field)] = template
        return target_parameter, changes
    raise ValueError("Action has no MODIFY_OBJECT edit to apply.")


def modify_contingency_object(
    action_name: str, action_schema: dict[str, Any], payload: dict[str, Any], *, write: bool = True
) -> dict[str, Any]:
    """Apply (or validate) a `writeback: run_record` MODIFY_OBJECT Action against the overlay.

    Counterpart of create_contingency_object for the modify half of the run-record lifecycle
    (e.g. UpdateRiskStatus on an adopted RiskItem, ApproveContingencyPlan on a created plan).
    Current state is read from Dolt ∪ overlay (contingency_object_data) so both seed rows and
    run-record creates are reachable; the declarative guards run (target constraints, state
    machine, submissionCriteria, Value Types) and the merged row is upserted into the
    run-record overlay — the overlay shadows any Dolt seed row by primary key on the read path.
    """
    object_type = str(action_schema.get("targetObjectTypeApiName") or "").strip()
    if not object_type:
        raise ValueError(f"Action `{action_name}` MODIFY_OBJECT edit is missing targetObjectTypeApiName.")
    _ensure_supported_object_type(object_type)
    _ensure_supported_action(object_type, action_name)

    pk_field = _contingency_pk_field(object_type)
    if not pk_field:
        raise ValueError(f"Object type `{object_type}` declares no primary key.")

    target_parameter, changes = _resolve_modify_object_changes(action_schema, payload)
    object_key = _extract_payload_object_key(payload.get(pk_field), pk_field)
    if not object_key and target_parameter:
        object_key = _extract_payload_object_key(payload.get(target_parameter), pk_field)
    if not object_key:
        raise KeyError(f"payload.{target_parameter or pk_field} is required.")
    object_key = str(object_key)

    changes.pop(pk_field, None)
    if not changes:
        raise ValueError("payload must provide at least one field to update.")
    property_names = _object_property_names(object_type)
    invalid_fields = sorted(field for field in changes if field not in property_names)
    if invalid_fields:
        raise ValueError(f"Unsupported field(s): {', '.join(invalid_fields)}")
    _validate_action_value_type_changes(object_type, changes)

    current_row = next(
        (row for row in contingency_object_data(object_type) if str(row.get(pk_field)) == object_key),
        None,
    )
    if current_row is None:
        raise KeyError(f"{object_type} {pk_field} not found: {object_key}")

    _validate_action_target_constraints(action_name, current_row)
    _validate_action_state_transition(action_name, current_row, changes, object_type)
    _validate_action_submission_criteria(action_name, current_row, changes, object_type)

    if not write:
        return {
            "success": True,
            "actionName": action_name,
            "objectType": object_type,
            pk_field: object_key,
            "validatedChanges": dict(changes),
        }

    updated = {**current_row, **changes}
    rows = [
        row
        for row in _read_contingency_runrecord(object_type)
        if str(row.get(pk_field)) != object_key
    ]
    rows.append(updated)
    _write_contingency_runrecord(object_type, rows)
    return {
        "success": True,
        "actionName": action_name,
        "objectType": object_type,
        pk_field: object_key,
        "data": updated,
    }


def get_backward_key_milestones_graph(project_id: str, selected_anchor_id: str | None = None) -> dict[str, Any]:
    source = _select_sources(project_id)[0]
    ontology = _load_ontology(source, use_effective_sla=True)
    warnings: list[str] = []
    anchor_options_payload: list[dict[str, Any]] = []
    effective_anchor_id: str | None = None
    anchor_date: date
    selected_targets: list[str]
    milestones = _load_project_backward_graph_target_milestones(project_id)
    if not milestones:
        raise ValueError(f"No BACKWARD_TARGET milestones found for project_id `{project_id}`.")
    for milestone in milestones:
        anchor_options_payload.append(_build_backward_anchor_option(milestone))
    choice_ids = [item["id"] for item in anchor_options_payload]
    if selected_anchor_id:
        sid = str(selected_anchor_id).strip()
        if sid not in choice_ids:
            raise ValueError(f"Invalid anchor_id `{sid}`. Allowed: {', '.join(choice_ids)}.")
        effective_anchor_id = sid
    else:
        effective_anchor_id = choice_ids[0]

    selected_milestone = next((item for item in milestones if item.get("milestoneKey") == effective_anchor_id), None)
    if selected_milestone is None:
        raise ValueError(f"Milestone `{effective_anchor_id}` not found in current project targets.")
    anchor_date = _parse_anchor_date_from_milestone(selected_milestone)
    selected_rows = _resolve_target_rows_for_milestone(ontology, selected_milestone, anchor_date=anchor_date)
    selected_targets = [row.localRowKey for row in selected_rows]

    schedule_run = ontology.functions.back_schedule(
        targets=selected_targets,
        anchor_date=anchor_date,
    )
    warnings.extend(schedule_run.warnings)

    result_keys = set(schedule_run.results.keys())
    target_key_set = set(schedule_run.metadata.get("target_keys", []))
    shared_key_set = {
        key
        for key in result_keys
        if sum(1 for target_key in target_key_set if _is_reachable(ontology, key, target_key)) > 1
    }

    nodes = []
    for key in sorted(
        result_keys,
        key=lambda item: (
            schedule_run.results[item].latest_start,
            ontology.row(item).activity.row_order,
        ),
    ):
        row = ontology.row(key)
        schedule = schedule_run.results[key]
        nodes.append(
            {
                "id": row.rowKey,
                "localId": row.localRowKey,
                "name": row.activityName,
                "managementUnit": row.managementUnit,
                "latestStart": schedule.latest_start.isoformat(),
                "latestFinish": schedule.latest_finish.isoformat(),
                "durationDays": row.duration_days,
                "isTarget": key in target_key_set,
                "isShared": key in shared_key_set,
            }
        )

    edges = []
    for key in result_keys:
        row = ontology.row(key)
        for dependency_key in row.activity.dependency_keys:
            if dependency_key not in result_keys:
                continue
            edges.append(
                {
                    "from": ontology.row(dependency_key).rowKey,
                    "to": row.rowKey,
                    "relationType": "depends_on",
                }
            )

    target_rows = [ontology.row(target_key) for target_key in schedule_run.metadata.get("target_keys", [])]
    out: dict[str, Any] = {
        "projectId": project_id,
        "anchorDate": anchor_date.isoformat(),
        "targets": [
            {
                "id": row.rowKey,
                "name": row.activityName,
            }
            for row in target_rows
        ],
        "nodes": nodes,
        "edges": edges,
        "warnings": warnings,
    }
    if anchor_options_payload:
        out["anchorOptions"] = anchor_options_payload
        out["selectedAnchorId"] = effective_anchor_id
    return out


def execute_backward_key_milestones(
    project_id: str,
    selected_anchor_id: str | None = None,
    anchor_id: str | None = None,
    temporary_anchor_dates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    effective_anchor_id = selected_anchor_id if selected_anchor_id is not None else anchor_id
    return _execute_backward_key_milestones(
        project_id,
        selected_anchor_id=effective_anchor_id,
        temporary_anchor_dates=temporary_anchor_dates,
    )


def apply_backward_key_milestones_action(project_id: str, selected_anchor_id: str | None = None) -> dict[str, Any]:
    raise ValueError(
        "Action Exclusive: executeBackwardKeyMilestones is a dry-run skill only. "
        "Collect proposed_mutations and call the OSDK Batch Action "
        "UpdateMilestoneDate.batchApply for physical writeback."
    )


def _execute_backward_key_milestones(
    project_id: str,
    selected_anchor_id: str | None = None,
    temporary_anchor_dates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = _select_sources(project_id)[0]
    ontology = _load_ontology(source, use_effective_sla=True)
    raw_milestones = _load_project_backward_target_milestones(project_id)
    milestones: list[dict[str, Any]] = []

    temporary_dates = {
        str(key).strip(): str(value).strip()
        for key, value in (temporary_anchor_dates or {}).items()
        if str(key).strip()
    }
    anchor_options_payload: list[dict[str, Any]] = []
    for milestone in raw_milestones:
        milestone_key = str(milestone.get("milestoneKey", "")).strip()
        option_milestone = dict(milestone)
        if milestone_key in temporary_dates:
            option_milestone["anchorDate"] = temporary_dates[milestone_key]
        milestones.append(option_milestone)
        anchor_options_payload.append(_build_backward_anchor_option(option_milestone))

    if not milestones:
        raise ValueError(f"No BACKWARD_TARGET milestones found for project_id `{project_id}`.")

    choice_ids = [item["id"] for item in anchor_options_payload]
    if selected_anchor_id:
        sid = str(selected_anchor_id).strip()
        if sid not in choice_ids:
            raise ValueError(f"Invalid anchor_id `{sid}`. Allowed: {', '.join(choice_ids)}.")
        effective_anchor_id = sid
    else:
        effective_anchor_id = choice_ids[0]

    selected_milestone = next((item for item in milestones if item.get("milestoneKey") == effective_anchor_id), None)
    if selected_milestone is None:
        raise ValueError(f"Milestone `{effective_anchor_id}` not found in current project targets.")

    if _should_use_pod_priority_backward(selected_milestone, milestones):
        return _execute_pod_priority_power_on_backward(
            project_id,
            source,
            ontology,
            milestones,
            selected_milestone,
            anchor_options_payload,
        )

    return _execute_single_backward_key_milestone(
        project_id,
        source,
        ontology,
        selected_milestone,
        anchor_options_payload=anchor_options_payload,
        execution_mode="SINGLE_ANCHOR",
    )


def _execute_single_backward_key_milestone(
    project_id: str,
    source: ProjectSource,
    ontology: LocalScheduleOntology,
    selected_milestone: dict[str, Any],
    *,
    anchor_options_payload: list[dict[str, Any]] | None = None,
    execution_mode: str = "SINGLE_ANCHOR",
) -> dict[str, Any]:
    anchor_date, target_dates, warnings = _backward_target_dates_for_milestone(ontology, selected_milestone)
    return _build_backward_result_from_target_dates(
        project_id,
        source,
        ontology,
        selected_milestone,
        anchor_date,
        target_dates,
        warnings,
        anchor_options_payload=anchor_options_payload,
        execution_mode=execution_mode,
    )


def _backward_target_dates_for_milestone(
    ontology: LocalScheduleOntology,
    selected_milestone: dict[str, Any],
) -> tuple[date, dict[str, dict[str, str]], list[str]]:
    anchor_date = _parse_anchor_date_from_milestone(selected_milestone)
    selected_rows = _resolve_target_rows_for_milestone(ontology, selected_milestone, anchor_date=anchor_date)
    schedule_run = ontology.functions.back_schedule(
        targets=[row.localRowKey for row in selected_rows],
        anchor_date=anchor_date,
    )
    target_dates: dict[str, dict[str, str]] = {}
    for local_key, schedule in schedule_run.results.items():
        row = ontology.row(local_key)
        target_dates[str(row.rowKey)] = {
            "startDate": schedule.latest_start.isoformat(),
            "endDate": schedule.latest_finish.isoformat(),
        }
    return anchor_date, target_dates, list(schedule_run.warnings)


def _build_backward_result_from_target_dates(
    project_id: str,
    source: ProjectSource,
    ontology: LocalScheduleOntology,
    selected_milestone: dict[str, Any],
    anchor_date: date,
    target_dates: dict[str, dict[str, str]],
    warnings: list[str],
    *,
    anchor_options_payload: list[dict[str, Any]] | None = None,
    execution_mode: str = "SINGLE_ANCHOR",
    summary_extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    effective_anchor_id = str(selected_milestone.get("milestoneKey", "")).strip()
    source_columns = _api_to_source_columns(DELIVERY_PLAN_ROW_OBJECT_TYPE)
    start_column = source_columns.get("startDate")
    end_column = source_columns.get("endDate")
    if not start_column or not end_column:
        raise ValueError("DeliveryPlanRow source columns for startDate/endDate are not configured.")

    # Dry-run may read the current source values to compute a diff, but it must never
    # mutate csv_rows or call _write_csv. Physical writeback belongs to OSDK Actions.
    csv_rows, _fieldnames = _read_csv(source.path)
    changed_row_keys: set[str] = set()
    proposed_mutations: list[dict[str, Any]] = []
    selected_label = str(selected_milestone.get("milestoneName", "倒排锚点"))
    reason_prefix = f"基于倒排锚点 `{selected_label}`（{anchor_date.isoformat()}）和依赖网络重新计算"
    for row_key, dates_by_field in target_dates.items():
        row = ontology.row(row_key)
        row_index = row.activity.row_order
        if row_index < 0 or row_index >= len(csv_rows):
            continue
        next_start = dates_by_field.get("startDate", "")
        next_end = dates_by_field.get("endDate", "")
        current_start = str(csv_rows[row_index].get(start_column, ""))
        current_end = str(csv_rows[row_index].get(end_column, ""))
        row_key = str(row.rowKey)
        # Emit one mutation per changed field so the UI can preview and approve
        # startDate/endDate independently without overwriting ground truth state.
        if _is_semantic_date_change(current_start, next_start):
            proposed_mutations.append(
                {
                    "milestoneId": row_key,
                    "rowKey": row_key,
                    "field": "startDate",
                    "originalDate": current_start,
                    "newDate": next_start,
                    "changeType": "UPDATE_START_DATE",
                    "reason": f"{reason_prefix}开始日期。",
                }
            )
            changed_row_keys.add(row_key)
        if _is_semantic_date_change(current_end, next_end):
            proposed_mutations.append(
                {
                    "milestoneId": row_key,
                    "rowKey": row_key,
                    "field": "endDate",
                    "originalDate": current_end,
                    "newDate": next_end,
                    "changeType": "UPDATE_END_DATE",
                    "reason": f"{reason_prefix}结束日期。",
                }
            )
            changed_row_keys.add(row_key)

    return {
        "status": "DRY_RUN_READY",
        "projectId": project_id,
        "selectedAnchorId": effective_anchor_id,
        "anchorDate": anchor_date.isoformat(),
        "summary": {
            "projectId": project_id,
            "selectedAnchorId": effective_anchor_id,
            "anchorDate": anchor_date.isoformat(),
            "affectedNodeCount": len(changed_row_keys),
            "mutationCount": len(proposed_mutations),
            "warningCount": len(warnings),
            "executionMode": execution_mode,
            **(summary_extras or {}),
        },
        "proposed_mutations": proposed_mutations,
        "warnings": list(warnings),
        "anchorOptions": anchor_options_payload or [],
    }


def _is_project_power_on_milestone(milestone: dict[str, Any]) -> bool:
    return (
        str(milestone.get("milestoneType", "")).strip() == "POWER_ON"
        and _is_project_global_milestone(milestone)
    )


def _is_pod_power_on_milestone(milestone: dict[str, Any]) -> bool:
    return (
        str(milestone.get("milestoneType", "")).strip() == "POWER_ON"
        and str(milestone.get("scopeType", "")).strip() == "POD"
        and bool(str(milestone.get("scopeKey", "")).strip())
    )


def _should_use_pod_priority_backward(
    selected_milestone: dict[str, Any],
    milestones: list[dict[str, Any]],
) -> bool:
    if not _is_project_power_on_milestone(selected_milestone):
        return False
    return any(_is_pod_power_on_milestone(milestone) for milestone in milestones)


def _pod_milestone_with_project_fallback_date(
    pod_milestone: dict[str, Any],
    project_anchor_date: date,
) -> dict[str, Any]:
    out = dict(pod_milestone)
    if not str(out.get("anchorDate", "")).strip():
        out["anchorDate"] = project_anchor_date.isoformat()
    return out


def _mutation_row_key(mutation: dict[str, Any]) -> str:
    return str(mutation.get("rowKey") or mutation.get("milestoneId") or "").strip()


def _mutation_field(mutation: dict[str, Any]) -> str:
    return str(mutation.get("field") or "").strip()


def _mutation_sort_date(mutation: dict[str, Any]) -> date | None:
    return _try_parse_plan_date(str(mutation.get("newDate") or ""))


def _should_replace_backward_mutation(
    current: dict[str, Any],
    candidate: dict[str, Any],
) -> bool:
    current_date = _mutation_sort_date(current)
    candidate_date = _mutation_sort_date(candidate)
    if current_date is not None and candidate_date is not None:
        return candidate_date < current_date
    if candidate_date is not None and current_date is None:
        return True
    return False


def _row_management_units(row: Any) -> set[str]:
    raw_unit = getattr(row, "managementUnit", None)
    if raw_unit is None:
        raw_unit = getattr(row, "management_unit", "")
    return set(_split_management_units(raw_unit))


def _filter_project_fallback_mutations(
    fallback_result: dict[str, Any],
    ontology: LocalScheduleOntology,
    covered_scope_keys: set[str],
) -> list[dict[str, Any]]:
    if not covered_scope_keys:
        return [
            dict(mutation)
            for mutation in fallback_result.get("proposed_mutations") or []
            if isinstance(mutation, dict)
        ]

    filtered: list[dict[str, Any]] = []
    for mutation in fallback_result.get("proposed_mutations") or []:
        if not isinstance(mutation, dict):
            continue
        row_key = _mutation_row_key(mutation)
        try:
            row_units = _row_management_units(ontology.row(row_key))
        except Exception:
            row_units = set()
        if row_units and row_units.intersection(covered_scope_keys):
            continue
        filtered.append(dict(mutation))
    return filtered


def _filter_project_fallback_target_dates(
    target_dates: dict[str, dict[str, str]],
    ontology: LocalScheduleOntology,
    covered_scope_keys: set[str],
) -> dict[str, dict[str, str]]:
    if not covered_scope_keys:
        return {row_key: dict(dates_by_field) for row_key, dates_by_field in target_dates.items()}

    filtered: dict[str, dict[str, str]] = {}
    for row_key, dates_by_field in target_dates.items():
        try:
            row_units = _row_management_units(ontology.row(row_key))
        except Exception:
            row_units = set()
        if row_units and row_units.intersection(covered_scope_keys):
            continue
        filtered[row_key] = dict(dates_by_field)
    return filtered


def _should_replace_backward_target(current: str, candidate: str) -> bool:
    current_date = _try_parse_plan_date(current)
    candidate_date = _try_parse_plan_date(candidate)
    if current_date is not None and candidate_date is not None:
        return candidate_date < current_date
    if candidate_date is not None and current_date is None:
        return True
    return False


def _merge_backward_target_dates(
    target_sets: list[dict[str, dict[str, str]]],
) -> dict[str, dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    for target_dates in target_sets:
        for row_key, dates_by_field in target_dates.items():
            row_targets = merged.setdefault(row_key, {})
            for field in ("startDate", "endDate"):
                candidate = str(dates_by_field.get(field) or "").strip()
                if not candidate:
                    continue
                current = row_targets.get(field)
                if current is None or _should_replace_backward_target(current, candidate):
                    row_targets[field] = candidate
    return merged


def _dedupe_warnings(warnings: list[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in warnings:
        warning = str(value or "").strip()
        if not warning or warning in seen:
            continue
        seen.add(warning)
        out.append(warning)
    return out


def _merge_backward_dry_runs_for_pod_priority(
    project_id: str,
    selected_milestone: dict[str, Any],
    project_anchor_date: date,
    pod_results: list[dict[str, Any]],
    fallback_result: dict[str, Any],
    fallback_mutations: list[dict[str, Any]],
    anchor_options_payload: list[dict[str, Any]],
) -> dict[str, Any]:
    mutation_by_key: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    seen_warnings: set[str] = set()

    def add_warning(value: Any) -> None:
        warning = str(value or "").strip()
        if not warning or warning in seen_warnings:
            return
        seen_warnings.add(warning)
        warnings.append(warning)

    def add_mutation(mutation: dict[str, Any]) -> None:
        row_key = _mutation_row_key(mutation)
        field = _mutation_field(mutation)
        if not row_key or field not in {"startDate", "endDate"}:
            return
        key = f"{row_key}:{field}"
        current = mutation_by_key.get(key)
        candidate = dict(mutation)
        if current is None or _should_replace_backward_mutation(current, candidate):
            mutation_by_key[key] = candidate

    for result in pod_results:
        for mutation in result.get("proposed_mutations") or []:
            if isinstance(mutation, dict):
                add_mutation(mutation)
        for warning in result.get("warnings") or []:
            add_warning(warning)

    for mutation in fallback_mutations:
        add_mutation(mutation)
    for warning in fallback_result.get("warnings") or []:
        add_warning(warning)

    proposed_mutations = list(mutation_by_key.values())
    affected_rows = {
        _mutation_row_key(mutation)
        for mutation in proposed_mutations
        if _mutation_row_key(mutation)
    }
    selected_anchor_id = str(selected_milestone.get("milestoneKey", "")).strip()
    summary = {
        "projectId": project_id,
        "selectedAnchorId": selected_anchor_id,
        "anchorDate": project_anchor_date.isoformat(),
        "affectedNodeCount": len(affected_rows),
        "mutationCount": len(proposed_mutations),
        "warningCount": len(warnings),
        "executionMode": "POD_PRIORITY",
        "podPriorityAnchorCount": len(pod_results),
        "projectFallbackAnchorId": selected_anchor_id,
    }
    return {
        "status": "DRY_RUN_READY",
        "projectId": project_id,
        "selectedAnchorId": selected_anchor_id,
        "anchorDate": project_anchor_date.isoformat(),
        "summary": summary,
        "proposed_mutations": proposed_mutations,
        "warnings": warnings,
        "anchorOptions": anchor_options_payload,
    }


def _execute_pod_priority_power_on_backward(
    project_id: str,
    source: ProjectSource,
    ontology: LocalScheduleOntology,
    milestones: list[dict[str, Any]],
    selected_milestone: dict[str, Any],
    anchor_options_payload: list[dict[str, Any]],
) -> dict[str, Any]:
    project_anchor_date = _parse_anchor_date_from_milestone(selected_milestone)
    pod_milestones = [
        milestone
        for milestone in milestones
        if _is_pod_power_on_milestone(milestone)
    ]
    covered_scope_keys = {
        str(milestone.get("scopeKey", "")).strip()
        for milestone in pod_milestones
        if str(milestone.get("scopeKey", "")).strip()
    }
    target_sets: list[dict[str, dict[str, str]]] = []
    warnings: list[Any] = []
    for pod_milestone in pod_milestones:
        _pod_anchor_date, pod_targets, pod_warnings = _backward_target_dates_for_milestone(
            ontology,
            _pod_milestone_with_project_fallback_date(pod_milestone, project_anchor_date),
        )
        target_sets.append(pod_targets)
        warnings.extend(pod_warnings)

    _fallback_anchor_date, fallback_targets, fallback_warnings = _backward_target_dates_for_milestone(
        ontology,
        selected_milestone,
    )
    target_sets.append(
        _filter_project_fallback_target_dates(
            fallback_targets,
            ontology,
            covered_scope_keys,
        )
    )
    warnings.extend(fallback_warnings)

    return _build_backward_result_from_target_dates(
        project_id,
        source,
        ontology,
        selected_milestone,
        project_anchor_date,
        _merge_backward_target_dates(target_sets),
        _dedupe_warnings(warnings),
        anchor_options_payload=anchor_options_payload,
        execution_mode="POD_PRIORITY",
        summary_extras={
            "podPriorityAnchorCount": len(pod_milestones),
            "projectFallbackAnchorId": str(selected_milestone.get("milestoneKey", "")).strip(),
        },
    )


def execute_forward_key_milestones(
    project_id: str,
    temporary_anchor: dict[str, Any] | None = None,
    temporaryAnchor: dict[str, Any] | None = None,
    manual_overrides: list[dict[str, Any]] | None = None,
    manualOverrides: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return _execute_forward_key_milestones(
        project_id,
        temporary_anchor or temporaryAnchor,
        manual_overrides if manual_overrides is not None else manualOverrides,
    )


def apply_forward_key_milestones_action(project_id: str) -> dict[str, Any]:
    raise ValueError(
        "Action Exclusive: executeForwardKeyMilestones is a dry-run skill only. "
        "Collect proposed_mutations and call the OSDK Batch Action "
        "UpdateMilestoneDate.batchApply for physical writeback."
    )


def _execute_forward_key_milestones(
    project_id: str,
    temporary_anchor: dict[str, Any] | None = None,
    manual_overrides: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from llm_openrouter_forwardschedule import AnchorWindow

    source = _select_sources(project_id)[0]
    ontology = _load_ontology(source, use_effective_sla=True)
    source_columns = _api_to_source_columns(DELIVERY_PLAN_ROW_OBJECT_TYPE)
    start_column = source_columns.get("startDate")
    end_column = source_columns.get("endDate")
    if not start_column or not end_column:
        raise ValueError("DeliveryPlanRow source columns for startDate/endDate are not configured.")

    csv_rows, _fieldnames = _read_csv(source.path)
    explicit_anchors: dict[str, Any] = {}
    anchor_milestones: list[dict[str, Any]] = []
    temporary_anchor_row_key = ""
    reason_prefix = ""
    anchor_mutation_reason = ""
    anchor_mode = "milestone"
    mutation_set = ScheduleMutationSet()
    preview_results: dict[str, Any] | None = None
    if manual_overrides:
        preview_explicit_anchors: dict[str, Any] = {}
        milestones = _load_project_forward_start_milestones(project_id)
        if not milestones:
            raise ValueError(f"No FORWARD_START milestones found for project_id `{project_id}`.")
        for milestone in milestones:
            anchor_date = _parse_forward_anchor_date_from_milestone(milestone)
            selected_rows = _resolve_forward_rows_for_milestone(ontology, milestone)
            for row in selected_rows:
                preview_explicit_anchors[row.localRowKey] = AnchorWindow(
                    start=anchor_date,
                    finish=anchor_date,
                    source=str(milestone.get("milestoneKey", "")),
                    explicit=True,
                )
        preview_results = ontology.functions.forward_schedule(
            explicit_anchors=preview_explicit_anchors,
            use_plan_roots=True,
        ).results
    manual_override_records = _parse_forward_manual_overrides(
        ontology,
        manual_overrides,
        csv_rows,
        start_column,
        end_column,
        preview_results,
    )

    if manual_override_records:
        anchor_mode = "manual_override"
        manual_rows_by_key: dict[str, ForwardManualOverrideRecord] = {}
        for override in manual_override_records:
            row_key = str(override.row.rowKey)
            manual_rows_by_key[row_key] = override
            explicit_anchors[override.row.localRowKey] = AnchorWindow(
                start=override.start_date,
                finish=override.end_date,
                source="manual-override",
                explicit=True,
            )
            mutation_set.add_update(
                row_key,
                override.field,
                override.new_date,
                original_date=override.original_date,
                reason=f"人工调整活动 `{override.row.activityName}` 的{_date_field_label(override.field)}。",
                is_manual_override=True,
            )
        anchor_milestones.extend(
            {
                "milestoneKey": row_key,
                "milestoneType": "MANUAL_OVERRIDE",
                "milestoneName": str(override.row.activityName),
                "anchorDate": override.end_date.isoformat(),
                "rowKeys": [row_key],
            }
            for row_key, override in manual_rows_by_key.items()
        )
        milestones = _load_project_forward_start_milestones(project_id)
        if not milestones:
            raise ValueError(f"No FORWARD_START milestones found for project_id `{project_id}`.")
        for milestone in milestones:
            anchor_date = _parse_forward_anchor_date_from_milestone(milestone)
            selected_rows = _resolve_forward_rows_for_milestone(ontology, milestone)
            for row in selected_rows:
                if row.localRowKey in explicit_anchors:
                    continue
                explicit_anchors[row.localRowKey] = AnchorWindow(
                    start=anchor_date,
                    finish=anchor_date,
                    source=str(milestone.get("milestoneKey", "")),
                    explicit=True,
                )
            anchor_milestones.append(
                {
                    "milestoneKey": str(milestone.get("milestoneKey", "")),
                    "milestoneType": str(milestone.get("milestoneType", "")),
                    "milestoneName": str(milestone.get("milestoneName", "")),
                    "anchorDate": anchor_date.isoformat(),
                    "rowKeys": [str(row.rowKey) for row in selected_rows],
                }
            )
        reason_prefix = f"基于 {len(manual_override_records)} 项人工调整重新正排"
    elif temporary_anchor is not None:
        row, start_date, end_date, changed_field = _parse_temporary_forward_anchor(ontology, temporary_anchor)
        temporary_anchor_row_key = str(row.rowKey)
        explicit_anchors[row.localRowKey] = AnchorWindow(
            start=start_date,
            finish=end_date,
            source="temporary-activity-edit",
            explicit=True,
        )
        field_label = "开始日期" if changed_field == "startDate" else "结束日期"
        reason_prefix = f"基于活动 `{row.activityName}` 的临时{field_label}执行正排沙箱推演"
        anchor_mutation_reason = f"{reason_prefix}。"
        anchor_mode = "temporary_activity"
        anchor_milestones.append(
            {
                "milestoneKey": temporary_anchor_row_key,
                "milestoneType": "TEMPORARY_ACTIVITY",
                "milestoneName": str(row.activityName),
                "anchorDate": end_date.isoformat(),
                "rowKeys": [temporary_anchor_row_key],
            }
        )
    else:
        milestones = _load_project_forward_start_milestones(project_id)
        if not milestones:
            raise ValueError(f"No FORWARD_START milestones found for project_id `{project_id}`.")

        for milestone in milestones:
            anchor_date = _parse_forward_anchor_date_from_milestone(milestone)
            selected_rows = _resolve_forward_rows_for_milestone(ontology, milestone)
            for row in selected_rows:
                explicit_anchors[row.localRowKey] = AnchorWindow(
                    start=anchor_date,
                    finish=anchor_date,
                    source=str(milestone.get("milestoneKey", "")),
                    explicit=True,
                )
            anchor_milestones.append(
                {
                    "milestoneKey": str(milestone.get("milestoneKey", "")),
                    "milestoneType": str(milestone.get("milestoneType", "")),
                    "milestoneName": str(milestone.get("milestoneName", "")),
                    "anchorDate": anchor_date.isoformat(),
                    "rowKeys": [str(row.rowKey) for row in selected_rows],
                }
            )

        anchor_names = [str(item.get("milestoneName") or item.get("milestoneType") or "正排锚点") for item in anchor_milestones]
        anchor_summary = "、".join(anchor_names[:3])
        if len(anchor_names) > 3:
            anchor_summary = f"{anchor_summary} 等 {len(anchor_names)} 个"
        reason_prefix = f"基于正排锚点 `{anchor_summary}` 和依赖网络重新计算"

    schedule_run = ontology.functions.forward_schedule(
        explicit_anchors=explicit_anchors,
        use_plan_roots=True,
    )

    for local_key, schedule in schedule_run.results.items():
        row = ontology.row(local_key)
        row_index = row.activity.row_order
        if row_index < 0 or row_index >= len(csv_rows):
            continue
        next_start = schedule.start.isoformat()
        next_end = schedule.finish.isoformat()
        current_start = str(csv_rows[row_index].get(start_column, ""))
        current_end = str(csv_rows[row_index].get(end_column, ""))
        row_key = str(row.rowKey)
        if _is_semantic_date_change(current_start, next_start):
            mutation_set.add_update(
                row_key,
                "startDate",
                next_start,
                original_date=current_start,
                reason=anchor_mutation_reason if row_key == temporary_anchor_row_key else f"{reason_prefix}开始日期。",
            )
        if _is_semantic_date_change(current_end, next_end):
            mutation_set.add_update(
                row_key,
                "endDate",
                next_end,
                original_date=current_end,
                reason=anchor_mutation_reason if row_key == temporary_anchor_row_key else f"{reason_prefix}结束日期。",
            )

    proposed_mutations = mutation_set.mutations
    changed_row_keys = {
        str(mutation.get("rowKey") or mutation.get("milestoneId") or "").strip()
        for mutation in proposed_mutations
        if str(mutation.get("rowKey") or mutation.get("milestoneId") or "").strip()
    }

    return {
        "status": "DRY_RUN_READY",
        "projectId": project_id,
        "summary": {
            "projectId": project_id,
            "affectedNodeCount": len(changed_row_keys),
            "mutationCount": len(proposed_mutations),
            "warningCount": len(schedule_run.warnings),
            "anchorCount": len(anchor_milestones),
            "anchorMode": anchor_mode,
        },
        "proposed_mutations": proposed_mutations,
        "warnings": list(schedule_run.warnings),
        "anchorMilestones": anchor_milestones,
    }


def execute_milestone_compression(
    project_id: str,
    selected_anchor_id: str | None = None,
    anchor_id: str | None = None,
) -> dict[str, Any]:
    from llm_openrouter_milestone_compression import compute_milestone_compression_schedule

    effective_anchor_id = selected_anchor_id if selected_anchor_id is not None else anchor_id
    source = _select_sources(project_id)[0]
    milestones = _load_project_milestone_compression_targets(project_id)
    if not milestones:
        raise ValueError(f"No {MILESTONE_COMPRESSION_TARGET_ROLE} milestones found for project_id `{project_id}`.")

    anchor_options_payload: list[dict[str, Any]] = []
    for milestone in milestones:
        anchor_options_payload.append(
            {
                "id": str(milestone.get("milestoneKey", "")),
                "label": str(milestone.get("milestoneName", "里程碑压缩")),
                "milestoneType": str(milestone.get("milestoneType", "")),
                "anchorDate": str(milestone.get("anchorDate", "")),
                "dependencyMilestoneTypes": str(milestone.get("dependencyMilestoneTypes", "")),
            }
        )

    choice_ids = [item["id"] for item in anchor_options_payload]
    if effective_anchor_id:
        sid = str(effective_anchor_id).strip()
        if sid not in choice_ids:
            raise ValueError(f"Invalid anchor_id `{sid}`. Allowed: {', '.join(choice_ids)}.")
        selected_anchor = sid
    else:
        selected_anchor = choice_ids[0]

    selected_milestone = next((item for item in milestones if item.get("milestoneKey") == selected_anchor), None)
    if selected_milestone is None:
        raise ValueError(f"Milestone `{selected_anchor}` not found in current project compression targets.")

    anchor_date = _parse_anchor_date_from_milestone(selected_milestone)
    ontology = _load_ontology(source, use_effective_sla=True)
    baseline_rows = _resolve_compression_baseline_rows(ontology, selected_milestone)
    baseline_dates = [
        parsed
        for row in baseline_rows
        for parsed in [_try_parse_plan_date(row.endDate)]
        if parsed is not None
    ]
    if not baseline_dates:
        milestone_key = str(selected_milestone.get("milestoneKey", "")).strip() or "<unknown>"
        raise ValueError(f"No parseable endDate found for compression baseline `{milestone_key}`.")
    baseline_date = max(baseline_dates)

    warnings = ontology.copy_warnings()
    results = compute_milestone_compression_schedule(
        ontology.activities,
        baseline_date=baseline_date,
        anchor_date=anchor_date,
        warnings=warnings,
    )

    source_columns = _api_to_source_columns(DELIVERY_PLAN_ROW_OBJECT_TYPE)
    start_column = source_columns.get("startDate")
    end_column = source_columns.get("endDate")
    if not start_column or not end_column:
        raise ValueError("DeliveryPlanRow source columns for startDate/endDate are not configured.")

    csv_rows, _fieldnames = _read_csv(source.path)
    changed_row_keys: set[str] = set()
    proposed_mutations: list[dict[str, Any]] = []
    selected_label = str(selected_milestone.get("milestoneName", "里程碑压缩"))
    shift_days = (anchor_date - baseline_date).days
    if shift_days < 0:
        shift_text = f"整体提前 {abs(shift_days)} 天"
    elif shift_days > 0:
        shift_text = f"整体后移 {shift_days} 天"
    else:
        shift_text = "保持当前日期"
    reason_prefix = (
        f"基于里程碑压缩锚点 `{selected_label}`（{anchor_date.isoformat()}）"
        f"相对到货基准（{baseline_date.isoformat()}）{shift_text}，保持活动工期不变"
    )

    for local_key, schedule in results.items():
        row = ontology.row(local_key)
        row_index = row.activity.row_order
        if row_index < 0 or row_index >= len(csv_rows):
            continue
        row_key = str(row.rowKey)
        if schedule.start is not None:
            next_start = schedule.start.isoformat()
            current_start = str(csv_rows[row_index].get(start_column, ""))
            if _is_semantic_date_change(current_start, next_start):
                proposed_mutations.append(
                    {
                        "milestoneId": row_key,
                        "rowKey": row_key,
                        "field": "startDate",
                        "originalDate": current_start,
                        "newDate": next_start,
                        "changeType": "UPDATE_START_DATE",
                        "reason": f"{reason_prefix}开始日期。",
                    }
                )
                changed_row_keys.add(row_key)
        if schedule.finish is not None:
            next_end = schedule.finish.isoformat()
            current_end = str(csv_rows[row_index].get(end_column, ""))
            if _is_semantic_date_change(current_end, next_end):
                proposed_mutations.append(
                    {
                        "milestoneId": row_key,
                        "rowKey": row_key,
                        "field": "endDate",
                        "originalDate": current_end,
                        "newDate": next_end,
                        "changeType": "UPDATE_END_DATE",
                        "reason": f"{reason_prefix}结束日期。",
                    }
                )
                changed_row_keys.add(row_key)

    dependency_types = _compression_dependency_milestone_types(selected_milestone)
    return {
        "status": "DRY_RUN_READY",
        "projectId": project_id,
        "selectedAnchorId": selected_anchor,
        "anchorDate": anchor_date.isoformat(),
        "baselineDate": baseline_date.isoformat(),
        "shiftDays": shift_days,
        "summary": {
            "projectId": project_id,
            "selectedAnchorId": selected_anchor,
            "anchorDate": anchor_date.isoformat(),
            "baselineDate": baseline_date.isoformat(),
            "shiftDays": shift_days,
            "baselineMilestoneTypes": dependency_types,
            "baselineRowCount": len(baseline_rows),
            "affectedNodeCount": len(changed_row_keys),
            "mutationCount": len(proposed_mutations),
            "warningCount": len(warnings),
        },
        "proposed_mutations": proposed_mutations,
        "warnings": list(warnings),
        "anchorOptions": anchor_options_payload,
    }


def execute_plan_compression_decision(
    project_id: str | None = None,
    projectId: str | None = None,
    power_on_target_date: str | None = None,
    powerOnTargetDate: str | None = None,
    cluster_debug_target_date: str | None = None,
    clusterDebugTargetDate: str | None = None,
    pod_power_on_target_dates: Any | None = None,
    podPowerOnTargetDates: Any | None = None,
    confirmed_arrival_advance_days: Any | None = None,
    confirmedArrivalAdvanceDays: Any | None = None,
    top_n: int | None = None,
    topN: int | None = None,
) -> dict[str, Any]:
    from llm_openrouter_milestone_compression import (
        STRATEGY_PROPORTIONAL,
        STRATEGY_PROPORTIONAL_EXTENSION,
        STRATEGY_TOP3_SLACK,
        compute_duration_compression_schedule,
        compute_duration_extension_schedule,
        compute_milestone_compression_schedule,
    )

    effective_project_id = str(project_id or projectId or "").strip()
    if not effective_project_id:
        raise ValueError("project_id is required.")

    effective_top_n = _normalize_plan_compression_top_n(
        top_n if top_n is not None else topN
    )

    source = _select_sources(effective_project_id)[0]
    ontology = _load_ontology(source, use_effective_sla=True)
    csv_rows, _fieldnames = _read_csv(source.path)
    source_columns = _api_to_source_columns(DELIVERY_PLAN_ROW_OBJECT_TYPE)
    start_column = source_columns.get("startDate")
    end_column = source_columns.get("endDate")
    if not start_column or not end_column:
        raise ValueError("DeliveryPlanRow source columns for startDate/endDate are not configured.")

    power_milestone = _load_project_milestone_by_type(effective_project_id, "POWER_ON")
    cluster_milestone = _load_project_milestone_by_type(effective_project_id, "CLUSTER_DEBUG")
    power_target = _optional_target_date(
        power_on_target_date if power_on_target_date is not None else powerOnTargetDate,
        fallback=_parse_anchor_date_from_milestone(power_milestone),
        field_name="power_on_target_date",
    )
    cluster_target = _optional_target_date(
        cluster_debug_target_date if cluster_debug_target_date is not None else clusterDebugTargetDate,
        fallback=_parse_anchor_date_from_milestone(cluster_milestone),
        field_name="cluster_debug_target_date",
    )
    confirmed_supply_advance_days = _optional_non_negative_int(
        (
            confirmed_arrival_advance_days
            if confirmed_arrival_advance_days is not None
            else confirmedArrivalAdvanceDays
        ),
        field_name="confirmed_arrival_advance_days",
    )

    warnings = ontology.copy_warnings()
    limit_duration_by_key = _limit_duration_by_key(ontology)
    power_rows = _resolve_target_rows_for_milestone(ontology, power_milestone, anchor_date=power_target)
    power_target_keys = [row.localRowKey for row in power_rows]
    power_baseline = _max_row_end_date(power_rows, "POWER_ON")
    pod_power_on_batch_targets, pod_power_on_milestone_mutations = _build_pod_power_on_batch_context(
        project_id=effective_project_id,
        ontology=ontology,
        power_target=power_target,
        power_baseline=power_baseline,
        raw_target_dates=(
            pod_power_on_target_dates
            if pod_power_on_target_dates is not None
            else podPowerOnTargetDates
        ),
    )
    if pod_power_on_batch_targets:
        power_target = max(
            [power_target]
            + [
                item["_targetDate"]
                for item in pod_power_on_batch_targets
                if isinstance(item.get("_targetDate"), date)
            ]
        )
    room_implementation_done_date = _project_room_implementation_done_date(effective_project_id, ontology)
    execution_mode = "POD_BATCH" if pod_power_on_batch_targets else "SINGLE_ANCHOR"
    pod_power_on_batch_count = len({
        str(item.get("targetDate", ""))
        for item in pod_power_on_batch_targets
        if str(item.get("targetDate", "")).strip()
    })

    phases: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []

    phase1_scenarios: list[dict[str, Any]] = []
    phase1_runs: dict[str, dict[str, Any]] = {}
    supply_rows = _resolve_compression_baseline_rows(
        ontology,
        {**power_milestone, "dependencyMilestoneTypes": "ARRIVAL"},
    )
    supply_baseline = _max_row_end_date(supply_rows, "ARRIVAL")
    suggested_supply_target = supply_baseline + (power_target - power_baseline)
    suggested_arrival_advance_days = max(0, (supply_baseline - suggested_supply_target).days)
    supply_target = (
        supply_baseline - timedelta(days=confirmed_supply_advance_days)
        if confirmed_supply_advance_days is not None
        else suggested_supply_target
    )
    effective_arrival_advance_days = max(0, (supply_baseline - supply_target).days)
    supply_parameter_overrides = {
        "roomImplementationDoneDate": room_implementation_done_date.isoformat() if room_implementation_done_date else "",
        "baselineArrivalDate": supply_baseline.isoformat(),
        "suggestedTargetArrivalDate": suggested_supply_target.isoformat(),
        "suggestedArrivalAdvanceDays": suggested_arrival_advance_days,
        "effectiveTargetArrivalDate": supply_target.isoformat(),
        "effectiveArrivalAdvanceDays": effective_arrival_advance_days,
    }
    if confirmed_supply_advance_days is not None:
        supply_parameter_overrides["confirmedArrivalAdvanceDays"] = confirmed_supply_advance_days
    supply_results = compute_milestone_compression_schedule(
        ontology.activities,
        baseline_date=supply_baseline,
        anchor_date=supply_target,
        warnings=warnings,
    )
    supply_mutations = _build_schedule_mutations(
        ontology,
        csv_rows,
        start_column,
        end_column,
        supply_results,
        phase_id="phase1_power_on",
        scenario_id="phase1_supply_shift",
        reason_prefix=(
            "第一阶段供应提前/后移：基于到货节点相对上电目标整体平移，保持活动工期不变，"
            f"目标到货 {supply_target.isoformat()}，目标上电 {power_target.isoformat()}"
        ),
    )
    supply_shift_days = (supply_target - supply_baseline).days
    phase1_scenarios.append(
        {
            "phaseId": "phase1_power_on",
            "scenarioId": "phase1_supply_shift",
            "name": "供应提前",
            "strategy": "SUPPLY_ADVANCE_SHIFT",
            "baselineDate": supply_baseline.isoformat(),
            "targetDate": supply_target.isoformat(),
            "requestedShiftDays": supply_shift_days,
            "mutationCount": len(supply_mutations),
            "isRecommended": False,
            "parameter_overrides": supply_parameter_overrides,
        }
    )
    phase1_runs["phase1_supply_shift"] = {"results": supply_results, "mutations": supply_mutations}
    supply_tool_input = {
        "project_id": effective_project_id,
        "target_supply_date": supply_target.isoformat(),
    }
    if confirmed_supply_advance_days is not None:
        supply_tool_input["confirmed_arrival_advance_days"] = confirmed_supply_advance_days
    tool_calls.append(
        {
            "phaseId": "phase1_power_on",
            "toolName": "preview_plan_supply_shift",
            "input": supply_tool_input,
            "status": "COMPLETED",
        }
    )

    if power_target > power_baseline:
        extension_results = compute_duration_extension_schedule(
            ontology.activities,
            target_keys=power_target_keys,
            baseline_date=power_baseline,
            anchor_date=power_target,
            warnings=warnings,
        )
        extension_mutations = _build_schedule_mutations(
            ontology,
            csv_rows,
            start_column,
            end_column,
            extension_results.results,
            phase_id="phase1_power_on",
            scenario_id="phase1_duration_proportional_extension",
            reason_prefix=(
                "第一阶段目标延后：按关键路径活动当前工期占比等比延长，"
                f"上电目标 {power_target.isoformat()}"
            ),
        )
        phase1_scenarios.append(
            {
                "phaseId": "phase1_power_on",
                "scenarioId": "phase1_duration_proportional_extension",
                "name": "关键路径等比延长",
                "strategy": STRATEGY_PROPORTIONAL_EXTENSION,
                "baselineDate": power_baseline.isoformat(),
                "targetDate": power_target.isoformat(),
                "requestedExtensionDays": extension_results.requested_extension_days,
                "achievedExtensionDays": extension_results.achieved_extension_days,
                "criticalPath": [ontology.row(key).rowKey for key in extension_results.critical_path_keys],
                "allocations": {
                    ontology.row(key).rowKey: days for key, days in extension_results.allocations.items()
                },
                "mutationCount": len(extension_mutations),
                "isRecommended": True,
            }
        )
        phase1_runs["phase1_duration_proportional_extension"] = {
            "results": extension_results.results,
            "mutations": extension_mutations,
        }
        tool_calls.append(
            {
                "phaseId": "phase1_power_on",
                "toolName": "preview_plan_global_proportional_compression",
                "input": {
                    "project_id": effective_project_id,
                    "target_finish_date": power_target.isoformat(),
                    "mode": STRATEGY_PROPORTIONAL_EXTENSION,
                },
                "status": "COMPLETED",
            }
        )
    elif power_target < power_baseline:
        _append_duration_compression_scenarios(
            ontology=ontology,
            activities=ontology.activities,
            csv_rows=csv_rows,
            start_column=start_column,
            end_column=end_column,
            limit_duration_by_key=limit_duration_by_key,
            phase_id="phase1_power_on",
            target_keys=power_target_keys,
            baseline_date=power_baseline,
            target_date=power_target,
            scenarios=phase1_scenarios,
            runs=phase1_runs,
            tool_calls=tool_calls,
            warnings=warnings,
            reason_subject="第一阶段上电目标提前",
            top_n=effective_top_n,
        )
        _mark_recommended_duration_scenario(phase1_scenarios, power_baseline, power_target)
    else:
        phase1_scenarios.append(
            {
                "phaseId": "phase1_power_on",
                "scenarioId": "phase1_noop",
                "name": "无需调整",
                "strategy": "NOOP",
                "baselineDate": power_baseline.isoformat(),
                "targetDate": power_target.isoformat(),
                "mutationCount": 0,
                "isRecommended": True,
            }
        )
        phase1_runs["phase1_noop"] = {"results": {}, "mutations": []}

    if not any(scenario.get("isRecommended") for scenario in phase1_scenarios):
        phase1_scenarios[-1]["isRecommended"] = True
    phase1_recommended_id = _recommended_scenario_id(phase1_scenarios)
    phase1_recommended_run = phase1_runs[phase1_recommended_id]
    activities_after_phase1 = _apply_schedule_results_to_activities(
        ontology.activities,
        phase1_recommended_run["results"],
    )
    phases.append(
        {
            "phaseId": "phase1_power_on",
            "name": "第一阶段：到货到上电",
            "baselineDate": power_baseline.isoformat(),
            "targetDate": power_target.isoformat(),
            "executionMode": execution_mode,
            "podPowerOnBatchCount": pod_power_on_batch_count,
            "recommendedScenarioId": phase1_recommended_id,
            "scenarios": phase1_scenarios,
        }
    )

    cluster_rows = _resolve_target_rows_for_milestone(ontology, cluster_milestone, anchor_date=cluster_target)
    cluster_target_keys = [row.localRowKey for row in cluster_rows]
    cluster_original_baseline = _max_activity_end_date(
        ontology.activities,
        cluster_target_keys,
        "CLUSTER_DEBUG",
    )
    phase2_start_shift_days = (power_target - power_baseline).days
    phase2_analysis_activities = _shift_activity_windows_after_power_batch_boundaries(
        activities_after_phase1,
        reference_activities=ontology.activities,
        boundary_date=power_baseline,
        project_shift_days=phase2_start_shift_days,
        pod_power_on_batch_targets=pod_power_on_batch_targets,
    )
    phase2_uses_virtual_baseline = (
        phase2_start_shift_days > 0
        or any(int(item.get("_shiftDays", 0) or 0) > 0 for item in pod_power_on_batch_targets)
    )
    cluster_baseline = _max_activity_end_date(
        phase2_analysis_activities,
        cluster_target_keys,
        "CLUSTER_DEBUG after phase1",
    )
    phase2_baseline_duration_days = (cluster_original_baseline - power_baseline).days
    phase2_target_duration_days = (cluster_target - power_target).days
    phase2_duration_delta_days = phase2_target_duration_days - phase2_baseline_duration_days
    phase2_scenarios: list[dict[str, Any]] = []
    phase2_runs: dict[str, dict[str, Any]] = {}
    if cluster_target > cluster_baseline:
        extension_results = compute_duration_extension_schedule(
            phase2_analysis_activities,
            target_keys=cluster_target_keys,
            baseline_date=cluster_baseline,
            anchor_date=cluster_target,
            warnings=warnings,
        )
        extension_mutations = _build_schedule_mutations(
            ontology,
            csv_rows,
            start_column,
            end_column,
            extension_results.results,
            phase_id="phase2_cluster_debug",
            scenario_id="phase2_duration_proportional_extension",
            reason_prefix=(
                "第二阶段目标延后：按关键路径活动当前工期占比等比延长，"
                f"集群性能调优目标 {cluster_target.isoformat()}"
            ),
        )
        phase2_scenarios.append(
            {
                "phaseId": "phase2_cluster_debug",
                "scenarioId": "phase2_duration_proportional_extension",
                "name": "关键路径等比延长",
                "strategy": STRATEGY_PROPORTIONAL_EXTENSION,
                "baselineDate": cluster_baseline.isoformat(),
                "targetDate": cluster_target.isoformat(),
                "requestedExtensionDays": extension_results.requested_extension_days,
                "achievedExtensionDays": extension_results.achieved_extension_days,
                "criticalPath": [ontology.row(key).rowKey for key in extension_results.critical_path_keys],
                "allocations": {
                    ontology.row(key).rowKey: days for key, days in extension_results.allocations.items()
                },
                "mutationCount": len(extension_mutations),
                "isRecommended": True,
            }
        )
        phase2_runs["phase2_duration_proportional_extension"] = {
            "results": extension_results.results,
            "mutations": extension_mutations,
        }
        tool_calls.append(
            {
                "phaseId": "phase2_cluster_debug",
                "toolName": "preview_plan_global_proportional_compression",
                "input": {
                    "project_id": effective_project_id,
                    "target_finish_date": cluster_target.isoformat(),
                    "mode": STRATEGY_PROPORTIONAL_EXTENSION,
                },
                "status": "COMPLETED",
            }
        )
    elif cluster_target < cluster_baseline:
        _append_duration_compression_scenarios(
            ontology=ontology,
            activities=phase2_analysis_activities,
            csv_rows=csv_rows,
            start_column=start_column,
            end_column=end_column,
            limit_duration_by_key=limit_duration_by_key,
            phase_id="phase2_cluster_debug",
            target_keys=cluster_target_keys,
            baseline_date=cluster_baseline,
            target_date=cluster_target,
            scenarios=phase2_scenarios,
            runs=phase2_runs,
            tool_calls=tool_calls,
            warnings=warnings,
            reason_subject="第二阶段集群性能调优目标提前",
            virtual_baseline=phase2_uses_virtual_baseline,
            top_n=effective_top_n,
        )
        _mark_recommended_duration_scenario(phase2_scenarios, cluster_baseline, cluster_target)
    else:
        phase2_scenarios.append(
            {
                "phaseId": "phase2_cluster_debug",
                "scenarioId": "phase2_noop",
                "name": "无需调整",
                "strategy": "NOOP",
                "baselineDate": cluster_baseline.isoformat(),
                "targetDate": cluster_target.isoformat(),
                "mutationCount": 0,
                "isRecommended": True,
            }
        )
        phase2_runs["phase2_noop"] = {"results": {}, "mutations": []}

    if not any(scenario.get("isRecommended") for scenario in phase2_scenarios):
        phase2_scenarios[-1]["isRecommended"] = True
    phase2_recommended_id = _recommended_scenario_id(phase2_scenarios)
    phase2_recommended_run = phase2_runs[phase2_recommended_id]
    phases.append(
        {
            "phaseId": "phase2_cluster_debug",
            "name": "第二阶段：上电到集群性能调优",
            "baselineDate": cluster_baseline.isoformat(),
            "targetDate": cluster_target.isoformat(),
            "startBaselineDate": power_baseline.isoformat(),
            "startTargetDate": power_target.isoformat(),
            "endBaselineDate": cluster_original_baseline.isoformat(),
            "endTargetDate": cluster_target.isoformat(),
            "baselineDurationDays": phase2_baseline_duration_days,
            "targetDurationDays": phase2_target_duration_days,
            "durationDeltaDays": phase2_duration_delta_days,
            "executionMode": execution_mode,
            "podPowerOnBatchCount": pod_power_on_batch_count,
            "recommendedScenarioId": phase2_recommended_id,
            "scenarios": phase2_scenarios,
        }
    )

    all_runs: dict[str, dict[str, Any]] = {}
    all_runs.update(phase1_runs)
    all_runs.update(phase2_runs)
    strategy_mutations = _build_plan_compression_strategy_mutations(phases, all_runs)
    llm_semantic_payload = _build_plan_compression_llm_payload(
        phases=phases,
        runs=all_runs,
        warnings=list(warnings),
        top_n=effective_top_n,
    )
    llm_decision = _try_plan_compression_llm_decision(
        project_id=effective_project_id,
        llm_semantic_payload=llm_semantic_payload,
        warnings=list(warnings),
    )
    advisor_runtime = "deterministic_fallback"
    if llm_decision is not None:
        recommended_plan_id = str(llm_decision.get("recommendedPlanId") or "").strip()
        if recommended_plan_id in strategy_mutations:
            advisor_runtime = "llm"
            decision_advice = str(llm_decision.get("decisionAdvice") or "").strip()
            llm_semantic_payload = _merge_plan_compression_llm_decision(
                llm_semantic_payload,
                llm_decision,
                recommended_plan_id=recommended_plan_id,
            )
        else:
            recommended_plan_id = _deterministic_plan_compression_strategy_id(llm_semantic_payload)
            decision_advice = _build_plan_compression_strategy_advice(llm_semantic_payload, recommended_plan_id)
            warnings.append("LLM 计划压缩推荐方案不在三方案工具集合内，已降级为确定性推荐。")
    else:
        recommended_plan_id = _deterministic_plan_compression_strategy_id(llm_semantic_payload)
        decision_advice = _build_plan_compression_strategy_advice(llm_semantic_payload, recommended_plan_id)
        warnings.append("LLM 计划压缩决策分析不可用，已使用三方案确定性分析兜底。")
    llm_semantic_payload = _mark_plan_compression_recommended_strategy(
        llm_semantic_payload,
        recommended_plan_id,
    )
    proposed_mutations = list(strategy_mutations.get(recommended_plan_id, []))
    affected_node_count = len({mutation["rowKey"] for mutation in proposed_mutations})
    return {
        "status": "DRY_RUN_READY",
        "projectId": effective_project_id,
        "summary": {
            "projectId": effective_project_id,
            "phaseCount": len(phases),
            "affectedNodeCount": affected_node_count,
            "mutationCount": len(proposed_mutations),
            "warningCount": len(warnings),
            "advisorRuntime": advisor_runtime,
            "writebackActionApiName": "UpdateMilestoneDate",
            "executionMode": execution_mode,
            "podPowerOnBatchCount": pod_power_on_batch_count,
            "podPowerOnMilestoneMutationCount": len(pod_power_on_milestone_mutations),
        },
        "recommendedPlanId": recommended_plan_id,
        "decisionAdvice": decision_advice,
        "phases": phases,
        "toolCalls": tool_calls,
        "llm_semantic_payload": llm_semantic_payload,
        "proposed_mutations": proposed_mutations,
        "podPowerOnBatchTargets": [
            {
                key: value
                for key, value in target.items()
                if not key.startswith("_")
            }
            for target in pod_power_on_batch_targets
        ],
        "podPowerOnMilestoneMutations": pod_power_on_milestone_mutations,
        "warnings": list(warnings),
    }


def _load_project_milestone_by_type(project_id: str, milestone_type: str) -> dict[str, Any]:
    candidates = [
        milestone
        for milestone in get_object_data(MILESTONE_OBJECT_TYPE, project_id=project_id)
        if str(milestone.get("milestoneType", "")).strip() == milestone_type
    ]
    if not candidates:
        raise ValueError(f"No Milestone with milestoneType `{milestone_type}` found for project_id `{project_id}`.")
    candidates.sort(key=lambda item: (str(item.get("milestoneName", "")), str(item.get("milestoneKey", ""))))
    return candidates[0]


def _optional_target_date(raw_value: Any, *, fallback: date, field_name: str) -> date:
    text = str(raw_value or "").strip()
    if not text:
        return fallback
    normalized = text.replace("/", "-")
    if len(normalized) >= 10:
        normalized = normalized[:10]
    return _required_iso_date_value(normalized, field_name)


def _optional_non_negative_int(raw_value: Any, *, field_name: str) -> int | None:
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    try:
        value = int(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a non-negative integer.") from exc
    if value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")
    return value


def _required_target_date(raw_value: Any, *, field_name: str) -> date:
    text = str(raw_value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required.")
    normalized = text.replace("/", "-")
    if len(normalized) >= 10:
        normalized = normalized[:10]
    return _required_iso_date_value(normalized, field_name)


def _normalized_date_text(raw_value: Any) -> str:
    parsed = _try_parse_plan_date(str(raw_value or ""))
    return parsed.isoformat() if parsed is not None else ""


def _pod_target_date_item_key(item: dict[str, Any]) -> str:
    target = item.get("targetPodPowerOnMilestone")
    if isinstance(target, dict):
        for key in ("milestoneKey", "rowKey", "id", "rid"):
            value = str(target.get(key) or "").strip()
            if value:
                return value
    for key in ("milestoneKey", "milestoneId", "rowKey", "row_key", "id"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return ""


def _normalize_pod_power_on_target_dates(raw_value: Any) -> dict[str, date]:
    if raw_value is None:
        return {}
    if not isinstance(raw_value, list):
        raise ValueError("pod_power_on_target_dates must be a list.")
    target_dates: dict[str, date] = {}
    for index, item in enumerate(raw_value):
        if not isinstance(item, dict):
            raise ValueError(f"pod_power_on_target_dates[{index}] must be an object.")
        milestone_key = _pod_target_date_item_key(item)
        if not milestone_key:
            raise ValueError(f"pod_power_on_target_dates[{index}].milestoneKey is required.")
        raw_date = item.get("anchorDate")
        if raw_date is None:
            raw_date = item.get("targetDate")
        target_dates[milestone_key] = _required_target_date(
            raw_date,
            field_name=f"pod_power_on_target_dates[{index}].anchorDate",
        )
    return target_dates


def _load_project_pod_power_on_milestones(project_id: str) -> list[dict[str, Any]]:
    return [
        milestone
        for milestone in _load_project_backward_target_milestones(project_id)
        if _is_pod_power_on_milestone(milestone)
    ]


def _build_pod_power_on_batch_context(
    *,
    project_id: str,
    ontology: LocalScheduleOntology,
    power_target: date,
    power_baseline: date,
    raw_target_dates: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pod_milestones = _load_project_pod_power_on_milestones(project_id)
    if not pod_milestones:
        return [], []

    override_dates = _normalize_pod_power_on_target_dates(raw_target_dates)
    # POD 分批上电仅在调用方显式给出 POD 级目标日期时启用。否则保持 SINGLE_ANCHOR：
    # 若在此按 POD 里程碑「已存锚点日期」派生批次目标，会经 execute_ 里的
    # power_target = max(power_target, *pod_targets) 把显式的 power_on_target_date
    # 反向顶高到 POD 既有日期，导致供应前移建议天数(suggestedArrivalAdvanceDays)恒为 0。
    if not override_dates:
        return [], []
    known_keys = {
        str(milestone.get("milestoneKey", "")).strip()
        for milestone in pod_milestones
    }
    unknown_keys = sorted(key for key in override_dates if key not in known_keys)
    if unknown_keys:
        raise ValueError(f"Unknown POD POWER_ON milestone(s): {', '.join(unknown_keys)}.")

    batch_targets: list[dict[str, Any]] = []
    milestone_mutations: list[dict[str, Any]] = []
    for milestone in pod_milestones:
        milestone_key = str(milestone.get("milestoneKey", "")).strip()
        scope_key = str(milestone.get("scopeKey", "")).strip()
        saved_date_text = _normalized_date_text(milestone.get("anchorDate"))
        saved_date = _try_parse_plan_date(saved_date_text)
        target_date = override_dates.get(milestone_key) or saved_date or power_target
        try:
            pod_rows = _resolve_target_rows_for_milestone(
                ontology,
                milestone,
                anchor_date=target_date,
            )
            baseline_date = _max_row_end_date(pod_rows, milestone_key)
        except ValueError:
            baseline_date = power_baseline

        target_text = target_date.isoformat()
        batch_targets.append(
            {
                "milestoneKey": milestone_key,
                "scopeKey": scope_key,
                "originalDate": saved_date_text,
                "targetDate": target_text,
                "baselineDate": baseline_date.isoformat(),
                "shiftDays": (target_date - baseline_date).days,
                "_targetDate": target_date,
                "_shiftDays": (target_date - baseline_date).days,
            }
        )
        if saved_date_text != target_text:
            milestone_mutations.append(
                {
                    "milestoneId": milestone_key,
                    "milestoneKey": milestone_key,
                    "scopeKey": scope_key,
                    "field": "anchorDate",
                    "originalDate": saved_date_text,
                    "newDate": target_text,
                    "changeType": "UPDATE_ANCHOR_DATE",
                    "reason": "计划压缩 POD 分批上电：同步更新 POD 级上电里程碑锚点日期。",
                }
            )

    return batch_targets, milestone_mutations


def _project_room_implementation_done_date(project_id: str, ontology: LocalScheduleOntology) -> date | None:
    try:
        milestone = _load_project_milestone_by_type(project_id, "ROOM_IMPLEMENTATION_DONE")
    except ValueError:
        return None
    try:
        rows = _resolve_forward_rows_for_milestone(ontology, milestone)
        return _max_row_end_date(rows, "ROOM_IMPLEMENTATION_DONE")
    except ValueError:
        pass
    for field_name in ("actualDate", "plannedDate", "anchorDate"):
        parsed = _try_parse_plan_date(str(milestone.get(field_name) or ""))
        if parsed is not None:
            return parsed
    return None


def _limit_duration_by_key(ontology: LocalScheduleOntology) -> dict[str, object]:
    values: dict[str, object] = {}
    for row in ontology.objects.DeliveryPlanRow.all():
        values[row.localRowKey] = row.to_schema_object().get("limitDuration", "")
    return values


def _max_row_end_date(rows: list[Any], label: str) -> date:
    dates = [_try_parse_plan_date(row.endDate) for row in rows]
    parsed = [item for item in dates if item is not None]
    if not parsed:
        raise ValueError(f"No parseable endDate found for `{label}`.")
    return max(parsed)


def _max_activity_end_date(activities: dict[str, Any], target_keys: list[str], label: str) -> date:
    parsed: list[date] = []
    for key in target_keys:
        activity = activities.get(key)
        if activity is None:
            continue
        value = _try_parse_plan_date(activity.planned_end)
        if value is not None:
            parsed.append(value)
    if not parsed:
        raise ValueError(f"No parseable virtual endDate found for `{label}`.")
    return max(parsed)


def _build_schedule_mutations(
    ontology: LocalScheduleOntology,
    csv_rows: list[dict[str, str]],
    start_column: str,
    end_column: str,
    results: dict[str, Any],
    *,
    phase_id: str,
    scenario_id: str,
    reason_prefix: str,
) -> list[dict[str, Any]]:
    proposed_mutations: list[dict[str, Any]] = []
    for local_key, schedule in results.items():
        try:
            row = ontology.row(local_key)
        except KeyError:
            continue
        row_index = row.activity.row_order
        if row_index < 0 or row_index >= len(csv_rows):
            continue
        row_key = str(row.rowKey)
        next_start = getattr(schedule, "start", None)
        if next_start is not None:
            new_start = next_start.isoformat()
            current_start = str(csv_rows[row_index].get(start_column, ""))
            if _is_semantic_date_change(current_start, new_start):
                proposed_mutations.append(
                    {
                        "milestoneId": row_key,
                        "rowKey": row_key,
                        "field": "startDate",
                        "originalDate": current_start,
                        "newDate": new_start,
                        "changeType": "UPDATE_START_DATE",
                        "reason": f"{reason_prefix}，调整开始日期。",
                        "phaseId": phase_id,
                        "scenarioId": scenario_id,
                    }
                )
        next_finish = getattr(schedule, "finish", None)
        if next_finish is not None:
            new_end = next_finish.isoformat()
            current_end = str(csv_rows[row_index].get(end_column, ""))
            if _is_semantic_date_change(current_end, new_end):
                proposed_mutations.append(
                    {
                        "milestoneId": row_key,
                        "rowKey": row_key,
                        "field": "endDate",
                        "originalDate": current_end,
                        "newDate": new_end,
                        "changeType": "UPDATE_END_DATE",
                        "reason": f"{reason_prefix}，调整结束日期。",
                        "phaseId": phase_id,
                        "scenarioId": scenario_id,
                    }
                )
    return proposed_mutations


def _apply_schedule_results_to_activities(
    activities: dict[str, Any],
    results: dict[str, Any],
) -> dict[str, Any]:
    adjusted = dict(activities)
    for local_key, schedule in results.items():
        activity = adjusted.get(local_key)
        if activity is None:
            continue
        start = getattr(schedule, "start", None)
        finish = getattr(schedule, "finish", None)
        adjusted[local_key] = replace(
            activity,
            planned_start=start.isoformat() if start is not None else activity.planned_start,
            planned_end=finish.isoformat() if finish is not None else activity.planned_end,
        )
    return adjusted


def _shift_activity_windows_after_boundary(
    activities: dict[str, Any],
    *,
    reference_activities: dict[str, Any],
    boundary_date: date,
    shift_days: int,
) -> dict[str, Any]:
    if shift_days <= 0:
        return activities

    shift = timedelta(days=shift_days)
    shifted = dict(activities)
    for local_key, activity in activities.items():
        reference = reference_activities.get(local_key, activity)
        reference_start = _try_parse_plan_date(getattr(reference, "planned_start", ""))
        reference_finish = _try_parse_plan_date(getattr(reference, "planned_end", ""))
        if not (
            (reference_start is not None and reference_start > boundary_date)
            or (reference_start is None and reference_finish is not None and reference_finish > boundary_date)
        ):
            continue

        start = _try_parse_plan_date(getattr(activity, "planned_start", ""))
        finish = _try_parse_plan_date(getattr(activity, "planned_end", ""))
        shifted[local_key] = replace(
            activity,
            planned_start=(start + shift).isoformat() if start is not None else activity.planned_start,
            planned_end=(finish + shift).isoformat() if finish is not None else activity.planned_end,
        )
    return shifted


def _shift_activity_windows_after_power_batch_boundaries(
    activities: dict[str, Any],
    *,
    reference_activities: dict[str, Any],
    boundary_date: date,
    project_shift_days: int,
    pod_power_on_batch_targets: list[dict[str, Any]],
) -> dict[str, Any]:
    if not pod_power_on_batch_targets:
        return _shift_activity_windows_after_boundary(
            activities,
            reference_activities=reference_activities,
            boundary_date=boundary_date,
            shift_days=project_shift_days,
        )

    shift_by_scope = {
        str(item.get("scopeKey", "")).strip(): int(item.get("_shiftDays", 0) or 0)
        for item in pod_power_on_batch_targets
        if str(item.get("scopeKey", "")).strip()
    }
    if project_shift_days <= 0 and not any(shift_days > 0 for shift_days in shift_by_scope.values()):
        return activities

    shifted = dict(activities)
    for local_key, activity in activities.items():
        reference = reference_activities.get(local_key, activity)
        reference_start = _try_parse_plan_date(getattr(reference, "planned_start", ""))
        reference_finish = _try_parse_plan_date(getattr(reference, "planned_end", ""))
        if not (
            (reference_start is not None and reference_start > boundary_date)
            or (reference_start is None and reference_finish is not None and reference_finish > boundary_date)
        ):
            continue

        units = _split_management_units(getattr(reference, "unit", ""))
        matching_shift_days = [
            shift_by_scope[unit]
            for unit in units
            if unit in shift_by_scope
        ]
        shift_days = max(matching_shift_days) if matching_shift_days else project_shift_days
        if shift_days <= 0:
            continue

        shift = timedelta(days=shift_days)
        start = _try_parse_plan_date(getattr(activity, "planned_start", ""))
        finish = _try_parse_plan_date(getattr(activity, "planned_end", ""))
        shifted[local_key] = replace(
            activity,
            planned_start=(start + shift).isoformat() if start is not None else activity.planned_start,
            planned_end=(finish + shift).isoformat() if finish is not None else activity.planned_end,
        )
    return shifted


DEFAULT_PLAN_COMPRESSION_TOP_N = 3


def _normalize_plan_compression_top_n(value: Any) -> int:
    """Coerce a caller-supplied TOP N into a positive int (default 3).

    Accepts an int or numeric string; falls back to the default for None,
    blank, non-numeric, or non-positive input so the parameter stays optional.
    """
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return DEFAULT_PLAN_COMPRESSION_TOP_N
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return DEFAULT_PLAN_COMPRESSION_TOP_N
    return parsed if parsed >= 1 else DEFAULT_PLAN_COMPRESSION_TOP_N


def _append_duration_compression_scenarios(
    *,
    ontology: LocalScheduleOntology,
    activities: dict[str, Any],
    csv_rows: list[dict[str, str]],
    start_column: str,
    end_column: str,
    limit_duration_by_key: dict[str, object],
    phase_id: str,
    target_keys: list[str],
    baseline_date: date,
    target_date: date,
    scenarios: list[dict[str, Any]],
    runs: dict[str, dict[str, Any]],
    tool_calls: list[dict[str, Any]],
    warnings: list[str],
    reason_subject: str,
    top_n: int = DEFAULT_PLAN_COMPRESSION_TOP_N,
    virtual_baseline: bool = False,
) -> None:
    from llm_openrouter_milestone_compression import (
        STRATEGY_PROPORTIONAL,
        STRATEGY_TOP3_SLACK,
        compute_duration_compression_schedule,
    )

    configs = [
        (
            "duration_top3_slack",
            f"工期 TOP{top_n} 空闲压缩",
            STRATEGY_TOP3_SLACK,
            f"按初始关键路径工期 TOP{top_n} 空闲压缩，单活动不低于极限工期",
        ),
        (
            "duration_proportional",
            "关键路径全局等比压缩",
            STRATEGY_PROPORTIONAL,
            "按当前关键路径工期占比全局等比压缩，未达目标时重新计算关键路径继续压缩",
        ),
    ]
    for suffix, name, strategy, reason_method in configs:
        scenario_id = f"{phase_id}_{suffix}"
        run = compute_duration_compression_schedule(
            activities,
            target_keys=target_keys,
            baseline_date=baseline_date,
            anchor_date=target_date,
            limit_duration_by_key=limit_duration_by_key,
            strategy=strategy,
            top_n=top_n,
            warnings=warnings,
        )
        mutations = _build_schedule_mutations(
            ontology,
            csv_rows,
            start_column,
            end_column,
            run.results,
            phase_id=phase_id,
            scenario_id=scenario_id,
            reason_prefix=f"{reason_subject}：{reason_method}，目标 {target_date.isoformat()}",
        )
        final_target_finish = getattr(run, "final_target_finish_date", None)
        if virtual_baseline and (final_target_finish is None or final_target_finish > target_date):
            mutations = []
        scenarios.append(
            {
                "phaseId": phase_id,
                "scenarioId": scenario_id,
                "name": name,
                "strategy": strategy,
                "baselineDate": baseline_date.isoformat(),
                "targetDate": target_date.isoformat(),
                "requestedCompressionDays": run.requested_compression_days,
                "achievedCompressionDays": run.achieved_compression_days,
                "criticalPath": [ontology.row(key).rowKey for key in run.critical_path_keys],
                "criticalPathIterations": [
                    [ontology.row(key).rowKey for key in path]
                    for path in getattr(run, "critical_path_iterations", [run.critical_path_keys])
                ],
                "allocations": {ontology.row(key).rowKey: days for key, days in run.allocations.items()},
                "stopReason": getattr(run, "stop_reason", ""),
                "finalTargetFinishDate": final_target_finish.isoformat() if final_target_finish is not None else "",
                "mutationCount": len(mutations),
                "isRecommended": False,
            }
        )
        runs[scenario_id] = {"results": run.results, "mutations": mutations}
        tool_calls.append(
            {
                "phaseId": phase_id,
                "toolName": (
                    "preview_plan_top3_slack_compression"
                    if strategy == STRATEGY_TOP3_SLACK
                    else "preview_plan_global_proportional_compression"
                ),
                "input": {
                    "target_finish_date": target_date.isoformat(),
                },
                "status": "COMPLETED",
            }
        )


def _mark_recommended_duration_scenario(
    scenarios: list[dict[str, Any]],
    baseline_date: date,
    target_date: date,
) -> None:
    requested = abs((baseline_date - target_date).days)
    candidates = [scenario for scenario in scenarios if "achievedCompressionDays" in scenario]
    if not candidates:
        return
    if max(int(item.get("achievedCompressionDays", 0)) for item in candidates) < requested:
        supply_shift = next(
            (scenario for scenario in scenarios if scenario.get("strategy") == "SUPPLY_ADVANCE_SHIFT"),
            None,
        )
        if supply_shift is not None:
            recommended_id = str(supply_shift["scenarioId"])
            for scenario in scenarios:
                scenario["isRecommended"] = scenario.get("scenarioId") == recommended_id
            return
    candidates.sort(
        key=lambda item: (
            0 if int(item.get("achievedCompressionDays", 0)) >= requested else 1,
            -int(item.get("achievedCompressionDays", 0)),
            int(item.get("mutationCount", 0)),
            str(item.get("scenarioId", "")),
        )
    )
    recommended_id = str(candidates[0]["scenarioId"])
    for scenario in scenarios:
        scenario["isRecommended"] = scenario.get("scenarioId") == recommended_id


def _recommended_scenario_id(scenarios: list[dict[str, Any]]) -> str:
    for scenario in scenarios:
        if scenario.get("isRecommended"):
            return str(scenario.get("scenarioId", ""))
    if not scenarios:
        raise ValueError("No scenario candidates were produced.")
    return str(scenarios[0].get("scenarioId", ""))


def _build_plan_compression_advice(phases: list[dict[str, Any]]) -> str:
    summaries: list[str] = []
    for phase in phases:
        recommended_id = phase.get("recommendedScenarioId")
        scenario = next(
            (item for item in phase.get("scenarios", []) if item.get("scenarioId") == recommended_id),
            {},
        )
        name = str(scenario.get("name") or recommended_id)
        strategy = str(scenario.get("strategy") or "")
        if strategy == "PROPORTIONAL_EXTENSION":
            summaries.append(f"{phase.get('name')} 建议采用 {name}，因为目标延后时应保持关键路径结构并按当前工期占比延长。")
        else:
            summaries.append(f"{phase.get('name')} 建议采用 {name}，作为当前目标日期下的推荐干跑方案。")
    return "LangGraph 本地 Skill 已完成两阶段计划压缩工具编排；" + " ".join(summaries)


def _plan_strategy_id_for_scenario(scenario: dict[str, Any]) -> str:
    strategy = str(scenario.get("strategy") or "").strip()
    if strategy == "SUPPLY_ADVANCE_SHIFT":
        return STRATEGY_ID_SUPPLY_FRONTLOAD
    if strategy in {"TOP3_SLACK", "TOPN_SLACK"}:
        return STRATEGY_ID_TOP3_SLACK
    if strategy in {"PROPORTIONAL", "PROPORTIONAL_EXTENSION"}:
        return STRATEGY_ID_GLOBAL_PROPORTIONAL
    return ""


def _build_plan_compression_strategy_mutations(
    phases: list[dict[str, Any]],
    runs: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    mutations_by_strategy = {strategy_id: [] for strategy_id in PLAN_COMPRESSION_STRATEGY_IDS}
    for phase in phases:
        for scenario in phase.get("scenarios", []):
            strategy_id = _plan_strategy_id_for_scenario(scenario)
            scenario_id = str(scenario.get("scenarioId") or "").strip()
            if not strategy_id or not scenario_id:
                continue
            mutations_by_strategy[strategy_id].extend(list(runs.get(scenario_id, {}).get("mutations", [])))
    return mutations_by_strategy


def _try_plan_compression_llm_decision(
    *,
    project_id: str,
    llm_semantic_payload: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any] | None:
    try:
        from langgraph_agent.recommenders.plan_compression import try_llm_recommend_plan_compression

        return try_llm_recommend_plan_compression(
            project_id=project_id,
            strategies=list(llm_semantic_payload.get("strategies", [])),
            warnings=warnings,
        )
    except Exception:
        return None


def _merge_plan_compression_llm_decision(
    llm_semantic_payload: dict[str, Any],
    llm_decision: dict[str, Any],
    *,
    recommended_plan_id: str,
) -> dict[str, Any]:
    strategies = [dict(item) for item in llm_semantic_payload.get("strategies", [])]
    overrides = {
        str(item.get("strategy_id") or "").strip(): item
        for item in list(llm_decision.get("strategies") or [])
        if isinstance(item, dict)
    }
    for strategy in strategies:
        strategy_id = str(strategy.get("strategy_id") or "").strip()
        override = overrides.get(strategy_id, {})
        if override.get("recommendation_summary"):
            strategy["recommendation_summary"] = _clip_text(str(override["recommendation_summary"]), limit=180)
        if isinstance(override.get("keyInformation"), list):
            strategy["keyInformation"] = [_clip_text(str(item), limit=80) for item in override["keyInformation"][:4]]
        if isinstance(override.get("cascading_risks"), list):
            strategy["cascading_risks"] = [_clip_text(str(item), limit=120) for item in override["cascading_risks"][:3]]
    return {
        **llm_semantic_payload,
        "strategies": strategies,
        "llmRecommendedPlanId": recommended_plan_id,
    }


def _deterministic_plan_compression_strategy_id(llm_semantic_payload: dict[str, Any]) -> str:
    strategies = list(llm_semantic_payload.get("strategies", []))
    by_id = {str(item.get("strategy_id") or ""): item for item in strategies if isinstance(item, dict)}
    for strategy_id in (
        STRATEGY_ID_GLOBAL_PROPORTIONAL,
        STRATEGY_ID_TOP3_SLACK,
        STRATEGY_ID_SUPPLY_FRONTLOAD,
    ):
        strategy = by_id.get(strategy_id, {})
        if int(strategy.get("proposedMutationCount", 0) or 0) > 0:
            return strategy_id
    return STRATEGY_ID_GLOBAL_PROPORTIONAL


def _build_plan_compression_strategy_advice(
    llm_semantic_payload: dict[str, Any],
    recommended_plan_id: str,
) -> str:
    strategy = next(
        (
            item
            for item in llm_semantic_payload.get("strategies", [])
            if item.get("strategy_id") == recommended_plan_id
        ),
        {},
    )
    title = str(strategy.get("title") or recommended_plan_id)
    summary = str(strategy.get("recommendation_summary") or "当前推荐由确定性规则生成。")
    return f"计划压缩决策报告：推荐采用 {title}。{summary}"


def _mark_plan_compression_recommended_strategy(
    llm_semantic_payload: dict[str, Any],
    recommended_plan_id: str,
) -> dict[str, Any]:
    strategies = []
    for strategy in llm_semantic_payload.get("strategies", []):
        payload = dict(strategy)
        payload["isRecommended"] = payload.get("strategy_id") == recommended_plan_id
        strategies.append(_apply_strategy_token_guard(payload))
    return {**llm_semantic_payload, "strategies": strategies}


def _build_plan_compression_llm_payload(
    *,
    phases: list[dict[str, Any]],
    runs: dict[str, dict[str, Any]],
    warnings: list[str],
    top_n: int = DEFAULT_PLAN_COMPRESSION_TOP_N,
) -> dict[str, Any]:
    scenario_index: dict[str, dict[str, Any]] = {}
    for phase in phases:
        phase_id = str(phase.get("phaseId", ""))
        for scenario in phase.get("scenarios", []):
            scenario_id = str(scenario.get("scenarioId", ""))
            if not scenario_id:
                continue
            scenario_index[scenario_id] = {
                "phaseId": phase_id,
                "phaseName": str(phase.get("name", phase_id)),
                "scenario": scenario,
            }

    strategies = [
        _build_supply_frontload_strategy(scenario_index, runs, warnings),
        _build_top3_slack_strategy(scenario_index, runs, warnings, top_n=top_n),
        _build_global_proportional_strategy(scenario_index, runs, warnings),
    ]
    return {
        "version": LLM_SEMANTIC_PAYLOAD_VERSION,
        "strategies": [_apply_strategy_token_guard(strategy) for strategy in strategies],
    }


def _build_supply_frontload_strategy(
    scenario_index: dict[str, dict[str, Any]],
    runs: dict[str, dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    candidates = [
        item
        for item in scenario_index.values()
        if str(item["scenario"].get("strategy", "")).strip() == "SUPPLY_ADVANCE_SHIFT"
    ]
    candidates.sort(key=lambda item: int(item["scenario"].get("mutationCount", 0)), reverse=True)
    selected_scenarios = [item["scenario"] for item in candidates]
    selected = selected_scenarios[0] if selected_scenarios else {}
    parameter_overrides = _strategy_parameter_overrides(selected)
    actions = _normalize_actionable_mutations(_mutations_for_scenarios(selected_scenarios, runs))
    shift_days = sum(int(scenario.get("requestedShiftDays", 0) or 0) for scenario in selected_scenarios)
    mutation_count = sum(int(scenario.get("mutationCount", 0) or 0) for scenario in selected_scenarios) or len(actions)
    return {
        "strategy_id": STRATEGY_ID_SUPPLY_FRONTLOAD,
        "strategy_type": "frontload",
        "title": "供应前移",
        "recommendation_summary": _clip_text(
            f"建议优先执行供应前移，目标平移 {shift_days} 天，变更 {mutation_count} 项。"
            if selected_scenarios
            else "当前未生成可执行的供应前移场景。"
        ),
        "quantitative_evidence": [
            {"metric": "phase_count", "value": len(selected_scenarios)},
            {"metric": "requested_shift_days", "value": shift_days},
            {"metric": "mutation_count", "value": mutation_count},
        ],
        "keyInformation": [
            f"覆盖 {len(selected_scenarios)} 个阶段",
            f"供应平移 {shift_days} 天",
            f"{mutation_count} 项日期变更",
            "保持活动工期不变",
        ],
        "phaseDetails": _phase_details_for_candidates(candidates),
        "toolName": PLAN_COMPRESSION_TOOL_NAMES[STRATEGY_ID_SUPPLY_FRONTLOAD],
        "toolInput": {
            "target_supply_date": selected.get("targetDate", ""),
            "phase_targets": _phase_tool_targets(candidates, "target_supply_date"),
        },
        "toolStatus": "COMPLETED",
        "isRecommended": False,
        "proposedMutationCount": mutation_count,
        "cascading_risks": _build_supply_parameter_risks(parameter_overrides),
        "parameter_overrides": parameter_overrides,
        "actionable_mutations": actions,
    }


def _build_top3_slack_strategy(
    scenario_index: dict[str, dict[str, Any]],
    runs: dict[str, dict[str, Any]],
    warnings: list[str],
    top_n: int = DEFAULT_PLAN_COMPRESSION_TOP_N,
) -> dict[str, Any]:
    candidates = [
        item
        for item in scenario_index.values()
        if str(item["scenario"].get("strategy", "")).strip() == "TOP3_SLACK"
    ]
    candidates.sort(
        key=lambda item: (
            -int(item["scenario"].get("achievedCompressionDays", 0) or 0),
            int(item["scenario"].get("mutationCount", 0) or 0),
            str(item["scenario"].get("scenarioId", "")),
        )
    )
    selected_scenarios = [item["scenario"] for item in candidates]
    selected = selected_scenarios[0] if selected_scenarios else {}
    actions = _normalize_actionable_mutations(_mutations_for_scenarios(selected_scenarios, runs))
    requested_days = sum(int(scenario.get("requestedCompressionDays", 0) or 0) for scenario in selected_scenarios)
    achieved_days = sum(int(scenario.get("achievedCompressionDays", 0) or 0) for scenario in selected_scenarios)
    mutation_count = sum(int(scenario.get("mutationCount", 0) or 0) for scenario in selected_scenarios) or len(actions)
    return {
        "strategy_id": STRATEGY_ID_TOP3_SLACK,
        "strategy_type": "top3_slack",
        "title": f"工期压缩TOP{top_n}空闲",
        "recommendation_summary": _clip_text(
            f"建议优先采用 Top{top_n} 空闲压缩，目标压缩 {requested_days} 天，"
            f"预计可实现 {achieved_days} 天；单活动不低于极限工期。"
            if selected_scenarios
            else f"当前未生成 Top{top_n} 空闲压缩场景。"
        ),
        "quantitative_evidence": [
            {"metric": "candidate_count", "value": len(candidates)},
            {"metric": "requested_compression_days", "value": requested_days},
            {"metric": "achieved_compression_days", "value": achieved_days},
        ],
        "keyInformation": [
            f"覆盖 {len(selected_scenarios)} 个阶段",
            f"目标压缩 {requested_days} 天",
            f"预计达成 {achieved_days} 天",
            f"{mutation_count} 项日期变更",
        ],
        "phaseDetails": _phase_details_for_candidates(candidates),
        "toolName": PLAN_COMPRESSION_TOOL_NAMES[STRATEGY_ID_TOP3_SLACK],
        "toolInput": {
            "target_finish_date": selected.get("targetDate", ""),
            "phase_targets": _phase_tool_targets(candidates, "target_finish_date"),
        },
        "toolStatus": "COMPLETED",
        "isRecommended": False,
        "proposedMutationCount": mutation_count,
        "cascading_risks": _build_strategy_risks(
            f"Top{top_n} 空闲压缩固定初始关键路径，活动触达极限工期后停止继续压缩。",
            warnings,
        ),
        "actionable_mutations": actions,
    }


def _build_global_proportional_strategy(
    scenario_index: dict[str, dict[str, Any]],
    runs: dict[str, dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    candidates = [
        item
        for item in scenario_index.values()
        if str(item["scenario"].get("strategy", "")).strip() in {"PROPORTIONAL", "PROPORTIONAL_EXTENSION"}
    ]
    candidates.sort(
        key=lambda item: (
            -int(item["scenario"].get("achievedCompressionDays", 0) or 0),
            -int(item["scenario"].get("achievedExtensionDays", 0) or 0),
            int(item["scenario"].get("mutationCount", 0) or 0),
            str(item["scenario"].get("scenarioId", "")),
        )
    )
    selected_scenarios = [item["scenario"] for item in candidates]
    selected = selected_scenarios[0] if selected_scenarios else {}
    actions = _normalize_actionable_mutations(_mutations_for_scenarios(selected_scenarios, runs))
    requested_days = sum(
        int(scenario.get("requestedCompressionDays", scenario.get("requestedExtensionDays", 0)) or 0)
        for scenario in selected_scenarios
    )
    achieved_days = sum(
        int(scenario.get("achievedCompressionDays", scenario.get("achievedExtensionDays", 0)) or 0)
        for scenario in selected_scenarios
    )
    mutation_count = sum(int(scenario.get("mutationCount", 0) or 0) for scenario in selected_scenarios) or len(actions)
    return {
        "strategy_id": STRATEGY_ID_GLOBAL_PROPORTIONAL,
        "strategy_type": "proportional",
        "title": "工期全局等比压缩",
        "recommendation_summary": _clip_text(
            f"建议采用关键路径全局等比策略，目标调整 {requested_days} 天，预计实现 {achieved_days} 天；"
            "若未达目标则重新计算关键路径并继续压缩。"
            if selected_scenarios
            else "当前未生成可执行的全局等比策略。"
        ),
        "quantitative_evidence": [
            {"metric": "candidate_count", "value": len(candidates)},
            {"metric": "requested_days", "value": requested_days},
            {"metric": "achieved_days", "value": achieved_days},
        ],
        "keyInformation": [
            f"覆盖 {len(selected_scenarios)} 个阶段",
            f"目标调整 {requested_days} 天",
            f"预计达成 {achieved_days} 天",
            f"{mutation_count} 项日期变更",
        ],
        "phaseDetails": _phase_details_for_candidates(candidates),
        "toolName": PLAN_COMPRESSION_TOOL_NAMES[STRATEGY_ID_GLOBAL_PROPORTIONAL],
        "toolInput": {
            "target_finish_date": selected.get("targetDate", ""),
            "phase_targets": _phase_tool_targets(candidates, "target_finish_date"),
        },
        "toolStatus": "COMPLETED",
        "isRecommended": False,
        "proposedMutationCount": mutation_count,
        "cascading_risks": _build_strategy_risks(
            "全局等比策略会在压缩后重算关键路径，直到达到目标或关键路径不再变化。",
            warnings,
        ),
        "actionable_mutations": actions,
    }


def _mutations_for_scenarios(
    scenarios: list[dict[str, Any]],
    runs: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for scenario in scenarios:
        scenario_id = str(scenario.get("scenarioId") or "").strip()
        if not scenario_id:
            continue
        values.extend(list(runs.get(scenario_id, {}).get("mutations", [])))
    return values


def _phase_details_for_candidates(candidates: list[dict[str, Any]]) -> list[str]:
    details: list[str] = []
    for item in candidates:
        scenario = item.get("scenario", {})
        phase_name = str(item.get("phaseName") or scenario.get("phaseId") or "阶段")
        details.append(
            f"{phase_name}：{scenario.get('baselineDate', '-')} -> {scenario.get('targetDate', '-')}"
        )
    return details


def _phase_tool_targets(candidates: list[dict[str, Any]], target_field: str) -> list[dict[str, str]]:
    targets: list[dict[str, str]] = []
    for item in candidates:
        scenario = item.get("scenario", {})
        targets.append(
            {
                "phase_id": str(scenario.get("phaseId") or item.get("phaseId") or ""),
                target_field: str(scenario.get("targetDate") or ""),
            }
        )
    return targets


def _strategy_parameter_overrides(scenario: dict[str, Any]) -> dict[str, Any]:
    values = scenario.get("parameter_overrides")
    return dict(values) if isinstance(values, dict) else {}


def _build_supply_parameter_risks(parameter_overrides: dict[str, Any]) -> list[str]:
    room_done_date = str(parameter_overrides.get("roomImplementationDoneDate") or "-").strip() or "-"
    suggested_days = parameter_overrides.get("suggestedArrivalAdvanceDays")
    try:
        suggested_days_text = str(int(suggested_days))
    except (TypeError, ValueError):
        suggested_days_text = "-"
    return [
        _clip_text(f"机房实施完成建议值：{room_done_date}，供应前移需确认该前置条件满足。"),
        _clip_text(f"到货提前建议值：{suggested_days_text} 天，默认作为供应商确认天数。"),
    ]


def _build_strategy_risks(base_risk: str, warnings: list[str]) -> list[str]:
    values = [_clip_text(base_risk)]
    values.extend(_clip_text(str(warning)) for warning in warnings[:2] if str(warning).strip())
    deduped: list[str] = []
    for item in values:
        if item and item not in deduped:
            deduped.append(item)
    return deduped


def _normalize_actionable_mutations(mutations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for mutation in mutations:
        milestone_id = str(mutation.get("milestoneId") or mutation.get("rowKey") or "").strip()
        field = str(mutation.get("field") or "").strip()
        new_date_raw = str(mutation.get("newDate") or "").strip()
        if not milestone_id or field not in {"startDate", "endDate"} or not new_date_raw:
            continue
        normalized_date = _normalize_compact_date(new_date_raw)
        if not normalized_date:
            continue
        dedupe_key = (milestone_id, field, normalized_date)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized.append(
            {
                "milestoneId": milestone_id,
                "field": field,
                "newDate": normalized_date,
                "precondition": f"{milestone_id}.{field} != {normalized_date}",
            }
        )
    return normalized[:12]


def _normalize_compact_date(raw_value: str) -> str:
    parsed = _try_parse_plan_date(raw_value)
    if parsed is None:
        return ""
    return parsed.isoformat()


def _clip_text(text: str, limit: int = 180) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _apply_strategy_token_guard(strategy: dict[str, Any]) -> dict[str, Any]:
    payload = dict(strategy)
    minimum_risk_count = 2 if isinstance(payload.get("parameter_overrides"), dict) else 1
    payload["recommendation_summary"] = _clip_text(str(payload.get("recommendation_summary", "")), limit=120)
    payload["cascading_risks"] = list(payload.get("cascading_risks", []))[:2]
    payload["actionable_mutations"] = list(payload.get("actionable_mutations", []))[:6]
    payload["quantitative_evidence"] = list(payload.get("quantitative_evidence", []))[:3]
    payload["keyInformation"] = list(payload.get("keyInformation", []))[:4]
    payload["phaseDetails"] = list(payload.get("phaseDetails", []))[:4]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if len(encoded) <= STRATEGY_CHAR_LIMIT:
        return payload
    payload["actionable_mutations"] = list(payload.get("actionable_mutations", []))[:3]
    payload["cascading_risks"] = list(payload.get("cascading_risks", []))[:minimum_risk_count]
    payload["phaseDetails"] = list(payload.get("phaseDetails", []))[:2]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if len(encoded) <= STRATEGY_CHAR_LIMIT:
        return payload
    payload["actionable_mutations"] = []
    payload["quantitative_evidence"] = list(payload.get("quantitative_evidence", []))[:2]
    payload["keyInformation"] = list(payload.get("keyInformation", []))[:2]
    payload["phaseDetails"] = list(payload.get("phaseDetails", []))[:1]
    payload["recommendation_summary"] = _clip_text(str(payload.get("recommendation_summary", "")), limit=80)
    return payload


def _is_writable_object_type(object_type: str) -> bool:
    """Action-editable iff the datasource binding declares ``writable: true``."""
    try:
        return bool(load_datasource_bindings().object_type(object_type).writable)
    except KeyError:
        return False


def _is_dolt_backed_writable(object_type: str) -> bool:
    """Writable but with no CSV/derived backing -> the object lives in the Dolt store.

    These objects (ChangeOrder / SupplierCompany) route their Action validate/apply
    through the Dolt write path, where the 3 validation layers run against current
    state read from Dolt and the edit is written via apply_object_update.
    """
    try:
        binding = load_datasource_bindings().object_type(object_type)
    except KeyError:
        return False
    return bool(binding.writable) and not binding.has_backing_data


def _object_primary_key_field(object_type: str) -> str:
    schema = _load_object_types().get(object_type) or {}
    keys = schema.get("primaryKeyPropertyApiNames")
    if isinstance(keys, list) and keys and isinstance(keys[0], str) and keys[0].strip():
        return keys[0].strip()
    raise ValueError(f"Object type primary key is not configured: {object_type}")


def _object_property_names(object_type: str) -> set[str]:
    schema = _load_object_types().get(object_type) or {}
    properties = schema.get("properties")
    names: set[str] = set()
    if isinstance(properties, dict):
        for fallback_name, property_schema in properties.items():
            if isinstance(property_schema, dict):
                names.add(str(property_schema.get("apiName") or fallback_name))
            else:
                names.add(str(fallback_name))
    return names


def _read_dolt_object_row(
    context: Any,
    object_type: str,
    primary_key_field: str,
    object_key: str,
) -> dict[str, Any] | None:
    for row in get_object_data_for_branch(context, object_type):
        if str(row.get(primary_key_field) or "") == str(object_key):
            return row
    return None


def _apply_object_update_dolt(
    object_type: str,
    action_name: str,
    payload: dict[str, Any],
    *,
    write: bool,
) -> dict[str, Any]:
    """Validate (and optionally apply) a single-object Action against the Dolt store.

    The three declarative validation layers run here exactly as on the CSV path, but
    the current object state is read from Dolt and the write goes to Dolt via
    apply_object_update — this is what makes value-type / state-machine /
    submissionCriteria fire end-to-end for the Dolt-backed objects.
    """
    if not _is_writable_object_type(object_type):
        raise ValueError(f"Object type `{object_type}` is read-only.")
    _ensure_supported_action(object_type, action_name)

    primary_key_field = _object_primary_key_field(object_type)
    object_key = _payload_object_key(
        payload,
        object_type,
        action_name,
        primary_key_field=primary_key_field,
    )
    if not object_key:
        raise KeyError(f"payload.{primary_key_field} is required.")
    object_key = str(object_key)

    changes = _payload_changes(payload, action_name)
    property_names = _object_property_names(object_type)
    invalid_fields = sorted(field for field in changes if field not in property_names)
    if invalid_fields:
        raise ValueError(f"Unsupported field(s): {', '.join(invalid_fields)}")
    editable_fields = _action_edit_fields(action_name)
    if editable_fields:
        disallowed_fields = sorted(field for field in changes if field not in editable_fields)
        if disallowed_fields:
            raise ValueError(f"Action `{action_name}` cannot update field(s): {', '.join(disallowed_fields)}")

    _validate_action_date_changes(object_type, changes)
    _validate_action_value_type_changes(object_type, changes)

    context = get_current_preview_branch()
    current_row = _read_dolt_object_row(context, object_type, primary_key_field, object_key)
    if current_row is None:
        raise KeyError(f"{object_type} {primary_key_field} not found: {object_key}")

    _validate_action_target_constraints(action_name, current_row)
    _validate_action_state_transition(action_name, current_row, changes, object_type)
    _validate_action_submission_criteria(action_name, current_row, changes, object_type)

    if not write:
        return {
            "success": True,
            "actionName": action_name,
            "objectType": object_type,
            primary_key_field: object_key,
            "validatedChanges": {api_name: _csv_value(value) for api_name, value in changes.items()},
        }

    commit_message = f"Apply {action_name} on {object_type} {object_key} ({', '.join(sorted(changes))})"
    apply_object_update_to_dolt(
        context,
        object_type,
        {primary_key_field: object_key},
        changes,
        author=_acting_user_author(payload),
        message=commit_message,
    )
    refreshed = _read_dolt_object_row(context, object_type, primary_key_field, object_key) or {}
    return {
        "success": True,
        "actionName": action_name,
        "objectType": object_type,
        primary_key_field: object_key,
        "data": refreshed,
    }


def validate_object_update(object_type: str, action_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate an Action payload without writing to the backing CSV."""
    _ensure_supported_object_type(object_type)
    if _is_dolt_backed_writable(object_type):
        return _apply_object_update_dolt(object_type, action_name, payload, write=False)
    if not _is_writable_object_type(object_type):
        raise ValueError(f"Object type `{object_type}` is read-only.")
    _ensure_supported_action(object_type, action_name)

    primary_key_field = _primary_key_field(object_type)
    object_key = _payload_object_key(payload, object_type, action_name)
    if not object_key:
        raise KeyError(f"payload.{primary_key_field} is required.")

    changes = _payload_changes(payload, action_name)
    source_columns = _api_to_source_columns(object_type)
    invalid_fields = sorted(field for field in changes if field not in source_columns)
    if invalid_fields:
        raise ValueError(f"Unsupported or read-only field(s): {', '.join(invalid_fields)}")

    editable_fields = _action_edit_fields(action_name)
    if editable_fields:
        disallowed_fields = sorted(field for field in changes if field not in editable_fields)
        if disallowed_fields:
            raise ValueError(
                f"Action `{action_name}` cannot update field(s): {', '.join(disallowed_fields)}"
            )

    _validate_action_date_changes(object_type, changes)
    _validate_action_value_type_changes(object_type, changes)

    refresh_project_id = str(payload.get("project_id")) if payload.get("project_id") else None
    if object_type == MILESTONE_OBJECT_TYPE:
        csv_path = BASE_DIR / MILESTONE_SOURCE_FILE
        if refresh_project_id is None:
            refresh_project_id = _project_id_from_milestone_key(str(object_key))
    else:
        source = _source_for_object_key(object_type, str(object_key), payload.get("project_id"))
        csv_path = source.path
        if refresh_project_id is None:
            refresh_project_id = source.project_id

    csv_rows, _fieldnames = _read_csv(csv_path)
    key_source_column = source_columns.get(primary_key_field)
    if key_source_column:
        row_index = _find_row_index(csv_rows, key_source_column, str(object_key))
        if row_index < 0:
            raise KeyError(f"{object_type} {primary_key_field} not found: {object_key}")
        _validate_action_target_constraints(action_name, csv_rows[row_index])
        _validate_action_state_transition(action_name, csv_rows[row_index], changes, object_type)
        _validate_action_submission_criteria(action_name, csv_rows[row_index], changes, object_type)
    elif object_type == DELIVERY_PLAN_ROW_OBJECT_TYPE:
        ontology = _load_ontology(source)
        target = ontology.objects.DeliveryPlanRow.get_or_none(str(object_key))
        if target is None:
            raise KeyError(f"DeliveryPlanRow rowKey not found: {object_key}")
        constraint_row = _object_to_constraint_row(target)
        _validate_action_target_constraints(action_name, constraint_row)
        _validate_action_state_transition(action_name, constraint_row, changes, object_type)
        _validate_action_submission_criteria(action_name, constraint_row, changes, object_type)
    else:
        raise ValueError(f"Primary key mapping missing for object type: {object_type}")

    result = {
        "success": True,
        "actionName": action_name,
        "objectType": object_type,
        "rowKey": str(object_key),
        "validatedChanges": {api_name: _csv_value(value) for api_name, value in changes.items()},
    }
    if action_name == "modifyPodPowerOnMilestoneAnchorDate" and "anchorDate" in changes:
        if refresh_project_id is None:
            refresh_project_id = _project_id_from_milestone_key(str(object_key))
        result["backwardDryRun"] = execute_backward_key_milestones(
            refresh_project_id,
            selected_anchor_id=str(object_key),
            temporary_anchor_dates={str(object_key): changes["anchorDate"]},
        )
    return result


def update_object_data(object_type: str, action_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Update an object row by primary key and write the change back to source CSV."""
    _ensure_supported_object_type(object_type)
    if _is_dolt_backed_writable(object_type):
        return _apply_object_update_dolt(object_type, action_name, payload, write=True)
    if not _is_writable_object_type(object_type):
        raise ValueError(f"Object type `{object_type}` is read-only.")
    _ensure_supported_action(object_type, action_name)

    primary_key_field = _primary_key_field(object_type)
    object_key = _payload_object_key(payload, object_type, action_name)
    if not object_key:
        raise KeyError(f"payload.{primary_key_field} is required.")

    changes = _payload_changes(payload, action_name)

    source_columns = _api_to_source_columns(object_type)
    invalid_fields = sorted(field for field in changes if field not in source_columns)
    if invalid_fields:
        raise ValueError(f"Unsupported or read-only field(s): {', '.join(invalid_fields)}")

    editable_fields = _action_edit_fields(action_name)
    if editable_fields:
        disallowed_fields = sorted(field for field in changes if field not in editable_fields)
        if disallowed_fields:
            raise ValueError(
                f"Action `{action_name}` cannot update field(s): {', '.join(disallowed_fields)}"
            )

    _validate_action_date_changes(object_type, changes)
    _validate_action_value_type_changes(object_type, changes)

    refresh_project_id = str(payload.get("project_id")) if payload.get("project_id") else None
    if object_type == MILESTONE_OBJECT_TYPE:
        csv_path = BASE_DIR / MILESTONE_SOURCE_FILE
        if refresh_project_id is None:
            refresh_project_id = _project_id_from_milestone_key(str(object_key))
    else:
        source = _source_for_object_key(object_type, str(object_key), payload.get("project_id"))
        csv_path = source.path
        if refresh_project_id is None:
            refresh_project_id = source.project_id

    csv_rows, fieldnames = _read_csv(csv_path)
    key_source_column = source_columns.get(primary_key_field)
    if key_source_column:
        row_index = _find_row_index(csv_rows, key_source_column, str(object_key))
    elif object_type == DELIVERY_PLAN_ROW_OBJECT_TYPE:
        ontology = _load_ontology(source)
        target = ontology.objects.DeliveryPlanRow.get_or_none(str(object_key))
        if target is None:
            raise KeyError(f"DeliveryPlanRow rowKey not found: {object_key}")
        row_index = target.activity.row_order
    else:
        raise ValueError(f"Primary key mapping missing for object type: {object_type}")
    if row_index < 0 or row_index >= len(csv_rows):
        raise KeyError(f"{object_type} {primary_key_field} not found: {object_key}")
    _validate_action_target_constraints(action_name, csv_rows[row_index])
    _validate_action_state_transition(action_name, csv_rows[row_index], changes, object_type)
    _validate_action_submission_criteria(action_name, csv_rows[row_index], changes, object_type)

    for api_name, value in changes.items():
        csv_rows[row_index][source_columns[api_name]] = _csv_value(value)

    _write_csv(csv_path, fieldnames, csv_rows)

    refreshed_rows = get_object_data(object_type, refresh_project_id)
    refreshed = next((item for item in refreshed_rows if item.get(primary_key_field) == object_key), None)
    if refreshed is None and row_index < len(refreshed_rows):
        refreshed = refreshed_rows[row_index]

    result = {
        "success": True,
        "actionName": action_name,
        "objectType": object_type,
        primary_key_field: object_key,
        "data": refreshed or {},
    }
    automation_results = _run_automations_safe(object_type, "UPDATE", refreshed or {})
    if automation_results:
        result["automations"] = automation_results
    return result


def _rows_matching_name_substrings(ontology: LocalScheduleOntology, substrings: list[str]) -> list[Any]:
    lowered = [str(s).strip().lower() for s in substrings if str(s).strip()]
    matched: list[Any] = []
    for row in ontology.objects.DeliveryPlanRow.all():
        name_l = row.activityName.lower()
        if any(sub in name_l for sub in lowered):
            matched.append(row)
    return matched


def _pick_one_plan_row_for_anchor(candidates: list[Any], pick: str, anchor_date: date | None = None) -> tuple[Any, date]:
    if not candidates:
        raise ValueError("No delivery plan rows matched anchor name_substrings.")
    strategy = (pick or "first_row_order").strip().lower()
    dated: list[tuple[Any, date]] = []
    for row in candidates:
        d = _try_parse_plan_date(row.endDate)
        if d is not None:
            dated.append((row, d))
    if anchor_date is not None and dated:
        exact_matches = [(row, d) for row, d in dated if d == anchor_date]
        if exact_matches:
            row, d = min(exact_matches, key=lambda x: x[0].activity.row_order)
            return row, d
    if strategy == "min_end":
        if not dated:
            # 容错：里程碑锚点日期来自 Milestone.csv，活动 endDate 缺失时仍可倒排。
            row = min(candidates, key=lambda r: r.activity.row_order)
            return row, date.min
        row, d = min(dated, key=lambda x: (x[1], x[0].activity.row_order))
        return row, d
    if strategy == "max_end":
        if not dated:
            # 容错：里程碑锚点日期来自 Milestone.csv，活动 endDate 缺失时仍可倒排。
            row = min(candidates, key=lambda r: r.activity.row_order)
            return row, date.min
        row, d = max(dated, key=lambda x: (x[1], x[0].activity.row_order))
        return row, d
    row = min(candidates, key=lambda r: r.activity.row_order)
    d = _try_parse_plan_date(row.endDate)
    if d is None:
        raise ValueError(f"Anchor row `{row.activityName}` has no parseable endDate.")
    return row, d


def _load_project_backward_target_milestones(project_id: str) -> list[dict[str, Any]]:
    milestones = get_object_data(MILESTONE_OBJECT_TYPE, project_id=project_id)
    backward_targets: list[dict[str, Any]] = []
    for milestone in milestones:
        if str(milestone.get("directionRole", "")).strip() != "BACKWARD_TARGET":
            continue
        backward_targets.append(milestone)
    backward_targets.sort(
        key=lambda item: (
            0 if str(item.get("scopeType", "")).strip() == "POD" else 1,
            str(item.get("milestoneName", "")),
            str(item.get("milestoneKey", "")),
        )
    )
    return backward_targets


def _is_project_global_milestone(milestone: dict[str, Any]) -> bool:
    scope_type = str(milestone.get("scopeType", "")).strip()
    scope_key = str(milestone.get("scopeKey", "")).strip()
    milestone_key = str(milestone.get("milestoneKey", "")).strip()
    if scope_type == "PROJECT":
        return scope_key in {"", "GLOBAL"}
    return scope_type == "" and "::PROJECT::GLOBAL::" in milestone_key


def _backward_graph_milestone_sort_key(milestone: dict[str, Any]) -> tuple[int, str]:
    preferred_order = {
        "POWER_ON": 0,
        "CLUSTER_DEBUG": 1,
    }
    milestone_type = str(milestone.get("milestoneType", "")).strip()
    return (preferred_order.get(milestone_type, 99), str(milestone.get("milestoneKey", "")))


def _load_project_backward_graph_target_milestones(project_id: str) -> list[dict[str, Any]]:
    milestones = [
        milestone
        for milestone in _load_project_backward_target_milestones(project_id)
        if _is_project_global_milestone(milestone)
    ]
    milestones.sort(key=_backward_graph_milestone_sort_key)
    return milestones


def _build_backward_anchor_option(milestone: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(milestone.get("milestoneKey", "")),
        "label": str(milestone.get("milestoneName", "锚点")),
        "milestoneType": str(milestone.get("milestoneType", "")),
        "anchorDate": str(milestone.get("anchorDate", "")),
        "scopeType": str(milestone.get("scopeType", "")),
        "scopeKey": str(milestone.get("scopeKey", "")),
    }


def _load_project_forward_start_milestones(project_id: str) -> list[dict[str, Any]]:
    milestones = get_object_data(MILESTONE_OBJECT_TYPE, project_id=project_id)
    forward_starts: list[dict[str, Any]] = []
    for milestone in milestones:
        if str(milestone.get("directionRole", "")).strip() != "FORWARD_START":
            continue
        forward_starts.append(milestone)
    forward_starts.sort(key=lambda item: (str(item.get("milestoneName", "")), str(item.get("milestoneKey", ""))))
    return forward_starts


def _load_project_milestone_compression_targets(project_id: str) -> list[dict[str, Any]]:
    milestones = get_object_data(MILESTONE_OBJECT_TYPE, project_id=project_id)
    compression_targets: list[dict[str, Any]] = []
    for milestone in milestones:
        if str(milestone.get("directionRole", "")).strip() != MILESTONE_COMPRESSION_TARGET_ROLE:
            continue
        compression_targets.append(milestone)
    compression_targets.sort(key=lambda item: (str(item.get("milestoneName", "")), str(item.get("milestoneKey", ""))))
    return compression_targets


def _parse_anchor_date_from_milestone(milestone: dict[str, Any]) -> date:
    milestone_key = str(milestone.get("milestoneKey", "")).strip() or "<unknown>"
    raw_anchor = str(milestone.get("anchorDate", "")).strip()
    if not raw_anchor:
        raise ValueError(f"Milestone `{milestone_key}` missing required `anchorDate`.")
    normalized_anchor = raw_anchor.replace("/", "-")
    if len(normalized_anchor) >= 10:
        normalized_anchor = normalized_anchor[:10]
    try:
        return parse_date(normalized_anchor)
    except Exception as exc:
        raise ValueError(f"Milestone `{milestone_key}` has invalid anchorDate `{raw_anchor}`.") from exc


def _parse_forward_anchor_date_from_milestone(milestone: dict[str, Any]) -> date:
    milestone_key = str(milestone.get("milestoneKey", "")).strip() or "<unknown>"
    for field_name in ("plannedDate", "actualDate", "anchorDate"):
        raw_value = str(milestone.get(field_name, "")).strip()
        if not raw_value:
            continue
        parsed = _try_parse_plan_date(raw_value)
        if parsed is not None:
            return parsed
        raise ValueError(f"FORWARD_START milestone `{milestone_key}` has invalid {field_name} `{raw_value}`.")
    raise ValueError(f"FORWARD_START milestone `{milestone_key}` missing required date.")


def _parse_temporary_forward_anchor(
    ontology: LocalScheduleOntology,
    payload: dict[str, Any],
) -> tuple[Any, date, date, str]:
    if not isinstance(payload, dict):
        raise ValueError("temporary_anchor must be an object.")
    row_key = str(payload.get("rowKey") or payload.get("row_key") or payload.get("milestoneId") or "").strip()
    if not row_key:
        raise KeyError("temporary_anchor.rowKey is required.")
    row = ontology.objects.DeliveryPlanRow.get_or_none(row_key)
    if row is None:
        raise KeyError(f"DeliveryPlanRow rowKey not found: {row_key}")

    changed_field = str(payload.get("field") or "").strip()
    if not changed_field:
        if "endDate" in payload:
            changed_field = "endDate"
        elif "startDate" in payload:
            changed_field = "startDate"
    if changed_field not in {"startDate", "endDate"}:
        raise ValueError("temporary_anchor.field must be startDate or endDate.")

    raw_start = payload.get("startDate")
    raw_end = payload.get("endDate")
    if raw_start is None or str(raw_start).strip() == "":
        raw_start = row.startDate
    if raw_end is None or str(raw_end).strip() == "":
        raw_end = row.endDate
    start_date = _required_iso_date_value(raw_start, "temporary_anchor.startDate")
    end_date = _required_iso_date_value(raw_end, "temporary_anchor.endDate")
    if end_date < start_date:
        raise ValueError("temporary_anchor.endDate must not be earlier than startDate.")
    return row, start_date, end_date, changed_field


def _parse_forward_manual_overrides(
    ontology: LocalScheduleOntology,
    payload: list[dict[str, Any]] | None,
    csv_rows: list[dict[str, Any]],
    start_column: str,
    end_column: str,
    preview_results: dict[str, Any] | None = None,
) -> list[ForwardManualOverrideRecord]:
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise ValueError("manual_overrides must be a list.")

    deduped: dict[tuple[str, str], ForwardManualOverrideRecord] = {}
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"manual_overrides[{index}] must be an object.")
        target_id = str(
            item.get("target_id")
            or item.get("targetId")
            or item.get("rowKey")
            or item.get("milestoneId")
            or ""
        ).strip()
        if not target_id:
            raise KeyError(f"manual_overrides[{index}].target_id is required.")

        field = str(item.get("field") or "").strip()
        if field not in {"startDate", "endDate"}:
            raise ValueError(f"manual_overrides[{index}].field must be startDate or endDate.")

        raw_new_value = item.get("new_value") if "new_value" in item else item.get("newValue")
        new_date = _required_iso_date_value(raw_new_value, f"manual_overrides[{index}].new_value")
        row = ontology.objects.DeliveryPlanRow.get_or_none(target_id)
        if row is None:
            raise KeyError(f"DeliveryPlanRow rowKey not found: {target_id}")

        row_index = row.activity.row_order
        source_row = csv_rows[row_index] if 0 <= row_index < len(csv_rows) else {}
        current_start = source_row.get(start_column, getattr(row, "startDate", ""))
        current_end = source_row.get(end_column, getattr(row, "endDate", ""))
        preview_schedule = (preview_results or {}).get(row.localRowKey)
        start_reference = getattr(preview_schedule, "start", None) or current_start
        end_reference = getattr(preview_schedule, "finish", None) or current_end
        start_date = _required_plan_date_value(start_reference, f"manual_overrides[{index}].current_startDate")
        end_date = _required_plan_date_value(end_reference, f"manual_overrides[{index}].current_endDate")
        original_raw = current_end if field == "endDate" else current_start
        original_date = str(original_raw or "")

        if field == "startDate":
            start_date = new_date
        else:
            end_date = new_date
        if end_date < start_date:
            raise ValueError(f"manual_overrides[{index}].endDate must not be earlier than startDate.")

        deduped[(target_id, field)] = ForwardManualOverrideRecord(
            row=row,
            field=field,
            original_date=original_date,
            new_date=new_date,
            start_date=start_date,
            end_date=end_date,
        )
    return list(deduped.values())


def _resolve_target_rows_for_milestone(
    ontology: LocalScheduleOntology,
    milestone: dict[str, Any],
    *,
    anchor_date: date | None = None,
) -> list[Any]:
    milestone_type = str(milestone.get("milestoneType", "")).strip()
    milestone_key = str(milestone.get("milestoneKey", "")).strip() or "<unknown>"
    rule = MILESTONE_TARGET_RULES.get(milestone_type)
    if rule is None:
        raise ValueError(f"No target rule configured for milestoneType `{milestone_type}` ({milestone_key}).")
    substrings = [str(item) for item in (rule.get("name_substrings") or []) if str(item).strip()]
    if not substrings:
        raise ValueError(f"Milestone target rule `{milestone_type}` has empty name_substrings.")
    candidates = _rows_matching_name_substrings(ontology, substrings)
    if not candidates:
        raise ValueError(f"No DeliveryPlanRow matched milestoneType `{milestone_type}` for `{milestone_key}`.")
    candidates = _filter_rows_by_milestone_scope(candidates, milestone)
    if not candidates:
        scope_key = str(milestone.get("scopeKey", "")).strip()
        raise ValueError(
            f"No DeliveryPlanRow matched milestoneType `{milestone_type}` for `{milestone_key}` "
            f"within scope `{scope_key}`."
        )
    if rule.get("match_all") is True:
        return sorted(candidates, key=lambda row: row.activity.row_order)
    try:
        row, _ = _pick_one_plan_row_for_anchor(
            candidates,
            str(rule.get("pick") or "first_row_order"),
            anchor_date=anchor_date,
        )
        return [row]
    except ValueError as exc:
        raise ValueError(
            f"Unable to resolve DeliveryPlanRow for milestoneType `{milestone_type}` ({milestone_key}): {exc}"
        ) from exc


def _filter_rows_by_milestone_scope(
    rows: list[Any],
    milestone: dict[str, Any],
) -> list[Any]:
    scope_type = str(milestone.get("scopeType", "")).strip()
    scope_key = str(milestone.get("scopeKey", "")).strip()
    if scope_type != "POD" or not scope_key:
        return rows
    return [
        row
        for row in rows
        if scope_key in _row_management_units(row)
    ]


def _resolve_forward_rows_for_milestone(ontology: LocalScheduleOntology, milestone: dict[str, Any]) -> list[Any]:
    milestone_type = str(milestone.get("milestoneType", "")).strip()
    milestone_key = str(milestone.get("milestoneKey", "")).strip() or "<unknown>"
    rule = FORWARD_MILESTONE_TARGET_RULES.get(milestone_type)
    if rule is None:
        raise ValueError(f"No forward target rule configured for milestoneType `{milestone_type}` ({milestone_key}).")
    substrings = [str(item) for item in (rule.get("name_substrings") or []) if str(item).strip()]
    if not substrings:
        raise ValueError(f"Forward milestone target rule `{milestone_type}` has empty name_substrings.")
    candidates = _rows_matching_name_substrings(ontology, substrings)
    if not candidates:
        raise ValueError(f"No DeliveryPlanRow matched forward milestoneType `{milestone_type}` for `{milestone_key}`.")
    if rule.get("match_all") is True:
        return sorted(candidates, key=lambda row: row.activity.row_order)
    row, _ = _pick_one_plan_row_for_anchor(candidates, str(rule.get("pick") or "first_row_order"))
    return [row]


def _compression_dependency_milestone_types(milestone: dict[str, Any]) -> list[str]:
    raw_value = str(milestone.get("dependencyMilestoneTypes", "")).strip()
    if not raw_value:
        return list(DEFAULT_COMPRESSION_BASELINE_MILESTONE_TYPES)
    values = [item.strip() for item in raw_value.replace("，", ",").split(",")]
    return [item for item in values if item]


def _resolve_compression_baseline_rows(ontology: LocalScheduleOntology, milestone: dict[str, Any]) -> list[Any]:
    milestone_key = str(milestone.get("milestoneKey", "")).strip() or "<unknown>"
    rows_by_key: dict[str, Any] = {}
    for dependency_type in _compression_dependency_milestone_types(milestone):
        rule = MILESTONE_TARGET_RULES.get(dependency_type)
        if rule is None:
            raise ValueError(
                f"No compression baseline rule configured for milestoneType `{dependency_type}` ({milestone_key})."
            )
        substrings = [str(item) for item in (rule.get("name_substrings") or []) if str(item).strip()]
        if not substrings:
            raise ValueError(f"Compression baseline rule `{dependency_type}` has empty name_substrings.")
        candidates = _rows_matching_name_substrings(ontology, substrings)
        if not candidates:
            raise ValueError(
                f"No DeliveryPlanRow matched compression baseline milestoneType `{dependency_type}` for `{milestone_key}`."
            )
        for row in candidates:
            rows_by_key[str(row.rowKey)] = row
    return sorted(rows_by_key.values(), key=lambda row: row.activity.row_order)


def _resolve_selected_row_for_milestone(
    ontology: LocalScheduleOntology,
    milestone: dict[str, Any],
    *,
    anchor_date: date | None = None,
) -> Any:
    return _resolve_target_rows_for_milestone(ontology, milestone, anchor_date=anchor_date)[0]


def _is_reachable(ontology: LocalScheduleOntology, candidate_key: str, target_key: str) -> bool:
    if candidate_key == target_key:
        return True
    stack = [target_key]
    visited: set[str] = set()
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        row = ontology.row(current)
        for dependency_key in row.activity.dependency_keys:
            if dependency_key == candidate_key:
                return True
            stack.append(dependency_key)
    return False


def _try_parse_plan_date(raw_value: str) -> date | None:
    text = str(raw_value or "").strip()
    if not text:
        return None

    normalized = text.replace("/", "-")
    if len(normalized) >= 10:
        normalized = normalized[:10]

    try:
        return parse_date(normalized)
    except Exception:
        return None


def _is_semantic_date_change(current_value: Any, next_value: Any) -> bool:
    current_text = str(current_value or "").strip()
    next_text = str(next_value or "").strip()
    current_date = _try_parse_plan_date(current_text)
    next_date = _try_parse_plan_date(next_text)
    if current_date is not None and next_date is not None:
        return current_date != next_date
    return current_text != next_text


def _required_plan_date_value(value: Any, field_name: str) -> date:
    parsed = _try_parse_plan_date(str(value or ""))
    if parsed is None:
        raise ValueError(f"{field_name} must be a date.")
    return parsed


def _date_change_type(field: str) -> str:
    return "UPDATE_START_DATE" if field == "startDate" else "UPDATE_END_DATE"


def _date_field_label(field: str) -> str:
    return "开始日期" if field == "startDate" else "结束日期"


def _object_binding(object_type: str):
    return load_datasource_bindings().object_type(object_type)


def _ensure_supported_object_type(object_type: str) -> None:
    if object_type not in SUPPORTED_OBJECT_TYPES:
        supported = ", ".join(sorted(SUPPORTED_OBJECT_TYPES))
        raise ValueError(f"Unsupported object_type `{object_type}`. Supported: {supported}.")


def _ensure_supported_action(object_type: str, action_name: str) -> None:
    supported_actions = set()
    if object_type == DELIVERY_PLAN_ROW_OBJECT_TYPE:
        supported_actions.add("update_delivery_plan_row")
    supported_actions.update(
        name
        for name, action_schema in _load_action_types().items()
        if action_schema.get("targetObjectTypeApiName") == object_type
    )
    if action_name not in supported_actions:
        raise ValueError(f"Unsupported action `{action_name}` for {object_type}.")


def _get_milestone_data(project_id: str | None) -> list[dict[str, Any]]:
    milestone_path = BASE_DIR / MILESTONE_SOURCE_FILE
    rows, _ = _read_csv(milestone_path)
    selected_sources = _select_sources(project_id)
    project_keys = {source.project_key for source in selected_sources}

    milestones = []
    for row in rows:
        if row.get("projectKey") not in project_keys:
            continue
        item = _json_safe(row)
        item["sourceFile"] = item.get("sourceFile") or MILESTONE_SOURCE_FILE
        milestones.append(item)
    return milestones


def _get_csv_table_data(object_type: str, sources: list[Any], project_id: str | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in sources:
        csv_rows, _ = _read_csv(_datasource_path(source))
        for row in csv_rows:
            item = _csv_table_row_to_object(object_type, row, source)
            if _matches_datasource_project(item, source, project_id):
                rows.append(item)
    return rows


def _csv_table_row_to_object(object_type: str, row: dict[str, Any], source: Any) -> dict[str, Any]:
    schema = _load_object_types().get(object_type) or {}
    properties = schema.get("properties") or {}
    source_to_api = {
        str(prop.get("sourceColumnName")).strip(): str(prop.get("apiName") or fallback_name)
        for fallback_name, prop in properties.items()
        if isinstance(prop, dict) and str(prop.get("sourceColumnName") or "").strip()
    }
    item: dict[str, Any] = {}
    for fallback_name, prop in properties.items():
        if not isinstance(prop, dict):
            continue
        api_name = str(prop.get("apiName") or fallback_name)
        source_column = str(prop.get("sourceColumnName") or "")
        if api_name in row:
            item[api_name] = row.get(api_name)
        elif source_column and source_column in row:
            item[api_name] = row.get(source_column)
    for key, value in row.items():
        if key in item or key in source_to_api:
            continue
        item[key] = value
    if "projectKey" in properties and not str(item.get("projectKey") or "").strip() and source.project_key:
        item["projectKey"] = source.project_key
    if "projectId" in properties and not str(item.get("projectId") or "").strip() and source.project_id:
        item["projectId"] = source.project_id
    if "sourceFile" in properties and not str(item.get("sourceFile") or "").strip():
        item["sourceFile"] = source.file_name
    return _json_safe(item)


def _get_json_section_data(sources: list[Any], project_id: str | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in sources:
        payload = _read_json_datasource(source)
        document = _json_document_metadata(payload, source)
        sections = payload.get("sections")
        if not isinstance(sections, list):
            raise ValueError(f"JSON datasource `{source.datasource_id}` must contain a sections array.")
        for index, section in enumerate(sections, start=1):
            if not isinstance(section, dict):
                raise ValueError(f"JSON datasource `{source.datasource_id}` sections must contain objects.")
            item = _json_section_row(source, document, section, index)
            if _matches_datasource_project(item, source, project_id):
                rows.append(item)
    return rows


def _read_json_datasource(source: Any) -> dict[str, Any]:
    path = _datasource_path(source)
    if not path.exists():
        raise FileNotFoundError(f"Backing JSON file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Backing JSON file is invalid: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON datasource `{source.datasource_id}` must be a JSON object.")
    return payload


def _read_json_rows_datasource(source: Any) -> list[dict[str, Any]]:
    """Read a JSON datasource whose top level is an array of object rows.

    Counterpart of _read_json_datasource (which expects a `{sections: [...]}` document): the
    contingency reference datasources (RiskRule / EquipmentConfig / ComponentConfig /
    MaintenancePolicy) are flat row arrays. A missing or malformed file raises a clear error
    rather than silently returning partial data.
    """
    path = _datasource_path(source)
    if not path.exists():
        raise FileNotFoundError(f"Backing JSON file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Backing JSON file is invalid: {path}") from exc
    if not isinstance(payload, list):
        raise ValueError(f"JSON datasource `{source.datasource_id}` must be a JSON array of rows.")
    return [row for row in payload if isinstance(row, dict)]


def _get_json_rows_data(sources: list[Any], project_id: str | None) -> list[dict[str, Any]]:
    """Read object rows from one or more flat-array JSON datasources (reader: json_rows).

    Mirrors _get_json_section_data but for plain row arrays: stamps sourceFile and applies the
    standard optional project filter. project_id is None on the contingency derivation path, so
    all rows flow through and per-project isolation is applied downstream by
    _filter_rows_by_project_key on each row's projectKey.
    """
    rows: list[dict[str, Any]] = []
    for source in sources:
        for raw in _read_json_rows_datasource(source):
            item = dict(raw)
            item.setdefault("sourceFile", source.file_name)
            if _matches_datasource_project(item, source, project_id):
                rows.append(item)
    return rows


def _datasource_path(source: Any) -> Path:
    path = Path(str(source.path or ""))
    return path if path.is_absolute() else BASE_DIR / path


def _json_document_metadata(payload: dict[str, Any], source: Any) -> dict[str, str]:
    return {
        "documentId": _string_value(payload.get("documentId") or source.datasource_id),
        "projectId": _string_value(payload.get("projectId") or source.project_id),
        "docType": _string_value(payload.get("docType") or source.metadata.get("docType")),
        "sourceFile": _string_value(payload.get("sourceFile") or source.file_name),
        "sourceMediaItemRid": _string_value(payload.get("sourceMediaItemRid")),
        "parseVersion": _string_value(payload.get("parseVersion")),
        "parsedAt": _string_value(payload.get("parsedAt")),
    }


def _json_section_row(
    source: Any,
    document: dict[str, str],
    section: dict[str, Any],
    index: int,
) -> dict[str, str]:
    order_index = _section_order_index(section, index)
    document_id = _string_value(section.get("documentId") or document["documentId"])
    facts = section.get("facts")
    return {
        "sectionId": _string_value(section.get("sectionId") or _generated_section_id(document_id, order_index, index)),
        "documentId": document_id,
        "projectId": _string_value(section.get("projectId") or document["projectId"] or source.project_id),
        "docType": _string_value(section.get("docType") or document["docType"] or source.metadata.get("docType")),
        "sourceFile": _string_value(section.get("sourceFile") or document["sourceFile"] or source.file_name),
        "sourceMediaItemRid": _string_value(section.get("sourceMediaItemRid") or document["sourceMediaItemRid"]),
        "parseVersion": _string_value(section.get("parseVersion") or document["parseVersion"]),
        "parsedAt": _string_value(section.get("parsedAt") or document["parsedAt"]),
        "titlePath": _string_value(section.get("titlePath")),
        "headingLevel": _string_value(section.get("headingLevel")),
        "orderIndex": _string_value(order_index),
        "markdownContent": _string_value(section.get("markdownContent")),
        "plainText": _string_value(section.get("plainText")),
        "factsJson": "" if facts is None else json.dumps(facts, ensure_ascii=False),
    }


def _section_order_index(section: dict[str, Any], fallback: int) -> int:
    raw_value = section.get("orderIndex")
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return fallback


def _generated_section_id(document_id: str, order_index: int, fallback: int) -> str:
    base = document_id or "document"
    try:
        suffix = f"{int(order_index):03d}"
    except (TypeError, ValueError):
        suffix = f"{fallback:03d}"
    return f"{base}::{suffix}"


def _matches_datasource_project(item: dict[str, Any], source: Any, project_id: str | None) -> bool:
    if project_id is None or project_id == "":
        return True
    expected = _normalize_project_id(project_id)
    item_project_id = str(item.get("projectId") or "").strip()
    if item_project_id:
        return expected == _normalize_project_id(item_project_id)
    item_project_key = str(item.get("projectKey") or "").strip()
    if item_project_key:
        return expected == _normalize_project_id(item_project_key)
    candidates = {
        _normalize_project_id(str(source.project_id or "")),
        _normalize_project_id(str(source.project_key or "")),
    }
    return expected in candidates


def _string_value(value: Any) -> str:
    return "" if value is None else str(value)


def _source_updated_at(source: ProjectSource) -> str:
    try:
        return datetime.fromtimestamp(source.path.stat().st_mtime).isoformat(timespec="seconds")
    except OSError:
        return ""


def _get_delivery_project_data(project_id: str | None) -> list[dict[str, Any]]:
    return [
        {
            "projectKey": source.project_key,
            "projectName": source.project_id,
            "sourceFile": source.file_name,
            "sourceUpdatedAt": _source_updated_at(source),
            "planVersion": "",
            "description": f"{source.project_id} 交付计划本体演示项目",
        }
        for source in _select_sources(project_id)
    ]


def _split_management_units(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    units: list[str] = []
    seen: set[str] = set()
    for raw_unit in text.replace("，", ",").split(","):
        unit = raw_unit.strip()
        if not unit or unit in seen:
            continue
        seen.add(unit)
        units.append(unit)
    return units


def _get_delivery_pod_data(project_id: str | None) -> list[dict[str, Any]]:
    pods_by_key: dict[str, dict[str, Any]] = {}
    batch_values_by_key: dict[str, set[str]] = {}

    for row in get_object_data(DELIVERY_PLAN_ROW_OBJECT_TYPE, project_id=project_id):
        project_key = str(row.get("projectKey") or "").strip()
        if not project_key:
            continue
        for unit in _split_management_units(row.get("managementUnit")):
            pod_key = f"{project_key}::{unit}"
            pod = pods_by_key.setdefault(
                pod_key,
                {
                    "podKey": pod_key,
                    "projectKey": project_key,
                    "podName": unit,
                    "managementUnit": unit,
                    "batch": "",
                    "description": "",
                    "activityCount": 0,
                    "sourceFile": row.get("sourceFile", ""),
                },
            )
            pod["activityCount"] = int(pod["activityCount"]) + 1
            batch = str(row.get("batch") or "").strip()
            if batch:
                batch_values_by_key.setdefault(pod_key, set()).add(batch)

    for pod_key, pod in pods_by_key.items():
        batches = sorted(batch_values_by_key.get(pod_key, set()))
        pod["batch"] = ",".join(batches)
        pod["description"] = f"{pod['managementUnit']} 关联 {pod['activityCount']} 条计划活动"

    return sorted(
        pods_by_key.values(),
        key=lambda item: (str(item.get("projectKey", "")), str(item.get("managementUnit", ""))),
    )


def _select_sources(project_id: str | None) -> list[ProjectSource]:
    if project_id is None or project_id == "":
        return list(PROJECT_SOURCES.values())
    normalized_project_id = _normalize_project_id(project_id)
    try:
        return [PROJECT_SOURCES[normalized_project_id]]
    except KeyError as exc:
        raise KeyError(f"Unknown project_id: {project_id}") from exc


def _normalize_project_id(project_id: str) -> str:
    raw = str(project_id).strip()
    if not raw:
        return raw
    if raw in PROJECT_SOURCES:
        return raw
    zjyd = "\u6d59\u6c5f\u79fb\u52a8"
    jd = "\u4eac\u4e1c"
    aliases = {
        "zjyd": zjyd,
        "jd": jd,
        "jingdong": jd,
        "zhejiangyidong": zjyd,
    }
    lowered = raw.lower()
    if lowered in aliases:
        return aliases[lowered]
    # 容错：部分终端或历史数据会把中文项目名编码错乱成“???”。
    if "?" in raw:
        if "?" in raw and "??" in raw:
            # 在问号降级场景下，优先映射到浙江移动（默认项目）。
            return zjyd
    if "\u6d59\u6c5f" in raw or "\u79fb\u52a8" in raw:
        return zjyd
    if "\u4eac\u4e1c" in raw:
        return jd
    return raw


def _source_for_row_key(row_key: str, project_id: Any = None) -> ProjectSource:
    if project_id:
        return _select_sources(str(project_id))[0]
    for source in PROJECT_SOURCES.values():
        if row_key.startswith(f"{source.project_key}::"):
            return source
    raise KeyError(f"Unable to infer project source from rowKey: {row_key}")


def _source_for_object_key(object_type: str, object_key: str, project_id: Any = None) -> ProjectSource:
    return _source_for_row_key(object_key, project_id)


def _project_id_from_milestone_key(milestone_key: str) -> str:
    parts = milestone_key.split("::")
    if not parts:
        raise KeyError(f"Unable to infer project_id from milestoneKey: {milestone_key}")
    project_key = parts[0]
    for source in PROJECT_SOURCES.values():
        if source.project_key == project_key:
            return source.project_id
    raise KeyError(f"Unable to infer project_id from milestoneKey: {milestone_key}")


def _primary_key_field(object_type: str) -> str:
    if object_type == MILESTONE_OBJECT_TYPE:
        return "milestoneKey"
    return "rowKey"


def _find_row_index(rows: list[dict[str, str]], key_column: str, object_key: str) -> int:
    for idx, row in enumerate(rows):
        if str(row.get(key_column, "")) == object_key:
            return idx
    return -1


def _truthy_text(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return text in {"true", "1", "yes", "y", "是", "已采纳", "adopted"}


def _format_sla_days(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = re.fullmatch(r"(\d+)\s*(?:天|d|D)?", text)
    if match:
        return f"{int(match.group(1))}天"
    return text


def _apply_effective_sla_to_plan_row_items(
    rows: list[dict[str, Any]],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    project_keys = [str(project_id or "").strip()] if project_id else sorted(
        {
            str(row.get("projectKey") or "").strip()
            for row in rows
            if isinstance(row, dict) and str(row.get("projectKey") or "").strip()
        }
    )
    standard_by_row_key: dict[str, object] = {}
    limit_by_row_key: dict[str, object] = {}
    for key in project_keys:
        if not key:
            continue
        standard, limit = _effective_sla_overrides_for_project(key)
        standard_by_row_key.update(standard)
        limit_by_row_key.update(limit)

    if not standard_by_row_key and not limit_by_row_key:
        return rows

    output: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        row_key = str(item.get("rowKey") or "").strip()
        standard_sla = _format_sla_days(standard_by_row_key.get(row_key))
        if standard_sla:
            item["sla"] = standard_sla
            item["standardDuration"] = standard_sla
        limit_sla = _format_sla_days(limit_by_row_key.get(row_key))
        if limit_sla:
            item["limitDuration"] = limit_sla
        output.append(item)
    return output


def _effective_sla_overrides_for_project(project_id: str) -> tuple[dict[str, object], dict[str, object]]:
    if ACTIVITY_SLA_ESTIMATE_OBJECT_TYPE not in SUPPORTED_OBJECT_TYPES:
        return {}, {}
    try:
        rows = get_object_data(ACTIVITY_SLA_ESTIMATE_OBJECT_TYPE, project_id=project_id)
    except Exception:
        return {}, {}

    standard_by_row_key: dict[str, object] = {}
    limit_by_row_key: dict[str, object] = {}
    for row in rows:
        if not _truthy_text(row.get("isAdopted")):
            continue
        row_key = str(row.get("rowKey") or "").strip()
        if not row_key:
            continue
        standard_sla = row.get("standardSlaDays")
        if standard_sla not in (None, ""):
            standard_by_row_key[row_key] = standard_sla
        limit_sla = row.get("limitSlaDays")
        if limit_sla not in (None, ""):
            limit_by_row_key[row_key] = limit_sla
    return standard_by_row_key, limit_by_row_key


def _load_ontology(source: ProjectSource, *, use_effective_sla: bool = False) -> LocalScheduleOntology:
    path = source.path
    if not path.exists():
        raise FileNotFoundError(f"Backing CSV file not found: {path}")
    effective_sla_by_row_key: dict[str, object] = {}
    effective_limit_duration_by_row_key: dict[str, object] = {}
    if use_effective_sla:
        effective_sla_by_row_key, effective_limit_duration_by_row_key = _effective_sla_overrides_for_project(
            source.project_id
        )
    preview_context = get_current_preview_branch()
    if not preview_context.is_main:
        rows = read_delivery_plan_source_rows(
            preview_context,
            project_key=source.project_key,
            source_columns=_api_to_source_columns(DELIVERY_PLAN_ROW_OBJECT_TYPE),
        )
        return LocalScheduleOntology.from_rows(
            rows,
            source_path=path,
            project_key=source.project_key,
            project_name=source.project_id,
            effective_sla_by_row_key=effective_sla_by_row_key,
            effective_limit_duration_by_row_key=effective_limit_duration_by_row_key,
        )
    return LocalScheduleOntology.from_file(
        path,
        project_key=source.project_key,
        project_name=source.project_id,
        effective_sla_by_row_key=effective_sla_by_row_key,
        effective_limit_duration_by_row_key=effective_limit_duration_by_row_key,
    )


def _api_to_source_columns(object_type: str) -> dict[str, str]:
    object_type_schema = _load_object_types().get(object_type)
    if object_type_schema is None:
        raise KeyError(f"Object type schema not found: {object_type}")

    mapping: dict[str, str] = {}
    for fallback_name, property_schema in object_type_schema.get("properties", {}).items():
        source_column = property_schema.get("sourceColumnName")
        if not source_column:
            continue
        api_name = property_schema.get("apiName", fallback_name)
        mapping[api_name] = source_column
    return mapping


def _load_object_types() -> dict[str, Any]:
    with OBJECT_TYPES_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_action_types() -> dict[str, Any]:
    with ACTION_TYPES_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        raise FileNotFoundError(f"Backing CSV file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return rows, fieldnames


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _payload_value(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _payload_object_key(
    payload: dict[str, Any],
    object_type: str,
    action_name: str,
    *,
    primary_key_field: str | None = None,
) -> Any:
    primary_key_field = primary_key_field or _primary_key_field(object_type)
    if object_type == MILESTONE_OBJECT_TYPE:
        direct_keys = (primary_key_field, "milestoneId", "rowKey", "row_key")
    else:
        direct_keys = (primary_key_field, "rowKey", "row_key")

    direct_value = _payload_value(payload, *direct_keys)
    object_key = _extract_payload_object_key(direct_value, primary_key_field)
    if object_key:
        return object_key

    target_parameter = _action_target_parameter(action_name)
    if target_parameter:
        return _extract_payload_object_key(payload.get(target_parameter), primary_key_field)
    return None


def _extract_payload_object_key(value: Any, primary_key_field: str) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        for key in (primary_key_field, "milestoneKey", "rowKey", "row_key", "id", "rid"):
            raw_value = value.get(key)
            if raw_value is not None and str(raw_value).strip():
                return raw_value
        return None
    return value


def _action_target_parameter(action_name: str) -> str | None:
    action_schema = _load_action_types().get(action_name) or {}
    for edit in action_schema.get("edits", []):
        if not isinstance(edit, dict):
            continue
        target_parameter = str(edit.get("targetParameter") or "").strip()
        if target_parameter:
            return target_parameter

    for parameter_name, parameter_schema in action_schema.get("parameters", {}).items():
        if not isinstance(parameter_schema, dict):
            continue
        data_type = parameter_schema.get("dataType", {})
        if isinstance(data_type, dict) and data_type.get("type") == "ontologyObject":
            return str(parameter_name)
    return None


def _payload_changes(payload: dict[str, Any], action_name: str) -> dict[str, Any]:
    changes = payload.get("changes")
    if changes is None:
        changes = payload.get("formData")
    if changes is None:
        editable_fields = _action_edit_fields(action_name)
        changes = {
            field: payload[field]
            for field in editable_fields
            if field in payload
        }
    if not isinstance(changes, dict) or not changes:
        raise ValueError("payload.changes must contain at least one field to update.")
    return changes


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _action_edit_fields(action_name: str) -> set[str]:
    action_schema = _load_action_types().get(action_name) or {}
    fields: set[str] = set()
    for edit in action_schema.get("edits", []):
        if not isinstance(edit, dict):
            continue
        property_updates = edit.get("propertyUpdates", {})
        if isinstance(property_updates, dict):
            fields.update(str(field) for field in property_updates)
    return fields


def _validate_action_target_constraints(action_name: str, target_row: dict[str, Any]) -> None:
    action_schema = _load_action_types().get(action_name) or {}
    constraints = action_schema.get("targetConstraints")
    if not isinstance(constraints, dict) or not constraints:
        return

    for field_name, expected_value in constraints.items():
        actual = str(target_row.get(str(field_name), "")).strip()
        if isinstance(expected_value, list):
            allowed_values = {str(value).strip() for value in expected_value}
        else:
            allowed_values = {str(expected_value).strip()}
        if actual not in allowed_values:
            allowed_text = ", ".join(sorted(allowed_values))
            raise ValueError(
                f"Action `{action_name}` requires target {field_name}={allowed_text}; got {actual or '<empty>'}."
            )


def _validate_action_state_transition(
    action_name: str,
    current_row: dict[str, Any],
    changes: dict[str, Any],
    object_type: str,
) -> None:
    """Generic, declaration-driven state-machine guard for an Action.

    Reads `stateTransitions` from the action schema and rejects illegal from->to
    moves of the governed field. Inert unless the action declares stateTransitions
    AND the governed field is in the pending changes, so existing actions are
    unaffected.
    """
    action_schema = _load_action_types().get(action_name) or {}
    _validate_state_transition_spec(
        action_name, action_schema.get("stateTransitions"), current_row, changes, object_type
    )


def _validate_state_transition_spec(
    action_name: str,
    transitions: Any,
    current_row: dict[str, Any],
    changes: dict[str, Any],
    object_type: str,
) -> None:
    """Spec-driven core of the state-machine guard.

    Shared by the action-level `stateTransitions` declaration and the per-edit specs
    carried by follow-on lifecycle edits (MODIFY_OBJECT edits inside CREATE actions,
    e.g. CreateDeliverabilityAssessment bumping its plan DRAFT -> ASSESSING).
    """
    if not isinstance(transitions, dict) or not transitions:
        return
    field = str(transitions.get("field", "")).strip()
    allowed = transitions.get("allowed")
    if not field or not isinstance(allowed, dict) or field not in changes:
        return

    new_state = str(changes.get(field) or "").strip()
    if new_state == "":
        return  # clearing a value is handled by required-ness rules, not the state machine

    current_state = ""
    if isinstance(current_row, dict):
        raw = current_row.get(field)
        if raw in (None, ""):
            source_column = _api_to_source_columns(object_type).get(field)
            if source_column is not None:
                raw = current_row.get(source_column)
        current_state = str(raw or "").strip()

    if current_state == "":
        initial_states = {str(item).strip() for item in (transitions.get("initialStates") or [])}
        if initial_states and new_state not in initial_states:
            raise ValueError(
                f"Action `{action_name}`: `{new_state}` is not a valid initial state for `{field}`; "
                f"allowed initial states: {', '.join(sorted(initial_states))}."
            )
        return

    if current_state == new_state:
        return  # no-op transition

    legal_next = allowed.get(current_state)
    if legal_next is None:
        raise ValueError(
            f"Action `{action_name}`: unknown current state `{current_state}` for `{field}`; no transitions defined."
        )
    legal_set = {str(item).strip() for item in legal_next}
    if new_state not in legal_set:
        allowed_text = ", ".join(sorted(legal_set)) or "<none>"
        raise ValueError(
            f"Action `{action_name}`: illegal state transition for `{field}`: "
            f"{current_state} -> {new_state}; allowed next: {allowed_text}."
        )


def _criteria_field_value(
    field: str,
    changes: dict[str, Any],
    current_row: dict[str, Any],
    source_columns: dict[str, str],
) -> Any:
    """Resolve a submissionCriteria field: pending change first, else current state.

    Reading current state lets rules reference fields the action is not editing
    (e.g. approvedAdvanceDays <= requestedAdvanceDays).
    """
    if field in changes:
        return changes[field]
    if isinstance(current_row, dict):
        if field in current_row:
            return current_row[field]
        source_column = source_columns.get(field)
        if source_column is not None:
            return current_row.get(source_column)
    return None


def _compare_criteria_values(left: Any, right: Any, op: str) -> bool:
    left_text = "" if left is None else str(left).strip()
    right_text = "" if right is None else str(right).strip()
    if op == "eq":
        return left_text == right_text
    if op == "ne":
        return left_text != right_text
    if op == "nonEmpty":
        return left_text != ""
    if op == "empty":
        return left_text == ""
    if op in ("lt", "lte", "gt", "gte"):
        try:
            left_value: Any = float(left_text)
            right_value: Any = float(right_text)
        except ValueError:
            left_value, right_value = left_text, right_text
        if op == "lt":
            return left_value < right_value
        if op == "lte":
            return left_value <= right_value
        if op == "gt":
            return left_value > right_value
        return left_value >= right_value
    raise ValueError(f"Unsupported submissionCriteria op: {op}")


def _eval_criteria_node(
    node: dict[str, Any],
    changes: dict[str, Any],
    current_row: dict[str, Any],
    source_columns: dict[str, str],
) -> bool:
    """Evaluate one submissionCriteria condition node to a boolean (does it hold?)."""
    if not isinstance(node, dict):
        raise ValueError("submissionCriteria condition node must be an object.")
    if "all" in node:
        return all(_eval_criteria_node(child, changes, current_row, source_columns) for child in node["all"])
    if "any" in node:
        return any(_eval_criteria_node(child, changes, current_row, source_columns) for child in node["any"])
    if "not" in node:
        return not _eval_criteria_node(node["not"], changes, current_row, source_columns)

    op = str(node.get("op", "")).strip()
    if not op:
        raise ValueError("submissionCriteria leaf node requires an `op`.")
    left = _criteria_field_value(str(node.get("field", "")), changes, current_row, source_columns)
    if op in ("nonEmpty", "empty"):
        return _compare_criteria_values(left, None, op)
    if "field2" in node:
        right = _criteria_field_value(str(node.get("field2", "")), changes, current_row, source_columns)
    else:
        right = node.get("value")
    return _compare_criteria_values(left, right, op)


def _validate_action_submission_criteria(
    action_name: str,
    current_row: dict[str, Any],
    changes: dict[str, Any],
    object_type: str,
) -> None:
    """Generic, declaration-driven submission-criteria (business rule) guard.

    Each rule's `condition` must hold for the merged (current state + pending
    changes) record, else the action is rejected with the rule's message. Inert
    unless the action declares submissionCriteria, so existing actions are
    unaffected.
    """
    action_schema = _load_action_types().get(action_name) or {}
    criteria = action_schema.get("submissionCriteria")
    if not isinstance(criteria, list) or not criteria:
        return
    source_columns = _api_to_source_columns(object_type)
    for rule in criteria:
        if not isinstance(rule, dict):
            continue
        condition = rule.get("condition")
        if condition is None:
            continue
        if not _eval_criteria_node(condition, changes, current_row, source_columns):
            message = str(rule.get("message") or rule.get("name") or "submission criteria not satisfied")
            raise ValueError(f"Action `{action_name}` submission criteria failed: {message}")


def _load_automation_types() -> dict[str, Any]:
    if not AUTOMATION_TYPES_PATH.exists():
        return {}
    with AUTOMATION_TYPES_PATH.open("r", encoding="utf-8") as handle:
        automation_types = json.load(handle)
    return automation_types if isinstance(automation_types, dict) else {}


def _load_function_types_registry() -> dict[str, Any]:
    if not FUNCTION_TYPES_PATH.exists():
        return {}
    with FUNCTION_TYPES_PATH.open("r", encoding="utf-8") as handle:
        function_types = json.load(handle)
    return function_types if isinstance(function_types, dict) else {}


def _matching_automations(object_type: str, event: str) -> list[tuple[str, dict[str, Any]]]:
    matches: list[tuple[str, dict[str, Any]]] = []
    for name, schema in _load_automation_types().items():
        if not isinstance(schema, dict):
            continue
        if str(schema.get("status", "ACTIVE")).upper() != "ACTIVE":
            continue
        trigger = schema.get("trigger") or {}
        if str(trigger.get("objectTypeApiName", "")) != object_type:
            continue
        events = {str(item).upper() for item in (trigger.get("on") or [])}
        if event.upper() not in events:
            continue
        matches.append((name, schema))
    return matches


def _run_function_by_api_name(function_api_name: str, params: dict[str, Any]) -> Any:
    function_schema = _load_function_types_registry().get(function_api_name)
    if function_schema is None:
        raise KeyError(f"Function not found: {function_api_name}")
    binding = function_schema.get("binding") or {}
    if str(binding.get("module", "")) != "data_connector":
        raise ValueError(f"Unsupported automation function binding: {binding.get('module')}")
    func = globals().get(str(binding.get("function", "")))
    if not callable(func):
        raise ValueError(f"Automation function not callable: {binding.get('function')}")
    return func(**params)


def run_automations(object_type: str, event: str, context: dict[str, Any]) -> list[dict[str, Any]]:
    """Find automations whose trigger matches (objectType, event) and run their effect.

    Effects are read-only Function calls that produce *suggestions* (the project's
    derive-then-confirm red-line), never automatic writes. Per-automation failures
    are captured, never raised, so an automation cannot break the triggering action.
    """
    context = context or {}
    results: list[dict[str, Any]] = []
    for name, schema in _matching_automations(object_type, event):
        effect = schema.get("effect") or {}
        if str(effect.get("type", "")) != "RUN_FUNCTION":
            continue
        function_api_name = str(effect.get("functionApiName", ""))
        mapping = effect.get("parameterMapping") or {}
        params: dict[str, Any] = {}
        for param_name, source_field in mapping.items():
            value = context.get(str(source_field))
            if value not in (None, ""):
                params[param_name] = value
        entry: dict[str, Any] = {"automation": name, "function": function_api_name}
        try:
            entry["result"] = _run_function_by_api_name(function_api_name, params)
        except Exception as exc:  # advisory: never fail the triggering action
            entry["error"] = str(exc)
        results.append(entry)
    return results


def _run_automations_safe(object_type: str, event: str, context: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        return run_automations(object_type, event, context)
    except Exception:
        return []


def _object_to_constraint_row(target: Any) -> dict[str, Any]:
    if isinstance(target, dict):
        return target
    row: dict[str, Any] = {}
    for name in dir(target):
        if name.startswith("_"):
            continue
        try:
            value = getattr(target, name)
        except Exception:
            continue
        if callable(value):
            continue
        row[name] = value
    return row


def _validate_action_date_changes(object_type: str, changes: dict[str, Any]) -> None:
    date_fields = {"startDate", "endDate"}
    if object_type == MILESTONE_OBJECT_TYPE:
        date_fields.update({"plannedDate", "actualDate", "anchorDate"})
    for date_field in sorted(date_fields):
        if date_field in changes:
            _validate_iso_date_value(changes[date_field], f"changes.{date_field}")


def _load_value_types() -> dict[str, Any]:
    """Load Value Type definitions; missing file means no value-type constraints."""
    if not VALUE_TYPES_PATH.exists():
        return {}
    with VALUE_TYPES_PATH.open("r", encoding="utf-8") as handle:
        value_types = json.load(handle)
    return value_types if isinstance(value_types, dict) else {}


def _property_value_type_map(object_type: str) -> dict[str, str]:
    """Map property apiName -> Value Type apiName for one object type."""
    object_type_schema = _load_object_types().get(object_type) or {}
    mapping: dict[str, str] = {}
    for fallback_name, property_schema in object_type_schema.get("properties", {}).items():
        value_type = property_schema.get("valueType")
        if value_type:
            api_name = property_schema.get("apiName", fallback_name)
            mapping[api_name] = str(value_type)
    return mapping


def _validate_value_against_type(
    value: Any,
    value_type_name: str,
    value_type_def: dict[str, Any],
    field_name: str,
) -> None:
    """Generic, declaration-driven constraint evaluator for one value.

    Constraint kinds are read from value-types.json, so adding a constraint there
    takes effect without code changes. Blank values pass here; required-ness is
    enforced elsewhere (mirrors `_validate_iso_date_value`).
    """
    text = "" if value is None else str(value).strip()
    if text == "":
        return

    for constraint in value_type_def.get("constraints", []) or []:
        if not isinstance(constraint, dict):
            continue
        constraint_type = str(constraint.get("type", "")).strip()
        if constraint_type == "oneOf":
            allowed = [str(item) for item in constraint.get("values", [])]
            if text not in allowed:
                raise ValueError(
                    f"{field_name} must be one of [{', '.join(allowed)}] "
                    f"per value type `{value_type_name}`; got `{text}`."
                )
        elif constraint_type == "integer":
            try:
                int(text)
            except ValueError as exc:
                raise ValueError(
                    f"{field_name} must be an integer per value type `{value_type_name}`; got `{text}`."
                ) from exc
        elif constraint_type == "range":
            try:
                number = float(text)
            except ValueError as exc:
                raise ValueError(
                    f"{field_name} must be numeric per value type `{value_type_name}`; got `{text}`."
                ) from exc
            minimum = constraint.get("minimum")
            maximum = constraint.get("maximum")
            if minimum is not None and number < float(minimum):
                raise ValueError(
                    f"{field_name} must be >= {minimum} per value type `{value_type_name}`; got `{text}`."
                )
            if maximum is not None and number > float(maximum):
                raise ValueError(
                    f"{field_name} must be <= {maximum} per value type `{value_type_name}`; got `{text}`."
                )
        elif constraint_type == "pattern":
            pattern = str(constraint.get("regex", ""))
            if pattern and re.fullmatch(pattern, text) is None:
                raise ValueError(
                    f"{field_name} must match pattern `{pattern}` "
                    f"per value type `{value_type_name}`; got `{text}`."
                )
        # Unknown constraint types are ignored for forward compatibility.


def _validate_action_value_type_changes(object_type: str, changes: dict[str, Any]) -> None:
    """Validate changed properties against their bound Value Type constraints."""
    value_types = _load_value_types()
    if not value_types:
        return
    value_type_map = _property_value_type_map(object_type)
    if not value_type_map:
        return
    for api_name, value in changes.items():
        value_type_name = value_type_map.get(api_name)
        if not value_type_name:
            continue
        value_type_def = value_types.get(value_type_name)
        if not isinstance(value_type_def, dict):
            continue
        _validate_value_against_type(value, value_type_name, value_type_def, f"changes.{api_name}")


def _validate_iso_date_value(value: Any, field_name: str) -> None:
    text = str(value or "").strip()
    if text == "":
        return
    _required_iso_date_value(text, field_name)


def _required_iso_date_value(value: Any, field_name: str) -> date:
    text = str(value or "").strip()
    if text == "":
        raise ValueError(f"{field_name} must be YYYY-MM-DD.")
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{field_name} must be YYYY-MM-DD.") from exc
    if parsed.isoformat() != text:
        raise ValueError(f"{field_name} must be YYYY-MM-DD.")
    return parsed


def _json_safe(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value
