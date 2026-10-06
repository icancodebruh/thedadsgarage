"""Fact tokens embedded in running text: `{{fact.id|kind[:scale][:decimals]}}`.

Bullets and descriptions never contain typed numbers; they reference facts by id and
the builder renders the value, so every number in text stays traceable.
"""

from __future__ import annotations

import re

FACT_TOKEN = re.compile(
    r"\{\{\s*(?P<id>[a-z0-9][a-z0-9_.\-]*)\s*\|\s*(?P<kind>[a-z_]+)"
    r"(?::(?P<scale>[a-z]+))?(?::(?P<decimals>\d))?\s*\}\}"
)


def token_refs(text: str) -> list[str]:
    """Fact ids referenced by tokens in a piece of text."""
    return [m["id"] for m in FACT_TOKEN.finditer(text)]
