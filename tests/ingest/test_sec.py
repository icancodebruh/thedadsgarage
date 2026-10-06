from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from deckforge.ingest import sec
from deckforge.ingest.models import Unit


def _entry(
    val: float, start: str | None, end: str, filed: str, form: str = "10-K", fp: str = "FY"
) -> dict[str, Any]:
    e = {"val": val, "end": end, "filed": filed, "form": form, "fp": fp, "accn": f"acc-{filed}"}
    if start:
        e["start"] = start
    return e


COMPANY_FACTS = {
    "entityName": "Testco Inc.",
    "facts": {
        "us-gaap": {
            "Revenues": {
                "units": {
                    "USD": [
                        _entry(900, "2023-01-01", "2023-12-31", "2024-02-20"),
                        _entry(1000, "2024-01-01", "2024-12-31", "2025-02-20"),
                        _entry(250, "2024-07-01", "2024-09-30", "2024-11-01", form="10-Q", fp="Q3"),
                        _entry(
                            905, "2023-01-01", "2023-12-31", "2025-02-20"
                        ),  # restated, filed later
                    ]
                }
            },
            "OperatingIncomeLoss": {
                "units": {"USD": [_entry(200, "2024-01-01", "2024-12-31", "2025-02-20")]}
            },
            "DepreciationDepletionAndAmortization": {
                "units": {"USD": [_entry(50, "2024-01-01", "2024-12-31", "2025-02-20")]}
            },
            "CashAndCashEquivalentsAtCarryingValue": {
                "units": {"USD": [_entry(77, None, "2024-12-31", "2025-02-20")]}
            },
        }
    },
}


def test_annual_values_latest_filing_wins() -> None:
    facts = {f.id: f for f in sec.facts_from_companyfacts(COMPANY_FACTS, "TST")}
    assert facts["tst.revenue.fy2024"].value == Decimal(1000)
    assert facts["tst.revenue.fy2023"].value == Decimal(905)  # restatement replaces original
    assert facts["tst.cash.fy2024"].value == Decimal(77)
    assert "accn acc-2025-02-20" in facts["tst.revenue.fy2024"].source_ref
    assert all(f.entity == "Testco Inc." for f in facts.values())


def test_year_filter() -> None:
    facts = sec.facts_from_companyfacts(COMPANY_FACTS, "TST", years=[2024])
    assert {f.period for f in facts} == {"FY2024"}


def test_derived_metrics_cite_inputs() -> None:
    reported = sec.facts_from_companyfacts(COMPANY_FACTS, "TST")
    derived = {f.id: f for f in sec.derive(reported, "TST")}
    assert derived["tst.ebitda.fy2024"].value == Decimal(250)
    assert derived["tst.ebitda_margin.fy2024"].value == Decimal("0.25")
    assert derived["tst.ebitda_margin.fy2024"].unit is Unit.PERCENT
    growth = derived["tst.revenue_growth.fy2024"]
    assert round(growth.value, 4) == Decimal("0.1050")
    assert "tst.revenue.fy2023" in growth.source_ref


def test_user_agent_required() -> None:
    with pytest.raises(sec.SecError, match="SEC_USER_AGENT"):
        sec.ingest_tickers(["TST"], "  ")
