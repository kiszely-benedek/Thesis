"""Self-check for the stage-2 pairing: does not depend on the PID2Graph files.

`build_manifest` takes geometric observations (`ConnectorObservation`) as input
and returns a manifest built from the PAIRS/ANNOTATIONS tables. Here the geometry
is made up (one shared placeholder box) — all that matters is that the keys
(sheet:node_id) match the ones in annotations.py. This test therefore guards that
the PAIRS and ANNOTATIONS tables stay internally consistent, without needing the
real drawings.
"""

from __future__ import annotations

from plantgraph.benchmark.models import BoundingBox, ConnectorObservation, Side
from plantgraph.benchmark.open100.annotations import ANNOTATIONS
from plantgraph.benchmark.open100.manifest import PAIRS, build_manifest

_PLACEHOLDER_BOX = BoundingBox(xmin=0.0, ymin=0.0, xmax=10.0, ymax=10.0)


def _fake_observations() -> list[ConnectorObservation]:
    """One observation per annotated connector — the geometry does not matter here."""
    return [
        ConnectorObservation(
            sheet_file=raw.sheet,
            node_id=f"inlet/outlet{raw.node}",
            bbox=_PLACEHOLDER_BOX,
            side=Side.LEFT,
        )
        for raw in ANNOTATIONS
    ]


def test_every_annotated_connector_is_accounted_for() -> None:
    manifest = build_manifest(_fake_observations())
    assert manifest.accounted_for()


def test_no_connector_appears_in_two_buckets() -> None:
    # If a key appeared both paired AND as dangling/unresolved, the PAIRS
    # table and the _classify rule would be contradicting each other.
    manifest = build_manifest(_fake_observations())
    paired = {p.from_key for p in manifest.connector_pairs} | {
        p.to_key for p in manifest.connector_pairs
    }
    dangling = {d.from_key for d in manifest.dangling}
    unresolved = {u.from_key for u in manifest.unresolved}
    assert not (paired & dangling)
    assert not (paired & unresolved)
    assert not (dangling & unresolved)


def test_every_pair_key_exists_among_the_annotations() -> None:
    # A typo'd key in the PAIRS table would silently "disappear" — better to fail here.
    known_keys = {raw.key for raw in ANNOTATIONS}
    for from_key, to_key, _rule, _note in PAIRS:
        assert from_key in known_keys
        assert to_key in known_keys


def test_pairs_do_not_reuse_a_connector() -> None:
    seen: set[str] = set()
    for from_key, to_key, _rule, _note in PAIRS:
        for key in (from_key, to_key):
            assert key not in seen, f"{key} appears in more than one pair"
            seen.add(key)
