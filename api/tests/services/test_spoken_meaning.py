import pytest

from app.services.vocabulary_builder import spoken_meaning


@pytest.mark.parametrize(
    ("meaning", "spoken"),
    [
        ("fey", "fey, fey."),
        ("Pacc.", "Pacc, Pacc."),
        ("am na", "am na, am na."),
        ("jamono", "jamono, jamono."),
        ("Jelee na", "Jelee na"),
        ("bés bu mu war a fey", "bés bu mu war a fey"),
    ],
)
def test_short_meanings_are_said_twice(meaning: str, spoken: str) -> None:
    assert spoken_meaning(meaning) == spoken
