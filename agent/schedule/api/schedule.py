from __future__ import annotations

from datetime import date
from typing import Sequence, TypeVar

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, JSONResponse

from agent.schedule.api.export_plan import (
    XLSX_MEDIA_TYPE,
    ExportPlanQueryError,
    resolve_plan_version_for_export,
    write_delivery_plan_xlsx,
)
from agent.schedule.engine import (
    EngineError,
    ScheduleResult,
    build_adjustment_options,
    generate_plan,
    recalculate_plan_with_duration_overrides,
    select_shadow_recommendation,
)
from agent.schedule.importer import DataImportError, load_input_bundle
from agent.schedule.store import AdjustOptionNotFound, PlanVersionNotFound, PlanVersionStore
from agent.schedule.contracts.api import (
    API_PREFIX,
    AdjustRequest,
    AdjustResponse,
    ChangeSet,
    CommitRequest,
    CommitResponse,
    ConflictDetail,
    ErrorResponse,
    GenerateRequest,
    GenerateResponse,
)
from agent.schedule.contracts.inputs import InputBundle
from agent.schedule.contracts.outputs import Explanation, MovedActivity, PlanResult

router = APIRouter(prefix=API_PREFIX, tags=["schedule"])

T = TypeVar("T")


def get_store(request: Request) -> PlanVersionStore:
    store = getattr(request.app.state, "schedule_plan_store", None)
    if store is None:
        store = PlanVersionStore(request.app.state.schedule_plan_store_path)
        request.app.state.schedule_plan_store = store
    return store


@router.get(
    "/project-data",
    response_model=InputBundle,
    responses={422: {"model": ErrorResponse}},
)
def get_project_data(total_card_count: int | None = Query(default=None, ge=1)):
    try:
        return load_input_bundle(total_card_count=total_card_count)
    except DataImportError as exc:
        return _error_response(
            422,
            ErrorResponse(
                code="IMPORT_ERROR",
                message=str(exc),
                conflicts=[
                    ConflictDetail(
                        constraint="02_项目数据",
                        detail=str(exc),
                    )
                ],
            ),
        )


