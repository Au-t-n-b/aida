from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import Any

try:  # standalone 服务自带 ontology/.env（DOLT_DATABASE_URL 等）：不依赖启动 shell 注入，
    # 缺它时所有 dolt_rows 读取会静默 degrade 成空表（症状：预案章节全空、riskCount=0）。
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
except Exception:  # pragma: no cover - dotenv optional
    pass

import data_connector
import datasource_bindings
from dataset_service import (
    DatasetConflictError,
    DatasetError,
    DatasetInvalidTransactionError,
    DatasetNotFoundError,
    DatasetNotImplementedError,
    DatasetUnavailableError,
    commit_dataset_transaction,
    create_dataset,
    create_dataset_branch,
    create_dataset_transaction,
    delete_dataset_branch,
    get_dataset_branch,
    list_dataset_branches,
    read_dataset_table,
    sync_object_type_backing_datasets,
    upload_dataset_file,
)
from dolt_schema_sync import (
    DoltSchemaSyncUnavailableError,
    sync_all_object_type_dolt_schemas,
    sync_object_type_dolt_schema,
)
from dolt_mirror import (
    ensure_preview_branch_data_source,
    sync_main_mirror,
    validate_main_mirror,
)
from data_connector import (
    get_backward_key_milestones_graph,
    get_linked_object_data,
    get_object_as_of,
    get_object_data,
    get_object_diff,
    get_object_history,
    update_object_data,
    validate_object_update,
)
from preview_branch import (
    PREVIEW_BRANCH_HEADER,
    PreviewBranchContext,
    PreviewBranchUnavailableError,
    apply_update_milestone_date_batch_to_dolt,
    create_preview_branch,
    discard_preview_branch,
    ensure_preview_branch_available,
    get_current_preview_branch,
    list_preview_branches,
    publish_preview_branch,
    resolve_preview_branch_context,
    use_preview_branch,
    writeback_overlay_enabled,
)

try:
    from fastapi import Request as FastAPIRequest
except ImportError:  # pragma: no cover - create_app 会给出更明确的依赖错误
    FastAPIRequest = Any


BASE_DIR = Path(__file__).parent
SCHEMA_DIR = BASE_DIR / "schema"
OBJECT_TYPES_PATH = SCHEMA_DIR / "object-types.json"
ACTION_TYPES_PATH = SCHEMA_DIR / "action-types.json"
LINK_TYPES_PATH = SCHEMA_DIR / "link-types.json"
DEFAULT_ONTOLOGY = "default"
# The delivery-contingency-plan ontology was merged into `default`: its object/link/value/
# function/action types now live in schema/*.json and its datasource bindings in
# schema/datasource-bindings.yaml. A single runtime ontology remains. (The `_ensure_default_
# runtime_ontology` gate + MetadataOnlyOntologyError machinery below stays as generic support
# for any future metadata-only ontology, but is dormant while `default` is the only ontology.)
ONTOLOGY_SCHEMA_DIRS = {
    DEFAULT_ONTOLOGY: SCHEMA_DIR,
}
ONTOLOGY_DISPLAY_METADATA = {
    DEFAULT_ONTOLOGY: {
        "displayName": "default",
        "description": "Local ontology powered by schema JSON and CSV backing data.",
    },
}
DEPRECATED_WRITEBACK_SKILL_ACTIONS: dict[str, str] = {}
WRITEBACK_QUERY_ACTIONS = {
    "backward-key-milestones": "executeBackwardKeyMilestones",
    "forward-key-milestones": "executeForwardKeyMilestones",
}
READONLY_FIELDS = {"rowKey", "projectKey", "localRowKey", "sourceFile"}
OBJECT_READONLY_FIELDS = {
    "Milestone": {
        "milestoneKey",
        "projectKey",
        "projectName",
        "scopeType",
        "scopeKey",
        "milestoneType",
        "sourceFile",
    },
}


class ObjectTypeNotFoundError(KeyError):
    pass


class ActionTypeNotFoundError(KeyError):
    pass


class OntologyNotFoundError(KeyError):
    pass


class MetadataOnlyOntologyError(RuntimeError):
    pass


def _ensure_ontology(ontology: str) -> str:
    normalized = (ontology or "").strip()
    if normalized in {"", DEFAULT_ONTOLOGY, "_"}:
        return DEFAULT_ONTOLOGY
    if normalized in ONTOLOGY_SCHEMA_DIRS:
        return normalized
    raise OntologyNotFoundError(f"Ontology not found: {ontology}")


def _ensure_default_runtime_ontology(ontology: str) -> str:
    ontology_id = _ensure_ontology(ontology)
    if ontology_id != DEFAULT_ONTOLOGY:
        raise MetadataOnlyOntologyError(
            f"Ontology `{ontology_id}` is metadata-only; runtime object data, skills, queries, preview branches, "
            "Dolt mirror, and action execution are only available for `default`."
        )
    return ontology_id


def _schema_path(ontology: str, filename: str) -> Path:
    ontology_id = _ensure_ontology(ontology)
    return ONTOLOGY_SCHEMA_DIRS[ontology_id] / filename


def _ontology_summary(ontology: str) -> dict[str, Any]:
    ontology_id = _ensure_ontology(ontology)
    display = ONTOLOGY_DISPLAY_METADATA[ontology_id]
    object_types = load_object_types(ontology_id)
    return {
        "apiName": ontology_id,
        "displayName": display["displayName"],
        "description": display["description"],
        "objectTypeCount": len(object_types),
    }


