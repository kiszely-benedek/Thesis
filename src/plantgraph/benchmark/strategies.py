"""Négy particionáló stratégia: hogyan vágjuk lapokra az üzemgráfot.

Mindegyik ugyanazt a szerződést teljesíti: kap egy teljes üzemgráfot, egy
SplitConfig-ot és egy magszámmal ellátott véletlengenerátort, visszaad egy
csomópont -> lapazonosító hozzárendelést. **Egyik sem vágja el az éleket** — azt
a splitter.py végzi a partíció alapján (splitter.md 2. fejezet).

Közös lépés mind a négyben: a lapkeret csak a "berendezést" számolja (szelep,
műszer, csővezeték-jelölő ingyen utazik — splitter.md nyitott 2. kérdés), ezért
előbb minden csomópontot a legközelebbi berendezéshez rendelünk (klaszter),
és a stratégiák a klaszterek szintjén döntenek. A négy stratégia csak abban
tér el, MILYEN SORRENDBEN engedi a klasztereket egy lapra: a lapokra tördelés
maga (_chunk_by_budget) közös kód.
"""

from __future__ import annotations

import random
import statistics
from collections import deque
from collections.abc import Callable

import networkx as nx

from plantgraph.benchmark.split_models import SplitConfig

# idézőjeles forward reference: nx.DiGraph valódi futásidőben nem indexelhető
# (a [str] csak a type stubban létezik), ezért itt nem szabad kiértékelni
StrategyFn = Callable[["nx.DiGraph[str]", SplitConfig, random.Random], dict[str, str]]


def flow_greedy(plant: nx.DiGraph[str], config: SplitConfig, rng: random.Random) -> dict[str, str]:
    """Az alapértelmezett stratégia: a feed-berendezésekből lefelé haladva tölti meg a lapokat.

    Ez utánozza, ahogyan egy tervező ténylegesen dolgozik (splitter.md 3.
    fejezet): a lapsorrend a folyamatirányt követi, ezért a legtöbb
    kereszthivatkozás a szomszédos lapszámra mutat.
    """
    equipment_owners, node_owner = _cluster_owners(plant, config.equipment_classes)
    owner_graph = _owner_graph(plant, node_owner)
    order = _flow_order(owner_graph, equipment_owners)
    owner_sheets = _chunk_by_budget(order, equipment_owners, config.sheet_equipment_budget)
    return _expand_to_nodes(owner_sheets, node_owner)


def modularity(plant: nx.DiGraph[str], config: SplitConfig, rng: random.Random) -> dict[str, str]:
    """Louvain-közösségeket keres a berendezés-gráfon, és a talált csoportokat tördeli lapokra.

    Ez a "technológiai egység szerinti particionálás" modellje: egy oszlop a
    forralójával, kondenzátorával és szivattyúival általában egy közösségbe esik.
    """
    equipment_owners, node_owner = _cluster_owners(plant, config.equipment_classes)
    owner_graph = _owner_graph(plant, node_owner)
    undirected = owner_graph.to_undirected()
    communities = nx.community.louvain_communities(undirected, seed=rng.randint(0, 2**31 - 1))
    # a sorted(...) a benne lévő szettek/listák belső sorrendjétől független,
    # determinisztikus bejárási sorrendet ad — enélkül a "same seed -> same
    # manifest" teszt időnként hibázna (lásd a modul docstringjét is)
    ordered_communities = sorted(sorted(community) for community in communities)
    order = [owner for community in ordered_communities for owner in community]
    owner_sheets = _chunk_by_budget(order, equipment_owners, config.sheet_equipment_budget)
    return _expand_to_nodes(owner_sheets, node_owner)


def by_unit(plant: nx.DiGraph[str], config: SplitConfig, rng: random.Random) -> dict[str, str]:
    """A deklarált technológiai egység (unit_id) szerint particionál, nem gráf-közösség szerint.

    A modularity ebből a szerkezetből *sejt* valamit a gráf topológiájából
    (Louvain-közösségek); a by_unit a generátor által már deklarált
    plant->unit hierarchiát követi közvetlenül (N6, `plant-generator.md` §5
    finding 3) — egy sheet sosem vegyít két egységet.

    Raises:
        ValueError: ha egyetlen berendezésnek sincs unit_id attribútuma.
    """
    equipment_owners, node_owner = _cluster_owners(plant, config.equipment_classes)
    owner_graph = _owner_graph(plant, node_owner)
    order = _flow_order(owner_graph, equipment_owners)
    unit_of = {owner: str(plant.nodes[owner].get("unit_id", "")) for owner in order}

    if not any(unit_of[owner] for owner in equipment_owners):
        raise ValueError("by_unit needs unit_id on equipment nodes")

    owner_sheets: list[list[str]] = []
    for unit_id in _units_in_flow_order(order, unit_of):
        owners_in_unit = [owner for owner in order if unit_of[owner] == unit_id]
        owner_sheets += _chunk_by_budget(
            owners_in_unit, equipment_owners, config.sheet_equipment_budget
        )
    return _expand_to_nodes(owner_sheets, node_owner)


