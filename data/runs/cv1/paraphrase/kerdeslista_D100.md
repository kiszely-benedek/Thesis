# Átfogalmazott kérdések a D100 üzemre (kézi teszteléshez)

Minden eredeti kérdéshez 4 változat: (1) laza angol, (2) tömör operátori angol, (3) formális angol, (4) magyar.
Az eredeti kérdés és a helyes válasz a benchmarkban van; a demóban a D100-at válaszd.

## 1. CONNECTED
- Eredeti: Can process flow reach T-47-4 from TK-3-3?
- 1: Is it possible for process flow to get from TK-3-3 to T-47-4?
- 2: flow path TK-3-3 to T-47-4? y/n
- 3: Is T-47-4 reachable by process flow originating at TK-3-3?
- 4: Eljuthat a technológiai áram a TK-3-3-ból a T-47-4-be?

## 2. CONNECTED
- Eredeti: Can process flow reach E-35-1 from P-32-1?
- 1: Can the process flow make it from P-32-1 over to E-35-1?
- 2: P-32-1 to E-35-1 flow connected? y/n
- 3: Is there a process flow connection by which E-35-1 is reachable from P-32-1?
- 4: El tud jutni a technológiai áram a P-32-1-től az E-35-1-ig?

## 3. COUNT_IN_UNIT
- Eredeti: How many heat exchangers are in unit 47?
- 1: How many heat exchangers do we have in unit 47?
- 2: HX count unit 47?
- 3: What is the total number of heat exchangers located in unit 47?
- 4: Hány hőcserélő van a 47-es egységben (unit 47)?

## 4. COUNT_IN_UNIT
- Eredeti: How many pressure vessels are in unit 36?
- 1: How many pressure vessels are there in unit 36?
- 2: # pressure vessels unit 36?
- 3: What is the number of pressure vessels contained in unit 36?
- 4: Hány nyomástartó edény található a 36-os egységben (unit 36)?

## 5. CROSS_UNIT
- Eredeti: Which other units receive process flow directly from unit 19?
- 1: Which other units get process flow straight from unit 19?
- 2: unit 19 direct flow to which other units?
- 3: To which other units is process flow delivered directly from unit 19?
- 4: Mely más egységek kapnak közvetlenül technológiai áramot a 19-es egységből (unit 19)?

## 6. CROSS_UNIT
- Eredeti: Which other units receive process flow directly from unit 14?
- 1: Which other units get process flow straight from unit 14?
- 2: unit 14 direct flow to which other units?
- 3: To which other units is process flow delivered directly from unit 14?
- 4: Mely más egységek kapnak közvetlenül technológiai áramot a 14-es egységből (unit 14)?

## 7. DOWNSTREAM_IN_UNIT
- Eredeti: Which equipment items and valves in unit 49 receive flow from C-49-5, directly or indirectly?
- 1: In unit 49, what equipment and valves get flow from C-49-5, whether directly or further down the line?
- 2: unit 49 equip + valves fed by C-49-5, direct/indirect?
- 3: Which equipment items and valves within unit 49 are supplied with flow from C-49-5, either directly or indirectly?
- 4: A 49-es egységben (unit 49) mely berendezések és szelepek kapnak áramot a C-49-5-ből, közvetlenül vagy közvetve?

## 8. DOWNSTREAM_IN_UNIT
- Eredeti: Which equipment items and valves in unit 2 receive flow from T-2-2, directly or indirectly?
- 1: In unit 2, which equipment and valves get flow from T-2-2, directly or indirectly?
- 2: unit 2 equip + valves downstream of T-2-2, direct or indirect?
- 3: Which equipment items and valves within unit 2 are fed by T-2-2, whether directly or indirectly?
- 4: A 2-es egységben (unit 2) mely berendezések és szelepek kapnak áramot a T-2-2-ből, közvetlenül vagy közvetve?

