import io
import json
from typing import Any

import httpx
import pytest
from PIL import Image

from app.ai.audio import silent_wav
from app.ai.contracts import DocumentContext, PageInput, QuestionContext
from app.ai.real.engine import RealAiEngine
from app.ai.settings import AiSettings
from app.core.languages import Language

INVOICE_TEXT = "SENELEC. Facture 2026-118. Montant à payer : 12 500 F CFA avant le 30/10/2026."


def photo() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (600, 800), "white").save(buffer, format="JPEG")
    return buffer.getvalue()


class FakeProviders:
    def __init__(
        self,
        document_type: str = "invoice",
        answer: str = "Avant le 30/10/2026.",
        page_cut_off: bool = False,
        transcribe_cut_off: bool = False,
        confident: bool = True,
        contract: dict[str, Any] | None = None,
        line_disagree: bool = False,
        line_position: float | None = 0.5,
    ) -> None:
        self.document_type = document_type
        self.answer = answer
        self.page_cut_off = page_cut_off
        self.transcribe_cut_off = transcribe_cut_off
        self.confident = confident
        self.contract = contract
        self.line_disagree = line_disagree
        self.line_position = line_position
        self.calls: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"].startswith("Leeral")
        if request.url.path.endswith("/audio/speech"):
            self.calls.append("tts")
            return httpx.Response(200, content=silent_wav(0.5))
        if request.url.path.endswith("/audio/transcriptions"):
            self.calls.append("asr")
            return httpx.Response(200, json={"text": "Kan laa wara fey ?"})
        payload = json.loads(request.content)
        content = payload["messages"][-1]["content"]
        prompt = content if isinstance(content, str) else content[0]["text"]
        return self._chat(prompt, payload.get("model"))

    def _chat(self, prompt: str, model: str | None) -> httpx.Response:
        if prompt.startswith(("Tu regardes la photo", "Tu lis le texte d'un document")):
            self.calls.append("classify")
            return self._reply(
                {
                    "document_type": self.document_type,
                    "document_language": "fr",
                    "confident": self.confident,
                }
            )
        if prompt.startswith("Recopie"):
            self.calls.append("transcribe")
            text = f"[page_coupee]\n{INVOICE_TEXT}" if self.transcribe_cut_off else INVOICE_TEXT
            return self._reply(text)
        if prompt.startswith(
            ("Tu lis la photo d'une ordonnance", "Tu lis le texte d'une ordonnance")
        ):
            self.calls.append("read")
            strength = (
                "750 mg" if self.line_disagree and model == "meta/muse-glimmer-30b" else ("500 mg")
            )
            line = {
                "raw": "Doliprane 500 mg 3/j 5 jours",
                "name_read": "Doliprane",
                "strength": strength,
                "times_per_day": 3,
                "duration_days": 5,
                "line_position": self.line_position,
                "legible": "yes",
            }
            body = {"medications": [line], "page_cut_off": self.page_cut_off}
            return self._reply(f"```json\n{json.dumps(body)}\n```")
        if prompt.startswith("Translate"):
            self.calls.append("translate")
            text = prompt.split("Text:\n", 1)[1]
            return self._reply(f"WO {text}")
        if prompt.startswith("Tu aides une personne qui ne lit pas"):
            self.calls.append("analyze")
            body: dict[str, Any] = {
                "title": "Facture d'électricité",
                "doc_type": "invoice",
                "category": "money",
                "summary_fr": f"C'est une facture. {INVOICE_TEXT}",
                "main_amount_xof": "12 500",
                "main_due_date": "2026-10-30",
                "key_points": [{"kind": "amount", "tag": "Montant", "title_fr": "12 500 F CFA"}],
                "suggested_questions": ["Combien je dois payer ?"],
            }
            if self.contract is not None:
                body["contract"] = self.contract
            return self._reply(body)
        if prompt.startswith("Tu es Leeral"):
            self.calls.append("answer")
            return self._reply({"answer": self.answer, "quote": None})
        raise AssertionError(prompt[:80])

    @staticmethod
    def _reply(content: Any) -> httpx.Response:
        text = content if isinstance(content, str) else json.dumps(content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": text}}], "usage": {"cost": 0.0001}},
        )


def engine(providers: FakeProviders) -> RealAiEngine:
    settings = AiSettings(
        ai_provider="real",
        openrouter_api_key="key",
        asr_base_url="https://asr.test",
        asr_api_key="key",
        tts_base_url="https://tts.test",
        tts_api_key="key",
    )
    return RealAiEngine(settings, httpx.AsyncClient(transport=httpx.MockTransport(providers)))


async def test_photographed_invoice_is_read_then_analyzed() -> None:
    providers = FakeProviders()

    analysis = await engine(providers).analyze_document(
        [PageInput(position=0, mime_type="image/jpeg", image=photo())]
    )

    assert providers.calls == ["classify", "classify", "transcribe", "analyze"]
    assert analysis.main_amount_xof == 12500
    assert analysis.main_due_date is not None
    assert analysis.full_text == INVOICE_TEXT


async def test_prescription_goes_through_double_reading() -> None:
    providers = FakeProviders(document_type="prescription")

    analysis = await engine(providers).analyze_document(
        [PageInput(position=0, mime_type="image/jpeg", image=photo())]
    )

    assert analysis.is_prescription
    assert providers.calls.count("read") == 2
    assert analysis.medications[0].status == "sure"
    assert "Doliprane 500 mg : 3 fois par jour, pendant 5 jours." in analysis.summary_fr


