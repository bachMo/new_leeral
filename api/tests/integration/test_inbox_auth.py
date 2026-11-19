import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import AccessTokenClaims
from app.models import AdminUser
from tests.integration.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, Harness


async def test_login_returns_tokens_and_profile(harness: Harness) -> None:
    response = await harness.client.post(
        "/v1/admin/auth/login", json={"email": " Bachir@Example.com ", "password": ADMIN_PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["admin"]["email"] == ADMIN_EMAIL
    assert body["expires_in"] == 15 * 60
    assert response.headers["cache-control"] == "no-store"
    me = await harness.client.get(
        "/v1/admin/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.json()["name"] == "Bachir"


async def test_wrong_password_and_unknown_email_look_the_same(harness: Harness) -> None:
    wrong = await harness.client.post(
        "/v1/admin/auth/login", json={"email": ADMIN_EMAIL, "password": "pas le bon"}
    )
    unknown = await harness.client.post(
        "/v1/admin/auth/login", json={"email": "x@example.com", "password": "pas le bon"}
    )

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["code"] == unknown.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_account_locks_after_repeated_failures(
    harness: Harness, session: AsyncSession
) -> None:
    for _ in range(harness.settings.admin_max_failed_logins):
        await harness.client.post(
            "/v1/admin/auth/login", json={"email": ADMIN_EMAIL, "password": "faux"}
        )

    locked = await harness.client.post(
        "/v1/admin/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )

    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "ACCOUNT_LOCKED"
    admin = await session.scalar(select(AdminUser).where(AdminUser.email == ADMIN_EMAIL))
    assert admin is not None and admin.locked_until is not None


async def test_refresh_rotates_the_token(harness: Harness) -> None:
    first = (
        await harness.client.post(
            "/v1/admin/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
    ).json()

    rotated = await harness.client.post(
        "/v1/admin/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )
    replayed = await harness.client.post(
        "/v1/admin/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )

    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != first["refresh_token"]
    assert replayed.status_code == 401


async def test_logout_closes_the_session(harness: Harness) -> None:
    headers = await harness.login()

    assert (await harness.client.post("/v1/admin/auth/logout", headers=headers)).status_code == 204
    after = await harness.client.get("/v1/admin/me", headers=headers)

    assert after.status_code == 401


async def test_disabled_admin_is_rejected_immediately(
    harness: Harness, session: AsyncSession
) -> None:
    headers = await harness.login()
    admin = await session.scalar(select(AdminUser).where(AdminUser.email == ADMIN_EMAIL))
    assert admin is not None
    admin.is_active = False
    await session.commit()

    assert (await harness.client.get("/v1/admin/me", headers=headers)).status_code == 401


async def test_app_user_token_cannot_open_the_inbox(harness: Harness) -> None:
    token = harness.tokens.issue_access_token(
        AccessTokenClaims(user_id=uuid.uuid4(), session_id=uuid.uuid4(), is_guest=False)
    )

    response = await harness.client.get(
        "/v1/admin/inbox/threads", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


async def test_inbox_requires_authentication(harness: Harness) -> None:
    assert (await harness.client.get("/v1/admin/inbox/threads")).status_code == 401
