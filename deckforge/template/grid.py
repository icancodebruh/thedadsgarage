"""Infers margins, title/content zones, and alignment guides from shape geometry."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from deckforge.template.models import Box, Grid, Margins

SNAP_TOLERANCE_IN = 0.05
FULL_BLEED_RATIO = 0.95
MAX_GUIDES = 24
LOW_PCT, HIGH_PCT = 5, 95


class Zone(StrEnum):
    TITLE = "title"
    FOOTER = "footer"
    CONTENT = "content"


@dataclass(frozen=True)
class Placed:
    box: Box
    zone: Zone


def percentile(values: Sequence[float], pct: float) -> float:
    """Nearest-rank percentile (deterministic, no interpolation)."""
    if not values:
        raise ValueError("percentile of empty sequence")
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def cluster(values: Sequence[float], tol: float, min_count: int) -> list[tuple[float, int]]:
    """Greedy 1-D clustering of sorted values; returns (mean, count) for dense clusters."""
    out: list[tuple[float, int]] = []
    group: list[float] = []
    for v in sorted(values):
        if group and v - group[-1] > tol:
            out.append((sum(group) / len(group), len(group)))
            group = []
        group.append(v)
    if group:
        out.append((sum(group) / len(group), len(group)))
    return [(round(m, 2), c) for m, c in out if c >= min_count]


def _guides(edges: list[float]) -> list[float]:
    min_count = max(3, math.ceil(0.03 * len(edges)))
    dense = cluster(edges, SNAP_TOLERANCE_IN, min_count)
    top = sorted(dense, key=lambda mc: (-mc[1], mc[0]))[:MAX_GUIDES]
    return sorted(m for m, _ in top)


def _in_bounds(b: Box, width: float, height: float) -> bool:
    full_bleed = b.w >= FULL_BLEED_RATIO * width or b.h >= FULL_BLEED_RATIO * height
    inside = b.x >= 0 and b.y >= 0 and b.x + b.w <= width + 0.01 and b.y + b.h <= height + 0.01
    return inside and not full_bleed and b.w > 0 and b.h > 0


def infer_grid(shapes: Sequence[Placed], width: float, height: float) -> Grid:
    usable = [s for s in shapes if _in_bounds(s.box, width, height)]
    if not usable:
        raise ValueError("no in-bounds shapes to infer a grid from")
    boxes = [s.box for s in usable]
    content = [s.box for s in usable if s.zone is Zone.CONTENT] or boxes
    titles = [s.box for s in usable if s.zone is Zone.TITLE]

    margins = Margins(
        left=round(percentile([b.x for b in boxes], LOW_PCT), 3),
        top=round(percentile([b.y for b in boxes], LOW_PCT), 3),
        right=round(width - percentile([b.x + b.w for b in boxes], HIGH_PCT), 3),
        bottom=round(height - percentile([b.y + b.h for b in boxes], HIGH_PCT), 3),
    )
    title_box = Counter(titles).most_common(1)[0][0] if titles else None
    c_left = percentile([b.x for b in content], LOW_PCT)
    c_right = percentile([b.x + b.w for b in content], HIGH_PCT)
    c_top = percentile([b.y for b in content], LOW_PCT)
    if title_box is not None:
        c_top = max(c_top, title_box.y + title_box.h)
    c_bottom = percentile([b.y + b.h for b in content], HIGH_PCT)
    content_box = Box(
        x=round(c_left, 3),
        y=round(c_top, 3),
        w=round(c_right - c_left, 3),
        h=round(c_bottom - c_top, 3),
    )
    edges_x = [e for b in content + titles for e in (b.x, b.x + b.w)]
    edges_y = [e for b in content + titles for e in (b.y, b.y + b.h)]
    return Grid(
        margins=margins,
        title_box=title_box,
        content_box=content_box,
        x_guides=_guides(edges_x),
        y_guides=_guides(edges_y),
        snap_tolerance_in=SNAP_TOLERANCE_IN,
    )
