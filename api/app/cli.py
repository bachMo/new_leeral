import argparse
import asyncio
import logging
import sys
import time
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from app.ai import build_ai_engine
from app.ai.contracts import (
    ConversationTurn,
    DocumentAnalysis,
    DocumentContext,
    PageInput,
    QuestionContext,
)
from app.ai.engine import AiEngine
from app.core.config import PROJECT_ROOT, get_settings
from app.core.languages import AVAILABLE_LANGUAGES, Language
from app.core.logging import configure_logging
from app.db.session import get_engine, get_session_factory
from app.integrations.storage import get_storage
from app.models import WhatsAppChannel
from app.repositories.system import WhatsAppChannelRepository
from app.services.ai_jobs import AiJobTracker
from app.services.core_vocabulary import CORE_WORDS
from app.services.media import FileKind, build_pages, detect
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


class Report:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._lines: list[str] = []

    def line(self, text: str = "") -> None:
        print(text)
        self._lines.append(text)

    def section(self, title: str) -> None:
        self.line()
        self.line(f"== {title}")

    def save(self) -> Path:
        path = self.directory / "report.txt"
        path.write_text("\n".join(self._lines) + "\n", encoding="utf-8")
        return path


async def try_document(
    paths: Sequence[str],
    language: str,
    questions: Sequence[str],
    questions_fr: Sequence[str],
    audio_questions: Sequence[str],
    output: str | None,
    *,
    back_translate: bool = False,
    check_pronunciation: bool = False,
) -> None:
    ai = build_ai_engine()
    target = Language(language)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    directory = Path(output) if output else PROJECT_ROOT / "var" / "try" / stamp
    directory.mkdir(parents=True, exist_ok=True)
    report = Report(directory)
    try:
        report.line(f"provider: {ai.name} | language: {target.value}")
        pages = await _load_pages(ai, paths, report)
        if pages is None:
            return
        started = time.perf_counter()
        analysis = await ai.analyze_document(pages)
        report.line(f"analysis: {time.perf_counter() - started:.1f}s for {len(pages)} page(s)")
        if not analysis.readable:
            report.line("document unreadable")
            return
        _report_analysis(report, analysis)
        context = DocumentContext(
            doc_type=analysis.doc_type,
            title=analysis.title,
            summary_fr=analysis.summary_fr,
            full_text=analysis.full_text,
            medications=analysis.medications,
        )
        report.section(f"Explanation ({target.value})")
        await _voice(
            ai,
            report,
            analysis.summary_fr,
            target,
            context,
            "explanation",
            back_translate=back_translate,
            check_pronunciation=check_pronunciation,
        )
        if analysis.key_points:
            report.section(f"Key points ({target.value})")
            for point in analysis.key_points:
                spoken = ". ".join(part for part in (point.title_fr, point.detail_fr) if part)
                localized = await ai.localize(
                    spoken, target, protected_terms=context.protected_terms
                )
                report.line(f"- {localized.text}")
        asked = [*await _spoken_questions(ai, audio_questions, target, report)]
        for text in questions:
            asked.append(await ai.to_french(text, target))
        asked.extend(questions_fr)
        history: list[ConversationTurn] = []
        for index, question_fr in enumerate(asked, start=1):
            report.section(f"Question {index}")
            report.line(f"question (fr): {question_fr}")
            started = time.perf_counter()
            reply = await ai.answer(
                QuestionContext(question_fr=question_fr, document=context, history=tuple(history))
            )
            report.line(f"answer (fr): {reply.text_fr}")
            report.line(f"grounded: {reply.grounded} | {time.perf_counter() - started:.1f}s")
            if reply.source_quote:
                report.line(f"source: {reply.source_quote}")
            await _voice(
                ai,
                report,
                reply.text_fr,
                target,
                context,
                f"answer-{index}",
                back_translate=back_translate,
                check_pronunciation=check_pronunciation,
            )
            history.extend(
                (
                    ConversationTurn(role="user", text_fr=question_fr),
                    ConversationTurn(role="assistant", text_fr=reply.text_fr),
                )
            )
    finally:
        await ai.aclose()
        report.line()
        report.line(f"saved in {report.save().parent}")


async def _load_pages(ai: AiEngine, paths: Sequence[str], report: Report) -> list[PageInput] | None:
    files = []
    for raw in paths:
        path = Path(raw)
        content = await asyncio.to_thread(path.read_bytes)
        detected = detect(content)
        if detected.kind is FileKind.IMAGE:
            quality = await ai.check_image(content)
            report.line(
                f"{path.name}: {quality.issue or 'ok'} (blur {quality.blur_score:.0f}, "
                f"brightness {quality.brightness:.0f}, {quality.width}x{quality.height})"
            )
            if not quality.ok:
                return None
        files.append((detected, content, path.name))
    return await asyncio.to_thread(build_pages, files, get_settings().max_pages_per_document)


