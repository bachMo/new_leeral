from app.ai.real.safety.posology_phrases import localize_posology_phrase
from app.core.languages import Language


def test_empty_catalog_leaves_the_phrase_untouched() -> None:
    text, substituted = localize_posology_phrase("Prends-le avant le repas.", Language.WOLOF)

    assert text == "Prends-le avant le repas."
    assert substituted == ()


def test_a_filled_catalog_entry_is_substituted() -> None:
    table = {Language.WOLOF: {"avant le repas": "bala lekk"}}

    text, substituted = localize_posology_phrase(
        "Prends-le avant le repas.", Language.WOLOF, table=table
    )

    assert text == "Prends-le bala lekk."
    assert substituted == ("bala lekk",)


def test_an_unfilled_language_in_a_partially_filled_table_is_untouched() -> None:
    table = {Language.WOLOF: {"avant le repas": "bala lekk"}}

    text, substituted = localize_posology_phrase(
        "Prends-le avant le repas.", Language.PULAAR, table=table
    )

    assert text == "Prends-le avant le repas."
    assert substituted == ()