## 9. FLOW_PATH
- Eredeti: Trace the process flow path from GV-6-13 to GV-16-2. List every equipment item and valve in order.
- 1: Can you walk me through the process flow path from GV-6-13 to GV-16-2, listing every piece of equipment and every valve in order?
- 2: flow path GV-6-13 to GV-16-2, all equip + valves in order
- 3: Trace the process flow route from GV-6-13 through to GV-16-2, enumerating each equipment item and valve in sequence.
- 4: Kövesd végig a technológiai áram útját a GV-6-13-tól a GV-16-2-ig, és sorold fel sorrendben az összes berendezést és szelepet.

## 10. FLOW_PATH
- Eredeti: Trace the process flow path from BV-1-9 to GV-13-2. List every equipment item and valve in order.
- 1: Can you walk me through the process flow path from BV-1-9 to GV-13-2, listing every piece of equipment and every valve in order?
- 2: flow path BV-1-9 to GV-13-2, all equip + valves in order
- 3: Trace the process flow route from BV-1-9 through to GV-13-2, enumerating each equipment item and valve in sequence.
- 4: Kövesd végig a technológiai áram útját a BV-1-9-től a GV-13-2-ig, és sorold fel sorrendben az összes berendezést és szelepet.

## 11. INSTRUMENTS_OF_ITEM
- Eredeti: Which instruments measure E-30-3?
- 1: What instruments are measuring E-30-3?
- 2: instruments on E-30-3?
- 3: Which instruments are associated with the measurement of E-30-3?
- 4: Mely műszerek mérik az E-30-3-at?

## 12. INSTRUMENTS_OF_ITEM
- Eredeti: Which instruments measure T-16-3?
- 1: What instruments are measuring T-16-3?
- 2: instruments on T-16-3?
- 3: Which instruments are associated with the measurement of T-16-3?
- 4: Mely műszerek mérik a T-16-3-at?

## 13. LOOKUP_TYPE
- Eredeti: What type of item is LT-19-3?
- 1: What kind of item is LT-19-3?
- 2: LT-19-3 item type?
- 3: How is LT-19-3 classified in terms of item type?
- 4: Milyen típusú elem az LT-19-3?

## 14. LOOKUP_TYPE
- Eredeti: What type of item is V-27-2?
- 1: What kind of item is V-27-2?
- 2: V-27-2 item type?
- 3: How is V-27-2 classified in terms of item type?
- 4: Milyen típusú elem a V-27-2?

## 15. LOOKUP_UNIT
- Eredeti: Which unit is CHV-21-4 located in?
- 1: Which unit is CHV-21-4 in?
- 2: CHV-21-4 which unit?
- 3: In which unit is CHV-21-4 situated?
- 4: Melyik egységben található a CHV-21-4?

## 16. LOOKUP_UNIT
- Eredeti: Which unit is PIC-13-4 located in?
- 1: Which unit is PIC-13-4 in?
- 2: PIC-13-4 which unit?
- 3: In which unit is PIC-13-4 situated?
- 4: Melyik egységben található a PIC-13-4?

## 17. LOOPS_NEAR_ITEM
- Eredeti: Which control loops act on valves directly connected to C-20-1?
- 1: What control loops work on the valves that are directly connected to C-20-1?
- 2: control loops on valves directly connected to C-20-1?
- 3: Which control loops act upon the valves directly connected to C-20-1?
- 4: Mely szabályozó körök hatnak a C-20-1-hez közvetlenül csatlakozó szelepekre?

## 18. LOOPS_NEAR_ITEM
- Eredeti: Which control loops act on valves directly connected to V-18-5?
- 1: What control loops work on the valves that are directly connected to V-18-5?
- 2: control loops on valves directly connected to V-18-5?
- 3: Which control loops act upon the valves directly connected to V-18-5?
- 4: Mely szabályozó körök hatnak a V-18-5-höz közvetlenül csatlakozó szelepekre?

