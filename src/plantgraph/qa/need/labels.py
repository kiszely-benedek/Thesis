"""The closed set of need labels (design `question-aware-retrieval.md` §4.1).

A **need label** names the shape of evidence a question needs: the item itself, its direct
neighbours, a flow route, everything upstream, and so on. One label per shape the plant graph
allows, each directional shape in both directions, plus `GENERIC` for "none of these". The set
is fixed before any held-out family is opened, so it cannot be tuned to them.

This module imports nothing: `qa/need/` must stay free of gold-side code.
"""

from __future__ import annotations

from enum import Enum


class NeedLabel(str, Enum):
    """One evidence shape; the description of each is the classifier's text (QAR-T4)."""

    ITEM = "ITEM"
    NEIGHBOURS_DOWNSTREAM = "NEIGHBOURS_DOWNSTREAM"
    NEIGHBOURS_UPSTREAM = "NEIGHBOURS_UPSTREAM"
    SIGNAL_CHAIN = "SIGNAL_CHAIN"
    PATH = "PATH"
    UPSTREAM_TO_FIRST_VALVE = "UPSTREAM_TO_FIRST_VALVE"
    DOWNSTREAM_TO_FIRST_VALVE = "DOWNSTREAM_TO_FIRST_VALVE"
    UPSTREAM_ALL = "UPSTREAM_ALL"
    DOWNSTREAM_ALL = "DOWNSTREAM_ALL"
    UNIT_SCOPE = "UNIT_SCOPE"
    GENERIC = "GENERIC"