async def test_sure_line_has_no_image_extract() -> None:
    providers = FakeProviders(document_type="prescription")

    analysis = await engine(providers).analyze_document(
        [PageInput(position=0, mime_type="image/jpeg", image=photo())]
    )

    assert analysis.medications[0].status == "sure"
    assert analysis.medications[0].image_extract is None


async def test_uncertain_line_gets_a_cropped_image_extract() -> None:
    providers = FakeProviders(document_type="prescription", line_disagree=True)

    analysis = await engine(providers).analyze_document(
        [PageInput(position=0, mime_type="image/jpeg", image=photo())]
    )

    assert analysis.medications[0].status == "to_check"
    assert analysis.medications[0].image_extract
    assert analysis.medications[0].image_extract != photo()


async def test_prescription_cut_off_page_keeps_medications_and_warns() -> None:
    providers = FakeProviders(document_type="prescription", page_cut_off=True)

    analysis = await engine(providers).analyze_document(
        [PageInput(position=0, mime_type="image/jpeg", image=photo())]
    )

    assert analysis.cut_off is True
    assert analysis.medications[0].status == "sure"
    assert "n'était pas dans la photo" in analysis.summary_fr


async def test_generic_document_cut_off_is_flagged_but_still_analyzed() -> None:
    providers = FakeProviders(transcribe_cut_off=True)

    analysis = await engine(providers).analyze_document(
        [PageInput(position=0, mime_type="image/jpeg", image=photo())]
    )

    assert "analyze" in providers.calls
    assert analysis.cut_off is True
    assert "n'était pas dans la photo" in analysis.summary_fr
    assert analysis.main_amount_xof == 12500


async def test_uncertain_classification_asks_what_the_document_is() -> None:
    providers = FakeProviders(confident=False)

    analysis = await engine(providers).analyze_document(
        [PageInput(position=0, mime_type="image/jpeg", image=photo())]
    )

    assert analysis.suggested_questions_fr[0] == "Quel est ce document ?"
    assert any(point.tag == "Incertain" for point in analysis.key_points)
    assert analysis.extracted_data["classification"]["confident"] is False


async def test_contract_terms_become_dedicated_key_points() -> None:
    contract = {
        "duration": "Durée indéterminée",
        "auto_renewal": "Reconduction tacite",
        "termination": "Préavis à donner avant résiliation",
        "penalties": ["Pénalité en cas de retard de paiement"],
        "parties": ["SENELEC", "Le client"],
        "amounts": [{"label": "Montant à payer", "amount_xof": "12 500"}],
        "vigilance_points": ["Clause de pénalité présente"],
    }
    providers = FakeProviders(document_type="contract", contract=contract)

    analysis = await engine(providers).analyze_document(
        [PageInput(position=0, mime_type="image/jpeg", image=photo())]
    )

    tags = [point.tag for point in analysis.key_points]
    assert tags[:9] == [
        "Avis",
        "Durée",
        "Reconduction",
        "Résiliation",
        "Pénalité",
        "Partie",
        "Partie",
        "Montant",
        "Vigilance",
    ]
    assert analysis.key_points[0].title_fr == (
        "Ceci n'est pas un avis juridique. "
        "Pour toute décision, demande à un professionnel du droit."
    )
    amount_point = next(point for point in analysis.key_points if point.tag == "Montant")
    assert amount_point.amount_xof == 12500


async def test_text_prescription_never_reaches_the_free_summary() -> None:
    providers = FakeProviders(document_type="prescription")

    analysis = await engine(providers).analyze_document(
        [PageInput(position=0, mime_type="text/plain", text="Doliprane 500 mg, 3 fois par jour")]
    )

    assert analysis.is_prescription
    assert "analyze" not in providers.calls
    assert providers.calls.count("read") == 2


async def test_localization_keeps_protected_values_and_speech_is_mp3() -> None:
    providers = FakeProviders()
    ai = engine(providers)

    localized = await ai.localize(
        "Prends Doliprane 3 fois par jour.", Language.WOLOF, protected_terms=["Doliprane"]
    )
    speech = await ai.speak(localized.text, Language.WOLOF)

    assert localized.text == "WO Prends Doliprane 3 fois par jour."
    assert localized.complete
    assert speech.mime_type == "audio/mpeg"
    assert speech.content


async def test_voice_question_is_transcribed() -> None:
    transcript = await engine(FakeProviders()).transcribe(
        b"OggS-audio", filename="../../voice.ogg", language=Language.WOLOF
    )

    assert transcript.text == "Kan laa wara fey ?"


@pytest.mark.parametrize(
    ("answer", "grounded"),
    [
        ("Avant le 30/10/2026.", True),
        ("Tu dois payer 40 000 F CFA.", False),
        ("Oui, 3 fois par jour.", False),
    ],
)
async def test_answers_with_invented_numbers_are_replaced(answer: str, grounded: bool) -> None:
    context = QuestionContext(
        question_fr="C'est 3 fois par jour ?",
        document=DocumentContext(
            doc_type="invoice", title="Facture", summary_fr=INVOICE_TEXT, full_text=INVOICE_TEXT
        ),
    )

    reply = await engine(FakeProviders(answer=answer)).answer(context)

    assert reply.grounded is grounded
    assert (reply.text_fr == answer) is grounded
