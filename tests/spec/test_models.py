from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from deckforge.spec.models import DeckSpec, FinancialTableSlide, TitleSlide

BASE = {
    "brief": "b",
    "template": {"pptx": "t.pptx", "style": "s.json", "layouts": "l.json"},
    "facts": "f.json",
}
ROW = {"label": "Revenue", "cells": ["a", None], "format": {"kind": "currency"}}


def test_discriminated_slides(deck_inputs: Path) -> None:
    spec = DeckSpec.load(deck_inputs / "deck_spec.json")
    assert isinstance(spec.slides[0], TitleSlide)
    assert isinstance(spec.slides[1], FinancialTableSlide)
    assert spec.slides[1].fact_refs()[0] == "testco.revenue.fy2024"


def test_row_cells_must_match_columns() -> None:
    with pytest.raises(ValidationError, match="cell count"):
        FinancialTableSlide(title="t", columns=["FY1"], rows=[ROW])


def test_unknown_slide_type_rejected() -> None:
    with pytest.raises(ValidationError):
        DeckSpec.model_validate({**BASE, "slides": [{"slide_type": "lbo", "title": "x"}]})


def test_brief_required() -> None:
    with pytest.raises(ValidationError):
        DeckSpec.model_validate(
            {**BASE, "brief": "", "slides": [{"slide_type": "title", "title": "x"}]}
        )
