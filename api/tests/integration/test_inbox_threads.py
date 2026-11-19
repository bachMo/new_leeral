from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.integrations.whatsapp.client import DownloadedMedia
from app.models.enums import WhatsAppDirection, WhatsAppMessageType
from tests.integration.conftest import Harness, add_message, make_conversation


async def test_threads_are_sorted_by_last_activity_with_unread_counts(
    harness: Harness, session: AsyncSession
) -> None:
    awa = await make_conversation(session, wa_phone="221771112233", name="Awa")
    moussa = await make_conversation(
        session, wa_phone="221779998877", name="Moussa", channel=awa.channel
    )
    await add_message(session, awa, body="Bonjour", ago=timedelta(hours=3))
    await add_message(session, awa, body="Tu es là ?", ago=timedelta(hours=2))
    await add_message(session, moussa, body="Merci", ago=timedelta(minutes=10))
    await add_message(
        session,
        moussa,
        type=WhatsAppMessageType.REACTION,
        body="👍",
        meta={"reaction": {"target": "wamid.x", "emoji": "👍"}},
        ago=timedelta(minutes=5),
    )
    headers = await harness.login()

    page = (await harness.client.get("/v1/admin/inbox/threads", headers=headers)).json()

    assert [item["name"] for item in page["items"]] == ["Moussa", "Awa"]
    assert [item["unread_count"] for item in page["items"]] == [1, 2]
    assert page["unread_threads"] == 2
    moussa_item = page["items"][0]
    assert moussa_item["phone"] == "+221779998877"
    assert moussa_item["last_message"]["type"] == "reaction"
    assert moussa_item["window_open"] is True


async def test_window_closes_24_hours_after_the_last_contact_message(
    harness: Harness, session: AsyncSession
) -> None:
    conversation = await make_conversation(session)
    await add_message(session, conversation, ago=timedelta(hours=25))
    await add_message(
        session,
        conversation,
        direction=WhatsAppDirection.OUTBOUND,
        body="Relance",
        ago=timedelta(hours=1),
    )
    headers = await harness.login()

    item = (await harness.client.get("/v1/admin/inbox/threads", headers=headers)).json()["items"][0]

    assert item["window_open"] is False
    assert item["last_message"]["sender"] == "bot"


async def test_search_and_filters(harness: Harness, session: AsyncSession) -> None:
    awa = await make_conversation(session, wa_phone="221771112233", name="Awa Diop")
    unknown = await make_conversation(
        session, wa_phone="221705556677", name=None, channel=awa.channel
    )
    await add_message(session, awa, ago=timedelta(hours=30))
    await add_message(session, unknown, ago=timedelta(minutes=1))
    headers = await harness.login()

    async def names(**params: str) -> list[str | None]:
        response = await harness.client.get(
            "/v1/admin/inbox/threads", headers=headers, params=params
        )
        assert response.status_code == 200, response.text
        return [item["wa_phone"] for item in response.json()["items"]]

    assert await names(q="diop") == ["221771112233"]
    assert await names(q="70 555") == ["221705556677"]
    assert await names(q="50%_") == []
    assert await names(filter="open") == ["221705556677"]
    assert await names(filter="paused") == []


async def test_messages_page_resolves_quotes_and_reactions(
    harness: Harness, session: AsyncSession
) -> None:
    conversation = await make_conversation(session)
    question = await add_message(session, conversation, body="Kañ laa wara fey ?")
    answer = await add_message(
        session,
        conversation,
        direction=WhatsAppDirection.OUTBOUND,
        body="Avant le 30",
        meta={"reply_to": question.wa_message_id},
        ago=timedelta(minutes=4),
    )
    await add_message(
        session,
        conversation,
        type=WhatsAppMessageType.REACTION,
        body="❤️",
        meta={"reaction": {"target": answer.wa_message_id, "emoji": "❤️"}},
        ago=timedelta(minutes=3),
    )
    headers = await harness.login()

    page = (
        await harness.client.get(
            f"/v1/admin/inbox/threads/{conversation.thread.id}/messages", headers=headers
        )
    ).json()

    items = page["items"]
    assert [item["body"] for item in items] == ["Kañ laa wara fey ?", "Avant le 30", "❤️"]
    assert items[1]["reply_to"] == {
        "id": str(question.id),
        "sender": "contact",
        "type": "text",
        "body": "Kañ laa wara fey ?",
    }
    assert items[2]["reaction"]["target_id"] == str(answer.id)
    assert page["has_more"] is False


