# Magyar kérdéslista a D100 üzemre (kézi teszteléshez a demóban)

Minden eredeti kérdéshez 4 magyar változat: (1) formális, (2) köznapi, (3) tömör, jegyzetszerű, (4) magyar–angol mérnöki szleng.
A demóban a D100-at válaszd. A helyes válasz a benchmarkban van; ezt a lista szándékosan nem tartalmazza.

## 1. CONNECTED
- Eredeti (angol): Can process flow reach T-47-4 from TK-3-3?
- 1: Eljuthat a technológiai áram a TK-3-3-ból a T-47-4-be?
- 2: El tud jutni az anyag a TK-3-3-ból a T-47-4-ig?
- 3: TK-3-3 → T-47-4: van folyamatáram-útvonal?
- 4: Van-e process flow path a TK-3-3-tól a T-47-4-ig?

## 2. CONNECTED
- Eredeti (angol): Can process flow reach E-35-1 from P-32-1?
- 1: El tud jutni a technológiai áram a P-32-1-től az E-35-1-ig?
- 2: Átjut a közeg a P-32-1-ből az E-35-1-be?
- 3: P-32-1-től E-35-1-ig van áramlási út?
- 4: A P-32-1 után downstream elérhető az E-35-1 a process flow mentén?

## 3. COUNT_IN_UNIT
- Eredeti (angol): How many heat exchangers are in unit 47?
- 1: Hány hőcserélő van a 47-es egységben (unit 47)?
- 2: Mennyi hőcserélő van a 47-es üzemrészben?
- 3: 47-es egység, hőcserélők száma?
- 4: Hány hőcserélő (HX) van a 47-es unitban?

## 4. COUNT_IN_UNIT
- Eredeti (angol): How many pressure vessels are in unit 36?
- 1: Hány nyomástartó edény található a 36-os egységben (unit 36)?
- 2: Mennyi nyomástartó edény van a 36-os üzemrészben?
- 3: Nyomástartó edények darabszáma a 36-os egységben?
- 4: Hány pressure vessel található a 36-os unitban?

## 5. CROSS_UNIT
- Eredeti (angol): Which other units receive process flow directly from unit 19?
- 1: Mely más egységek kapnak közvetlenül technológiai áramot a 19-es egységből (unit 19)?
- 2: Mely más üzemrészekbe megy közvetlenül anyag a 19-es egységből?
- 3: 19-es egységből közvetlenül táplált többi egység?
- 4: Mely másik unitokat táplálja közvetlenül a 19-es unit process flow-ja?

## 6. CROSS_UNIT
- Eredeti (angol): Which other units receive process flow directly from unit 14?
- 1: Mely más egységek kapnak közvetlenül technológiai áramot a 14-es egységből (unit 14)?
- 2: Melyik másik üzemrészekbe folyik át közvetlenül anyag a 14-es egységből?
- 3: 14-es egységből közvetlenül táplált többi egység?
- 4: Mely másik unitokat táplálja közvetlenül a 14-es unit process flow-ja?

## 7. DOWNSTREAM_IN_UNIT
- Eredeti (angol): Which equipment items and valves in unit 49 receive flow from C-49-5, directly or indirectly?
- 1: A 49-es egységben (unit 49) mely berendezések és szelepek kapnak áramot a C-49-5-ből, közvetlenül vagy közvetve?
- 2: A 49-es üzemrészen belül melyik berendezésekbe és szelepekbe jut el a C-49-5-ből jövő anyag, akár közvetlenül, akár közvetve?
- 3: 49-es egységen belül C-49-5-ből (közvetlenül/közvetve) áramot kapó berendezések, szelepek?
- 4: A 49-es unitban mely equipmentek és szelepek vannak a C-49-5-től downstream, közvetlenül vagy közvetve?

## 8. DOWNSTREAM_IN_UNIT
- Eredeti (angol): Which equipment items and valves in unit 2 receive flow from T-2-2, directly or indirectly?
- 1: A 2-es egységben (unit 2) mely berendezések és szelepek kapnak áramot a T-2-2-ből, közvetlenül vagy közvetve?
- 2: A 2-es üzemrészen belül melyik berendezésekbe és szelepekbe jut el a T-2-2-ből jövő anyag, akár közvetlenül, akár közvetve?
- 3: 2-es egységen belül T-2-2-ből (közvetlenül/közvetve) áramot kapó berendezések, szelepek?
- 4: A 2-es unitban mely equipmentek és szelepek vannak a T-2-2-től downstream, közvetlenül vagy közvetve?

