import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Entity, TextEnum
from app.models.enums import (
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    PlanCode,
    SubscriptionOrigin,
    UsageFeature,
)


class Plan(Entity):
    __tablename__ = "plans"

    code: Mapped[PlanCode] = mapped_column(TextEnum(PlanCode), unique=True)
    price_xof: Mapped[int]
    duration_days: Mapped[int | None]
    writings_per_month: Mapped[int]
    practice_per_day: Mapped[int | None]
    document_words: Mapped[bool]


class Payment(Entity):
    __tablename__ = "payments"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"))
    payer_phone: Mapped[str | None]
    amount_xof: Mapped[int]
    provider: Mapped[PaymentProvider] = mapped_column(TextEnum(PaymentProvider))
    method: Mapped[PaymentMethod | None] = mapped_column(TextEnum(PaymentMethod))
    public_token: Mapped[str] = mapped_column(unique=True)
    provider_ref: Mapped[str | None]
    status: Mapped[PaymentStatus] = mapped_column(
        TextEnum(PaymentStatus), default=PaymentStatus.PENDING
    )
    paid_at: Mapped[datetime | None]
    raw_payload: Mapped[dict[str, Any] | None]


class Subscription(Entity):
    __tablename__ = "subscriptions"
    __table_args__ = (Index("ix_subscriptions_user_expires", "user_id", "expires_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"))
    origin: Mapped[SubscriptionOrigin] = mapped_column(TextEnum(SubscriptionOrigin))
    payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payments.id"), unique=True)
    started_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    reminder_sent_at: Mapped[datetime | None]


class UsageCounter(Entity):
    __tablename__ = "usage_counters"
    __table_args__ = (UniqueConstraint("user_id", "feature", "period"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    feature: Mapped[UsageFeature] = mapped_column(TextEnum(UsageFeature))
    period: Mapped[str]
    count: Mapped[int] = mapped_column(default=0)
