from __future__ import annotations

from decimal import Decimal

import pytest

from deckforge.build.formatting import FormatError, format_fact, units_label
from deckforge.ingest.models import Fact, Unit
from deckforge.spec.models import FormatKind, NumberFormat, Scale


def _fact(value: str, unit: Unit) -> Fact:
    return Fact(
        id="x",
        entity="T",
        metric="m",
        period="p",
        value=Decimal(value),
        unit=unit,
        source_ref="test fixture",
    )


@pytest.mark.parametrize(
    ("value", "unit", "fmt", "expected"),
    [
        ("1012650000", Unit.USD, NumberFormat(kind=FormatKind.CURRENCY), "1,012.7"),
        ("-12340000", Unit.USD, NumberFormat(kind=FormatKind.CURRENCY), "(12.3)"),
        ("-10000", Unit.USD, NumberFormat(kind=FormatKind.CURRENCY), "0.0"),
        (
            "2500000000",
            Unit.USD,
            NumberFormat(kind=FormatKind.CURRENCY, scale=Scale.BILLIONS),
            "2.5",
        ),
        ("0.2555", Unit.PERCENT, NumberFormat(kind=FormatKind.PERCENT), "25.6%"),
        ("-0.05", Unit.PERCENT, NumberFormat(kind=FormatKind.PERCENT), "(5.0%)"),
        ("12.25", Unit.RATIO, NumberFormat(kind=FormatKind.MULTIPLE), "12.3x"),
        (
            "147.4",
            Unit.USD_PER_SHARE,
            NumberFormat(kind=FormatKind.PER_SHARE, decimals=2),
            "$147.40",
        ),
        ("61234567", Unit.SHARES, NumberFormat(kind=FormatKind.NUMBER, decimals=0), "61"),
    ],
)
def test_format_fact(value: str, unit: Unit, fmt: NumberFormat, expected: str) -> None:
    assert format_fact(_fact(value, unit), fmt) == expected


def test_unit_mismatch_raises() -> None:
    with pytest.raises(FormatError):
        format_fact(_fact("0.2", Unit.PERCENT), NumberFormat(kind=FormatKind.CURRENCY))


def test_units_label() -> None:
    assert units_label(NumberFormat(kind=FormatKind.CURRENCY)) == "($ USD in Millions)"
    assert units_label(NumberFormat(kind=FormatKind.CURRENCY, scale=Scale.UNITS)) == "($ USD)"
