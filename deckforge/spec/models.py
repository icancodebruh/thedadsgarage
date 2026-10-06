"""Schema for `deck_spec.json`: the brief plus one validated entry per slide."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SPEC_VERSION = "0.1"
MAX_TABLE_COLUMNS = 10
MAX_TABLE_ROWS = 25


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FormatKind(StrEnum):
    CURRENCY = "currency"
    PER_SHARE = "per_share"
    PERCENT = "percent"
    MULTIPLE = "multiple"
    NUMBER = "number"


class Scale(StrEnum):
    UNITS = "units"
    THOUSANDS = "thousands"
    MILLIONS = "millions"
    BILLIONS = "billions"


class NumberFormat(_Model):
    kind: FormatKind
    scale: Scale = Scale.MILLIONS
    decimals: int = Field(default=1, ge=0, le=3)


class RowStyle(StrEnum):
    NORMAL = "normal"
    SUBTOTAL = "subtotal"
    TOTAL = "total"
    MEMO = "memo"  # e.g. "% growth" lines under a metric


class TableRow(_Model):
    label: str = Field(min_length=1)
    cells: list[str | None] = Field(description="Fact id per column; null renders a dash")
    format: NumberFormat
    style: RowStyle = RowStyle.NORMAL


class TitleSlide(_Model):
    slide_type: Literal["title"] = "title"
    layout_id: str = "title_slide"
    title: str = Field(min_length=1)
    subtitle: str | None = None
    date: dt.date | None = None


class FinancialTableSlide(_Model):
    slide_type: Literal["financial_table"] = "financial_table"
    layout_id: str = "title_and_content"
    title: str = Field(min_length=1)
    units_label: str | None = Field(
        default=None, description="Defaults to a label derived from the first row's scale"
    )
    columns: list[str] = Field(min_length=1, max_length=MAX_TABLE_COLUMNS)
    rows: list[TableRow] = Field(min_length=1, max_length=MAX_TABLE_ROWS)

    @model_validator(mode="after")
    def _rows_match_columns(self) -> FinancialTableSlide:
        bad = [r.label for r in self.rows if len(r.cells) != len(self.columns)]
        if bad:
            raise ValueError(f"rows with a cell count != {len(self.columns)} columns: {bad}")
        return self

    def fact_refs(self) -> list[str]:
        return [c for r in self.rows for c in r.cells if c is not None]


SlideSpec = Annotated[TitleSlide | FinancialTableSlide, Field(discriminator="slide_type")]


class TemplateRef(_Model):
    """Paths are relative to the spec file."""

    pptx: Path
    style: Path
    layouts: Path


class DeckSpec(_Model):
    schema_version: str = SPEC_VERSION
    brief: str = Field(min_length=1, description="The user brief; re-read at every stage")
    template: TemplateRef
    facts: Path
    slides: list[SlideSpec] = Field(min_length=1)

    @classmethod
    def load(cls, path: Path) -> DeckSpec:
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
