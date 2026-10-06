"""Runs every deterministic checker against a built deck."""

from __future__ import annotations

import logging

from deckforge.qc.checkers import CHECKERS
from deckforge.qc.context import QCContext
from deckforge.qc.models import Issue, Severity

log = logging.getLogger(__name__)


def run_checks(ctx: QCContext, skip: frozenset[str] = frozenset()) -> list[Issue]:
    issues: list[Issue] = []
    for name, check in CHECKERS.items():
        if name in skip:
            continue
        found = check(ctx)
        log.debug("checker ran", extra={"checker": name, "issues": len(found)})
        issues += found
    errors = sum(i.severity is Severity.ERROR for i in issues)
    log.info("qc complete", extra={"issues": len(issues), "errors": errors})
    return issues
