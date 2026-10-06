"""Deterministic QC checkers; each module exposes NAME and check(ctx) -> list[Issue]."""

from __future__ import annotations

from collections.abc import Callable

from deckforge.qc.checkers import (
    casing,
    consistency,
    fonts,
    number_format,
    overflow,
    placeholders,
    sources,
    spelling,
    ties,
)
from deckforge.qc.context import QCContext
from deckforge.qc.models import Issue

Checker = Callable[[QCContext], list[Issue]]

CHECKERS: dict[str, Checker] = {
    m.NAME: m.check
    for m in (
        fonts,
        overflow,
        number_format,
        consistency,
        ties,
        sources,
        placeholders,
        casing,
        spelling,
    )
}
