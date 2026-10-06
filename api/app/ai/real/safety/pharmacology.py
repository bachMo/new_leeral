import csv
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.ai.real.safety.text import fold

RULES_PATH = Path(__file__).resolve().parents[1] / "data" / "pharmacology_rules.csv"

_UNIT_TO_MG = {"mg": 1.0, "g": 1000.0, "mcg": 0.001, "µg": 0.001, "ug": 0.001}
_STRENGTH = re.compile(r"(\d+(?:[.,]\d+)?)\s*(mg|mcg|µg|ug|g)\b", re.IGNORECASE)


def parse_strength_mg(strength: str | None) -> float | None:
    if not strength or not (match := _STRENGTH.search(strength)):
        return None
    return float(match.group(1).replace(",", ".")) * _UNIT_TO_MG[match.group(2).lower()]


@dataclass(frozen=True, slots=True)
class PharmacologyRule:
    dci: str
    max_daily_dose_mg: float | None
    typical_duration_days_max: int | None
    reviewed_by: str | None


@dataclass(frozen=True, slots=True)
class CoherenceCheck:
    rule: PharmacologyRule | None
    reasons: tuple[str, ...]

    @property
    def flagged(self) -> bool:
        return bool(self.reasons)


class PharmacologyRules:
    def __init__(self, rules: dict[str, PharmacologyRule], aliases: dict[str, str]) -> None:
        self._rules = rules
        self._aliases = aliases

    @classmethod
    def load(cls, path: Path = RULES_PATH) -> "PharmacologyRules":
        rules: dict[str, PharmacologyRule] = {}
        aliases: dict[str, str] = {}
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                dci = fold(row["dci_normalized"])
                rules[dci] = PharmacologyRule(
                    dci=dci,
                    max_daily_dose_mg=float(row["max_daily_dose_mg"])
                    if row["max_daily_dose_mg"].strip()
                    else None,
                    typical_duration_days_max=int(row["typical_duration_days_max"])
                    if row["typical_duration_days_max"].strip()
                    else None,
                    reviewed_by=row["reviewed_by"] or None,
                )
                for alias in (dci, *row["aliases"].split(";")):
                    if folded := fold(alias):
                        aliases[folded] = dci
        return cls(rules, aliases)

    def __len__(self) -> int:
        return len(self._rules)

    def find(self, name: str) -> PharmacologyRule | None:
        folded = fold(name)
        dci = self._aliases.get(folded) or next(
            (dci for alias, dci in self._aliases.items() if folded.startswith(f"{alias} ")),
            None,
        )
        return self._rules.get(dci) if dci else None

    def check(
        self,
        name: str,
        *,
        strength: str | None,
        times_per_day: int | None,
        duration_days: int | None,
    ) -> CoherenceCheck:
        rule = self.find(name)
        if rule is None:
            return CoherenceCheck(rule=None, reasons=())
        reasons: list[str] = []
        dose_mg = parse_strength_mg(strength)
        if rule.max_daily_dose_mg is not None and dose_mg is not None and times_per_day:
            daily = dose_mg * times_per_day
            if daily > rule.max_daily_dose_mg:
                reasons.append(
                    f"daily dose {daily:g} mg above plausible maximum "
                    f"{rule.max_daily_dose_mg:g} mg for {rule.dci}"
                )
        if (
            rule.typical_duration_days_max is not None
            and duration_days is not None
            and duration_days > rule.typical_duration_days_max
        ):
            reasons.append(
                f"duration {duration_days} days above usual maximum "
                f"{rule.typical_duration_days_max} days for {rule.dci}"
            )
        if times_per_day is not None and not 1 <= times_per_day <= 8:
            reasons.append(f"implausible frequency of {times_per_day} intakes per day")
        return CoherenceCheck(rule=rule, reasons=tuple(reasons))


@lru_cache
def get_pharmacology_rules() -> PharmacologyRules:
    return PharmacologyRules.load()
