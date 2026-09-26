"""Labels for the 96 OPEN100 connectors — read off the montages.

This is stage 2's raw material: stage 1 (extract.py, crops.py) only found the
connectors and produced images of them. Here we record what each one *says* —
which sheet it references, which grid cell, which service code ("RCS", "CVCS",
"ACW", ...), and which line number.

**How this was read, and how reliable it is.** The labels were read off the
montage images on 2026-08-31 — not OCR, but visual reading, as the design note
(open100-annotation.md) recommended. This does **not** replace the manual
review the design note calls for: small, similar-looking number sequences (e.g.
the ACW-211150 series) can be misread. The `note` field flags where confidence
is lower — there, manifest.py assigns the weaker `MatchRule`, and final
verification remains the user's job.

One row's fields:
  sheet, node          — the connector's key (see ConnectorObservation.key)
  target_pid, target_sheet_no, target_grid — what it references; None if the
      label has no recognizable P&ID reference (see 11/22: an equipment name, not a sheet)
  service              — the label's short system code (e.g. "RHRS", "ACW")
  line_number          — the pipe segment's label, if it was visible on the crop
  note                 — anything needed for pairing or for judging reliability
"""

from __future__ import annotations

from pydantic import BaseModel


class RawConnectorText(BaseModel):
    """A connector's label as read off, before pairing."""

    sheet: str
    node: str
    target_pid: str | None
    target_sheet_no: int | None
    target_grid: str | None
    service: str | None
    line_number: str | None
    note: str | None

    @property
    def key(self) -> str:
        """The same key ConnectorObservation.key produces — this is how the two tables join."""
        return f"{self.sheet}:inlet/outlet{self.node}"


