"""Financial summary table: native PowerPoint table bound to facts, with units and source."""

from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.slide import Slide
from pptx.table import _Cell
from pptx.util import Emu, Inches

from deckforge.build.formatting import DASH, format_fact, units_label
from deckforge.build.slide_types.base import (
    BuildContext,
    LayoutOverflowError,
    add_text,
    find_placeholder,
    remove_empty_placeholders,
    style_run,
)
from deckforge.build.slide_types.title import LayoutMismatchError
from deckforge.build.style_tokens import TextToken
from deckforge.ingest.models import Fact
from deckforge.spec.models import FinancialTableSlide, FormatKind, RowStyle
from deckforge.template.models import Box

LINE_HEIGHT = 1.4  # line box height as a multiple of font size
ROW_HEIGHT = 1.8  # table row height as a multiple of font size
LABEL_COL_SHARE = 0.32
GAP_IN = 0.1
CELL_PAD_X_IN, CELL_PAD_Y_IN = 0.05, 0.02
MEMO_INDENT_IN = 0.2


def _pt_to_in(pt: float, factor: float) -> float:
    return pt * factor / 72


class FinancialTableSlideType:
    slide_type = "financial_table"

    def render(self, slide: Slide, spec: FinancialTableSlide, ctx: BuildContext) -> None:
        tokens = ctx.tokens
        facts = {f.id: f for f in ctx.facts.require(spec.fact_refs())}

        title = find_placeholder(slide, PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE)
        if title is None:
            raise LayoutMismatchError(f"layout '{spec.layout_id}' has no title placeholder")
        title.text_frame.text = spec.title
        remove_empty_placeholders(slide)

        cb = tokens.content_box
        line_h = _pt_to_in(tokens.footnote.size_pt, LINE_HEIGHT)
        currency = next(
            (r.format for r in spec.rows if r.format.kind is FormatKind.CURRENCY),
            spec.rows[0].format,
        )
        add_text(
            slide,
            Box(x=cb.x, y=cb.y, w=cb.w, h=line_h),
            spec.units_label or units_label(currency),
            tokens.footnote,
        )

        sources = sorted({f.source_ref for f in facts.values()})
        note = "Source: " + "; ".join(sources)
        note_h = line_h * 2
        add_text(
            slide, Box(x=cb.x, y=cb.y + cb.h - note_h, w=cb.w, h=note_h), note, tokens.footnote
        )

        row_h = _pt_to_in(tokens.table.size_pt, ROW_HEIGHT)
        n_rows = len(spec.rows) + 1
        top = cb.y + line_h + GAP_IN
        available = (cb.y + cb.h - note_h - GAP_IN) - top
        if row_h * n_rows > available:
            raise LayoutOverflowError(
                f"'{spec.title}': {n_rows} rows need {row_h * n_rows:.2f}in, "
                f"only {available:.2f}in available"
            )
        self._table(slide, spec, ctx, facts, Box(x=cb.x, y=top, w=cb.w, h=row_h * n_rows))

    def _table(
        self,
        slide: Slide,
        spec: FinancialTableSlide,
        ctx: BuildContext,
        facts: dict[str, Fact],
        box: Box,
    ) -> None:
        tokens = ctx.tokens
        n_cols = len(spec.columns) + 1
        frame = slide.shapes.add_table(
            len(spec.rows) + 1, n_cols, Inches(box.x), Inches(box.y), Inches(box.w), Inches(box.h)
        )
        table = frame.table
        table.first_row = True
        table.horz_banding = False

        total_w = Inches(box.w)
        label_w = int(total_w * LABEL_COL_SHARE)
        value_w = (total_w - label_w) // len(spec.columns)
        table.columns[0].width = Emu(label_w)
        for i in range(1, n_cols):
            table.columns[i].width = Emu(value_w)
        table.columns[n_cols - 1].width = Emu(total_w - label_w - value_w * (n_cols - 2))
        row_h = Emu(Inches(box.h) // (len(spec.rows) + 1))
        for row in table.rows:
            row.height = row_h

        for c, label in enumerate(["", *spec.columns]):
            _cell(
                table.cell(0, c),
                label,
                token=tokens.table,
                bold=True,
                align=PP_ALIGN.LEFT if c == 0 else PP_ALIGN.RIGHT,
                fill=tokens.header_fill,
                color=tokens.header_text,
            )

        for r, row in enumerate(spec.rows, start=1):
            bold = row.style in (RowStyle.TOTAL, RowStyle.SUBTOTAL)
            fill = tokens.emphasis_fill if row.style is RowStyle.TOTAL else None
            indent = MEMO_INDENT_IN if row.style is RowStyle.MEMO else 0.0
            _cell(
                table.cell(r, 0),
                row.label,
                token=tokens.table,
                bold=bold,
                fill=fill,
                align=PP_ALIGN.LEFT,
                indent=indent,
            )
            for c, ref in enumerate(row.cells, start=1):
                text = format_fact(facts[ref], row.format) if ref else DASH
                _cell(
                    table.cell(r, c),
                    text,
                    token=tokens.table,
                    bold=bold,
                    fill=fill,
                    align=PP_ALIGN.RIGHT,
                )


def _cell(
    cell: _Cell,
    text: str,
    *,
    token: TextToken,
    bold: bool,
    align: PP_ALIGN,
    fill: str | None,
    color: str | None = None,
    indent: float = 0.0,
) -> None:
    if fill:
        cell.fill.solid()  # type: ignore[no-untyped-call]
        cell.fill.fore_color.rgb = RGBColor.from_string(fill)  # type: ignore[no-untyped-call]
    else:
        cell.fill.background()  # type: ignore[no-untyped-call]  # explicit no-fill overrides the table style
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    cell.margin_left = Inches(CELL_PAD_X_IN + indent)
    cell.margin_right = Inches(CELL_PAD_X_IN)
    cell.margin_top = cell.margin_bottom = Inches(CELL_PAD_Y_IN)
    paragraph = cell.text_frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text
    style_run(run, token, bold=bold, color=color)
