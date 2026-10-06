"""Turns QC issues into targeted deck-spec edits (never edits the .pptx directly)."""

from __future__ import annotations

import itertools
import logging
from collections import defaultdict

from pydantic import BaseModel

from deckforge.ingest.models import FactSet
from deckforge.llm import LLMError, StructuredLLM
from deckforge.qc.models import Issue, SpecFix
from deckforge.spec.models import DeckSpec, FinancialTableSlide, SlideSpec
from deckforge.spec.planner import revise_slide
from deckforge.template.models import LayoutLibrary

log = logging.getLogger(__name__)
CONTINUED = " (cont'd)"


def _valid_cut(slide: FinancialTableSlide, cut: int) -> bool:
    """A cut is valid when no tie-out (sum_of / ratio_of) spans both sides."""
    position = {r.label: i for i, r in enumerate(slide.rows)}
    for i, row in enumerate(slide.rows):
        for label in (row.sum_of or []) + (row.ratio_of or []):
            if (i < cut) != (position[label] < cut):
                return False
    return True


def split_table(
    slide: FinancialTableSlide, max_rows: int | None = None
) -> list[FinancialTableSlide]:
    """Split into slides of at most `max_rows` rows (default: halves), cutting only where
    no tie-out group is broken. Returns the slide unchanged when no such cut exists."""
    n = len(slide.rows)
    size = max_rows or -(-n // 2)
    cuts: list[int] = []
    start = 0
    while n - start > size:
        cut = next((c for c in range(start + size, start, -1) if _valid_cut(slide, c)), None)
        if cut is None:
            return [slide]
        cuts.append(cut)
        start = cut
    if not cuts:
        return [slide]
    title = slide.title.removesuffix(CONTINUED)
    bounds = [0, *cuts, n]
    return [
        slide.model_copy(
            update={"rows": slide.rows[a:b], "title": title if i == 0 else title + CONTINUED}
        )
        for i, (a, b) in enumerate(itertools.pairwise(bounds))
    ]


def apply_fixes(
    spec: DeckSpec,
    issues: list[Issue],
    *,
    facts: FactSet,
    library: LayoutLibrary,
    llm: StructuredLLM | None,
) -> tuple[DeckSpec, list[str]]:
    """Apply one round of fixes; returns the new spec and a description of each change."""
    by_slide: dict[int, list[Issue]] = defaultdict(list)
    for issue in issues:
        if issue.fix is not None:
            by_slide[issue.fix.slide].append(issue)

    slides: list[SlideSpec] = []
    applied: list[str] = []
    for n, slide in enumerate(spec.slides, start=1):
        fixes = {i.fix.kind: i.fix for i in by_slide.get(n, []) if i.fix}
        if "set_title" in fixes:
            new_title = _value(fixes["set_title"])
            applied.append(f"slide {n}: title '{slide.title}' -> '{new_title}'")
            slide = slide.model_copy(update={"title": new_title})
        if "split_table" in fixes and isinstance(slide, FinancialTableSlide):
            parts = split_table(slide, fixes["split_table"].max_rows)
            if len(parts) > 1:
                applied.append(f"slide {n}: split table into {len(parts)} slides")
                slides.extend(parts)
                continue
            log.warning("table cannot be split without breaking tie-outs", extra={"slide": n})
        if "revise_slide" in fixes:
            slide = _revise(slide, n, by_slide[n], spec, facts, library, llm, applied)
        slides.append(slide)
    return spec.model_copy(update={"slides": slides}), applied


def _value(fix: SpecFix) -> str:
    if fix.value is None:
        raise ValueError(f"{fix.kind} fix without a value")
    return fix.value


def _revise(
    slide: SlideSpec,
    n: int,
    issues: list[Issue],
    spec: DeckSpec,
    facts: FactSet,
    library: LayoutLibrary,
    llm: StructuredLLM | None,
    applied: list[str],
) -> SlideSpec:
    if llm is None:
        log.warning("slide revision needs Claude; skipped", extra={"slide": n})
        return slide
    try:
        revised: BaseModel = revise_slide(
            slide=slide,
            problems=[i.message for i in issues],
            brief=spec.brief,
            facts=facts,
            library=library,
            llm=llm,
        )
    except LLMError as exc:
        log.warning("slide revision failed", extra={"slide": n, "reason": str(exc)})
        return slide
    applied.append(f"slide {n}: revised by Claude for {len(issues)} issue(s)")
    return revised  # type: ignore[return-value]
