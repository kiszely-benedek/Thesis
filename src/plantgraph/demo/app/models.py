"""Data types the demo shows the user: sheet links, the cost estimate and the spend status."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SheetLink(BaseModel):
    """A drawing sheet the answer points at, with the PDF page that shows it."""

    model_config = ConfigDict(frozen=True)

    sheet_id: str
    #: 1-based page of the sheet in the exported drawing PDF.
    page: int
    #: Tags that put this sheet in the list (empty for a sheet the agent only read).
    tags: tuple[str, ...] = ()


class TierCostStats(BaseModel):
    """What one cascade tier cost per question in recorded runs."""

    model_config = ConfigDict(frozen=True)

    median_usd: float
    #: The dearest question seen: the figure a reservation is built on.
    max_usd: float
    n_questions: int
    #: The recorded runs the figures were read from.
    run_ids: tuple[str, ...]
    #: True when no run of the asked corpus matched, so another corpus's runs stand in.
    other_corpus: bool


class CostEstimate(BaseModel):
    """Per-tier cost figures and the amount one confirmed question reserves."""

    model_config = ConfigDict(frozen=True)

    per_tier: dict[str, TierCostStats]
    #: Safety factor times the sum of the tiers' worst seen costs.
    reservation_usd: float


class SpendStatus(BaseModel):
    """Money spent this session, the cap, and everything the demo has ever spent."""

    model_config = ConfigDict(frozen=True)

    session_spent_usd: float
    #: `None` when the server runs without paid calls (no cap needed).
    session_cap_usd: float | None
    #: Sum over the demo's whole `calls.jsonl`, across sessions.
    demo_total_spent_usd: float
