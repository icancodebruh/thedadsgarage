"""Deck-wide number formatting: scaled values, fixed decimals, negatives in brackets."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from deckforge.ingest.models import Fact, Unit
from deckforge.spec.models import FormatKind, NumberFormat, Scale

DASH = "\u2013"  # en dash for empty cells

SCALE_DIVISOR: dict[Scale, Decimal] = {
    Scale.UNITS: Decimal(1),
    Scale.THOUSANDS: Decimal(1_000),
    Scale.MILLIONS: Decimal(1_000_000),
    Scale.BILLIONS: Decimal(1_000_000_000),
}

# Which fact units each display format accepts.
COMPATIBLE_UNITS: dict[FormatKind, frozenset[Unit]] = {
    FormatKind.CURRENCY: frozenset({Unit.USD}),
    FormatKind.PER_SHARE: frozenset({Unit.USD_PER_SHARE}),
    FormatKind.PERCENT: frozenset({Unit.PERCENT}),
    FormatKind.MULTIPLE: frozenset({Unit.RATIO}),
    FormatKind.NUMBER: frozenset({Unit.SHARES, Unit.COUNT}),
}


class FormatError(ValueError):
    """A fact's unit cannot be shown with the requested format."""


def _round(value: Decimal, decimals: int) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)


def format_fact(fact: Fact, fmt: NumberFormat) -> str:
    if fact.unit not in COMPATIBLE_UNITS[fmt.kind]:
        raise FormatError(f"fact '{fact.id}' has unit {fact.unit}, cannot format as {fmt.kind}")
    value = fact.value
    if fmt.kind in (FormatKind.CURRENCY, FormatKind.NUMBER):
        value = value / SCALE_DIVISOR[fmt.scale]
    elif fmt.kind is FormatKind.PERCENT:
        value = value * 100
    rounded = _round(value, fmt.decimals)
    if rounded == 0:
        rounded = abs(rounded)  # avoid "(0.0)"
    body = f"{abs(rounded):,.{fmt.decimals}f}"
    if fmt.kind is FormatKind.PERCENT:
        body += "%"
    elif fmt.kind is FormatKind.MULTIPLE:
        body += "x"
    elif fmt.kind is FormatKind.PER_SHARE:
        body = "$" + body
    return f"({body})" if rounded < 0 else body


def units_label(fmt: NumberFormat) -> str:
    """Default units line shown under a data-slide title, e.g. '($ USD in Millions)'."""
    if fmt.scale is Scale.UNITS:
        return "($ USD)"
    return f"($ USD in {fmt.scale.value.title()})"
