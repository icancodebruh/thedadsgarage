#!/usr/bin/env bash
# Jazz Pharmaceuticals board deck, end to end. Run from the repo root.
# Needs: templates/jazz_pitch_book.pptx (local only), SEC_USER_AGENT in .env,
# examples/jazz/inputs.xlsx filled in (market data + valuation ranges).
set -euo pipefail
EX=examples/jazz

uv run deckforge template analyze templates/jazz_pitch_book.pptx --out out/jazz_pitch_book
uv run deckforge ingest sec JAZZ NBIX ALKS INCY UTHR BMRN --years 2022-2025 --out "$EX/facts.sec.json"
uv run deckforge ingest excel "$EX/inputs.xlsx" --out "$EX/facts.inputs.json"
uv run deckforge ingest merge "$EX/facts.sec.json" "$EX/facts.inputs.json" --out "$EX/facts.json"
# Optional: let Claude draft the spec from the brief instead of the checked-in one.
#   uv run deckforge plan "$EX/brief.md" --facts "$EX/facts.json" \
#     --template templates/jazz_pitch_book.pptx --style out/jazz_pitch_book/style.json \
#     --layouts out/jazz_pitch_book/layouts.json --out "$EX/deck_spec.json"
uv run deckforge make "$EX/deck_spec.json" --out out/jazz
