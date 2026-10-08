from __future__ import annotations

from decimal import Decimal

from deckforge.build.formatting import format_value
from deckforge.ingest.models import Unit
from deckforge.spec.models import FormatKind, NumberFormat, Scale


def test_inline_currency_has_symbol_and_suffix() -> None:
    fmt = NumberFormat(kind=FormatKind.CURRENCY, scale=Scale.BILLIONS, decimals=1)
    assert format_value(Decimal("3812000000"), Unit.USD, fmt, inline=True) == "$3.8bn"
    assert (
        format_value(
            Decimal("-12000000"), Unit.USD, NumberFormat(kind=FormatKind.CURRENCY), inline=True
        )
        == "($12.0m)"
    )
