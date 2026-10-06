"""Spelling and grammar via LanguageTool (optional extra: `uv sync --extra proof`)."""

from __future__ import annotations

import importlib
import re
from typing import Any

from deckforge.qc.checkers.common import slide_texts
from deckforge.qc.context import QCContext
from deckforge.qc.models import Issue, Severity

NAME = "spelling"
NUMERIC = re.compile(r"[\d$%()]")
IGNORED_RULES = frozenset(
    {"WHITESPACE_RULE", "UPPERCASE_SENTENCE_START", "COMMA_PARENTHESIS_WHITESPACE"}
)


def _tool() -> Any:
    module = importlib.import_module("language_tool_python")
    return module.LanguageTool("en-US")


def check(ctx: QCContext) -> list[Issue]:
    try:
        tool = _tool()
    except Exception as exc:  # missing package, Java, or network for the LT download
        return [
            Issue(
                checker=NAME,
                severity=Severity.INFO,
                slide=None,
                message=f"spell/grammar check skipped: {type(exc).__name__}: {exc}",
            )
        ]
    issues: list[Issue] = []
    try:
        for n, slide in ctx.slides():
            for shape, text in slide_texts(slide):
                if getattr(shape, "has_table", False) or text.startswith("Source:"):
                    continue
                for match in tool.check(text):
                    if match.rule_id in IGNORED_RULES:
                        continue
                    word = text[match.offset : match.offset + match.error_length]
                    if NUMERIC.search(word):
                        continue
                    # Capitalised "misspellings" are company names, tickers and acronyms.
                    if match.rule_issue_type == "misspelling" and word[:1].isupper():
                        continue
                    issues.append(
                        Issue(
                            checker=NAME,
                            severity=Severity.WARNING,
                            slide=n,
                            message=f"'{word}': {match.message}",
                        )
                    )
    finally:
        tool.close()
    return issues