def _units_in_flow_order(order: list[str], unit_of: dict[str, str]) -> list[str]:
    """Az egységeket az első bennük szereplő owner flow-sorrendi pozíciója szerint sorolja fel."""
    seen: list[str] = []
    for owner in order:
        unit_id = unit_of[owner]
        if unit_id not in seen:
            seen.append(unit_id)
    return seen


def utility_aware(
    plant: nx.DiGraph[str], config: SplitConfig, rng: random.Random
) -> dict[str, str]:
    """Előbb a magas fokszámú (utility-jellegű) berendezéseket teszi hub-lapokra.

    Utána flow_greedy fut a maradékon.

    A gőz-, hűtővíz- és műszerlevegő-fejvezetékek sok rendszerhez kapcsolódnak
    (splitter.md 3. fejezet, "hub sheets"); ez a stratégia ezt a szerkezetet adja hozzá.

    Megjegyzés: a kísérletekben egyelőre nem használjuk, amíg a generátor nem
    termel utility-t (`plant-generator.md` §5) — enélkül a "hub" csak egy
    magas fokszámú folyamat-berendezés lenne, nem valódi fejvezeték.
    """
    equipment_owners, node_owner = _cluster_owners(plant, config.equipment_classes)
    owner_graph = _owner_graph(plant, node_owner)
    hub_owners = _detect_hubs(owner_graph, equipment_owners)

    hub_order = sorted(hub_owners)
    hub_sheets = _chunk_by_budget(hub_order, equipment_owners, config.sheet_equipment_budget)

    rest_graph = owner_graph.copy()
    rest_graph.remove_nodes_from(hub_owners)
    rest_equipment = equipment_owners - hub_owners
    rest_order = _flow_order(rest_graph, rest_equipment)
    rest_sheets = _chunk_by_budget(rest_order, rest_equipment, config.sheet_equipment_budget)

    return _expand_to_nodes(hub_sheets + rest_sheets, node_owner)


def random_partition(
    plant: nx.DiGraph[str], config: SplitConfig, rng: random.Random
) -> dict[str, str]:
    """Kontroll-stratégia: berendezéseket véletlen sorrendben, technológiától függetlenül osztja el.

    Szándékosan valószerűtlen (splitter.md 3. fejezet): ha ez ugyanolyan
    visszakeresési pontosságot ad, mint flow_greedy, az önmagában eredmény —
    azt jelenti, hogy a benchmark nem érzékeny a particionálás realizmusára.
    """
    equipment_owners, node_owner = _cluster_owners(plant, config.equipment_classes)
    order = sorted(set(node_owner.values()))
    rng.shuffle(order)
    owner_sheets = _chunk_by_budget(order, equipment_owners, config.sheet_equipment_budget)
    return _expand_to_nodes(owner_sheets, node_owner)


STRATEGIES: dict[str, StrategyFn] = {
    "flow_greedy": flow_greedy,
    "modularity": modularity,
    "by_unit": by_unit,
    "utility_aware": utility_aware,
    "random": random_partition,
}


def _cluster_owners(
    plant: nx.DiGraph[str], equipment_classes: set[str]
) -> tuple[set[str], dict[str, str]]:
    """Minden csomópontot a legközelebbi berendezéshez rendel.

    A rárakódott műszerek így a berendezésükkel utaznak egy lapra.

    A node_class attribútum dönti el, mi számít berendezésnek (SplitConfig
    paraméter, nem beégetett pyDEXPI-osztálylista — lásd splitter.md 2. nyitott
    kérdés). Ha egy csomóponthoz egyáltalán nem ér el berendezés (elszigetelt
    műszer-alhálózat), önmaga lesz a saját klasztere; ritka eset, és nem számít
    bele a lapkeretbe, mert nem berendezés.
    """
    equipment_owners = {
        node_id
        for node_id, attrs in plant.nodes(data=True)
        if attrs.get("node_class") in equipment_classes
    }
    owner: dict[str, str] = {
        equipment_id: equipment_id for equipment_id in sorted(equipment_owners)
    }

    undirected = plant.to_undirected(as_view=True)
    queue: deque[str] = deque(sorted(equipment_owners))
    while queue:
        node_id = queue.popleft()
        for neighbour in sorted(undirected.neighbors(node_id)):
            if neighbour in owner:
                continue
            owner[neighbour] = owner[node_id]
            queue.append(neighbour)

    for node_id in sorted(plant.nodes):
        if node_id not in owner:
            owner[node_id] = node_id

    return equipment_owners, owner


