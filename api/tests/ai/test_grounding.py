from datetime import date

from app.ai.real.analysis import (
    _amount_in_text,
    _date_in_text,
    _grounded_summary,
    _is_grounded,
    _urgency_from_due_date,
)
from app.ai.real.dialogue import numbers_are_grounded
from app.ai.real.speech import chunk_text


def test_answer_with_invented_number_is_rejected() -> None:
    sources = ["Montant à payer : 12 500 F CFA avant le 30/10/2026."]

    assert numbers_are_grounded("Tu dois payer 12 500 francs avant le 30.", sources)
    assert not numbers_are_grounded("Tu dois payer 15 000 francs.", sources)


def test_amounts_and_dates_must_appear_in_the_document() -> None:
    text = "Montant à payer : 12 500 F CFA. Date limite : 30/10/2026."

    assert _amount_in_text(12500, text) == 12500
    assert _amount_in_text(99000, text) is None
    assert _date_in_text(date(2026, 10, 30), text) == date(2026, 10, 30)
    assert _date_in_text(date(2026, 11, 2), text) is None


def test_sentence_with_an_invented_number_is_dropped_from_the_summary() -> None:
    text = "Montant à payer : 12 500 F CFA avant le 30/10/2026."
    summary = (
        "C'est une facture. Tu dois payer 12 500 francs. "
        "Il y a une pénalité de 5000 francs si tu es en retard."
    )

    grounded = _grounded_summary(summary, text)

    assert "5000" not in grounded
    assert "12 500" in grounded


def test_key_point_text_must_be_grounded_too() -> None:
    text = "Montant à payer : 12 500 F CFA."

    assert _is_grounded("Montant 12 500 F CFA", text)
    assert not _is_grounded("Pénalité de 5000 F CFA", text)


def test_close_due_dates_become_urgent() -> None:
    today = date(2026, 10, 6)

    assert _urgency_from_due_date(date(2026, 10, 10), today, "none") == "urgent"
    assert _urgency_from_due_date(date(2026, 10, 30), today, "none") == "soon"
    assert _urgency_from_due_date(None, today, "none") == "none"


def test_speech_chunks_respect_the_tts_limit() -> None:
    text = " ".join(["Une phrase assez longue pour remplir le texte."] * 40)

    chunks = chunk_text(text, 500)

    assert all(len(chunk) <= 500 for chunk in chunks)
    assert " ".join(chunks) == text
