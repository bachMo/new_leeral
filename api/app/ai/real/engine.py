import asyncio
import logging
from collections.abc import Sequence
from datetime import date

import httpx

from app.ai import prescription_text
from app.ai.contracts import (
    PRESCRIPTION,
    Answer,
    ComposedWriting,
    DocumentAnalysis,
    DocumentContext,
    ImageQuality,
    LocalizedText,
    PageInput,
    QuestionContext,
    SpeechAudio,
    Transcript,
    VocabularyCandidate,
    WritingField,
)
from app.ai.errors import AiOutputError
from app.ai.quality import assess_quality
from app.ai.real import analysis, dialogue, prescription, prompts, vocabulary, writing
from app.ai.real.clients.kiriku import KirikuClient
from app.ai.real.clients.openrouter import ModelProfile, OpenRouterClient
from app.ai.real.pages import PageReader
from app.ai.real.reasoning import Reasoner
from app.ai.real.safety.lexicon import get_lexicon
from app.ai.real.safety.pharmacology import get_pharmacology_rules
from app.ai.real.speech import SpeechSynthesizer
from app.ai.real.translation import Translator
from app.ai.settings import AiSettings
from app.core.languages import Language
from app.core.logging import log_step

logger = logging.getLogger("leeral.ai.engine")

_TRANSCRIPTION_CONCURRENCY = 3


