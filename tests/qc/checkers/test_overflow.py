from __future__ import annotations

from deckforge.qc.checkers import overflow
from deckforge.qc.models import Severity
from tests.qc.checkers.helpers import add_box
from tests.qc.conftest import MakeCtx


def test_clean_deck_passes(make_ctx: MakeCtx) -> None:
    assert [i for i in overflow.check(make_ctx()) if i.severity is Severity.ERROR] == []


def test_text_too_long_for_box(make_ctx: MakeCtx) -> None:
    ctx = make_ctx(lambda prs: add_box(prs, 2, "word " * 200, size=18, h=0.4))
    assert any("needs" in i.message for i in overflow.check(ctx))


def test_shape_off_slide(make_ctx: MakeCtx) -> None:
    ctx = make_ctx(lambda prs: add_box(prs, 2, "x", x=9.5, w=2.0))
    assert any("beyond the slide" in i.message for i in overflow.check(ctx))
