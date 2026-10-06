"""Fonts, sizes, and colors set on the slides must come from style.json.

Only explicit run formatting is checked: anything inherited comes from the template's
own masters and layouts and is template style by definition.
"""

from __future__ import annotations

from deckforge.qc.checkers.common import paragraphs
from deckforge.qc.context import QCContext
from deckforge.qc.models import Issue, Severity
from deckforge.template.ooxml import first, xpath

NAME = "fonts"


def check(ctx: QCContext) -> list[Issue]:
    style = ctx.style
    fonts = set(style.allowed_fonts) | {style.theme_fonts.major, style.theme_fonts.minor}
    sizes = set(style.allowed_font_sizes_pt) | {
        lvl.size_pt for lvl in style.master_text_styles.title + style.master_text_styles.body
    }
    palette = style.palette
    colors = {c.hex for c in palette.text + palette.fill + palette.line}
    colors |= set(style.theme_colors.values())

    issues: list[Issue] = []
    seen: set[tuple[int, str]] = set()

    def report(n: int, msg: str) -> None:
        if (n, msg) not in seen:
            seen.add((n, msg))
            issues.append(Issue(checker=NAME, severity=Severity.ERROR, slide=n, message=msg))

    for n, slide in ctx.slides():
        for shape in ctx.shapes(slide):
            for p in paragraphs(shape):
                for r_pr in xpath(p, "a:r/a:rPr"):
                    latin = first(r_pr, "a:latin")
                    face = latin.get("typeface") if latin is not None else None
                    if face and not face.startswith("+") and face not in fonts:
                        report(n, f"font '{face}' is not in the template ({sorted(fonts)})")
                    if (sz := r_pr.get("sz")) and int(sz) / 100 not in sizes:
                        report(
                            n,
                            f"font size {int(sz) / 100:g}pt is not a template size "
                            f"({sorted(sizes)})",
                        )
                    color = first(r_pr, "a:solidFill/a:srgbClr")
                    if color is not None and color.get("val", "").upper() not in colors:
                        report(n, f"text color #{color.get('val')} is not in the palette")
    return issues
