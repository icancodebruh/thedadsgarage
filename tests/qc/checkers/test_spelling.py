from __future__ import annotations

import importlib.util

import pytest

from deckforge.qc.checkers import spelling
from deckforge.qc.models import Severity
from tests.qc.checkers.helpers import add_box
from tests.qc.conftest import MakeCtx

HAS_LT = importlib.util.find_spec("language_tool_python") is not None


@pytest.mark.skipif(HAS_LT, reason="LanguageTool installed; skip path not exercised")
def test_skips_cleanly_without_languagetool(make_ctx: MakeCtx) -> None:
    issues = spelling.check(make_ctx())
    assert len(issues) == 1 and issues[0].severity is Severity.INFO


@pytest.mark.skipif(not HAS_LT, reason="needs the proof extra")
def test_flags_typos_but_not_company_names(make_ctx: MakeCtx) -> None:
    ctx = make_ctx(lambda prs: add_box(prs, 2, "Testco grew its revenu quickly"))
    issues = spelling.check(ctx)
    if issues and issues[0].severity is Severity.INFO:
        pytest.skip(f"LanguageTool unavailable: {issues[0].message}")
    words = " ".join(i.message for i in issues)
    assert "'revenu'" in words and "Testco" not in words
