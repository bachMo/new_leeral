import pytest

from app.ai.contracts import MedicationLine
from app.ai.prescription_text import explain_prescription, prescription_key_points
from app.ai.real.prescription import (
    MedicationReading,
    PrescriptionReading,
    _flag_cross_page_mismatches,
    align,
    page_cut_off,
    verify_line,
)
from app.ai.real.safety.lexicon import Lexicon, get_lexicon
from app.ai.real.safety.pharmacology import PharmacologyRules, get_pharmacology_rules


@pytest.fixture(scope="module")
def lexicon() -> Lexicon:
    return get_lexicon()


@pytest.fixture(scope="module")
def rules() -> PharmacologyRules:
    return get_pharmacology_rules()


def reading(**overrides: object) -> MedicationReading:
    values: dict[str, object] = {
        "name_read": "Amoxicilline",
        "strength": "500 mg",
        "times_per_day": 3,
        "duration_days": 7,
        "legible": "yes",
    }
    values.update(overrides)
    return MedicationReading.model_validate(values)


def verify(
    first: MedicationReading | None,
    second: MedicationReading | None,
    lexicon: Lexicon,
    rules: PharmacologyRules,
) -> MedicationLine:
    return verify_line(
        first, second, position=0, page_position=0, lexicon=lexicon, pharmacology=rules
    )


def test_line_is_sure_only_when_both_readings_agree(
    lexicon: Lexicon, rules: PharmacologyRules
) -> None:
    line = verify(reading(), reading(strength="500mg"), lexicon, rules)

    assert line.status == "sure"
    assert line.lexicon_name == "Amoxicilline"


def test_disagreement_on_a_dose_requires_a_check(
    lexicon: Lexicon, rules: PharmacologyRules
) -> None:
    line = verify(reading(), reading(times_per_day=2), lexicon, rules)

    assert line.status == "to_check"
    assert line.field_statuses["times_per_day"] == "to_check"


def test_single_reading_is_never_sure(lexicon: Lexicon, rules: PharmacologyRules) -> None:
    assert verify(reading(), None, lexicon, rules).status == "to_check"


def test_unknown_name_is_never_sure(lexicon: Lexicon, rules: PharmacologyRules) -> None:
    line = verify(reading(name_read="Zorblax"), reading(name_read="Zorblax"), lexicon, rules)

    assert line.status == "to_check"


def test_implausible_dose_is_flagged(lexicon: Lexicon, rules: PharmacologyRules) -> None:
    line = verify(
        reading(strength="2 g", times_per_day=4),
        reading(strength="2 g", times_per_day=4),
        lexicon,
        rules,
    )

    assert line.status == "to_check"
    assert line.pharmacology_flags


def test_unreadable_name_makes_the_line_unreadable(
    lexicon: Lexicon, rules: PharmacologyRules
) -> None:
    line = verify(
        reading(name_read=None, legible="no"), reading(name_read=None, legible="no"), lexicon, rules
    )

    assert line.status == "unreadable"


def test_disagreement_on_timing_requires_a_check(
    lexicon: Lexicon, rules: PharmacologyRules
) -> None:
    line = verify(
        reading(timing="avant le repas"), reading(timing="après le repas"), lexicon, rules
    )

    assert line.status == "to_check"
    assert line.timing is None


def test_dose_is_not_spoken_for_lines_to_check(lexicon: Lexicon, rules: PharmacologyRules) -> None:
    line = verify(reading(strength="1 g"), reading(strength="500 mg"), lexicon, rules)

    points = prescription_key_points([line])

    assert points[0].title_fr == "Amoxicilline"
    assert "1 g" not in explain_prescription([line], simple=False)


def test_alignment_pairs_lines_by_name() -> None:
    pairs = align(
        [reading(name_read="Doliprane"), reading(name_read="Amoxicilline")],
        [reading(name_read="Amoxicil1ine"), reading(name_read="Doliprane")],
    )

    assert [(first.name_read, second.name_read) for first, second in pairs if first and second] == [
        ("Doliprane", "Doliprane"),
        ("Amoxicilline", "Amoxicil1ine"),
    ]


def test_explanation_never_states_a_dose_for_lines_to_check(
    lexicon: Lexicon, rules: PharmacologyRules
) -> None:
    line = verify(reading(), reading(times_per_day=2), lexicon, rules)

    explanation = explain_prescription([line], simple=False)

    assert "fois par jour" not in explanation
    assert "pharmacien" in explanation


