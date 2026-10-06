from typing import Any

from pydantic import BaseModel, ConfigDict


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ErrorBody(Schema):
    code: str
    message: str
    message_key: str
    audio_key: str
    retryable: bool
    request_id: str | None = None
    fields: dict[str, Any] = {}


class ErrorEnvelope(Schema):
    error: ErrorBody


class Accepted(Schema):
    status: str = "accepted"
