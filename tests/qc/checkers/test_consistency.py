from __future__ import annotations

import json

from deckforge.qc.checkers import consistency
from tests.qc.conftest import MakeCtx


def test_clean_deck_passes(make_ctx: MakeCtx) -> None:
    assert consistency.check(make_ctx()) == []


def test_conflicting_values_for_same_metric_period(make_ctx: MakeCtx) -> None:
    ctx = make_ctx()
    facts = json.loads((ctx.deck_path.parent / "facts.json").read_text())
    dup = dict(facts["facts"][1], id="testco.revenue_dup.fy2024", value="999")
    ctx.facts = ctx.facts.model_validate({"facts": [*facts["facts"], dup]})
    ctx.spec = ctx.spec.model_copy(
        update={
            "slides": [
                *ctx.spec.slides,
                ctx.spec.slides[1].model_copy(
                    update={"bullets": ["{{testco.revenue_dup.fy2024|currency}}"]}
                ),
            ]
        }
    )
    assert any("conflicting values" in i.message for i in consistency.check(ctx))
