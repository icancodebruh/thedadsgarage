from __future__ import annotations

import pytest

from deckforge.template.models import CaseRule
from deckforge.template.text_rules import classify_title, infer_text_rules


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Summary of Jaguar Valuation", CaseRule.TITLE),
        ("Revenue Projections: Management vs. Consensus", CaseRule.TITLE),
        ("Summary of the valuation work", CaseRule.SENTENCE),
        ("EXECUTIVE SUMMARY", CaseRule.UPPER),
        ("Overview", None),
        ("Key drivers Of Growth Margin", CaseRule.MIXED),
    ],
)
def test_classify_title(title: str, expected: CaseRule | None) -> None:
    assert classify_title(title) == expected


def test_infer_text_rules_majority_and_period() -> None:
    rules = infer_text_rules(["Market Overview Today", "Deal Terms Summary", "Next steps here"])
    assert rules.title_case is CaseRule.TITLE
    assert rules.title_case_confidence == pytest.approx(0.667, abs=1e-3)
    assert rules.title_trailing_period is False


def test_infer_text_rules_empty() -> None:
    rules = infer_text_rules([])
    assert rules.title_case is CaseRule.MIXED
    assert rules.title_case_confidence == 0.0
