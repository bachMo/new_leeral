import csv
import difflib
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.ai.real.safety.text import fold, trigrams

LEXICON_PATH = Path(__file__).resolve().parents[1] / "data" / "lexicon_terms.csv"

TRUSTED_STATUSES = frozenset({"official", "verified"})
FUZZY_THRESHOLD = 0.85
MIN_TERM_LENGTH = 3
_CANDIDATE_POOL = 250
_MAX_LENGTH_GAP = 4


@dataclass(frozen=True, slots=True)
class LexiconMatch:
    query: str
    term: str | None
    status: str | None
    ratio: float
    trusted: bool
    suggestion: str | None


class Lexicon:
    def __init__(self, statuses: dict[str, str]) -> None:
        self._statuses = statuses
        self._trusted_terms = [
            term
            for term, status in statuses.items()
            if status in TRUSTED_STATUSES and len(term) >= MIN_TERM_LENGTH
        ]
        self._index: dict[str, list[int]] = defaultdict(list)
        for position, term in enumerate(self._trusted_terms):
            for gram in trigrams(term):
                self._index[gram].append(position)

    @classmethod
    def load(cls, path: Path = LEXICON_PATH) -> "Lexicon":
        statuses: dict[str, str] = {}
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                term = fold(row["term"])
                if not term:
                    continue
                status = row["status"]
                current = statuses.get(term)
                if current is None or (
                    current not in TRUSTED_STATUSES and status in TRUSTED_STATUSES
                ):
                    statuses[term] = status
        return cls(statuses)

    def __len__(self) -> int:
        return len(self._statuses)

    def lookup(self, name: str) -> LexiconMatch:
        query = fold(name)
        if len(query) < MIN_TERM_LENGTH:
            return LexiconMatch(name, None, None, 0.0, trusted=False, suggestion=None)
        status = self._statuses.get(query)
        if status in TRUSTED_STATUSES:
            return LexiconMatch(name, query, status, 1.0, trusted=True, suggestion=None)
        suggestion, ratio = self._closest_trusted(query)
        return LexiconMatch(
            name,
            query if status is not None else None,
            status,
            ratio,
            trusted=False,
            suggestion=suggestion if ratio >= FUZZY_THRESHOLD else None,
        )

    def _closest_trusted(self, query: str) -> tuple[str | None, float]:
        shared: Counter[int] = Counter()
        for gram in trigrams(query):
            shared.update(self._index.get(gram, ()))
        best_term: str | None = None
        best_ratio = 0.0
        for position, _ in shared.most_common(_CANDIDATE_POOL):
            candidate = self._trusted_terms[position]
            if candidate == query or abs(len(candidate) - len(query)) > _MAX_LENGTH_GAP:
                continue
            ratio = difflib.SequenceMatcher(None, query, candidate).ratio()
            if ratio > best_ratio:
                best_term, best_ratio = candidate, ratio
        return best_term, best_ratio


@lru_cache
def get_lexicon() -> Lexicon:
    return Lexicon.load()
