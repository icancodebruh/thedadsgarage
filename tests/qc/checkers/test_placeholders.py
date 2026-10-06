from __future__ import annotations

from deckforge.qc.checkers import placeholders
from tests.qc.checkers.helpers import add_box
from tests.qc.conftest import MakeCtx


def test_clean_deck_passes(make_ctx: MakeCtx) -> None:
    assert placeholders.check(make_ctx()) == []


def test_filler_text(make_ctx: MakeCtx) -> None:
    ctx = make_ctx(lambda prs: add_box(prs, 3, "Lorem ipsum TBD"))
    assert any("filler" in i.message for i in placeholders.check(ctx))


def test_empty_placeholder(make_ctx: MakeCtx) -> None:
    ctx = make_ctx(lambda prs: prs.slides.add_slide(prs.slide_layouts[1]))
    assert any("empty placeholder" in i.message for i in placeholders.check(ctx))
