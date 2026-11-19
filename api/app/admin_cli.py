import getpass
import os

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.passwords import MIN_PASSWORD_LENGTH, hash_password
from app.db.session import get_session_factory
from app.models import AdminSession, AdminUser
from app.repositories.admin import AdminUserRepository
from app.services.admin_auth_service import normalize_email

PASSWORD_ENV = "LEERAL_ADMIN_PASSWORD"


def read_password() -> str:
    from_env = os.environ.get(PASSWORD_ENV)
    if from_env:
        password = from_env
    else:
        password = getpass.getpass("Mot de passe : ")
        if getpass.getpass("Confirme le mot de passe : ") != password:
            raise SystemExit("Les deux mots de passe ne correspondent pas.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(f"Le mot de passe doit faire au moins {MIN_PASSWORD_LENGTH} caractères.")
    return password


async def create_admin(email: str, name: str) -> None:
    address = normalize_email(email)
    if "@" not in address:
        raise SystemExit("Adresse e-mail invalide.")
    password = read_password()
    async with get_session_factory()() as session:
        admins = AdminUserRepository(session)
        if await admins.by_email(address) is not None:
            raise SystemExit(f"Un compte existe déjà pour {address}.")
        admins.add(
            AdminUser(
                email=address,
                name=name.strip() or address,
                password_hash=hash_password(password),
                is_active=True,
                failed_attempts=0,
            )
        )
        await session.commit()
    print(f"Compte admin créé : {address}")


async def set_password(email: str) -> None:
    address = normalize_email(email)
    password = read_password()
    async with get_session_factory()() as session:
        admin = await AdminUserRepository(session).by_email(address)
        if admin is None:
            raise SystemExit(f"Aucun compte pour {address}.")
        admin.password_hash = hash_password(password)
        admin.failed_attempts = 0
        admin.locked_until = None
        await _revoke_sessions(session, admin)
        await session.commit()
    print(f"Mot de passe changé pour {address}. Toutes ses sessions sont fermées.")


async def set_active(email: str, *, active: bool) -> None:
    address = normalize_email(email)
    async with get_session_factory()() as session:
        admin = await AdminUserRepository(session).by_email(address)
        if admin is None:
            raise SystemExit(f"Aucun compte pour {address}.")
        admin.is_active = active
        admin.failed_attempts = 0
        admin.locked_until = None
        if not active:
            await _revoke_sessions(session, admin)
        await session.commit()
    print(f"Compte {address} {'activé' if active else 'désactivé'}.")


async def list_admins() -> None:
    async with get_session_factory()() as session:
        admins = (await session.scalars(select(AdminUser).order_by(AdminUser.email))).all()
    if not admins:
        print("Aucun compte admin.")
    for admin in admins:
        state = "actif" if admin.is_active else "désactivé"
        last = admin.last_login_at.strftime("%Y-%m-%d %H:%M") if admin.last_login_at else "jamais"
        print(f"{admin.email}  {admin.name}  {state}  dernière connexion : {last}")


async def _revoke_sessions(session: AsyncSession, admin: AdminUser) -> None:
    await session.execute(
        update(AdminSession)
        .where(AdminSession.admin_id == admin.id, AdminSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
