from datetime import datetime
from typing import Literal

from app.models.enums import PaymentMethod, PaymentProvider, PaymentStatus, PlanCode
from app.schemas.common import Schema


class PlanOut(Schema):
    code: PlanCode
    price_xof: int
    duration_days: int | None
    writings_per_month: int
    practice_per_day: int | None
    document_words: bool


class CheckoutIn(Schema):
    plan_code: PlanCode = PlanCode.LEERAL_PLUS
    method: PaymentMethod | None = None
    payer_phone: str | None = None


class PaymentOut(Schema):
    public_token: str
    status: PaymentStatus
    provider: PaymentProvider
    method: PaymentMethod | None
    amount_xof: int
    checkout_url: str | None
    paid_at: datetime | None
    created_at: datetime


class SimulatedOutcomeIn(Schema):
    outcome: Literal["success", "failure"] = "success"
