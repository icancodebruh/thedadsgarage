"""Slide-type plugins, keyed by `slide_type`."""

from __future__ import annotations

from deckforge.build.slide_types.base import SlideType
from deckforge.build.slide_types.financial_table import FinancialTableSlideType
from deckforge.build.slide_types.title import TitleSlideType

REGISTRY: dict[str, SlideType] = {
    plugin.slide_type: plugin for plugin in (TitleSlideType(), FinancialTableSlideType())
}
