from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from deckforge.ingest.models import Fact, FactSet, MissingFactError, Unit


def _fact(fact_id: str) -> Fact:
    return Fact(
        id=fact_id,
        entity="Testco",
        metric="revenue",
        period="FY2025",
        value=Decimal(1),
        unit=Unit.USD,
        source_ref="test fixture",
    )


def test_duplicate_ids_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate fact ids"):
        FactSet(facts=[_fact("a.b"), _fact("a.b")])


def test_require_lists_every_missing_id() -> None:
    facts = FactSet(facts=[_fact("a.b")])
    assert facts.get("a.b").id == "a.b"
    with pytest.raises(MissingFactError) as err:
        facts.require(["a.b", "z.z", "c.c"])
    assert err.value.missing == ["c.c", "z.z"]


@pytest.mark.parametrize("bad", ["Revenue", "", "a b", ".x"])
def test_fact_id_pattern(bad: str) -> None:
    with pytest.raises(ValidationError):
        _fact(bad)


def test_source_ref_required() -> None:
    with pytest.raises(ValidationError):
        Fact(
            id="a",
            entity="T",
            metric="m",
            period="p",
            value=Decimal(1),
            unit=Unit.USD,
            source_ref="",
        )
