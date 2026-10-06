from __future__ import annotations

from pathlib import Path

from deckforge.qc import vision_review
from deckforge.qc.models import Severity
from deckforge.spec.models import DeckSpec
from deckforge.template.models import StyleSpec
from tests.conftest import FakeLLM


def test_findings_become_issues_with_fixes(full_inputs: Path, tmp_path: Path) -> None:
    spec = DeckSpec.load(full_inputs / "deck_spec.json")
    style = StyleSpec.model_validate_json((full_inputs / "style.json").read_text())
    pngs = []
    for n in range(1, 3):
        png = tmp_path / f"slide-{n}.png"
        png.write_bytes(b"\x89PNG fake")
        pngs.append(png)
    llm = FakeLLM(
        {
            "findings": [
                {
                    "slide": 2,
                    "severity": "error",
                    "category": "overflow",
                    "message": "bullet clipped",
                    "suggested_fix": "shorten",
                },
                {
                    "slide": 1,
                    "severity": "warning",
                    "category": "style",
                    "message": "x",
                    "suggested_fix": "y",
                },
            ]
        }
    )
    issues = vision_review.review(pngs, spec, style, llm)
    assert issues[0].severity is Severity.ERROR and issues[0].fix is not None
    assert issues[0].fix.kind == "revise_slide"
    assert issues[1].fix is None  # title slides are not revised by Claude
    content = llm.calls[0]["content"]
    assert sum(1 for c in content if c["type"] == "image") == 2
    assert spec.brief in content[0]["text"]
