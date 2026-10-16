"""The English text table of the demo page, loaded from `static/labels.en.json`.

The JSON is the one place where an outcome, stop reason, tier, strategy, topic, store state,
job state or error code gets its visitor-facing English text. The server sends codes; the
page looks the text up. The server itself reads only the topic sections (to tag examples).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict

LABELS_PATH = Path(__file__).parent / "static" / "labels.en.json"


class Labels(BaseModel):
    """Every section of the label table; each maps a code to its English text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcomes: dict[str, str]
    stop_reasons: dict[str, str]
    tiers: dict[str, str]
    strategies: dict[str, str]
    #: Topic code -> heading, in the order the page lists them.
    topics: dict[str, str]
    #: Question-family value -> topic code.
    family_topics: dict[str, str]
    store_states: dict[str, str]
    job_states: dict[str, str]
    error_codes: dict[str, str]
    answer_values: dict[str, str]


@lru_cache(maxsize=1)
def load_labels() -> Labels:
    """Read and validate the label table (once).

    Raises:
        FileNotFoundError: the JSON is missing.
        ValueError: it is not valid JSON or has missing or unknown sections.
    """
    if not LABELS_PATH.exists():
        raise FileNotFoundError(f"expected the label table at {LABELS_PATH}, found no such file")
    return Labels.model_validate(json.loads(LABELS_PATH.read_text(encoding="utf-8")))
