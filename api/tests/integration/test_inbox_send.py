import io
from datetime import timedelta

from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.integrations.whatsapp.client import WhatsAppError
from app.models import WhatsAppMessage
from app.models.enums import WhatsAppDirection, WhatsAppMessageType
from tests.integration.conftest import Harness, add_message, make_conversation


def _png() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (40, 30), (10, 120, 200)).save(output, format="PNG")
    return output.getvalue()


async def _outbound_count(session: AsyncSession) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(WhatsAppMessage)
            .where(WhatsAppMessage.direction == WhatsAppDirection.OUTBOUND)
        )
        or 0
    )


async def test_text_reply_quotes_the_message_and_pauses_the_bot(
    harness: Harness, session: AsyncSession
) -> None:
    conversation = await make_conversation(session)
    question = await add_message(session, conversation, body="Kañ laa wara fey ?")
    headers = await harness.login()

    response = await harness.client.post(
        f"/v1/admin/inbox/threads/{conversation.thread.id}/messages",
        headers=headers,
        data={"type": "text", "text": "  Avant le 30 octobre.  ", "reply_to": str(question.id)},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["sender"], body["admin_name"], body["body"]) == (
        "admin",
        "Bachir",
        "Avant le 30 octobre.",
    )
    assert body["reply_to"]["id"] == str(question.id)
    assert harness.whatsapp.calls[-1] == (
        "text",
        {"to": "221771112233", "body": "Avant le 30 octobre.", "reply_to": question.wa_message_id},
    )
    await session.refresh(conversation.thread)
    paused_until = conversation.thread.bot_paused_until
    assert paused_until is not None
    assert timedelta(minutes=59) < paused_until - utcnow() <= timedelta(minutes=60)


async def test_closed_window_blocks_free_messages_but_allows_the_template(
    harness: Harness, session: AsyncSession
) -> None:
    conversation = await make_conversation(session)
    await add_message(session, conversation, ago=timedelta(hours=24, minutes=1))
    headers = await harness.login()
    url = f"/v1/admin/inbox/threads/{conversation.thread.id}/messages"

    blocked = await harness.client.post(url, headers=headers, data={"type": "text", "text": "Hey"})
    template = await harness.client.post(url, headers=headers, data={"type": "template"})

    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "WHATSAPP_WINDOW_CLOSED"
    assert template.status_code == 201
    assert template.json()["template_name"] == "leeral_rappel"
    assert harness.whatsapp.calls == [
        ("template", {"to": "221771112233", "name": "leeral_rappel", "language": "fr"})
    ]


async def test_reactions_do_not_reopen_the_window(harness: Harness, session: AsyncSession) -> None:
    conversation = await make_conversation(session)
    await add_message(session, conversation, ago=timedelta(hours=30))
    await add_message(
        session,
        conversation,
        type=WhatsAppMessageType.REACTION,
        body="👍",
        meta={"reaction": {"target": "wamid.x", "emoji": "👍"}},
        ago=timedelta(minutes=1),
    )
    headers = await harness.login()

    response = await harness.client.post(
        f"/v1/admin/inbox/threads/{conversation.thread.id}/messages",
        headers=headers,
        data={"type": "text", "text": "Hey"},
    )

    assert response.status_code == 409


async def test_photo_is_stored_sent_and_viewable(harness: Harness, session: AsyncSession) -> None:
    conversation = await make_conversation(session)
    await add_message(session, conversation)
    headers = await harness.login()

    response = await harness.client.post(
        f"/v1/admin/inbox/threads/{conversation.thread.id}/messages",
        headers=headers,
        data={"type": "image", "text": "Voici le reçu"},
        files={"file": ("recu.png", _png(), "image/png")},
    )

    assert response.status_code == 201, response.text
    message = response.json()
    assert (message["type"], message["body"], message["has_media"]) == (
        "image",
        "Voici le reçu",
        True,
    )
    name, call = harness.whatsapp.calls[-1]
    assert (name, call["kind"], call["mime_type"], call["caption"]) == (
        "media",
        "image",
        "image/png",
        "Voici le reçu",
    )
    link = await harness.client.get(
        f"/v1/admin/inbox/messages/{message['id']}/media", headers=headers
    )
    assert link.status_code == 200
    assert link.json()["mime_type"] == "image/png"


async def test_document_keeps_its_filename(harness: Harness, session: AsyncSession) -> None:
    conversation = await make_conversation(session)
    await add_message(session, conversation)
    headers = await harness.login()

    response = await harness.client.post(
        f"/v1/admin/inbox/threads/{conversation.thread.id}/messages",
        headers=headers,
        data={"type": "document"},
        files={"file": ("Attestation.pdf", b"%PDF-1.4 test", "application/pdf")},
    )

    assert response.status_code == 201, response.text
    assert response.json()["filename"] == "Attestation.pdf"
    assert harness.whatsapp.calls[-1][1]["filename"] == "Attestation.pdf"


async def test_contact_card_is_normalized(harness: Harness, session: AsyncSession) -> None:
    conversation = await make_conversation(session)
    await add_message(session, conversation)
    headers = await harness.login()

    response = await harness.client.post(
        f"/v1/admin/inbox/threads/{conversation.thread.id}/messages",
        headers=headers,
        data={
            "type": "contact",
            "contact_name": "Pharmacie Baobab",
            "contact_phone": "77 123 45 67",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["contacts"] == [
        {"name": "Pharmacie Baobab", "phones": ["+221771234567"]}
    ]
    assert harness.whatsapp.calls[-1][1]["phone"] == "+221771234567"


async def test_meta_refusal_is_explained_and_nothing_is_recorded(
    harness: Harness, session: AsyncSession
) -> None:
    conversation = await make_conversation(session)
    await add_message(session, conversation)
    harness.whatsapp.fail_with = WhatsAppError(
        "graph api error",
        status_code=400,
        error_code=131026,
        details="Message undeliverable",
    )
    headers = await harness.login()

    response = await harness.client.post(
        f"/v1/admin/inbox/threads/{conversation.thread.id}/messages",
        headers=headers,
        data={"type": "image"},
        files={"file": ("a.png", _png(), "image/png")},
    )

    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "WHATSAPP_SEND_FAILED"
    assert error["fields"] == {"reason": "Message undeliverable", "code": 131026, "status": 400}
    assert await _outbound_count(session) == 0
    assert not any(harness.storage.path_for("").rglob("*.png"))


async def test_empty_text_and_unknown_quote_are_rejected(
    harness: Harness, session: AsyncSession
) -> None:
    conversation = await make_conversation(session)
    other = await make_conversation(session, wa_phone="221700000001", channel=conversation.channel)
    foreign = await add_message(session, other)
    await add_message(session, conversation)
    headers = await harness.login()
    url = f"/v1/admin/inbox/threads/{conversation.thread.id}/messages"

    empty = await harness.client.post(url, headers=headers, data={"type": "text", "text": "   "})
    foreign_quote = await harness.client.post(
        url, headers=headers, data={"type": "text", "text": "ok", "reply_to": str(foreign.id)}
    )
    missing_file = await harness.client.post(url, headers=headers, data={"type": "image"})

    assert empty.status_code == 422
    assert foreign_quote.status_code == 404
    assert missing_file.status_code == 422
    assert harness.whatsapp.calls == []
