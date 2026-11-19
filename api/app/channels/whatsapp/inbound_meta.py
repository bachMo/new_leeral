from typing import Any

from app.integrations.whatsapp.payloads import InboundMessage
from app.models.enums import WhatsAppMessageType

TYPE_MAP = {
    "text": WhatsAppMessageType.TEXT,
    "image": WhatsAppMessageType.IMAGE,
    "document": WhatsAppMessageType.DOCUMENT,
    "audio": WhatsAppMessageType.AUDIO,
    "button": WhatsAppMessageType.BUTTON,
    "interactive": WhatsAppMessageType.INTERACTIVE,
    "video": WhatsAppMessageType.VIDEO,
    "sticker": WhatsAppMessageType.STICKER,
    "location": WhatsAppMessageType.LOCATION,
    "contacts": WhatsAppMessageType.CONTACTS,
    "reaction": WhatsAppMessageType.REACTION,
}
UNHANDLED_TYPES = frozenset(
    {
        WhatsAppMessageType.UNSUPPORTED,
        WhatsAppMessageType.VIDEO,
        WhatsAppMessageType.STICKER,
        WhatsAppMessageType.LOCATION,
        WhatsAppMessageType.CONTACTS,
    }
)


def message_type(message: InboundMessage) -> WhatsAppMessageType:
    return TYPE_MAP.get(message.type, WhatsAppMessageType.UNSUPPORTED)


def inbound_body(message: InboundMessage) -> str | None:
    if message.text is not None:
        return message.text.body
    if message.reply_id is not None:
        return message.reply_id
    media = message.any_media
    if media is not None:
        return media.caption or media.filename
    if message.reaction is not None:
        return message.reaction.emoji or None
    if message.location is not None:
        return message.location.name or message.location.address
    if message.contacts:
        names = [contact.name.formatted_name for contact in message.contacts if contact.name]
        return ", ".join(name for name in names if name) or None
    return None


def inbound_meta(message: InboundMessage) -> dict[str, Any] | None:
    meta: dict[str, Any] = {}
    if message.type not in TYPE_MAP:
        meta["kind"] = message.type
    if message.context is not None and message.context.id:
        meta["reply_to"] = message.context.id
    media = message.any_media
    if media is not None:
        if media.filename:
            meta["filename"] = media.filename
        if media.voice:
            meta["voice"] = True
    if message.reply_title:
        meta["reply_title"] = message.reply_title
    if message.location is not None:
        meta["location"] = message.location.model_dump(exclude_none=True)
    if message.contacts:
        meta["contacts"] = [
            {
                "name": contact.name.formatted_name if contact.name else "",
                "phones": [
                    phone.phone or phone.wa_id
                    for phone in contact.phones
                    if phone.phone or phone.wa_id
                ],
            }
            for contact in message.contacts
        ]
    if message.reaction is not None:
        meta["reaction"] = {
            "target": message.reaction.message_id,
            "emoji": message.reaction.emoji or "",
        }
    return meta or None
