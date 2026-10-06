from fastapi import APIRouter, status

from app.api.deps import CurrentUser, EntitlementServiceDep, PresenterDep, UserServiceDep
from app.models import User
from app.schemas.users import MeOut, PlanStatusOut, ProfileIn, UsageOut
from app.services.billing_service import EntitlementService

router = APIRouter(prefix="/me", tags=["account"])


async def _me(user: User, entitlements: EntitlementService, presenter: PresenterDep) -> MeOut:
    current = await entitlements.for_user(user)
    usage = await entitlements.usage(user)
    return MeOut(
        user=presenter.user(user),
        plan=PlanStatusOut(
            code=current.plan.code,
            expires_at=current.expires_at,
            document_words=current.plan.document_words,
        ),
        usage=UsageOut.model_validate(usage),
    )


@router.get("", response_model=MeOut)
async def read_me(
    user: CurrentUser, entitlements: EntitlementServiceDep, presenter: PresenterDep
) -> MeOut:
    return await _me(user, entitlements, presenter)


@router.patch("", response_model=MeOut)
async def update_me(
    body: ProfileIn,
    user: CurrentUser,
    service: UserServiceDep,
    entitlements: EntitlementServiceDep,
    presenter: PresenterDep,
) -> MeOut:
    updated = await service.update_profile(
        user,
        first_name=body.first_name,
        language=body.language,
        accept_terms=body.accept_terms,
    )
    return await _me(updated, entitlements, presenter)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(user: CurrentUser, service: UserServiceDep) -> None:
    await service.delete_account(user)
