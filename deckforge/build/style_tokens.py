"""Design tokens for slide builders, derived only from `style.json`.

Each token documents the rule that picks it, so a different reference template
produces a different, but still consistent, set of tokens.
"""

from __future__ import annotations

from dataclasses import dataclass

from deckforge.template.models import Box, FontUsage, StyleSpec, TextRole


class StyleError(ValueError):
    """`style.json` lacks something the builders need."""


@dataclass(frozen=True)
class TextToken:
    font: str
    size_pt: float
    color: str
    bold: bool


@dataclass(frozen=True)
class StyleTokens:
    title: TextToken
    body: TextToken
    table: TextToken
    footnote: TextToken
    header_fill: str
    header_text: str
    emphasis_fill: str
    content_box: Box
    slide_width_in: float
    slide_height_in: float


def _luminance(hex_: str) -> float:
    """WCAG relative luminance."""

    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _top(style: StyleSpec, *roles: TextRole) -> FontUsage | None:
    """Most-used font combination for the first role that has any text."""
    for role in roles:
        usages = [f for f in style.fonts if f.role is role]
        if usages:
            return usages[0]  # style.fonts is sorted by character count within role
    return None


def _token(usage: FontUsage | None, fallback_color: str, what: str) -> TextToken:
    if usage is None:
        raise StyleError(f"style.json has no text usage for {what}")
    return TextToken(usage.font, usage.size_pt, usage.color or fallback_color, usage.bold)


def derive_tokens(style: StyleSpec) -> StyleTokens:
    if not style.palette.text or len(style.palette.fill) < 2:
        raise StyleError("style.json palette needs >=1 text color and >=2 fill colors")
    text_color = style.palette.text[0].hex  # most-used text color
    body = _token(_top(style, TextRole.BODY, TextRole.OTHER), text_color, "body")
    table = _token(
        _top(style, TextRole.TABLE_BODY, TextRole.BODY, TextRole.OTHER), text_color, "table"
    )
    # Header fill: most-used fill. Emphasis fill (totals): next most-used fill.
    header_fill = style.palette.fill[0].hex
    emphasis_fill = style.palette.fill[1].hex
    # Header text: the palette text color with the best contrast on the header fill.
    header_text = max((c.hex for c in style.palette.text), key=lambda h: contrast(h, header_fill))
    return StyleTokens(
        title=_token(_top(style, TextRole.TITLE), text_color, "titles"),
        body=body,
        table=table,
        # Footnotes: the smallest allowed size, in the body font and color.
        footnote=TextToken(body.font, min(style.allowed_font_sizes_pt), body.color, False),
        header_fill=header_fill,
        header_text=header_text,
        emphasis_fill=emphasis_fill,
        content_box=style.grid.content_box,
        slide_width_in=style.slide_size.width_in,
        slide_height_in=style.slide_size.height_in,
    )
