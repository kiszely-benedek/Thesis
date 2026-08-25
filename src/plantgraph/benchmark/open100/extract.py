"""Kikeresi a lapok közötti csatlakozók helyét a PID2Graph annotációs fájljaiból.

Háttér: a PID2Graph adathalmaz minden rajzhoz ad egy GraphML fájlt, ami a rajz
gépi leírása. Ez a leírás viszont tisztán geometriai — minden csomópont annyit
mond, hogy "itt egy szelep van, ezekkel a koordinátákkal". **Szöveg egyáltalán
nincs benne**: sem berendezés-azonosító, sem felirat.

Emiatt a csatlakozók feliratát (ami megmondja, melyik lapra mutatnak) nem lehet a
GraphML-ből kiolvasni — csak a képről. Ez a modul tehát csak megkeresi, hol vannak
a csatlakozók; az elolvasásuk a kivágásokon történik, lásd crops.py.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from plantgraph.benchmark.models import BoundingBox, ConnectorObservation, Side

GRAPHML_NS = {"g": "http://graphml.graphdrawing.org/xmlns"}

#: Ezt a csomópont-osztályt használja a PID2Graph a lapszéli csatlakozókra.
#: Figyelem: van egy 'connector' nevű osztálya is, de az egészen mást jelent —
#: lapon belüli csomóponti jelölést, amiből 2408 darab van a 12 lapon. Ha arra
#: illesztenénk, zajt kapnánk, nem csatlakozókat.
CONNECTOR_LABEL = "inlet/outlet"

_BBOX_KEYS = ("xmin", "ymin", "xmax", "ymax")


def _attribute_names(root: ET.Element) -> dict[str, str]:
    """Feloldja a GraphML rövidítéseit.

    A GraphML nem a nevén nevezi az attribútumokat, hanem kulcsokkal hivatkozik
    rájuk: a fájl elején deklarálja, hogy 'd0' = 'label', 'd1' = 'xmin', és így
    tovább. Ez a függvény ezt a szótárat adja vissza.
    """
    return {
        key.get("id", ""): key.get("attr.name", "")
        for key in root.findall("g:key", GRAPHML_NS)
    }


def _node_data(node: ET.Element, names: dict[str, str]) -> dict[str, str]:
    """Egy csomópont XML-gyerekeit sima {attribútumnév: érték} szótárrá alakítja."""
    return {
        names[d.get("key", "")]: (d.text or "")
        for d in node.findall("g:data", GRAPHML_NS)
        if d.get("key", "") in names
    }


def _to_bbox(data: dict[str, str]) -> BoundingBox | None:
    """Befoglaló dobozt épít, vagy None-t ad, ha a csomópontnak hiányos a koordinátája."""
    if not all(k in data for k in _BBOX_KEYS):
        return None
    return BoundingBox(**{k: float(data[k]) for k in _BBOX_KEYS})


def _side_of(bbox: BoundingBox, image_width: int) -> Side:
    """Megmondja, a lap bal vagy jobb széléhez tartozik-e a szimbólum.

    Ez csak a képen elfoglalt helyet nézi. Szándékosan nem következtet belőle
    irányra: a bejövő csatlakozókat szokás balra rajzolni, de ez konvenció, nem
    szabály, és a valódi irányt a felirat mondja ki.
    """
    return Side.LEFT if bbox.centre_x < image_width / 2 else Side.RIGHT


def connectors_in_sheet(
    graphml_path: Path, image_width: int
) -> list[ConnectorObservation]:
    """Összegyűjti egy lap összes lapközi csatlakozóját.

    Args:
        graphml_path: a laphoz tartozó PID2Graph annotációs fájl.
        image_width: a rajz szélessége képpontban; ebből dől el a bal/jobb oldal.

    Returns:
        Egy-egy megfigyelés minden csatlakozóhoz, egyelőre csak geometriával —
        a feliratuk még üres.

    Raises:
        ValueError: ha a fájlban nincs <graph> elem, vagyis nem az, aminek hisszük.
    """
    root = ET.parse(graphml_path).getroot()
    graph = root.find("g:graph", GRAPHML_NS)
    if graph is None:
        raise ValueError(f"no <graph> element in {graphml_path}")

    names = _attribute_names(root)
    stem = graphml_path.stem
    found: list[ConnectorObservation] = []

    for node in graph.findall("g:node", GRAPHML_NS):
        data = _node_data(node, names)
        if data.get("label") != CONNECTOR_LABEL:
            continue
        bbox = _to_bbox(data)
        if bbox is None:
            continue
        found.append(
            ConnectorObservation(
                sheet_file=stem,
                node_id=node.get("id", ""),
                bbox=bbox,
                side=_side_of(bbox, image_width),
            )
        )
    return found


def label_counts(graphml_path: Path) -> dict[str, int]:
    """Megszámolja, melyik elemtípusból hány van a lapon.

    Gyors józansági ellenőrzés: ha egy új adathalmazon a számok nem hasonlítanak
    arra, amit várunk, akkor rossz fájlokat olvasunk, vagy más a formátum.
    """
    root = ET.parse(graphml_path).getroot()
    graph = root.find("g:graph", GRAPHML_NS)
    if graph is None:
        raise ValueError(f"no <graph> element in {graphml_path}")

    names = _attribute_names(root)
    counts: dict[str, int] = {}
    for node in graph.findall("g:node", GRAPHML_NS):
        label = _node_data(node, names).get("label", "?")
        counts[label] = counts.get(label, 0) + 1
    return counts
