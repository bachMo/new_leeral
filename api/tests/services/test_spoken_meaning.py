import pytest

from app.core.languages import Language
from app.services.vocabulary_builder import spoken_meaning


@pytest.mark.parametrize(
    ("meaning", "language", "spoken"),
    [
        ("fey", Language.WOLOF, "Baat bi mooy: fey."),
        ("Pacc.", Language.WOLOF, "Baat bi mooy: Pacc."),
        ("bés bu mu war a fey", Language.WOLOF, "Baat bi mooy: bés bu mu war a fey."),
        ("yobbu", Language.PULAAR, "Konngol ngol ko: yobbu."),
    ],
)
def test_every_word_is_introduced_before_being_said(
    meaning: str, language: Language, spoken: str
) -> None:
    assert spoken_meaning(meaning, language) == spoken
