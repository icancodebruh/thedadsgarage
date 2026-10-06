"""Financial summary table: native table bound to facts, with units line and source."""

from __future__ import annotations

from pptx.slide import Slide

from deckforge.build.formatting import DASH, units_label
from deckforge.build.slide_types.base import (
    BuildContext,
    data_frame,
    remove_empty_placeholders,
    set_title,
    source_footnote,
)
from deckforge.build.tables import RowModel, draw_table
from deckforge.spec.models import FinancialTableSlide, FormatKind

LABEL_COL_SHARE = 0.32


class FinancialTableSlideType:
    slide_type = "financial_table"

    def render(self, slide: Slide, spec: FinancialTableSlide, ctx: BuildContext) -> None:
        set_title(slide, spec.title, spec.layout_id)
        remove_empty_placeholders(slide)
        currency = next(
            (r.format for r in spec.rows if r.format.kind is FormatKind.CURRENCY),
            spec.rows[0].format,
        )
        body = data_frame(slide, ctx, spec.units_label or units_label(currency))
        rows = [
            RowModel(
                [r.label] + [ctx.number(ref, r.format) if ref else DASH for ref in r.cells],
                r.style,
            )
            for r in spec.rows
        ]
        draw_table(
            slide,
            body,
            ["", *spec.columns],
            rows,
            ctx.tokens,
            label_share=LABEL_COL_SHARE,
            slide_number=ctx.slide_number,
            what=f"'{spec.title}'",
        )
        source_footnote(slide, ctx)
