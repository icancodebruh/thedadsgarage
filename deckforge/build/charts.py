"""Native PowerPoint charts styled from design tokens."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import cast

from pptx.chart.data import CategoryChartData, ChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.shapes.graphfrm import GraphicFrame
from pptx.slide import Slide
from pptx.util import Inches, Pt

from deckforge.build.style_tokens import StyleTokens
from deckforge.template.models import Box

GAP_WIDTH = 60
AXIS_PAD = 0.12  # share of the data span left empty either side of the bars


LABEL_SPACE = 0.18  # share of the data span reserved right of each bar for its high label
NICE_STEPS = (1.0, 2.0, 2.5, 5.0, 10.0)
TARGET_TICKS = 6


@dataclass(frozen=True)
class RangeBar:
    label: str
    low: float
    high: float
    low_text: str  # already formatted and bound to facts
    high_text: str


def _rgb(hex_: str) -> RGBColor:
    return cast(RGBColor, RGBColor.from_string(hex_))  # type: ignore[no-untyped-call]


def nice_step(span: float) -> float:
    """A 1/2/2.5/5 x 10^k tick step giving roughly TARGET_TICKS ticks over `span`."""
    raw = span / TARGET_TICKS
    magnitude = 10 ** math.floor(math.log10(raw))
    return float(next(m * magnitude for m in NICE_STEPS if m * magnitude >= raw))


def axis_bounds(bars: list[RangeBar]) -> tuple[float, float, float]:
    """Axis min/max/step: padded, rounded to ticks, room for the high labels."""
    lo, hi = min(b.low for b in bars), max(b.high for b in bars)
    span = hi - lo or abs(hi) or 1.0
    step = nice_step(span * (1 + AXIS_PAD * 2 + LABEL_SPACE))
    low = math.floor((lo - span * AXIS_PAD) / step) * step
    high = math.ceil((hi + span * (AXIS_PAD + LABEL_SPACE)) / step) * step
    return max(low, 0.0) if lo >= 0 else low, high, step


def football_field(
    slide: Slide, box: Box, bars: list[RangeBar], tokens: StyleTokens, axis_format: str
) -> GraphicFrame:
    """Horizontal floating bars: invisible base + visible range + invisible label pad.

    The low value is labelled at the inside end of the invisible base (just left of the
    bar) and the high value at the inside base of the pad (just right of the bar), so
    labels never clip inside narrow ranges.
    """
    ordered = list(reversed(bars))  # bar charts plot bottom-up; keep spec order top-down
    lo, hi, step = axis_bounds(bars)
    pad = (hi - lo) * LABEL_SPACE
    data = CategoryChartData(number_format=axis_format)  # type: ignore[no-untyped-call]
    data.categories = [b.label for b in ordered]
    data.add_series("Low", [b.low for b in ordered])  # type: ignore[no-untyped-call]
    data.add_series("Range", [b.high - b.low for b in ordered])  # type: ignore[no-untyped-call]
    data.add_series("Pad", [pad for _ in ordered])  # type: ignore[no-untyped-call]
    frame = slide.shapes.add_chart(
        XL_CHART_TYPE.BAR_STACKED,
        Inches(box.x),
        Inches(box.y),
        Inches(box.w),
        Inches(box.h),
        cast(ChartData, data),
    )
    chart = frame.chart  # type: ignore[attr-defined]
    chart.has_legend = False
    chart.font.name = tokens.table.font
    chart.font.size = Pt(tokens.table.size_pt)
    chart.font.color.rgb = _rgb(tokens.table.color)

    plot = chart.plots[0]
    plot.gap_width = GAP_WIDTH
    plot.overlap = 100
    base, span, spacer = plot.series
    for invisible in (base, spacer):
        invisible.format.fill.background()
        invisible.format.line.fill.background()
    span.format.fill.solid()
    span.format.fill.fore_color.rgb = _rgb(tokens.header_fill)
    for series, position, attr in (
        (base, XL_LABEL_POSITION.INSIDE_END, "low_text"),
        (spacer, XL_LABEL_POSITION.INSIDE_BASE, "high_text"),
    ):
        for point, bar in zip(series.points, ordered, strict=True):
            label = point.data_label
            label.position = position
            label.text_frame.text = getattr(bar, attr)
            run = label.text_frame.paragraphs[0].runs[0]
            run.font.size = Pt(tokens.footnote.size_pt)
            run.font.bold = True
            run.font.color.rgb = _rgb(tokens.table.color)

    value_axis = chart.value_axis
    value_axis.minimum_scale, value_axis.maximum_scale = lo, hi
    value_axis.major_unit = step
    value_axis.has_major_gridlines = True
    value_axis.major_gridlines.format.line.color.rgb = _rgb(tokens.emphasis_fill)
    value_axis.tick_labels.number_format = axis_format
    value_axis.tick_labels.number_format_is_linked = False
    value_axis.tick_labels.font.size = Pt(tokens.footnote.size_pt)
    value_axis.format.line.fill.background()
    category_axis = chart.category_axis
    category_axis.format.line.color.rgb = _rgb(tokens.table.color)
    category_axis.tick_labels.font.size = Pt(tokens.table.size_pt)
    return cast(GraphicFrame, frame)
