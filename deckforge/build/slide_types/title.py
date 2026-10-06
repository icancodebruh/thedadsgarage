"""Title slide: deck title, subtitle, and date in the layout's own placeholders."""

from __future__ import annotations

from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.slide import Slide

from deckforge.build.slide_types.base import (
    BuildContext,
    find_placeholder,
    remove_empty_placeholders,
    set_paragraphs,
)
from deckforge.spec.models import TitleSlide


class LayoutMismatchError(ValueError):
    """The chosen layout lacks a placeholder this slide type needs."""


class TitleSlideType:
    slide_type = "title"

    def render(self, slide: Slide, spec: TitleSlide, ctx: BuildContext) -> None:
        title = find_placeholder(slide, PP_PLACEHOLDER.CENTER_TITLE, PP_PLACEHOLDER.TITLE)
        if title is None:
            raise LayoutMismatchError(f"layout '{spec.layout_id}' has no title placeholder")
        title.text_frame.text = spec.title

        lines = [s for s in (spec.subtitle, _format_date(spec)) if s]
        if lines:
            sub = find_placeholder(slide, PP_PLACEHOLDER.SUBTITLE, PP_PLACEHOLDER.BODY)
            if sub is None:
                raise LayoutMismatchError(f"layout '{spec.layout_id}' has no subtitle placeholder")
            set_paragraphs(sub.text_frame, lines)
        remove_empty_placeholders(slide)


def _format_date(spec: TitleSlide) -> str | None:
    return f"{spec.date:%B} {spec.date.day}, {spec.date.year}" if spec.date else None
