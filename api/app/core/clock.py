from datetime import UTC, date, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def today() -> date:
    return utcnow().date()


def month_period(moment: datetime | None = None) -> str:
    return (moment or utcnow()).strftime("%Y-%m")


def day_period(moment: datetime | None = None) -> str:
    return (moment or utcnow()).strftime("%Y-%m-%d")
