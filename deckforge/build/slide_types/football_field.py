"""Valuation football field: native floating-bar chart of implied value ranges."""

from __future__ import annotations

from pptx.slide import Slide

from deckforge.build.charts import RangeBar, football_field
from deckforge.build.formatting import SYMBOL, scaled, units_label
from deckforge.build.slide_types.base import (
    BuildContext,
    data_frame,
    footnote_text,
    remove_empty_placeholders,
    set_title,
)
from deckforge.ingest.models import Unit
from deckforge.spec.models import FootballFieldSlide, FormatKind


class RangeError(ValueError):
    """A bar's low is above its high."""


def axis_number_format(kind: FormatKind, unit: Unit) -> str:
    if kind in (FormatKind.PER_SHARE, FormatKind.CURRENCY):
        return f'"{SYMBOL.get(unit, "$")}"#,##0'
    if kind is FormatKind.MULTIPLE:
        return '0.0"x"'
    if kind is FormatKind.PERCENT:
        return '0"%"'
    return "#,##0"


class FootballFieldSlideType:
    slide_type = "football_field"

    def render(self, slide: Slide, spec: FootballFieldSlide, ctx: BuildContext) -> None:
        set_title(slide, spec.title, spec.layout_id)
        remove_empty_placeholders(slide)
        fmt = spec.format
        unit = ctx.facts.get(spec.bars[0].low).unit
        parts = [spec.units_label or units_label(fmt, unit)]
        if spec.reference:
            parts.append(f"{spec.reference_label}: {ctx.number(spec.reference, fmt)}")
        parts += [f"{m.label}: {ctx.number(m.fact, fmt)}" for m in spec.more_references]
        body = data_frame(
            slide, ctx, "  |  ".join(parts), footnote_text(ctx, spec.fact_refs(), spec.footnote)
        )

        bars: list[RangeBar] = []
        for bar in spec.bars:
            low, high = ctx.facts.get(bar.low), ctx.facts.get(bar.high)
            if low.value > high.value:
                raise RangeError(f"'{bar.label}': low {low.id} is above high {high.id}")
            bars.append(
                RangeBar(
                    label=ctx.text(bar.label),
                    low=float(scaled(low.value, fmt)),
                    high=float(scaled(high.value, fmt)),
                    low_text=ctx.number(low.id, fmt),
                    high_text=ctx.number(high.id, fmt),
                )
            )
        football_field(slide, body, bars, ctx.tokens, axis_number_format(fmt.kind, unit))
