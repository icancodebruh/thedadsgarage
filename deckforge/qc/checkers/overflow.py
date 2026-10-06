"""Text must fit its box, shapes stay on the slide and inside the template margins."""

from __future__ import annotations

import math

from pptx.shapes.base import BaseShape
from pptx.slide import Slide

from deckforge.qc.checkers.common import has_own_geometry, is_slide_number, paragraph_text
from deckforge.qc.context import QCContext
from deckforge.qc.models import Issue, Severity, SpecFix
from deckforge.template.inventory import shape_box
from deckforge.template.ooxml import EMU_PER_INCH, first, xpath

NAME = "overflow"
AVG_CHAR_EM = 0.5  # average glyph width of a proportional sans font, in ems
LINE_SPACING = 1.2
FIT_TOLERANCE = 1.05
MARGIN_TOLERANCE_IN = 0.05
DEFAULT_INSET_IN = 0.1  # OOXML default left/right inset; 0.05 top/bottom


def _inset(body_pr: object, attr: str, default: float) -> float:
    value = body_pr.get(attr) if body_pr is not None else None  # type: ignore[attr-defined]
    return int(value) / EMU_PER_INCH if value is not None else default


def text_height_in(ctx: QCContext, shape: BaseShape, slide: Slide, width_in: float) -> float:
    """Estimated rendered height of a shape's text when wrapped to `width_in`."""
    tx_body = first(shape.element, "p:txBody")
    if tx_body is None:
        return 0.0
    chain = ctx.resolver.level_chain(shape, slide.slide_layout)
    total = 0.0
    for p in xpath(tx_body, "a:p"):
        style = ctx.resolver.resolve(first(p, "a:r/a:rPr"), first(p, "a:pPr"), chain)
        size_in = style.size_pt / 72
        chars_per_line = max(1, int(width_in / (size_in * AVG_CHAR_EM)))
        lines = max(1, math.ceil(len(paragraph_text(p)) / chars_per_line))
        total += lines * size_in * LINE_SPACING
    return total


def _fix_for(ctx: QCContext, n: int) -> SpecFix | None:
    if n > len(ctx.spec.slides):
        return None
    kind = ctx.spec.slides[n - 1].slide_type
    if kind == "financial_table":
        return SpecFix(kind="split_table", slide=n)
    if kind in ("exec_summary", "company_overview"):
        return SpecFix(kind="revise_slide", slide=n)
    return None


def check(ctx: QCContext) -> list[Issue]:
    issues: list[Issue] = []
    width, height = ctx.style.slide_size.width_in, ctx.style.slide_size.height_in
    m = ctx.style.grid.margins
    for n, slide in ctx.slides():
        for shape in slide.shapes:
            box = shape_box(shape)
            if box is None or not has_own_geometry(shape) or is_slide_number(shape):
                continue
            if box.x < 0 or box.y < 0 or box.x + box.w > width or box.y + box.h > height:
                issues.append(
                    Issue(
                        checker=NAME,
                        severity=Severity.ERROR,
                        slide=n,
                        message=f"'{shape.name}' extends beyond the slide",
                    )
                )
            elif (
                box.x < m.left - MARGIN_TOLERANCE_IN
                or box.x + box.w > width - m.right + MARGIN_TOLERANCE_IN
            ):
                issues.append(
                    Issue(
                        checker=NAME,
                        severity=Severity.WARNING,
                        slide=n,
                        message=f"'{shape.name}' crosses the template side margins",
                    )
                )
            if getattr(shape, "has_table", False):
                needed = _table_height(ctx, shape, slide)
                limit = ctx.style.grid.content_box.y + ctx.style.grid.content_box.h
                if box.y + needed > limit + 0.01:
                    issues.append(
                        Issue(
                            checker=NAME,
                            severity=Severity.ERROR,
                            slide=n,
                            message=f"table '{shape.name}' runs past the content "
                            f"area ({box.y + needed:.2f}in > {limit:.2f}in)",
                            fix=_fix_for(ctx, n),
                        )
                    )
                continue
            body_pr = first(shape.element, "p:txBody/a:bodyPr")
            inner_w = (
                box.w
                - _inset(body_pr, "lIns", DEFAULT_INSET_IN)
                - _inset(body_pr, "rIns", DEFAULT_INSET_IN)
            )
            inner_h = box.h - _inset(body_pr, "tIns", 0.05) - _inset(body_pr, "bIns", 0.05)
            needed = text_height_in(ctx, shape, slide, inner_w)
            if needed > inner_h * FIT_TOLERANCE and needed > 0:
                issues.append(
                    Issue(
                        checker=NAME,
                        severity=Severity.ERROR,
                        slide=n,
                        message=f"text in '{shape.name}' needs ~{needed:.2f}in but "
                        f"the box is {inner_h:.2f}in high",
                        fix=_fix_for(ctx, n),
                    )
                )
    return issues


def _table_height(ctx: QCContext, shape: BaseShape, slide: Slide) -> float:
    """Rows grow to fit their text, so estimate each row's rendered height."""
    table = shape.table  # type: ignore[attr-defined]
    total = 0.0
    for row in table.rows:
        row_h = row.height / EMU_PER_INCH
        for c, cell in enumerate(row.cells):
            col_w = table.columns[c].width / EMU_PER_INCH
            inner_w = col_w - (cell.margin_left + cell.margin_right) / EMU_PER_INCH
            lines = 0.0
            for p in cell.text_frame.paragraphs:
                size_pt = next((r.font.size.pt for r in p.runs if r.font.size), 12.0)
                cpl = max(1, int(inner_w / (size_pt / 72 * AVG_CHAR_EM)))
                lines += max(1, math.ceil(len(p.text) / cpl)) * size_pt / 72 * LINE_SPACING
            pad = (cell.margin_top + cell.margin_bottom) / EMU_PER_INCH
            row_h = max(row_h, lines + pad)
        total += row_h
    return total