def test_form_and_instructions_are_sure_only_when_both_readings_agree(
    lexicon: Lexicon, rules: PharmacologyRules
) -> None:
    line = verify(
        reading(form="comprimé", instructions="à jeun"),
        reading(form="comprimé", instructions="à jeun"),
        lexicon,
        rules,
    )

    assert line.status == "sure"
    assert line.form == "comprimé"
    assert line.instructions == "à jeun"
    assert "comprimé" in explain_prescription([line], simple=False)
    assert "à jeun" in explain_prescription([line], simple=False)


def test_disagreement_on_form_requires_a_check(lexicon: Lexicon, rules: PharmacologyRules) -> None:
    line = verify(
        reading(form="comprimé"), reading(form="sirop"), lexicon, rules
    )

    assert line.status == "to_check"
    assert line.field_statuses["form"] == "to_check"


def test_dci_is_verified_against_the_lexicon_restricted_to_dci_terms(
    lexicon: Lexicon, rules: PharmacologyRules
) -> None:
    line = verify(
        reading(dci_read="amoxicilline"), reading(dci_read="amoxicilline"), lexicon, rules
    )

    assert line.dci_lexicon == "amoxicilline"
    assert line.field_statuses["dci"] == "sure"


def test_dci_read_as_a_brand_only_name_is_never_trusted(
    lexicon: Lexicon, rules: PharmacologyRules
) -> None:
    line = verify(reading(dci_read="Doliprane"), reading(dci_read="Doliprane"), lexicon, rules)

    assert line.dci_lexicon is None
    assert line.field_statuses["dci"] == "to_check"


def test_raw_line_is_kept_alongside_structured_fields(
    lexicon: Lexicon, rules: PharmacologyRules
) -> None:
    line = verify(
        reading(raw="Amoxicilline 500 mg 3x/j 7 jours"), reading(), lexicon, rules
    )

    assert line.raw_read == "Amoxicilline 500 mg 3x/j 7 jours"


def test_page_cut_off_requires_both_models_to_agree() -> None:
    cut = PrescriptionReading.model_validate({"page_cut_off": True})
    not_cut = PrescriptionReading.model_validate({"page_cut_off": False})

    assert page_cut_off(cut, cut) is True
    assert page_cut_off(cut, not_cut) is False
    assert page_cut_off(not_cut, not_cut) is False


def test_cut_off_warning_is_added_without_dropping_readable_lines(
    lexicon: Lexicon, rules: PharmacologyRules
) -> None:
    line = verify(reading(), reading(), lexicon, rules)

    explanation = explain_prescription([line], simple=False, cut_off=True)
    points = prescription_key_points([line], cut_off=True)

    assert line.status == "sure"
    assert "Amoxicilline" in explanation
    assert "n'était pas dans la photo" in explanation
    assert points[0].tag == "Incomplet"


def test_same_medication_with_conflicting_dose_across_pages_is_flagged(
    lexicon: Lexicon, rules: PharmacologyRules
) -> None:
    page_one = verify_line(
        reading(), reading(), position=0, page_position=0, lexicon=lexicon, pharmacology=rules
    )
    page_two = verify_line(
        reading(strength="1000 mg"),
        reading(strength="1000 mg"),
        position=1,
        page_position=1,
        lexicon=lexicon,
        pharmacology=rules,
    )
    assert page_one.status == "sure"
    assert page_two.status == "sure"

    flagged = _flag_cross_page_mismatches([page_one, page_two])

    assert all(line.status == "to_check" for line in flagged)
    assert all("cross_page_mismatch" in line.pharmacology_flags for line in flagged)


def test_same_medication_without_conflict_across_pages_is_untouched(
    lexicon: Lexicon, rules: PharmacologyRules
) -> None:
    page_one = verify_line(
        reading(), reading(), position=0, page_position=0, lexicon=lexicon, pharmacology=rules
    )
    page_two = verify_line(
        reading(), reading(), position=1, page_position=1, lexicon=lexicon, pharmacology=rules
    )

    flagged = _flag_cross_page_mismatches([page_one, page_two])

    assert all(line.status == "sure" for line in flagged)


def test_name_match_threshold_is_configurable() -> None:
    first = [reading(name_read="Amoxicilline")]
    second = [reading(name_read="Amoxiciline")]

    loose = align(first, second, name_match_threshold=0.5)
    strict = align(first, second, name_match_threshold=0.99)

    assert all(pair[1] is not None for pair in loose)
    assert any(pair[1] is None for pair in strict)