## 9. FLOW_PATH
- Eredeti (angol): Trace the process flow path from GV-6-13 to GV-16-2. List every equipment item and valve in order.
- 1: Kövesd végig a technológiai áram útját a GV-6-13-tól a GV-16-2-ig, és sorold fel sorrendben az összes berendezést és szelepet.
- 2: Le tudnád követni, merre megy az anyag a GV-6-13-tól a GV-16-2-ig? Írd le sorban az összes berendezést és szelepet, ami útba esik.
- 3: Útvonal GV-6-13 → GV-16-2, berendezések + szelepek sorrendben.
- 4: Trace-eld le a flow path-t a GV-6-13-tól a GV-16-2-ig, és listázd sorrendben az összes equipmentet és valve-ot.

## 10. FLOW_PATH
- Eredeti (angol): Trace the process flow path from BV-1-9 to GV-13-2. List every equipment item and valve in order.
- 1: Kövesd végig a technológiai áram útját a BV-1-9-től a GV-13-2-ig, és sorold fel sorrendben az összes berendezést és szelepet.
- 2: Le tudnád követni, merre megy az anyag a BV-1-9-től a GV-13-2-ig? Írd le sorban az összes berendezést és szelepet, ami útba esik.
- 3: Útvonal BV-1-9 → GV-13-2, berendezések + szelepek sorrendben.
- 4: Trace-eld le a flow path-t a BV-1-9-től a GV-13-2-ig, és listázd sorrendben az összes equipmentet és valve-ot.

## 11. INSTRUMENTS_OF_ITEM
- Eredeti (angol): Which instruments measure E-30-3?
- 1: Mely műszerek mérik az E-30-3-at?
- 2: Melyik műszerek mérnek az E-30-3-on?
- 3: E-30-3 mérőműszerei?
- 4: Melyik instrument tagek mérik az E-30-3-at?

## 12. INSTRUMENTS_OF_ITEM
- Eredeti (angol): Which instruments measure T-16-3?
- 1: Mely műszerek mérik a T-16-3-at?
- 2: Melyik műszerek mérnek a T-16-3-on?
- 3: T-16-3 mérőműszerei?
- 4: Melyik instrument tagek mérik a T-16-3-at?

## 13. LOOKUP_TYPE
- Eredeti (angol): What type of item is LT-19-3?
- 1: Milyen típusú elem az LT-19-3?
- 2: Mi az az LT-19-3, milyen fajta elem?
- 3: LT-19-3 típusa?
- 4: Milyen item type-hoz tartozik az LT-19-3 tag?

## 14. LOOKUP_TYPE
- Eredeti (angol): What type of item is V-27-2?
- 1: Milyen típusú elem a V-27-2?
- 2: Mi az a V-27-2, milyen fajta elem?
- 3: V-27-2 típusa?
- 4: Milyen item type-hoz tartozik a V-27-2 tag?

## 15. LOOKUP_UNIT
- Eredeti (angol): Which unit is CHV-21-4 located in?
- 1: Melyik egységben található a CHV-21-4?
- 2: A CHV-21-4 melyik üzemrészben van?
- 3: CHV-21-4 – melyik egység?
- 4: Melyik unitban van a CHV-21-4 tag?

## 16. LOOKUP_UNIT
- Eredeti (angol): Which unit is PIC-13-4 located in?
- 1: Melyik egységben található a PIC-13-4?
- 2: A PIC-13-4 melyik üzemrészben van?
- 3: PIC-13-4 – melyik egység?
- 4: Melyik unitban van a PIC-13-4 tag?

## 17. LOOPS_NEAR_ITEM
- Eredeti (angol): Which control loops act on valves directly connected to C-20-1?
- 1: Mely szabályozó körök hatnak a C-20-1-hez közvetlenül csatlakozó szelepekre?
- 2: Mely szabályozókörök működtetik azokat a szelepeket, amelyek közvetlenül a C-20-1-re vannak kötve?
- 3: C-20-1-hez közvetlenül kötött szelepekre ható szabályozókörök?
- 4: Melyik control loopok hatnak a C-20-1-re közvetlenül rákötött valve-okra?

## 18. LOOPS_NEAR_ITEM
- Eredeti (angol): Which control loops act on valves directly connected to V-18-5?
- 1: Mely szabályozó körök hatnak a V-18-5-höz közvetlenül csatlakozó szelepekre?
- 2: Mely szabályozókörök működtetik azokat a szelepeket, amelyek közvetlenül a V-18-5-re vannak kötve?
- 3: V-18-5-höz közvetlenül kötött szelepekre ható szabályozókörök?
- 4: Melyik control loopok hatnak a V-18-5-re közvetlenül rákötött valve-okra?

