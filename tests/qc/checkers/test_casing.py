from __future__ import annotations

from deckforge.qc.checkers import casing
from deckforge.spec.models import DeckSpec
from tests.qc.conftest import MakeCtx


def _retitle(title: str) -> object:
    def edit(spec: DeckSpec) -> DeckSpec:
        slides = list(spec.slides)
        slides[3] = slides[3].model_copy(update={"title": title})
        return spec.model_copy(update={"slides": slides})

    return edit


def test_clean_titles_pass(make_ctx: MakeCtx) -> None:
    assert casing.check(make_ctx()) == []


def test_sentence_case_title_gets_fix(make_ctx: MakeCtx) -> None:
    issues = casing.check(make_ctx(spec_edit=_retitle("Testco financial summary for the year.")))
    assert len(issues) == 1 and issues[0].fix is not None
    assert issues[0].fix.value == "Testco Financial Summary for the Year"
