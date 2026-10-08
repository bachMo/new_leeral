import logging
from typing import Protocol

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.logging import mask_phone
from app.core.phone import to_whatsapp_id
from app.integrations.whatsapp.client import WhatsAppClient, WhatsAppError

logger = logging.getLogger("leeral.otp")


class OtpDelivery(Protocol):
    async def deliver(self, phone_number: str, code: str) -> None: ...


class WhatsAppOtpDelivery:
    def __init__(self, settings: Settings, client: WhatsAppClient) -> None:
        self._settings = settings
        self._client = client

    async def deliver(self, phone_number: str, code: str) -> None:
        try:
            await self._client.send_otp_template(
                self._settings.whatsapp_default_phone_id,
                to_whatsapp_id(phone_number),
                self._settings.whatsapp_otp_template,
                self._settings.whatsapp_template_language,
                code,
            )
        except WhatsAppError as exc:
            logger.warning("otp_delivery_failed", extra={"phone": mask_phone(phone_number)})
            raise AppError(ErrorCode.OTP_DELIVERY_FAILED) from exc


class ConsoleOtpDelivery:
    async def deliver(self, phone_number: str, code: str) -> None:
        logger.warning(
            "development_otp_code", extra={"phone": mask_phone(phone_number), "code": code}
        )


class DemoOtpDelivery:
    async def deliver(self, phone_number: str, code: str) -> None:
        logger.info("demo_otp_issued", extra={"phone": mask_phone(phone_number)})


def build_otp_delivery(settings: Settings, client: WhatsAppClient) -> OtpDelivery:
    if settings.otp_delivery == "demo":
        code = settings.otp_demo_code.get_secret_value()
        if not code.isdigit() or len(code) != settings.otp_length:
            raise RuntimeError("OTP_DEMO_CODE must contain exactly OTP_LENGTH digits")
        return DemoOtpDelivery()
    if settings.otp_delivery == "console":
        if settings.environment == "production":
            raise RuntimeError("OTP_DELIVERY=console is not allowed in production")
        return ConsoleOtpDelivery()
    return WhatsAppOtpDelivery(settings, client)
