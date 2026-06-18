from __future__ import annotations

import os
from datetime import date


AS_OF_DATE_ENV = "SCHEDULE_AS_OF_DATE"


def get_as_of_date() -> date:
    raw = os.environ.get(AS_OF_DATE_ENV, "").strip()
    if not raw:
        return date.today()
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{AS_OF_DATE_ENV} must use YYYY-MM-DD format.") from exc
