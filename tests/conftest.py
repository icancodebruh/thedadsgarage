"""Shared fixtures: a small self-made reference deck built with python-pptx."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, TypeVar

import pytest
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt
from pydantic import BaseModel

from deckforge.template.analyze import analyze_template, write_outputs

T = TypeVar("T", bound=BaseModel)

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
        box = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(1.5), Inches(4), Inches(1)
        )
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


# Synthetic test facts (not real company data).
TEST_SOURCE = "test fixture"
TEST_VALUES = {
    "revenue": ("USD", ["1000000000", "1250000000"]),
    "net_income": ("USD", ["-12340000", "56780000"]),
    "ebitda_margin": ("percent", ["0.2", "0.255"]),
}


def write_json(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


@pytest.fixture
def deck_inputs(reference_deck: Path, tmp_path: Path) -> Path:
    """A spec directory: analyzed template, synthetic facts, and a 2-slide deck_spec.json."""
    style, library = analyze_template(reference_deck)
    write_outputs(style, library, tmp_path)
    shutil.copy(reference_deck, tmp_path / "template.pptx")
    facts = [
        {
            "id": f"testco.{metric}.fy{2024 + i}",
            "entity": "Testco",
            "metric": metric,
            "period": f"FY{2024 + i}",
            "value": v,
            "unit": unit,
            "source_ref": TEST_SOURCE,
        }
        for metric, (unit, values) in TEST_VALUES.items()
        for i, v in enumerate(values)
    ]
    write_json(tmp_path / "facts.json", {"facts": facts})
    usd = {"kind": "currency", "scale": "millions", "decimals": 1}
    spec = {
        "brief": "Test deck",
        "template": {"pptx": "template.pptx", "style": "style.json", "layouts": "layouts.json"},
        "facts": "facts.json",
        "slides": [
            {
                "slide_type": "title",
                "title": "Project Testco",
                "subtitle": "Board update",
                "date": "2026-10-06",
            },
            {
                "slide_type": "financial_table",
                "title": "Testco Financial Summary",
                "columns": ["FY 2024", "FY 2025"],
                "rows": [
                    {
                        "label": "Revenue",
                        "cells": ["testco.revenue.fy2024", "testco.revenue.fy2025"],
                        "format": usd,
                    },
                    {
                        "label": "% Margin",
                        "cells": [None, "testco.ebitda_margin.fy2025"],
                        "format": {"kind": "percent"},
                        "style": "memo",
                    },
                    {
                        "label": "Net Income",
                        "cells": ["testco.net_income.fy2024", "testco.net_income.fy2025"],
                        "format": usd,
                        "style": "total",
                    },
                ],
            },
        ],
    }
    write_json(tmp_path / "deck_spec.json", spec)
    return tmp_path


FULL_FACTS = {
    # id: (entity, metric, period, value, unit)
    "testco.revenue.fy2024": ("Testco", "revenue", "FY2024", "1000000000", "USD"),
    "testco.revenue.fy2025": ("Testco", "revenue", "FY2025", "1250000000", "USD"),
    "testco.cogs.fy2025": ("Testco", "cogs", "FY2025", "-500000000", "USD"),
    "testco.gross_profit.fy2025": ("Testco", "gross_profit", "FY2025", "750000000", "USD"),
    "testco.gross_margin.fy2025": ("Testco", "gross_margin", "FY2025", "0.6", "percent"),
    "testco.share_price.current": ("Testco", "share_price", "current", "42.5", "USD_per_share"),
    "testco.ev_ebitda.ltm": ("Testco", "ev_ebitda", "LTM", "9.5", "ratio"),
    "peera.ev_ebitda.ltm": ("Peer A", "ev_ebitda", "LTM", "10", "ratio"),
    "peerb.ev_ebitda.ltm": ("Peer B", "ev_ebitda", "LTM", "12", "ratio"),
    "peerc.ev_ebitda.ltm": ("Peer C", "ev_ebitda", "LTM", "17", "ratio"),
    "testco.val_dcf.low": ("Testco", "val_dcf_low", "current", "38", "USD_per_share"),
    "testco.val_dcf.high": ("Testco", "val_dcf_high", "current", "51", "USD_per_share"),
    "testco.val_comps.low": ("Testco", "val_comps_low", "current", "40", "USD_per_share"),
    "testco.val_comps.high": ("Testco", "val_comps_high", "current", "47", "USD_per_share"),
}


@pytest.fixture
def full_inputs(reference_deck: Path, tmp_path: Path) -> Path:
    """A spec directory exercising all six slide types (synthetic test data)."""
    style, library = analyze_template(reference_deck)
    write_outputs(style, library, tmp_path)
    shutil.copy(reference_deck, tmp_path / "template.pptx")
    facts = [
        {
            "id": i,
            "entity": e,
            "metric": m,
            "period": p,
            "value": v,
            "unit": u,
            "source_ref": TEST_SOURCE,
        }
        for i, (e, m, p, v, u) in FULL_FACTS.items()
    ]
    write_json(tmp_path / "facts.json", {"facts": facts})
    usd = {"kind": "currency", "scale": "millions", "decimals": 1}
    mult = {"kind": "multiple"}
    spec = {
        "brief": "Test deck with every slide type",
        "template": {"pptx": "template.pptx", "style": "style.json", "layouts": "layouts.json"},
        "facts": "facts.json",
        "slides": [
            {"slide_type": "title", "title": "Project Testco", "date": "2026-10-06"},
            {
                "slide_type": "exec_summary",
                "title": "Executive Summary",
                "bullets": [
                    "Revenue reached {{testco.revenue.fy2025|currency:billions:2}} in FY2025",
                    "Testco trades at {{testco.ev_ebitda.ltm|multiple:1}} LTM EBITDA",
                ],
            },
            {
                "slide_type": "company_overview",
                "title": "Testco at a Glance",
                "description": "Testco makes test fixtures.",
                "highlights": ["Gross margin of {{testco.gross_margin.fy2025|percent:1}}"],
                "key_stats": [
                    {
                        "label": "Share price",
                        "fact": "testco.share_price.current",
                        "format": {"kind": "per_share", "decimals": 2},
                    }
                ],
            },
            {
                "slide_type": "financial_table",
                "title": "Testco Financial Summary",
                "columns": ["FY 2025"],
                "rows": [
                    {"label": "Revenue", "cells": ["testco.revenue.fy2025"], "format": usd},
                    {"label": "COGS", "cells": ["testco.cogs.fy2025"], "format": usd},
                    {
                        "label": "Gross Profit",
                        "cells": ["testco.gross_profit.fy2025"],
                        "format": usd,
                        "style": "total",
                        "sum_of": ["Revenue", "COGS"],
                    },
                    {
                        "label": "% Margin",
                        "cells": ["testco.gross_margin.fy2025"],
                        "format": {"kind": "percent"},
                        "style": "memo",
                        "ratio_of": ["Gross Profit", "Revenue"],
                    },
                ],
            },
            {
                "slide_type": "trading_comps",
                "title": "Comparable Companies",
                "columns": [{"header": "EV / EBITDA", "format": mult}],
                "rows": [
                    {"company": "Peer A", "cells": ["peera.ev_ebitda.ltm"]},
                    {"company": "Peer B", "cells": ["peerb.ev_ebitda.ltm"]},
                    {"company": "Peer C", "cells": ["peerc.ev_ebitda.ltm"]},
                    {"company": "Testco", "cells": ["testco.ev_ebitda.ltm"], "is_target": True},
                ],
            },
            {
                "slide_type": "football_field",
                "title": "Valuation Summary",
                "reference": "testco.share_price.current",
                "bars": [
                    {"label": "DCF", "low": "testco.val_dcf.low", "high": "testco.val_dcf.high"},
                    {
                        "label": "Comps",
                        "low": "testco.val_comps.low",
                        "high": "testco.val_comps.high",
                    },
                ],
            },
        ],
    }
    write_json(tmp_path / "deck_spec.json", spec)
    return tmp_path


def build_full(inputs: Path) -> Path:
    from deckforge.build.renderer import build_deck
    from deckforge.spec.models import DeckSpec

    return build_deck(DeckSpec.load(inputs / "deck_spec.json"), inputs, inputs / "deck.pptx")


class FakeLLM:
    """Returns queued structured answers in order and records what it was asked."""

    def __init__(self, *answers: object) -> None:
        self.answers = list(answers)
        self.calls: list[dict[str, Any]] = []

    def structured(self, *, system: str, content: list[dict[str, Any]], schema: type[T]) -> T:
        self.calls.append({"system": system, "content": content, "schema": schema})
        answer = self.answers.pop(0)
        return schema.model_validate(answer) if isinstance(answer, dict) else answer  # type: ignore[return-value]
