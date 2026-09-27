"""The context-wall fit check every strategy's final prompt goes through (`qa-system.md` §7, §12).

A **context wall** is the largest prompt an LLM's fixed-size context window
accepts before the provider rejects the call outright — every model has one,
and the pilot (`pilot.py`) measures it once per pinned model by a binary
search that records `max_ok_chars` (safe) and `min_rejected_chars` (already
rejected). This module turns that measurement into a decision: send the
call, or already know it will not fit.

There are two paths to `Outcome.DID_NOT_FIT` (ADR-0013 point 6, "one shared
final step"), and both are **outcomes, never errors** — a plant-scale prompt
that does not fit is exactly what the thesis claim expects to observe:

- **pre-call** (`check_fit`): the prompt is at or beyond `min_rejected_chars`,
  a size the probe has already seen the provider reject. No call is made, so
  this path costs nothing.
- **on-call** (`handle_overflow`): the prompt is smaller than that, the call
  is attempted, and the provider still raises `ContextOverflow`.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from plantgraph.llm.models import ContextOverflow, ContextWall
from plantgraph.qa.models import Outcome


class FitDecision(BaseModel):
    """Whether the final call should be attempted, and the trace to record either way."""

    model_config = ConfigDict(frozen=True)

    should_call: bool
    #: Set only when `should_call` is False. `check_fit` and `handle_overflow`
    #: never return `should_call=False` without one (no silent failures).
    outcome: Outcome | None
    #: Which path decided this, for `QuestionResult.trace` (§7's "a record of
    #: which path triggered"). Always has `fit_check` and `overflow_on_call`.
    trace: dict[str, Any]


def check_fit(prompt_chars: int, wall: ContextWall | None) -> FitDecision:
    """Decide, before any call, whether a prompt of `prompt_chars` should be sent (§7).

    Characters, not tokens, are the unit (decision D6): the wall itself was
    measured against the same serialized format, so no tokenizer needs to
    agree with the provider's.

    Until the pilot has measured a wall for the pinned model, `wall` is
    `None`. That is **not treated as an error**: nothing here can yet tell a
    prompt that fits from one that does not, so every call is let through,
    and only the on-call path (`handle_overflow`) can still catch an
    oversized one. This is what lets a coder task or a dev run work before
    CP1's first measured wall exists (`qa-system.md` §18.2).
    """
    if wall is None:
        return FitDecision(
            should_call=True,
            outcome=None,
            trace={"fit_check": "no_wall_known", "overflow_on_call": False},
        )
    if wall.min_rejected_chars is not None and prompt_chars >= wall.min_rejected_chars:
        return FitDecision(
            should_call=False,
            outcome=Outcome.DID_NOT_FIT,
            trace={
                "fit_check": "pre_call_over_min_rejected",
                "overflow_on_call": False,
                "prompt_chars": prompt_chars,
                "min_rejected_chars": wall.min_rejected_chars,
            },
        )
    # At or under max_ok_chars is the wall's known-safe zone. Above it but
    # below min_rejected_chars (or above it with no rejection measured yet)
    # is the margin the binary search left unresolved, so the call is still
    # attempted and only a live ContextOverflow settles it (§7, "the margin").
    fit_check = "under_max_ok" if prompt_chars <= wall.max_ok_chars else "within_margin"
    return FitDecision(
        should_call=True, outcome=None, trace={"fit_check": fit_check, "overflow_on_call": False}
    )


def handle_overflow(prompt_chars: int, error: ContextOverflow) -> FitDecision:
    """Turn an on-call `ContextOverflow` into `DID_NOT_FIT` (§7's second path).

    Never re-raised: like the pre-call rejection above, this is scored data,
    not a bug — the provider is telling us the prompt did not fit.
    """
    return FitDecision(
        should_call=False,
        outcome=Outcome.DID_NOT_FIT,
        trace={
            "fit_check": "overflow_on_call",
            "overflow_on_call": True,
            "prompt_chars": prompt_chars,
            "provider_message": str(error),
        },
    )
