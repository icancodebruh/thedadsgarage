from __future__ import annotations

from decimal import Decimal

from deckforge.ingest.models import FactSet
from deckforge.qc.checkers import ties
from tests.qc.conftest import MakeCtx


def _with_value(facts: FactSet, fact_id: str, value: str) -> FactSet:
    return FactSet(
        facts=[
            f.model_copy(update={"value": Decimal(value)}) if f.id == fact_id else f
            for f in facts.facts
        ]
    )


def test_tied_table_passes(make_ctx: MakeCtx) -> None:
    assert ties.check(make_ctx()) == []


def test_total_that_does_not_sum(make_ctx: MakeCtx) -> None:
    ctx = make_ctx()
    ctx.facts = _with_value(ctx.facts, "testco.gross_profit.fy2025", "760000000")
    messages = [i.message for i in ties.check(ctx)]
    assert any("does not equal the sum" in m for m in messages)


def test_ratio_that_does_not_tie(make_ctx: MakeCtx) -> None:
    ctx = make_ctx()
    ctx.facts = _with_value(ctx.facts, "testco.gross_margin.fy2025", "0.65")
    assert any("Gross Profit / Revenue" in i.message for i in ties.check(ctx))
