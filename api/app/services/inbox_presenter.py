import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from app.channels.whatsapp.threads import bot_is_paused
from app.models import User, WhatsAppMessage, WhatsAppThread
from app.models.enums import WhatsAppDirection, WhatsAppMessageType
from app.repositories.inbox import WINDOW, ThreadRow
from app.schemas.inbox import (
    LastMessageOut,
    LocationOut,
    MessageOut,
    QuotedOut,
    ReactionOut,
    Sender,
    SharedContactOut,
    ThreadOut,
)

QUOTE_MAX_LENGTH = 160


def sender_of(message: WhatsAppMessage) -> Sender:
    if message.direction is WhatsAppDirection.INBOUND:
        return "contact"
    return "admin" if message.admin_id is not None else "bot"


def display_body(message: WhatsAppMessage) -> str | None:
    meta = message.meta or {}
    if message.direction is WhatsAppDirection.INBOUND and message.type in {
        WhatsAppMessageType.INTERACTIVE,
        WhatsAppMessageType.BUTTON,
    }:
        title = meta.get("reply_title")
        return str(title) if title else message.body_text
    return message.body_text


def referenced_wa_ids(messages: Sequence[WhatsAppMessage]) -> list[str]:
    ids: list[str] = []
    for message in messages:
        meta = message.meta or {}
        if isinstance(meta.get("reply_to"), str):
            ids.append(meta["reply_to"])
        reaction = meta.get("reaction")
        if isinstance(reaction, dict) and isinstance(reaction.get("target"), str):
            ids.append(reaction["target"])
    return ids


def _location(meta: Mapping[str, Any]) -> LocationOut | None:
    location = meta.get("location")
    if not isinstance(location, dict):
        return None
    try:
        return LocationOut.model_validate(location)
    except ValueError:
        return None


def _contacts(meta: Mapping[str, Any]) -> list[SharedContactOut]:
    contacts = meta.get("contacts")
    if not isinstance(contacts, list):
        return []
    result = []
    for contact in contacts:
        if isinstance(contact, dict):
            phones = [str(phone) for phone in contact.get("phones") or [] if phone]
            result.append(SharedContactOut(name=str(contact.get("name") or ""), phones=phones))
    return result


def _quote(meta: Mapping[str, Any], references: Mapping[str, WhatsAppMessage]) -> QuotedOut | None:
    target = references.get(str(meta.get("reply_to") or ""))
    if target is None:
        return None
    body = display_body(target)
    return QuotedOut(
        id=target.id,
        sender=sender_of(target),
        type=target.type.value,
        body=body[:QUOTE_MAX_LENGTH] if body else None,
    )


def _reaction(
    meta: Mapping[str, Any], references: Mapping[str, WhatsAppMessage]
) -> ReactionOut | None:
    reaction = meta.get("reaction")
    if not isinstance(reaction, dict) or not reaction.get("target"):
        return None
    target_wa_id = str(reaction["target"])
    target = references.get(target_wa_id)
    return ReactionOut(
        target_id=target.id if target else None,
        target_wa_id=target_wa_id,
        emoji=str(reaction.get("emoji") or ""),
    )


def message_out(
    message: WhatsAppMessage,
    references: Mapping[str, WhatsAppMessage],
    admin_names: Mapping[uuid.UUID, str],
) -> MessageOut:
    meta = message.meta or {}
    filename = meta.get("filename")
    return MessageOut(
        id=message.id,
        wa_message_id=message.wa_message_id,
        direction="inbound" if message.direction is WhatsAppDirection.INBOUND else "outbound",
        sender=sender_of(message),
        admin_name=admin_names.get(message.admin_id) if message.admin_id else None,
        type=message.type.value,
        body=display_body(message),
        status=message.status.value,
        error=message.error,
        has_media=bool(message.media_key or message.wa_media_id),
        media_mime=message.media_mime,
        filename=str(filename) if filename else None,
        voice=bool(meta.get("voice")),
        template_name=message.template_name,
        location=_location(meta),
        contacts=_contacts(meta),
        reply_to=_quote(meta, references),
        reaction=_reaction(meta, references),
        created_at=message.created_at,
        updated_at=message.updated_at,
    )


def last_message_out(message: WhatsAppMessage) -> LastMessageOut:
    return LastMessageOut(
        id=message.id,
        sender=sender_of(message),
        type=message.type.value,
        body=display_body(message),
        status=message.status.value,
        created_at=message.created_at,
    )


def display_name(user: User | None) -> str | None:
    if user is None:
        return None
    return user.first_name or user.whatsapp_name


def window_expires(last_inbound_at: datetime | None) -> datetime | None:
    return last_inbound_at + WINDOW if last_inbound_at else None


def thread_fields(row: ThreadRow, now: datetime) -> dict[str, Any]:
    thread: WhatsAppThread = row.thread
    expires = window_expires(row.last_inbound_at)
    return {
        "id": thread.id,
        "wa_phone": thread.wa_phone,
        "phone": f"+{thread.wa_phone}",
        "name": display_name(row.user),
        "language": row.user.language.value if row.user else None,
        "last_message": last_message_out(row.last_message),
        "unread_count": row.unread_count,
        "last_inbound_at": row.last_inbound_at,
        "window_expires_at": expires,
        "window_open": expires is not None and expires > now,
        "bot_paused": bot_is_paused(thread, now),
        "bot_paused_manual": thread.bot_paused,
        "bot_paused_until": thread.bot_paused_until
        if thread.bot_paused_until and thread.bot_paused_until > now
        else None,
    }


def thread_out(row: ThreadRow, now: datetime) -> ThreadOut:
    return ThreadOut(**thread_fields(row, now))
