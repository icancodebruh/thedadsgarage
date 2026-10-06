"""Number conventions in rendered text: brackets for negatives, lower-case x for multiples.

Deck-wide precision (one decimals setting per format) is checked from the manifest in
the consistency checker.
"""

from __future__ import annotations

import re

from deckforge.qc.checkers.common import slide_texts
from deckforge.qc.context import QCContext
from deckforge.qc.models import Issue, Severity

NAME = "number_format"
MINUS_NUMBER = re.compile(r"(?<![\w)])[-\u2212]\s?\$?\d")
UPPER_MULTIPLE = re.compile(r"\d(?:\.\d+)?X\b")


def check(ctx: QCContext) -> list[Issue]:
    issues: list[Issue] = []
    for n, slide in ctx.slides():
        for shape, text in slide_texts(slide):
            if MINUS_NUMBER.search(text):
                issues.append(
                    Issue(
                        checker=NAME,
                        severity=Severity.ERROR,
                        slide=n,
                        message=f"'{shape.name}' shows a negative with a minus sign; use brackets",
                    )
                )
            if UPPER_MULTIPLE.search(text):
                issues.append(
                    Issue(
                        checker=NAME,
                        severity=Severity.ERROR,
                        slide=n,
                        message=f"'{shape.name}' writes multiples as 'X'; use 'x'",
                    )
                )
    return issues
