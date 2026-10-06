# DeckForge

Finance deck generator (pitch / IC / company profile): a reference PowerPoint template in,
a client-ready, **native and editable** `.pptx` out. Every number is bound to a sourced
fact, and every slide passes automated QC before delivery. See `CLAUDE.md` for the full
design brief and engineering standards.

## Pipeline

| Stage | Command | Output |
|---|---|---|
| Template analysis | `deckforge template analyze REF.pptx` | `style.json`, `layouts.json` |
| Ingest: SEC 10-K XBRL | `deckforge ingest sec JAZZ NBIX --years 2022-2025` | facts (with filing refs) |
| Ingest: Excel inputs | `deckforge ingest excel inputs.xlsx` | facts (blank cells reported as gaps) |
| Merge | `deckforge ingest merge a.json b.json --out facts.json` | one `facts.json` (conflicts fail) |
| Brief to spec (Claude) | `deckforge plan brief.md --facts ... --template ... --style ... --layouts ...` | `deck_spec.json` |
| Build | `deckforge build deck_spec.json` | `.pptx` + `.manifest.json` (every number, its facts and sources) |
| QC | `deckforge qc deck.pptx --spec deck_spec.json` | issues (exit 1 on errors) |
| **All of it** | `deckforge make deck_spec.json --out out/x` | `deck.pptx`, `qc_report.md/json`, per-pass PNGs and specs |

`make` builds, renders with headless LibreOffice, runs the deterministic checkers plus a
Claude vision review, turns failures into **spec edits** (retitle, split an overflowing
table, have Claude tighten a slide) and rebuilds. It stops after at most two fix passes
and reports whatever remains.

## Slide types

`title`, `exec_summary`, `company_overview`, `financial_table`, `trading_comps`
(peer median/mean computed and traced), `football_field` (native floating-bar chart).
Running text never contains typed numbers: it uses tokens such as
`{{jazz.revenue.fy2025|currency:billions:1}}`, rendered from `facts.json`.

## QC checkers (`deckforge/qc/checkers/`)

fonts/sizes/colors from `style.json` · text overflow, slide bounds, margins · negatives
in brackets, lower-case `x` · same metric + period = same value, one precision per format
· table totals and ratios tie · source footnote on every data slide and no number without
a fact · no filler text or empty placeholders · title casing per the template ·
spelling/grammar (LanguageTool, optional) · rendered-slide vision review (Claude).

## Setup

```bash
uv sync                      # Python 3.11+, installs dev tools too
uv sync --extra proof        # optional: LanguageTool spell/grammar check (needs Java)
cp .env.example .env         # SEC_USER_AGENT, ANTHROPIC_API_KEY
uv run pytest && uv run ruff check . && uv run mypy
```

LibreOffice (`soffice`) and Poppler (`pdftoppm`) are needed for rendering and vision QC.
Without Claude credentials, `plan` is unavailable and `make` skips vision review and
LLM revisions (deterministic QC still runs; use `--no-llm` to skip explicitly).

## Example: Jazz Pharmaceuticals

`examples/jazz/` has the brief, a deck spec covering all six slide types, and
`inputs.xlsx` for the data SEC filings do not carry (share price, market cap, peer
EV/EBITDA, valuation ranges). Fill the yellow cells, then run `examples/jazz/run.sh`.
Missing data stops the build with a list of every gap; nothing is guessed.

## Data policy

Public-company data and self-made templates only. Reference decks under `templates/` are
git-ignored; commit only templates you own (`git add -f`).
