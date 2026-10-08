"""Same metric + period = same value everywhere; same fact shown at the same precision."""

from __future__ import annotations

from collections import defaultdict

from deckforge.qc.context import QCContext
from deckforge.qc.models import Issue, Severity

NAME = "consistency"


def check(ctx: QCContext) -> list[Issue]:
    issues: list[Issue] = []
    used = set(ctx.spec.fact_refs())
    by_key: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    ids_by_key: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for fact in ctx.facts.facts:
        if fact.id in used:
            key = (fact.entity.lower(), fact.metric.lower(), fact.period.lower())
            by_key[key].add(str(fact.value.normalize()))
            ids_by_key[key].append(fact.id)
    for key, values in sorted(by_key.items()):
        if len(values) > 1:
            issues.append(
                Issue(
                    checker=NAME,
                    severity=Severity.ERROR,
                    slide=None,
                    message=f"{key[0]} {key[1]} {key[2]} has conflicting values "
                    f"{sorted(values)} in facts {ids_by_key[key]}",
                )
            )

    # Deck-wide precision: one decimals setting per (format kind, scale).
    decimals: dict[str, set[str]] = defaultdict(set)
    for b in ctx.manifest.bindings:
        kind, scale, dp = b.format_key.split("/")
        group = f"{kind}/{scale}" if kind in ("currency", "number") else kind
        decimals[group].add(dp)
    for group, dps in sorted(decimals.items()):
        if len(dps) > 1:
            issues.append(
                Issue(
                    checker=NAME,
                    severity=Severity.WARNING,
                    slide=None,
                    message=f"{group} numbers use different decimal places {sorted(dps)}",
                )
            )
    return issues
