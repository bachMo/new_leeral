from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.ai.engine import AiEngine
from app.api.presenters import Presenter
from app.core.config import Settings, get_settings
from app.core.errors import AppError, ErrorCode
from app.core.security import AccessTokenClaims, TokenService
from app.db.session import get_session_factory
from app.db.unit_of_work import UnitOfWork
from app.integrations.payments import PaymentGateway
from app.integrations.storage import FileStorage
from app.integrations.whatsapp.client import WhatsAppClient
from app.models import User
from app.repositories.users import UserRepository
from app.services.auth_service import AuthService
from app.services.billing_service import BillingService, EntitlementService
from app.services.conversation_service import ConversationService
from app.services.document_service import DocumentService
from app.services.learning_service import LearningService
from app.services.otp_delivery import OtpDelivery
from app.services.user_service import UserService
from app.services.writing_service import WritingService
from app.workers.queue import JobQueue

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class AppContainer:
    settings: Settings
    ai: AiEngine
    storage: FileStorage
    queue: JobQueue
    tokens: TokenService
    whatsapp: WhatsAppClient
    otp_delivery: OtpDelivery
    payments: PaymentGateway


def get_container(request: Request) -> AppContainer:
    container: AppContainer = request.app.state.container
    return container


Container = Annotated[AppContainer, Depends(get_container)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_uow(container: Container) -> AsyncIterator[UnitOfWork]:
    async with get_session_factory()() as session:
        yield UnitOfWork(session, container.queue)


Uow = Annotated[UnitOfWork, Depends(get_uow)]


@dataclass(frozen=True, slots=True)
class Principal:
    user: User
    claims: AccessTokenClaims


async def _principal(
    container: Container,
    uow: Uow,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal | None:
    if credentials is None:
        return None
    claims = container.tokens.decode_access_token(credentials.credentials)
    user = await UserRepository(uow.session).get(claims.user_id)
    if user is None:
        raise AppError(ErrorCode.UNAUTHENTICATED)
    return Principal(user=user, claims=claims)


async def optional_principal(
    principal: Annotated[Principal | None, Depends(_principal)],
) -> Principal | None:
    return principal


async def require_principal(
    principal: Annotated[Principal | None, Depends(_principal)],
) -> Principal:
    if principal is None:
        raise AppError(ErrorCode.UNAUTHENTICATED)
    return principal


async def require_user(principal: Annotated[Principal, Depends(require_principal)]) -> User:
    return principal.user


async def require_account(user: Annotated[User, Depends(require_user)]) -> User:
    if user.is_guest:
        raise AppError(ErrorCode.ACCOUNT_REQUIRED)
    return user


CurrentPrincipal = Annotated[Principal, Depends(require_principal)]
MaybePrincipal = Annotated[Principal | None, Depends(optional_principal)]
CurrentUser = Annotated[User, Depends(require_user)]
CurrentAccount = Annotated[User, Depends(require_account)]


def get_presenter(container: Container) -> Presenter:
    return Presenter(container.storage)


PresenterDep = Annotated[Presenter, Depends(get_presenter)]


def get_auth_service(uow: Uow, container: Container) -> AuthService:
    return AuthService(uow, container.settings, container.tokens, container.otp_delivery)


def get_user_service(uow: Uow) -> UserService:
    return UserService(uow)


def get_entitlement_service(uow: Uow) -> EntitlementService:
    return EntitlementService(uow.session)


def get_document_service(uow: Uow, container: Container) -> DocumentService:
    return DocumentService(uow, container.ai, container.storage, container.settings)


def get_conversation_service(uow: Uow, container: Container) -> ConversationService:
    return ConversationService(uow, container.storage, container.settings)


def get_writing_service(
    uow: Uow, conversations: Annotated[ConversationService, Depends(get_conversation_service)]
) -> WritingService:
    return WritingService(uow, conversations)


def get_learning_service(uow: Uow, container: Container) -> LearningService:
    return LearningService(uow, container.settings)


def get_billing_service(uow: Uow, container: Container) -> BillingService:
    return BillingService(uow, container.payments, container.settings.default_phone_region)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
EntitlementServiceDep = Annotated[EntitlementService, Depends(get_entitlement_service)]
DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
ConversationServiceDep = Annotated[ConversationService, Depends(get_conversation_service)]
WritingServiceDep = Annotated[WritingService, Depends(get_writing_service)]
LearningServiceDep = Annotated[LearningService, Depends(get_learning_service)]
BillingServiceDep = Annotated[BillingService, Depends(get_billing_service)]
