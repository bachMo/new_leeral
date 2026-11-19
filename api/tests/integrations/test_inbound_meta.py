from typing import Any

from app.channels.whatsapp.inbound_meta import (
    UNHANDLED_TYPES,
    inbound_body,
    inbound_meta,
    message_type,
)
from app.integrations.whatsapp.payloads import InboundMessage
from app.models.enums import WhatsAppMessageType


def _message(**fields: Any) -> InboundMessage:
    return InboundMessage.model_validate(
        {"from": "221770000000", "id": "wamid.1", "timestamp": "1700000000", **fields}
    )


def test_location_is_kept_with_coordinates() -> None:
    message = _message(
        type="location",
        location={"latitude": 14.69, "longitude": -17.44, "name": "Marché Sandaga"},
    )

    assert message_type(message) is WhatsAppMessageType.LOCATION
    assert inbound_body(message) == "Marché Sandaga"
    assert inbound_meta(message) == {
        "location": {"latitude": 14.69, "longitude": -17.44, "name": "Marché Sandaga"}
    }


def test_shared_contact_keeps_name_and_phones() -> None:
    message = _message(
        type="contacts",
        contacts=[
            {
                "name": {"formatted_name": "Awa Diop"},
                "phones": [{"phone": "+221 77 123 45 67", "wa_id": "221771234567"}],
            }
        ],
    )

    assert message_type(message) is WhatsAppMessageType.CONTACTS
    assert inbound_body(message) == "Awa Diop"
    assert inbound_meta(message) == {
        "contacts": [{"name": "Awa Diop", "phones": ["+221 77 123 45 67"]}]
    }


def test_reaction_points_to_its_target() -> None:
    message = _message(type="reaction", reaction={"message_id": "wamid.target", "emoji": "👍"})

    assert message_type(message) is WhatsAppMessageType.REACTION
    assert inbound_body(message) == "👍"
    assert inbound_meta(message) == {"reaction": {"target": "wamid.target", "emoji": "👍"}}


def test_removed_reaction_has_an_empty_emoji() -> None:
    message = _message(type="reaction", reaction={"message_id": "wamid.target"})

    assert inbound_meta(message) == {"reaction": {"target": "wamid.target", "emoji": ""}}


def test_video_and_sticker_keep_their_media() -> None:
    video = _message(
        type="video", video={"id": "media-1", "mime_type": "video/mp4", "caption": "vu"}
    )
    sticker = _message(type="sticker", sticker={"id": "media-2", "mime_type": "image/webp"})

    assert message_type(video) is WhatsAppMessageType.VIDEO
    assert video.any_media is not None and video.any_media.id == "media-1"
    assert inbound_body(video) == "vu"
    assert message_type(sticker) is WhatsAppMessageType.STICKER
    assert sticker.any_media is not None and sticker.any_media.id == "media-2"


def test_quoted_reply_and_voice_flag() -> None:
    message = _message(
        type="audio",
        audio={"id": "media-3", "mime_type": "audio/ogg; codecs=opus", "voice": True},
        context={"from": "221700000000", "id": "wamid.quoted"},
    )

    assert inbound_meta(message) == {"reply_to": "wamid.quoted", "voice": True}


def test_button_reply_keeps_its_title_for_display() -> None:
    message = _message(
        type="interactive",
        interactive={"type": "button_reply", "button_reply": {"id": "lang:wo", "title": "Wolof"}},
    )

    assert inbound_body(message) == "lang:wo"
    assert inbound_meta(message) == {"reply_title": "Wolof"}


def test_unknown_types_stay_unsupported_and_named() -> None:
    message = _message(type="order")

    assert message_type(message) is WhatsAppMessageType.UNSUPPORTED
    assert inbound_meta(message) == {"kind": "order"}


def test_bot_still_answers_new_types_with_the_unsupported_prompt() -> None:
    for kind in ("video", "sticker", "location", "contacts", "order"):
        assert message_type(_message(type=kind)) in UNHANDLED_TYPES
    assert message_type(_message(type="reaction")) not in UNHANDLED_TYPES
