import uuid
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert

from app.core.clock import utcnow
from app.core.languages import Language
from app.models import AuthSession, OtpCode, User
from app.repositories.base import Repository


class UserRepository(Repository[User]):
    model = User

    async def by_phone(self, phone_number: str) -> User | None:
        return await self.session.scalar(select(User).where(User.phone_number == phone_number))

    async def by_device(self, device_id: str) -> User | None:
        return await self.session.scalar(select(User).where(User.guest_device_id == device_id))

    async def insert_if_absent(
        self, *, phone_number: str, whatsapp_name: str | None, language: Language
    ) -> bool:
        now = utcnow()
        inserted = await self.session.scalar(
            insert(User)
            .values(
                phone_number=phone_number,
                whatsapp_name=whatsapp_name,
                language=language,
                registered_at=now,
                last_seen_at=now,
            )
            .on_conflict_do_nothing(index_elements=["phone_number"])
            .returning(User.id)
        )
        return inserted is not None

    async def touch(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(last_seen_at=func.now())
        )

    async def inactive_guest_ids(self, before: datetime, limit: int) -> list[uuid.UUID]:
        rows = await self.session.scalars(
            select(User.id)
            .where(User.is_guest.is_(True), User.last_seen_at < before)
            .order_by(User.last_seen_at)
            .limit(limit)
        )
        return list(rows)

    async def delete_by_ids(self, user_ids: list[uuid.UUID]) -> None:
        await self.session.execute(delete(User).where(User.id.in_(user_ids)))


class OtpRepository(Repository[OtpCode]):
    model = OtpCode

    async def latest_for(self, phone_number: str) -> OtpCode | None:
        return await self.session.scalar(
            select(OtpCode)
            .where(OtpCode.phone_number == phone_number)
            .order_by(OtpCode.created_at.desc())
            .limit(1)
            .with_for_update()
        )

    async def delete_expired(self, before: datetime) -> int:
        deleted = await self.session.scalars(
            delete(OtpCode).where(OtpCode.expires_at < before).returning(OtpCode.id)
        )
        return len(deleted.all())


class AuthSessionRepository(Repository[AuthSession]):
    model = AuthSession

    async def by_refresh_hash(self, token_hash: str) -> AuthSession | None:
        return await self.session.scalar(
            select(AuthSession)
            .where(AuthSession.refresh_token_hash == token_hash)
            .with_for_update()
        )

    async def revoke_all_for(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=func.now())
        )

    async def move_to(self, source_user_id: uuid.UUID, target_user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == source_user_id)
            .values(user_id=target_user_id)
        )