# sheet, node, target_pid, target_sheet_no, target_grid, service, line_number, note
_ROWS: tuple[
    tuple[str, str, str | None, int | None, str | None, str | None, str | None, str | None], ...
] = (
    # --- sheet 0: Main Steam System (PID 140) ---
    ("0", "79", "180", 1, None, "ES", "SIZE-ES-140083-SPEC-HC-X", None),
    ("0", "80", "240", 1, None, "TBS", "SIZE-MSS-140076-SPEC-HC-X", None),
    ("0", "81", "240", 1, None, "TBS", "SIZE-MSS-140077-SPEC-HC-X", None),
    ("0", "82", "190", 1, None, "HPD", "SIZE-HPSD-140082-SPEC-HC-X", None),
    ("0", "83", "150", 1, None, "ACC", "SIZE-MSS-140081-SPEC-HC-X", None),
    ("0", "84", "170", 1, None, "FWS", "SIZE-FWS-140083-SPEC-HC-X", None),
    ("0", "85", "190", 1, None, "HPD", "SIZE-HPSD-140080-SPEC-HC-X", None),
    ("0", "86", "190", 1, None, "HPD", "SIZE-HPSD-140079-SPEC-HC-X", None),
    ("0", "87", "190", 1, None, "HPD", "SIZE-HPSD-140078-SPEC-HC-X", None),
    # --- sheet 1: Air Cooled Condenser (PID 150) ---
    ("1", "3", "140", 1, "E-1", "MSS", None, "nincs line a kivágáson — csak egy DETAIL-jelölés (harang, szaggatott kör, kerék); a 0/83-mal való párosítás csak a kölcsönös lap-hivatkozáson alapul"),
    ("1", "5", "160", 1, None, "CND", "SIZE-ACC-150098-SPEC-HC-X", "a DETAIL A SECTION VIEW-ban áll: ugyanaz az LCV 1501 + LIT 25094A/B csomópont, mint 1/73 a fő nézetben — tehát ugyanannak a csatlakozásnak a megismételt rajza, nem második cső; a részletnézet 150098-at, a fő nézet 150104-et ír (forrásrajzi eltérés). Megoldatlan marad, mert 2/16 már 1/73 párja"),
    ("1", "22", "190", 1, None, "HPD", None, None),
    ("1", "24", "160", 1, "F-1", "CND", "SIZE-ACC-160090-SPEC-HC-X", None),
    ("1", "47", "250", 1, None, "TURB", None, "bejövő stílusú felirat, mégsincs rácsmező — valós következetlenség"),
    ("1", "73", "160", 1, None, "CND", "SIZE-COND-150104-SPEC-HC-X", None),
    # --- sheet 2: Condensate System (PID 160) ---
    ("2", "13", "150", 1, None, "ACC", "SIZE-ACC-160090-SPEC-HC-X", None),
    ("2", "14", "170", 2, "E-1", "FWS", "SIZE-FWS-175271-SPEC-HC-X", "line ütközik 7/33-mal, valószínűleg véletlen egyezés"),
    ("2", "15", "200", 4, None, "WTS", "SIZE-WTS-275235-SPEC-HC-X", None),
    ("2", "16", "150", 1, "C-12", "CND", "SIZE-CND-150104-SPEC-HC-X", None),
    ("2", "17", "240", 1, "E-12", "ESS", "SIZE-ESS-165117-SPEC-HC-X", "dangling célú, a line nem számít; a szomszédos SIZE-COND-161115 egy másik, ide nem tartozó csőé — a felhasználó találta a hibás korábbi olvasatot"),
    ("2", "88", "290", 1, None, "WWS", None, None),
    ("2", "93", "270", 1, None, "WPS", None, None),
    ("2", "95", "240", 1, None, "MSS", "SIZE-COND-161114-SPEC-HC-X", None),
    ("2", "96", "180", 1, None, "ESS", "SIZE-ESS-165117-SPEC-HC-X", None),
    ("2", "97", "290", 1, None, "WSS", "SIZE-WSS-167118-SPEC-HC-X", None),
    # --- sheet 3: Feedwater System (PID 170) ---
    ("3", "16", "170", 2, None, "FWS", "SIZE-FWS-161131-SPEC-HC-X", None),
    ("3", "82", "140", 1, None, "MSS", "SIZE-MSS-170133-SPEC-HC-X", "line eltér 0/84-étől, csak a lap-kölcsönösség párosítja"),
    ("3", "89", "290", 1, None, "WSS", "SIZE-WSS-170134-SPEC-HC-X", None),
    # --- sheet 4: Extraction Steam System (PID 180) ---
    ("4", "16", "260", 1, None, "PDS", "SIZE-PDS-165139-SPEC-HC-X", None),
    ("4", "39", "190", 1, None, "HPSD", "SIZE-HPSD-166140-SPEC-HC-X", None),
    ("4", "41", "160", 1, "E-1", "CND", "SIZE-CND-165117-SPEC-HC-X", None),
    ("4", "42", "200", 4, None, "WTS", None, None),
    ("4", "43", "140", 1, None, "MSS", "SIZE-ESS-140083-SPEC-HC-X", None),
    ("4", "48", "240", 1, "D-1", "TBS", "SIZE-ESS-250137-SPEC-HC-X", None),
    ("4", "104", "240", 1, "E-1", "TBS", "SIZE-ESS-250136-SPEC-HC-X", None),
    ("4", "117", "160", 1, "E-1", "CND", "SIZE-CND-165117-SPEC-HC-X", "NEM duplikált észlelés: külön zászló a lap tetején (TCV 16013 felé), míg 4/41 a CND-HTR-166 N9-be megy; a forrásrajz ugyanazt a vezetékszámot nyomtatta két külön csőre — 2026-09-05-i harmadik olvasás igazolta"),
    # --- sheet 5: Reactor Coolant System, sheet 1/2 (PID 100) ---
    ("5", "12", "290", 1, None, "WSS", "SIZE-WS-101024-SPEC-HC-X", None),
    ("5", "38", "120", 1, None, "RHRS", "SIZE-RHRS-100021-SPEC-HC-X", None),
    ("5", "43", "100", 2, None, "RC", "SIZE-RCS-101006-SPEC-HC-X", "a zászlón RC-PID-100-2 áll (a lap többi hivatkozása RCS-PID-100-2) — úgy rögzítjük, ahogy nyomtatva van"),
    ("5", "45", "110", 1, None, "CVCS", "SIZE-CVCS-101022-SPEC-HC-X", None),
    ("5", "46", "100", 2, None, "RCS", "SIZE-RCS-100008-SPEC-HC-X", None),
    ("5", "47", "110", 1, "H-12", "CVCS", "SIZE-CVCS-110053-SPEC-HC-X", None),
    ("5", "49", "120", 1, "C-1", "RHRS", "SIZE-RHRS-121073-SPEC-HC-X", None),
    ("5", "54", "120", 1, "E-1", "RHRS", "SIZE-RHRS-121A072-SPEC-HC-X", None),
    ("5", "78", "100", 2, None, "RCS", "SIZE-RCS-100007-SPEC-HC-X", None),
    ("5", "86", "290", 1, None, "WSS", "SIZE-WSS-100023-SPEC-HC-X", None),
    ("5", "114", "110", 1, "G-12", "CVCS", "SIZE-CVCS-115C049-SPEC-HC-X", "a G-12 rácsmező pontosan 10/14 helyére mutat, és a line is egyezik; 10/14 saját célszövege viszont tisztán olvashatóan PID 120-1 (RHR), nem 100-1 — forrásrajzi ellentmondás, lásd a pár megjegyzését"),
    ("5", "124", "120", 1, "D-1", "RHRS", "SPEC-RHRS-121A065-SPEC-HC-X", "valódi elgépelés a forrásban: 'SPEC-' a 'SIZE-' helyett"),
    # --- sheet 6: Reactor Coolant System, sheet 2/2 (PID 100) — the pump-detail sheet ---
    ("6", "16", "100", 1, "G-1", "RCS", "SIZE-RCS-100007-SPEC-HC-X", None),
    ("6", "27", "100", 1, "C-1", "RCS", "SIZE-RCS-100008-SPEC-HC-X", None),
    ("6", "28", "210", 2, "C-1", "ACW", "SIZE-ACW-211158-SPEC-HC-X", "DETAIL B — RCS-PU-102B azonosság-bizonyíték; a 211158 a függőleges feliraton közvetlenül olvasható (2026-09-05, széles kivágás), nem kikövetkeztetett"),
    ("6", "30", "210", 2, "C-1", "ACW", "SIZE-ACW-211157-SPEC-HC-X", "DETAIL A — RCS-PU-102A azonosság-bizonyíték"),
    ("6", "31", "100", 1, "D-1", "RCS", "SIZE-RCS-101006-SPEC-HC-X", None),
    ("6", "40", "210", 2, None, "ACW", "SIZE-ACW-102160-SPEC-HC-X", "COOLANT HT EXCH RC-P100-X001 felirat a közelben — a szivattyú harmadik írásmódja; a line-t egy független újraolvasás találta meg egy szélesebb kivágáson"),
    ("6", "41", "210", 2, None, "ACW", None, "ugyanaz a COOLANT HT EXCH RC-P100-X001 felirat"),
    ("6", "68", "320", 1, None, "RWS", "SIZE-RWS-104025-SPEC-HC-X", None),
    ("6", "69", "130", 1, None, "SWS", "SIZE-SWS-132172-SPEC-HC-X", None),
    ("6", "71", "320", 1, None, "RWS", None, None),
    # --- sheet 7: Aux Cooling Water System, sheet 1/2 (PID 210) ---
    ("7", "30", "170", 2, None, "FWS", "SIZE-ACW-175271-SPEC-HC-X", "javítva egy független újraolvasás alapján (korábban tévesen 211152 volt itt — az valójában 7/75-höz tartozik); a 175271 szám 2/14-en és 7/33-on is előfordul eltérő előtaggal, tehát önmagában nem egyedi itt"),
    ("7", "31", "170", 2, None, "FWS", "SIZE-ACW-211270-SPEC-HC-X", None),
    ("7", "32", "240", 1, None, "TBS", "SIZE-ACW-250261-SPEC-HC-X", None),
    ("7", "33", "210", 2, "F-1", "ACW", "SIZE-FWS-175271-SPEC-HC-X", "a zászlón ACW áll (korábban tévesen a line FWS előtagja került ide); line ütközik 2/14-gyel és 7/30-cal. A (F-1) rácsmező a 8. lapon a jobb szél F sorára mutat — ott 8/5 áll, amelynek saját felirata SWS PID 130-1; a 8. lap egyetlen 210-1-re kimenő zászlója 8/54, ugyanennek az F-sori fejvezetéknek a bal végén. 2026-09-05: kizárásos alapon 8/54-gyel párosítva (service_direction), lásd a pár megjegyzését"),
    ("7", "34", "160", 1, None, "WTS", None, "a zászló WTS PID 160-1 / MAKE-UP WATER; a 160-as lapon (2. lap) nincs 210-re mutató zászló, és minden más MAKE-UP WATER zászló a WTS PID 200-x rajzra hivatkozik — valószínűleg elírt rajzszám (200 helyett 160). A 'FCV XXX' helykitöltő is jelzi, hogy a rajz itt befejezetlen. Nem feloldható, megoldatlan marad"),
    ("7", "35", None, None, None, None, None, "olvashatatlan kivágás; a doboz szokatlanul keskeny (~17px) — talán tévesen észlelt csomópont; egy független újraolvasás is megerősítette: nem csatlakozó, hanem egy fúvóka/karima jel szöveg nélkül"),
    ("7", "75", "210", 2, None, "ACW", "SIZE-ACW-211152-SPEC-HC-X", "a line-t egy független újraolvasás találta meg; ez párosítja 8/7-tel (mindkét oldalon 211152 szerepel)"),
    ("7", "76", "250", 1, None, "TBS", "SIZE-ACW-211153-SPEC-HC-X", None),
    # --- sheet 8: Aux Cooling Water System, sheet 2/2 (PID 210) ---
    ("8", "5", "130", 1, None, "SWS", "SIZE-ACW-111162-SPEC-HC-X", "a zászlón SWS áll, a line előtagja ACW; ez az F-sori egyenes fejvezeték jobb vége, a bal vége 8/54 — két kimenő zászló egy csövön, két függőleges betáplálással"),
    ("8", "6", "130", 1, None, "SWS", "SIZE-SWS-130182-SPEC-HC-X", None),
    ("8", "7", "210", 1, "A-1", "ACW", "SIZE-ACW-211152-SPEC-HC-X", "párosítva 7/75-tel (lásd ott) egy független újraolvasás alapján"),
    ("8", "12", "100", 2, None, "RCS", "SIZE-ACW-211157-SPEC-HC-X", "a zászlón RCS áll, a line előtagja ACW"),
    ("8", "13", "100", 2, None, "RCS", "SIZE-ACW-211158-SPEC-HC-X", "a zászlón RCS áll, a line előtagja ACW; egy ág csatlakozik a felirat előtt, de a felirat a zászlóba futó végszakaszon van"),
    ("8", "15", "130", 1, None, "SWS", "SIZE-ACS-102163-SPEC-HC-X", "javítva: korábban tévesen 270/WPS volt itt (8/16-tal felcserélve) egy független újraolvasás alapján; a line egy összefolyó fejvezetéken van, nem egyedi forráshoz köthető"),
    ("8", "16", "270", 1, None, "WPS", "SIZE-ACW-111164-SPEC-HC-X", "javítva: korábban tévesen 130/ACW volt itt (8/15-tel felcserélve) egy független újraolvasás alapján"),
    ("8", "17", "130", 1, None, "SWS", "SIZE-SWS-132181-SPEC-HC-X", None),
    ("8", "31", "100", 2, "C-1", "RCS", "SIZE-ACW-102160-SPEC-HC-X", "a zászlón RCS áll, a line előtagja ACW"),
    ("8", "32", "100", 2, "A-4", "RCS", "SIZE-ACW-102161-SPEC-HC-X", "a zászlón RCS áll, a line előtagja ACW; A-4 rácsmező, nem a szokásos szél-oszlop"),
    ("8", "54", "210", 1, None, "ACW", None, "a 111156 az F-sori egyenes fejvezetéken van, amely 8/54-től 8/5-ig fut két függőleges betáplálással, mindkét végén kimenő zászlóval — nem köthető egyedül ehhez a csatlakozóhoz; korábbi párja (7/75) 8/7-hez került. 2026-09-05: kizárásos alapon 7/33-mal párosítva (service_direction), lásd ott"),
    # --- sheet 9: Residual Heat Removal System, sheet 2/2 (PID 120) ---
    ("9", "2", "120", 1, None, "RHR", None, "egyirányú hivatkozás: a 9. lap (RHR 120-2) erre és 9/59-re hivatkozik a 120-1-es lapra, de a 11. lap (120-1) egyetlen zászlója sem hivatkozik vissza a 120-2-re — a 9. lap gyűjtő/osztó fejvezetékei (minden műszer XXX) a másik oldalon nincsenek megrajzolva. Nincs mit párosítani"),
    ("9", "59", "120", 1, None, "RHR", None, "ugyanaz, mint 9/2 — egyirányú hivatkozás, a 11. lapon nincs visszamutató zászló"),
    # --- sheet 10: Chemical Volume Cooling Water (PID 110) ---
    ("10", "14", "120", 1, None, "RHR", "SIZE-CVCS-115C049-SPEC-HC-X", "célszöveg tisztán olvasható: PID 120-1 / RHR (2026-09-05). Ez ellentmond az 5/114-gyel való párnak, amely a line-egyezésen és a G-12 rácsmezőn áll; alternatív pár 11/128 (CVCS PID 110-1, bejövő, line nélkül) volna"),
    ("10", "15", "270", 1, None, "WPS", "SIZE-WPS-116050-SPEC-HC-X", None),
    ("10", "16", "320", 1, None, "RWS", "SIZE-RWS-116055-SPEC-HC-X", None),
    ("10", "24", "120", 1, "C-1", "RHRS", "SIZE-RHRS-121071-SPEC-HC-X", None),
    ("10", "45", "100", 1, None, "RCS", "SIZE-CVCS-110053-SPEC-HC-X", None),
    ("10", "94", "320", 1, None, "CAS", None, "más névvel (CAS), mint a 320-as PID többi hivatkozása (RWS) — feloldhatatlan mindkét esetben"),
    ("10", "149", "270", 1, None, "WPS", "SIZE-WPS-111058-SPEC-HC-X", None),
    ("10", "193", "300", 1, None, None, None, "a zászlón csak PID 300-1 / MAKE-UP WATER áll, rendszerkód nélkül — a korábbi WTS nem volt a rajzon"),
    ("10", "195", "320", 1, None, "RWS", "SIZE-RWS-116052-SPEC-HC-X", "a line-t egy független újraolvasás találta meg; dangling célú, nem befolyásolja a párosítást"),
    ("10", "196", "100", 1, "C-1", "RCS", "SIZE-CVCS-101022-SPEC-HC-X", None),
    # --- sheet 11: Residual Heat Removal System, sheet 1/2 (PID 120) ---
    ("11", "18", "100", 1, None, "RCS", "SIZE-RHRS-121A072-SPEC-HC-X", None),
    ("11", "22", None, None, None, None, None, "'REACTOR WATER SERVICE TANK' — berendezésnév, nincs P&ID-hivatkozás a feliraton. 2026-09-05: mind a 12 lap berendezés-jegyzékét (alsó sáv) átnéztük, ilyen nevű tartály egyiken sincs — a tartály a korpuszon kívül van, de rajzszám nélkül nem tudjuk, melyik lapon"),
    ("11", "23", "100", 1, "H-1", "RCS", "SIZE-RHRS-100021-SPEC-HC-X", None),
    ("11", "109", "100", 1, None, "RCS", "SPEC-RHRS-121A065-SPEC-HC-X", None),
    ("11", "118", "110", 1, None, "CVCS", "SIZE-RHRS-121071-SPEC-HC-X", None),
    ("11", "127", "100", 1, None, "RCS", "SIZE-RHRS-121073-SPEC-HC-X", None),
    ("11", "128", "110", 1, None, "CVCS", None, "sheet10 egyetlen szabad kimenő csatlakozója sem illik ide"),
)

ANNOTATIONS: tuple[RawConnectorText, ...] = tuple(
    RawConnectorText(
        sheet=sheet,
        node=node,
        target_pid=target_pid,
        target_sheet_no=target_sheet_no,
        target_grid=target_grid,
        service=service,
        line_number=line_number,
        note=note,
    )
    for sheet, node, target_pid, target_sheet_no, target_grid, service, line_number, note in _ROWS
)
