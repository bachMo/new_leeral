import hashlib
import hmac
import uuid

import pytest

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.phone import normalize_phone_number
from app.core.security import AccessTokenClaims, TokenService
from app.integrations.whatsapp.signature import is_valid_signature


@pytest.fixture
def tokens() -> TokenService:
    return TokenService(Settings(jwt_secret="x" * 40))


def test_access_token_round_trip(tokens: TokenService) -> None:
    claims = AccessTokenClaims(user_id=uuid.uuid4(), session_id=uuid.uuid4(), is_guest=True)

    assert tokens.decode_access_token(tokens.issue_access_token(claims)) == claims


def test_tampered_token_is_rejected(tokens: TokenService) -> None:
    token = tokens.issue_access_token(
        AccessTokenClaims(user_id=uuid.uuid4(), session_id=uuid.uuid4(), is_guest=False)
    )

    with pytest.raises(AppError) as error:
        tokens.decode_access_token(token[:-2] + "aa")

    assert error.value.code is ErrorCode.UNAUTHENTICATED


def test_short_secret_is_refused() -> None:
    with pytest.raises(RuntimeError):
        TokenService(Settings(jwt_secret="short"))


@pytest.mark.parametrize("raw", ["77 123 45 67", "+221771234567", "221771234567"])
def test_senegalese_numbers_are_normalized(raw: str) -> None:
    assert normalize_phone_number(raw, "SN") == "+221771234567"


def test_invalid_number_is_rejected() -> None:
    with pytest.raises(AppError) as error:
        normalize_phone_number("12", "SN")

    assert error.value.code is ErrorCode.INVALID_PHONE_NUMBER


def test_webhook_signature() -> None:
    body = b'{"object":"whatsapp_business_account"}'
    signature = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()

    assert is_valid_signature("secret", body, signature)
    assert not is_valid_signature("secret", body + b" ", signature)
    assert not is_valid_signature("", body, signature)
