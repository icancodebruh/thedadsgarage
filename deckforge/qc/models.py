"""QC issues, targeted spec fixes, and the report written after the fix loop."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Severity(StrEnum):
    ERROR = "error"  # blocks delivery; the fix loop tries to resolve it
    WARNING = "warning"  # reported; fixed only when a deterministic fix exists
    INFO = "info"  # a check that was skipped or is advisory


FixKind = Literal["set_title", "split_table", "revise_slide"]


class SpecFix(BaseModel):
    """A targeted edit to deck_spec.json (fixes go to the spec, never the .pptx)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: FixKind
    slide: int = Field(description="1-based slide number")
    value: str | None = Field(default=None, description="New title for set_title")
    max_rows: int | None = Field(default=None, description="Rows per slide for split_table")


class Issue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    checker: str
    severity: Severity
    slide: int | None
    message: str
    fix: SpecFix | None = None


class PassRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int
    deck: Path | None
    issues: list[Issue]
    fixes_applied: list[str] = Field(default_factory=list)


class QCReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passes: list[PassRecord] = Field(default_factory=list)

    @property
    def final(self) -> PassRecord:
        return self.passes[-1]

    @property
    def clean(self) -> bool:
        return not any(i.severity is Severity.ERROR for i in self.final.issues)

    def to_markdown(self) -> str:
        lines = ["# DeckForge QC report", ""]
        status = "PASS" if self.clean else "FAIL"
        lines += [f"**Status:** {status} after {len(self.passes)} build(s)", ""]
        for p in self.passes:
            lines.append(f"## Pass {p.number}")
            for fix in p.fixes_applied:
                lines.append(f"- fix applied: {fix}")
            if not p.issues:
                lines.append("- no issues")
            for i in sorted(p.issues, key=lambda i: (i.slide or 0, i.severity, i.checker)):
                where = f"slide {i.slide}" if i.slide else "deck"
                lines.append(f"- **{i.severity.value}** [{i.checker}] {where}: {i.message}")
            lines.append("")
        return "\n".join(lines)
