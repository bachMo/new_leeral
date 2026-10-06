import logging
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response, status
from pydantic import ValidationError

from app.api.deps import Container, Uow
from app.channels.whatsapp.ingestion import WebhookIngestor
from app.core.errors import AppError, ErrorCode
from app.integrations.whatsapp.payloads import WebhookPayload
from app.integrations.whatsapp.signature import is_valid_signature

logger = logging.getLogger("leeral.webhooks")

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/whatsapp", response_class=Response)
async def verify_whatsapp(
    container: Container,
    mode: Annotated[str, Query(alias="hub.mode")],
    token: Annotated[str, Query(alias="hub.verify_token")],
    challenge: Annotated[str, Query(alias="hub.challenge")],
) -> Response:
    expected = container.settings.whatsapp_verify_token.get_secret_value()
    if mode != "subscribe" or not expected or token != expected:
        raise AppError(ErrorCode.FORBIDDEN)
    return Response(content=challenge, media_type="text/plain")


@router.post("/whatsapp", status_code=status.HTTP_200_OK)
async def receive_whatsapp(request: Request, container: Container, uow: Uow) -> dict[str, int]:
    body = await request.body()
    secret = container.settings.meta_app_secret.get_secret_value()
    if not is_valid_signature(secret, body, request.headers.get("X-Hub-Signature-256")):
        raise AppError(ErrorCode.WEBHOOK_SIGNATURE_INVALID)
    try:
        payload = WebhookPayload.model_validate_json(body)
    except ValidationError:
        logger.warning("whatsapp_payload_invalid")
        return {"accepted": 0}
    accepted = await WebhookIngestor(uow, container.settings).ingest(payload)
    return {"accepted": accepted}
