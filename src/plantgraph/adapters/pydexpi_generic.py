"""A séma-ismeretlen pyDEXPI osztályok generikus fallback-ja (ADR-0016, `kg-construction.md` §3.1).

Egy valódi rajz jóval több pyDEXPI-osztályt használ, mint amennyit a séma
(`graph.schema`) curated (a generátor és a splitter által ismert 12+4 osztály)
— pl. `PipeTee`, `BlindFlange`, egy dugattyús szivattyú (`ReciprocatingPump`).
A `pydexpi_adapter.py` ezeket eddig némán eldobta (`kg-construction.md` §2).
ADR-0016 döntése szerint egyik sem veszhet el: egy ismeretlen osztály a
`GenericItem` node_class-t kapja, a pyDEXPI-osztálynevét (`dexpi_class`) és egy
curated ős-lánc-előtagot (`dexpi_labels`) megőrizve rendes csomópont-
tulajdonságként.

Ez a modul azért él külön a `pydexpi_adapter.py`-tól, nem mert fogalmilag más
réteg volna, hanem mert az már a 400 soros fájlkorlátnál van (§3.1 "Where the
code lives") — pontosan az a helyzet, mint `graph/schema.py` és
`graph/validation.py` között.
"""

from __future__ import annotations

import collections
import re
from collections.abc import Iterable, Mapping

import networkx as nx
import pydexpi.dexpi_classes.pydantic_classes as pydexpi_classes
import pydexpi.toolkits.base_model_utils as base_model_utils
from pydantic import BaseModel

# `_relation_of` privát, de ez a modul csak a 400 soros korlát miatt vált külön a
# pydexpi_adapter.py-tól (lásd a modul docstringjét) — egy adapter-család két fájlja.
# Enélkül a related_to-átalakításnak (rule 5) újra kellene fejtenie az irány-megfordítás
# szabályát (pl. `measured_by` a "reference"/"sensingLocation" élt megfordítja), és tévesen
# "elveszettnek" látná az így már helyesen leképezett éleket.
from plantgraph.adapters.pydexpi_adapter import _relation_of, topology_node_class
from plantgraph.graph import schema

#: a `_map_nodes` szándékosan struktúra-rétegbe foglalja ezeket (`pydexpi_adapter.py`
#: docstringje) — sosem generikus csomópont, még ha a séma nem is ismeri fel őket
_STRUCTURE_LABELS = frozenset({"PlantSection", "ProcessPlant"})

#: pyDEXPI ős-osztálynév -> séma-kategória, amit "gyökérnek" tekintünk (§3.1 "Label cut-off").
#: A gyökér utáni pyDEXPI-lánc mixin-osztályokba fut (`CustomAttributeOwner`, ...), amik nem
#: kategóriák — ezért áll meg a bejárás itt, nem a lánc végén.
_CATEGORY_ROOTS: dict[str, schema.NodeCategory] = {
    "Equipment": schema.NodeCategory.EQUIPMENT,
    "PipingComponent": schema.NodeCategory.PIPING,
}

#: biztonságos Neo4j-címke alak — mind a curated lánc, mind a fallback egy elemű lánca
#: ez ellen ellenőrződik, mielőtt a store (T6) egyáltalán megkapná (§3.1 rule 7)
_LABEL_PATTERN = re.compile(r"^[A-Z][A-Za-z0-9]*$")


class GenericInfo(BaseModel):
    """Amit egy `GenericItem`-mé fordított csomópont megőriz a valódi pyDEXPI-azonosságából."""

    dexpi_class: str
    category: schema.NodeCategory
    labels: tuple[str, ...]


def classify(label: str) -> GenericInfo:
    """Egy pyDEXPI osztálynevet kategóriává és Neo4j-címkeláncra bont (§3.1 rule 2).

    A pyDEXPI saját ős-láncán sétál a legelső kategória-gyökérig (`Equipment` vagy
    `PipingComponent`), azt is beleértve. Gyökér nélkül, vagy ha `label` nem is
    pyDEXPI-osztály neve, a kategória `other`, és a lánc csak önmaga.

    Raises:
        ValueError: ha egy címkelánc-elem nem biztonságos Neo4j-címke alak.
    """
    dexpi_class = getattr(pydexpi_classes, label, None)
    if dexpi_class is None:
        return GenericInfo(
            dexpi_class=label, category=schema.NodeCategory.OTHER, labels=_checked((label,))
        )
    chain: list[str] = []
    for ancestor in base_model_utils.get_inheritance_from_dexpi_class(dexpi_class):
        chain.append(ancestor.__name__)
        category = _CATEGORY_ROOTS.get(ancestor.__name__)
        if category is not None:
            return GenericInfo(dexpi_class=label, category=category, labels=_checked(tuple(chain)))
    return GenericInfo(
        dexpi_class=label, category=schema.NodeCategory.OTHER, labels=_checked((label,))
    )


def _checked(labels: tuple[str, ...]) -> tuple[str, ...]:
    """Minden láncelemet a Neo4j-címke alakhoz köt — a store (T6) erre épít, injekció nélkül."""
    for label in labels:
        if not _LABEL_PATTERN.match(label):
            raise ValueError(
                f"{label!r} is not a safe Neo4j label (expected {_LABEL_PATTERN.pattern})"
            )
    return labels


