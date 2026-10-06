"""DeckForge command-line interface.

deckforge template analyze REF.pptx            -> style.json + layouts.json
deckforge ingest sec JAZZ NBIX --years 2022-2024 -> facts (SEC XBRL)
deckforge ingest excel inputs.xlsx              -> facts (manual / market inputs)
deckforge ingest merge a.json b.json            -> one facts.json
deckforge plan BRIEF.md ...                     -> deck_spec.json (Claude)
deckforge build deck_spec.json                  -> .pptx (+ manifest)
deckforge qc deck.pptx --spec deck_spec.json    -> QC issues
deckforge make deck_spec.json                   -> build + render + QC + fix loop
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from deckforge.build.renderer import build_deck, load_manifest
from deckforge.config import load_env
from deckforge.ingest import excel, sec
from deckforge.ingest.models import FactSet
from deckforge.llm import ClaudeLLM, default_llm
from deckforge.log import configure_logging
from deckforge.pipeline import make
from deckforge.qc.context import QCContext
from deckforge.qc.models import Severity
from deckforge.qc.render import render_slides
from deckforge.qc.run import run_checks
from deckforge.spec.models import DeckSpec, TemplateRef
from deckforge.spec.planner import plan_deck
from deckforge.template.analyze import analyze_template, write_outputs
from deckforge.template.models import LayoutLibrary, StyleSpec

log = logging.getLogger("deckforge.cli")


def _years(spec: str | None) -> list[int] | None:
    if not spec:
        return None
    lo, _, hi = spec.partition("-")
    return list(range(int(lo), int(hi or lo) + 1))


def _relative(path: Path, start: Path) -> Path:
    return Path(os.path.relpath(path.resolve(), start.resolve()))


# --- commands ---------------------------------------------------------------------------


def _template_analyze(args: argparse.Namespace) -> int:
    out: Path = args.out or Path("out") / args.pptx.stem
    style, library = analyze_template(args.pptx)
    style_path, layouts_path = write_outputs(style, library, out)
    log.info("template analyzed", extra={"style": str(style_path), "layouts": str(layouts_path)})
    for warning in library.warnings:
        log.warning(warning)
    return 0


def _ingest_sec(args: argparse.Namespace) -> int:
    facts = sec.ingest_tickers(
        args.tickers, os.environ.get("SEC_USER_AGENT", ""), _years(args.years)
    )
    FactSet(facts=facts).dump(args.out)
    log.info("facts written", extra={"path": str(args.out), "facts": len(facts)})
    return 0


def _ingest_excel(args: argparse.Namespace) -> int:
    result = excel.read_facts(args.xlsx, args.sheet)
    FactSet(facts=result.facts).dump(args.out)
    log.info("facts written", extra={"path": str(args.out), "facts": len(result.facts)})
    if result.missing:
        log.warning("blank values (gaps)", extra={"ids": result.missing})
    return 0


def _ingest_merge(args: argparse.Namespace) -> int:
    sets = [FactSet.load(p) for p in args.inputs]
    merged = sets[0].merge(*sets[1:])
    merged.dump(args.out)
    log.info("facts merged", extra={"path": str(args.out), "facts": len(merged.facts)})
    return 0


def _plan(args: argparse.Namespace) -> int:
    out: Path = args.out
    base = out.parent
    style = StyleSpec.model_validate_json(args.style.read_text())
    library = LayoutLibrary.model_validate_json(args.layouts.read_text())
    spec = plan_deck(
        brief=args.brief.read_text(encoding="utf-8"),
        facts=FactSet.load(args.facts),
        style=style,
        library=library,
        template=TemplateRef(
            pptx=_relative(args.template, base),
            style=_relative(args.style, base),
            layouts=_relative(args.layouts, base),
        ),
        facts_path=_relative(args.facts, base),
        llm=ClaudeLLM(),
    )
    spec.dump(out)
    log.info("spec planned", extra={"path": str(out), "slides": len(spec.slides)})
    return 0


def _build(args: argparse.Namespace) -> int:
    spec_path: Path = args.spec
    out: Path = args.out or Path("out") / f"{spec_path.parent.name}.pptx"
    deck = build_deck(DeckSpec.load(spec_path), spec_path.parent, out)
    if args.render:
        pngs = render_slides(deck, args.render)
        log.info("slides rendered", extra={"dir": str(args.render), "count": len(pngs)})
    return 0


def _render(args: argparse.Namespace) -> int:
    out = args.out or Path("out") / f"{args.pptx.stem}_png"
    pngs = render_slides(args.pptx, out)
    log.info("slides rendered", extra={"dir": str(out), "count": len(pngs)})
    return 0


def _qc(args: argparse.Namespace) -> int:
    spec = DeckSpec.load(args.spec)
    ctx = QCContext.load(args.pptx, spec, args.spec.parent, load_manifest(args.pptx))
    issues = run_checks(ctx)
    print(json.dumps([i.model_dump(mode="json") for i in issues], indent=2))
    return 1 if any(i.severity is Severity.ERROR for i in issues) else 0


def _make(args: argparse.Namespace) -> int:
    out: Path = args.out or Path("out") / args.spec.parent.name
    llm = None if args.no_llm else default_llm()
    skip = frozenset(args.skip or [])
    result = make(args.spec, out, llm=llm, max_fix_passes=args.max_fix_passes, skip=skip)
    print(result.report.to_markdown())
    log.info(
        "make done",
        extra={
            "deck": str(result.deck),
            "report": str(result.report_path),
            "spec": str(result.spec),
            "clean": result.report.clean,
        },
    )
    return 0 if result.report.clean else 1


# --- parser -----------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deckforge", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    template = sub.add_parser("template", help="reference template tools")
    t_sub = template.add_subparsers(dest="template_command", required=True)
    analyze = t_sub.add_parser("analyze", help="extract style.json + layouts.json")
    analyze.add_argument("pptx", type=Path)
    analyze.add_argument("--out", type=Path, help="output dir (default: out/<stem>)")
    analyze.set_defaults(func=_template_analyze)

    ingest = sub.add_parser("ingest", help="build facts.json from sources")
    i_sub = ingest.add_subparsers(dest="ingest_command", required=True)
    i_sec = i_sub.add_parser("sec", help="annual 10-K facts from SEC XBRL")
    i_sec.add_argument("tickers", nargs="+")
    i_sec.add_argument("--years", help="e.g. 2021-2024")
    i_sec.add_argument("--out", type=Path, default=Path("facts.sec.json"))
    i_sec.set_defaults(func=_ingest_sec)
    i_xls = i_sub.add_parser("excel", help="facts from an Excel 'facts' sheet")
    i_xls.add_argument("xlsx", type=Path)
    i_xls.add_argument("--sheet", default=excel.SHEET)
    i_xls.add_argument("--out", type=Path, default=Path("facts.excel.json"))
    i_xls.set_defaults(func=_ingest_excel)
    i_merge = i_sub.add_parser("merge", help="merge facts files (conflicts are errors)")
    i_merge.add_argument("inputs", type=Path, nargs="+")
    i_merge.add_argument("--out", type=Path, default=Path("facts.json"))
    i_merge.set_defaults(func=_ingest_merge)

    plan = sub.add_parser("plan", help="Claude: brief -> deck_spec.json")
    plan.add_argument("brief", type=Path)
    plan.add_argument("--facts", type=Path, required=True)
    plan.add_argument("--template", type=Path, required=True, help="reference .pptx")
    plan.add_argument("--style", type=Path, required=True)
    plan.add_argument("--layouts", type=Path, required=True)
    plan.add_argument("--out", type=Path, default=Path("deck_spec.json"))
    plan.set_defaults(func=_plan)

    build = sub.add_parser("build", help="render deck_spec.json into a .pptx")
    build.add_argument("spec", type=Path)
    build.add_argument("--out", type=Path, help="output .pptx (default: out/<spec dir>.pptx)")
    build.add_argument("--render", type=Path, metavar="DIR", help="also render PNGs to DIR")
    build.set_defaults(func=_build)

    render = sub.add_parser("render", help="render a .pptx to one PNG per slide")
    render.add_argument("pptx", type=Path)
    render.add_argument("--out", type=Path)
    render.set_defaults(func=_render)

    qc = sub.add_parser("qc", help="run deterministic QC checks on a built deck")
    qc.add_argument("pptx", type=Path)
    qc.add_argument("--spec", type=Path, required=True)
    qc.set_defaults(func=_qc)

    mk = sub.add_parser("make", help="build + render + QC + fix loop (max 2 passes)")
    mk.add_argument("spec", type=Path)
    mk.add_argument("--out", type=Path, help="output dir (default: out/<spec dir>)")
    mk.add_argument("--max-fix-passes", type=int, default=2, choices=range(0, 3))
    mk.add_argument("--no-llm", action="store_true", help="skip vision review and LLM fixes")
    mk.add_argument("--skip", nargs="*", help="checker names to skip, e.g. spelling vision")
    mk.set_defaults(func=_make)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    load_env()
    args = build_parser().parse_args(argv)
    configure_logging(logging.DEBUG if args.verbose else logging.INFO)
    try:
        return int(args.func(args))
    except (ValueError, RuntimeError, OSError) as exc:
        log.error(str(exc), extra={"error": type(exc).__name__})
        return 2


if __name__ == "__main__":
    sys.exit(main())
