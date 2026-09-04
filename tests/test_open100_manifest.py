"""A stage 2 párosítás önellenőrzése: nem függ a PID2Graph fájloktól.

A build_manifest bemenete geometriai megfigyelések (ConnectorObservation), a
kimenete pedig a PAIRS/ANNOTATIONS táblák alapján épített manifest. Itt a
geometriát kitaláljuk (egy közös helyőrző dobozzal) — csak az számít, hogy a
kulcsok (sheet:node_id) megegyezzenek az annotations.py-ban szereplőkkel. Így
ez a teszt azt őrzi, hogy a PAIRS és az ANNOTATIONS táblák önmagukban
konzisztensek maradnak, anélkül hogy a valódi rajzokra lenne szükség.
"""

from __future__ import annotations

from plantgraph.benchmark.models import BoundingBox, ConnectorObservation, Side
from plantgraph.benchmark.open100.annotations import ANNOTATIONS
from plantgraph.benchmark.open100.manifest import PAIRS, build_manifest

_PLACEHOLDER_BOX = BoundingBox(xmin=0.0, ymin=0.0, xmax=10.0, ymax=10.0)


def _fake_observations() -> list[ConnectorObservation]:
    """Egy megfigyelés minden annotált csatlakozóhoz — a geometria itt lényegtelen."""
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
    # Ha egy kulcs párban ÉS lógóként/megoldatlanként is szerepelne, az azt
    # jelentené, hogy a PAIRS és a _classify szabály egymásnak ellentmond.
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
    # Elgépelt kulcs a PAIRS táblában csendben "elveszne" — inkább bukjon el itt.
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
