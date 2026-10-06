from __future__ import annotations

from pathlib import Path

import pytest

from deckforge.ingest.models import FactSet
from deckforge.llm import LLMError
from deckforge.spec.models import DeckSpec, ExecSummarySlide
from deckforge.spec.planner import PlannedDeck, plan_deck, revise_slide, validate_plan
from deckforge.template.models import LayoutLibrary, StyleSpec
from tests.conftest import FakeLLM

GOOD = {
    "slides": [
        {"slide_type": "title", "title": "Project Testco"},
        {
            "slide_type": "exec_summary",
            "title": "Executive Summary",
            "bullets": ["Revenue reached {{testco.revenue.fy2025|currency:billions:2}} in FY2025"],
        },
    ]
}
TYPED_NUMBER = {
    "slides": [
        {
            "slide_type": "exec_summary",
            "title": "Executive Summary",
            "bullets": ["Revenue reached $1.25B in FY2025"],
        },
    ]
}


def _inputs(full_inputs: Path) -> dict[str, object]:
    spec = DeckSpec.load(full_inputs / "deck_spec.json")
    return {
        "brief": "b",
        "facts": FactSet.load(full_inputs / "facts.json"),
        "style": StyleSpec.model_validate_json((full_inputs / "style.json").read_text()),
        "library": LayoutLibrary.model_validate_json((full_inputs / "layouts.json").read_text()),
        "template": spec.template,
        "facts_path": spec.facts,
    }


def test_valid_plan_becomes_spec(full_inputs: Path) -> None:
    llm = FakeLLM(GOOD)
    spec = plan_deck(llm=llm, **_inputs(full_inputs))  # type: ignore[arg-type]
    assert [s.slide_type for s in spec.slides] == ["title", "exec_summary"]
    assert spec.brief == "b" and len(llm.calls) == 1
    assert llm.calls[0]["schema"] is PlannedDeck


def test_typed_numbers_rejected_then_retried(full_inputs: Path) -> None:
    llm = FakeLLM(TYPED_NUMBER, GOOD)
    plan_deck(llm=llm, **_inputs(full_inputs))  # type: ignore[arg-type]
    retry_text = str(llm.calls[1]["content"][-1])
    assert "typed number" in retry_text


def test_gives_up_after_retries(full_inputs: Path) -> None:
    with pytest.raises(LLMError, match="still invalid"):
        plan_deck(llm=FakeLLM(TYPED_NUMBER, TYPED_NUMBER), **_inputs(full_inputs))  # type: ignore[arg-type]


def test_unknown_fact_and_layout(full_inputs: Path) -> None:
    inputs = _inputs(full_inputs)
    bad = ExecSummarySlide(title="T", layout_id="nope", bullets=["{{x.y|percent}}"])
    problems = validate_plan([bad], inputs["facts"], inputs["library"])  # type: ignore[arg-type]
    assert any("unknown layout_id" in p for p in problems)
    assert any("x.y" in p for p in problems)


def test_revise_slide_keeps_type(full_inputs: Path) -> None:
    inputs = _inputs(full_inputs)
    slide = ExecSummarySlide(title="T", bullets=["long " * 50])
    fixed = revise_slide(
        slide=slide,
        problems=["too long"],
        brief="b",
        facts=inputs["facts"],  # type: ignore[arg-type]
        library=inputs["library"],  # type: ignore[arg-type]
        llm=FakeLLM({"title": "T", "bullets": ["short"]}),
    )
    assert isinstance(fixed, ExecSummarySlide) and fixed.bullets == ["short"]
