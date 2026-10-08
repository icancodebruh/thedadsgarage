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
# House convention: lower-case scale suffixes in running text ($3.8bn, \u20b9271.2m).
SCALE_SUFFIX: dict[Scale, str] = {
    Scale.UNITS: "",
    Scale.THOUSANDS: "k",
    Scale.MILLIONS: "m",
    Scale.BILLIONS: "bn",
}

CURRENCY_UNITS = frozenset({Unit.USD, Unit.INR})
PER_SHARE_UNITS = frozenset({Unit.USD_PER_SHARE, Unit.INR_PER_SHARE})
SYMBOL: dict[Unit, str] = {
    Unit.USD: "$",
    Unit.USD_PER_SHARE: "$",
    Unit.INR: "\u20b9",
    Unit.INR_PER_SHARE: "\u20b9",
}
CURRENCY_CODE: dict[Unit, str] = {Unit.USD: "USD", Unit.INR: "INR"}

# Which fact units each display format accepts.
COMPATIBLE_UNITS: dict[FormatKind, frozenset[Unit]] = {
    FormatKind.CURRENCY: CURRENCY_UNITS,
    FormatKind.PER_SHARE: PER_SHARE_UNITS,
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
        body = SYMBOL[unit] + body
    elif fmt.kind is FormatKind.CURRENCY and inline:
        body = SYMBOL[unit] + body + SCALE_SUFFIX[fmt.scale]
    elif fmt.kind is FormatKind.CURRENCY and fmt.symbol:
        body = SYMBOL[unit] + body
    elif fmt.kind is FormatKind.NUMBER and inline:
        body += SCALE_SUFFIX[fmt.scale]
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


def units_label(fmt: NumberFormat, unit: Unit = Unit.USD) -> str:
    """Default units line under a data-slide title, e.g. '($ USD in Millions)'."""
    base = unit if unit in CURRENCY_CODE else {Unit.INR_PER_SHARE: Unit.INR}.get(unit, Unit.USD)
    label = f"{SYMBOL[base]} {CURRENCY_CODE[base]}"
    if fmt.kind is FormatKind.PER_SHARE or fmt.scale is Scale.UNITS:
        return f"({label})"
    return f"({label} in {fmt.scale.value.title()})"