def load_action_types(ontology: str = DEFAULT_ONTOLOGY) -> dict[str, Any]:
    with _schema_path(ontology, "action-types.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_skill_types(ontology: str = DEFAULT_ONTOLOGY) -> dict[str, Any]:
    """Skills now live in the Function registry (function-types.json) tagged with
    kind == "SKILL". This view filters them back out so existing skill callers and
    the /skillTypes endpoint keep working unchanged, while gaining ontology awareness."""
    return {
        api_name: schema
        for api_name, schema in load_function_types(ontology).items()
        if isinstance(schema, dict) and schema.get("kind") == "SKILL"
    }


def load_link_types(ontology: str = DEFAULT_ONTOLOGY) -> dict[str, Any]:
    with _schema_path(ontology, "link-types.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_value_types(ontology: str = DEFAULT_ONTOLOGY) -> dict[str, Any]:
    path = _schema_path(ontology, "value-types.json")
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        value_types = json.load(handle)
    return value_types if isinstance(value_types, dict) else {}


def load_function_types(ontology: str = DEFAULT_ONTOLOGY) -> dict[str, Any]:
    path = _schema_path(ontology, "function-types.json")
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        function_types = json.load(handle)
    return function_types if isinstance(function_types, dict) else {}


def load_interface_types(ontology: str = DEFAULT_ONTOLOGY) -> dict[str, Any]:
    path = _schema_path(ontology, "interface-types.json")
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        interface_types = json.load(handle)
    return interface_types if isinstance(interface_types, dict) else {}


def load_automation_types(ontology: str = DEFAULT_ONTOLOGY) -> dict[str, Any]:
    path = _schema_path(ontology, "automation-types.json")
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        automation_types = json.load(handle)
    return automation_types if isinstance(automation_types, dict) else {}


def list_object_type_summaries(ontology: str = DEFAULT_ONTOLOGY) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for object_type, schema in load_object_types(ontology).items():
        display = schema.get("displayMetadata", {})
        summaries.append(
            {
                "apiName": schema.get("apiName", object_type),
                "displayName": display.get("displayName", object_type),
                "description": display.get("description", schema.get("description", "")),
                "status": schema.get("status", "ACTIVE"),
            }
        )
    return summaries


def _primary_key_field(object_type: str, object_schema: dict[str, Any]) -> str:
    key_candidates = object_schema.get("primaryKeyPropertyApiNames", [])
    if isinstance(key_candidates, list) and key_candidates and isinstance(key_candidates[0], str):
        return key_candidates[0]
    raise ValueError(f"Object type primary key is not configured: {object_type}")


def _paginate_items(items: list[dict[str, Any]], limit: int, offset: int) -> list[dict[str, Any]]:
    start = max(offset, 0)
    end = start + max(limit, 0)
    return items[start:end]


def _matches_filter_value(field_value: Any, condition: Any) -> bool:
    raw_value = "" if field_value is None else str(field_value)
    if isinstance(condition, dict):
        operator = condition.get("op", "eq")
        target = condition.get("value")
        if operator == "eq":
            return raw_value == ("" if target is None else str(target))
        if operator == "contains":
            return str(target or "") in raw_value
        if operator == "in":
            if not isinstance(target, list):
                return False
            values = {"" if item is None else str(item) for item in target}
            return raw_value in values
        raise ValueError(f"Unsupported filter operator: {operator}")
    return raw_value == ("" if condition is None else str(condition))


def _match_filters(item: dict[str, Any], filters: dict[str, Any]) -> bool:
    if not filters:
        return True
    clauses = filters.get("and")
    if clauses is not None:
        if not isinstance(clauses, list):
            raise ValueError("filters.and must be a list.")
        return all(_match_filters(item, clause if isinstance(clause, dict) else {}) for clause in clauses)
    for field, condition in filters.items():
        if field == "and":
            continue
        if not _matches_filter_value(item.get(field), condition):
            return False
    return True


def _normalize_action_types(ontology: str = DEFAULT_ONTOLOGY) -> list[dict[str, Any]]:
    action_types = load_action_types(ontology)
    if isinstance(action_types, dict):
        return list(action_types.values())
    if isinstance(action_types, list):
        return action_types
    raise ValueError("action-types.json must be a JSON object or array.")


def _normalize_skill_types(ontology: str = DEFAULT_ONTOLOGY) -> list[dict[str, Any]]:
    if _ensure_ontology(ontology) != DEFAULT_ONTOLOGY:
        return []
    # Skills are sourced from the Function registry (kind == "SKILL"); load_skill_types
    # always returns a dict keyed by apiName.
    return list(load_skill_types(ontology).values())


def _normalize_link_types(ontology: str = DEFAULT_ONTOLOGY) -> list[dict[str, Any]]:
    link_types = load_link_types(ontology)
    if isinstance(link_types, dict):
        return list(link_types.values())
    if isinstance(link_types, list):
        return link_types
    raise ValueError("link-types.json must be a JSON object or array.")


def _normalize_value_types(ontology: str = DEFAULT_ONTOLOGY) -> list[dict[str, Any]]:
    value_types = load_value_types(ontology)
    if isinstance(value_types, dict):
        return list(value_types.values())
    if isinstance(value_types, list):
        return value_types
    raise ValueError("value-types.json must be a JSON object or array.")


def _normalize_function_types(ontology: str = DEFAULT_ONTOLOGY) -> list[dict[str, Any]]:
    # Each ontology publishes its own declared Functions; ontologies without a
    # function-types.json load as {} → []. Non-default ontologies may declare read-only
    # derived Functions (e.g. delivery-contingency-plan's deriveContingencyRisks).
    function_types = load_function_types(_ensure_ontology(ontology))
    if isinstance(function_types, dict):
        values: list[dict[str, Any]] = list(function_types.values())
    elif isinstance(function_types, list):
        values = function_types
    else:
        raise ValueError("function-types.json must be a JSON object or array.")
    # Skills share this registry (kind == "SKILL") but are published via /skillTypes,
    # not the Function/Query surfaces.
    return [item for item in values if not (isinstance(item, dict) and item.get("kind") == "SKILL")]


def _normalize_interface_types(ontology: str = DEFAULT_ONTOLOGY) -> list[dict[str, Any]]:
    interface_types = load_interface_types(ontology)
    if isinstance(interface_types, dict):
        return list(interface_types.values())
    if isinstance(interface_types, list):
        return interface_types
    raise ValueError("interface-types.json must be a JSON object or array.")


def object_types_implementing_interface(
    interface_api_name: str,
    ontology: str = DEFAULT_ONTOLOGY,
    *,
    object_types: dict[str, Any] | None = None,
) -> list[str]:
    """Polymorphic lookup: object types that declare they implement an interface."""
    object_types = object_types if object_types is not None else load_object_types(ontology)
    return sorted(
        name
        for name, schema in object_types.items()
        if interface_api_name in (schema.get("implementsInterfaces") or [])
    )


def interface_conformance_violations(
    ontology: str = DEFAULT_ONTOLOGY,
    *,
    object_types: dict[str, Any] | None = None,
    interface_types: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Check every implementer actually carries each interface's required properties."""
    object_types = object_types if object_types is not None else load_object_types(ontology)
    interface_types = interface_types if interface_types is not None else load_interface_types(ontology)
    violations: list[dict[str, Any]] = []
    for object_name, object_schema in object_types.items():
        implemented = object_schema.get("implementsInterfaces") or []
        property_names = set((object_schema.get("properties") or {}).keys())
        for interface_name in implemented:
            interface = interface_types.get(interface_name)
            if not isinstance(interface, dict):
                violations.append(
                    {"objectType": object_name, "interface": interface_name, "reason": "unknown interface"}
                )
                continue
            for required_property in interface.get("properties") or {}:
                if required_property not in property_names:
                    violations.append(
                        {
                            "objectType": object_name,
                            "interface": interface_name,
                            "missingProperty": required_property,
                        }
                    )
    return violations


def _normalize_automation_types(ontology: str = DEFAULT_ONTOLOGY) -> list[dict[str, Any]]:
    if _ensure_ontology(ontology) != DEFAULT_ONTOLOGY:
        return []
    automation_types = load_automation_types(ontology)
    if isinstance(automation_types, dict):
        return list(automation_types.values())
    if isinstance(automation_types, list):
        return automation_types
    raise ValueError("automation-types.json must be a JSON object or array.")


def _payload_project_id(payload: dict[str, Any]) -> str:
    project_id = str(payload.get("project_id") or payload.get("projectId") or "").strip()
    if not project_id:
        raise ValueError("payload.project_id is required.")
    return project_id


def _payload_anchor_id(payload: dict[str, Any]) -> str | None:
    anchor_id_raw = payload.get("anchor_id")
    if anchor_id_raw is None:
        anchor_id_raw = payload.get("anchorId")
    anchor_id = str(anchor_id_raw).strip() if anchor_id_raw is not None else None
    if anchor_id == "":
        return None
    return anchor_id


def _action_only_writeback_detail(action_name: str) -> str:
    return (
        "CSV writeback is action-only. Use "
        f"/api/v2/ontologies/default/actions/{action_name}/apply."
    )


def _milestone_action_exclusive_detail(action_name: str, skill_name: str) -> str:
    return (
        f"Action Exclusive: {action_name} is dry-run only. "
        "Run the Skill to collect proposed_mutations, then call the OSDK Batch Action "
        f"UpdateMilestoneDate.batchApply for physical writeback. Skill: {skill_name}."
    )


def execute_local_python_handler(
    handler_schema: dict[str, Any], payload: dict[str, Any], *, write: bool = True
) -> dict[str, Any]:
    module_name = str(handler_schema.get("module", "")).strip()
    function_name = str(handler_schema.get("function", "")).strip()
    if not module_name or not function_name:
        raise ValueError("Local action handler is missing module/function.")

    module = importlib.import_module(module_name)
    func = getattr(module, function_name)
    if module_name == "data_connector" and function_name == "apply_backward_key_milestones_action":
        return func(project_id=_payload_project_id(payload), selected_anchor_id=_payload_anchor_id(payload))
    if module_name == "data_connector" and function_name == "apply_forward_key_milestones_action":
        return func(project_id=_payload_project_id(payload))
    if module_name == "data_connector" and function_name == "publish_contingency_findings_action":
        return func(payload, write=write)

    raise ValueError(f"Unsupported local action handler: {module_name}.{function_name}")


def execute_local_skill(skill_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    skill_types = load_skill_types()
    skill_schema = skill_types.get(skill_name)
    if skill_schema is None:
        raise KeyError(f"Skill not found: {skill_name}")

    binding = skill_schema.get("binding", {})
    module_name = str(binding.get("module", "")).strip()
    function_name = str(binding.get("function", "")).strip()
    if not module_name or not function_name:
        raise ValueError(f"Skill `{skill_name}` is missing a callable binding.")

    if module_name == "data_connector":
        module = importlib.import_module(module_name)
        func = getattr(module, function_name)
        return func(**payload)

    raise ValueError(f"Unsupported local skill binding: {module_name}.{function_name}")


def execute_function_type(
    function_name: str, payload: dict[str, Any], ontology: str = DEFAULT_ONTOLOGY
) -> Any:
    """Execute a registered ontology Function by apiName via its declared binding.

    Generic and declaration-driven: kwargs are built from the Function's declared
    parameters, so adding a Function to function-types.json (with a data_connector
    binding) makes it callable here without any router change. Ontology-aware so read-only
    derived Functions declared on non-default ontologies (e.g. delivery-contingency-plan's
    deriveContingencyRisks) resolve against their own registry.
    """
    function_schema = load_function_types(_ensure_ontology(ontology)).get(function_name)
    if function_schema is None:
        raise KeyError(f"Function not found: {function_name}")
    if isinstance(function_schema, dict) and function_schema.get("kind") == "SKILL":
        raise ValueError(
            f"`{function_name}` is a Skill, not a Function; execute it via "
            f"/api/v2/ontologies/<ontology>/skills/{function_name}/execute."
        )

    binding = function_schema.get("binding", {})
    module_name = str(binding.get("module", "")).strip()
    function_attr = str(binding.get("function", "")).strip()
    if not module_name or not function_attr:
        raise ValueError(f"Function `{function_name}` is missing a callable binding.")
    if module_name != "data_connector":
        raise ValueError(f"Unsupported local function binding: {module_name}.{function_attr}")

    kwargs: dict[str, Any] = {}
    for param_name, param_schema in (function_schema.get("parameters") or {}).items():
        raw_value = payload.get(param_name)
        if raw_value is None or (isinstance(raw_value, str) and raw_value.strip() == ""):
            if isinstance(param_schema, dict) and param_schema.get("required"):
                raise ValueError(f"Function `{function_name}` requires parameter `{param_name}`.")
            continue
        kwargs[param_name] = raw_value

    module = importlib.import_module(module_name)
    func = getattr(module, function_attr, None)
    if not callable(func):
        raise ValueError(f"Function binding `{module_name}.{function_attr}` is not callable.")
    return func(**kwargs)


def _run_record_create_target(action_schema: Any) -> str:
    """Object type a `writeback: run_record` CREATE_OBJECT Action materializes, or "" when the
    Action is not an eligible run-record create.

    Run-record routing is driven by Action metadata — a CREATE_OBJECT edit + `writeback:
    run_record` + a writable target ObjectType — NOT by which ontology id the request names.
    (After the contingency ontology was merged into `default`, this is what tells a run-record
    create like AdoptDerivedRisk → RiskItem apart from a plan CSV/Dolt writeback.)
    """
    if not isinstance(action_schema, dict):
        return ""
    if str(action_schema.get("writeback") or "") != "run_record":
        return ""
    create_edit = next(
        (
            edit
            for edit in action_schema.get("edits", [])
            if isinstance(edit, dict) and edit.get("type") == "CREATE_OBJECT"
        ),
        None,
    )
    if create_edit is None:
        return ""
    object_type = str(
        create_edit.get("objectTypeApiName")
        or action_schema.get("targetObjectTypeApiName")
        or ""
    ).strip()
    if not object_type or not datasource_bindings.resolve_object_type_writable(object_type):
        return ""
    return object_type


def _apply_runrecord_create_action(
    action_name: str, action_schema: dict[str, Any], payload: dict[str, Any], *, write: bool
) -> dict[str, Any]:
    """Apply (or validate) a `writeback: run_record` CREATE_OBJECT Action, persisting the new
    object to the run-record overlay via the data layer. Eligibility/routing is decided by
    `_run_record_create_target` from Action metadata, independent of ontology id.
    """
    return data_connector.create_contingency_object(action_name, action_schema, payload, write=write)


def _run_record_modify_target(action_schema: Any) -> str:
    """Object type a `writeback: run_record` MODIFY_OBJECT Action edits, or "" when the Action
    is not an eligible run-record modify.

    Counterpart of `_run_record_create_target` for the modify half of the run-record lifecycle:
    run-record objects live in the overlay (not Dolt/CSV), so their MODIFY Actions (e.g.
    UpdateRiskStatus on an adopted RiskItem, ApproveContingencyPlan on a created plan) must
    route to the overlay engine instead of the Dolt/CSV writeback paths, which cannot see
    overlay rows.
    """
    if not isinstance(action_schema, dict):
        return ""
    if str(action_schema.get("writeback") or "") != "run_record":
        return ""
    modify_edit = next(
        (
            edit
            for edit in action_schema.get("edits", [])
            if isinstance(edit, dict) and edit.get("type") == "MODIFY_OBJECT"
        ),
        None,
    )
    if modify_edit is None:
        return ""
    object_type = str(action_schema.get("targetObjectTypeApiName") or "").strip()
    if not object_type or not datasource_bindings.resolve_object_type_writable(object_type):
        return ""
    return object_type


def _apply_runrecord_modify_action(
    action_name: str, action_schema: dict[str, Any], payload: dict[str, Any], *, write: bool
) -> dict[str, Any]:
    """Apply (or validate) a `writeback: run_record` MODIFY_OBJECT Action against the overlay."""
    return data_connector.modify_contingency_object(action_name, action_schema, payload, write=write)


def apply_action_type(
    action_name: str, payload: dict[str, Any], ontology: str = DEFAULT_ONTOLOGY
) -> dict[str, Any]:
    action_schema = load_action_types(_ensure_ontology(ontology)).get(action_name)
    if action_schema is None:
        raise KeyError(f"Action not found: {action_name}")
    if _run_record_create_target(action_schema):
        return _apply_runrecord_create_action(action_name, action_schema, payload, write=True)
    if _run_record_modify_target(action_schema):
        return _apply_runrecord_modify_action(action_name, action_schema, payload, write=True)

    if action_name == "modifyPodPowerOnMilestoneAnchorDate":
        return apply_pod_power_on_milestone_anchor_date(payload)

    side_effects = action_schema.get("sideEffects", {})
    if side_effects.get("type") == "DRY_RUN_ONLY":
        skill_name = str(side_effects.get("skillApiName", "")).strip()
        raise ValueError(_milestone_action_exclusive_detail(action_name, skill_name))

    if side_effects.get("type") == "LOCAL_PYTHON":
        return execute_local_python_handler(side_effects, payload, write=True)

    if side_effects.get("type") == "LOCAL_SKILL":
        skill_name = str(side_effects.get("skillApiName", "")).strip()
        if not skill_name:
            raise ValueError(f"Action `{action_name}` is missing sideEffects.skillApiName.")
        raise ValueError(
            f"Action `{action_name}` must use LOCAL_PYTHON for CSV writeback; LOCAL_SKILL is not executable."
        )

    object_type = str(action_schema.get("targetObjectTypeApiName", "")).strip()
    if object_type:
        enriched_payload = dict(payload)
        enriched_payload.setdefault("object_type", object_type)
        return update_object_data(object_type, action_name, enriched_payload)

    raise ValueError(f"Action `{action_name}` is not executable.")


def validate_action_type(
    action_name: str, payload: dict[str, Any], ontology: str = DEFAULT_ONTOLOGY
) -> dict[str, Any]:
    action_schema = load_action_types(_ensure_ontology(ontology)).get(action_name)
    if action_schema is None:
        raise KeyError(f"Action not found: {action_name}")
    if _run_record_create_target(action_schema):
        return _apply_runrecord_create_action(action_name, action_schema, payload, write=False)
    if _run_record_modify_target(action_schema):
        return _apply_runrecord_modify_action(action_name, action_schema, payload, write=False)

    side_effects = action_schema.get("sideEffects", {})
    if side_effects.get("type") == "DRY_RUN_ONLY":
        skill_name = str(side_effects.get("skillApiName", "")).strip()
        raise ValueError(_milestone_action_exclusive_detail(action_name, skill_name))

    if side_effects.get("type") == "LOCAL_PYTHON":
        return execute_local_python_handler(side_effects, payload, write=False)

    object_type = str(action_schema.get("targetObjectTypeApiName", "")).strip()
    if not object_type:
        raise ValueError(f"Action `{action_name}` has no target object type.")
    enriched_payload = dict(payload)
    enriched_payload.setdefault("object_type", object_type)
    return validate_object_update(object_type, action_name, enriched_payload)


def _normalize_update_milestone_date_batch(
    payload: dict[str, Any] | list[Any],
) -> tuple[list[dict[str, Any]], str | None]:
    if isinstance(payload, list):
        batch = payload
        project_id = None
    elif isinstance(payload, dict):
        raw_batch = payload.get("batch")
        if not isinstance(raw_batch, list):
            raise ValueError("payload.batch must be a list.")
        batch = raw_batch
        project_id = str(payload.get("project_id") or payload.get("projectId") or "").strip() or None
    else:
        raise ValueError("payload must be an object with batch list.")

    normalized_items: list[dict[str, Any]] = []
    for index, item in enumerate(batch):
        if not isinstance(item, dict):
            raise ValueError(f"payload.batch[{index}] must be an object.")
        row_key = str(item.get("milestoneId") or item.get("rowKey") or "").strip()
        if not row_key:
            raise ValueError(f"payload.batch[{index}].milestoneId is required.")
        date_field = str(item.get("dateField") or item.get("field") or "").strip()
        if date_field not in {"startDate", "endDate"}:
            raise ValueError(f"payload.batch[{index}].dateField must be startDate or endDate.")
        new_date = item.get("newDate")
        if new_date is None:
            raise ValueError(f"payload.batch[{index}].newDate is required.")
        data_connector._validate_iso_date_value(new_date, f"payload.batch[{index}].newDate")
        normalized_items.append(
            {
                "milestoneId": row_key,
                "rowKey": row_key,
                "dateField": date_field,
                "newDate": str(new_date),
                "reason": str(item.get("reason") or ""),
            }
        )

    return normalized_items, project_id


def _group_update_milestone_date_items(
    normalized_items: list[dict[str, Any]],
    project_id: str | None,
) -> dict[Path, dict[str, Any]]:
    grouped_payloads: dict[Path, dict[str, Any]] = {}
    for item in normalized_items:
        source = data_connector._source_for_object_key(
            data_connector.DELIVERY_PLAN_ROW_OBJECT_TYPE,
            item["rowKey"],
            project_id,
        )
        csv_path = source.path
        group = grouped_payloads.setdefault(
            csv_path,
            {"project_id": source.project_id, "project_key": source.project_key, "file_name": source.file_name, "items": []},
        )
        group["items"].append(item)
    return grouped_payloads


def _resolve_update_milestone_date_groups(
    grouped_payloads: dict[Path, dict[str, Any]],
    source_columns: dict[str, str],
) -> dict[Path, dict[str, Any]]:
    row_key_column = source_columns.get("rowKey")
    resolved_groups: dict[Path, dict[str, Any]] = {}
    for csv_path, group in grouped_payloads.items():
        csv_rows, fieldnames = data_connector._read_csv(csv_path)
        row_index_by_key: dict[str, int] = {}
        if row_key_column:
            for row_index, row in enumerate(csv_rows):
                row_index_by_key[str(row.get(row_key_column, ""))] = row_index
        else:
            source = data_connector.ProjectSource(
                str(group["project_id"]),
                str(group["file_name"]),
                str(group["project_key"]),
            )
            ontology = data_connector._load_ontology(source)
            for item in group["items"]:
                row_key = item["rowKey"]
                if row_key in row_index_by_key:
                    continue
                target = ontology.objects.DeliveryPlanRow.get_or_none(row_key)
                if target is not None:
                    row_index_by_key[row_key] = target.activity.row_order

        for item in group["items"]:
            row_key = item["rowKey"]
            row_index = row_index_by_key.get(row_key)
            if row_index is None:
                raise KeyError(f"DeliveryPlanRow rowKey not found: {row_key}")
        resolved_groups[csv_path] = {
            **group,
            "csv_rows": csv_rows,
            "fieldnames": fieldnames,
            "row_index_by_key": row_index_by_key,
        }

    return resolved_groups


def _validate_update_milestone_date_batch(payload: dict[str, Any] | list[Any]) -> tuple[list[dict[str, Any]], str | None]:
    normalized_items, project_id = _normalize_update_milestone_date_batch(payload)
    preview_context = get_current_preview_branch()
    if not preview_context.is_main:
        ensure_preview_branch_available(preview_context)
        return normalized_items, project_id
    source_columns = data_connector._api_to_source_columns(data_connector.DELIVERY_PLAN_ROW_OBJECT_TYPE)
    grouped_payloads = _group_update_milestone_date_items(normalized_items, project_id)
    _resolve_update_milestone_date_groups(grouped_payloads, source_columns)
    return normalized_items, project_id


def apply_update_milestone_date_batch(payload: dict[str, Any] | list[Any]) -> dict[str, Any]:
    # This route is the local stand-in for Palantir OSDK batchApply. It is allowed
    # to write because the caller has already approved a dry-run diff.
    normalized_items, project_id = _normalize_update_milestone_date_batch(payload)
    preview_context = get_current_preview_branch()
    # Preview branches always write to Dolt; on main, route writes to Dolt too when
    # the writeback overlay is enabled (edits live on main, pipeline merges via ingest).
    if not preview_context.is_main or writeback_overlay_enabled():
        project_key = data_connector._select_sources(project_id)[0].project_key if project_id else None
        return apply_update_milestone_date_batch_to_dolt(
            preview_context,
            normalized_items,
            project_key=project_key,
        )
    source_columns = data_connector._api_to_source_columns(data_connector.DELIVERY_PLAN_ROW_OBJECT_TYPE)
    grouped_payloads = _group_update_milestone_date_items(normalized_items, project_id)
    resolved_groups = _resolve_update_milestone_date_groups(grouped_payloads, source_columns)

    for csv_path, group in resolved_groups.items():
        csv_rows = group["csv_rows"]
        fieldnames = group["fieldnames"]
        row_index_by_key = group["row_index_by_key"]
        for item in group["items"]:
            row_key = item["rowKey"]
            row_index = row_index_by_key[row_key]
            csv_rows[row_index][source_columns[item["dateField"]]] = item["newDate"]

        data_connector._write_csv(csv_path, fieldnames, csv_rows)

    refreshed_by_project: dict[str, dict[str, dict[str, Any]]] = {}
    for group in grouped_payloads.values():
        source_project_id = str(group["project_id"])
        if source_project_id in refreshed_by_project:
            continue
        refreshed_rows = get_object_data("DeliveryPlanRow", source_project_id)
        refreshed_by_project[source_project_id] = {
            str(row.get("rowKey") or ""): row for row in refreshed_rows if str(row.get("rowKey") or "")
        }

    results: list[dict[str, Any]] = []
    for item in normalized_items:
        source = data_connector._source_for_object_key(
            data_connector.DELIVERY_PLAN_ROW_OBJECT_TYPE,
            item["rowKey"],
            project_id,
        )
        refreshed_row = refreshed_by_project.get(source.project_id, {}).get(item["rowKey"], {})
        results.append({**item, "data": refreshed_row})

    return {
        "success": True,
        "actionName": "UpdateMilestoneDate",
        "appliedCount": len(results),
        "results": results,
    }


def _extract_batch(payload: dict[str, Any] | list[Any]) -> tuple[list[Any], str | None]:
    if isinstance(payload, list):
        return payload, None
    if isinstance(payload, dict):
        raw_batch = payload.get("batch")
        if not isinstance(raw_batch, list):
            raise ValueError("payload.batch must be a list.")
        project_id = str(payload.get("project_id") or payload.get("projectId") or "").strip() or None
        return raw_batch, project_id
    raise ValueError("payload must be an object with batch list.")


POD_POWER_WRITEBACK_ANCHOR_AND_BACKWARD_SCHEDULE = "ANCHOR_AND_BACKWARD_SCHEDULE"
POD_POWER_WRITEBACK_ANCHOR_ONLY = "ANCHOR_ONLY"


def _pod_power_on_writeback_mode(payload: dict[str, Any] | list[Any]) -> str:
    if not isinstance(payload, dict):
        return POD_POWER_WRITEBACK_ANCHOR_AND_BACKWARD_SCHEDULE
    raw_mode = payload.get("writebackMode")
    if raw_mode is None:
        raw_mode = payload.get("writeback_mode")
    mode = str(raw_mode or POD_POWER_WRITEBACK_ANCHOR_AND_BACKWARD_SCHEDULE).strip().upper()
    allowed = {
        POD_POWER_WRITEBACK_ANCHOR_AND_BACKWARD_SCHEDULE,
        POD_POWER_WRITEBACK_ANCHOR_ONLY,
    }
    if mode not in allowed:
        raise ValueError(
            "payload.writebackMode must be ANCHOR_AND_BACKWARD_SCHEDULE or ANCHOR_ONLY."
        )
    return mode


def _normalize_pod_power_on_batch_item(item: Any, default_project_id: str | None, index: int) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError(f"payload.batch[{index}] must be an object.")
    payload = dict(item)
    project_id = str(payload.pop("projectId", "") or payload.get("project_id") or default_project_id or "").strip()
    if project_id:
        payload["project_id"] = project_id

    milestone_key = str(
        payload.get("milestoneKey")
        or payload.get("milestoneId")
        or payload.get("rowKey")
        or payload.get("row_key")
        or ""
    ).strip()
    if milestone_key and not payload.get("targetPodPowerOnMilestone"):
        payload["targetPodPowerOnMilestone"] = {"milestoneKey": milestone_key}
    if not payload.get("targetPodPowerOnMilestone"):
        raise ValueError(f"payload.batch[{index}].targetPodPowerOnMilestone is required.")
    if "anchorDate" not in payload:
        raise ValueError(f"payload.batch[{index}].anchorDate is required.")
    return payload


def _pod_power_on_milestone_key(item: dict[str, Any]) -> str:
    target = item.get("targetPodPowerOnMilestone")
    if isinstance(target, dict):
        return str(target.get("milestoneKey") or target.get("rowKey") or target.get("id") or "").strip()
    return str(target or item.get("milestoneKey") or item.get("rowKey") or "").strip()


def _project_id_from_pod_power_on_items(normalized_items: list[dict[str, Any]]) -> str:
    project_ids: set[str] = set()
    for item in normalized_items:
        project_id = str(item.get("project_id") or "").strip()
        if not project_id:
            project_id = data_connector._project_id_from_milestone_key(_pod_power_on_milestone_key(item))
        if project_id:
            project_ids.add(project_id)
    if not project_ids:
        raise ValueError("payload.batch must include at least one project_id or milestoneKey.")
    if len(project_ids) > 1:
        raise ValueError("payload.batch must contain Pod power-on milestones from a single project.")
    return next(iter(project_ids))


def _project_power_on_anchor_id(project_id: str) -> str:
    graph = get_backward_key_milestones_graph(project_id=project_id)
    for option in graph.get("anchorOptions") or []:
        if str(option.get("milestoneType") or "").strip() == "POWER_ON":
            anchor_id = str(option.get("id") or "").strip()
            if anchor_id:
                return anchor_id
    raise ValueError(f"No project-level POWER_ON backward anchor found for project_id `{project_id}`.")


def _temporary_anchor_dates_from_pod_power_on_items(normalized_items: list[dict[str, Any]]) -> dict[str, str]:
    temporary_dates: dict[str, str] = {}
    for item in normalized_items:
        milestone_key = _pod_power_on_milestone_key(item)
        anchor_date = str(item.get("anchorDate") or "").strip()
        if milestone_key and anchor_date:
            temporary_dates[milestone_key] = anchor_date
    return temporary_dates


def _execute_pod_power_on_batch_backward_dry_run(normalized_items: list[dict[str, Any]]) -> dict[str, Any]:
    project_id = _project_id_from_pod_power_on_items(normalized_items)
    return data_connector.execute_backward_key_milestones(
        project_id,
        selected_anchor_id=_project_power_on_anchor_id(project_id),
        temporary_anchor_dates=_temporary_anchor_dates_from_pod_power_on_items(normalized_items),
    )


def _merge_pod_power_on_backward_dry_runs(
    normalized_items: list[dict[str, Any]],
    validation_results: list[dict[str, Any]],
) -> dict[str, Any]:
    first_dry_run = next((result.get("backwardDryRun") for result in validation_results if result.get("backwardDryRun")), None)
    mutation_by_key: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for result in validation_results:
        dry_run = result.get("backwardDryRun")
        if not isinstance(dry_run, dict):
            continue
        for mutation in dry_run.get("proposed_mutations") or []:
            if not isinstance(mutation, dict):
                continue
            row_key = str(mutation.get("rowKey") or mutation.get("milestoneId") or "").strip()
            field = str(mutation.get("field") or "").strip()
            if not row_key or not field:
                continue
            mutation_by_key[f"{row_key}:{field}"] = dict(mutation)
        for warning in dry_run.get("warnings") or []:
            if warning:
                warnings.append(str(warning))

    proposed_mutations = list(mutation_by_key.values())
    affected_rows = {
        str(mutation.get("rowKey") or mutation.get("milestoneId") or "").strip()
        for mutation in proposed_mutations
        if str(mutation.get("rowKey") or mutation.get("milestoneId") or "").strip()
    }
    first_summary = first_dry_run.get("summary", {}) if isinstance(first_dry_run, dict) else {}
    summary = {
        "projectId": first_summary.get("projectId") or normalized_items[0].get("project_id", "") if normalized_items else "",
        "selectedAnchorId": first_summary.get("selectedAnchorId") or _pod_power_on_milestone_key(normalized_items[0]) if normalized_items else "",
        "anchorDate": first_summary.get("anchorDate") or str(normalized_items[0].get("anchorDate") or "") if normalized_items else "",
        "affectedNodeCount": len(affected_rows),
        "mutationCount": len(proposed_mutations),
        "warningCount": len(warnings),
    }
    merged = {
        "status": "DRY_RUN_READY",
        "projectId": summary["projectId"],
        "selectedAnchorId": summary["selectedAnchorId"],
        "anchorDate": summary["anchorDate"],
        "summary": summary,
        "proposed_mutations": proposed_mutations,
        "warnings": warnings,
    }
    if isinstance(first_dry_run, dict) and "anchorOptions" in first_dry_run:
        merged["anchorOptions"] = first_dry_run["anchorOptions"]
    return merged


def _schedule_payload_from_backward_dry_run(backward_dry_run: dict[str, Any]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for mutation in backward_dry_run.get("proposed_mutations") or []:
        if not isinstance(mutation, dict):
            continue
        row_key = str(mutation.get("rowKey") or mutation.get("milestoneId") or "").strip()
        field = str(mutation.get("field") or "").strip()
        new_date = mutation.get("newDate")
        if not row_key or field not in {"startDate", "endDate"} or new_date is None:
            continue
        payload.append(
            {
                "milestoneId": row_key,
                "rowKey": row_key,
                "dateField": field,
                "newDate": str(new_date),
                "reason": str(mutation.get("reason") or ""),
            }
        )
    return payload


def _empty_update_milestone_date_batch_result() -> dict[str, Any]:
    return {
        "success": True,
        "actionName": "UpdateMilestoneDate",
        "appliedCount": 0,
        "results": [],
    }


def _apply_pod_power_on_milestone_anchor_date_only(item: dict[str, Any]) -> dict[str, Any]:
    payload = dict(item)
    payload.setdefault("object_type", data_connector.MILESTONE_OBJECT_TYPE)
    return update_object_data(
        data_connector.MILESTONE_OBJECT_TYPE,
        "modifyPodPowerOnMilestoneAnchorDate",
        payload,
    )


def _validate_pod_power_on_milestone_anchor_date_items(
    normalized_items: list[dict[str, Any]],
    *,
    writeback_mode: str = POD_POWER_WRITEBACK_ANCHOR_AND_BACKWARD_SCHEDULE,
) -> dict[str, Any]:
    action_name = "modifyPodPowerOnMilestoneAnchorDate"
    validation_results = [validate_action_type(action_name, item) for item in normalized_items]
    backward_dry_run: dict[str, Any] | None = None
    schedule_payload: list[dict[str, Any]] = []
    if writeback_mode != POD_POWER_WRITEBACK_ANCHOR_ONLY:
        backward_dry_run = _execute_pod_power_on_batch_backward_dry_run(normalized_items)
        schedule_payload = _schedule_payload_from_backward_dry_run(backward_dry_run)
        schedule_batch: dict[str, Any] = {"batch": schedule_payload}
        project_id = str(backward_dry_run.get("summary", {}).get("projectId") or "").strip()
        if project_id:
            schedule_batch["project_id"] = project_id

        if schedule_payload:
            _validate_update_milestone_date_batch(schedule_batch)

    return {
        "success": True,
        "actionName": action_name,
        "writebackMode": writeback_mode,
        "validatedCount": len(validation_results),
        "results": validation_results,
        "backwardDryRun": backward_dry_run,
        "scheduleMutationCount": len(schedule_payload),
    }


def _apply_pod_power_on_milestone_anchor_date_items(
    normalized_items: list[dict[str, Any]],
    *,
    writeback_mode: str = POD_POWER_WRITEBACK_ANCHOR_AND_BACKWARD_SCHEDULE,
) -> dict[str, Any]:
    action_name = "modifyPodPowerOnMilestoneAnchorDate"
    validation_result = _validate_pod_power_on_milestone_anchor_date_items(
        normalized_items,
        writeback_mode=writeback_mode,
    )
    backward_dry_run = validation_result["backwardDryRun"]
    if writeback_mode == POD_POWER_WRITEBACK_ANCHOR_ONLY:
        schedule_payload = []
        schedule_apply_result = _empty_update_milestone_date_batch_result()
    else:
        schedule_payload = _schedule_payload_from_backward_dry_run(backward_dry_run)
        schedule_batch: dict[str, Any] = {"batch": schedule_payload}
        project_id = str(backward_dry_run.get("summary", {}).get("projectId") or "").strip()
        if project_id:
            schedule_batch["project_id"] = project_id

        if schedule_payload:
            schedule_apply_result = apply_update_milestone_date_batch(schedule_batch)
        else:
            schedule_apply_result = _empty_update_milestone_date_batch_result()

    results = [_apply_pod_power_on_milestone_anchor_date_only(item) for item in normalized_items]
    return {
        "success": True,
        "actionName": action_name,
        "writebackMode": writeback_mode,
        "appliedCount": len(results),
        "results": results,
        "backwardDryRun": backward_dry_run,
        "scheduleMutationCount": len(schedule_payload),
        "scheduleApplyResult": schedule_apply_result,
    }


def apply_pod_power_on_milestone_anchor_date(payload: dict[str, Any]) -> dict[str, Any]:
    normalized_item = _normalize_pod_power_on_batch_item(payload, None, 0)
    batch_result = _apply_pod_power_on_milestone_anchor_date_items(
        [normalized_item],
        writeback_mode=_pod_power_on_writeback_mode(payload),
    )
    result = dict(batch_result["results"][0])
    result["backwardDryRun"] = batch_result["backwardDryRun"]
    result["scheduleMutationCount"] = batch_result["scheduleMutationCount"]
    result["scheduleApplyResult"] = batch_result["scheduleApplyResult"]
    result["writebackMode"] = batch_result["writebackMode"]
    return result


def apply_pod_power_on_milestone_anchor_date_batch(payload: dict[str, Any] | list[Any]) -> dict[str, Any]:
    batch, project_id = _extract_batch(payload)
    normalized_items = [
        _normalize_pod_power_on_batch_item(item, project_id, index)
        for index, item in enumerate(batch)
    ]
    return _apply_pod_power_on_milestone_anchor_date_items(
        normalized_items,
        writeback_mode=_pod_power_on_writeback_mode(payload),
    )


def validate_pod_power_on_milestone_anchor_date_batch(payload: dict[str, Any] | list[Any]) -> dict[str, Any]:
    batch, project_id = _extract_batch(payload)
    normalized_items = [
        _normalize_pod_power_on_batch_item(item, project_id, index)
        for index, item in enumerate(batch)
    ]
    return _validate_pod_power_on_milestone_anchor_date_items(
        normalized_items,
        writeback_mode=_pod_power_on_writeback_mode(payload),
    )


def build_object_meta(object_type: str) -> dict[str, Any]:
    object_types = load_object_types()
    object_type_schema = object_types.get(object_type)
    if object_type_schema is None:
        raise ObjectTypeNotFoundError(f"Object type not found: {object_type}")

    return {
        "objectType": object_type,
        "dataSchema": build_data_schema(object_type_schema),
        "uiSchema": build_ui_schema(object_type, object_type_schema),
        "rawObjectType": object_type_schema,
    }


def load_object_types(ontology: str = DEFAULT_ONTOLOGY) -> dict[str, Any]:
    with _schema_path(ontology, "object-types.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_data_schema(object_type_schema: dict[str, Any]) -> dict[str, Any]:
    display = object_type_schema.get("displayMetadata", {})
    data_schema: dict[str, Any] = {
        "title": display.get("displayName", object_type_schema.get("apiName", "")),
        "description": display.get("description", object_type_schema.get("description", "")),
        "type": "object",
        "properties": {},
    }

    required: list[str] = []
    for fallback_name, property_schema in object_type_schema.get("properties", {}).items():
        api_name = property_schema.get("apiName", fallback_name)
        data_schema["properties"][api_name] = build_property_schema(property_schema)
        if property_schema.get("required") is True:
            required.append(api_name)

    if required:
        data_schema["required"] = required
    return data_schema


def build_property_schema(property_schema: dict[str, Any]) -> dict[str, Any]:
    display = property_schema.get("displayMetadata", {})
    schema = {
        "type": to_json_schema_type(property_schema.get("dataType", {}).get("type")),
        "title": display.get("displayName", property_schema.get("apiName", "")),
    }
    description = display.get("description")
    if description:
        schema["description"] = description
    return schema


def to_json_schema_type(data_type: str | None) -> str:
    return {
        "string": "string",
        "integer": "integer",
        "long": "integer",
        "double": "number",
        "float": "number",
        "decimal": "number",
        "boolean": "boolean",
    }.get(data_type or "", "string")


def build_ui_schema(object_type: str, object_type_schema: dict[str, Any]) -> dict[str, Any]:
    ui_schema: dict[str, Any] = {}
    readonly_fields = READONLY_FIELDS | OBJECT_READONLY_FIELDS.get(object_type, set())
    for fallback_name, property_schema in object_type_schema.get("properties", {}).items():
        api_name = property_schema.get("apiName", fallback_name)
        if api_name in readonly_fields:
            ui_schema[api_name] = {"ui:readonly": True}

    if object_type == "DeliveryPlanRow":
        ui_schema["ui:gantt"] = {
            "idField": "rowKey",
            "nameField": "activityName",
            "startField": "startDate",
            "endField": "endDate",
            "dependencyField": "dependencyActivities",
            "groupField": "managementUnit",
        }
    elif object_type == "Milestone":
        ui_schema["ui:gantt"] = {
            "idField": "milestoneKey",
            "nameField": "milestoneName",
            "startField": "plannedDate",
            "endField": "plannedDate",
            "dependencyField": "dependencyMilestoneTypes",
            "groupField": "scopeKey",
        }
    return ui_schema


def create_app():
    try:
        from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import JSONResponse, StreamingResponse
    except ImportError as exc:
        raise RuntimeError("fastapi is required to create the backend app.") from exc

    app = FastAPI(title="Schema-Driven UI Backend", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def preview_branch_context_middleware(request, call_next):
        try:
            context = resolve_preview_branch_context(request.headers.get(PREVIEW_BRANCH_HEADER))
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"detail": str(exc)})
        if not context.is_main:
            try:
                ensure_preview_branch_data_source(context)
            except PreviewBranchUnavailableError as exc:
                return JSONResponse(status_code=503, content={"detail": str(exc)})
        with use_preview_branch(context):
            return await call_next(request)

    def _require_object_type_schema(ontology: str, object_type: str) -> dict[str, Any]:
        object_schema = load_object_types(ontology).get(object_type)
        if object_schema is None:
            raise ObjectTypeNotFoundError(f"Object type not found: {object_type}")
        return object_schema

    def _require_action_type_schema(ontology: str, action_type: str) -> dict[str, Any]:
        action_types = load_action_types(ontology)
        if isinstance(action_types, dict):
            action_schema = action_types.get(action_type)
            if action_schema is None:
                raise ActionTypeNotFoundError(f"Action type not found: {action_type}")
            if not isinstance(action_schema, dict):
                raise ValueError(f"Action type schema must be a JSON object: {action_type}")
            return action_schema
        if isinstance(action_types, list):
            for action_schema in action_types:
                if isinstance(action_schema, dict) and action_schema.get("apiName") == action_type:
                    return action_schema
            raise ActionTypeNotFoundError(f"Action type not found: {action_type}")
        raise ValueError("action-types.json must be a JSON object or array.")

    def _list_object_items(ontology: str, object_type: str, project_id: str | None) -> list[dict[str, Any]]:
        ontology_id = _ensure_ontology(ontology)
        _require_object_type_schema(ontology_id, object_type)  # raises 404 for an unknown object type
        # Single merged ontology: reads always go through the local facade, which serves CSV /
        # Dolt / derived / metadata + run-record overlay per the ObjectType's datasource binding
        # — no ontology-id branching.
        return get_object_data(object_type, project_id=project_id)

    def _build_objects_page(
        ontology: str,
        object_type: str,
        project_id: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        items = _list_object_items(ontology, object_type, project_id)
        return {
            "items": _paginate_items(items, limit, offset),
            "limit": limit,
            "offset": offset,
            "total": len(items),
        }

    def _preview_branch_dependency(
        preview_branch_id: str | None = Header(default=None, alias=PREVIEW_BRANCH_HEADER),
    ) -> PreviewBranchContext:
        return resolve_preview_branch_context(preview_branch_id)

    def _preview_branch_http_error(exc: PreviewBranchUnavailableError) -> HTTPException:
        return HTTPException(status_code=503, detail=str(exc))

    def _ensure_preview_action_supported(action: str) -> None:
        preview_context = get_current_preview_branch()
        if preview_context.is_main or action == "UpdateMilestoneDate":
            return
        raise PreviewBranchUnavailableError(
            f"{PREVIEW_BRANCH_HEADER} routing is not implemented for Action `{action}`."
        )

    def _mirror_object_types_from_payload(payload: dict[str, Any] | None) -> list[str] | None:
        if not payload:
            return None
        raw = payload.get("objectTypes") or payload.get("object_types")
        if raw is None:
            return None
        if not isinstance(raw, list):
            raise ValueError("payload.objectTypes must be a list.")
        return [str(item) for item in raw]

    def _dataset_http_exception(exc: Exception) -> HTTPException:
        if isinstance(exc, DatasetNotImplementedError):
            return HTTPException(status_code=501, detail=str(exc))
        if isinstance(exc, DatasetUnavailableError):
            return HTTPException(status_code=503, detail=str(exc))
        if isinstance(exc, DatasetConflictError):
            return HTTPException(status_code=409, detail=str(exc))
        if isinstance(exc, DatasetNotFoundError):
            return HTTPException(status_code=404, detail=str(exc))
        if isinstance(exc, DatasetInvalidTransactionError):
            return HTTPException(status_code=400, detail=str(exc))
        if isinstance(exc, DatasetError):
            return HTTPException(status_code=getattr(exc, "status_code", 400), detail=str(exc))
        if isinstance(exc, ValueError):
            return HTTPException(status_code=400, detail=str(exc))
        return HTTPException(status_code=500, detail=str(exc))

    @app.post("/api/v1/datasets")
    def create_v1_dataset(payload: dict[str, Any]):
        try:
            object_type = payload.get("objectType") or payload.get("objectTypeApiName")
            return create_dataset(
                name=str(payload.get("name") or ""),
                parent_folder_rid=str(payload.get("parentFolderRid") or ""),
                object_type=str(object_type).strip() if object_type else None,
                object_types=load_object_types(),
            )
        except Exception as exc:
            raise _dataset_http_exception(exc) from exc

    @app.post("/api/v1/datasets/{datasetRid}/transactions")
    def create_v1_dataset_transaction(datasetRid: str, payload: dict[str, Any]):
        try:
            return create_dataset_transaction(
                datasetRid,
                str(payload.get("transactionType") or "UPDATE"),
            )
        except Exception as exc:
            raise _dataset_http_exception(exc) from exc

    @app.post("/api/v1/datasets/{datasetRid}/files:upload")
    async def upload_v1_dataset_file(
        datasetRid: str,
        request: FastAPIRequest,
        transactionRid: str | None = Query(default=None),
        filePath: str | None = Query(default=None),
    ):
        try:
            if not transactionRid:
                raise ValueError("transactionRid query parameter is required.")
            content = await request.body()
            return upload_dataset_file(
                datasetRid,
                transactionRid,
                content,
                file_name=filePath,
            )
        except Exception as exc:
            raise _dataset_http_exception(exc) from exc

    @app.post("/api/v1/datasets/{datasetRid}/transactions/{transactionRid}/commit")
    def commit_v1_dataset_transaction(datasetRid: str, transactionRid: str):
        try:
            return commit_dataset_transaction(datasetRid, transactionRid)
        except Exception as exc:
            raise _dataset_http_exception(exc) from exc

    @app.get("/api/v1/datasets/{datasetRid}/readTable")
    def read_v1_dataset_table(datasetRid: str, format: str = Query(default="json")):
        try:
            result = read_dataset_table(datasetRid, output_format=format)
            if result.get("format") == "csv":
                return Response(content=str(result.get("content") or ""), media_type="text/csv")
            return result
        except Exception as exc:
            raise _dataset_http_exception(exc) from exc

    @app.get("/api/v1/datasets/{datasetRid}/branches")
    def list_v1_dataset_branches(datasetRid: str):
        try:
            return list_dataset_branches(datasetRid)
        except Exception as exc:
            raise _dataset_http_exception(exc) from exc

    @app.get("/api/v1/datasets/{datasetRid}/branches/{branchId}")
    def get_v1_dataset_branch(datasetRid: str, branchId: str):
        try:
            return get_dataset_branch(datasetRid, branchId)
        except Exception as exc:
            raise _dataset_http_exception(exc) from exc

    @app.post("/api/v1/datasets/{datasetRid}/branches/{branchId}")
    def create_v1_dataset_branch(datasetRid: str, branchId: str, payload: dict[str, Any] | None = None):
        try:
            return create_dataset_branch(datasetRid, branchId, payload)
        except Exception as exc:
            raise _dataset_http_exception(exc) from exc

    @app.delete("/api/v1/datasets/{datasetRid}/branches/{branchId}", status_code=204)
    def delete_v1_dataset_branch(datasetRid: str, branchId: str):
        try:
            delete_dataset_branch(datasetRid, branchId)
            return Response(status_code=204)
        except Exception as exc:
            raise _dataset_http_exception(exc) from exc

    @app.post("/api/v1/datasets:syncObjectBackingData")
    def sync_v1_object_type_backing_datasets(payload: dict[str, Any] | None = None):
        try:
            object_type_names = None
            if payload and isinstance(payload.get("objectTypes"), list):
                object_type_names = [str(item) for item in payload["objectTypes"]]
            return sync_object_type_backing_datasets(
                object_types=load_object_types(),
                object_type_names=object_type_names,
            )
        except Exception as exc:
            raise _dataset_http_exception(exc) from exc

    @app.get("/api/v1/ontology/meta/{object_type}")
    def get_meta(object_type: str):
        try:
            # v1 作为兼容入口，复用 v2 objectType 的 raw schema 语义。
            return _require_object_type_schema(DEFAULT_ONTOLOGY, object_type)
        except ObjectTypeNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v1/ontology/data/{object_type}")
    def get_data(object_type: str, project_id: str | None = Query(default=None)):
        try:
            # v1 保持历史返回（数组），数据来源与 v2 objects 列表一致。
            return _list_object_items(DEFAULT_ONTOLOGY, object_type, project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except TypeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v1/ontology/graph/backward-key-milestones")
    def get_backward_key_milestones(
        project_id: str = Query(...),
        anchor_id: str | None = Query(default=None, description="倒排锚点 id（与 anchorOptions[].id 一致），缺省为第一个选项"),
    ):
        try:
            return get_backward_key_milestones_graph(project_id=project_id, selected_anchor_id=anchor_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/v1/ontology/graph/backward-key-milestones/execute")
    def execute_backward_key_milestones_endpoint(payload: dict[str, Any]):
        raise HTTPException(status_code=400, detail=_action_only_writeback_detail("executeBackwardKeyMilestones"))

    @app.post("/api/v1/ontology/action/{action_name}")
    def post_action(action_name: str, payload: dict[str, Any]):
        object_type = payload.get("object_type")
        if not object_type:
            raise HTTPException(status_code=400, detail="payload.object_type is required.")
        try:
            return update_object_data(str(object_type), action_name, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies")
    def list_ontologies():
        return [_ontology_summary(ontology) for ontology in ONTOLOGY_SCHEMA_DIRS]

    @app.get("/api/v2/ontologies/{ontology}")
    def get_ontology(ontology: str):
        try:
            ontology_id = _ensure_ontology(ontology)
            return _ontology_summary(ontology_id)
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/objectTypes")
    def list_v2_object_types(ontology: str):
        try:
            ontology_id = _ensure_ontology(ontology)
            return list_object_type_summaries(ontology_id)
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/v2/ontologies/{ontology}/objectTypes/sync-dolt-schema")
    def sync_v2_all_object_type_dolt_schemas(ontology: str):
        try:
            ontology_id = _ensure_default_runtime_ontology(ontology)
            return sync_all_object_type_dolt_schemas(load_object_types(ontology_id))
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DoltSchemaSyncUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/objectTypes/{object_type}")
    def get_v2_object_type(ontology: str, object_type: str):
        try:
            ontology_id = _ensure_ontology(ontology)
            return _require_object_type_schema(ontology_id, object_type)
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ObjectTypeNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/v2/ontologies/{ontology}/objectTypes/{object_type}/sync-dolt-schema")
    def sync_v2_object_type_dolt_schema(ontology: str, object_type: str):
        try:
            ontology_id = _ensure_default_runtime_ontology(ontology)
            object_schema = _require_object_type_schema(ontology_id, object_type)
            return sync_object_type_dolt_schema(object_type, object_schema)
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ObjectTypeNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except DoltSchemaSyncUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/v2/ontologies/{ontology}/doltMirror/sync")
    def sync_v2_dolt_main_mirror(ontology: str, payload: dict[str, Any] | None = None):
        try:
            ontology_id = _ensure_default_runtime_ontology(ontology)
            return sync_main_mirror(
                object_types=_mirror_object_types_from_payload(payload),
                object_type_schemas=load_object_types(ontology_id),
            )
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PreviewBranchUnavailableError as exc:
            raise _preview_branch_http_error(exc) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/doltMirror/validate")
    def validate_v2_dolt_main_mirror(
        ontology: str,
        objectTypes: str | None = Query(default=None),
    ):
        try:
            ontology_id = _ensure_default_runtime_ontology(ontology)
            return validate_main_mirror(
                object_types=objectTypes,
                object_type_schemas=load_object_types(ontology_id),
            )
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PreviewBranchUnavailableError as exc:
            raise _preview_branch_http_error(exc) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/linkTypes")
    def list_v2_link_types(ontology: str):
        try:
            ontology_id = _ensure_ontology(ontology)
            return _normalize_link_types(ontology_id)
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/actionTypes")
    def list_v2_action_types(ontology: str):
        try:
            ontology_id = _ensure_ontology(ontology)
            return _normalize_action_types(ontology_id)
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/actionTypes/{action_type}")
    def get_v2_action_type(ontology: str, action_type: str):
        try:
            ontology_id = _ensure_ontology(ontology)
            return _require_action_type_schema(ontology_id, action_type)
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ActionTypeNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/valueTypes")
    def list_v2_value_types(ontology: str):
        try:
            ontology_id = _ensure_ontology(ontology)
            return _normalize_value_types(ontology_id)
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/valueTypes/{value_type}")
    def get_v2_value_type(ontology: str, value_type: str):
        try:
            ontology_id = _ensure_ontology(ontology)
            schema = load_value_types(ontology_id).get(value_type)
            if schema is None:
                raise KeyError(f"Value type not found: {value_type}")
            return schema
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/functionTypes")
    def list_v2_function_types(ontology: str):
        try:
            ontology_id = _ensure_ontology(ontology)
            return _normalize_function_types(ontology_id)
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/functionTypes/{function_type}")
    def get_v2_function_type(ontology: str, function_type: str):
        try:
            ontology_id = _ensure_ontology(ontology)
            schema = load_function_types(ontology_id).get(function_type)
            if schema is None or (isinstance(schema, dict) and schema.get("kind") == "SKILL"):
                raise KeyError(f"Function not found: {function_type}")
            return schema
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/interfaceTypes")
    def list_v2_interface_types(ontology: str):
        try:
            ontology_id = _ensure_ontology(ontology)
            return _normalize_interface_types(ontology_id)
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/interfaceTypes/{interface_type}")
    def get_v2_interface_type(ontology: str, interface_type: str):
        try:
            ontology_id = _ensure_ontology(ontology)
            schema = load_interface_types(ontology_id).get(interface_type)
            if schema is None:
                raise KeyError(f"Interface type not found: {interface_type}")
            return schema
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/interfaceTypes/{interface_type}/objectTypes")
    def list_v2_interface_object_types(ontology: str, interface_type: str):
        try:
            ontology_id = _ensure_ontology(ontology)
            if interface_type not in load_interface_types(ontology_id):
                raise KeyError(f"Interface type not found: {interface_type}")
            return {
                "interfaceType": interface_type,
                "objectTypeApiNames": object_types_implementing_interface(interface_type, ontology_id),
            }
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/automationTypes")
    def list_v2_automation_types(ontology: str):
        try:
            ontology_id = _ensure_ontology(ontology)
            return _normalize_automation_types(ontology_id)
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/automationTypes/{automation_type}")
    def get_v2_automation_type(ontology: str, automation_type: str):
        try:
            ontology_id = _ensure_ontology(ontology)
            schema = load_automation_types(ontology_id).get(automation_type)
            if schema is None:
                raise KeyError(f"Automation type not found: {automation_type}")
            return schema
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/v2/ontologies/{ontology}/automations:evaluate")
    def evaluate_v2_automations(
        ontology: str,
        payload: dict[str, Any],
        _preview_branch: PreviewBranchContext = Depends(_preview_branch_dependency),
    ):
        try:
            _ensure_default_runtime_ontology(ontology)
            object_type = str(payload.get("objectType") or payload.get("object_type") or "").strip()
            if not object_type:
                raise ValueError("payload.objectType is required.")
            event = str(payload.get("event") or "UPDATE").strip()
            context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
            return {
                "objectType": object_type,
                "event": event,
                "automations": data_connector.run_automations(object_type, event, context),
            }
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PreviewBranchUnavailableError as exc:
            raise _preview_branch_http_error(exc) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/skillTypes")
    def list_v2_skill_types(ontology: str):
        try:
            ontology_id = _ensure_ontology(ontology)
            return _normalize_skill_types(ontology_id)
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/queryTypes")
    def list_v2_query_types(ontology: str):
        try:
            ontology_id = _ensure_ontology(ontology)
            return _normalize_function_types(ontology_id)
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/queries/backward-key-milestones")
    def get_v2_backward_key_milestones(
        ontology: str,
        project_id: str = Query(...),
        anchor_id: str | None = Query(default=None, description="倒排锚点 id（与 anchorOptions[].id 一致），缺省为第一个选项"),
    ):
        try:
            _ensure_default_runtime_ontology(ontology)
            return get_backward_key_milestones_graph(project_id=project_id, selected_anchor_id=anchor_id)
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/queries/{query}")
    def get_v2_query(
        ontology: str,
        query: str,
        project_id: str = Query(...),
        anchor_id: str | None = Query(default=None, description="倒排锚点 id（与 anchorOptions[].id 一致），缺省为第一个选项"),
        _preview_branch: PreviewBranchContext = Depends(_preview_branch_dependency),
    ):
        try:
            _ensure_default_runtime_ontology(ontology)
            if query == "backward-key-milestones":
                return get_backward_key_milestones_graph(project_id=project_id, selected_anchor_id=anchor_id)
            raise KeyError(f"Query not found: {query}")
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PreviewBranchUnavailableError as exc:
            raise _preview_branch_http_error(exc) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/v2/ontologies/{ontology}/queries/backward-key-milestones/execute")
    def execute_v2_backward_key_milestones(
        ontology: str,
        payload: dict[str, Any],
        _preview_branch: PreviewBranchContext = Depends(_preview_branch_dependency),
    ):
        try:
            _ensure_default_runtime_ontology(ontology)
            raise HTTPException(status_code=400, detail=_action_only_writeback_detail("executeBackwardKeyMilestones"))
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/v2/ontologies/{ontology}/skills/{skill}/execute")
    def execute_v2_skill(
        ontology: str,
        skill: str,
        payload: dict[str, Any],
        _preview_branch: PreviewBranchContext = Depends(_preview_branch_dependency),
    ):
        try:
            _ensure_default_runtime_ontology(ontology)
            action_name = DEPRECATED_WRITEBACK_SKILL_ACTIONS.get(skill)
            if action_name:
                raise HTTPException(status_code=400, detail=_action_only_writeback_detail(action_name))
            return execute_local_skill(skill, payload)
        except HTTPException:
            raise
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except TypeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PreviewBranchUnavailableError as exc:
            raise _preview_branch_http_error(exc) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/previewBranches")
    def list_v2_preview_branches(ontology: str):
        try:
            _ensure_default_runtime_ontology(ontology)
            return list_preview_branches()
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PreviewBranchUnavailableError as exc:
            raise _preview_branch_http_error(exc) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/v2/ontologies/{ontology}/previewBranches")
    def create_v2_preview_branch(
        ontology: str,
        payload: dict[str, Any] | None = None,
        preview_branch: PreviewBranchContext = Depends(_preview_branch_dependency),
    ):
        try:
            _ensure_default_runtime_ontology(ontology)
            return create_preview_branch(base_context=preview_branch, payload=payload)
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PreviewBranchUnavailableError as exc:
            raise _preview_branch_http_error(exc) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/v2/ontologies/{ontology}/previewBranches/{preview_branch_id}/publish")
    def publish_v2_preview_branch(ontology: str, preview_branch_id: str):
        try:
            _ensure_default_runtime_ontology(ontology)
            return publish_preview_branch(preview_branch_id)
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PreviewBranchUnavailableError as exc:
            raise _preview_branch_http_error(exc) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/v2/ontologies/{ontology}/previewBranches/{preview_branch_id}/discard")
    def discard_v2_preview_branch(ontology: str, preview_branch_id: str):
        try:
            _ensure_default_runtime_ontology(ontology)
            return discard_preview_branch(preview_branch_id)
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PreviewBranchUnavailableError as exc:
            raise _preview_branch_http_error(exc) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/v2/ontologies/{ontology}/actions/{action}/apply")
    def apply_v2_action(
        ontology: str,
        action: str,
        payload: dict[str, Any],
        acting_user: str | None = Header(default=None, alias="X-Acting-User"),
        _preview_branch: PreviewBranchContext = Depends(_preview_branch_dependency),
    ):
        try:
            ontology_id = _ensure_ontology(ontology)
            if ontology_id != DEFAULT_ONTOLOGY:
                # Non-default (metadata-only) ontologies: only run-record CREATE actions are
                # runtime-enabled; apply_action_type raises MetadataOnlyOntologyError (-> 501)
                # for everything else (MODIFY actions, writes to template object types).
                return apply_action_type(action, payload, ontology=ontology_id)
            _ensure_preview_action_supported(action)
            if action == "UpdateMilestoneDate":
                return apply_update_milestone_date_batch({"batch": [payload]})
            if acting_user:
                # Attribute the Dolt commit to the acting user so object history shows who edited.
                payload = {**payload, "actingUser": acting_user}
            return apply_action_type(action, payload)
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PreviewBranchUnavailableError as exc:
            raise _preview_branch_http_error(exc) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/v2/ontologies/{ontology}/actions/{action}/validate")
    def validate_v2_action(
        ontology: str,
        action: str,
        payload: dict[str, Any],
        _preview_branch: PreviewBranchContext = Depends(_preview_branch_dependency),
    ):
        try:
            ontology_id = _ensure_ontology(ontology)
            if ontology_id != DEFAULT_ONTOLOGY:
                return validate_action_type(action, payload, ontology=ontology_id)
            _ensure_preview_action_supported(action)
            if action == "UpdateMilestoneDate":
                normalized_items, _project_id = _validate_update_milestone_date_batch({"batch": [payload]})
                return {
                    "success": True,
                    "actionName": "UpdateMilestoneDate",
                    "validatedCount": len(normalized_items),
                    "results": [],
                }
            return validate_action_type(action, payload)
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PreviewBranchUnavailableError as exc:
            raise _preview_branch_http_error(exc) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/v2/ontologies/{ontology}/actions/{action}/validateBatch")
    def validate_v2_action_batch(
        ontology: str,
        action: str,
        payload: dict[str, Any],
        _preview_branch: PreviewBranchContext = Depends(_preview_branch_dependency),
    ):
        try:
            _ensure_default_runtime_ontology(ontology)
            _ensure_preview_action_supported(action)
            if action == "UpdateMilestoneDate":
                normalized_items, _project_id = _validate_update_milestone_date_batch(payload)
                return {
                    "success": True,
                    "actionName": "UpdateMilestoneDate",
                    "validatedCount": len(normalized_items),
                    "results": [],
                }
            if action == "modifyPodPowerOnMilestoneAnchorDate":
                return validate_pod_power_on_milestone_anchor_date_batch(payload)
            raise KeyError(f"Batch Action validation not found: {action}")
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PreviewBranchUnavailableError as exc:
            raise _preview_branch_http_error(exc) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/v2/ontologies/{ontology}/actions/{action}/applyBatch")
    def apply_v2_action_batch(
        ontology: str,
        action: str,
        payload: dict[str, Any],
        _preview_branch: PreviewBranchContext = Depends(_preview_branch_dependency),
    ):
        try:
            _ensure_default_runtime_ontology(ontology)
            _ensure_preview_action_supported(action)
            if action == "UpdateMilestoneDate":
                return apply_update_milestone_date_batch(payload)
            if action == "modifyPodPowerOnMilestoneAnchorDate":
                return apply_pod_power_on_milestone_anchor_date_batch(payload)
            raise KeyError(f"Batch Action not found: {action}")
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PreviewBranchUnavailableError as exc:
            raise _preview_branch_http_error(exc) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/v2/ontologies/{ontology}/queries/forward-key-milestones/execute")
    def execute_v2_forward_key_milestones(
        ontology: str,
        payload: dict[str, Any],
        _preview_branch: PreviewBranchContext = Depends(_preview_branch_dependency),
    ):
        try:
            _ensure_default_runtime_ontology(ontology)
            raise HTTPException(status_code=400, detail=_action_only_writeback_detail("executeForwardKeyMilestones"))
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/v2/ontologies/{ontology}/queries/{query}/execute")
    def execute_v2_query(
        ontology: str,
        query: str,
        payload: dict[str, Any],
        _preview_branch: PreviewBranchContext = Depends(_preview_branch_dependency),
    ):
        try:
            _ensure_default_runtime_ontology(ontology)
            action_name = WRITEBACK_QUERY_ACTIONS.get(query)
            if action_name:
                raise HTTPException(status_code=400, detail=_action_only_writeback_detail(action_name))
            raise KeyError(f"Query not found: {query}")
        except HTTPException:
            raise
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PreviewBranchUnavailableError as exc:
            raise _preview_branch_http_error(exc) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/v2/ontologies/{ontology}/functions/{function}/execute")
    def execute_v2_function(
        ontology: str,
        function: str,
        payload: dict[str, Any],
        _preview_branch: PreviewBranchContext = Depends(_preview_branch_dependency),
    ):
        try:
            ontology_id = _ensure_ontology(ontology)
            function_schema = load_function_types(ontology_id).get(function)
            if function_schema is None:
                raise KeyError(f"Function not found: {function}")
            # Read-only derived Functions (建议值, no writeback) may run on metadata-only
            # ontologies; Skills and stateful work stay gated to the default runtime ontology.
            is_readonly_function = (
                isinstance(function_schema, dict)
                and function_schema.get("kind") == "FUNCTION"
                and (function_schema.get("sideEffects") or {}).get("type") == "NONE"
            )
            if ontology_id != DEFAULT_ONTOLOGY and not is_readonly_function:
                _ensure_default_runtime_ontology(ontology)
            return {
                "success": True,
                "functionName": function,
                "result": execute_function_type(function, payload, ontology=ontology_id),
            }
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PreviewBranchUnavailableError as exc:
            raise _preview_branch_http_error(exc) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/objects/{object_type}")
    def list_v2_objects(
        ontology: str,
        object_type: str,
        project_id: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        _preview_branch: PreviewBranchContext = Depends(_preview_branch_dependency),
    ):
        try:
            ontology_id = _ensure_ontology(ontology)
            return _build_objects_page(ontology_id, object_type, project_id, limit, offset)
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ObjectTypeNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PreviewBranchUnavailableError as exc:
            raise _preview_branch_http_error(exc) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/objects/{object_type}/{primary_key}")
    def get_v2_object_by_primary_key(
        ontology: str,
        object_type: str,
        primary_key: str,
        project_id: str | None = Query(default=None),
        as_of: str | None = Query(default=None, alias="asOf"),
        _preview_branch: PreviewBranchContext = Depends(_preview_branch_dependency),
    ):
        try:
            ontology_id = _ensure_default_runtime_ontology(ontology)
            object_schema = _require_object_type_schema(ontology_id, object_type)
            primary_key_field = _primary_key_field(object_type, object_schema)
            if as_of:
                # Time-travel read: the object's value as of a commit / timestamp / branch.
                rows = get_object_as_of(
                    object_type,
                    as_of,
                    primary_key={primary_key_field: primary_key},
                    project_id=project_id,
                )
                matched = rows[0] if rows else None
            else:
                items = get_object_data(object_type, project_id=project_id)
                matched = next((item for item in items if str(item.get(primary_key_field, "")) == primary_key), None)
            if matched is None:
                raise KeyError(f"Object not found: {object_type}/{primary_key}")
            return {"object": matched, **({"asOf": as_of} if as_of else {})}
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ObjectTypeNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PreviewBranchUnavailableError as exc:
            raise _preview_branch_http_error(exc) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/objects/{object_type}/{primary_key}/history")
    def get_v2_object_history(
        ontology: str,
        object_type: str,
        primary_key: str,
        project_id: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=1000),
        _preview_branch: PreviewBranchContext = Depends(_preview_branch_dependency),
    ):
        try:
            ontology_id = _ensure_default_runtime_ontology(ontology)
            object_schema = _require_object_type_schema(ontology_id, object_type)
            primary_key_field = _primary_key_field(object_type, object_schema)
            versions = get_object_history(
                object_type,
                {primary_key_field: primary_key},
                project_id=project_id,
                limit=limit,
            )
            return {
                "objectType": object_type,
                "primaryKey": {primary_key_field: primary_key},
                "versions": versions,
                "total": len(versions),
            }
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ObjectTypeNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PreviewBranchUnavailableError as exc:
            raise _preview_branch_http_error(exc) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/objects/{object_type}/{primary_key}/diff")
    def get_v2_object_diff(
        ontology: str,
        object_type: str,
        primary_key: str,
        from_ref: str = Query(alias="from"),
        to_ref: str = Query(alias="to"),
        project_id: str | None = Query(default=None),
        _preview_branch: PreviewBranchContext = Depends(_preview_branch_dependency),
    ):
        try:
            ontology_id = _ensure_default_runtime_ontology(ontology)
            object_schema = _require_object_type_schema(ontology_id, object_type)
            primary_key_field = _primary_key_field(object_type, object_schema)
            diff = get_object_diff(
                object_type,
                from_ref,
                to_ref,
                {primary_key_field: primary_key},
                project_id=project_id,
            )
            return {
                "objectType": object_type,
                "primaryKey": {primary_key_field: primary_key},
                "fromRef": from_ref,
                "toRef": to_ref,
                "diff": diff,
                "total": len(diff),
            }
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ObjectTypeNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PreviewBranchUnavailableError as exc:
            raise _preview_branch_http_error(exc) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/v2/ontologies/{ontology}/objects/{object_type}/search")
    def search_v2_objects(
        ontology: str,
        object_type: str,
        payload: dict[str, Any],
        project_id: str | None = Query(default=None),
        _preview_branch: PreviewBranchContext = Depends(_preview_branch_dependency),
    ):
        try:
            ontology_id = _ensure_default_runtime_ontology(ontology)
            _require_object_type_schema(ontology_id, object_type)
            filters = payload.get("filters", {})
            limit = int(payload.get("limit", 50))
            offset = int(payload.get("offset", 0))
            if limit < 1 or limit > 500:
                raise ValueError("limit must be between 1 and 500.")
            if offset < 0:
                raise ValueError("offset must be >= 0.")
            if not isinstance(filters, dict):
                raise ValueError("filters must be an object.")
            items = get_object_data(object_type, project_id=project_id)
            matched = [item for item in items if _match_filters(item, filters)]
            return {
                "items": _paginate_items(matched, limit, offset),
                "limit": limit,
                "offset": offset,
                "total": len(matched),
            }
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PreviewBranchUnavailableError as exc:
            raise _preview_branch_http_error(exc) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/v2/ontologies/{ontology}/objects/{object_type}/aggregate")
    def aggregate_v2_objects(
        ontology: str,
        object_type: str,
        payload: dict[str, Any],
        project_id: str | None = Query(default=None),
        _preview_branch: PreviewBranchContext = Depends(_preview_branch_dependency),
    ):
        try:
            ontology_id = _ensure_default_runtime_ontology(ontology)
            _require_object_type_schema(ontology_id, object_type)
            op = payload.get("op", "count")
            if op != "count":
                raise ValueError("Only aggregate op `count` is supported.")
            filters = payload.get("filters", {})
            if not isinstance(filters, dict):
                raise ValueError("filters must be an object.")
            items = get_object_data(object_type, project_id=project_id)
            matched = [item for item in items if _match_filters(item, filters)]
            return {"op": "count", "value": len(matched)}
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PreviewBranchUnavailableError as exc:
            raise _preview_branch_http_error(exc) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/v2/ontologies/{ontology}/objects/{object_type}/{primary_key}/links/{link_type}")
    def list_v2_links(
        ontology: str,
        object_type: str,
        primary_key: str,
        link_type: str,
        _preview_branch: PreviewBranchContext = Depends(_preview_branch_dependency),
    ):
        try:
            ontology_id = _ensure_default_runtime_ontology(ontology)
            available = load_link_types(ontology_id)
            if link_type not in available:
                raise KeyError(f"Link type not found: {link_type}")
            items = get_linked_object_data(object_type, primary_key, link_type)
            return {
                "linkType": link_type,
                "fromObjectType": object_type,
                "fromObjectKey": primary_key,
                "items": items,
                "total": len(items),
            }
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except NotImplementedError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PreviewBranchUnavailableError as exc:
            raise _preview_branch_http_error(exc) from exc

    @app.get("/api/v2/ontologies/{ontology}/objects/{object_type}/{primary_key}/links/{link_type}/{target_primary_key}")
    def get_v2_link_target(
        ontology: str,
        object_type: str,
        primary_key: str,
        link_type: str,
        target_primary_key: str,
        _preview_branch: PreviewBranchContext = Depends(_preview_branch_dependency),
    ):
        try:
            ontology_id = _ensure_default_runtime_ontology(ontology)
            available = load_link_types(ontology_id)
            if link_type not in available:
                raise KeyError(f"Link type not found: {link_type}")
            items = get_linked_object_data(object_type, primary_key, link_type)
            matched = next((item for item in items if str(item.get("rowKey", "")) == target_primary_key), None)
            if matched is None:
                raise KeyError(f"Linked object not found: {target_primary_key}")
            return {"object": matched}
        except MetadataOnlyOntologyError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except OntologyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PreviewBranchUnavailableError as exc:
            raise _preview_branch_http_error(exc) from exc
        except NotImplementedError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


try:
    app = create_app()
except RuntimeError:
    app = None
