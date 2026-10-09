import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import day_period, month_period, utcnow
from app.core.errors import AppError, ErrorCode, NotFoundError
from app.core.phone import normalize_phone_number
from app.core.security import generate_public_token
from app.db.unit_of_work import UnitOfWork
from app.integrations.payments import CheckoutRequest, PaymentGateway
from app.models import Payment, Plan, Subscription, User
from app.models.enums import (
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    PlanCode,
    SubscriptionOrigin,
    UsageFeature,
)
from app.repositories.billing import (
    PaymentRepository,
    PlanRepository,
    SubscriptionRepository,
    UsageRepository,
)
from app.repositories.documents import DocumentRepository
from app.workers.jobs import Job

logger = logging.getLogger("leeral.billing")

BACKFILLED_DOCUMENTS = 10


@dataclass(frozen=True, slots=True)
class Entitlements:
    plan: Plan
    expires_at: datetime | None

    @property
    def is_premium(self) -> bool:
        return self.plan.code == PlanCode.LEERAL_PLUS


@dataclass(frozen=True, slots=True)
class UsageSnapshot:
    writings_used: int
    writings_limit: int
    practice_used: int
    practice_limit: int | None


class EntitlementService:
    def __init__(self, session: AsyncSession) -> None:
        self._plans = PlanRepository(session)
        self._subscriptions = SubscriptionRepository(session)
        self._usage = UsageRepository(session)

    async def for_user(self, user: User) -> Entitlements:
        subscription = await self._subscriptions.active(user.id, utcnow())
        if subscription is not None:
            plan = await self._plans.get(subscription.plan_id)
            if plan is not None:
                return Entitlements(plan=plan, expires_at=subscription.expires_at)
        free = await self._plans.by_code(PlanCode.FREE)
        if free is None:
            raise RuntimeError("the free plan is missing, run the migrations")
        return Entitlements(plan=free, expires_at=None)

    async def consume(self, user: User, feature: UsageFeature) -> None:
        entitlements = await self.for_user(user)
        limit, period = self._limit_and_period(entitlements.plan, feature)
        used = await self._usage.increment(user.id, feature, period)
        if limit is not None and used > limit:
            raise AppError(
                ErrorCode.QUOTA_EXCEEDED,
                fields={"feature": feature.value, "limit": limit, "plan": entitlements.plan.code},
            )

    async def usage(self, user: User) -> UsageSnapshot:
        plan = (await self.for_user(user)).plan
        return UsageSnapshot(
            writings_used=await self._usage.count(user.id, UsageFeature.WRITING, month_period()),
            writings_limit=plan.writings_per_month,
            practice_used=await self._usage.count(user.id, UsageFeature.PRACTICE, day_period()),
            practice_limit=plan.practice_per_day,
        )

    async def has_document_words(self, user: User) -> bool:
        return (await self.for_user(user)).plan.document_words

    @staticmethod
    def _limit_and_period(plan: Plan, feature: UsageFeature) -> tuple[int | None, str]:
        if feature is UsageFeature.WRITING:
            return plan.writings_per_month, month_period()
        if feature is UsageFeature.PRACTICE:
            return plan.practice_per_day, day_period()
        return None, day_period()


class BillingService:
    def __init__(self, uow: UnitOfWork, gateway: PaymentGateway, default_region: str) -> None:
        self._uow = uow
        self._gateway = gateway
        self._default_region = default_region
        self._plans = PlanRepository(uow.session)
        self._payments = PaymentRepository(uow.session)
        self._subscriptions = SubscriptionRepository(uow.session)

    async def plans(self) -> Sequence[Plan]:
        return await self._plans.all()

    async def checkout(
        self,
        user: User,
        plan_code: PlanCode,
        method: PaymentMethod | None,
        payer_phone: str | None,
    ) -> Payment:
        if user.is_guest:
            raise AppError(ErrorCode.ACCOUNT_REQUIRED)
        plan = await self._plans.by_code(plan_code)
        if plan is None or plan.price_xof <= 0:
            raise NotFoundError("plan")
        phone = (
            normalize_phone_number(payer_phone, self._default_region)
            if payer_phone
            else user.phone_number
        )
        payment = self._payments.add(
            Payment(
                user_id=user.id,
                plan_id=plan.id,
                payer_phone=phone,
                amount_xof=plan.price_xof,
                provider=self._gateway.provider,
                method=method,
                public_token=generate_public_token(),
                status=PaymentStatus.PENDING,
            )
        )
        session = await self._gateway.create_checkout(
            CheckoutRequest(
                public_token=payment.public_token,
                amount_xof=payment.amount_xof,
                method=method,
                payer_phone=phone,
                description=f"Leeral+ {plan.duration_days} jours",
            )
        )
        payment.provider_ref = session.provider_ref
        payment.raw_payload = {"checkout_url": session.checkout_url}
        await self._uow.commit()
        return payment

    async def payment(self, user: User, public_token: str) -> Payment:
        payment = await self._payments.by_public_token(public_token)
        if payment is None or payment.user_id != user.id:
            raise NotFoundError("payment")
        return payment

    async def settle_simulated(self, user: User, public_token: str, *, succeeded: bool) -> Payment:
        payment = await self.payment(user, public_token)
        if payment.provider != PaymentProvider.SIMULATED:
            raise AppError(ErrorCode.FORBIDDEN)
        if payment.status != PaymentStatus.PENDING:
            raise AppError(ErrorCode.PAYMENT_NOT_PENDING)
        now = utcnow()
        if not succeeded:
            payment.status = PaymentStatus.FAILED
            await self._uow.commit()
            return payment
        payment.status = PaymentStatus.SUCCEEDED
        payment.paid_at = now
        await self._grant(payment, now)
        await self._uow.commit()
        logger.info("payment_succeeded", extra={"payment_id": str(payment.id)})
        return payment

    async def _grant(self, payment: Payment, now: datetime) -> None:
        plan = await self._plans.get(payment.plan_id)
        if plan is None or plan.duration_days is None:
            raise NotFoundError("plan")
        latest = await self._subscriptions.latest_expiry(payment.user_id)
        starts_at = max(now, latest) if latest else now
        self._subscriptions.add(
            Subscription(
                user_id=payment.user_id,
                plan_id=plan.id,
                origin=SubscriptionOrigin.PAYMENT,
                payment_id=payment.id,
                started_at=starts_at,
                expires_at=starts_at + timedelta(days=plan.duration_days),
            )
        )
        if plan.document_words:
            await self._learn_from_past_documents(payment.user_id)

    async def _learn_from_past_documents(self, user_id: uuid.UUID) -> None:
        documents = await DocumentRepository(self._uow.session).ready_without_words(
            user_id, BACKFILLED_DOCUMENTS
        )
        for document_id in documents:
            self._uow.defer(
                Job.EXTRACT_WORDS, key=f"words:{document_id}", document_id=str(document_id)
            )
