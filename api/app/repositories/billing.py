import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.models import Payment, Plan, Subscription, UsageCounter
from app.models.enums import PlanCode, UsageFeature
from app.repositories.base import Repository


class PlanRepository(Repository[Plan]):
    model = Plan

    async def by_code(self, code: PlanCode) -> Plan | None:
        return await self.session.scalar(select(Plan).where(Plan.code == code))

    async def all(self) -> Sequence[Plan]:
        return (await self.session.scalars(select(Plan).order_by(Plan.price_xof))).all()


class PaymentRepository(Repository[Payment]):
    model = Payment

    async def by_public_token(self, token: str) -> Payment | None:
        return await self.session.scalar(
            select(Payment).where(Payment.public_token == token).with_for_update()
        )


class SubscriptionRepository(Repository[Subscription]):
    model = Subscription

    async def active(self, user_id: uuid.UUID, now: datetime) -> Subscription | None:
        return await self.session.scalar(
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.started_at <= now,
                Subscription.expires_at > now,
            )
            .order_by(Subscription.expires_at.desc())
            .limit(1)
        )

    async def latest_expiry(self, user_id: uuid.UUID) -> datetime | None:
        return await self.session.scalar(
            select(Subscription.expires_at)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.expires_at.desc())
            .limit(1)
        )

    async def expiring_between(
        self, start: datetime, end: datetime, limit: int
    ) -> Sequence[Subscription]:
        return (
            await self.session.scalars(
                select(Subscription)
                .where(
                    Subscription.expires_at >= start,
                    Subscription.expires_at < end,
                    Subscription.reminder_sent_at.is_(None),
                )
                .order_by(Subscription.expires_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()


class UsageRepository(Repository[UsageCounter]):
    model = UsageCounter

    async def increment(self, user_id: uuid.UUID, feature: UsageFeature, period: str) -> int:
        statement = (
            insert(UsageCounter)
            .values(user_id=user_id, feature=feature.value, period=period, count=1)
            .on_conflict_do_update(
                index_elements=["user_id", "feature", "period"],
                set_={"count": UsageCounter.count + 1},
            )
            .returning(UsageCounter.count)
        )
        return int((await self.session.execute(statement)).scalar_one())

    async def count(self, user_id: uuid.UUID, feature: UsageFeature, period: str) -> int:
        value = await self.session.scalar(
            select(UsageCounter.count).where(
                UsageCounter.user_id == user_id,
                UsageCounter.feature == feature,
                UsageCounter.period == period,
            )
        )
        return int(value or 0)
