from __future__ import annotations

import pytest

from deckforge.qc.checkers import number_format
from tests.qc.checkers.helpers import add_box
from tests.qc.conftest import MakeCtx


def test_clean_deck_passes(make_ctx: MakeCtx) -> None:
    assert number_format.check(make_ctx()) == []


@pytest.mark.parametrize(("text", "expect"), [("loss of -12.3", "minus"), ("at 9.5X", "'x'")])
def test_bad_conventions(make_ctx: MakeCtx, text: str, expect: str) -> None:
    ctx = make_ctx(lambda prs: add_box(prs, 2, text))
    assert any(expect in i.message for i in number_format.check(ctx))
