from __future__ import annotations

import json
from pathlib import Path

from deckforge.pipeline import make
from deckforge.qc.models import Severity


def test_make_clean_deck(full_inputs: Path) -> None:
    out = full_inputs / "run"
    result = make(full_inputs / "deck_spec.json", out, llm=None, skip=frozenset({"spelling"}))
    assert result.report.clean, result.report.to_markdown()
    assert len(result.report.passes) == 1
    assert (out / "deck.pptx").exists() and (out / "qc_report.md").exists()


def test_fix_loop_retitles_and_rebuilds(full_inputs: Path) -> None:
    spec_path = full_inputs / "deck_spec.json"
    spec = json.loads(spec_path.read_text())
    spec["slides"][3]["title"] = "testco financial summary for the year."
    spec_path.write_text(json.dumps(spec))
    result = make(spec_path, full_inputs / "run", llm=None, skip=frozenset({"spelling"}))
    assert len(result.report.passes) == 2
    assert any("title" in f for f in result.report.passes[0].fixes_applied)
    assert result.report.clean
    fixed = json.loads(result.spec.read_text())
    assert fixed["slides"][3]["title"] == "Testco Financial Summary for the Year"
    assert all(i.severity is not Severity.ERROR for i in result.report.final.issues)


def test_overflow_at_build_splits_table(full_inputs: Path) -> None:
    spec_path = full_inputs / "deck_spec.json"
    spec = json.loads(spec_path.read_text())
    table = spec["slides"][3]
    plain = [dict(r, style="normal", sum_of=None, ratio_of=None) for r in table["rows"]]
    table["rows"] = (plain * 7)[:25]
    for i, row in enumerate(table["rows"]):
        row["label"] = f"Line {chr(65 + i)}"
    spec_path.write_text(json.dumps(spec))
    result = make(spec_path, full_inputs / "run", llm=None, skip=frozenset({"spelling"}))
    assert result.report.passes[0].issues[0].checker == "build"
    assert "split table" in result.report.passes[0].fixes_applied[0]
    assert result.report.passes[1].deck is not None
    assert result.report.clean, result.report.to_markdown()
