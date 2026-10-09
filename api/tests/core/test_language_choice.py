import pytest

from app.channels.whatsapp.language_choice import named_language
from app.core.languages import Language


@pytest.mark.parametrize(
    ("transcript", "expected"),
    [
        ("Wolof", Language.WOLOF),
        ("wolof.", Language.WOLOF),
        ("Wolofu", Language.WOLOF),
        ("ci wolof rek", Language.WOLOF),
        ("Pulaar", Language.PULAAR),
        ("Pular !", Language.PULAAR),
        ("Fulfulde", Language.PULAAR),
        ("Seereer", Language.SERER),
        ("sérère", Language.SERER),
    ],
)
def test_a_bare_language_name_is_recognised(transcript: str, expected: Language) -> None:
    assert named_language(transcript) is expected


@pytest.mark.parametrize(
    "transcript",
    [
        "",
        "Avant quelle date je dois payer ?",
        "wolof pulaar",
        "Lan mooy wolof bi ci kayit bi",
        "facture",
        "bonjour",
    ],
)
def test_anything_else_is_a_regular_message(transcript: str) -> None:
    assert named_language(transcript) is None