async def test_older_messages_are_paged_with_a_cursor(
    harness: Harness, session: AsyncSession
) -> None:
    conversation = await make_conversation(session)
    for index in range(45):
        await add_message(
            session, conversation, body=f"m{index}", ago=timedelta(minutes=60 - index)
        )
    headers = await harness.login()
    url = f"/v1/admin/inbox/threads/{conversation.thread.id}/messages"

    latest = (await harness.client.get(url, headers=headers)).json()
    older = (
        await harness.client.get(url, headers=headers, params={"before": latest["items"][0]["id"]})
    ).json()

    assert len(latest["items"]) == 40 and latest["has_more"] is True
    assert latest["items"][0]["body"] == "m5" and latest["items"][-1]["body"] == "m44"
    assert [item["body"] for item in older["items"]] == [f"m{index}" for index in range(5)]
    assert older["has_more"] is False


async def test_changes_since_a_cursor_include_status_updates(
    harness: Harness, session: AsyncSession
) -> None:
    conversation = await make_conversation(session)
    sent = await add_message(
        session, conversation, direction=WhatsAppDirection.OUTBOUND, ago=timedelta(hours=1)
    )
    await add_message(session, conversation, ago=timedelta(hours=1))
    cursor = utcnow() - timedelta(minutes=1)
    sent.status = sent.status.__class__.READ
    await session.commit()
    headers = await harness.login()

    changed = (
        await harness.client.get(
            f"/v1/admin/inbox/threads/{conversation.thread.id}/messages",
            headers=headers,
            params={"updated_after": cursor.isoformat()},
        )
    ).json()

    assert [(item["id"], item["status"]) for item in changed["items"]] == [(str(sent.id), "read")]


async def test_reading_clears_unread_and_sends_the_read_receipt(
    harness: Harness, session: AsyncSession
) -> None:
    conversation = await make_conversation(session)
    await add_message(session, conversation, body="un", ago=timedelta(minutes=9))
    latest = await add_message(session, conversation, body="deux", ago=timedelta(minutes=8))
    headers = await harness.login()

    thread = (
        await harness.client.post(
            f"/v1/admin/inbox/threads/{conversation.thread.id}/read", headers=headers
        )
    ).json()

    assert thread["unread_count"] == 0
    assert ("read", {"message_id": latest.wa_message_id}) in harness.whatsapp.calls


async def test_bot_can_be_paused_and_resumed(harness: Harness, session: AsyncSession) -> None:
    conversation = await make_conversation(session)
    await add_message(session, conversation)
    headers = await harness.login()
    url = f"/v1/admin/inbox/threads/{conversation.thread.id}/bot"

    paused = (await harness.client.put(url, headers=headers, json={"paused": True})).json()
    resumed = (await harness.client.put(url, headers=headers, json={"paused": False})).json()

    assert (paused["bot_paused"], paused["bot_paused_manual"]) == (True, True)
    assert (resumed["bot_paused"], resumed["bot_paused_until"]) == (False, None)


async def test_thread_detail_shows_the_contact(harness: Harness, session: AsyncSession) -> None:
    conversation = await make_conversation(session, name="Awa")
    await add_message(session, conversation, ago=timedelta(days=2))
    await add_message(session, conversation)
    headers = await harness.login()

    detail = (
        await harness.client.get(
            f"/v1/admin/inbox/threads/{conversation.thread.id}", headers=headers
        )
    ).json()

    assert detail["whatsapp_name"] == "Awa"
    assert detail["plan"]["code"] == "free"
    assert detail["documents_count"] == 0
    assert detail["channel_number"] == "+221 76 611 10 21"
    assert detail["first_contact_at"] < detail["last_inbound_at"]


async def test_inbound_media_is_archived_on_first_view(
    harness: Harness, session: AsyncSession
) -> None:
    conversation = await make_conversation(session)
    photo = await add_message(
        session,
        conversation,
        type=WhatsAppMessageType.IMAGE,
        body=None,
        wa_media_id="media-1",
        media_mime="image/jpeg",
    )
    harness.whatsapp.media["media-1"] = DownloadedMedia(b"\xff\xd8\xffjpeg", "image/jpeg")
    headers = await harness.login()

    link = await harness.client.get(f"/v1/admin/inbox/messages/{photo.id}/media", headers=headers)

    assert link.status_code == 200
    assert link.json()["mime_type"] == "image/jpeg"
    await session.refresh(photo)
    assert photo.media_key is not None
    assert await harness.storage.get(photo.media_key) == b"\xff\xd8\xffjpeg"


async def test_expired_inbound_media_reports_unavailable(
    harness: Harness, session: AsyncSession
) -> None:
    conversation = await make_conversation(session)
    photo = await add_message(
        session, conversation, type=WhatsAppMessageType.IMAGE, wa_media_id="gone"
    )
    headers = await harness.login()

    response = await harness.client.get(
        f"/v1/admin/inbox/messages/{photo.id}/media", headers=headers
    )

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "MEDIA_UNAVAILABLE"
