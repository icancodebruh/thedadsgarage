from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.presentation import Presentation as PresentationT

from deckforge.build.renderer import load_manifest
from deckforge.qc.context import QCContext
from deckforge.spec.models import DeckSpec
from tests.conftest import build_full

MakeCtx = Callable[..., QCContext]


@pytest.fixture
def make_ctx(full_inputs: Path) -> MakeCtx:
    """Build the full deck, optionally mutate the .pptx or spec, and load a QC context."""

    def make(
        mutate: Callable[[PresentationT], None] | None = None,
        spec_edit: Callable[[DeckSpec], DeckSpec] | None = None,
    ) -> QCContext:
        deck = build_full(full_inputs)
        manifest = load_manifest(deck)
        if mutate:
            prs = Presentation(str(deck))
            mutate(prs)
            prs.save(str(deck))
        spec = DeckSpec.load(full_inputs / "deck_spec.json")
        if spec_edit:
            spec = spec_edit(spec)
        return QCContext.load(deck, spec, full_inputs, manifest)

    return make