## 19. LOOP_ACTUATED_VALVE
- Eredeti (angol): Which valve is actuated by control loop LIC-18-3?
- 1: Melyik szelepet működteti az LIC-18-3 szabályozó kör?
- 2: Az LIC-18-3 szabályozókör melyik szelepet mozgatja?
- 3: LIC-18-3 kör → melyik szelep?
- 4: Melyik valve-ot vezérli az LIC-18-3 control loop?

## 20. LOOP_ACTUATED_VALVE
- Eredeti (angol): Which valve is actuated by control loop TIC-41-3?
- 1: Melyik szelepet működteti a TIC-41-3 szabályozó kör?
- 2: A TIC-41-3 szabályozókör melyik szelepet mozgatja?
- 3: TIC-41-3 kör → melyik szelep?
- 4: Melyik valve-ot vezérli a TIC-41-3 control loop?

## 21. LOOP_MEASURED_EQUIPMENT
- Eredeti (angol): Which equipment item does control loop LIC-31-5 measure?
- 1: Melyik berendezést méri az LIC-31-5 szabályozó kör?
- 2: Az LIC-31-5 szabályozókör melyik berendezésen mér?
- 3: LIC-31-5 kör mért berendezése?
- 4: Az LIC-31-5 control loop melyik equipmentet méri?

## 22. LOOP_MEASURED_EQUIPMENT
- Eredeti (angol): Which equipment item does control loop LIC-33-5 measure?
- 1: Melyik berendezést méri az LIC-33-5 szabályozó kör?
- 2: Az LIC-33-5 szabályozókör melyik berendezésen mér?
- 3: LIC-33-5 kör mért berendezése?
- 4: Az LIC-33-5 control loop melyik equipmentet méri?

## 23. NEIGHBOURS_DOWNSTREAM
- Eredeti (angol): Which equipment items and valves receive flow directly from GV-28-8?
- 1: Mely berendezések és szelepek kapnak közvetlenül áramot a GV-28-8-ból?
- 2: Melyik berendezésekbe és szelepekbe megy közvetlenül a GV-28-8-ból az anyag?
- 3: GV-28-8 után közvetlenül következő berendezések, szelepek?
- 4: Mely equipmentek és valve-ok vannak közvetlenül downstream a GV-28-8-tól?

## 24. NEIGHBOURS_DOWNSTREAM
- Eredeti (angol): Which equipment items and valves receive flow directly from P-23-1?
- 1: Mely berendezések és szelepek kapnak közvetlenül áramot a P-23-1-ből?
- 2: Melyik berendezésekbe és szelepekbe megy közvetlenül a P-23-1-ből az anyag?
- 3: P-23-1 után közvetlenül következő berendezések, szelepek?
- 4: Mely equipmentek és valve-ok vannak közvetlenül downstream a P-23-1-től?

## 25. NO_PATH
- Eredeti (angol): Trace the process flow path from V-34-2 to TK-50-6. List every equipment item and valve in order.
- 1: Kövesd végig a technológiai áram útját a V-34-2-től a TK-50-6-ig, és sorold fel sorrendben az összes berendezést és szelepet.
- 2: Le tudnád követni, merre megy az anyag a V-34-2-től a TK-50-6-ig? Írd le sorban az összes berendezést és szelepet, ami útba esik.
- 3: Útvonal V-34-2 → TK-50-6, berendezések + szelepek sorrendben.
- 4: Trace-eld le a flow path-t a V-34-2-től a TK-50-6-ig, és listázd sorrendben az összes equipmentet és valve-ot.

## 26. NO_PATH
- Eredeti (angol): Trace the process flow path from P-11-5 to P-20-1. List every equipment item and valve in order.
- 1: Kövesd végig a technológiai áram útját a P-11-5-től a P-20-1-ig, és sorold fel sorrendben az összes berendezést és szelepet.
- 2: Le tudnád követni, merre megy az anyag a P-11-5-től a P-20-1-ig? Írd le sorban az összes berendezést és szelepet, ami útba esik.
- 3: Útvonal P-11-5 → P-20-1, berendezések + szelepek sorrendben.
- 4: Trace-eld le a flow path-t a P-11-5-től a P-20-1-ig, és listázd sorrendben az összes equipmentet és valve-ot.

## 27. SAME_UNIT
- Eredeti (angol): Are E-12-1 and E-12-4 in the same unit?
- 1: Ugyanabban az egységben van az E-12-1 és az E-12-4?
- 2: Egy üzemrészben van az E-12-1 meg az E-12-4?
- 3: E-12-1 és E-12-4 – azonos egység?
- 4: Az E-12-1 és az E-12-4 ugyanabba a unitba tartozik?

