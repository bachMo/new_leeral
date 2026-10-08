from typing import cast

import pytest

from app.core.config import Settings
from app.integrations.whatsapp.client import WhatsAppClient
from app.services.otp_delivery import DemoOtpDelivery, build_otp_delivery

CLIENT = cast(WhatsAppClient, object())


def test_demo_delivery_is_built_with_a_valid_code() -> None:
    settings = Settings(otp_delivery="demo", otp_demo_code="2026", otp_length=4)

    assert isinstance(build_otp_delivery(settings, CLIENT), DemoOtpDelivery)


def test_demo_delivery_is_allowed_in_production() -> None:
    settings = Settings(
        environment="production", otp_delivery="demo", otp_demo_code="2026", otp_length=4
    )

    assert isinstance(build_otp_delivery(settings, CLIENT), DemoOtpDelivery)


@pytest.mark.parametrize("code", ["", "12", "12345", "12a4"])
def test_demo_delivery_refuses_an_invalid_code(code: str) -> None:
    settings = Settings(otp_delivery="demo", otp_demo_code=code, otp_length=4)

    with pytest.raises(RuntimeError):
        build_otp_delivery(settings, CLIENT)
