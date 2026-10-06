"""Slide titles follow the template's casing rule and trailing-period convention."""

from __future__ import annotations

from deckforge.qc.context import QCContext
from deckforge.qc.models import Issue, Severity, SpecFix
from deckforge.template.models import CaseRule
from deckforge.template.text_rules import classify_title, to_sentence_case, to_title_case

NAME = "casing"
MIN_CONFIDENCE = 0.6  # only enforce a rule the reference deck follows consistently


def check(ctx: QCContext) -> list[Issue]:
    rules = ctx.style.text_rules
    issues: list[Issue] = []
    for n, spec in enumerate(ctx.spec.slides, start=1):
        title = spec.title
        fixed = title
        if rules.title_case_confidence >= MIN_CONFIDENCE:
            got = classify_title(title)
            if rules.title_case is CaseRule.TITLE and got in (CaseRule.SENTENCE, CaseRule.MIXED):
                fixed = to_title_case(fixed)
            elif rules.title_case is CaseRule.SENTENCE and got in (CaseRule.TITLE, CaseRule.MIXED):
                fixed = to_sentence_case(fixed)
        if not rules.title_trailing_period and fixed.endswith("."):
            fixed = fixed.rstrip(".")
        if fixed != title:
            issues.append(
                Issue(
                    checker=NAME,
                    severity=Severity.WARNING,
                    slide=n,
                    message=f"title '{title}' breaks the template's {rules.title_case.value} rule",
                    fix=SpecFix(kind="set_title", slide=n, value=fixed),
                )
            )
    return issues
