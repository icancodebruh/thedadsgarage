from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from deckforge.build.renderer import build_deck
from deckforge.qc.render import render_slides
from deckforge.spec.models import DeckSpec


@pytest.mark.skipif(
    shutil.which("soffice") is None or shutil.which("pdftoppm") is None,
    reason="LibreOffice/Poppler not installed",
)
def test_renders_one_png_per_slide(deck_inputs: Path, tmp_path: Path) -> None:
    deck = build_deck(
        DeckSpec.load(deck_inputs / "deck_spec.json"), deck_inputs, tmp_path / "deck.pptx"
    )
    pngs = render_slides(deck, tmp_path / "png")
    assert [p.name for p in pngs] == ["slide-1.png", "slide-2.png"]
