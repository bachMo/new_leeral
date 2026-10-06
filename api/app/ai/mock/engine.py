import asyncio
import re
from collections.abc import Sequence
from datetime import date, timedelta

from app.ai.audio import silent_wav, wav_to_speech
from app.ai.contracts import (
    Answer,
    ComposedDocument,
    ComposedWriting,
    DocumentAnalysis,
    DocumentContext,
    ImageQuality,
    KeyPointDraft,
    LocalizedText,
    MedicationLine,
    PageInput,
    QuestionContext,
    SpeechAudio,
    Transcript,
    VocabularyCandidate,
    WordCategoryValue,
    WritingField,
    WritingSection,
)
from app.ai.prescription_text import (
    SUGGESTED_QUESTIONS,
    explain_prescription,
    prescription_context,
    prescription_key_points,
)
from app.ai.quality import assess_quality
from app.ai.settings import AiSettings
from app.core.languages import Language

_SPOKEN_CHARS_PER_SECOND = 14
_MAX_MOCK_AUDIO_S = 20
_PRESCRIPTION_HINTS = ("ordonnance", "prescription", "medic")
_MOCK_PREFIX = re.compile(r"^\[(wo|ff|sr)\]\s*")
_WORD = re.compile(r"[a-zàâçéèêëîïôûùüÿœ]{6,}", re.IGNORECASE)
_KNOWN_WORDS: dict[str, WordCategoryValue] = {
    "facture": "money",
    "montant": "money",
    "paiement": "money",
    "ordonnance": "health",
    "médicament": "health",
    "rendez-vous": "health",
    "inscription": "school",
    "attestation": "admin",
    "signature": "admin",
    "échéance": "money",
}


