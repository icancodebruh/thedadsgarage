"""Records every number the builder renders, with the facts and sources behind it."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class Binding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    slide: int
    text: str = Field(description="The rendered string, e.g. '(12.3)' or '$3.1B'")
    fact_ids: list[str]
    source_refs: list[str]
    derived: str | None = Field(default=None, description="How a computed value was derived")
    format_key: str = Field(description="kind/scale/decimals used, for consistency checks")


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bindings: list[Binding] = Field(default_factory=list)

    def for_slide(self, slide: int) -> list[Binding]:
        return [b for b in self.bindings if b.slide == slide]

    def dump(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Manifest:
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
