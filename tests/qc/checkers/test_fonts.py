from __future__ import annotations

from deckforge.qc.checkers import fonts
from tests.qc.checkers.helpers import add_box
from tests.qc.conftest import MakeCtx


def test_clean_deck_passes(make_ctx: MakeCtx) -> None:
    assert fonts.check(make_ctx()) == []


def test_off_template_font_size_and_color(make_ctx: MakeCtx) -> None:
    ctx = make_ctx(lambda prs: add_box(prs, 2, "x", font="Comic Sans MS", size=13, color="FF00FF"))
    messages = " ".join(i.message for i in fonts.check(ctx))
    assert "Comic Sans MS" in messages and "13pt" in messages and "#FF00FF" in messages