## 28. SAME_UNIT
- Eredeti (angol): Are E-19-5 and TK-17-4 in the same unit?
- 1: Ugyanabban az egységben van az E-19-5 és a TK-17-4?
- 2: Egy üzemrészben van az E-19-5 meg a TK-17-4?
- 3: E-19-5 és TK-17-4 – azonos egység?
- 4: Az E-19-5 és a TK-17-4 ugyanabba a unitba tartozik?

## 29. SHEETS_OF_TAG
- Eredeti (angol): On which sheets is P-23-1 drawn?
- 1: Mely lapokon van ábrázolva a P-23-1?
- 2: Melyik lapokon szerepel a P-23-1?
- 3: P-23-1 – rajzlapok?
- 4: Melyik sheeteken van rajta a P-23-1?

## 30. SHEETS_OF_TAG
- Eredeti (angol): On which sheets is T-32-2 drawn?
- 1: Mely lapokon van ábrázolva a T-32-2?
- 2: Melyik lapokon szerepel a T-32-2?
- 3: T-32-2 – rajzlapok?
- 4: Melyik sheeteken van rajta a T-32-2?

## 31. UNANSWERABLE_TAG
- Eredeti (angol): What type of item is FV-48-5?
- 1: Milyen típusú elem az FV-48-5?
- 2: Mi az az FV-48-5, milyen fajta elem?
- 3: FV-48-5 típusa?
- 4: Milyen item type-hoz tartozik az FV-48-5 tag?

## 32. UNANSWERABLE_TAG
- Eredeti (angol): Trace the process flow path from V-13-7 to GV-12-10. List every equipment item and valve in order.
- 1: Kövesd végig a technológiai áram útját a V-13-7-től a GV-12-10-ig, és sorold fel sorrendben az összes berendezést és szelepet.
- 2: Le tudnád követni, merre megy az anyag a V-13-7-től a GV-12-10-ig? Írd le sorban az összes berendezést és szelepet, ami útba esik.
- 3: Útvonal V-13-7 → GV-12-10, berendezések + szelepek sorrendben.
- 4: Trace-eld le a flow path-t a V-13-7-től a GV-12-10-ig, és listázd sorrendben az összes equipmentet és valve-ot.

## 33. UPSTREAM_ISOLATION
- Eredeti (angol): To isolate T-26-1 from all upstream equipment, which valves must be closed?
- 1: Mely szelepeket kell zárni, hogy a T-26-1-et leválasszuk az összes felette (áramlási irányban előtte) lévő berendezésről?
- 2: Melyik szelepeket kell elzárni, hogy a T-26-1 le legyen választva minden áramlásirányban előtte lévő berendezésről?
- 3: T-26-1 izolálása az összes upstream berendezéstől – zárandó szelepek?
- 4: Mely valve-okat kell lezárni, hogy a T-26-1-et izoláljuk az összes upstream equipmenttől?

## 34. UPSTREAM_ISOLATION
- Eredeti (angol): To isolate T-13-5 from all upstream equipment, which valves must be closed?
- 1: Mely szelepeket kell zárni, hogy a T-13-5-öt leválasszuk az összes felette (áramlási irányban előtte) lévő berendezésről?
- 2: Melyik szelepeket kell elzárni, hogy a T-13-5 le legyen választva minden áramlásirányban előtte lévő berendezésről?
- 3: T-13-5 izolálása az összes upstream berendezéstől – zárandó szelepek?
- 4: Mely valve-okat kell lezárni, hogy a T-13-5-öt izoláljuk az összes upstream equipmenttől?

## 35. UPSTREAM_SOURCES
- Eredeti (angol): Which source items, with nothing flowing into them, ultimately feed TK-23-4?
- 1: Mely forráselemek, amelyekbe nem folyik be semmi, táplálják végső soron a TK-23-4-et?
- 2: Melyik kiinduló elemekből jön végső soron a TK-23-4 betáplálása, olyanokból, amikbe semmi nem folyik be?
- 3: TK-23-4 végső forrásai (amikbe semmi nem folyik be)?
- 4: Melyek azok a source itemek, amelyekbe semmi nem folyik be, és végső soron a TK-23-4-et táplálják?

## 36. UPSTREAM_SOURCES
- Eredeti (angol): Which source items, with nothing flowing into them, ultimately feed V-39-1?
- 1: Mely forráselemek, amelyekbe nem folyik be semmi, táplálják végső soron a V-39-1-et?
- 2: Melyik kiinduló elemekből jön végső soron a V-39-1 betáplálása, olyanokból, amikbe semmi nem folyik be?
- 3: V-39-1 végső forrásai (amikbe semmi nem folyik be)?
- 4: Melyek azok a source itemek, amelyekbe semmi nem folyik be, és végső soron a V-39-1-et táplálják?
