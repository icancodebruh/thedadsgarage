"""Trading comparables: peers x metrics native table with computed summary statistics."""

from __future__ import annotations

import statistics
from decimal import Decimal

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
from deckforge.spec.models import CompsRow, FormatKind, RowStyle, Statistic, TradingCompsSlide

LABEL_COL_SHARE = 0.28
STAT_LABELS: dict[Statistic, str] = {
    "median": "Median",
    "mean": "Mean",
    "high": "High",
    "low": "Low",
}


class CompsError(ValueError):
    """A comps column mixes units, so statistics cannot be computed."""


def _stat(name: Statistic, values: list[Decimal]) -> Decimal:
    if name == "median":
        return Decimal(statistics.median(values))
    if name == "mean":
        return sum(values, Decimal(0)) / len(values)
    return max(values) if name == "high" else min(values)


class TradingCompsSlideType:
    slide_type = "trading_comps"

    def render(self, slide: Slide, spec: TradingCompsSlide, ctx: BuildContext) -> None:
        set_title(slide, spec.title, spec.layout_id)
        remove_empty_placeholders(slide)
        currency = next(
            (c.format for c in spec.columns if c.format.kind is FormatKind.CURRENCY), None
        )
        units = spec.units_label or (units_label(currency) if currency else None)
        lines = " ".join(x for x in (spec.subtitle, units) if x) or None
        body = data_frame(slide, ctx, lines)

        peers = [self._row(r, spec, ctx) for r in spec.rows if not r.is_target]
        targets = [self._row(r, spec, ctx) for r in spec.rows if r.is_target]
        rows = peers + self._stats(spec, ctx) + targets
        draw_table(
            slide,
            body,
            ["Company", *[c.header for c in spec.columns]],
            rows,
            ctx.tokens,
            label_share=LABEL_COL_SHARE,
            slide_number=ctx.slide_number,
            what=f"'{spec.title}'",
        )
        source_footnote(slide, ctx)

    def _row(self, row: CompsRow, spec: TradingCompsSlide, ctx: BuildContext) -> RowModel:
        cells = [
            ctx.number(ref, col.format) if ref else DASH
            for ref, col in zip(row.cells, spec.columns, strict=True)
        ]
        return RowModel(
            [row.company, *cells], RowStyle.HIGHLIGHT if row.is_target else RowStyle.NORMAL
        )

    def _stats(self, spec: TradingCompsSlide, ctx: BuildContext) -> list[RowModel]:
        peers = [r for r in spec.rows if not r.is_target]
        out: list[RowModel] = []
        for name in spec.statistics:
            cells: list[str] = []
            for i, col in enumerate(spec.columns):
                facts = ctx.facts.require([ref for r in peers if (ref := r.cells[i])])
                if not facts:
                    cells.append(DASH)
                    continue
                units = {f.unit for f in facts}
                if len(units) > 1:
                    raise CompsError(f"column '{col.header}' mixes units {sorted(units)}")
                value = _stat(name, [f.value for f in facts])
                cells.append(
                    ctx.derived(
                        value,
                        facts[0].unit,
                        col.format,
                        [f.id for f in facts],
                        f"{name} of {len(facts)} peers",
                    )
                )
            out.append(RowModel([STAT_LABELS[name], *cells], RowStyle.SUBTOTAL))
        return out
