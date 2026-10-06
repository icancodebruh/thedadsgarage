"""Valuation football field: native floating-bar chart of implied value ranges."""

from __future__ import annotations

from pptx.slide import Slide

from deckforge.build.charts import RangeBar, football_field
from deckforge.build.formatting import scaled, units_label
from deckforge.build.slide_types.base import (
    BuildContext,
    data_frame,
    remove_empty_placeholders,
    set_title,
    source_footnote,
)
from deckforge.spec.models import FootballFieldSlide, FormatKind


class RangeError(ValueError):
    """A bar's low is above its high."""


def axis_number_format(kind: FormatKind) -> str:
    if kind in (FormatKind.PER_SHARE, FormatKind.CURRENCY):
        return '"$"#,##0'
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
        units = spec.units_label or units_label(fmt)
        if spec.reference:
            units = f"{units}  |  {spec.reference_label}: {ctx.number(spec.reference, fmt)}"
        body = data_frame(slide, ctx, units)

        bars: list[RangeBar] = []
        for bar in spec.bars:
            low, high = ctx.facts.get(bar.low), ctx.facts.get(bar.high)
            if low.value > high.value:
                raise RangeError(f"'{bar.label}': low {low.id} is above high {high.id}")
            bars.append(
                RangeBar(
                    label=bar.label,
                    low=float(scaled(low.value, fmt)),
                    high=float(scaled(high.value, fmt)),
                    low_text=ctx.number(low.id, fmt),
                    high_text=ctx.number(high.id, fmt),
                )
            )
        football_field(slide, body, bars, ctx.tokens, axis_number_format(fmt.kind))
        source_footnote(slide, ctx)
