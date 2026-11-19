import uuid

import pytest

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.passwords import hash_password, verify_password
from app.core.security import AccessTokenClaims, AdminTokenClaims, TokenService


@pytest.fixture
def tokens() -> TokenService:
    return TokenService(Settings(jwt_secret="x" * 40))


def test_password_round_trip() -> None:
    encoded = hash_password("un mot de passe solide")

    assert encoded.startswith("scrypt$")
    assert verify_password("un mot de passe solide", encoded)
    assert not verify_password("un mot de passe faux", encoded)


def test_same_password_gets_a_new_salt() -> None:
    assert hash_password("identique-identique") != hash_password("identique-identique")


@pytest.mark.parametrize(
    "encoded", ["", "scrypt$1$2", "bcrypt$16384$8$1$aaaa$bbbb", "scrypt$x$8$1$a$b"]
)
def test_malformed_hash_never_verifies(encoded: str) -> None:
    assert not verify_password("anything", encoded)


def test_admin_token_round_trip(tokens: TokenService) -> None:
    claims = AdminTokenClaims(admin_id=uuid.uuid4(), session_id=uuid.uuid4())

    assert tokens.decode_admin_token(tokens.issue_admin_token(claims)) == claims


def test_user_token_cannot_open_the_inbox(tokens: TokenService) -> None:
    user_token = tokens.issue_access_token(
        AccessTokenClaims(user_id=uuid.uuid4(), session_id=uuid.uuid4(), is_guest=False)
    )

    with pytest.raises(AppError) as error:
        tokens.decode_admin_token(user_token)

    assert error.value.code is ErrorCode.UNAUTHENTICATED


def test_admin_token_cannot_be_used_as_a_user_token(tokens: TokenService) -> None:
    admin_token = tokens.issue_admin_token(
        AdminTokenClaims(admin_id=uuid.uuid4(), session_id=uuid.uuid4())
    )

    with pytest.raises(AppError):
        tokens.decode_access_token(admin_token)
