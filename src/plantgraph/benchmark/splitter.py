"""A szintetikus benchmark-generátor: egy üzemgráfot lapokra vág, és megoldókulcsot ad hozzá.

Az orchestrálás négy lépésből áll (splitter.md 2. fejezet):

  1. particionálás — melyik csomópont melyik lapra kerül (strategies.py),
  2. lapok kivágása — az egy laphoz tartozó csomópontok/élek gráffá alakítása,
  3. **azonosság-alapú** kereszthivatkozás: néhány berendezést több lapra is
     felrajzolunk (splitter.md nyitott 3. kérdés),
  4. **off-page connector**: a fennmaradó lapok közötti éleket két csonk-
     csomóponttal helyettesítjük, és felírjuk a párjukat a megoldókulcsba
     (connectors.py — saját modul, mert a splitter.py e nélkül túllépné a
     400 soros fájlkorlátot).

Ez a modul csak a gráfot alakítja; képet nem rajzol (splitter.md 1. fejezet).
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

import networkx as nx

from plantgraph.benchmark import connectors
from plantgraph.benchmark.models import IdentityGroup, SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.strategies import STRATEGIES, StrategyFn


def split(plant: nx.DiGraph[str], config: SplitConfig) -> tuple[list[SheetGraph], SplitManifest]:
    """Egy teljes üzemgráfot lapokra vág, és előállítja a hozzá tartozó megoldókulcsot.

    Minden véletlen döntés egyetlen, config.seed-ből magozott
    random.Random-on megy át — a globális random modult sosem érinti, hogy a
    "same seed -> byte-identical manifest" ígéret tartható legyen.
    """
    _validate_has_equipment(plant, config.equipment_classes)
    rng = random.Random(config.seed)

    node_sheet = _strategy(config.strategy)(plant, config, rng)
    sheets = _induce_sheets(plant, node_sheet)
    identity_groups, resolved_edges = _duplicate_equipment(plant, sheets, node_sheet, config, rng)
    connector_pairs = connectors.cut_remaining_edges(
        plant, sheets, node_sheet, resolved_edges, config, rng
    )

    all_connectors = [connector for sheet in sheets.values() for connector in sheet.connectors]
    manifest = SplitManifest(
        source="synthetic",
        sheet_files=sorted(sheets),
        strategy=config.strategy,
        seed=config.seed,
        source_graph_hash=_hash_graph(plant),
        connector_pairs=connector_pairs,
        off_page_connectors=all_connectors,
        identity_groups=identity_groups,
    )
    return [sheets[sheet_id] for sheet_id in sorted(sheets)], manifest


def _strategy(name: str) -> StrategyFn:
    try:
        return STRATEGIES[name]
    except KeyError:
        known = sorted(STRATEGIES)
        raise ValueError(f"unknown split strategy {name!r}; choose one of {known}") from None


def _validate_has_equipment(plant: nx.DiGraph[str], equipment_classes: set[str]) -> None:
    has_equipment = any(
        attrs.get("node_class") in equipment_classes for _, attrs in plant.nodes(data=True)
    )
    if not has_equipment:
        raise ValueError(
            f"plant graph has no node with node_class in {sorted(equipment_classes)}; "
            "the splitter needs at least one equipment node to anchor the sheet budget"
        )


def _hash_graph(plant: nx.DiGraph[str]) -> str:
    """A gráf stabil ujjlenyomata — ez teszi reprodukálhatóvá a benchmark-példányt."""
    nodes = sorted((node_id, sorted(attrs.items())) for node_id, attrs in plant.nodes(data=True))
    edges = sorted(
        (source, target, sorted(attrs.items())) for source, target, attrs in plant.edges(data=True)
    )
    canonical = repr((nodes, edges)).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _induce_sheets(plant: nx.DiGraph[str], node_sheet: dict[str, str]) -> dict[str, SheetGraph]:
    """Minden csomópontot és lapon belüli élt a saját lapja gráfjába másol.

    A lapok közötti éleket még érintetlenül hagyja — azokat a hívó kezeli.
    """
    sheets = {
        sheet_id: SheetGraph(sheet_id=sheet_id, graph=nx.DiGraph())
        for sheet_id in sorted(set(node_sheet.values()))
    }
    for node_id, attrs in plant.nodes(data=True):
        sheets[node_sheet[node_id]].graph.add_node(node_id, **attrs)
    for source, target, attrs in plant.edges(data=True):
        if node_sheet[source] == node_sheet[target]:
            sheets[node_sheet[source]].graph.add_edge(source, target, **attrs)
    return sheets


def _duplicate_equipment(
    plant: nx.DiGraph[str],
    sheets: dict[str, SheetGraph],
    node_sheet: dict[str, str],
    config: SplitConfig,
    rng: random.Random,
) -> tuple[list[IdentityGroup], set[tuple[str, str]]]:
    """Kiválaszt egy duplication_rate hányadot a lapok közti szomszédú berendezésekből.

    Ez az **azonosság-alapú** kereszthivatkozás (splitter.md nyitott 3.
    kérdés): a kiválasztott berendezéseket felrajzoljuk minden olyan lapra,
    ahol van szomszédjuk — egy home előfordulás teljes attribútumokkal, és
    egy-egy reference előfordulás a tag-gel és kevés mással. Az itt feloldott
    éleket a hívó már nem vágja el off-page connectorral.
    """
    candidates = sorted(
        _equipment_with_cross_sheet_neighbours(plant, node_sheet, config.equipment_classes)
    )
    chosen_count = round(len(candidates) * config.duplication_rate)
    chosen = rng.sample(candidates, chosen_count) if chosen_count else []

    groups: list[IdentityGroup] = []
    resolved_edges: set[tuple[str, str]] = set()
    for node_id in sorted(chosen):
        group, edges = _draw_on_neighbour_sheets(plant, sheets, node_sheet, node_id, config, rng)
        groups.append(group)
        resolved_edges |= edges
    return groups, resolved_edges


def _equipment_with_cross_sheet_neighbours(
    plant: nx.DiGraph[str], node_sheet: dict[str, str], equipment_classes: set[str]
) -> list[str]:
    """Azok a berendezések, amelyeknek van másik lapra eső szomszédja.

    Csak ezek jöhetnek szóba duplikálásra.
    """
    result: list[str] = []
    for node_id, attrs in plant.nodes(data=True):
        if attrs.get("node_class") not in equipment_classes:
            continue
        home_sheet = node_sheet[node_id]
        neighbours = set(plant.predecessors(node_id)) | set(plant.successors(node_id))
        if any(node_sheet[neighbour] != home_sheet for neighbour in neighbours):
            result.append(node_id)
    return result


def _draw_on_neighbour_sheets(
    plant: nx.DiGraph[str],
    sheets: dict[str, SheetGraph],
    node_sheet: dict[str, str],
    node_id: str,
    config: SplitConfig,
    rng: random.Random,
) -> tuple[IdentityGroup, set[tuple[str, str]]]:
    """Egy kiválasztott berendezést felrajzol minden szomszédos lapjára.

    A helyi éleket a másolathoz köti azon a lapon, ahol felrajzoltuk.
    """
    home_sheet = node_sheet[node_id]
    home_attrs = plant.nodes[node_id]
    tag = str(home_attrs.get("tag", node_id))
    neighbours = set(plant.predecessors(node_id)) | set(plant.successors(node_id))
    other_sheets = sorted(
        {node_sheet[neighbour] for neighbour in neighbours if node_sheet[neighbour] != home_sheet}
    )

    references: list[str] = []
    tag_variants: dict[str, str] = {}
    resolved_edges: set[tuple[str, str]] = set()
    for sheet_id in other_sheets:
        reference_tag = tag if config.exact_match_tags else _tag_variant(tag, rng)
        sheets[sheet_id].graph.add_node(
            node_id, tag=reference_tag, node_class=home_attrs.get("node_class")
        )
        reference_key = f"{sheet_id}:{node_id}"
        references.append(reference_key)
        if reference_tag != tag:
            tag_variants[reference_key] = reference_tag
        resolved_edges |= _wire_local_edges(plant, sheets[sheet_id], node_id, sheet_id, node_sheet)

    group = IdentityGroup(
        tag=tag, home=f"{home_sheet}:{node_id}", references=references, tag_variants=tag_variants
    )
    return group, resolved_edges


def _wire_local_edges(
    plant: nx.DiGraph[str],
    sheet: SheetGraph,
    node_id: str,
    sheet_id: str,
    node_sheet: dict[str, str],
) -> set[tuple[str, str]]:
    """A duplikált csomópont azon éleit köti be, amelyek másik végpontja is ezen a lapon lakik."""
    resolved: set[tuple[str, str]] = set()
    for _, target, attrs in plant.out_edges(node_id, data=True):
        if node_sheet[target] == sheet_id:
            sheet.graph.add_edge(node_id, target, **attrs)
            resolved.add((node_id, target))
    for source, _, attrs in plant.in_edges(node_id, data=True):
        if node_sheet[source] == sheet_id:
            sheet.graph.add_edge(source, node_id, **attrs)
            resolved.add((source, node_id))
    return resolved


def _tag_variant(tag: str, rng: random.Random) -> str:
    """Elüti a tagot a home-előfordulástól, hogy a benchmark ne legyen triviálisan összeilleszthető.

    Az OPEN100-on ugyanaz a szivattyú RC-P102A és RCS-PU-102A alakban is
    szerepel — ezt utánozzuk néhány egyszerű, de nem szabályos átalakítással.
    """
    mutations: list[Any] = [
        lambda t: t.replace("-", ""),  # RC-P102A -> RCP102A
        lambda t: t.replace("-", "-0", 1),  # RC-P102A -> RC-0P102A
        lambda t: t.lower(),  # RC-P102A -> rc-p102a
    ]
    return str(rng.choice(mutations)(tag))
