"""Pydantic schemas for template analysis outputs (`style.json`, `layouts.json`).

All geometry is in inches (rounded to 3 dp) so files are human-readable and diffable.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "0.1"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceInfo(_Model):
    filename: str
    sha256: str
    slide_count: int


class Box(_Model):
    """Bounding box in inches, origin top-left."""

    x: float
    y: float
    w: float
    h: float


Aspect = Literal["16:9", "4:3", "16:10", "other"]


class SlideSize(_Model):
    width_in: float
    height_in: float
    aspect: Aspect


# --- style.json -------------------------------------------------------------------------


class ThemeFonts(_Model):
    major: str
    minor: str


class TextLevelStyle(_Model):
    """Resolved default run style for one outline level of a master text style."""

    level: int
    font: str
    size_pt: float
    color: str | None
    bold: bool
    align: str | None
    bullet: str | None


class MasterTextStyles(_Model):
    title: list[TextLevelStyle]
    body: list[TextLevelStyle]


class TextRole(StrEnum):
    TITLE = "title"
    BODY = "body"
    TABLE_HEADER = "table_header"
    TABLE_BODY = "table_body"
    OTHER = "other"


class FontUsage(_Model):
    """One observed (font, size, bold, color) combination, weighted by character count."""

    role: TextRole
    font: str
    size_pt: float
    bold: bool
    color: str | None
    chars: int
    share: float = Field(description="Share of characters within this role, 0-1")


class ColorUsage(_Model):
    hex: str
    count: int
    share: float
    theme_slot: str | None = Field(default=None, description="Matching theme color slot, if any")


class Palette(_Model):
    text: list[ColorUsage]
    fill: list[ColorUsage]
    line: list[ColorUsage]


class Margins(_Model):
    left: float
    top: float
    right: float
    bottom: float


class Grid(_Model):
    margins: Margins
    title_box: Box | None
    content_box: Box
    x_guides: list[float] = Field(description="Frequent left/right edges (inches)")
    y_guides: list[float] = Field(description="Frequent top/bottom edges (inches)")
    snap_tolerance_in: float


class CaseRule(StrEnum):
    TITLE = "title_case"
    SENTENCE = "sentence_case"
    UPPER = "upper_case"
    MIXED = "mixed"


class TextRules(_Model):
    title_case: CaseRule
    title_case_confidence: float
    title_trailing_period: bool


class StyleSpec(_Model):
    schema_version: str = SCHEMA_VERSION
    source: SourceInfo
    slide_size: SlideSize
    theme_name: str
    theme_colors: dict[str, str]
    theme_fonts: ThemeFonts
    master_text_styles: MasterTextStyles
    fonts: list[FontUsage]
    allowed_fonts: list[str]
    allowed_font_sizes_pt: list[float]
    palette: Palette
    grid: Grid
    text_rules: TextRules


# --- layouts.json -----------------------------------------------------------------------


class PlaceholderSpec(_Model):
    idx: int
    type: str
    name: str
    box: Box | None


class StaticShape(_Model):
    """Decoration baked into a master or layout (logo, footer text, rule)."""

    kind: str
    name: str
    box: Box
    text: str | None


class LayoutSpec(_Model):
    layout_id: str
    name: str
    master_index: int
    layout_index: int
    placeholders: list[PlaceholderSpec]
    static_shapes: list[StaticShape]
    used_by_slides: list[int]


class ContentKind(StrEnum):
    TITLE = "title"
    TEXT = "text"
    TABLE = "table"
    CHART = "chart"
    PICTURE = "picture"
    DIAGRAM = "diagram"
    EMPTY = "empty"


class ShapeKind(StrEnum):
    PLACEHOLDER = "placeholder"
    TEXT = "text"
    AUTOSHAPE = "autoshape"
    PICTURE = "picture"
    TABLE = "table"
    CHART = "chart"
    GROUP = "group"
    FREEFORM = "freeform"
    LINE = "line"
    OTHER = "other"


class SlideShape(_Model):
    kind: ShapeKind
    name: str
    box: Box
    placeholder_type: str | None = None
    has_text: bool


class SlideArchetype(_Model):
    """A reference slide from the deck, reusable as a pattern for generation."""

    slide_number: int
    layout_id: str
    title: str | None
    content_kind: ContentKind
    shape_counts: dict[str, int]
    shapes: list[SlideShape]
    warnings: list[str]


class LayoutLibrary(_Model):
    schema_version: str = SCHEMA_VERSION
    source: SourceInfo
    layouts: list[LayoutSpec]
    slides: list[SlideArchetype]
    warnings: list[str]
