from __future__ import annotations

from pathlib import Path

from deckforge.ingest.excel import read_facts
from deckforge.spec.models import DeckSpec

EXAMPLE = Path(__file__).parent.parent / "examples" / "jazz"


def test_jazz_spec_is_valid_and_fully_tokenised() -> None:
    spec = DeckSpec.load(EXAMPLE / "deck_spec.json")
    assert [s.slide_type for s in spec.slides] == [
        "title",
        "exec_summary",
        "company_overview",
        "financial_table",
        "trading_comps",
        "football_field",
    ]
    assert spec.brief == (EXAMPLE / "brief.md").read_text()


def test_jazz_input_sheet_covers_non_sec_facts() -> None:
    spec = DeckSpec.load(EXAMPLE / "deck_spec.json")
    sheet = read_facts(EXAMPLE / "inputs.xlsx")
    inputs = set(sheet.missing) | {f.id for f in sheet.facts}
    sec_metrics = ("revenue", "revenue_growth", "ebitda", "ebitda_margin", "net_income")
    needed = {r for r in spec.fact_refs() if r.split(".")[1] not in sec_metrics}
    assert needed <= inputs
