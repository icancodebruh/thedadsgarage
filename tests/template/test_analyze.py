from __future__ import annotations

from pathlib import Path

from deckforge.cli import main
from deckforge.template.analyze import analyze_template, write_outputs
from deckforge.template.models import CaseRule, ContentKind, LayoutLibrary, StyleSpec, TextRole


def test_style_spec(reference_deck: Path) -> None:
    style, _ = analyze_template(reference_deck)
    assert style.source.slide_count == 4
    assert style.slide_size.aspect == "4:3"
    assert "Arial" in style.allowed_fonts
    assert 12.0 in style.allowed_font_sizes_pt
    assert style.palette.fill[0].hex == "113D63"
    assert "CCD1D7" in {c.hex for c in style.palette.fill}
    assert "FFFFFF" in {c.hex for c in style.palette.text}
    assert style.text_rules.title_case is CaseRule.TITLE
    assert style.grid.title_box is not None
    assert {f.role for f in style.fonts} >= {TextRole.TITLE, TextRole.TABLE_HEADER}
    assert len(style.master_text_styles.body) == 5


def test_layout_library(reference_deck: Path) -> None:
    _, library = analyze_template(reference_deck)
    ids = [layout.layout_id for layout in library.layouts]
    assert len(ids) == len(set(ids))
    title_only = next(lay for lay in library.layouts if lay.layout_id == "title_only")
    assert title_only.used_by_slides == [2, 3, 4]
    kinds = {s.slide_number: s.content_kind for s in library.slides}
    assert kinds[1] is ContentKind.TITLE
    assert kinds[4] is ContentKind.PICTURE
    assert any("picture" in w for w in library.slides[3].warnings)
    assert any("[4]" in w for w in library.warnings)


def test_outputs_are_deterministic_and_valid(reference_deck: Path, tmp_path: Path) -> None:
    first = write_outputs(*analyze_template(reference_deck), tmp_path / "a")
    second = write_outputs(*analyze_template(reference_deck), tmp_path / "b")
    for a, b in zip(first, second, strict=True):
        assert a.read_bytes() == b.read_bytes()
    StyleSpec.model_validate_json(first[0].read_text())
    LayoutLibrary.model_validate_json(first[1].read_text())


def test_cli_writes_outputs(reference_deck: Path, tmp_path: Path) -> None:
    assert main(["template", "analyze", str(reference_deck), "--out", str(tmp_path)]) == 0
    assert (tmp_path / "style.json").exists()
    assert (tmp_path / "layouts.json").exists()
