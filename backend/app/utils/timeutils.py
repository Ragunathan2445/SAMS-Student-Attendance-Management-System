from datetime import date, datetime, timezone

from app.core.config import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def now_local() -> datetime:
    return datetime.now(get_settings().tz)


def today_local() -> date:
    return now_local().date()


def month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year + (month == 12), (month % 12) + 1, 1)
    from datetime import timedelta

    return start, end - timedelta(days=1)
