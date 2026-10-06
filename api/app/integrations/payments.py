import uuid
from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings
from app.models.enums import PaymentMethod, PaymentProvider


@dataclass(frozen=True, slots=True)
class CheckoutRequest:
    public_token: str
    amount_xof: int
    method: PaymentMethod | None
    payer_phone: str | None
    description: str


@dataclass(frozen=True, slots=True)
class CheckoutSession:
    provider_ref: str
    checkout_url: str | None


class PaymentGateway(Protocol):
    @property
    def provider(self) -> PaymentProvider: ...

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutSession: ...


class SimulatedGateway:
    @property
    def provider(self) -> PaymentProvider:
        return PaymentProvider.SIMULATED

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        return CheckoutSession(provider_ref=f"sim_{uuid.uuid4().hex[:16]}", checkout_url=None)


def build_payment_gateway(settings: Settings) -> PaymentGateway:
    if settings.payment_provider == "simulated":
        return SimulatedGateway()
    raise ValueError(f"unsupported payment provider: {settings.payment_provider}")
