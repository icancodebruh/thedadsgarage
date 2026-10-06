"""Deck-wide number formatting: scaled values, fixed decimals, negatives in brackets."""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

from deckforge.ingest.models import Fact, Unit
from deckforge.spec.models import FormatKind, NumberFormat, Scale
from deckforge.spec.tokens import FACT_TOKEN, token_refs

__all__ = ["FACT_TOKEN", "token_refs"]

DASH = "\u2013"  # en dash for empty cells

SCALE_DIVISOR: dict[Scale, Decimal] = {
    Scale.UNITS: Decimal(1),
    Scale.THOUSANDS: Decimal(1_000),
    Scale.MILLIONS: Decimal(1_000_000),
    Scale.BILLIONS: Decimal(1_000_000_000),
}
SCALE_SUFFIX: dict[Scale, str] = {
    Scale.UNITS: "",
    Scale.THOUSANDS: "K",
    Scale.MILLIONS: "M",
    Scale.BILLIONS: "B",
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
    """A fact's unit cannot be shown with the requested format, or a token is malformed."""


def round_half_up(value: Decimal, decimals: int) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)


def scaled(value: Decimal, fmt: NumberFormat) -> Decimal:
    """The number as displayed before rounding (scale applied, percent x100)."""
    if fmt.kind in (FormatKind.CURRENCY, FormatKind.NUMBER):
        return value / SCALE_DIVISOR[fmt.scale]
    if fmt.kind is FormatKind.PERCENT:
        return value * 100
    return value


def check_unit(unit: Unit, fmt: NumberFormat, what: str) -> None:
    if unit not in COMPATIBLE_UNITS[fmt.kind]:
        raise FormatError(f"{what} has unit {unit}, cannot format as {fmt.kind}")


def format_value(value: Decimal, unit: Unit, fmt: NumberFormat, *, inline: bool = False) -> str:
    """Format a number. `inline` (running text) adds $ and a scale suffix to currency."""
    check_unit(unit, fmt, f"value {value}")
    rounded = round_half_up(scaled(value, fmt), fmt.decimals)
    if rounded == 0:
        rounded = abs(rounded)  # avoid "(0.0)"
    body = f"{abs(rounded):,.{fmt.decimals}f}"
    if fmt.kind is FormatKind.PERCENT:
        body += "%"
    elif fmt.kind is FormatKind.MULTIPLE:
        body += "x"
    elif fmt.kind is FormatKind.PER_SHARE:
        body = "$" + body
    elif fmt.kind is FormatKind.CURRENCY and inline:
        body = "$" + body + SCALE_SUFFIX[fmt.scale]
    return f"({body})" if rounded < 0 else body


def format_fact(fact: Fact, fmt: NumberFormat, *, inline: bool = False) -> str:
    check_unit(fact.unit, fmt, f"fact '{fact.id}'")
    return format_value(fact.value, fact.unit, fmt, inline=inline)


def parse_token(match: re.Match[str]) -> tuple[str, NumberFormat]:
    try:
        kind = FormatKind(match["kind"])
        fmt = NumberFormat(
            kind=kind,
            scale=Scale(match["scale"]) if match["scale"] else Scale.MILLIONS,
            decimals=int(match["decimals"]) if match["decimals"] else 1,
        )
    except ValueError as exc:
        raise FormatError(f"bad fact token {match[0]!r}: {exc}") from exc
    return match["id"], fmt


def units_label(fmt: NumberFormat) -> str:
    """Default units line shown under a data-slide title, e.g. '($ USD in Millions)'."""
    if fmt.kind is FormatKind.PER_SHARE or fmt.scale is Scale.UNITS:
        return "($ USD)"
    return f"($ USD in {fmt.scale.value.title()})"
