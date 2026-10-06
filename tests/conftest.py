"""Shared fixtures: a small self-made reference deck built with python-pptx."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

NAVY = RGBColor.from_string("113D63")
GREY = RGBColor.from_string("CCD1D7")


@pytest.fixture(scope="session")
def reference_deck(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("deck")
    png = tmp / "chart.png"
    Image.new("RGB", (400, 300), "white").save(png)

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(10), Inches(7.5)
    title_layout, content_layout = prs.slide_layouts[0], prs.slide_layouts[5]  # title only

    slide = prs.slides.add_slide(title_layout)
    slide.shapes.title.text = "Project Falcon"

    titles = ["Executive Summary", "Valuation Overview for Falcon", "Trading Comparables"]
    for i, title in enumerate(titles):
        slide = prs.slides.add_slide(content_layout)
        slide.shapes.title.text = title
        box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(1.5),
                                     Inches(4), Inches(1))  # fmt: skip
        box.fill.solid()
        box.fill.fore_color.rgb = NAVY
        run = box.text_frame.paragraphs[0].add_run()
        run.text = "Key message"
        run.font.name, run.font.size = "Arial", Pt(12)
        run.font.color.rgb = RGBColor.from_string("FFFFFF")
        if i == 1:
            table = slide.shapes.add_table(3, 2, Inches(0.5), Inches(3), Inches(6), Inches(1.5))
            table.table.cell(0, 0).text = "Metric"
            table.table.cell(1, 0).fill.solid()
            table.table.cell(1, 0).fill.fore_color.rgb = GREY
        if i == 2:
            slide.shapes.add_picture(str(png), Inches(0.5), Inches(3), Inches(8), Inches(3.5))

    path = tmp / "reference.pptx"
    prs.save(str(path))
    return path
