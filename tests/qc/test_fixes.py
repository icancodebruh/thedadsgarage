from __future__ import annotations

from pathlib import Path

from deckforge.ingest.models import FactSet
from deckforge.qc.fixes import apply_fixes, split_table
from deckforge.qc.models import Issue, Severity, SpecFix
from deckforge.spec.models import DeckSpec, FinancialTableSlide
from deckforge.template.models import LayoutLibrary


def _load(inputs: Path) -> tuple[DeckSpec, FactSet, LayoutLibrary]:
    return (
        DeckSpec.load(inputs / "deck_spec.json"),
        FactSet.load(inputs / "facts.json"),
        LayoutLibrary.model_validate_json((inputs / "layouts.json").read_text()),
    )


def test_fully_tied_table_is_not_split(full_inputs: Path) -> None:
    spec, _, _ = _load(full_inputs)
    table = spec.slides[3]
    assert isinstance(table, FinancialTableSlide)
    assert split_table(table) == [table]


def test_split_into_chunks_keeps_tie_groups(full_inputs: Path) -> None:
    spec, _, _ = _load(full_inputs)
    table = spec.slides[3]
    assert isinstance(table, FinancialTableSlide)
    plain = [
        table.rows[0].model_copy(update={"label": f"Line {c}", "sum_of": None, "ratio_of": None})
        for c in "ABCDE"
    ]
    big = table.model_copy(update={"rows": plain + list(table.rows)})  # 5 plain + 4 tied
    parts = split_table(big, max_rows=4)
    assert [len(p.rows) for p in parts] == [4, 1, 4]
    assert [p.title.endswith("(cont'd)") for p in parts] == [False, True, True]
    assert [r for p in parts for r in p.rows] == big.rows


def test_apply_title_and_split(full_inputs: Path) -> None:
    spec, facts, library = _load(full_inputs)
    issues = [
        Issue(
            checker="casing",
            severity=Severity.WARNING,
            slide=2,
            message="m",
            fix=SpecFix(kind="set_title", slide=2, value="New Title"),
        ),
        Issue(
            checker="overflow",
            severity=Severity.ERROR,
            slide=4,
            message="m",
            fix=SpecFix(kind="split_table", slide=4),
        ),
    ]
    fixed, applied = apply_fixes(spec, issues, facts=facts, library=library, llm=None)
    assert fixed.slides[1].title == "New Title"
    assert len(fixed.slides) == len(spec.slides)  # fully tied table stays whole
    assert len(applied) == 1


def test_revise_without_llm_is_a_no_op(full_inputs: Path) -> None:
    spec, facts, library = _load(full_inputs)
    issue = Issue(
        checker="vision",
        severity=Severity.ERROR,
        slide=2,
        message="m",
        fix=SpecFix(kind="revise_slide", slide=2),
    )
    fixed, applied = apply_fixes(spec, [issue], facts=facts, library=library, llm=None)
    assert fixed == spec and applied == []
