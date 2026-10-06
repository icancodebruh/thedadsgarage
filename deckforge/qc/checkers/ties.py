"""Table totals and ratios must tie to their components."""

from __future__ import annotations

from decimal import Decimal

from deckforge.build.formatting import round_half_up, scaled
from deckforge.qc.context import QCContext
from deckforge.qc.models import Issue, Severity
from deckforge.spec.models import FinancialTableSlide

NAME = "ties"
RATIO_TOLERANCE = Decimal("0.0005")  # 0.05 percentage points


def check(ctx: QCContext) -> list[Issue]:
    issues: list[Issue] = []
    values = {f.id: f.value for f in ctx.facts.facts}
    for n, spec in enumerate(ctx.spec.slides, start=1):
        if not isinstance(spec, FinancialTableSlide):
            continue
        rows = {r.label: r for r in spec.rows}
        for row in spec.rows:
            for col, column in enumerate(spec.columns):
                total_ref = row.cells[col]
                if total_ref is None:
                    continue
                total = values[total_ref]
                if row.sum_of:
                    refs = [rows[label].cells[col] for label in row.sum_of]
                    if any(r is None for r in refs):
                        continue
                    parts = [values[r] for r in refs if r]
                    unit = Decimal(1).scaleb(-row.format.decimals)
                    raw_gap = abs(scaled(sum(parts, Decimal(0)) - total, row.format))
                    if raw_gap > unit / 2:
                        issues.append(
                            Issue(
                                checker=NAME,
                                severity=Severity.ERROR,
                                slide=n,
                                message=f"'{row.label}' ({column}) does not equal "
                                f"the sum of {row.sum_of}",
                            )
                        )
                        continue
                    shown = sum(
                        (round_half_up(scaled(p, row.format), row.format.decimals) for p in parts),
                        Decimal(0),
                    )
                    if shown != round_half_up(scaled(total, row.format), row.format.decimals):
                        issues.append(
                            Issue(
                                checker=NAME,
                                severity=Severity.WARNING,
                                slide=n,
                                message=f"'{row.label}' ({column}) does not foot "
                                "on the displayed (rounded) figures",
                            )
                        )
                if row.ratio_of:
                    num_ref, den_ref = (rows[label].cells[col] for label in row.ratio_of)
                    if num_ref is None or den_ref is None or values[den_ref] == 0:
                        continue
                    expected = values[num_ref] / values[den_ref]
                    if abs(expected - total) > RATIO_TOLERANCE:
                        issues.append(
                            Issue(
                                checker=NAME,
                                severity=Severity.ERROR,
                                slide=n,
                                message=f"'{row.label}' ({column}) is {total}, but "
                                f"{row.ratio_of[0]} / {row.ratio_of[1]} "
                                f"= {expected:.4f}",
                            )
                        )
    return issues
