from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover - dependency guard
    yaml = None
    _YAML_IMPORT_ERROR = exc
else:
    _YAML_IMPORT_ERROR = None


BASE_DIR = Path(__file__).parent
DEFAULT_BINDINGS_PATH = BASE_DIR / "schema" / "datasource-bindings.yaml"
ALLOWED_READERS = {
    "csv_plan_rows",
    "csv_table",
    "derived_project",
    "derived_pod",
    "dolt_rows",
    "json_sections",
    "json_rows",
    "metadata_only",
}
ALLOWED_DATASOURCE_TYPES = {"csv", "json"}
CSV_BACKING_READERS = {
    "csv_plan_rows",
    "csv_table",
    "derived_project",
    "derived_pod",
}


@dataclass(frozen=True)
class DatasourceBinding:
    datasource_id: str
    datasource_type: str
    path: str
    project_id: str
    project_key: str
    metadata: dict[str, str]

    @property
    def file_name(self) -> str:
        return Path(self.path).name


@dataclass(frozen=True)
class ObjectTypeBinding:
    object_type: str
    reader: str
    source_ids: tuple[str, ...]
    writable: bool
    derived: bool

    @property
    def has_backing_data(self) -> bool:
        return self.reader in CSV_BACKING_READERS and bool(self.source_ids)


class DatasourceBindingRegistry:
    def __init__(
        self,
        *,
        datasources: dict[str, DatasourceBinding],
        object_types: dict[str, ObjectTypeBinding],
    ) -> None:
        self.datasources = dict(datasources)
        self.object_types = dict(object_types)

    def object_type(self, object_type: str) -> ObjectTypeBinding:
        try:
            return self.object_types[object_type]
        except KeyError as exc:
            raise KeyError(f"Datasource binding not found for ObjectType: {object_type}") from exc

    def source(self, datasource_id: str) -> DatasourceBinding:
        try:
            return self.datasources[datasource_id]
        except KeyError as exc:
            raise KeyError(f"Datasource not found: {datasource_id}") from exc

    def sources_for_object_type(self, object_type: str) -> list[DatasourceBinding]:
        binding = self.object_type(object_type)
        return [self.source(source_id) for source_id in binding.source_ids]

    def project_sources(self) -> list[DatasourceBinding]:
        try:
            return [
                source
                for source in self.sources_for_object_type("DeliveryPlanRow")
                if source.project_id and source.project_key
            ]
        except KeyError:
            return []

    def has_backing_data(self, object_type: str) -> bool:
        return self.object_type(object_type).has_backing_data

    def object_types_with_backing_data(self) -> tuple[str, ...]:
        return tuple(
            object_type
            for object_type, binding in self.object_types.items()
            if binding.has_backing_data
        )

    def runtime_object_types(self) -> tuple[str, ...]:
        return tuple(self.object_types)


def load_datasource_bindings(path: str | Path | None = None) -> DatasourceBindingRegistry:
    if yaml is None:
        raise RuntimeError("PyYAML is required to load datasource binding configuration.") from _YAML_IMPORT_ERROR

    bindings_path = Path(path) if path is not None else DEFAULT_BINDINGS_PATH
    with bindings_path.open("r", encoding="utf-8") as handle:
        raw_config = yaml.safe_load(handle)

    if not isinstance(raw_config, dict):
        raise ValueError("Datasource binding config must be a YAML mapping.")

    datasources = _load_datasources(raw_config.get("datasources"))
    object_types = _load_object_type_bindings(raw_config.get("objectTypes"), datasources)
    return DatasourceBindingRegistry(datasources=datasources, object_types=object_types)


def object_types_with_backing_data(path: str | Path | None = None) -> tuple[str, ...]:
    return load_datasource_bindings(path).object_types_with_backing_data()


def supported_runtime_object_types(path: str | Path | None = None) -> set[str]:
    return set(load_datasource_bindings(path).runtime_object_types())


def load_datasource_bindings_for_ontology(ontology: str | None = None) -> DatasourceBindingRegistry:
    """Load the datasource bindings for a given ontology.

    Only the merged `default` ontology remains: the delivery-contingency-plan ontology and its
    template/run-record `writable` split were merged into schema/datasource-bindings.yaml.
    """
    key = (ontology or "default").strip() or "default"
    if key in {"default", "_"}:
        return load_datasource_bindings()
    raise KeyError(f"No datasource bindings configured for ontology: {ontology}")


