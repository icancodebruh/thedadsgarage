"""Slide-type plugin interface and shared drawing helpers."""

from __future__ import annotations

import copy
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol, cast

from pptx.dml.color import RGBColor
from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.shapes.autoshape import Shape
from pptx.shapes.base import BaseShape
from pptx.slide import Slide, SlideLayout
from pptx.text.text import TextFrame, _Run
from pptx.util import Emu, Inches, Pt

from deckforge.build.style_tokens import StyleTokens, TextToken
from deckforge.ingest.models import FactSet
from deckforge.template.models import Box
from deckforge.template.ooxml import first, xpath


class LayoutOverflowError(ValueError):
    """Content does not fit the space the template allows."""


@dataclass(frozen=True)
class BuildContext:
    tokens: StyleTokens
    facts: FactSet


class SlideType(Protocol):
    """A plugin that renders one spec entry onto a slide created from its layout."""

    slide_type: str

    def render(self, slide: Slide, spec: Any, ctx: BuildContext) -> None: ...


def placeholders(slide: Slide | SlideLayout) -> list[BaseShape]:
    # python-pptx annotates placeholder iteration incorrectly; cast through Iterable.
    return list(cast("Iterable[BaseShape]", slide.placeholders))


def find_placeholder(slide: Slide, *types: PP_PLACEHOLDER) -> Shape | None:
    for ph in placeholders(slide):
        if ph.placeholder_format.type in types and isinstance(ph, Shape):
            return ph
    return None


def add_slide_number(slide: Slide) -> bool:
    """Copy the layout's slide-number placeholder (with its field) onto the slide.

    python-pptx's `add_slide` skips date/footer/slide-number placeholders.
    Returns False when the layout has none.
    """
    layout_ph = next(
        (
            ph
            for ph in placeholders(slide.slide_layout)
            if ph.placeholder_format.type == PP_PLACEHOLDER.SLIDE_NUMBER
        ),
        None,
    )
    if layout_ph is None:
        return False
    sp = copy.deepcopy(layout_ph.element)
    tree = first(slide.element, "p:cSld/p:spTree")
    ids = [int(el.get("id")) for el in xpath(tree, ".//p:cNvPr")]
    c_nv_pr = first(sp, "p:nvSpPr/p:cNvPr")
    assert tree is not None and c_nv_pr is not None
    c_nv_pr.set("id", str(max(ids, default=1) + 1))
    tree.append(sp)
    return True


def remove_shape(shape: BaseShape) -> None:
    el = shape.element
    el.getparent().remove(el)


def remove_empty_placeholders(slide: Slide) -> None:
    """Delete placeholders left without text so no prompt text renders."""
    for ph in placeholders(slide):
        if not (isinstance(ph, Shape) and ph.text_frame.text.strip()):
            remove_shape(ph)


def style_run(
    run: _Run, token: TextToken, *, bold: bool | None = None, color: str | None = None
) -> None:
    run.font.name = token.font
    run.font.size = Pt(token.size_pt)
    run.font.bold = token.bold if bold is None else bold
    run.font.color.rgb = RGBColor.from_string(color or token.color)  # type: ignore[no-untyped-call]


def set_paragraphs(frame: TextFrame, lines: list[str]) -> None:
    """Replace text keeping inherited (placeholder) formatting: one paragraph per line."""
    frame.text = lines[0]
    for line in lines[1:]:
        frame.add_paragraph().text = line  # type: ignore[no-untyped-call]


def add_text(
    slide: Slide, box: Box, text: str, token: TextToken, align: PP_ALIGN = PP_ALIGN.LEFT
) -> Shape:
    shape = slide.shapes.add_textbox(Inches(box.x), Inches(box.y), Inches(box.w), Inches(box.h))
    frame = shape.text_frame
    frame.word_wrap = True
    frame.vertical_anchor = MSO_ANCHOR.TOP
    for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(frame, side, Emu(0))
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text
    style_run(run, token)
    return shape
