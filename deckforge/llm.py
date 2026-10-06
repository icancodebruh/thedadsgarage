"""Claude access for planning, revision, and vision review (structured outputs only).

Every call returns a validated pydantic object; free text never flows into the deck.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Protocol, TypeVar, cast

import anthropic
from anthropic.types.beta import BetaOutputConfigParam
from pydantic import BaseModel

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"
# Server-side fallback re-runs a safety-declined request on Anthropic's recommended model.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 16_000

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Claude could not produce a usable structured answer."""


class StructuredLLM(Protocol):
    def structured(self, *, system: str, content: list[dict[str, Any]], schema: type[T]) -> T: ...


class ClaudeLLM:
    def __init__(self, model: str | None = None, effort: str = "high") -> None:
        self.model = model or os.environ.get("DECKFORGE_MODEL", DEFAULT_MODEL)
        self.effort = effort
        self._client = anthropic.Anthropic()

    def structured(self, *, system: str, content: list[dict[str, Any]], schema: type[T]) -> T:
        try:
            response = self._client.beta.messages.parse(
                model=self.model,
                max_tokens=MAX_TOKENS,
                betas=[FALLBACK_BETA],
                fallbacks="default",
                system=system,
                messages=[{"role": "user", "content": content}],  # type: ignore[typeddict-item]
                output_format=schema,
                output_config=cast(BetaOutputConfigParam, {"effort": self.effort}),
            )
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Claude API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError(f"cannot reach the Claude API: {exc}") from exc
        if response.stop_reason == "refusal":
            raise LLMError("Claude declined the request")
        parsed = response.parsed_output
        if parsed is None:
            raise LLMError(f"no structured output (stop_reason={response.stop_reason})")
        log.info(
            "claude call",
            extra={
                "schema": schema.__name__,
                "model": response.model,
                "output_tokens": response.usage.output_tokens,
            },
        )
        return parsed


def default_llm() -> StructuredLLM | None:
    """A Claude client when credentials are configured, else None (LLM steps are skipped)."""
    try:
        return ClaudeLLM()
    except anthropic.AnthropicError as exc:
        log.warning("Claude unavailable; LLM steps skipped", extra={"reason": str(exc)})
        return None
