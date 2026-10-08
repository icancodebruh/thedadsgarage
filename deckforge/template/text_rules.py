"""Infers title-casing conventions from the reference deck's slide titles."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable

from deckforge.template.models import CaseRule, TextRules

# Words conventionally lower-case inside a title-cased heading.
MINOR_WORDS = frozenset(
    {
        "a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "into",
        "nor", "of", "on", "or", "per", "the", "to", "vs", "via", "with", "cont'd",
    }
)  # fmt: skip
_WORD = re.compile(r"[A-Za-z][A-Za-z'\u2019\-]*")
TITLE_THRESHOLD = 0.8
SENTENCE_THRESHOLD = 0.3


def classify_title(title: str) -> CaseRule | None:
    """Classify one title, or None when it has too few words to tell."""
    words = _WORD.findall(title)
    if len(words) < 2:
        return None
    letters = "".join(words)
    if letters.isupper() and len(letters) > 3:
        return CaseRule.UPPER
    significant = [w for w in words[1:] if w.lower() not in MINOR_WORDS and not w.isupper()]
    if not significant:
        return None
    capitalised = sum(w[0].isupper() for w in significant) / len(significant)
    if capitalised >= TITLE_THRESHOLD:
        return CaseRule.TITLE
    if capitalised <= SENTENCE_THRESHOLD:
        return CaseRule.SENTENCE
    return CaseRule.MIXED


def infer_text_rules(titles: Iterable[str]) -> TextRules:
    titles = [t.strip() for t in titles if t and t.strip()]
    votes = Counter(c for t in titles if (c := classify_title(t)) is not None)
    if votes:
        # Ties break on enum order so the result is deterministic.
        rule, count = max(votes.items(), key=lambda kv: (kv[1], -list(CaseRule).index(kv[0])))
        confidence = round(count / sum(votes.values()), 3)
    else:
        rule, confidence = CaseRule.MIXED, 0.0
    trailing = sum(t.endswith(".") for t in titles) > len(titles) / 2 if titles else False
    return TextRules(
        title_case=rule, title_case_confidence=confidence, title_trailing_period=trailing
    )


def _is_acronym(word: str) -> bool:
    return any(c.isupper() for c in word[1:]) or word.isupper()


def to_title_case(title: str) -> str:
    """Capitalise significant words; keep minor words lower and acronyms as written."""
    words = title.split(" ")
    out: list[str] = []
    for i, word in enumerate(words):
        core = word.strip("()\"'")
        if not core or _is_acronym(core) or not core[0].isalpha():
            out.append(word)
        elif i > 0 and core.lower() in MINOR_WORDS and not words[i - 1].endswith(":"):
            out.append(word.lower())
        else:
            out.append(word.replace(core, core[0].upper() + core[1:], 1))
    return " ".join(out)


def to_sentence_case(title: str) -> str:
    """Lower-case every word except the first and acronyms (proper nouns need review)."""
    words = title.split(" ")
    return " ".join(w if i == 0 or _is_acronym(w) else w.lower() for i, w in enumerate(words))
