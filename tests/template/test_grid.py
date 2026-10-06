from __future__ import annotations

import pytest

from deckforge.template.grid import Placed, Zone, cluster, infer_grid, percentile
from deckforge.template.models import Box


def test_percentile_nearest_rank() -> None:
    assert percentile([5, 1, 3, 2, 4], 50) == 3
    assert percentile([1.0], 95) == 1.0
    with pytest.raises(ValueError):
        percentile([], 50)


def test_cluster_groups_within_tolerance() -> None:
    assert cluster([0.5, 0.52, 0.51, 3.0, 3.01, 7.0], tol=0.05, min_count=2) == [
        (0.51, 3),
        (3.0, 2),
    ]


def test_infer_grid_margins_title_and_content() -> None:
    title = Box(x=0.5, y=0.4, w=9.0, h=0.5)
    shapes = [Placed(title, Zone.TITLE)] * 5 + [
        Placed(Box(x=0.5, y=1.2, w=4.25, h=2.0), Zone.CONTENT),
        Placed(Box(x=5.25, y=1.2, w=4.25, h=2.0), Zone.CONTENT),
        Placed(Box(x=0.5, y=3.5, w=9.0, h=3.0), Zone.CONTENT),
        Placed(Box(x=0, y=0, w=10, h=7.5), Zone.CONTENT),  # full-bleed: ignored
        Placed(Box(x=0.5, y=7.0, w=2.0, h=0.3), Zone.FOOTER),
    ]
    grid = infer_grid(shapes, width=10, height=7.5)
    assert grid.title_box == title
    assert grid.margins.left == 0.5
    assert grid.margins.right == 0.5
    assert grid.content_box == Box(x=0.5, y=1.2, w=9.0, h=5.3)
    assert 0.5 in grid.x_guides


def test_infer_grid_requires_shapes() -> None:
    with pytest.raises(ValueError):
        infer_grid([], width=10, height=7.5)
