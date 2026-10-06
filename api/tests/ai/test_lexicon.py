import pytest

from app.ai.real.safety.lexicon import Lexicon, get_lexicon


@pytest.fixture(scope="module")
def lexicon() -> Lexicon:
    return get_lexicon()


def test_exact_official_name_is_trusted(lexicon: Lexicon) -> None:
    match = lexicon.lookup("Amoxicilline")

    assert match.trusted
    assert match.suggestion is None


def test_typo_is_never_trusted_and_points_to_the_real_name(lexicon: Lexicon) -> None:
    match = lexicon.lookup("Amoxiciline")

    assert not match.trusted
    assert match.suggestion == "amoxicilline"


def test_typo_on_the_first_letter_is_still_suggested(lexicon: Lexicon) -> None:
    assert lexicon.lookup("moxicilline").suggestion == "amoxicilline"


@pytest.mark.parametrize("name", ["a", "", "  "])
def test_too_short_names_are_never_trusted(lexicon: Lexicon, name: str) -> None:
    match = lexicon.lookup(name)

    assert not match.trusted
    assert match.suggestion is None
