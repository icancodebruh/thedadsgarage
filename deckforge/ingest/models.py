"""Schema for `facts.json`: every number the deck may show, each with its source."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

FACT_ID_PATTERN = r"^[a-z0-9][a-z0-9_.\-]*$"


class Unit(StrEnum):
    USD = "USD"
    USD_PER_SHARE = "USD_per_share"
    INR = "INR"
    INR_PER_SHARE = "INR_per_share"
    PERCENT = "percent"  # stored as a fraction: 0.25 == 25%
    RATIO = "ratio"  # multiples, e.g. EV / EBITDA
    SHARES = "shares"
    COUNT = "count"


class MissingFactError(KeyError):
    """A spec references facts that `facts.json` does not contain."""

    def __init__(self, missing: list[str]) -> None:
        super().__init__(missing)
        self.missing = missing

    def __str__(self) -> str:
        return f"facts.json has no value for: {', '.join(self.missing)}"


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=FACT_ID_PATTERN)
    entity: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    period: str = Field(min_length=1)
    value: Decimal
    unit: Unit
    source_ref: str = Field(min_length=1, description="Filing/accession, file+cell, or URL")


class FactSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    facts: list[Fact]

    @model_validator(mode="after")
    def _unique_ids(self) -> FactSet:
        counts = Counter(f.id for f in self.facts)
        dupes = sorted(i for i, n in counts.items() if n > 1)
        if dupes:
            raise ValueError(f"duplicate fact ids: {dupes}")
        return self

    def get(self, fact_id: str) -> Fact:
        return self.require([fact_id])[0]

    def require(self, fact_ids: list[str]) -> list[Fact]:
        """Return facts in order, or raise listing every missing id at once."""
        index = {f.id: f for f in self.facts}
        missing = sorted({i for i in fact_ids if i not in index})
        if missing:
            raise MissingFactError(missing)
        return [index[i] for i in fact_ids]

    def merge(self, *others: FactSet) -> FactSet:
        """Combine fact sets; the same id with a different value is a conflict."""
        index = {f.id: f for f in self.facts}
        for other in others:
            for fact in other.facts:
                existing = index.get(fact.id)
                if existing is not None and existing.value != fact.value:
                    raise ValueError(
                        f"conflicting values for '{fact.id}': {existing.value} "
                        f"({existing.source_ref}) vs {fact.value} ({fact.source_ref})"
                    )
                index.setdefault(fact.id, fact)
        return FactSet(facts=sorted(index.values(), key=lambda f: f.id))

    def dump(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> FactSet:
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
