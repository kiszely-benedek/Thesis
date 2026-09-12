"""Szintetikus üzemgráfokat épít a splitter tesztjeihez.

A pyDEXPI-adapter (ADR-0003) még nem létezik, ezért ezek a fixture-ök
networkx-szel közvetlenül épülnek fel — a splitter csak azt várja el a
bemenettől, hogy minden csomópontján legyen 'node_class' és 'tag' attribútum
(lásd splitter.md 2. fejezet, "In"). Nincs "test_" előtagja, ezért a pytest nem
gyűjti be tesztként.

A berendezés-csomópontok kapnak egy 'manufacturer' attribútumot is, amit a
splitter sosem másol át a reference-előfordulásokra — ez adja a fogódzót
annak teszteléséhez, hogy a duplikált csomópont valóban csak a tag-et és
kevés mást hordoz (lásd test_identity_groups.py).
"""

from __future__ import annotations

import networkx as nx

EQUIPMENT_CLASSES = ("pump", "exchanger", "column", "tank")


def make_plant_graph(
    chain_length: int = 4, branches: int = 2, utility_fanout: int = 4
) -> nx.DiGraph:
    """Egy hihető üzemgráf: feed, berendezés-láncok, utility fejvezeték és a rájuk kötött műszerek.

    Az utility fejvezeték szándékosan magas fokszámú — sok berendezéshez kapcsolódik,
    ahogy egy gőz- vagy hűtővízhálózat is tenné (lásd utility_aware a strategies.py-ban).

    Args:
        chain_length: hány berendezés van egy technológiai láncban a feedtől lefelé.
        branches: hány párhuzamos technológiai lánc induljon a feedből.
        utility_fanout: hány berendezéshez kapcsolódjon az utility fejvezeték.
    """
    plant = nx.DiGraph()
    feed = "feed-1"
    plant.add_node(feed, node_class="vessel", tag="V-100", manufacturer="Acme")

    utility = "utility-steam"
    plant.add_node(utility, node_class="utility_header", tag="STM-HDR-1")

    all_equipment = [feed]
    for branch in range(branches):
        all_equipment += _add_chain(plant, feed, branch, chain_length)

    for node_id in all_equipment[:utility_fanout]:
        plant.add_edge(utility, node_id, service="steam")

    return plant


def _add_chain(plant: nx.DiGraph, feed: str, branch: int, chain_length: int) -> list[str]:
    """Egy technológiai láncot fűz a feedtől lefelé, minden állomáshoz egy-egy műszerrel."""
    equipment_ids: list[str] = []
    upstream = feed
    for step in range(chain_length):
        node_class = EQUIPMENT_CLASSES[step % len(EQUIPMENT_CLASSES)]
        node_id = f"eq-{branch}-{step}"
        tag = f"{node_class[0].upper()}-{branch}{step}"
        plant.add_node(node_id, node_class=node_class, tag=tag, manufacturer="Acme")
        plant.add_edge(upstream, node_id, service="process")
        _attach_instrument(plant, node_id, branch, step)
        equipment_ids.append(node_id)
        upstream = node_id
    return equipment_ids


def _attach_instrument(plant: nx.DiGraph, equipment_id: str, branch: int, step: int) -> None:
    """Egy műszert köt egy berendezésre.

    Sosem számít a lapkeretbe, csak a berendezésével kell utaznia.
    """
    instrument_id = f"inst-{branch}-{step}"
    plant.add_node(instrument_id, node_class="instrument", tag=f"FT-{branch}{step}")
    plant.add_edge(equipment_id, instrument_id, service="signal")