@router.get(
    "/export-plan",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def export_delivery_plan(
    plan_id: str | None = Query(default=None),
    version: int | None = Query(default=None, ge=1),
    store: PlanVersionStore = Depends(get_store),
):
    try:
        stored = resolve_plan_version_for_export(store, plan_id=plan_id, version=version)
    except ExportPlanQueryError as exc:
        return _error_response(
            422,
            ErrorResponse(
                code="VALIDATION_ERROR",
                message=str(exc),
            ),
        )
    except PlanVersionNotFound:
        target = f"计划 {plan_id} 的 v{version}" if plan_id and version else "最新正式计划版本"
        return _error_response(
            404,
            ErrorResponse(
                code="PLAN_VERSION_NOT_FOUND",
                message=f"找不到{target}，请先完成初排或下发。",
            ),
        )

    output_path = write_delivery_plan_xlsx(stored.plan, stored.inputs)
    return FileResponse(
        output_path,
        media_type=XLSX_MEDIA_TYPE,
        filename="交付计划表.xlsx",
    )


@router.post(
    "/generate",
    response_model=GenerateResponse,
    responses={422: {"model": ErrorResponse}},
)
def generate_schedule(payload: GenerateRequest, store: PlanVersionStore = Depends(get_store)):
    try:
        result = generate_plan(payload.inputs, include_risks=True)
    except EngineError as exc:
        return _error_response(422, exc.to_response())

    assert isinstance(result, ScheduleResult)
    store.save_plan_version(result.plan, payload.inputs)
    return GenerateResponse(
        plan=result.plan,
        readiness_suggestions=result.readiness_suggestions,
        risks=result.risks,
        unmet=[],
        explanation=Explanation(
            is_initial=True,
            notes=["已生成初排并保存为计划版本。"],
        ),
    )


@router.post(
    "/adjust",
    response_model=AdjustResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def adjust_schedule(payload: AdjustRequest, store: PlanVersionStore = Depends(get_store)):
    try:
        base = store.get_plan_version(payload.plan_id, payload.base_version)
    except PlanVersionNotFound:
        return _error_response(
            404,
            ErrorResponse(
                code="PLAN_VERSION_NOT_FOUND",
                message=f"找不到计划 {payload.plan_id} 的 v{payload.base_version} 基线。",
            ),
        )

    merged_inputs = apply_changes(base.inputs, payload.changes)
    try:
        result = generate_plan(
            merged_inputs,
            incidents=payload.changes.incidents,
            plan_id=payload.plan_id,
            version=payload.base_version + 1,
            base_version=payload.base_version,
            include_risks=True,
        )
    except EngineError as exc:
        return _error_response(422, exc.to_response())

    assert isinstance(result, ScheduleResult)
    adjustment = build_adjustment_options(merged_inputs, payload.changes, result.plan, result.risks)
    for option in adjustment.options:
        store.save_adjust_option(payload.plan_id, payload.base_version, option, merged_inputs)
    return AdjustResponse(
        options=adjustment.options,
        unmet=adjustment.unmet,
        gap=adjustment.gap,
        explanation=_adjust_explanation(base.plan, result.plan, payload.changes),
    )


@router.post(
    "/commit",
    response_model=CommitResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def commit_schedule(payload: CommitRequest, store: PlanVersionStore = Depends(get_store)):
    try:
        stored_option = store.get_adjust_option(payload.plan_id, payload.base_version, payload.option_id)
    except AdjustOptionNotFound:
        return _error_response(
            404,
            ErrorResponse(
                code="OPTION_NOT_FOUND",
                message=f"找不到计划 {payload.plan_id} 基于 v{payload.base_version} 的方案 {payload.option_id}。",
            ),
        )

    new_version = store.next_version(payload.plan_id)
    committed_plan = stored_option.option.plan
    if payload.duration_overrides:
        try:
            committed_plan = recalculate_plan_with_duration_overrides(
                stored_option.inputs,
                stored_option.option.plan,
                payload.duration_overrides,
            )
        except EngineError as exc:
            return _error_response(422, exc.to_response())
    committed_plan = committed_plan.model_copy(update={"version": new_version, "base_version": payload.base_version})
    store.save_plan_version(committed_plan, stored_option.inputs)
    adjust_options = store.list_adjust_options(payload.plan_id, payload.base_version)
    shadow_option = select_shadow_recommendation([stored.option for stored in adjust_options])
    store.save_shadow_recommendation_log(
        plan_id=payload.plan_id,
        base_version=payload.base_version,
        new_version=new_version,
        shadow_option=shadow_option,
        selected_option=stored_option.option,
        duration_overrides_applied=bool(payload.duration_overrides),
    )
    return CommitResponse(
        plan_id=payload.plan_id,
        new_version=new_version,
        plan=committed_plan,
    )


def apply_changes(base: InputBundle, changes: ChangeSet) -> InputBundle:
    updates = {
        "rooms": _merge_by_id(base.rooms, changes.rooms, "room_id"),
        "arrivals": _merge_by_id(base.arrivals, changes.arrivals, "arrival_id"),
        "teams": _merge_by_id(base.teams, changes.teams, "team_id"),
        "batches": _merge_by_id(base.batches, changes.batches, "batch_id"),
        "anchors": _merge_by_id(base.anchors, changes.anchors, "anchor_id"),
    }
    if changes.rule_config is not None:
        updates["rule_config"] = changes.rule_config
    return base.model_copy(update=updates)


def _merge_by_id(existing: Sequence[T], changes: Sequence[T], id_attr: str) -> list[T]:
    by_id = {getattr(item, id_attr): item for item in existing}
    for item in changes:
        by_id[getattr(item, id_attr)] = item
    return list(by_id.values())


def _adjust_explanation(base_plan: PlanResult, new_plan: PlanResult, changes: ChangeSet) -> Explanation:
    notes = ["已按实体 id 覆盖变更，并生成调整方案。"]
    if changes.demands:
        notes.append("已按诉求生成 A/B/C 或 buffer 方案，并逐条给出风险与不可满足项。")
    if changes.reworks:
        notes.append("已将返工作为独立活动插入方案排期。")

    return Explanation(
        is_initial=False,
        anchors_used=[anchor.anchor_id for anchor in changes.anchors],
        strategy_used="均匀压缩",
        critical_path_change=_critical_path_change(base_plan.critical_path, new_plan.critical_path),
        moved_activities=_moved_activities(base_plan, new_plan),
        notes=notes,
    )


def _critical_path_change(old_path: list[str], new_path: list[str]) -> str | None:
    if old_path == new_path:
        return "关键路径未变化。"
    return "关键路径已重算并发生变化。"


def _moved_activities(base_plan: PlanResult, new_plan: PlanResult) -> list[MovedActivity]:
    base_by_id = {activity.instance_id: activity for activity in base_plan.activities}
    moved: list[MovedActivity] = []
    for activity in new_plan.activities:
        old = base_by_id.get(activity.instance_id)
        if old is None:
            continue
        if old.start_date == activity.start_date and old.end_date == activity.end_date:
            continue
        direction = _direction(old.start_date, activity.start_date)
        moved.append(
            MovedActivity(
                instance_id=activity.instance_id,
                old_start=old.start_date,
                old_end=old.end_date,
                new_start=activity.start_date,
                new_end=activity.end_date,
                direction=direction,
            )
        )
    return moved


def _direction(old_start: date, new_start: date) -> str:
    return "提前" if new_start < old_start else "顺延"


def _error_response(status_code: int, error: ErrorResponse) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=error.model_dump(mode="json"))
