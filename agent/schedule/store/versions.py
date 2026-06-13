from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.schedule.contracts.inputs import InputBundle
from agent.schedule.contracts.outputs import PlanResult, StrategyPlan


class PlanVersionNotFound(KeyError):
    """Raised when the requested plan version is not in SQLite."""


class AdjustOptionNotFound(KeyError):
    """Raised when commit references an unknown sandbox option."""


@dataclass(frozen=True)
class StoredPlanVersion:
    plan_id: str
    version: int
    base_version: int | None
    plan: PlanResult
    inputs: InputBundle


@dataclass(frozen=True)
class StoredAdjustOption:
    plan_id: str
    base_version: int
    option_id: str
    option: StrategyPlan
    inputs: InputBundle


class PlanVersionStore:
    """Small SQLite store for versioned PlanResult JSON snapshots."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def save_plan_version(self, plan: PlanResult, inputs: InputBundle) -> StoredPlanVersion:
        created_at = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO plan_versions (
                    plan_id, version, base_version, plan_json, input_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    plan.plan_id,
                    plan.version,
                    plan.base_version,
                    _to_json(plan),
                    _to_json(inputs),
                    created_at,
                ),
            )
        return StoredPlanVersion(
            plan_id=plan.plan_id,
            version=plan.version,
            base_version=plan.base_version,
            plan=plan,
            inputs=inputs,
        )

    def get_plan_version(self, plan_id: str, version: int) -> StoredPlanVersion:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT plan_id, version, base_version, plan_json, input_json
                FROM plan_versions
                WHERE plan_id = ? AND version = ?
                """,
                (plan_id, version),
            ).fetchone()
        if row is None:
            raise PlanVersionNotFound(f"{plan_id}@v{version}")
        return StoredPlanVersion(
            plan_id=row["plan_id"],
            version=row["version"],
            base_version=row["base_version"],
            plan=PlanResult.model_validate(json.loads(row["plan_json"])),
            inputs=InputBundle.model_validate(json.loads(row["input_json"])),
        )

    def next_version(self, plan_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT MAX(version) AS max_version FROM plan_versions WHERE plan_id = ?",
                (plan_id,),
            ).fetchone()
        max_version = row["max_version"] if row is not None else None
        return int(max_version or 0) + 1

    def save_adjust_option(
        self,
        plan_id: str,
        base_version: int,
        option: StrategyPlan,
        inputs: InputBundle,
    ) -> StoredAdjustOption:
        created_at = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO adjust_options (
                    plan_id, base_version, option_id, option_json, input_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    base_version,
                    option.option_id,
                    _to_json(option),
                    _to_json(inputs),
                    created_at,
                ),
            )
        return StoredAdjustOption(
            plan_id=plan_id,
            base_version=base_version,
            option_id=option.option_id,
            option=option,
            inputs=inputs,
        )

    def get_adjust_option(self, plan_id: str, base_version: int, option_id: str) -> StoredAdjustOption:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT plan_id, base_version, option_id, option_json, input_json
                FROM adjust_options
                WHERE plan_id = ? AND base_version = ? AND option_id = ?
                """,
                (plan_id, base_version, option_id),
            ).fetchone()
        if row is None:
            raise AdjustOptionNotFound(f"{plan_id}@v{base_version}/{option_id}")
        return StoredAdjustOption(
            plan_id=row["plan_id"],
            base_version=row["base_version"],
            option_id=row["option_id"],
            option=StrategyPlan.model_validate(json.loads(row["option_json"])),
            inputs=InputBundle.model_validate(json.loads(row["input_json"])),
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS plan_versions (
                    plan_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    base_version INTEGER,
                    plan_json TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (plan_id, version)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS adjust_options (
                    plan_id TEXT NOT NULL,
                    base_version INTEGER NOT NULL,
                    option_id TEXT NOT NULL,
                    option_json TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (plan_id, base_version, option_id)
                )
                """
            )


def _to_json(model: Any) -> str:
    return json.dumps(model.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
