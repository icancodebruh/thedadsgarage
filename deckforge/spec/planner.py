"""Claude turns a brief into a validated deck spec, and revises single slides on request.

Claude sees fact ids and values so it can choose a storyline, but it may only reference
numbers through fact ids/tokens: digits it types into text are rejected and re-asked.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from deckforge.build.formatting import FACT_TOKEN, FormatError, parse_token
from deckforge.ingest.models import FactSet, MissingFactError
from deckforge.llm import LLMError, StructuredLLM
from deckforge.spec.models import (
    CompanyOverviewSlide,
    DeckSpec,
    ExecSummarySlide,
    SlideSpec,
    TemplateRef,
)
from deckforge.template.models import LayoutLibrary, StyleSpec

MAX_ATTEMPTS = 2
YEAR_OR_PERIOD = re.compile(r"\b(?:FY|CY|Q[1-4])?\s?(?:19|20)\d{2}[AE]?\b")

SYSTEM = """\
You plan finance presentation decks (pitch books, IC memos, company profiles) that are \
rendered into a fixed corporate PowerPoint template. You output a JSON deck plan.

Slide types you may use:
- title: deck title, subtitle, date.
- exec_summary: 3-6 bullets, one message each; the key conclusions of the deck.
- company_overview: business description, up to 6 highlights, and key statistics.
- financial_table: periods as columns; metrics as rows with formats; optional sum_of / \
ratio_of so totals and margins can be tied out.
- trading_comps: one row per peer company plus the target (is_target=true); one column \
per metric; median/mean rows are computed for you.
- football_field: implied valuation ranges (low/high fact per methodology) with an optional \
reference such as the current share price.

Hard rules:
1. Never type a number into any text (titles, bullets, descriptions, highlights) except \
calendar years. Put numbers in text only as tokens {{fact.id|kind[:scale][:decimals]}} where \
kind is currency, per_share, percent, multiple or number and scale is units, thousands, \
millions or billions. Example: "Revenue reached {{acme.revenue.fy2024|currency:billions:1}}".
2. Every fact id you use must appear in the facts catalog exactly. If the brief needs data \
the catalog lacks, leave that content out; do not invent ids.
3. Use only the layout ids provided. Title slides use the layout with a center title.
4. Titles follow the template casing rule given below and carry no trailing period.
5. One message per slide; order the deck as a storyline that answers the brief.
6. Pick formats that match each fact's unit: USD -> currency (or per_share for \
USD_per_share), percent -> percent, ratio -> multiple, shares/count -> number.
"""

REVISE_SYSTEM = """\
You revise one slide of a finance deck so that it passes review. Keep its message and \
fact tokens/ids; fix exactly the listed problems (e.g. shorten text so it fits). Never type \
numbers into text except calendar years; use {{fact.id|kind[:scale][:decimals]}} tokens and \
only fact ids already present in the slide or in the catalog."""


class PlannedDeck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slides: list[SlideSpec]


def facts_catalog(facts: FactSet) -> str:
    rows = [
        {
            "id": f.id,
            "entity": f.entity,
            "metric": f.metric,
            "period": f.period,
            "unit": f.unit.value,
            "value": str(f.value),
        }
        for f in facts.facts
    ]
    return "\n".join(json.dumps(r, sort_keys=True) for r in rows)


def layouts_summary(library: LayoutLibrary) -> str:
    lines = []
    for lay in library.layouts:
        phs = ", ".join(sorted({p.type for p in lay.placeholders}))
        lines.append(
            f"- {lay.layout_id}: placeholders [{phs}]; used by reference slides "
            f"{lay.used_by_slides or 'none'}"
        )
    return "\n".join(lines)


def _text_fields(slide: BaseModel) -> list[str]:
    texts = [getattr(slide, "title", "")]
    if isinstance(slide, ExecSummarySlide):
        texts += slide.bullets
    if isinstance(slide, CompanyOverviewSlide):
        texts += [slide.description, *slide.highlights]
    return texts


def validate_plan(slides: list[Any], facts: FactSet, library: LayoutLibrary) -> list[str]:
    """Problems that make a plan unusable, phrased so Claude can fix them."""
    problems: list[str] = []
    layout_ids = {lay.layout_id for lay in library.layouts}
    for n, slide in enumerate(slides, start=1):
        if slide.layout_id not in layout_ids:
            problems.append(f"slide {n}: unknown layout_id '{slide.layout_id}'")
        for text in _text_fields(slide):
            for match in FACT_TOKEN.finditer(text):
                try:
                    parse_token(match)
                except FormatError as exc:
                    problems.append(f"slide {n}: {exc}")
            bare = YEAR_OR_PERIOD.sub(" ", FACT_TOKEN.sub(" ", text))
            if re.search(r"\d", bare):
                problems.append(f"slide {n}: typed number in text {text!r}; use fact tokens")
        try:
            facts.require(slide.fact_refs())
        except MissingFactError as exc:
            problems.append(f"slide {n}: {exc}")
    return problems


def plan_deck(
    *,
    brief: str,
    facts: FactSet,
    style: StyleSpec,
    library: LayoutLibrary,
    template: TemplateRef,
    facts_path: Any,
    llm: StructuredLLM,
) -> DeckSpec:
    content: list[dict[str, Any]] = [
        {"type": "text", "text": f"<brief>\n{brief}\n</brief>"},
        {"type": "text", "text": f"<facts_catalog>\n{facts_catalog(facts)}\n</facts_catalog>"},
        {
            "type": "text",
            "text": f"<layouts>\n{layouts_summary(library)}\n</layouts>\n"
            f"<title_rule>{style.text_rules.title_case.value}</title_rule>",
        },
    ]
    problems: list[str] = []
    for _ in range(MAX_ATTEMPTS):
        attempt = list(content)
        if problems:
            attempt.append(
                {
                    "type": "text",
                    "text": "Your previous plan was rejected:\n- "
                    + "\n- ".join(problems)
                    + "\nReturn a corrected full plan.",
                }
            )
        plan = llm.structured(system=SYSTEM, content=attempt, schema=PlannedDeck)
        problems = validate_plan(plan.slides, facts, library)
        if not problems:
            return DeckSpec(brief=brief, template=template, facts=facts_path, slides=plan.slides)
    raise LLMError("plan still invalid after retries:\n- " + "\n- ".join(problems))


def revise_slide(
    *,
    slide: BaseModel,
    problems: list[str],
    brief: str,
    facts: FactSet,
    library: LayoutLibrary,
    llm: StructuredLLM,
) -> BaseModel:
    """Ask Claude for a corrected version of one slide (same slide type)."""
    schema = type(slide)
    content: list[dict[str, Any]] = [
        {"type": "text", "text": f"<brief>\n{brief}\n</brief>"},
        {"type": "text", "text": f"<slide>\n{slide.model_dump_json(indent=2)}\n</slide>"},
        {"type": "text", "text": "<problems>\n- " + "\n- ".join(problems) + "\n</problems>"},
        {"type": "text", "text": f"<facts_catalog>\n{facts_catalog(facts)}\n</facts_catalog>"},
    ]
    revised = llm.structured(system=REVISE_SYSTEM, content=content, schema=schema)
    issues = validate_plan([revised], facts, library)
    if issues:
        raise LLMError("revised slide invalid: " + "; ".join(issues))
    try:
        return schema.model_validate(revised.model_dump())
    except ValidationError as exc:
        raise LLMError(f"revised slide failed validation: {exc}") from exc