class RealAiEngine:
    def __init__(self, settings: AiSettings, http: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._http = http or httpx.AsyncClient(
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)
        )
        openrouter = OpenRouterClient(settings, self._http)
        kiriku = KirikuClient(settings, self._http)
        reader_a = ModelProfile(
            settings.reader_model_a,
            settings.reader_model_a_reasoning_effort,
            settings.reader_timeout_seconds,
            settings.reader_max_retries,
            settings.reader_http_provider or None,
        )
        reader_b = ModelProfile(
            settings.reader_model_b,
            settings.reader_model_b_reasoning_effort,
            settings.reader_timeout_seconds,
            settings.reader_max_retries,
            settings.reader_http_provider or None,
        )
        self._kiriku = kiriku
        self._pages = PageReader(openrouter, settings, reader_a, reader_b)
        self._prescriptions = prescription.PrescriptionReader(
            openrouter, self._pages, reader_a, reader_b, get_lexicon(), get_pharmacology_rules()
        )
        self._reasoner = Reasoner(
            openrouter,
            ModelProfile(
                settings.llm_model_short,
                settings.llm_model_short_reasoning_effort,
                settings.llm_timeout_seconds,
                settings.llm_max_retries,
            ),
            ModelProfile(
                settings.llm_model_long,
                settings.llm_model_long_reasoning_effort,
                settings.llm_timeout_seconds,
                settings.llm_max_retries,
            ),
            long_threshold_tokens=settings.llm_long_document_token_threshold,
        )
        self._translator = Translator(
            openrouter,
            ModelProfile(
                settings.translator_model_primary,
                settings.translator_model_primary_reasoning_effort,
                settings.translator_timeout_seconds,
                settings.translator_max_retries,
            ),
            ModelProfile(
                settings.translator_model_fallback,
                settings.translator_model_fallback_reasoning_effort,
                settings.translator_timeout_seconds,
                settings.translator_max_retries,
            ),
            max_attempts=settings.translator_max_attempts_per_sentence,
        )
        self._speech = SpeechSynthesizer(
            kiriku,
            max_chars=settings.tts_max_input_chars,
            concurrency=settings.tts_concurrency,
            bitrate_kbps=settings.mp3_bitrate_kbps,
        )

    @property
    def name(self) -> str:
        return "real"

    async def check_image(self, image: bytes) -> ImageQuality:
        with log_step(logger, "check_image", bytes=len(image)) as out:
            quality = await asyncio.to_thread(assess_quality, image, self._settings)
            out["issue"] = quality.issue.value if quality.issue else None
            out["width"] = quality.width
            out["height"] = quality.height
            return quality

    async def analyze_document(self, pages: Sequence[PageInput]) -> DocumentAnalysis:
        with log_step(logger, "analyze_document", pages=len(pages)) as out:
            analysis_result = await self._analyze_document(pages)
            out["doc_type"] = analysis_result.doc_type
            out["readable"] = analysis_result.readable
            out["medications"] = len(analysis_result.medications)
            return analysis_result

    async def _analyze_document(self, pages: Sequence[PageInput]) -> DocumentAnalysis:
        first_page = next(
            (page for page in pages if page.image is not None or (page.text or "").strip()),
            None,
        )
        if first_page is not None:
            classification = await self._pages.classify(first_page)
            if classification.document_type == PRESCRIPTION:
                return await self._analyze_prescription(
                    pages, classification.model_dump(mode="json")
                )
        page_texts = await self._page_texts(pages)
        cut_off = any("[page_coupee]" in text for text in page_texts)
        full_text = "\n\n".join(
            f"--- Page {index + 1} ---\n{text}" if len(page_texts) > 1 else text
            for index, text in enumerate(page_texts)
        ).strip()
        if len(full_text.replace("[illisible]", "").strip()) < self._settings.min_page_text_chars:
            return DocumentAnalysis(
                readable=False,
                doc_type="unknown",
                title="Document illisible",
                category="other",
                summary_fr="",
                full_text=full_text,
                cut_off=cut_off,
                page_texts=tuple(page_texts),
            )
        return await analysis.analyze_text(
            self._reasoner,
            full_text,
            page_texts=tuple(page_texts),
            today=date.today(),
            cut_off=cut_off,
        )

    async def simplify(self, document: DocumentContext) -> str:
        with log_step(logger, "simplify", is_prescription=document.is_prescription) as out:
            if document.is_prescription:
                result = prescription_text.explain_prescription(document.medications, simple=True)
            else:
                raw = await self._reasoner.complete_json(
                    prompts.SIMPLIFY.format(summary=document.summary_fr),
                    operation="simplify_explanation",
                    max_tokens=600,
                )
                summary = raw.get("summary_fr")
                if not isinstance(summary, str) or not summary.strip():
                    raise AiOutputError("simplification without summary")
                result = summary.strip()
            out["length"] = len(result)
            return result

    async def localize(
        self, text_fr: str, language: Language, *, protected_terms: Sequence[str] = ()
    ) -> LocalizedText:
        with log_step(
            logger,
            "localize",
            language=language.value,
            protected_terms=len(protected_terms),
            length=len(text_fr),
        ) as out:
            result = await self._translator.localize(
                text_fr, language, protected_terms=protected_terms
            )
            out["complete"] = result.complete
            out["length"] = len(result.text)
            return result

    async def to_french(self, text: str, language: Language) -> str:
        with log_step(logger, "to_french", language=language.value, length=len(text)) as out:
            result = await self._translator.to_french(text, language)
            out["length"] = len(result)
            return result

    async def speak(self, text: str, language: Language) -> SpeechAudio:
        with log_step(logger, "speak", language=language.value, length=len(text)) as out:
            audio = await self._speech.speak(text, language)
            out["duration_s"] = audio.duration_s
            out["bytes"] = len(audio.content)
            return audio

    async def transcribe(
        self, audio: bytes, *, filename: str, language: Language | None
    ) -> Transcript:
        with log_step(
            logger,
            "transcribe",
            bytes=len(audio),
            language=language.value if language else None,
        ) as out:
            text = await self._kiriku.transcribe(audio, filename=filename, language=language)
            out["length"] = len(text)
            return Transcript(text=text, language=language)

    async def answer(self, context: QuestionContext) -> Answer:
        with log_step(
            logger,
            "answer",
            has_document=context.document is not None,
            history=len(context.history),
        ) as out:
            result = await dialogue.answer_question(self._reasoner, context)
            out["grounded"] = result.grounded
            out["has_quote"] = result.source_quote is not None
            return result

    async def interpret_writing_answer(self, field: WritingField, answer_fr: str) -> str | None:
        with log_step(
            logger, "interpret_writing_answer", field=field.key, length=len(answer_fr)
        ) as out:
            result = await writing.interpret_answer(self._reasoner, field, answer_fr)
            out["found"] = result is not None
            return result

    async def compose_writing(
        self, writing_type: str, fields: Sequence[WritingField], values: dict[str, str]
    ) -> ComposedWriting:
        with log_step(
            logger, "compose_writing", writing_type=writing_type, fields=len(fields)
        ) as out:
            result = await writing.compose(self._reasoner, writing_type, fields, values)
            out["documents"] = len(result.documents)
            return result

    async def extract_vocabulary(self, text_fr: str, *, limit: int) -> list[VocabularyCandidate]:
        with log_step(
            logger, "extract_vocabulary", length=len(text_fr), limit=limit
        ) as out:
            result = await vocabulary.extract_vocabulary(self._reasoner, text_fr, limit=limit)
            out["count"] = len(result)
            return result

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _analyze_prescription(
        self, pages: Sequence[PageInput], classification: dict[str, object]
    ) -> DocumentAnalysis:
        read_lines, cut_off = await self._prescriptions.read_pages(pages)
        lines = tuple(read_lines)
        return DocumentAnalysis(
            readable=True,
            doc_type=PRESCRIPTION,
            title="Ordonnance",
            category="health",
            summary_fr=prescription_text.explain_prescription(lines, simple=False, cut_off=cut_off),
            full_text=prescription_text.prescription_context(lines, cut_off=cut_off),
            cut_off=cut_off,
            medications=lines,
            key_points=prescription_text.prescription_key_points(lines, cut_off=cut_off),
            suggested_questions_fr=prescription_text.SUGGESTED_QUESTIONS,
            protected_terms=tuple(name for line in lines if (name := line.display_name)),
            extracted_data={
                "classification": classification,
                "medication_count": len(lines),
                "lines_to_check": sum(line.status != "sure" for line in lines),
                "cut_off": cut_off,
            },
        )

    async def _page_texts(self, pages: Sequence[PageInput]) -> list[str]:
        semaphore = asyncio.Semaphore(_TRANSCRIPTION_CONCURRENCY)

        async def read(page: PageInput) -> str:
            if page.text is not None and (
                page.image is None or len(page.text.strip()) >= self._settings.min_page_text_chars
            ):
                return page.text.strip()
            async with semaphore:
                return await self._pages.transcribe(page)

        return list(await asyncio.gather(*(read(page) for page in pages)))
