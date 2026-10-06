from app.core.clock import utcnow
from app.core.errors import AppError, ErrorCode
from app.core.languages import Language, ensure_available
from app.db.unit_of_work import UnitOfWork
from app.integrations.storage import owner_prefix
from app.models import User
from app.repositories.users import UserRepository
from app.workers.jobs import Job


class UserService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow
        self._users = UserRepository(uow.session)

    async def update_profile(
        self,
        user: User,
        *,
        first_name: str | None = None,
        language: Language | None = None,
        accept_terms: bool | None = None,
    ) -> User:
        if first_name is not None:
            if user.is_guest:
                raise AppError(ErrorCode.ACCOUNT_REQUIRED)
            user.first_name = first_name.strip()
        if language is not None:
            user.language = ensure_available(language)
        if accept_terms:
            user.terms_accepted_at = user.terms_accepted_at or utcnow()
        elif accept_terms is False:
            raise AppError(ErrorCode.TERMS_NOT_ACCEPTED)
        await self._uow.commit()
        return user

    async def delete_account(self, user: User) -> None:
        prefixes = {owner_prefix(user.id, is_guest=True), owner_prefix(user.id, is_guest=False)}
        await self._users.delete(user)
        for prefix in sorted(prefixes):
            self._uow.defer(Job.DELETE_STORAGE_PREFIX, prefix=prefix)
        await self._uow.commit()
