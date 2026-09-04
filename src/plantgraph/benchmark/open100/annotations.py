"""A 96 OPEN100 csatlakozó felirata — amit a montázsokról leolvastunk.

Ez a stage 2 nyersanyaga: a stage 1 (extract.py, crops.py) csak megtalálta a
csatlakozókat és képet készített róluk. Itt rögzítjük, mit *mond* mindegyik —
melyik lapra hivatkozik, milyen rácsmezőre, milyen szolgáltatási kódra
("RCS", "CVCS", "ACW", ...), és milyen vezetékszámra.

**Hogyan olvastuk le, és mennyire megbízható.** A feliratokat 2026-08-31-én
olvastuk le a montázsképekről — nem OCR, hanem vizuális leolvasás, ahogy a
tervdokumentum (open100-annotation.md) is javasolta. Ez **nem** helyettesíti a
tervben előírt kézi ellenőrzést: apró, egymáshoz hasonló számsorok (pl. az
ACW-211150-es sorozat) esetén a leolvasás tévedhet. A `note` mező jelzi, ahol a
bizalmi szint alacsonyabb — ott a manifest.py a gyengébb `MatchRule`-t adja, és
a végső ellenőrzés a felhasználó dolga marad.

Egy sor mezői:
  sheet, node          — a csatlakozó kulcsa (lásd ConnectorObservation.key)
  target_pid, target_sheet_no, target_grid — mire hivatkozik; None, ha nincs
      felismerhető P&ID-hivatkozás a feliraton (lásd 11/22: berendezésnév, nem lap)
  service              — a felirat rövid rendszerkódja (pl. "RHRS", "ACW")
  line_number          — a csővezeték felirata, ha látható volt a kivágáson
  note                 — bármi, ami a párosításhoz vagy a megbízhatósághoz kell
"""

from __future__ import annotations

from pydantic import BaseModel


class RawConnectorText(BaseModel):
    """Egy csatlakozó leolvasott felirata, még párosítás előtt."""

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
        return f"{self.sheet}:inlet/outlet{self.node}"


