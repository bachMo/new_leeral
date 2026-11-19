import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import Schema

Sender = Literal["contact", "bot", "admin"]
ThreadFilter = Literal["all", "unread", "open", "paused"]


class AdminOut(Schema):
    id: uuid.UUID
    email: str
    name: str


class AdminLoginIn(Schema):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class AdminRefreshIn(Schema):
    refresh_token: str = Field(min_length=1, max_length=256)


class AdminTokenOut(Schema):
    access_token: str
    refresh_token: str
    expires_in: int
    admin: AdminOut


class LocationOut(Schema):
    latitude: float
    longitude: float
    name: str | None = None
    address: str | None = None


class SharedContactOut(Schema):
    name: str
    phones: list[str]


class QuotedOut(Schema):
    id: uuid.UUID
    sender: Sender
    type: str
    body: str | None


class ReactionOut(Schema):
    target_id: uuid.UUID | None
    target_wa_id: str
    emoji: str


class MessageOut(Schema):
    id: uuid.UUID
    wa_message_id: str
    direction: Literal["inbound", "outbound"]
    sender: Sender
    admin_name: str | None
    type: str
    body: str | None
    status: str
    error: str | None
    has_media: bool
    media_mime: str | None
    filename: str | None
    voice: bool
    template_name: str | None
    location: LocationOut | None
    contacts: list[SharedContactOut]
    reply_to: QuotedOut | None
    reaction: ReactionOut | None
    created_at: datetime
    updated_at: datetime


class LastMessageOut(Schema):
    id: uuid.UUID
    sender: Sender
    type: str
    body: str | None
    status: str
    created_at: datetime


class ThreadOut(Schema):
    id: uuid.UUID
    wa_phone: str
    phone: str
    name: str | None
    language: str | None
    last_message: LastMessageOut
    unread_count: int
    last_inbound_at: datetime | None
    window_expires_at: datetime | None
    window_open: bool
    bot_paused: bool
    bot_paused_manual: bool
    bot_paused_until: datetime | None


class ThreadPageOut(Schema):
    items: list[ThreadOut]
    has_more: bool
    unread_threads: int
    server_time: datetime


class PlanOut(Schema):
    code: str
    expires_at: datetime | None


class ThreadDetailOut(ThreadOut):
    user_id: uuid.UUID | None
    whatsapp_name: str | None
    first_name: str | None
    registered: bool
    plan: PlanOut | None
    documents_count: int
    first_contact_at: datetime | None
    last_seen_at: datetime | None
    channel_number: str


class MessagePageOut(Schema):
    items: list[MessageOut]
    has_more: bool
    server_time: datetime


class BotStateIn(Schema):
    paused: bool


class MediaLinkOut(Schema):
    url: str
    mime_type: str | None
    filename: str | None
