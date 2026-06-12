"""8.3 maintenance start/end date and over-EOS calculation."""
from __future__ import annotations

from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from agent.proposal.models import OverEos

DEFAULT_WARRANTY_POLICY = "按华为标准保修政策"


def default_start_date(*, today: date | None = None) -> date:
    base = today or date.today()
    return base + relativedelta(months=+6)


def end_date_from_start(start: date, years: int) -> date:
    return start + relativedelta(years=+years) - timedelta(days=1)


def compute_over_eos(eos: date | None, maint_end: date) -> OverEos:
    if eos is None:
        return OverEos.NO
    return OverEos.YES if eos < maint_end else OverEos.NO


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def format_iso_date(d: date | None) -> str | None:
    if d is None:
        return None
    return d.isoformat()