# sheet, node, target_pid, target_sheet_no, target_grid, service, line_number, note
_ROWS: tuple[
    tuple[str, str, str | None, int | None, str | None, str | None, str | None, str | None], ...
] = (
    # --- 0. lap: Main Steam System (PID 140) ---
    ("0", "79", "180", 1, None, "ES", "SIZE-ES-140083-SPEC-HC-X", None),
    ("0", "80", "240", 1, None, "TBS", "SIZE-MSS-140076-SPEC-HC-X", None),
    ("0", "81", "240", 1, None, "TBS", "SIZE-MSS-140077-SPEC-HC-X", None),
    ("0", "82", "190", 1, None, "HPD", "SIZE-HPSD-140082-SPEC-HC-X", None),
    ("0", "83", "150", 1, None, "ACC", "SIZE-MSS-140081-SPEC-HC-X", None),
    ("0", "84", "170", 1, None, "FWS", "SIZE-FWS-140083-SPEC-HC-X", None),
    ("0", "85", "190", 1, None, "HPD", "SIZE-HPSD-140080-SPEC-HC-X", None),
    ("0", "86", "190", 1, None, "HPD", "SIZE-HPSD-140079-SPEC-HC-X", None),
    ("0", "87", "190", 1, None, "HPD", "SIZE-HPSD-140078-SPEC-HC-X", None),
    # --- 1. lap: Air Cooled Condenser (PID 150) ---
    ("1", "3", "140", 1, "E-1", "MSS", None, "nincs line a kivágáson — csak egy DETAIL-jelölés (harang, szaggatott kör, kerék); a 0/83-mal való párosítás csak a kölcsönös lap-hivatkozáson alapul"),
    ("1", "5", "160", 1, None, "CND", "SIZE-ACC-150098-SPEC-HC-X", "sheet2 létezik, de nincs hozzáilló pár ezzel a line-nal"),
    ("1", "22", "190", 1, None, "HPD", None, None),
    ("1", "24", "160", 1, "F-1", "CND", "SIZE-ACC-160090-SPEC-HC-X", None),
    ("1", "47", "250", 1, None, "TURB", None, "bejövő stílusú felirat, mégsincs rácsmező — valós következetlenség"),
    ("1", "73", "160", 1, None, "CND", "SIZE-COND-150104-SPEC-HC-X", None),
    # --- 2. lap: Condensate System (PID 160) ---
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
    # --- 3. lap: Feedwater System (PID 170) ---
    ("3", "16", "170", 2, None, "FWS", "SIZE-FWS-161131-SPEC-HC-X", None),
    ("3", "82", "140", 1, None, "MSS", "SIZE-MSS-170133-SPEC-HC-X", "line eltér 0/84-étől, csak a lap-kölcsönösség párosítja"),
    ("3", "89", "290", 1, None, "WSS", "SIZE-WSS-170134-SPEC-HC-X", None),
    # --- 4. lap: Extraction Steam System (PID 180) ---
    ("4", "16", "260", 1, None, "PDS", "SIZE-PDS-165139-SPEC-HC-X", None),
    ("4", "39", "190", 1, None, "HPSD", "SIZE-HPSD-166140-SPEC-HC-X", None),
    ("4", "41", "160", 1, "E-1", "CND", "SIZE-CND-165117-SPEC-HC-X", None),
    ("4", "42", "200", 4, None, "WTS", None, None),
    ("4", "43", "140", 1, None, "MSS", "SIZE-ESS-140083-SPEC-HC-X", None),
    ("4", "48", "240", 1, "D-1", "TBS", "SIZE-ESS-250137-SPEC-HC-X", None),
    ("4", "104", "240", 1, "E-1", "TBS", "SIZE-ESS-250136-SPEC-HC-X", None),
    ("4", "117", "160", 1, "E-1", "CND", "SIZE-CND-165117-SPEC-HC-X", "vélhetően duplikátum: azonos cél és line, mint 4/41"),
    # --- 5. lap: Reactor Coolant System, sheet 1/2 (PID 100) ---
    ("5", "12", "290", 1, None, "WSS", "SIZE-WS-101024-SPEC-HC-X", None),
    ("5", "38", "120", 1, None, "RHRS", "SIZE-RHRS-100021-SPEC-HC-X", None),
    ("5", "43", "100", 2, None, "RCS", "SIZE-RCS-101006-SPEC-HC-X", None),
    ("5", "45", "110", 1, None, "CVCS", "SIZE-CVCS-101022-SPEC-HC-X", None),
    ("5", "46", "100", 2, None, "RCS", "SIZE-RCS-100008-SPEC-HC-X", None),
    ("5", "47", "110", 1, "H-12", "CVCS", "SIZE-CVCS-110053-SPEC-HC-X", None),
    ("5", "49", "120", 1, "C-1", "RHRS", "SIZE-RHRS-121073-SPEC-HC-X", None),
    ("5", "54", "120", 1, "E-1", "RHRS", "SIZE-RHRS-121A072-SPEC-HC-X", None),
    ("5", "78", "100", 2, None, "RCS", "SIZE-RCS-100007-SPEC-HC-X", None),
    ("5", "86", "290", 1, None, "WSS", "SIZE-WSS-100023-SPEC-HC-X", None),
    ("5", "114", "110", 1, "G-12", "CVCS", "SIZE-CVCS-115C049-SPEC-HC-X", "10/14 célszövege bizonytalanul olvasható; a line-egyezés erősebb jel"),
    ("5", "124", "120", 1, "D-1", "RHRS", "SPEC-RHRS-121A065-SPEC-HC-X", "valódi elgépelés a forrásban: 'SPEC-' a 'SIZE-' helyett"),
    # --- 6. lap: Reactor Coolant System, sheet 2/2 (PID 100) — a szivattyú-részletek lapja ---
    ("6", "16", "100", 1, "G-1", "RCS", "SIZE-RCS-100007-SPEC-HC-X", None),
    ("6", "27", "100", 1, "C-1", "RCS", "SIZE-RCS-100008-SPEC-HC-X", None),
    ("6", "28", "210", 2, "C-1", "ACW", "SIZE-ACW-211158-SPEC-HC-X", "DETAIL B — RCS-PU-102B azonosság-bizonyíték; utolsó számjegy kikövetkeztetve"),
    ("6", "30", "210", 2, "C-1", "ACW", "SIZE-ACW-211157-SPEC-HC-X", "DETAIL A — RCS-PU-102A azonosság-bizonyíték"),
    ("6", "31", "100", 1, "D-1", "RCS", "SIZE-RCS-101006-SPEC-HC-X", None),
    ("6", "40", "210", 2, None, "ACW", "SIZE-ACW-102160-SPEC-HC-X", "COOLANT HT EXCH RC-P100-X001 felirat a közelben — a szivattyú harmadik írásmódja; a line-t egy független újraolvasás találta meg egy szélesebb kivágáson"),
    ("6", "41", "210", 2, None, "ACW", None, "ugyanaz a COOLANT HT EXCH RC-P100-X001 felirat"),
    ("6", "68", "320", 1, None, "RWS", "SIZE-RWS-104025-SPEC-HC-X", None),
    ("6", "69", "130", 1, None, "SWS", "SIZE-SWS-132172-SPEC-HC-X", None),
    ("6", "71", "320", 1, None, "RWS", None, None),
    # --- 7. lap: Aux Cooling Water System, sheet 1/2 (PID 210) ---
    ("7", "30", "170", 2, None, "FWS", "SIZE-ACW-175271-SPEC-HC-X", "javítva egy független újraolvasás alapján (korábban tévesen 211152 volt itt — az valójában 7/75-höz tartozik); a 175271 szám 2/14-en és 7/33-on is előfordul eltérő előtaggal, tehát önmagában nem egyedi itt"),
    ("7", "31", "170", 2, None, "FWS", "SIZE-ACW-211270-SPEC-HC-X", None),
    ("7", "32", "240", 1, None, "TBS", "SIZE-ACW-250261-SPEC-HC-X", None),
    ("7", "33", "210", 2, "F-1", "FWS", "SIZE-FWS-175271-SPEC-HC-X", "line ütközik 2/14-gyel és 7/30-cal; sheet8 létezik, de a rácsmező nem igazolható rács-interpoláció nélkül"),
    ("7", "34", "160", 1, None, "WTS", None, "bizonytalan olvasat; 'FCV XXX' helykitöltő jelzi, hogy a forrásrajz is befejezetlen itt"),
    ("7", "35", None, None, None, None, None, "olvashatatlan kivágás; a doboz szokatlanul keskeny (~17px) — talán tévesen észlelt csomópont; egy független újraolvasás is megerősítette: nem csatlakozó, hanem egy fúvóka/karima jel szöveg nélkül"),
    ("7", "75", "210", 2, None, "ACW", "SIZE-ACW-211152-SPEC-HC-X", "a line-t egy független újraolvasás találta meg; ez párosítja 8/7-tel (mindkét oldalon 211152 szerepel)"),
    ("7", "76", "250", 1, None, "TBS", "SIZE-ACW-211153-SPEC-HC-X", None),
    # --- 8. lap: Aux Cooling Water System, sheet 2/2 (PID 210) ---
    ("8", "5", "130", 1, None, "ACW", "SIZE-ACW-111162-SPEC-HC-X", None),
    ("8", "6", "130", 1, None, "SWS", "SIZE-SWS-130182-SPEC-HC-X", None),
    ("8", "7", "210", 1, "A-1", "ACW", "SIZE-ACW-211152-SPEC-HC-X", "párosítva 7/75-tel (lásd ott) egy független újraolvasás alapján"),
    ("8", "12", "100", 2, None, "ACW", "SIZE-ACW-211157-SPEC-HC-X", None),
    ("8", "13", "100", 2, None, "ACW", "SIZE-ACW-211158-SPEC-HC-X", None),
    ("8", "15", "130", 1, None, "SWS", "SIZE-ACS-102163-SPEC-HC-X", "javítva: korábban tévesen 270/WPS volt itt (8/16-tal felcserélve) egy független újraolvasás alapján; a line egy összefolyó fejvezetéken van, nem egyedi forráshoz köthető"),
    ("8", "16", "270", 1, None, "WPS", "SIZE-ACW-111164-SPEC-HC-X", "javítva: korábban tévesen 130/ACW volt itt (8/15-tel felcserélve) egy független újraolvasás alapján"),
    ("8", "17", "130", 1, None, "SWS", "SIZE-SWS-132181-SPEC-HC-X", None),
    ("8", "31", "100", 2, "C-1", "ACW", "SIZE-ACW-102160-SPEC-HC-X", None),
    ("8", "32", "100", 2, "A-4", "ACW", "SIZE-ACW-102161-SPEC-HC-X", None),
    ("8", "54", "210", 1, None, "ACW", None, "javítva: a korábbi line (111156) egy összefolyás utáni fejvezetéken van, nem ehhez a csatlakozóhoz köthető — egy független újraolvasás találta; korábbi párja (7/75) most 8/7-hez van párosítva, ezért ez megoldatlan marad"),
    # --- 9. lap: Residual Heat Removal System, sheet 2/2 (PID 120) ---
    ("9", "2", "120", 1, None, "RHR", None, "sheet11 létezik, de mind a négy kimenő csatlakozója már máshoz van párosítva"),
    ("9", "59", "120", 1, None, "RHR", None, "ugyanaz, mint 9/2"),
    # --- 10. lap: Chemical Volume Cooling Water (PID 110) ---
    ("10", "14", "120", 1, None, "RHR", "SIZE-CVCS-115C049-SPEC-HC-X", "célszöveg bizonytalanul olvasható ('RHR' vagy 'RCS'); a line-egyezés erősebb jel"),
    ("10", "15", "270", 1, None, "WPS", "SIZE-WPS-116050-SPEC-HC-X", None),
    ("10", "16", "320", 1, None, "RWS", "SIZE-RWS-116055-SPEC-HC-X", None),
    ("10", "24", "120", 1, "C-1", "RHRS", "SIZE-RHRS-121071-SPEC-HC-X", None),
    ("10", "45", "100", 1, None, "RCS", "SIZE-CVCS-110053-SPEC-HC-X", None),
    ("10", "94", "320", 1, None, "CAS", None, "más névvel (CAS), mint a 320-as PID többi hivatkozása (RWS) — feloldhatatlan mindkét esetben"),
    ("10", "149", "270", 1, None, "WPS", "SIZE-WPS-111058-SPEC-HC-X", None),
    ("10", "193", "300", 1, None, "WTS", None, None),
    ("10", "195", "320", 1, None, "RWS", "SIZE-RWS-116052-SPEC-HC-X", "a line-t egy független újraolvasás találta meg; dangling célú, nem befolyásolja a párosítást"),
    ("10", "196", "100", 1, "C-1", "RCS", "SIZE-CVCS-101022-SPEC-HC-X", None),
    # --- 11. lap: Residual Heat Removal System, sheet 1/2 (PID 120) ---
    ("11", "18", "100", 1, None, "RCS", "SIZE-RHRS-121A072-SPEC-HC-X", None),
    ("11", "22", None, None, None, None, None, "'REACTOR WATER SERVICE TANK' — berendezésnév, nincs P&ID-hivatkozás a feliraton"),
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
