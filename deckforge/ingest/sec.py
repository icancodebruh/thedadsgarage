"""SEC EDGAR XBRL "company facts" -> facts (annual 10-K values, with filing references).

Uses SEC's public JSON API with the standard library. SEC requires a descriptive
User-Agent with contact details: set SEC_USER_AGENT in .env (e.g. "Jane Doe jane@x.com").
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
import logging
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from deckforge.ingest.models import Fact, Unit

log = logging.getLogger(__name__)

COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
ANNUAL_FORMS = frozenset({"10-K", "10-K/A", "20-F", "20-F/A"})
ANNUAL_DAYS = range(350, 381)
TIMEOUT_S = 30


class SecError(RuntimeError):
    """SEC data could not be fetched or did not contain what was asked for."""


@dataclass(frozen=True)
class Concept:
    metric: str
    tags: tuple[str, ...]  # us-gaap tags in priority order
    unit_key: str  # XBRL unit, e.g. "USD" or "USD/shares"
    unit: Unit
    instant: bool = False  # balance-sheet item (point in time) vs. flow over the year


CONCEPTS: tuple[Concept, ...] = (
    Concept(
        "revenue",
        ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"),
        "USD",
        Unit.USD,
    ),
    Concept("gross_profit", ("GrossProfit",), "USD", Unit.USD),
    Concept("operating_income", ("OperatingIncomeLoss",), "USD", Unit.USD),
    Concept("net_income", ("NetIncomeLoss",), "USD", Unit.USD),
    Concept(
        "d_and_a",
        (
            "DepreciationDepletionAndAmortization",
            "DepreciationAndAmortization",
            "DepreciationAmortizationAndAccretionNet",
        ),
        "USD",
        Unit.USD,
    ),
    Concept("eps_diluted", ("EarningsPerShareDiluted",), "USD/shares", Unit.USD_PER_SHARE),
    Concept("cash", ("CashAndCashEquivalentsAtCarryingValue",), "USD", Unit.USD, instant=True),
    Concept(
        "long_term_debt", ("LongTermDebt", "LongTermDebtNoncurrent"), "USD", Unit.USD, instant=True
    ),
)


def _get_json(url: str, user_agent: str) -> Any:
    request = urllib.request.Request(
        url, headers={"User-Agent": user_agent, "Accept-Encoding": "gzip"}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            body = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
    except OSError as exc:
        raise SecError(f"GET {url} failed: {exc}") from exc
    return json.loads(body)


def lookup_cik(ticker: str, user_agent: str) -> int:
    data = _get_json(TICKERS_URL, user_agent)
    for row in data.values():
        if str(row["ticker"]).upper() == ticker.upper():
            return int(row["cik_str"])
    raise SecError(f"ticker {ticker!r} not found in SEC's ticker list")


def fetch_company_facts(cik: int, user_agent: str) -> dict[str, Any]:
    data: dict[str, Any] = _get_json(COMPANY_FACTS_URL.format(cik=cik), user_agent)
    return data


def _annual_entries(entries: Iterable[dict[str, Any]], instant: bool) -> dict[int, dict[str, Any]]:
    """Latest-filed annual value per fiscal-period end year."""
    best: dict[int, dict[str, Any]] = {}
    for e in entries:
        if e.get("form") not in ANNUAL_FORMS:
            continue
        end = dt.date.fromisoformat(e["end"])
        if instant:
            if e.get("fp") != "FY":
                continue
        else:
            start = dt.date.fromisoformat(e["start"]) if e.get("start") else None
            if start is None or (end - start).days not in ANNUAL_DAYS:
                continue
        current = best.get(end.year)
        if current is None or e["filed"] > current["filed"]:
            best[end.year] = e
    return best


def facts_from_companyfacts(
    data: dict[str, Any], ticker: str, years: Iterable[int] | None = None
) -> list[Fact]:
    entity = str(data.get("entityName") or ticker.upper())
    gaap = data.get("facts", {}).get("us-gaap", {})
    wanted = set(years) if years is not None else None
    facts: list[Fact] = []
    for concept in CONCEPTS:
        found: dict[int, tuple[str, dict[str, Any]]] = {}
        for tag in concept.tags:  # earlier tags win for any year they cover
            units = gaap.get(tag, {}).get("units", {}).get(concept.unit_key, [])
            for year, entry in _annual_entries(units, concept.instant).items():
                found.setdefault(year, (tag, entry))
        for year, (tag, e) in sorted(found.items()):
            if wanted is not None and year not in wanted:
                continue
            facts.append(
                Fact(
                    id=f"{ticker.lower()}.{concept.metric}.fy{year}",
                    entity=entity,
                    metric=concept.metric,
                    period=f"FY{year}",
                    value=Decimal(str(e["val"])),
                    unit=concept.unit,
                    source_ref=f"SEC EDGAR {e['form']} (accn {e['accn']}, filed {e['filed']}), "
                    f"us-gaap:{tag}, period ending {e['end']}",
                )
            )
    return facts


def derive(facts: list[Fact], ticker: str) -> list[Fact]:
    """EBITDA, margins and growth computed from reported facts, citing their inputs."""
    t = ticker.lower()
    index = {f.id: f for f in facts}
    out: list[Fact] = []

    def add(
        metric: str, year: int, value: Decimal, unit: Unit, how: str, inputs: list[Fact]
    ) -> None:
        refs = ", ".join(f.id for f in inputs)
        new = Fact(
            id=f"{t}.{metric}.fy{year}",
            entity=inputs[0].entity,
            metric=metric,
            period=f"FY{year}",
            value=value,
            unit=unit,
            source_ref=f"Derived: {how} from {refs}",
        )
        index[new.id] = new
        out.append(new)

    years = sorted({int(f.period[2:]) for f in facts if f.period.startswith("FY")})
    for y in years:
        op, da = index.get(f"{t}.operating_income.fy{y}"), index.get(f"{t}.d_and_a.fy{y}")
        if op and da:
            add("ebitda", y, op.value + da.value, Unit.USD, "operating income + D&A", [op, da])
    for y in years:
        rev = index.get(f"{t}.revenue.fy{y}")
        if rev is None or rev.value == 0:
            continue
        for metric, margin in (
            ("ebitda", "ebitda_margin"),
            ("net_income", "net_margin"),
            ("gross_profit", "gross_margin"),
        ):
            num = index.get(f"{t}.{metric}.fy{y}")
            if num:
                add(
                    margin,
                    y,
                    num.value / rev.value,
                    Unit.PERCENT,
                    f"{metric} / revenue",
                    [num, rev],
                )
        prev = index.get(f"{t}.revenue.fy{y - 1}")
        if prev and prev.value:
            add(
                "revenue_growth",
                y,
                rev.value / prev.value - 1,
                Unit.PERCENT,
                "revenue / prior-year revenue - 1",
                [rev, prev],
            )
    return out


def ingest_tickers(
    tickers: Iterable[str], user_agent: str, years: Iterable[int] | None = None
) -> list[Fact]:
    if not user_agent.strip():
        raise SecError("set SEC_USER_AGENT (name + email), as SEC's fair-access policy requires")
    out: list[Fact] = []
    for ticker in tickers:
        cik = lookup_cik(ticker, user_agent)
        reported = facts_from_companyfacts(fetch_company_facts(cik, user_agent), ticker, years)
        if not reported:
            raise SecError(f"{ticker}: no annual us-gaap facts found")
        out += reported + derive(reported, ticker)
        log.info("sec facts", extra={"ticker": ticker, "cik": cik, "facts": len(reported)})
    return out
