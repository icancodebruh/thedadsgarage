"""DeckForge command-line interface."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from deckforge.build.renderer import build_deck
from deckforge.log import configure_logging
from deckforge.qc.render import render_slides
from deckforge.spec.models import DeckSpec
from deckforge.template.analyze import analyze_template, write_outputs

log = logging.getLogger("deckforge.cli")


def _cmd_template_analyze(args: argparse.Namespace) -> int:
    src: Path = args.pptx
    out: Path = args.out or Path("out") / src.stem
    style, library = analyze_template(src)
    style_path, layouts_path = write_outputs(style, library, out)
    log.info(
        "template analyzed",
        extra={
            "style": str(style_path),
            "layouts": str(layouts_path),
            "warnings": len(library.warnings),
        },
    )
    for warning in library.warnings:
        log.warning(warning)
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    spec_path: Path = args.spec
    out: Path = args.out or Path("out") / f"{spec_path.parent.name}.pptx"
    deck = build_deck(DeckSpec.load(spec_path), spec_path.parent, out)
    if args.render:
        _render(deck, args.render)
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    _render(args.pptx, args.out or Path("out") / f"{args.pptx.stem}_png")
    return 0


def _render(deck: Path, out_dir: Path) -> None:
    pngs = render_slides(deck, out_dir)
    log.info("slides rendered", extra={"dir": str(out_dir), "count": len(pngs)})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="deckforge", description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    template = sub.add_parser("template", help="reference template tools")
    template_sub = template.add_subparsers(dest="template_command", required=True)
    analyze = template_sub.add_parser("analyze", help="extract style.json + layouts.json")
    analyze.add_argument("pptx", type=Path, help="reference .pptx")
    analyze.add_argument("--out", type=Path, help="output directory (default: out/<stem>)")
    analyze.set_defaults(func=_cmd_template_analyze)

    build = sub.add_parser("build", help="render deck_spec.json into a .pptx")
    build.add_argument("spec", type=Path, help="deck_spec.json")
    build.add_argument("--out", type=Path, help="output .pptx (default: out/<spec dir>.pptx)")
    build.add_argument("--render", type=Path, metavar="DIR", help="also render PNGs to DIR")
    build.set_defaults(func=_cmd_build)

    render = sub.add_parser("render", help="render a .pptx to one PNG per slide")
    render.add_argument("pptx", type=Path)
    render.add_argument("--out", type=Path, help="output dir (default: out/<stem>_png)")
    render.set_defaults(func=_cmd_render)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(logging.DEBUG if args.verbose else logging.INFO)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
