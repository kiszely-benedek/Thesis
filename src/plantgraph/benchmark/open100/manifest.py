"""Összeállítja a végleges OPEN100 megoldókulcsot a leolvasott feliratokból.

A stage 2 lépései, ide sűrítve:

  1. minden csatlakozóhoz hozzácsatoljuk a leolvasott feliratot (annotations.py),
  2. a célra hivatkozó csatlakozókat vagy párba állítjuk (PAIRS — kézzel
     azonosítva, lásd lent), vagy lógóként rögzítjük (a cél lap nincs a
     korpuszban), vagy megoldatlanként (a cél lap megvan, de nem találtunk
     hozzáilló csatlakozót),
  3. ellenőrizzük, hogy mind a 96 csatlakozó sorsa ismert — SplitManifest.accounted_for().

**A párosítás kézi munka, nem algoritmus.** A tervdokumentum egy rangsorolt
illesztő szabályt ír le (line_number → rácsmező → szolgáltatás+irány); itt ezt
a rangsort a leolvasáskor soronként alkalmaztuk, nem egy
futtatható illesztő. A PAIRS lista ennek a döntésnek a lenyomata, minden sorhoz
a match_rule jelzi, mennyire volt egyértelmű.
"""

from __future__ import annotations

from plantgraph.benchmark.models import (
    ConnectorObservation,
    ConnectorPair,
    DanglingReference,
    MatchRule,
    SheetRef,
    SplitManifest,
    UnresolvedConnector,
)
from plantgraph.benchmark.open100.annotations import ANNOTATIONS, RawConnectorText
from plantgraph.benchmark.open100.sheets import KNOWN_ABSENT, SHEETS, resolve

SOURCE_NAME = "PID2Graph/OPEN100"

# (from_key, to_key, match_rule, note)
# Kézzel azonosított párok a montázsok elolvasása alapján, 2026-08-31.
PAIRS: tuple[tuple[str, str, MatchRule, str | None], ...] = (
    ("0:inlet/outlet83", "1:inlet/outlet3", MatchRule.GRID_MUTUAL, "1/3 nem mutat line-t; csak a kölcsönös lap-hivatkozás (0→ACC-150-1, 1→MSS-140-1) igazolja"),
    ("1:inlet/outlet24", "2:inlet/outlet13", MatchRule.LINE_NUMBER, None),
    ("2:inlet/outlet96", "4:inlet/outlet41", MatchRule.LINE_NUMBER, "a 165117 szám a dangling 2/17-en is szerepel (eltérő cél) — a szám önmagában nem egyedi itt, a cél-kölcsönösség is szükséges hozzá"),
    ("0:inlet/outlet79", "4:inlet/outlet43", MatchRule.LINE_NUMBER, "eltérő előtag (ES/ESS), azonos szám"),
    ("5:inlet/outlet38", "11:inlet/outlet23", MatchRule.LINE_NUMBER, None),
    ("5:inlet/outlet43", "6:inlet/outlet31", MatchRule.LINE_NUMBER, None),
    ("5:inlet/outlet45", "10:inlet/outlet196", MatchRule.LINE_NUMBER, None),
    ("5:inlet/outlet46", "6:inlet/outlet27", MatchRule.LINE_NUMBER, None),
    ("5:inlet/outlet47", "10:inlet/outlet45", MatchRule.LINE_NUMBER, None),
    ("5:inlet/outlet49", "11:inlet/outlet127", MatchRule.LINE_NUMBER, None),
    ("5:inlet/outlet54", "11:inlet/outlet18", MatchRule.LINE_NUMBER, None),
    ("5:inlet/outlet78", "6:inlet/outlet16", MatchRule.LINE_NUMBER, None),
    ("5:inlet/outlet114", "10:inlet/outlet14", MatchRule.LINE_NUMBER, "10/14 célszövege bizonytalan"),
    ("5:inlet/outlet124", "11:inlet/outlet109", MatchRule.LINE_NUMBER, "valós elgépelés: 'SPEC-' a 'SIZE-' helyett, mindkét oldalon"),
    ("6:inlet/outlet28", "8:inlet/outlet13", MatchRule.LINE_NUMBER, "utolsó számjegy kikövetkeztetve kizárással"),
    ("6:inlet/outlet30", "8:inlet/outlet12", MatchRule.LINE_NUMBER, None),
    ("10:inlet/outlet24", "11:inlet/outlet118", MatchRule.LINE_NUMBER, None),
    ("1:inlet/outlet73", "2:inlet/outlet16", MatchRule.LINE_NUMBER, "eltérő előtag (CND/COND), azonos szám — a felhasználó találta a hiányzó line-t"),
    ("0:inlet/outlet84", "3:inlet/outlet82", MatchRule.GRID_MUTUAL, "eltérő line-szám, csak a lapok kölcsönös hivatkozása alapján"),
    ("7:inlet/outlet75", "8:inlet/outlet7", MatchRule.LINE_NUMBER, "mindkét oldalon SIZE-ACW-211152-SPEC-HC-X — egy független újraolvasás találta; a korábbi (gyenge) 8/54-7/75 párosítást lecseréli"),
    ("6:inlet/outlet40", "8:inlet/outlet31", MatchRule.LINE_NUMBER, "mindkét oldalon SIZE-ACW-102160-SPEC-HC-X — a 6/40 oldali line-t egy független újraolvasás találta meg egy szélesebb kivágáson; korábban service_direction volt"),
    ("6:inlet/outlet41", "8:inlet/outlet32", MatchRule.SERVICE_DIRECTION, "kizárásos párosítás, line nem olvasható egyik oldalon sem — egy független újraolvasás is megerősítette, hogy 6/41-en nincs line"),
)

