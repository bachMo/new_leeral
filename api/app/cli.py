import argparse
import asyncio
import logging

from app.ai import build_ai_engine
from app.ai.contracts import PageInput
from app.core.config import get_settings
from app.core.languages import AVAILABLE_LANGUAGES, Language
from app.core.logging import configure_logging
from app.db.session import get_engine, get_session_factory
from app.integrations.storage import get_storage
from app.models import WhatsAppChannel
from app.repositories.system import WhatsAppChannelRepository
from app.services.ai_jobs import AiJobTracker
from app.services.core_vocabulary import CORE_WORDS
from app.services.ui_prompt_service import UiPromptSynchronizer
from app.services.vocabulary_builder import VocabularyBuilder

logger = logging.getLogger("leeral.cli")


def _languages(selected: str | None) -> list[Language]:
    if selected:
        return [Language(selected)]
    return sorted(AVAILABLE_LANGUAGES, key=lambda language: language.value)


async def seed_channel(display_number: str, language: str | None) -> None:
    settings = get_settings()
    if not settings.whatsapp_default_phone_id:
        raise SystemExit("WHATSAPP_DEFAULT_PHONE_ID is empty in .env")
    async with get_session_factory()() as session:
        channels = WhatsAppChannelRepository(session)
        channel = await channels.by_phone_number_id(settings.whatsapp_default_phone_id)
        if channel is None:
            channel = channels.add(
                WhatsAppChannel(
                    phone_number_id=settings.whatsapp_default_phone_id,
                    display_number=display_number,
                )
            )
        channel.display_number = display_number
        channel.language = Language(language) if language else None
        channel.is_active = True
        await session.commit()
    print(f"WhatsApp channel ready: {display_number}")


async def seed_words(language: str | None) -> None:
    ai = build_ai_engine()
    sessions = get_session_factory()
    builder = VocabularyBuilder(sessions, ai, get_storage(), AiJobTracker(sessions, ai.name))
    try:
        async with sessions() as session:
            for word_fr, category, example in CORE_WORDS:
                word = await builder.get_or_create_word(
                    session, word_fr, category, example, is_core=True
                )
                for target in _languages(language):
                    await builder.ensure_translation(session, word, target)
                await session.commit()
                print(f"  {word_fr}")
    finally:
        await ai.aclose()
    print(f"{len(CORE_WORDS)} core words ready")


async def sync_prompts(language: str | None, force: bool) -> None:
    ai = build_ai_engine()
    try:
        async with get_session_factory()() as session:
            synchronizer = UiPromptSynchronizer(session, ai, get_storage())
            for target in _languages(language):
                created, failed = await synchronizer.sync(target, force=force)
                print(f"{target.value}: {created} prompts generated, {failed} failed")
    finally:
        await ai.aclose()


async def check_ai(language: str) -> None:
    ai = build_ai_engine()
    target = Language(language)
    try:
        print(f"provider: {ai.name}")
        localized = await ai.localize(
            "Tu dois payer 12 500 F CFA avant le 30 octobre.", target, protected_terms=()
        )
        print(f"translation ({target.value}): {localized.text}")
        audio = await ai.speak(localized.text, target)
        print(f"speech: {len(audio.content)} bytes, {audio.duration_s}s")
        back = await ai.to_french(localized.text, target)
        print(f"back to french: {back}")
        analysis = await ai.analyze_document(
            [
                PageInput(
                    position=0,
                    mime_type="text/plain",
                    text=(
                        "SENELEC - Facture n° 2026-118. Montant à payer : 12 500 F CFA "
                        "avant le 30/10/2026."
                    ),
                    filename="check.txt",
                )
            ]
        )
        print(f"analysis: {analysis.title} / {analysis.summary_fr}")
    finally:
        await ai.aclose()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="leeral", description="Leeral administration")
    commands = parser.add_subparsers(dest="command", required=True)

    channel = commands.add_parser("seed-channel", help="register the WhatsApp number")
    channel.add_argument("--display-number", required=True)
    channel.add_argument("--language", choices=[lang.value for lang in Language])

    words = commands.add_parser("seed-words", help="create core vocabulary with audio")
    words.add_argument("--language", choices=[lang.value for lang in AVAILABLE_LANGUAGES])

    prompts = commands.add_parser("sync-prompts", help="generate spoken interface prompts")
    prompts.add_argument("--language", choices=[lang.value for lang in AVAILABLE_LANGUAGES])
    prompts.add_argument("--force", action="store_true")

    check = commands.add_parser("check-ai", help="call every AI capability once")
    check.add_argument(
        "--language", default="wo", choices=[lang.value for lang in AVAILABLE_LANGUAGES]
    )

    args = parser.parse_args(argv)
    configure_logging("WARNING", json_output=False)
    runners = {
        "seed-channel": lambda: seed_channel(args.display_number, args.language),
        "seed-words": lambda: seed_words(args.language),
        "sync-prompts": lambda: sync_prompts(args.language, args.force),
        "check-ai": lambda: check_ai(args.language),
    }

    async def run() -> None:
        try:
            await runners[args.command]()
        finally:
            await get_engine().dispose()

    asyncio.run(run())


if __name__ == "__main__":
    main()