def prepare_generic(
    conceptual: nx.MultiDiGraph[str],
) -> tuple[nx.MultiDiGraph[str], dict[str, GenericInfo]]:
    """Egy másolaton minden eldobandó csomópontot `GenericItem`-re címkéz át (§3.1 rule 1).

    A séma-ismeretlen osztályok így már ismert osztályként (`GenericItem` a
    `schema.IMPORTABLE_CLASSES`-ben van) érik el `map_conceptual_graph`-ot, ahelyett
    hogy az eldobná őket. A struktúra-osztályokat (`PlantSection`, `ProcessPlant`)
    szándékosan érintetlenül hagyja — azokat az adapter másképp dolgozza fel.
    """
    prepared = conceptual.copy()
    infos: dict[str, GenericInfo] = {}
    for node_id, attrs in conceptual.nodes(data=True):
        label = str(attrs.get("label"))
        if label in _STRUCTURE_LABELS or topology_node_class(label) is not None:
            continue
        infos[node_id] = classify(label)
        prepared.nodes[node_id]["label"] = schema.NodeClass.GENERIC_ITEM.value
    return prepared, infos


def annotate_generic(
    plant: nx.DiGraph[str], infos: Mapping[str, GenericInfo], conceptual: nx.MultiDiGraph[str]
) -> None:
    """Ráírja a `dexpi_class`/`category`/`dexpi_labels`-t és a tag-et minden generikus node-ra.

    A `map_conceptual_graph` és a `proteusId`-ra való átnevezés között fut (§3.1 rule 4),
    amíg a csomópont-id-k még megegyeznek `infos` és `conceptual` kulcsaival.
    """
    for node_id, info in infos.items():
        if node_id not in plant.nodes:
            continue  # nem ez a fallback dobta el — más okból esett ki (pl. jövőbeli szabály)
        attrs = plant.nodes[node_id]
        attrs["dexpi_class"] = info.dexpi_class
        attrs["category"] = info.category.value
        attrs["dexpi_labels"] = list(info.labels)
        attrs["tag"] = _generic_tag(info.category, conceptual.nodes[node_id])


def _generic_tag(category: schema.NodeCategory, source_attrs: Mapping[str, object]) -> str | None:
    """Tagging rule per category (§3.1 rule 3) — the same attribute `_tag_of` also reads.

    Within the piping category, a safety valve has no `pipingComponentNumber`, only a
    `positionNumber` (e.g. EX01's "SV 104.01" — a gap found while probing the file,
    `kg-construction.md` §10): without this fallback it would go tag-less, and `resolve()`
    would never find it by tag.
    """
    if category is schema.NodeCategory.EQUIPMENT:
        return _as_str(source_attrs.get("tagName"))
    if category is schema.NodeCategory.PIPING:
        return _as_str(source_attrs.get("pipingComponentNumber")) or _as_str(
            source_attrs.get("positionNumber")
        )
    return None


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def add_related_to_edges(
    plant: nx.DiGraph[str], conceptual: nx.MultiDiGraph[str]
) -> tuple[dict[str, int], int]:
    """`related_to` élt ad minden élhez, amit `_map_edges` ismeretlen címke miatt eldobott.

    Mindkét végnek már térképezett `plant`-csomópontnak kell lennie — egy el nem ért
    végpontú él ehelyett `edges_lost_to_unmapped_endpoints`, más könyvelési tétel (§3.1 rule 5).

    Returns:
        A hozzáadott `related_to` élek száma `dexpi_label` szerint, és hány pár volt már
        él (`ImportReport.related_to_collapsed`) — ilyenkor a duplikátum nem kerül be.
    """
    added: collections.Counter[str] = collections.Counter()
    collapsed = 0
    for source, target, attrs in conceptual.edges(data=True):
        if attrs.get("attr_name") == "parentStructure" or _relation_of(attrs) is not None:
            continue  # már feloldva máshogy, vagy a séma egyik ismert relációjára térképezve
        if source not in plant.nodes or target not in plant.nodes:
            continue
        dexpi_label = f"{attrs.get('label')}/{attrs.get('attr_name')}"
        if plant.has_edge(source, target):
            collapsed += 1
            continue
        plant.add_edge(
            source, target, relation=schema.Relation.RELATED_TO.value, dexpi_label=dexpi_label
        )
        added[dexpi_label] += 1
    return dict(added), collapsed


def count_nodes_per_dexpi_class(
    conceptual: nx.MultiDiGraph[str], mapped_ids: Iterable[str]
) -> dict[str, int]:
    """Minden térképezett csomópontot a valódi pyDEXPI-osztálya szerint számol (§3.1 rule 6).

    Ismert és generikus osztályra egyaránt — ez a fallback saját lefedettségi
    ellenőrzése: az összegnek egyeznie kell a konceptuális gráf címke-számaival, mínusz
    a szándékosan struktúrába foglalt csomópontok.
    """
    labels = (str(conceptual.nodes[node_id]["label"]) for node_id in mapped_ids)
    return dict(collections.Counter(labels))
