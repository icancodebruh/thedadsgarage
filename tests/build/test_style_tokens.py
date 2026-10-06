from __future__ import annotations

from pathlib import Path

import pytest

from deckforge.build.style_tokens import StyleError, contrast, derive_tokens
from deckforge.template.analyze import analyze_template
from deckforge.template.models import Palette


def test_tokens_from_reference(reference_deck: Path) -> None:
    style, _ = analyze_template(reference_deck)
    tokens = derive_tokens(style)
    assert tokens.header_fill == "113D63"
    assert tokens.emphasis_fill == style.palette.fill[1].hex
    assert tokens.header_text == "FFFFFF"
    assert tokens.footnote.size_pt == min(style.allowed_font_sizes_pt)
    assert tokens.content_box == style.grid.content_box


def test_contrast() -> None:
    assert contrast("000000", "FFFFFF") == pytest.approx(21.0)
    assert contrast("777777", "777777") == pytest.approx(1.0)


def test_missing_palette_raises(reference_deck: Path) -> None:
    style, _ = analyze_template(reference_deck)
    bare = style.model_copy(update={"palette": Palette(text=[], fill=[], line=[])})
    with pytest.raises(StyleError):
        derive_tokens(bare)
