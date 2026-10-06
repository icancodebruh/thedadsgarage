"""Slide-type plugins, keyed by `slide_type`."""

from __future__ import annotations

from deckforge.build.slide_types.base import SlideType
from deckforge.build.slide_types.company_overview import CompanyOverviewSlideType
from deckforge.build.slide_types.exec_summary import ExecSummarySlideType
from deckforge.build.slide_types.financial_table import FinancialTableSlideType
from deckforge.build.slide_types.football_field import FootballFieldSlideType
from deckforge.build.slide_types.title import TitleSlideType
from deckforge.build.slide_types.trading_comps import TradingCompsSlideType

REGISTRY: dict[str, SlideType] = {
    plugin.slide_type: plugin
    for plugin in (
        TitleSlideType(),
        ExecSummarySlideType(),
        CompanyOverviewSlideType(),
        FinancialTableSlideType(),
        TradingCompsSlideType(),
        FootballFieldSlideType(),
    )
}
