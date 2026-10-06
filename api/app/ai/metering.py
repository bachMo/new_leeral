from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(slots=True)
class UsageMeter:
    cost_usd: Decimal = Decimal(0)
    calls: dict[str, int] = field(default_factory=dict)

    def record(self, operation: str, cost_usd: float | None = None) -> None:
        self.calls[operation] = self.calls.get(operation, 0) + 1
        if cost_usd:
            self.cost_usd += Decimal(str(cost_usd))


_current_meter: ContextVar[UsageMeter | None] = ContextVar("ai_usage_meter", default=None)


@contextmanager
def metered() -> Iterator[UsageMeter]:
    meter = UsageMeter()
    token = _current_meter.set(meter)
    try:
        yield meter
    finally:
        _current_meter.reset(token)


def record_usage(operation: str, cost_usd: float | None = None) -> None:
    meter = _current_meter.get()
    if meter is not None:
        meter.record(operation, cost_usd)
