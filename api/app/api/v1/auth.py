from fastapi import APIRouter, status

from app.api.deps import AuthServiceDep, CurrentPrincipal, MaybePrincipal, PresenterDep
from app.schemas.auth import (
    GuestIn,
    OtpChallengeOut,
    OtpRequestIn,
    OtpVerifyIn,
    RefreshIn,
    TokenOut,
)
from app.services.auth_service import AuthResult, DeviceInfo

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens(result: AuthResult, presenter: PresenterDep) -> TokenOut:
    return TokenOut(
        access_token=result.tokens.access_token,
        refresh_token=result.tokens.refresh_token,
        expires_in=result.tokens.expires_in,
        is_new_account=result.is_new_account,
        user=presenter.user(result.user),
    )


@router.post("/guest", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def start_guest(body: GuestIn, service: AuthServiceDep, presenter: PresenterDep) -> TokenOut:
    result = await service.start_guest(
        body.device_id,
        body.language,
        DeviceInfo(body.platform, body.device_name, body.push_token),
    )
    return _tokens(result, presenter)


@router.post("/otp/request", response_model=OtpChallengeOut)
async def request_otp(body: OtpRequestIn, service: AuthServiceDep) -> OtpChallengeOut:
    challenge = await service.request_otp(body.phone_number)
    return OtpChallengeOut.model_validate(challenge)


@router.post("/otp/verify", response_model=TokenOut)
async def verify_otp(
    body: OtpVerifyIn,
    service: AuthServiceDep,
    presenter: PresenterDep,
    principal: MaybePrincipal,
) -> TokenOut:
    result = await service.verify_otp(
        body.phone_number,
        body.code,
        body.language,
        DeviceInfo(body.platform, body.device_name, body.push_token),
        guest=principal.user if principal and principal.user.is_guest else None,
    )
    return _tokens(result, presenter)


@router.post("/refresh", response_model=TokenOut)
async def refresh(body: RefreshIn, service: AuthServiceDep, presenter: PresenterDep) -> TokenOut:
    return _tokens(await service.refresh(body.refresh_token), presenter)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(principal: CurrentPrincipal, service: AuthServiceDep) -> None:
    await service.logout(principal.claims.session_id)
