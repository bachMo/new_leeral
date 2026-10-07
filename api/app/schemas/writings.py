import uuid
from datetime import datetime

from app.models.enums import WritingOutputKind, WritingStatus, WritingType
from app.schemas.common import Schema


class WritingStepSpecOut(Schema):
    key: str
    question_fr: str
    required: bool


class WritingTypeOut(Schema):
    type: WritingType
    title_fr: str
    description_fr: str
    steps: list[WritingStepSpecOut]


class WritingStartIn(Schema):
    type: WritingType


class WritingConfirmIn(Schema):
    accepted: bool


class WritingStepOut(Schema):
    position: int
    field_key: str
    question_fr: str
    required: bool
    question_message_id: uuid.UUID
    understood_value: str | None
    confirmed: bool


class WritingOutputOut(Schema):
    id: uuid.UUID
    version: int
    kind: WritingOutputKind
    content: str
    pdf_url: str
    readback_audio_url: str | None
    created_at: datetime


class WritingOut(Schema):
    id: uuid.UUID
    type: WritingType
    title_fr: str
    status: WritingStatus
    conversation_id: uuid.UUID
    current_step: int
    total_steps: int
    steps: list[WritingStepOut]
    outputs: list[WritingOutputOut]
    created_at: datetime