## 19. LOOP_ACTUATED_VALVE
- Eredeti: Which valve is actuated by control loop LIC-18-3?
- 1: What valve does control loop LIC-18-3 actuate?
- 2: LIC-18-3 drives which valve?
- 3: Which valve is operated by control loop LIC-18-3?
- 4: Melyik szelepet működteti az LIC-18-3 szabályozó kör?

## 20. LOOP_ACTUATED_VALVE
- Eredeti: Which valve is actuated by control loop TIC-41-3?
- 1: What valve does control loop TIC-41-3 actuate?
- 2: TIC-41-3 drives which valve?
- 3: Which valve is operated by control loop TIC-41-3?
- 4: Melyik szelepet működteti a TIC-41-3 szabályozó kör?

## 21. LOOP_MEASURED_EQUIPMENT
- Eredeti: Which equipment item does control loop LIC-31-5 measure?
- 1: What piece of equipment is control loop LIC-31-5 measuring?
- 2: LIC-31-5 measures which equip?
- 3: Which equipment item is the subject of measurement by control loop LIC-31-5?
- 4: Melyik berendezést méri az LIC-31-5 szabályozó kör?

## 22. LOOP_MEASURED_EQUIPMENT
- Eredeti: Which equipment item does control loop LIC-33-5 measure?
- 1: What piece of equipment is control loop LIC-33-5 measuring?
- 2: LIC-33-5 measures which equip?
- 3: Which equipment item is the subject of measurement by control loop LIC-33-5?
- 4: Melyik berendezést méri az LIC-33-5 szabályozó kör?

## 23. NEIGHBOURS_DOWNSTREAM
- Eredeti: Which equipment items and valves receive flow directly from GV-28-8?
- 1: What equipment and valves get flow straight from GV-28-8?
- 2: equip + valves directly downstream of GV-28-8?
- 3: Which equipment items and valves are fed directly by GV-28-8?
- 4: Mely berendezések és szelepek kapnak közvetlenül áramot a GV-28-8-ból?

## 24. NEIGHBOURS_DOWNSTREAM
- Eredeti: Which equipment items and valves receive flow directly from P-23-1?
- 1: What equipment and valves get flow straight from P-23-1?
- 2: equip + valves directly downstream of P-23-1?
- 3: Which equipment items and valves are fed directly by P-23-1?
- 4: Mely berendezések és szelepek kapnak közvetlenül áramot a P-23-1-ből?

## 25. NO_PATH
- Eredeti: Trace the process flow path from V-34-2 to TK-50-6. List every equipment item and valve in order.
- 1: Can you trace the process flow path from V-34-2 to TK-50-6 and list all the equipment and valves in order?
- 2: flow path V-34-2 to TK-50-6, all equip + valves in order
- 3: Trace the process flow route from V-34-2 to TK-50-6, enumerating each equipment item and valve in sequence.
- 4: Kövesd végig a technológiai áram útját a V-34-2-től a TK-50-6-ig, és sorold fel sorrendben az összes berendezést és szelepet.

## 26. NO_PATH
- Eredeti: Trace the process flow path from P-11-5 to P-20-1. List every equipment item and valve in order.
- 1: Can you trace the process flow path from P-11-5 to P-20-1 and list all the equipment and valves in order?
- 2: flow path P-11-5 to P-20-1, all equip + valves in order
- 3: Trace the process flow route from P-11-5 to P-20-1, enumerating each equipment item and valve in sequence.
- 4: Kövesd végig a technológiai áram útját a P-11-5-től a P-20-1-ig, és sorold fel sorrendben az összes berendezést és szelepet.

## 27. SAME_UNIT
- Eredeti: Are E-12-1 and E-12-4 in the same unit?
- 1: Are E-12-1 and E-12-4 both in the same unit?
- 2: E-12-1 & E-12-4 same unit?
- 3: Are E-12-1 and E-12-4 located within the same unit?
- 4: Ugyanabban az egységben van az E-12-1 és az E-12-4?

