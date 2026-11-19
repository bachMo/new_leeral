from sqlalchemy import select

from app.models import AdminSession, AdminUser
from app.repositories.base import Repository


class AdminUserRepository(Repository[AdminUser]):
    model = AdminUser

    async def by_email(self, email: str) -> AdminUser | None:
        return await self.session.scalar(select(AdminUser).where(AdminUser.email == email))


class AdminSessionRepository(Repository[AdminSession]):
    model = AdminSession

    async def by_refresh_hash(self, refresh_hash: str) -> AdminSession | None:
        return await self.session.scalar(
            select(AdminSession).where(AdminSession.refresh_token_hash == refresh_hash)
        )
