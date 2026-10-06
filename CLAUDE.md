# DeckForge — Finance Deck Generator (personal project)

## Mission
Generate client-ready finance PowerPoint decks (pitch / IC / company profile) that match a
reference template on the first pass, with every number traceable to a source and every
slide passing automated QC. Goal: remove the "iterate 100 times" loop of generic AI decks.

Data policy: public-company data and self-made templates only. No third-party or client material.

## MVP scope (v0.1)
In:
- One reference template (.pptx) → extracted style + layout library
- 6 slide types: title, exec summary, company overview, financial summary table,
  trading comps table, valuation football field (native chart)
- Inputs: structured Excel/CSV + SEC filings (edgartools)
- Output: native, editable .pptx (native charts, no images of tables)
- QC: deterministic checks + rendered visual review, max 2 auto-fix passes
- CLI only

Out (later): web UI, LBO/precedents slides, image/logo sourcing, live data vendors, multi-template.

## Pipeline
1. **Ingest** — openpyxl (Excel), edgartools (SEC XBRL), docling (PDFs) → `facts.json`
   (every fact has `value`, `unit`, `period`, `source_ref`)
2. **Template analysis** — parse reference .pptx (masters, layouts, placeholders, fonts,
   palette, grid) → `style.json` + `layouts.json`  (PPTAgent-style: learn from the reference)
3. **Brief → spec** — Claude turns the user brief into `deck_spec.json` (validated by
   pydantic). One entry per slide: `slide_type`, `layout_id`, `title`, content blocks,
   `fact_refs`. The brief is stored in the spec and re-read at every stage.
4. **Build** — python-pptx renders spec into the template's layouts. Numbers are bound
   from `facts.json` by reference, never typed by the model.
5. **QC** — deterministic checkers (below) + LibreOffice headless → PNG per slide →
   Claude vision review against `style.json` and the brief.
6. **Fix loop** — failed checks become targeted spec edits; rebuild; max 2 passes, then
   report remaining issues instead of looping.

## QC rules (each is its own tested checker)
- Fonts, sizes, colors only from `style.json`
- No text overflow / clipping; shapes snap to template grid; consistent margins
- Number formats consistent deck-wide ($m, 1 dp, multiples as "x", negatives in brackets)
- Same metric + period = same value on every slide
- Table totals and percentages tie
- Every data slide has a source footnote; every number has a `source_ref`
- No placeholder text (lorem, xxx, TBD, empty placeholders)
- Title case / sentence case per template rule; spell + grammar check (LanguageTool)
- Rendered slide matches its layout (vision check)

## Repo structure
```
deckforge/
  ingest/        # excel.py, sec.py, pdf.py -> facts.json
  template/      # analyze.py -> style.json, layouts.json
  spec/          # models.py (pydantic), planner.py (Claude brief -> spec)
  build/         # renderer.py, slide_types/*.py, charts.py
  qc/            # checkers/*.py, render.py (LibreOffice), vision_review.py
  cli.py
templates/       # reference .pptx files
examples/        # sample briefs + public-company inputs
tests/           # pytest, one test file per checker and slide type
```

## Engineering standards
- Python 3.11+, `uv` for env/deps, type hints everywhere, pydantic for all schemas
- `ruff` (lint + format), `mypy`, `pytest`; tests before merging any checker
- Small pure functions; slide types are plugins with one interface
- No hardcoded numbers or styles in code — everything from facts/style files
- Secrets in `.env` (never committed); structured logging; deterministic outputs (seeded)
- Ask before adding a dependency; prefer the ones listed below

## Rules for Claude
- Never invent or transcribe numbers; bind from `facts.json` or stop and flag the gap
- After any build/template change, run the full render + QC loop and show results
- Keep the brief in view; if a slide drifts from it, fix the spec, not the output file
- Prefer native PowerPoint objects (tables, charts) over images
- Don't copy code from source-available repos; learn the pattern, write our own

## Reference repos
| Area | Repo | Use / note |
|---|---|---|
| Finance deck agent | anthropics/financial-services | Pitch Agent, ib-check-deck, deck-refresh patterns |
| PPTX skill | anthropics/skills (pptx) | Render-check loop pattern; source-available, don't copy |
| Reference-deck learning | icip-cas/PPTAgent | Template analysis + edit-based generation |
| UI / API reference | presenton/presenton | Apache 2.0; template-from-PPTX, later UI |
| PPTX engine | scanny/python-pptx | Core build library |
| PPTX via MCP | GongRzhe/Office-PowerPoint-MCP-Server | Optional agent editing |
| SEC data | dgunning/edgartools | XBRL statements, MCP server |
| Market data | OpenBB-finance/OpenBB | Check license before any commercial use |
| PDF parsing | docling-project/docling | Tables from filings / reports |
| PPTX → text | microsoft/markitdown | Read existing decks |
| Proofing | languagetool-org/languagetool | Spelling + grammar |
| Rendering | LibreOffice (headless) | PPTX → PDF/PNG for visual QC |

## Milestones
1. Template analyzer outputs `style.json` + `layouts.json` for one reference deck
2. Spec schema + 2 slide types (title, financial table) render correctly
3. Deterministic QC checkers with tests
4. Render + vision review + fix loop
5. Remaining 4 slide types + SEC ingest
6. Minimal UI (Streamlit) once CLI output is reliable