def _owner_graph(plant: nx.DiGraph[str], node_owner: dict[str, str]) -> nx.DiGraph[str]:
    """A klaszterek közötti éleket ábrázoló, összevont gráf — ezen dönt minden stratégia."""
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_nodes_from(sorted(set(node_owner.values())))
    for source, target in plant.edges():
        owner_source, owner_target = node_owner[source], node_owner[target]
        if owner_source != owner_target:
            graph.add_edge(owner_source, owner_target)
    return graph


def _flow_order(owner_graph: nx.DiGraph[str], equipment_owners: set[str]) -> list[str]:
    """Depth-first preorder walk from the feed equipment (zero in-degree) downstream.

    Depth-first, not breadth-first (ADR-0017): a breadth-first walk visits one
    step of every chain before the second step of any of them, so under a
    fixed sheet budget the two ends of an edge end up dozens of chains apart —
    nearly every inter-cluster edge gets cut. Depth-first walks one chain to
    its end before starting the next, so a chain mostly stays on one sheet.
    """
    feeds = sorted(owner for owner in equipment_owners if owner_graph.in_degree(owner) == 0)
    if not feeds and owner_graph.number_of_nodes() > 0:
        # a cyclic graph has no true feed (zero in-degree node) —
        # deterministic fallback so the walk still starts somewhere
        feeds = [sorted(owner_graph.nodes)[0]]

    order: list[str] = []
    visited: set[str] = set()
    # a stack, not a queue: LIFO order gives depth-first rather than breadth-first
    stack: list[str] = list(reversed(feeds))
    while len(visited) < owner_graph.number_of_nodes():
        if not stack:
            remaining = sorted(set(owner_graph.nodes) - visited)
            stack.append(remaining[0])
        node_id = stack.pop()
        if node_id in visited:
            continue
        visited.add(node_id)
        order.append(node_id)
        # reversed so sorted() order comes off the stack first (smallest successor next)
        stack.extend(sorted(owner_graph.successors(node_id), reverse=True))
    return order


def _detect_hubs(owner_graph: nx.DiGraph[str], equipment_owners: set[str]) -> set[str]:
    """A fokszám-eloszlásból számolja ki, mely berendezések számítanak utility-hubnak.

    Szándékosan nincs külön beállítás a küszöbre: az OPEN100-on megfigyelt
    mintázat (splitter.md 3. fejezet) gráfonként más fokszámnál jelentkezne,
    ezért az átlag + szórás fölötti kiugrókat vesszük hubnak, nem egy konstanst.
    """
    if len(equipment_owners) < 2:
        return set()
    degrees = {owner: owner_graph.degree(owner) for owner in equipment_owners}
    mean = statistics.mean(degrees.values())
    spread = statistics.pstdev(degrees.values())
    threshold = mean + spread
    return {owner for owner, degree in degrees.items() if degree > threshold and degree > 0}


def _chunk_by_budget(order: list[str], equipment_owners: set[str], budget: int) -> list[list[str]]:
    """Egy sorrendbe rendezett klaszterlistát tördel lapokra.

    Csak a berendezés-klaszterek számítanak a keretbe.
    """
    sheets: list[list[str]] = [[]]
    equipment_count = 0
    for owner in order:
        is_equipment = owner in equipment_owners
        if is_equipment and equipment_count >= budget and sheets[-1]:
            sheets.append([])
            equipment_count = 0
        sheets[-1].append(owner)
        if is_equipment:
            equipment_count += 1
    return sheets


def _expand_to_nodes(owner_sheets: list[list[str]], node_owner: dict[str, str]) -> dict[str, str]:
    """Az owner -> lap hozzárendelést kiterjeszti minden csomópontra a klasztertagság alapján."""
    owner_sheet_id = {
        owner: str(index) for index, owners in enumerate(owner_sheets) for owner in owners
    }
    return {node_id: owner_sheet_id[owner] for node_id, owner in node_owner.items()}