## 28. SAME_UNIT
- Eredeti: Are E-19-5 and TK-17-4 in the same unit?
- 1: Are E-19-5 and TK-17-4 both in the same unit?
- 2: E-19-5 & TK-17-4 same unit?
- 3: Are E-19-5 and TK-17-4 located within the same unit?
- 4: Ugyanabban az egységben van az E-19-5 és a TK-17-4?

## 29. SHEETS_OF_TAG
- Eredeti: On which sheets is P-23-1 drawn?
- 1: Which sheets show P-23-1?
- 2: P-23-1 which sheets?
- 3: On which drawing sheets does P-23-1 appear?
- 4: Mely lapokon van ábrázolva a P-23-1?

## 30. SHEETS_OF_TAG
- Eredeti: On which sheets is T-32-2 drawn?
- 1: Which sheets show T-32-2?
- 2: T-32-2 which sheets?
- 3: On which drawing sheets does T-32-2 appear?
- 4: Mely lapokon van ábrázolva a T-32-2?

## 31. UNANSWERABLE_TAG
- Eredeti: What type of item is FV-48-5?
- 1: What kind of item is FV-48-5?
- 2: FV-48-5 item type?
- 3: How is FV-48-5 classified in terms of item type?
- 4: Milyen típusú elem az FV-48-5?

## 32. UNANSWERABLE_TAG
- Eredeti: Trace the process flow path from V-13-7 to GV-12-10. List every equipment item and valve in order.
- 1: Can you trace the process flow path from V-13-7 to GV-12-10 and list all the equipment and valves in order?
- 2: flow path V-13-7 to GV-12-10, all equip + valves in order
- 3: Trace the process flow route from V-13-7 to GV-12-10, enumerating each equipment item and valve in sequence.
- 4: Kövesd végig a technológiai áram útját a V-13-7-től a GV-12-10-ig, és sorold fel sorrendben az összes berendezést és szelepet.

## 33. UPSTREAM_ISOLATION
- Eredeti: To isolate T-26-1 from all upstream equipment, which valves must be closed?
- 1: Which valves do I need to close to isolate T-26-1 from everything upstream?
- 2: valves to close to isolate T-26-1 from all upstream equip?
- 3: Which block valves must be closed in order to isolate T-26-1 from all upstream equipment?
- 4: Mely szelepeket kell zárni, hogy a T-26-1-et leválasszuk az összes felette (áramlási irányban előtte) lévő berendezésről?

## 34. UPSTREAM_ISOLATION
- Eredeti: To isolate T-13-5 from all upstream equipment, which valves must be closed?
- 1: Which valves do I need to close to isolate T-13-5 from everything upstream?
- 2: valves to close to isolate T-13-5 from all upstream equip?
- 3: Which block valves must be closed in order to isolate T-13-5 from all upstream equipment?
- 4: Mely szelepeket kell zárni, hogy a T-13-5-öt leválasszuk az összes felette (áramlási irányban előtte) lévő berendezésről?

## 35. UPSTREAM_SOURCES
- Eredeti: Which source items, with nothing flowing into them, ultimately feed TK-23-4?
- 1: What are the starting points, the sources with nothing feeding into them, that eventually end up feeding TK-23-4?
- 2: ultimate source items (no inflow) feeding TK-23-4?
- 3: Which source items, having no inflow, are ultimately upstream of TK-23-4?
- 4: Mely forráselemek, amelyekbe nem folyik be semmi, táplálják végső soron a TK-23-4-et?

## 36. UPSTREAM_SOURCES
- Eredeti: Which source items, with nothing flowing into them, ultimately feed V-39-1?
- 1: What are the starting points, the sources with nothing feeding into them, that eventually end up feeding V-39-1?
- 2: ultimate source items (no inflow) feeding V-39-1?
- 3: Which source items, having no inflow, are ultimately upstream of V-39-1?
- 4: Mely forráselemek, amelyekbe nem folyik be semmi, táplálják végső soron a V-39-1-et?
