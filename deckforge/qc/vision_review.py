"""Claude reviews rendered slide images against the brief, spec, and template style."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from deckforge.llm import StructuredLLM
from deckforge.qc.models import Issue, Severity, SpecFix
from deckforge.spec.models import DeckSpec
from deckforge.template.models import StyleSpec

NAME = "vision"
SYSTEM = """\
You are the final reviewer of an investment-banking presentation before it goes to a \
client. You see each rendered slide image, the slide's spec, the deck brief, and the \
template style. Report only concrete, visible defects:
- text overflowing or clipped, overlapping elements, cramped or uneven spacing
- elements misaligned with the template grid, or styling that departs from the template
- a slide that does not match its intended layout or slide type
- content that drifts from the brief or the slide's stated message
- illegible charts/tables (labels colliding, unreadable sizes)
Do not comment on numbers' correctness (checked elsewhere) or on matters of taste. \
Use severity "error" only for defects a client would notice; otherwise "warning". \
Return an empty list when a slide is clean."""


class VisionFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slide: int
    severity: Literal["error", "warning"]
    category: Literal[
        "overflow", "overlap", "alignment", "style", "layout", "brief_drift", "legibility"
    ]
    message: str
    suggested_fix: str


class VisionReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[VisionFinding]


def style_summary(style: StyleSpec) -> str:
    return json.dumps(
        {
            "slide_size_in": [style.slide_size.width_in, style.slide_size.height_in],
            "fonts": style.allowed_fonts,
            "font_sizes_pt": style.allowed_font_sizes_pt,
            "palette": {
                "text": [c.hex for c in style.palette.text[:6]],
                "fill": [c.hex for c in style.palette.fill[:6]],
            },
            "margins_in": style.grid.margins.model_dump(),
            "title_rule": style.text_rules.title_case.value,
        }
    )


def review(pngs: list[Path], spec: DeckSpec, style: StyleSpec, llm: StructuredLLM) -> list[Issue]:
    content: list[dict[str, Any]] = [
        {"type": "text", "text": f"<brief>\n{spec.brief}\n</brief>"},
        {"type": "text", "text": f"<template_style>\n{style_summary(style)}\n</template_style>"},
    ]
    for n, (png, slide) in enumerate(zip(pngs, spec.slides, strict=False), start=1):
        content.append(
            {"type": "text", "text": f"<slide number={n}>\n{slide.model_dump_json()}\n</slide>"}
        )
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.standard_b64encode(png.read_bytes()).decode("ascii"),
                },
            }
        )
    result = llm.structured(system=SYSTEM, content=content, schema=VisionReview)
    issues = []
    for f in result.findings:
        revisable = 1 <= f.slide <= len(spec.slides) and spec.slides[f.slide - 1].slide_type in (
            "exec_summary",
            "company_overview",
        )
        issues.append(
            Issue(
                checker=NAME,
                severity=Severity(f.severity),
                slide=f.slide,
                message=f"[{f.category}] {f.message} (suggested: {f.suggested_fix})",
                fix=SpecFix(kind="revise_slide", slide=f.slide) if revisable else None,
            )
        )
    return issues
