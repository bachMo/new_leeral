from app.ai.real.safety.dates import localize_month_names
from app.core.languages import Language


def test_month_name_is_substituted_in_wolof() -> None:
    text, substituted = localize_month_names("Le 30 octobre 2026.", Language.WOLOF)

    assert text == "Le 30 oktoobar 2026."
    assert substituted == ("oktoobar",)


def test_month_name_is_substituted_in_pulaar_and_serer() -> None:
    assert localize_month_names("en mars", Language.PULAAR) == ("en marsa", ("marsa",))
    assert localize_month_names("en mars", Language.SERER) == ("en marsa", ("marsa",))


def test_text_without_a_month_name_is_unchanged() -> None:
    assert localize_month_names("Montant à payer : 12 500 F CFA", Language.WOLOF) == (
        "Montant à payer : 12 500 F CFA",
        (),
    )


def test_matching_is_case_insensitive() -> None:
    text, substituted = localize_month_names("OCTOBRE", Language.WOLOF)

    assert text == "oktoobar"
    assert substituted == ("oktoobar",)