def resolve_object_type_writable(object_type: str) -> bool | None:
    """Resolve an ObjectType's `writable` flag from the merged default bindings.

    Returns the declared flag, or None when the ObjectType is not declared. The template
    (read-only) vs run-record (writable) split — including the merged contingency objects —
    is enforced uniformly from the single default registry.
    """
    try:
        return bool(load_datasource_bindings().object_type(object_type).writable)
    except KeyError:
        return None


def _load_datasources(raw_datasources: Any) -> dict[str, DatasourceBinding]:
    datasource_items: list[tuple[str, dict[str, Any]]] = []
    if raw_datasources is None:
        return {}
    if isinstance(raw_datasources, list):
        for raw_item in raw_datasources:
            if not isinstance(raw_item, dict):
                raise ValueError("Each datasource binding must be a YAML mapping.")
            datasource_id = str(raw_item.get("id") or "").strip()
            if not datasource_id:
                raise ValueError("Datasource binding is missing id.")
            datasource_items.append((datasource_id, raw_item))
    elif isinstance(raw_datasources, dict):
        for datasource_id, raw_item in raw_datasources.items():
            if not isinstance(raw_item, dict):
                raise ValueError(f"Datasource `{datasource_id}` must be a YAML mapping.")
            item = dict(raw_item)
            item.setdefault("id", datasource_id)
            datasource_items.append((str(datasource_id), item))
    else:
        raise ValueError("datasources must be a list or mapping.")

    datasources: dict[str, DatasourceBinding] = {}
    for datasource_id, raw_item in datasource_items:
        if datasource_id in datasources:
            raise ValueError(f"Duplicate datasource id `{datasource_id}`.")
        datasource_type = str(raw_item.get("type") or "").strip()
        if datasource_type not in ALLOWED_DATASOURCE_TYPES:
            raise ValueError(f"Unsupported datasource type `{datasource_type}` for `{datasource_id}`.")
        path = str(raw_item.get("path") or "").strip()
        if not path:
            raise ValueError(f"Datasource `{datasource_id}` is missing path.")
        project_id = str(raw_item.get("projectId") or raw_item.get("project_id") or "").strip()
        project_key = str(raw_item.get("projectKey") or raw_item.get("project_key") or project_id).strip()
        metadata = {
            str(key): str(value).strip()
            for key, value in raw_item.items()
            if key not in {"id", "type", "path", "projectId", "project_id", "projectKey", "project_key"}
            and value is not None
        }
        datasources[datasource_id] = DatasourceBinding(
            datasource_id=datasource_id,
            datasource_type=datasource_type,
            path=path,
            project_id=project_id,
            project_key=project_key,
            metadata=metadata,
        )
    return datasources


def _load_object_type_bindings(
    raw_object_types: Any,
    datasources: dict[str, DatasourceBinding],
) -> dict[str, ObjectTypeBinding]:
    if raw_object_types is None:
        return {}
    if not isinstance(raw_object_types, dict):
        raise ValueError("objectTypes must be a YAML mapping.")

    object_types: dict[str, ObjectTypeBinding] = {}
    for object_type, raw_binding in raw_object_types.items():
        if not isinstance(raw_binding, dict):
            raise ValueError(f"ObjectType `{object_type}` binding must be a YAML mapping.")
        reader = str(raw_binding.get("reader") or "").strip()
        if reader not in ALLOWED_READERS:
            raise ValueError(f"Unsupported datasource reader `{reader}` for ObjectType `{object_type}`.")
        source_ids = _source_ids(raw_binding.get("sources"))
        for source_id in source_ids:
            if source_id not in datasources:
                raise ValueError(f"ObjectType `{object_type}` references missing datasource `{source_id}`.")
        object_types[str(object_type)] = ObjectTypeBinding(
            object_type=str(object_type),
            reader=reader,
            source_ids=source_ids,
            writable=bool(raw_binding.get("writable", False)),
            derived=bool(raw_binding.get("derived", False)),
        )
    return object_types


def _source_ids(raw_sources: Any) -> tuple[str, ...]:
    if raw_sources is None:
        return ()
    if not isinstance(raw_sources, list):
        raise ValueError("ObjectType sources must be a list.")
    source_ids: list[str] = []
    for raw_source in raw_sources:
        source_id = str(raw_source or "").strip()
        if not source_id:
            raise ValueError("ObjectType sources must not contain empty datasource ids.")
        source_ids.append(source_id)
    return tuple(source_ids)
