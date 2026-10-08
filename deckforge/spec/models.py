"""Schema for `deck_spec.json`: the brief plus one validated entry per slide."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from deckforge.spec.tokens import token_refs

SPEC_VERSION = "0.1"
MAX_TABLE_COLUMNS = 10
MAX_TABLE_ROWS = 25
# Non-numeric markers allowed in place of a fact id in table cells.
LITERAL_CELLS = frozenset({"NM", "n.a."})


def cell_refs(cells: list[str | None]) -> list[str]:
    """Fact ids among table cells (skips blanks and literal markers such as NM)."""
    return [c for c in cells if c is not None and c not in LITERAL_CELLS]


def _tokens(*texts: str | None) -> list[str]:
    return [r for t in texts if t for r in token_refs(t)]


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
    symbol: bool = Field(
        default=False, description="Show the currency symbol in table cells (mixed currencies)"
    )


class RowStyle(StrEnum):
    NORMAL = "normal"
    SUBTOTAL = "subtotal"
    TOTAL = "total"
    MEMO = "memo"  # e.g. "% growth" lines under a metric
    HIGHLIGHT = "highlight"  # e.g. the target company in a comps table


# --- slide types ------------------------------------------------------------------------


class TitleSlide(_Model):
    slide_type: Literal["title"] = "title"
    layout_id: str = "title_slide"
    title: str = Field(min_length=1)
    subtitle: str | None = None
    date: dt.date | None = None

    def fact_refs(self) -> list[str]:
        return []


class ExecSummarySlide(_Model):
    slide_type: Literal["exec_summary"] = "exec_summary"
    layout_id: str = "title_and_content"
    title: str = Field(min_length=1)
    bullets: list[str] = Field(
        min_length=1,
        max_length=8,
        description="One message per bullet; numbers only as {{fact.id|kind[:scale][:dp]}}",
    )

    def fact_refs(self) -> list[str]:
        return [r for b in self.bullets for r in token_refs(b)]


class KeyStat(_Model):
    """A key-facts row: either a fact with a format, or text (numbers only as tokens)."""

    label: str = Field(min_length=1)
    fact: str | None = None
    format: NumberFormat | None = None
    text: str | None = None

    @model_validator(mode="after")
    def _one_value(self) -> KeyStat:
        if (self.text is None) == (self.fact is None):
            raise ValueError(f"key stat '{self.label}': give either fact+format or text")
        if self.fact is not None and self.format is None:
            raise ValueError(f"key stat '{self.label}': fact needs a format")
        return self

    def fact_refs(self) -> list[str]:
        return [self.fact] if self.fact else _tokens(self.text)


class CompanyOverviewSlide(_Model):
    slide_type: Literal["company_overview"] = "company_overview"
    layout_id: str = "title_and_content"
    title: str = Field(min_length=1)
    description: str = Field(min_length=1, max_length=1200)
    highlights: list[str] = Field(default_factory=list, max_length=6)
    key_stats: list[KeyStat] = Field(min_length=1, max_length=10)
    left_heading: str = "Business Overview"
    right_heading: str = "Key Statistics"

    def fact_refs(self) -> list[str]:
        refs = _tokens(self.description, *self.highlights)
        return refs + [r for s in self.key_stats for r in s.fact_refs()]


class TableRow(_Model):
    label: str = Field(min_length=1)
    cells: list[str | None] = Field(description="Fact id per column; null renders a dash")
    format: NumberFormat
    style: RowStyle = RowStyle.NORMAL
    sum_of: list[str] | None = Field(
        default=None, description="Labels of rows that must add up to this row (QC tie-out)"
    )
    ratio_of: list[str] | None = Field(
        default=None,
        min_length=2,
        max_length=2,
        description="[numerator label, denominator label] this row must equal (QC tie-out)",
    )


FOOTNOTE_FIELD = Field(
    default=None, max_length=600, description="Methodology note; numbers only as fact tokens"
)


class FinancialTableSlide(_Model):
    slide_type: Literal["financial_table"] = "financial_table"
    layout_id: str = "title_and_content"
    title: str = Field(min_length=1)
    units_label: str | None = Field(
        default=None, description="Defaults to a label derived from the first currency row"
    )
    footnote: str | None = FOOTNOTE_FIELD
    columns: list[str] = Field(min_length=1, max_length=MAX_TABLE_COLUMNS)
    rows: list[TableRow] = Field(min_length=1, max_length=MAX_TABLE_ROWS)

    @model_validator(mode="after")
    def _rows_match_columns(self) -> FinancialTableSlide:
        bad = [r.label for r in self.rows if len(r.cells) != len(self.columns)]
        if bad:
            raise ValueError(f"rows with a cell count != {len(self.columns)} columns: {bad}")
        labels = {r.label for r in self.rows}
        for r in self.rows:
            missing = [x for x in (r.sum_of or []) + (r.ratio_of or []) if x not in labels]
            if missing:
                raise ValueError(f"row '{r.label}' ties to unknown rows {missing}")
        return self

    def fact_refs(self) -> list[str]:
        return [c for r in self.rows for c in cell_refs(r.cells)] + _tokens(self.footnote)


class CompsColumn(_Model):
    header: str = Field(min_length=1)
    format: NumberFormat
    stats: bool = Field(default=True, description="Show summary statistics for this column")


class CompsRow(_Model):
    company: str = Field(min_length=1)
    cells: list[str | None]
    is_target: bool = False
    in_stats: bool = Field(default=True, description="Include in the peer statistics")


Statistic = Literal["median", "mean", "high", "low"]
DEFAULT_STATS: tuple[Statistic, ...] = ("median", "mean")


class TradingCompsSlide(_Model):
    slide_type: Literal["trading_comps"] = "trading_comps"
    layout_id: str = "title_and_content"
    title: str = Field(min_length=1)
    subtitle: str | None = Field(default=None, description="Peer-set definition")
    units_label: str | None = None
    columns: list[CompsColumn] = Field(min_length=1, max_length=8)
    rows: list[CompsRow] = Field(min_length=2, max_length=15)
    statistics: list[Statistic] = Field(default_factory=lambda: list(DEFAULT_STATS))
    stats_label: str | None = Field(
        default=None, description="Peer-set name for statistic rows, e.g. 'Indian peer'"
    )
    footnote: str | None = FOOTNOTE_FIELD

    @model_validator(mode="after")
    def _shape(self) -> TradingCompsSlide:
        bad = [r.company for r in self.rows if len(r.cells) != len(self.columns)]
        if bad:
            raise ValueError(f"rows with a cell count != {len(self.columns)} columns: {bad}")
        if sum(r.is_target for r in self.rows) > 1:
            raise ValueError("at most one target row")
        return self

    def fact_refs(self) -> list[str]:
        return [c for r in self.rows for c in cell_refs(r.cells)] + _tokens(
            self.subtitle, self.footnote
        )


class ReferenceMark(_Model):
    label: str = Field(min_length=1)
    fact: str


class FootballFieldBar(_Model):
    label: str = Field(min_length=1, description="Methodology; numbers only as fact tokens")
    low: str = Field(description="Fact id of the range low")
    high: str = Field(description="Fact id of the range high")


class FootballFieldSlide(_Model):
    slide_type: Literal["football_field"] = "football_field"
    layout_id: str = "title_and_content"
    title: str = Field(min_length=1)
    units_label: str | None = None
    bars: list[FootballFieldBar] = Field(min_length=1, max_length=10)
    format: NumberFormat = NumberFormat(kind=FormatKind.PER_SHARE, decimals=2)
    reference: str | None = Field(default=None, description="Fact id, e.g. current share price")
    reference_label: str = "Current share price"
    more_references: list[ReferenceMark] = Field(default_factory=list, max_length=3)
    footnote: str | None = FOOTNOTE_FIELD

    def fact_refs(self) -> list[str]:
        refs = [r for b in self.bars for r in (b.low, b.high, *token_refs(b.label))]
        refs += [self.reference] if self.reference else []
        return refs + [m.fact for m in self.more_references] + _tokens(self.footnote)


SlideSpec = Annotated[
    TitleSlide
    | ExecSummarySlide
    | CompanyOverviewSlide
    | FinancialTableSlide
    | TradingCompsSlide
    | FootballFieldSlide,
    Field(discriminator="slide_type"),
]
DATA_SLIDE_TYPES = frozenset(
    {"exec_summary", "company_overview", "financial_table", "trading_comps", "football_field"}
)


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
    glossary: list[str] = Field(
        default_factory=list,
        description="Names and terms that are not data or misspellings (product models, "
        "tickers, brand names); exempt from the untraced-number and spelling checks",
    )
    language: str = Field(default="en-US", description="Spell-check language, e.g. en-GB")

    def fact_refs(self) -> list[str]:
        return [r for s in self.slides for r in s.fact_refs()]

    @classmethod
    def load(cls, path: Path) -> DeckSpec:
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def dump(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
