"""Every data slide cites its sources, and every number on a slide is bound to a fact."""

from __future__ import annotations

import re

from deckforge.qc.checkers.common import slide_texts
from deckforge.qc.context import QCContext
from deckforge.qc.models import Issue, Severity
from deckforge.spec.models import DATA_SLIDE_TYPES

NAME = "sources"
SOURCE_PREFIX = "Source:"
# Numbers that are labels, not data: periods, years, dates, footnote markers.
NON_DATA = [
    re.compile(r"\b(?:FY|CY|LTM|NTM|Q[1-4])\s?'?\d{2,4}[AEP]?\b"),
    re.compile(
        r"\b(?:January|February|March|April|May|June|July|August|September|October|November"
        r"|December)\s+\d{1,2},\s+\d{4}\b"
    ),
    re.compile(r"\b\d{1,2}-(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{2,4}\b"),
    re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{2,4}\b"),
    re.compile(r"\b(?:Q[1-4]|H[12]|[1-9]M)\b"),
    re.compile(r"\b(?:19|20)\d{2}[AEP]?\b"),
    re.compile(r"^\(\d\)|\(\d\)$", re.MULTILINE),
]
DIGIT = re.compile(r"\d")


def check(ctx: QCContext) -> list[Issue]:
    issues: list[Issue] = []
    for b in ctx.manifest.bindings:
        if not b.source_refs:
            issues.append(
                Issue(
                    checker=NAME,
                    severity=Severity.ERROR,
                    slide=b.slide,
                    message=f"'{b.text}' has no source_ref",
                )
            )
    glossary = sorted(ctx.spec.glossary, key=len, reverse=True)
    for n, slide in ctx.slides():
        spec_type = ctx.spec.slides[n - 1].slide_type if n <= len(ctx.spec.slides) else None
        bound = sorted({b.text for b in ctx.manifest.for_slide(n)}, key=len, reverse=True)
        texts = list(slide_texts(slide))
        has_source = any(t.strip().startswith(SOURCE_PREFIX) for _, t in texts)
        if spec_type in DATA_SLIDE_TYPES and ctx.manifest.for_slide(n) and not has_source:
            issues.append(
                Issue(
                    checker=NAME,
                    severity=Severity.ERROR,
                    slide=n,
                    message="data slide has no 'Source:' footnote",
                )
            )
        for shape, text in texts:
            if text.strip().startswith(SOURCE_PREFIX):
                continue
            remaining = text
            for value in [*bound, *glossary]:
                # Whole tokens only: a bound "200" must not erase part of "2007".
                remaining = re.sub(rf"(?<![\w.,]){re.escape(value)}(?![\w]|[.,]\d)", " ", remaining)
            for pattern in NON_DATA:
                remaining = pattern.sub(" ", remaining)
            if DIGIT.search(remaining):
                snippet = remaining.strip().replace("\n", " ")[:60]
                issues.append(
                    Issue(
                        checker=NAME,
                        severity=Severity.ERROR,
                        slide=n,
                        message=f"'{shape.name}' has a number not bound to facts.json: '{snippet}'",
                    )
                )
    return issues
