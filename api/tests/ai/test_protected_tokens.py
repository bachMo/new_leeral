import pytest

from app.ai.real.safety.protected_tokens import TokenMismatchError, protect, restore


def test_numbers_and_terms_are_replaced_in_a_single_pass() -> None:
    protected = protect(
        "Amoxicilline acide clavulanique 500 mg, 3 fois par jour",
        protected_terms=["Amoxicilline", "Amoxicilline acide clavulanique"],
    )

    assert protected.text == "⟦0⟧ ⟦1⟧ mg, ⟦2⟧ fois par jour"
    assert protected.values == ("Amoxicilline acide clavulanique", "500", "3")


def test_restore_puts_original_values_back() -> None:
    protected = protect("Prends 2 comprimés de Doliprane", protected_terms=["Doliprane"])

    assert restore("Jël ⟦0⟧ ⟦1⟧", protected) == "Jël 2 Doliprane"


@pytest.mark.parametrize(
    ("translation", "missing", "duplicated"),
    [("Jël ⟦0⟧", [1], []), ("⟦0⟧ ⟦0⟧ ⟦1⟧", [], [0]), ("⟦0⟧ ⟦1⟧ ⟦7⟧", [], [7])],
)
def test_restore_refuses_altered_tokens(
    translation: str, missing: list[int], duplicated: list[int]
) -> None:
    protected = protect("Prends 2 comprimés de Doliprane", protected_terms=["Doliprane"])

    with pytest.raises(TokenMismatchError) as error:
        restore(translation, protected)

    assert error.value.missing == missing
    assert error.value.duplicated == duplicated