class MockAiEngine:
    def __init__(self, settings: AiSettings) -> None:
        self._settings = settings

    @property
    def name(self) -> str:
        return "mock"

    async def check_image(self, image: bytes) -> ImageQuality:
        return await asyncio.to_thread(assess_quality, image, self._settings)

    async def analyze_document(self, pages: Sequence[PageInput]) -> DocumentAnalysis:
        if any(hint in page.filename.lower() for page in pages for hint in _PRESCRIPTION_HINTS):
            return _mock_prescription()
        texts = tuple((page.text or "").strip() for page in pages)
        full_text = "\n\n".join(text for text in texts if text) or (
            "Société d'électricité. Facture n° 2026-118. Montant à payer : 12 500 F CFA "
            "avant le 30/10/2026. En cas de retard, des frais seront ajoutés."
        )
        due = date.today() + timedelta(days=12)
        return DocumentAnalysis(
            readable=True,
            doc_type="invoice",
            title="Facture d'électricité",
            category="money",
            summary_fr=(
                "C'est une facture d'électricité. Tu dois payer 12500 francs CFA. "
                "Tu as jusqu'à la date limite pour payer. Si tu payes en retard, "
                "des frais seront ajoutés."
            ),
            full_text=full_text,
            page_texts=texts,
            issuer="Société d'électricité",
            urgency="soon",
            urgency_label="À payer bientôt",
            main_due_date=due,
            main_amount_xof=12500,
            key_points=(
                KeyPointDraft(
                    kind="amount", tag="Montant", title_fr="12 500 F CFA à payer", amount_xof=12500
                ),
                KeyPointDraft(
                    kind="date",
                    tag="Date limite",
                    title_fr="Payer avant la date limite",
                    due_date=due,
                ),
                KeyPointDraft(kind="info", tag="Retard", title_fr="Des frais en cas de retard"),
            ),
            suggested_questions_fr=(
                "Combien je dois payer ?",
                "Avant quelle date je dois payer ?",
                "Que se passe-t-il si je paye en retard ?",
            ),
        )

    async def simplify(self, document: DocumentContext) -> str:
        if document.is_prescription:
            return explain_prescription(document.medications, simple=True)
        first_sentences = re.split(r"(?<=[.!?])\s+", document.summary_fr)[:2]
        return " ".join(first_sentences)

    async def localize(
        self, text_fr: str, language: Language, *, protected_terms: Sequence[str] = ()
    ) -> LocalizedText:
        return LocalizedText(
            language=language, text=f"[{language.value}] {text_fr}", text_fr=text_fr
        )

    async def to_french(self, text: str, language: Language) -> str:
        return _MOCK_PREFIX.sub("", text)

    async def speak(self, text: str, language: Language) -> SpeechAudio:
        duration = min(max(1, len(text) // _SPOKEN_CHARS_PER_SECOND), _MAX_MOCK_AUDIO_S)
        return await asyncio.to_thread(
            wav_to_speech, silent_wav(duration), bitrate_kbps=self._settings.mp3_bitrate_kbps
        )

    async def transcribe(
        self, audio: bytes, *, filename: str, language: Language | None
    ) -> Transcript:
        return Transcript(text="Avant quelle date je dois payer ?", language=language)

    async def answer(self, context: QuestionContext) -> Answer:
        if context.document is None:
            return Answer(text_fr="Je peux t'aider à comprendre tes papiers. Envoie-moi une photo.")
        first = re.split(r"(?<=[.!?])\s+", context.document.summary_fr)[0]
        return Answer(text_fr=f"D'après le document : {first}", source_quote=None)

    async def interpret_writing_answer(self, field: WritingField, answer_fr: str) -> str | None:
        cleaned = answer_fr.strip().rstrip(".")
        return cleaned[:1].upper() + cleaned[1:] if cleaned else None

    async def compose_writing(
        self, writing_type: str, fields: Sequence[WritingField], values: dict[str, str]
    ) -> ComposedWriting:
        facts = tuple(
            f"{field.question_fr} {values[field.key]}" for field in fields if field.key in values
        )
        documents: list[ComposedDocument] = []
        if writing_type == "cv_cover_letter":
            documents.append(
                ComposedDocument(
                    kind="cv",
                    title=values.get("full_name", "Curriculum vitae"),
                    sections=(WritingSection(heading="Informations", lines=facts),),
                )
            )
            documents.append(
                ComposedDocument(
                    kind="cover_letter",
                    title="Lettre de motivation",
                    sections=(
                        WritingSection(heading=None, lines=("Madame, Monsieur,",)),
                        WritingSection(heading=None, lines=facts),
                        WritingSection(heading=None, lines=("Veuillez agréer mes salutations.",)),
                    ),
                )
            )
        else:
            documents.append(
                ComposedDocument(
                    kind="letter",
                    title="Courrier",
                    sections=(
                        WritingSection(heading=None, lines=("Madame, Monsieur,",)),
                        WritingSection(heading=None, lines=facts),
                        WritingSection(heading=None, lines=("Veuillez agréer mes salutations.",)),
                    ),
                )
            )
        return ComposedWriting(
            documents=tuple(documents),
            readback_fr="Ton document est prêt. Il reprend les informations que tu as données.",
        )

    async def extract_vocabulary(self, text_fr: str, *, limit: int) -> list[VocabularyCandidate]:
        lowered = text_fr.lower()
        sentences = re.split(r"(?<=[.!?])\s+", text_fr)
        candidates = [word for word in _KNOWN_WORDS if word in lowered]
        candidates += [
            word.lower() for word in _WORD.findall(text_fr) if word.lower() not in candidates
        ]
        result: list[VocabularyCandidate] = []
        for word in dict.fromkeys(candidates):
            sentence = next((s for s in sentences if word in s.lower()), word)
            result.append(
                VocabularyCandidate(
                    word_fr=word,
                    category=_KNOWN_WORDS.get(word, "common"),
                    sentence_fr=sentence.strip(),
                )
            )
        return result[:limit]

    async def aclose(self) -> None:
        return None


def _mock_prescription() -> DocumentAnalysis:
    lines = (
        MedicationLine(
            position=0,
            page_position=0,
            status="sure",
            name_read="Amoxicilline",
            lexicon_name="Amoxicilline",
            lexicon_suggestion=None,
            strength="500 mg",
            times_per_day=3,
            duration_days=7,
            timing="après les repas",
            field_statuses={
                "name": "sure",
                "strength": "sure",
                "times_per_day": "sure",
                "duration": "sure",
            },
        ),
        MedicationLine(
            position=1,
            page_position=0,
            status="to_check",
            name_read="Paracetamol",
            lexicon_name=None,
            lexicon_suggestion="paracetamol",
            strength="1 g",
            times_per_day=None,
            duration_days=None,
            timing=None,
            field_statuses={
                "name": "to_check",
                "strength": "to_check",
                "times_per_day": "unreadable",
                "duration": "unreadable",
            },
        ),
    )
    return DocumentAnalysis(
        readable=True,
        doc_type="prescription",
        title="Ordonnance",
        category="health",
        summary_fr=explain_prescription(lines, simple=False),
        full_text=prescription_context(lines),
        medications=lines,
        key_points=prescription_key_points(lines),
        suggested_questions_fr=SUGGESTED_QUESTIONS,
        protected_terms=("Amoxicilline", "Paracetamol"),
        extracted_data={"medication_count": 2, "lines_to_check": 1},
    )
