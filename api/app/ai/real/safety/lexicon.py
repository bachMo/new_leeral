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


DCI_KINDS = frozenset({"dci", "dci_core"})


@dataclass(frozen=True, slots=True)
class _TrustedIndex:
    terms: list[str]
    index: dict[str, list[int]]

    @classmethod
    def build(cls, terms: list[str]) -> "_TrustedIndex":
        index: dict[str, list[int]] = defaultdict(list)
        for position, term in enumerate(terms):
            for gram in trigrams(term):
                index[gram].append(position)
        return cls(terms, index)

    def closest(self, query: str) -> tuple[str | None, float]:
        shared: Counter[int] = Counter()
        for gram in trigrams(query):
            shared.update(self.index.get(gram, ()))
        best_term: str | None = None
        best_ratio = 0.0
        for position, _ in shared.most_common(_CANDIDATE_POOL):
            candidate = self.terms[position]
            if candidate == query or abs(len(candidate) - len(query)) > _MAX_LENGTH_GAP:
                continue
            ratio = difflib.SequenceMatcher(None, query, candidate).ratio()
            if ratio > best_ratio:
                best_term, best_ratio = candidate, ratio
        return best_term, best_ratio


class Lexicon:
    def __init__(
        self,
        statuses: dict[str, str],
        kinds: dict[str, frozenset[str]] | None = None,
        *,
        fuzzy_threshold: float = FUZZY_THRESHOLD,
        min_term_length: int = MIN_TERM_LENGTH,
    ) -> None:
        self._statuses = statuses
        self._kinds = kinds or {}
        self._fuzzy_threshold = fuzzy_threshold
        self._min_term_length = min_term_length
        trusted_terms = [
            term
            for term, status in statuses.items()
            if status in TRUSTED_STATUSES and len(term) >= min_term_length
        ]
        self._all_index = _TrustedIndex.build(trusted_terms)
        dci_terms = [
            term for term in trusted_terms if self._kinds.get(term, frozenset()) & DCI_KINDS
        ]
        self._dci_index = _TrustedIndex.build(dci_terms)

    @classmethod
    def load(
        cls,
        path: Path = LEXICON_PATH,
        *,
        fuzzy_threshold: float = FUZZY_THRESHOLD,
        min_term_length: int = MIN_TERM_LENGTH,
    ) -> "Lexicon":
        statuses: dict[str, str] = {}
        kinds: dict[str, set[str]] = defaultdict(set)
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
                if status in TRUSTED_STATUSES:
                    kinds[term].add(row["kind"])
        return cls(
            statuses,
            {term: frozenset(values) for term, values in kinds.items()},
            fuzzy_threshold=fuzzy_threshold,
            min_term_length=min_term_length,
        )

    def __len__(self) -> int:
        return len(self._statuses)

    def lookup(self, name: str, *, dci_only: bool = False) -> LexiconMatch:
        index = self._dci_index if dci_only else self._all_index
        query = fold(name)
        if len(query) < self._min_term_length:
            return LexiconMatch(name, None, None, 0.0, trusted=False, suggestion=None)
        status = self._statuses.get(query)
        trusted = status in TRUSTED_STATUSES and (
            not dci_only or bool(self._kinds.get(query, frozenset()) & DCI_KINDS)
        )
        if trusted:
            return LexiconMatch(name, query, status, 1.0, trusted=True, suggestion=None)
        suggestion, ratio = index.closest(query)
        return LexiconMatch(
            name,
            query if status is not None else None,
            status,
            ratio,
            trusted=False,
            suggestion=suggestion if ratio >= self._fuzzy_threshold else None,
        )


@lru_cache
def get_lexicon(
    *, fuzzy_threshold: float = FUZZY_THRESHOLD, min_term_length: int = MIN_TERM_LENGTH
) -> Lexicon:
    return Lexicon.load(fuzzy_threshold=fuzzy_threshold, min_term_length=min_term_length)