def _report_analysis(report: Report, analysis: DocumentAnalysis) -> None:
    report.section("Analysis (fr)")
    report.line(f"type: {analysis.doc_type} | category: {analysis.category}")
    report.line(f"title: {analysis.title}")
    report.line(f"issuer: {analysis.issuer} | date: {analysis.document_date}")
    report.line(f"amount: {analysis.main_amount_xof} | due: {analysis.main_due_date}")
    report.line(f"urgency: {analysis.urgency} {analysis.urgency_label or ''}".rstrip())
    report.line(f"summary: {analysis.summary_fr}")
    for point in analysis.key_points:
        report.line(f"- [{point.kind}] {point.title_fr} | {point.detail_fr or ''}")
    for line in analysis.medications:
        report.line(
            f"* {line.status} | read: {line.name_read} | lexicon: {line.lexicon_name} "
            f"| suggestion: {line.lexicon_suggestion} | {line.strength} | "
            f"{line.times_per_day}x/day | {line.duration_days} days | {line.timing} "
            f"| flags: {', '.join(line.pharmacology_flags) or '-'}"
        )
    for question in analysis.suggested_questions_fr:
        report.line(f"? {question}")


async def _spoken_questions(
    ai: AiEngine, paths: Sequence[str], language: Language, report: Report
) -> list[str]:
    asked: list[str] = []
    for raw in paths:
        path = Path(raw)
        audio = await asyncio.to_thread(path.read_bytes)
        transcript = await ai.transcribe(audio, filename=path.name, language=language)
        report.line(f"{path.name} heard: {transcript.text}")
        asked.append(await ai.to_french(transcript.text, language))
    return asked


async def _voice(
    ai: AiEngine,
    report: Report,
    text_fr: str,
    language: Language,
    context: DocumentContext,
    name: str,
    *,
    back_translate: bool = False,
    check_pronunciation: bool = False,
) -> None:
    localized = await ai.localize(text_fr, language, protected_terms=context.protected_terms)
    report.line(f"{language.value}: {localized.text}")
    if not localized.complete:
        report.line("warning: some sentences could not be translated")
    if back_translate:
        back = await ai.to_french(localized.text, language)
        report.line(f"back to french: {back}")
        report.line(f"(original was): {text_fr}")
    audio = await ai.speak(localized.text, language)
    path = report.directory / f"{name}-{language.value}.{audio.extension}"
    await asyncio.to_thread(path.write_bytes, audio.content)
    report.line(f"audio: {path.name} ({audio.duration_s}s)")
    if check_pronunciation:
        heard = await ai.transcribe(audio.content, filename=path.name, language=language)
        report.line(f"heard back by ASR: {heard.text}")


def main(argv: list[str] | None = None) -> None:
    # Windows consoles default to a codepage (e.g. cp1252) that lacks wolof/pulaar letters
    # such as "ŋ" : printing one would otherwise crash this CLI instead of just this letter.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
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

    trial = commands.add_parser(
        "try-document", help="run the real document pipeline on local files, without database"
    )
    trial.add_argument("files", nargs="+", help="photos, PDF or DOCX of one document")
    trial.add_argument(
        "--language", default="wo", choices=[lang.value for lang in AVAILABLE_LANGUAGES]
    )
    trial.add_argument("--question", action="append", default=[], help="in the chosen language")
    trial.add_argument("--question-fr", action="append", default=[], help="in French")
    trial.add_argument("--question-audio", action="append", default=[], help="voice note file")
    trial.add_argument("--output", help="folder for audio files and report.txt")
    trial.add_argument(
        "--back-translate",
        action="store_true",
        help="translate the spoken text back to French for a drift check (extra API calls)",
    )
    trial.add_argument(
        "--check-pronunciation",
        action="store_true",
        help="transcribe the generated audio back (ASR) to spot-check numbers/names (extra calls)",
    )

    args = parser.parse_args(argv)
    if args.command == "try-document":
        missing = [raw for raw in (*args.files, *args.question_audio) if not Path(raw).is_file()]
        if missing:
            raise SystemExit(f"file not found: {', '.join(missing)}")
    diagnostic = args.command in {"try-document", "check-ai"}
    configure_logging("INFO" if diagnostic else "WARNING", json_output=False)
    runners = {
        "seed-channel": lambda: seed_channel(args.display_number, args.language),
        "seed-words": lambda: seed_words(args.language),
        "sync-prompts": lambda: sync_prompts(args.language, args.force),
        "check-ai": lambda: check_ai(args.language),
        "try-document": lambda: try_document(
            args.files,
            args.language,
            args.question,
            args.question_fr,
            args.question_audio,
            args.output,
            back_translate=args.back_translate,
            check_pronunciation=args.check_pronunciation,
        ),
    }

    async def run() -> None:
        try:
            await runners[args.command]()
        finally:
            await get_engine().dispose()

    asyncio.run(run())


if __name__ == "__main__":
    main()
