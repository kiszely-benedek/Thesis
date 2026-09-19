"""Teszt-only `PlantBuilder`: a generátor topológia-döntéseiből séma szerinti `nx.DiGraph`-ot épít.

Ez az oracle, amihez a majdani pyDEXPI-adapter kimenetét kell hasonlítani —
nem egy második éles útvonal (`plant-generator.md`, "Offline split of step 3",
"New invariant for step 3a": "The test-only builder is an oracle, not a
second production path"). Ezért szándékosan a lehető legegyszerűbb: minden
`PlantBuilder`-hívás közvetlenül egy-egy networkx csomópontot/élt ad hozzá,
a `graph.schema`-ban rögzített tulajdonságokkal.

Nincs "test_" előtagja, ezért a pytest nem gyűjti be tesztként — ugyanúgy,
ahogy `plant_fixtures.py` sem.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import networkx as nx

from plantgraph.benchmark.generator_models import DataValue, LoopSpec, ValveSpec
from plantgraph.graph.schema import Relation


class GraphPlantBuilder:
    """A `PlantBuilder` Protocol séma-hű, csak tesztekhez való implementációja."""

    backend_version = "graph-test-builder"

    def __init__(self, plant_id: str) -> None:
        self.plant_id = plant_id
        self.graph: nx.DiGraph[str] = nx.DiGraph()

    def add_section(self, unit_no: int) -> None:
        """Nincs teendő: a `PlantSection` a struktúra-rétegben él, itt nem csomópont (§4.1)."""
        return None

    def add_equipment(
        self,
        node_id: str,
        node_class: str,
        unit_no: int,
        tag: str,
        tag_prefix: str,
        tag_seq: int,
        data: Mapping[str, DataValue],
    ) -> None:
        """Felvesz egy berendezés-csomópontot; a `data` üres (equipment_data még nem aktív)."""
        self.graph.add_node(
            node_id, node_class=node_class, tag=tag, plant_id=self.plant_id, unit_id=str(unit_no)
        )

    def add_stream(
        self,
        line_number: str,
        fluid_code: str,
        src_id: str,
        dst_id: str,
        valves: Sequence[ValveSpec],
    ) -> None:
        """Berajzolja a csővezetéket: `src -> v1 -> ... -> vn -> dst`, `send_to` éleken."""
        # a szelep a forrás egységéhez tartozik (§3.3 lépés 4); a forrás már fel
        # van véve add_equipment-tel, tehát az unit_id attribútuma innen olvasható
        unit_id = self.graph.nodes[src_id]["unit_id"]
        chain = [src_id]
        for valve in valves:
            self.graph.add_node(
                valve.node_id,
                node_class=valve.node_class,
                tag=valve.tag,
                plant_id=self.plant_id,
                unit_id=unit_id,
            )
            chain.append(valve.node_id)
        chain.append(dst_id)

        # chain[1:] szándékosan eggyel rövidebb: ez adja az egymást követő párokat
        for upstream, downstream in zip(chain, chain[1:], strict=False):
            self.graph.add_edge(
                upstream,
                downstream,
                relation=Relation.SEND_TO.value,
                line_number=line_number,
                fluid_code=fluid_code,
            )

    def add_control_loop(self, loop: LoopSpec) -> None:
        """Berajzolja a kört: equipment -measured_by-> PSGF -> PIF -> AF -control-> valve (§4.3)."""
        unit_id = self.graph.nodes[loop.equipment_id]["unit_id"]
        pif_tag = f"{loop.variable}IC-{loop.unit_no}-{loop.loop_no}"

        self._add_instrument_node(
            loop.psgf_id,
            "ProcessSignalGeneratingFunction",
            f"{loop.variable}T-{loop.unit_no}-{loop.loop_no}",
            unit_id,
            loop.variable,
            pif_tag,
        )
        self._add_instrument_node(
            loop.pif_id, "ProcessInstrumentationFunction", pif_tag, unit_id, loop.variable, pif_tag
        )
        self._add_instrument_node(
            loop.af_id,
            "ActuatingFunction",
            f"{loop.variable}V-{loop.unit_no}-{loop.loop_no}",
            unit_id,
            loop.variable,
            pif_tag,
        )

        self.graph.add_edge(loop.equipment_id, loop.psgf_id, relation=Relation.MEASURED_BY.value)
        self.graph.add_edge(loop.psgf_id, loop.pif_id, relation=Relation.SEND_SIGNAL_TO.value)
        self.graph.add_edge(loop.pif_id, loop.af_id, relation=Relation.SEND_SIGNAL_TO.value)
        self.graph.add_edge(loop.af_id, loop.valve_id, relation=Relation.CONTROL.value)

    def _add_instrument_node(
        self,
        node_id: str,
        node_class: str,
        tag: str,
        unit_id: str,
        variable: str,
        loop_tag: str,
    ) -> None:
        """Egy műszer-csomópontot vesz fel; `loop_tag` mindig a PIF saját tag-je (§3.6)."""
        self.graph.add_node(
            node_id,
            node_class=node_class,
            tag=tag,
            plant_id=self.plant_id,
            unit_id=unit_id,
            loop_tag=loop_tag,
            measured_variable=variable,
        )
