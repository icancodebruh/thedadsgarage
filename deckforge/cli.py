"""DeckForge command-line interface."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from deckforge.log import configure_logging
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(logging.DEBUG if args.verbose else logging.INFO)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
