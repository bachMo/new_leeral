from app.core.config import Settings
from app.services.auth_service import public_demo_code


def test_demo_code_is_shared_when_codes_are_not_delivered() -> None:
    settings = Settings(otp_delivery="demo", otp_demo_code="2207", otp_length=4)

    assert public_demo_code(settings) == "2207"


def test_demo_code_is_never_shared_when_codes_are_delivered_on_whatsapp() -> None:
    settings = Settings(otp_delivery="whatsapp", otp_demo_code="2207", otp_length=4)

    assert public_demo_code(settings) is None