# Nincs IDENTITY_GROUPS ebben a fájlban. Az RCS-PU-102A/102B azonosság
# (5. lap folyamatábra ↔ 6. lap DETAIL A/B) képileg igazolt, de nincs hozzá
# valódi graphml csomópont: a sheet5 mind a hat "pump" címkéjű csomópontja
# ellenőrzötten áramláselem (FE/FT), nem a szivattyútest, és a sheet6-on
# egyetlen "pump" címkéjű csomópont sincs. Egy IdentityGroup-nak kitalált
# kulcsot adni pont az a hiba lenne, amit korábban már elkövettünk és
# kijavítottunk (lásd 50-progress/2026-W35.md). Amíg nincs valódi csomópont,
# ez a lelet szövegben marad — lásd open100-annotation.md 1. nyitott kérdés.


def _dangling_reason(pid: str | None) -> str:
    """Emberi olvasható indoklás egy lógó hivatkozáshoz, ha ismerjük a rendszer nevét."""
    name = KNOWN_ABSENT.get(pid or "")
    if name is None:
        return "target sheet not present in corpus"
    return f"target sheet not present in corpus ({name})"


def _classify(raw: RawConnectorText, paired_keys: set[str]) -> tuple[str, object]:
    """Eldönti, a három sors (párba került / lógó / megoldatlan) melyikébe esik egy csatlakozó.

    A "párba került" eseteket a hívó már kiszűrte (paired_keys) — ez a függvény
    csak a maradékot osztályozza a felirat alapján: van-e feloldható cél.
    """
    if raw.key in paired_keys:
        return "paired", None
    if raw.target_pid is None:
        return "unresolved", UnresolvedConnector(
            from_key=raw.key, reason=raw.note or "no P&ID reference on the label"
        )
    target = SheetRef(pid=raw.target_pid, sheet_no=raw.target_sheet_no or 1)
    if resolve(target) is None:
        return "dangling", DanglingReference(
            from_key=raw.key, target=target, reason=_dangling_reason(raw.target_pid)
        )
    reason = raw.note or "target sheet exists but no matching connector was found on it"
    return "unresolved", UnresolvedConnector(from_key=raw.key, reason=reason)


def build_manifest(observations: list[ConnectorObservation]) -> SplitManifest:
    """Összeilleszti a geometriát (stage 1) és a feliratokat (annotations.py) egy manifestbe."""
    by_key = {raw.key: raw for raw in ANNOTATIONS}
    enriched = [_enrich(obs, by_key[obs.key]) for obs in observations]

    paired_keys = {frm for frm, _, _, _ in PAIRS} | {to for _, to, _, _ in PAIRS}
    dangling: list[DanglingReference] = []
    unresolved: list[UnresolvedConnector] = []
    for raw in ANNOTATIONS:
        bucket, entry = _classify(raw, paired_keys)
        if bucket == "dangling":
            dangling.append(entry)  # type: ignore[arg-type]
        elif bucket == "unresolved":
            unresolved.append(entry)  # type: ignore[arg-type]

    pairs = [
        ConnectorPair(from_key=frm, to_key=to, match_rule=rule, note=note)
        for frm, to, rule, note in PAIRS
    ]

    return SplitManifest(
        source=SOURCE_NAME,
        sheet_files=sorted(SHEETS, key=int),
        connectors=enriched,
        connector_pairs=pairs,
        dangling=dangling,
        unresolved=unresolved,
    )


def _enrich(obs: ConnectorObservation, raw: RawConnectorText) -> ConnectorObservation:
    """Ráírja a geometriai megfigyelésre a leolvasott feliratot."""
    target = None
    if raw.target_pid is not None:
        target = SheetRef(pid=raw.target_pid, sheet_no=raw.target_sheet_no or 1)
    return obs.model_copy(
        update={
            "target": target,
            "grid_cell": raw.target_grid,
            "service": raw.service,
            "line_number": raw.line_number,
        }
    )


__all__ = ["build_manifest", "PAIRS"]
