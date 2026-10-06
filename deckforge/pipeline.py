"""End to end: build -> render -> QC (deterministic + vision) -> fix spec -> rebuild.

At most `max_fix_passes` rounds of fixes; whatever remains is reported, not looped on.
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from deckforge.build.renderer import build_deck, load_manifest
from deckforge.build.slide_types.base import LayoutOverflowError
from deckforge.ingest.models import FactSet
from deckforge.llm import LLMError, StructuredLLM
from deckforge.qc import vision_review
from deckforge.qc.context import QCContext
from deckforge.qc.fixes import apply_fixes
from deckforge.qc.models import Issue, PassRecord, QCReport, Severity, SpecFix
from deckforge.qc.render import RenderError, render_slides
from deckforge.qc.run import run_checks
from deckforge.spec.models import DeckSpec
from deckforge.template.models import LayoutLibrary

log = logging.getLogger(__name__)
MAX_FIX_PASSES = 2


@dataclass(frozen=True)
class MakeResult:
    deck: Path | None
    spec: Path
    report: QCReport
    report_path: Path


def _qc(
    deck: Path,
    spec: DeckSpec,
    base_dir: Path,
    png_dir: Path,
    llm: StructuredLLM | None,
    skip: frozenset[str],
) -> list[Issue]:
    ctx = QCContext.load(deck, spec, base_dir, load_manifest(deck))
    issues = run_checks(ctx, skip)
    try:
        pngs = render_slides(deck, png_dir)
    except RenderError as exc:
        return [
            *issues,
            Issue(
                checker="render",
                severity=Severity.WARNING,
                slide=None,
                message=f"render skipped: {exc}",
            ),
        ]
    if llm is None or "vision" in skip:
        return [
            *issues,
            Issue(
                checker="vision",
                severity=Severity.INFO,
                slide=None,
                message="vision review skipped (no Claude credentials)",
            ),
        ]
    try:
        return issues + vision_review.review(pngs, spec, ctx.style, llm)
    except LLMError as exc:
        return [
            *issues,
            Issue(
                checker="vision",
                severity=Severity.WARNING,
                slide=None,
                message=f"vision review failed: {exc}",
            ),
        ]


def make(
    spec_path: Path,
    out_dir: Path,
    *,
    llm: StructuredLLM | None,
    max_fix_passes: int = MAX_FIX_PASSES,
    skip: frozenset[str] = frozenset(),
) -> MakeResult:
    base_dir = spec_path.parent.resolve()
    spec = DeckSpec.load(spec_path)
    facts = FactSet.load(base_dir / spec.facts)
    library = LayoutLibrary.model_validate_json((base_dir / spec.template.layouts).read_text())
    out_dir.mkdir(parents=True, exist_ok=True)
    report = QCReport()
    final_deck: Path | None = None
    final_spec = spec_path

    for n in range(max_fix_passes + 1):
        target = out_dir / f"deck.pass{n}.pptx"
        built: Path | None = None
        try:
            built = build_deck(spec, base_dir, target)
            issues = _qc(built, spec, base_dir, out_dir / f"png.pass{n}", llm, skip)
            final_deck = built
        except LayoutOverflowError as exc:
            issues = [
                Issue(
                    checker="build",
                    severity=Severity.ERROR,
                    slide=exc.slide,
                    message=str(exc),
                    fix=SpecFix(kind="split_table", slide=exc.slide, max_rows=exc.max_rows),
                )
            ]
        record = PassRecord(number=n, deck=built, issues=issues)
        report.passes.append(record)
        blocking = [
            i
            for i in issues
            if i.severity is Severity.ERROR or (i.fix and i.fix.kind == "set_title")
        ]
        if not blocking or n == max_fix_passes:
            break
        spec, applied = apply_fixes(spec, blocking, facts=facts, library=library, llm=llm)
        record.fixes_applied = applied
        if not applied:
            break
        final_spec = out_dir / f"deck_spec.pass{n + 1}.json"
        # Revised specs live next to the outputs; keep their paths valid from there.
        spec = _rebase(spec, base_dir, out_dir)
        base_dir = out_dir.resolve()
        spec.dump(final_spec)

    if final_deck is not None:
        shutil.copyfile(final_deck, out_dir / "deck.pptx")
        shutil.copyfile(final_deck.with_suffix(".manifest.json"), out_dir / "deck.manifest.json")
    report_path = out_dir / "qc_report.json"
    report_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    (out_dir / "qc_report.md").write_text(report.to_markdown() + "\n", encoding="utf-8")
    log.info("make finished", extra={"clean": report.clean, "passes": len(report.passes)})
    return MakeResult(
        deck=out_dir / "deck.pptx" if final_deck else None,
        spec=final_spec,
        report=report,
        report_path=report_path,
    )


def _rebase(spec: DeckSpec, old: Path, new: Path) -> DeckSpec:
    def rel(p: Path) -> Path:
        return Path(os.path.relpath((old / p).resolve(), new.resolve()))

    template = spec.template.model_copy(
        update={
            "pptx": rel(spec.template.pptx),
            "style": rel(spec.template.style),
            "layouts": rel(spec.template.layouts),
        }
    )
    return spec.model_copy(update={"template": template, "facts": rel(spec.facts)})
