from fastapi import APIRouter, status

from app.api.deps import BillingServiceDep, CurrentAccount, PresenterDep
from app.schemas.billing import CheckoutIn, PaymentOut, PlanOut, SimulatedOutcomeIn

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans", response_model=list[PlanOut])
async def plans(service: BillingServiceDep) -> list[PlanOut]:
    return [PlanOut.model_validate(plan) for plan in await service.plans()]


@router.post("/checkout", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
async def checkout(
    body: CheckoutIn, user: CurrentAccount, service: BillingServiceDep, presenter: PresenterDep
) -> PaymentOut:
    payment = await service.checkout(user, body.plan_code, body.method, body.payer_phone)
    return presenter.payment(payment)


@router.get("/payments/{public_token}", response_model=PaymentOut)
async def read_payment(
    public_token: str, user: CurrentAccount, service: BillingServiceDep, presenter: PresenterDep
) -> PaymentOut:
    return presenter.payment(await service.payment(user, public_token))


@router.post("/payments/{public_token}/simulate", response_model=PaymentOut)
async def simulate_payment(
    public_token: str,
    body: SimulatedOutcomeIn,
    user: CurrentAccount,
    service: BillingServiceDep,
    presenter: PresenterDep,
) -> PaymentOut:
    payment = await service.settle_simulated(
        user, public_token, succeeded=body.outcome == "success"
    )
    return presenter.payment(payment)
