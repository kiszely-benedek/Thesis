---
topic: Public real and professionally drawn P&ID sheets, downloaded and hand-inventoried, as a reference set for generator v2
date: 2026-10-25
status: draft, researcher agent
question: >
  Which real (or realistic, professionally drawn) P&IDs can be downloaded from public sources, and what do they show,
  sheet by sheet, about equipment, valves, ISA instruments, control schemes, trims, utilities, off-sheet connectors and
  tag/line-number formats? Which of generator v2's declared parameters do they confirm, contradict or let us calibrate?
related: [10-literature/real-pid-composition-2026-10.md, 10-literature/real-pid-data-sweep-2026-10.md,
          10-literature/pid-structural-rules.md, 40-design/generator-v2-realism.md, ADR-0057]
local_copy: C:/Users/Otthon/Desktop/valos-pid-mintak/ (outside the repository; MANIFEST.csv lists every file)
---

# Real P&ID samples: download set and hand inventory

## 0. How to read this note

- **Every count in §3 was hand-counted by me from the rendered image**, in this session, from the files in the local
  folder (path in the front matter). I render PDF pages with PyMuPDF at 60–220 dpi and read them as images. Where a
  sheet is too dense or too low-resolution to be sure, the entry says so and gives a lower bound (`≥`) or leaves the
  item uncounted. I did not count anything I could not see.
- Tags: **[HC]** hand count from the image; **[R]** read as text on the drawing (tag, title, note); **[U]** my
  interpretation (for example, calling a set-point link a cascade). Earlier-session facts are **[P]** (from the two
  sibling notes, not re-opened).
- This note does **not** repeat `real-pid-composition-2026-10.md` (vocabulary, PID2Graph statistics, papers) or
  `real-pid-data-sweep-2026-10.md` (DEXPI XML, datasets). It adds drawings and what is on them.
- "Sheet" = one drawing page. Inventory IDs (H1, D1, …) are used in all tables.

## 1. Bottom line

1. **Collected: 31 drawing files, 225 pages, from 11 source families** (DEXPI, OPEN100, three US/Canadian municipal
   bid sets, Hanford WTP, Hanford HWVP, a UT Austin dissertation, an AIChE/Ford, Bacon & Davis deck, Wikimedia
   Commons, CSB). The two Hanford sets alone give **35 + 128 large-format pages** of real plant P&IDs (Bechtel 2019,
   Fluor Daniel 1990). Total 58 MB. [HC of files/pages]
2. **16 sheets of distinct process types were inventoried** (§3). The real refinery/gas-plant content is thin:
   one as-built NGL depropanizer P&ID (El Paso Eunice gas plant, at ~1150 px only) and one fired-heater archive
   P&ID, both inside the FB&D teaching deck. **No public compressor-stage (anti-surge) P&ID and no flare-header P&ID
   was found** from the sources reachable today (§6).
3. **What the sheets confirm in the v2 design:** check-then-block on pump discharge; PI between pump and check;
   PSV with car-sealed-open blocks to a relief header; thermal-relief PSVs on the cooling-water side of
   exchangers; utilities as off-sheet stubs naming the partner drawing (never headers on the unit sheet); A/B(/C)
   installed spares; line numbers carrying size, service, spec and insulation.
4. **What they contradict:** (a) "no cascade loops" (§7 of the design) — cascades are the *common* scheme on the
   real process sheets (four on the depropanizer alone, one level-to-flow cascade on a Hanford pump sheet);
   (b) `min_equipment_per_sheet = 3` — 4 of the 16 inventoried sheets carry one or two equipment items, and
   `max_equipment_per_sheet = 10` — the Covestro sheet carries 16; (c) on-off valves are not always `XV`
   (Hanford and HWVP use `YV`); (d) steam condensate does not always leave through a steam trap (Hanford uses a
   drain pot with level control).
5. **What they let us calibrate (small samples, stated as such):** spare pattern of pump sets, triple share,
   bypass rate of control-valve stations, off-sheet connectors per sheet, signal off-sheet connectors. See §5.
6. **Real sheets are not one style.** Five unrelated line-number grammars, five equipment-tag grammars and at least
   two instrument-drawing conventions (ISA bubbles vs SCADA/PLC/FIELD bands in US wastewater) appear in 16 sheets.
   Wastewater sheets carry **no line numbers at all** (size + service only).

## 2. What was collected

Full row-per-file list with URL, publisher, licence text and process type: `MANIFEST.csv` in the local folder.
Summary:

| Folder | Source | Files / pages | Licence or copyright **as stated** | Real or teaching |
|---|---|---|---|---|
| `dexpi/` | DEXPI e.V. Public Example PIDs, gitlab.com/dexpi/TrainingTestCases | 8 drawings (C01 ×2 versions, C02, C03, C04, C05, C08 ×2) | CC BY 4.0 (repo LICENSE); C08 title blocks also print "CONFIDENTIAL"/"INTERNAL" and "Copyright acc. ISO 16016" | demonstrators; C02 (BASF), C03 (Equinor), C08 (Covestro) industry-authored |
| `open100/` | Energy Impact Center, open-100.com | 12 PNG | none stated; "INFORMATION ONLY – NOT FOR CONSTRUCTION …" notice [P]; PID2Graph redistributes CC BY-SA 4.0 [P] | professional open design, not built |
| `wenatchee_wwtp/` | City of Wenatchee WA, WWTP Digester #4 bid set (Oct 2021, RH2/HDR) | 12 pages (legend + 11 P&IDs), extracted from a 167-page set | none found in the extracted text → **unclear** | real plant |
| `valdosta_wpcp/` | City of Valdosta GA, Withlacoochee WPCP (CDM Smith) | 3 pages (2 legends + 1 P&ID) | "© 2022"; "… PROPERTY OF CDM SMITH AND ARE NOT TO BE USED … FOR ANY OTHER PROJECT WITHOUT THE WRITTEN AUTHORIZATION OF CDM SMITH" | real plant |
| `southwest_middlesex_ps/` | Municipality of Southwest Middlesex ON, Glencoe Industrial Park SPS (Stantec) | 4 pages (3 legends + P&ID DI-101) | "The Copyrights to all designs and drawings are the property of Stantec. Reproduction or use … forbidden." | real plant |
| `ut_austin_srp/` | E. Chen, PhD dissertation, UT Austin 2007 | 4 figures (absorber/stripper P&IDs, two campaigns) | "Copyright by Eric Chen 2007" | real pilot plant, simplified |
| `hanford_wtp_bof/` | Hanford Administrative Record AR-03207 (DOE ORP / Bechtel, Oct 2019) | 47 pages, 35 large-format P&IDs (24590-BOF-M6-DEP/DVP) | none stated → **unclear** (contractor drawings in a public record) | real plant |
| `hanford_hwvp/` | Hanford record D196016874 (DOE Richland / Fluor Daniel, 1990) | 136 pages, 128 large-format (TOC, legends, ~120 P&IDs) | stamped "FOR INFORMATION ONLY"; no licence → **unclear** | real plant (design stage) |
| `fbd_aiche/` | Ford, Bacon & Davis, "Art of the P&ID", AIChE 2019 | 94 slides, 14 with P&IDs | none found in the PDF text → **unclear** | vendor teaching deck; slides 65–71, 80–82 are real archive P&IDs, 74–77 templates |
| `wikimedia/` | Wikimedia Commons (users Ub, Evinfo) | 3 images | CC BY-SA 3.0 | teaching |
| `csb/` | US CSB, Williams Geismar case study (Oct 2016) | 2 pages (fig. 4, fig. 23) | none stated; US federal agency publication (public domain under 17 U.S.C. §105 is my reading) | simplified schematic, not a P&ID |

**Usability for the thesis.** Only DEXPI (CC BY 4.0) and Wikimedia (CC BY-SA 3.0) carry an open licence. Valdosta,
Southwest Middlesex and Chen carry explicit copyright; Wenatchee, Hanford, FB&D are unclear. All are fine as a
*private reference set* for designing the generator; figures reproduced in the thesis should come from the
CC-licensed ones, or be cited as "redrawn after".

## 3. Hand inventory (16 sheets, distinct process types)

All counts [HC] unless marked. "Off-sheet" = labelled continuation arrows; "signal off-sheet" = instrument-signal
continuations, counted separately where present.

### 3.1 Summary table

| ID | Sheet (file, page) | Process | Equip. | Valves | Instr. (approx. bubbles) | Loops / schemes seen | Off-sheet (process + signal) | Resolution |
|---|---|---|---|---|---|---|---|---|
| H1 | Hanford WTP 24590-BOF-M6-DEP-00003002 rev 2 (AR-03207 p22) | evaporator steam reboiler | 1 | 14 manual (6 inline, 5 drain, 2 vent, 1 instrument-air) + 1 CV | 16 | level feedback on condensate pot; TC → steam PC on utility sheet [U: cascade]; conductivity HH trip | 5 + 6 | native ~150 dpi, fully legible |
| H2 | WTP DEP-00003004 (AR-03207 p24) | condensers + 2-stage steam ejectors | 9 | ≥30 manual (not fully counted); 2 PV, 3 YV on-off; 2 PSV + 3 PSE | ≥60 | pressure feedback ×1; level LC-8251A/B → 2 LVs off-sheet | ≥8 + ≥4 | legible, very dense |
| H3 | WTP DEP-00002003 (AR-03207 p17) | transfer pumps A/B | 2 | per pump: suction block, discharge check + block, 1 vent, 2 drains; header: 2 blocks + bypass around flowmeter, 1 RO, LV | 25 | **level → flow cascade** (LC-8211 → FC-8182 → LV-8211); pump permissive interlock | 3 + 5 | legible (top 80 % viewed) |
| D1 | Covestro UER-1234567 (DEXPI C08) | reaction section with distillation | 16 | 72 manual (AB002–AB065, AH001–004, AG001–002, AK001, AR001) + 8 actuated + 1 safety valve | 40 | flow, temperature, level, pressure feedback; PIC → two valves [U: split range]; multivariable UC | 16 + 0 | vector, legible |
| D2 | Covestro UER-2345678 (DEXPI C08) | feed vessel + agitated reactor | 4 | 6 manual + 1 actuated | 5 | FIC, PIC, LIC | 2 | vector |
| D3 | BASF C02 process column (DEXPI) | packed column | 1 | 3 manual | 3 | redundant safety pressure A/B → PIS*Z*A | 1 | legible |
| O1 | OPEN100 ACW PID 210 sheet 2/2 | utility: cooling-water distribution | 1 | 5 MOV, 1 TCV, 2 untagged actuated, 1 PSV, 2 check | 5 | none drawn as loops | 11 | 3194 px, legible |
| W1 | Wenatchee 000Y-06 (p7) | digester gas + waste gas burner (flare) | 4 new + ~9 existing (grey) | 2 PRV + 2 flame arresters on digester; burner: 3 solenoid, back-flash preventer; FCV-550-01 | ~15 field + SCADA block | none as closed loops (PLC-mediated) | 3 | vector |
| W2 | Wenatchee 000Y-08 (p9) | hot-water heating utility | 5 new pumps + ~9 existing | per pump: block, flex conn., check, block; 3 TCV | 5 PI + 5 PE + 5 motor I/O blocks | none drawn | 9 | vector |
| V1 | Valdosta I-3 (p3) | belt filter press + polymer | 6 + 3 existing | 4 (SV ×3, BV ×1) | ~30 incl. panel HS | PLC I/O list only | ~8 (battery-limit) | vector |
| F1 | FB&D slide 81 "Archive P&ID (Fired Heater)" | fired heater + fuel-gas train | 3 | ≥6 manual, 4 XV, 3 PCV | ~13 + ~8 logic boxes | TIC; BMS trips (PSL, PSH, flame scanner → XVs) | 3 | embedded raster; small items uncertain |
| F2 | FB&D slide 65 = El Paso Eunice Gas Plant, EUAP107D sheet 13 of 30, depropanizer, rev 6 as-built | NGL fractionation (refinery-type column) | 4 | ≥4 CV stations with block + bypass, ≥6 CVs, 1 PSV, 2 steam-trap stations; manual valves not countable | ≥45 (incl. ≥8 TW) | **4 cascades** (TC → FC steam; LIC → FC ×2; AIC → TIC); PIC → PIC on other sheet | 13 | 1146×744 px raster: **lower bounds only** |
| F3 | FB&D slides 74–75 | standard templates: centrifugal pump, pressure vessel | 1 + 1 | see §4 | 3 + 4 | HOA/S-S motor switches | — | legible |
| U1 | Chen 2007 fig. 2-23 | CO₂ stripper pilot (absorber/stripper) | 9 | 6 control valves, no manual valves, no PSV | ≈28 (19 TT) | flow and temperature feedback | 5 (text arrows) | vector |
| HW1 | HWVP H-2-123051 sheet 1, SRAT (D196016874 p23) | slurry receipt/adjustment tank with condenser (nuclear vitrification) | 3 | ≥8 actuated (FV, TV, YV), manual not countable | ~60 (±5) | flow, temperature (3-way TV) feedback; FIC → YIC set point [U]; numbered interlocks | ~21 | 1990 scan, legible with effort |
| WM | Wikimedia "Schéma P&ID" (Evinfo) | water tank heating/level | 1 | 4 HV, 2 solenoid, 1 TV, 1 LV | ~20 | LT → LC → LIC → LV; TT → TC → TV; LAHH/LSH → HMS | 1 | 3344 px, left part viewed only |

### 3.2 Instruments by ISA function letters (selected sheets, [HC])

| ID | Letters seen (count where countable) |
|---|---|
| H1 | TE 2, TT 2, TI 2 (H, HH alarms), TC 1; LT 1, LI 1 (H, L), LC 1, LV 1; CE 1, CT 1, CI 1 (H, HH), CSHH 1; CY (logic) 1 |
| H2 | PT 6, PI 7, PDI 2, PC 1, PSLL 1; TE 3, TT 3, TI 7; FT 3, FI 3; LT 1, LI 1, LSL 1, LC 2; ZSL 3, ZSH 3, HS 3, YC 3, ZI 3, YY 3, YV 3; PSV 2, PSE 3 |
| H3 | PT 1, PI 1 (HH, H, L, LL), PSLL 1, PSHH 1; FT 1, FI 1 (L, LL), FSLL 1, FQI 1, FC 1; LC 1 (from another sheet), LV 1; HS 10 (A/M, S/S, L/R, START, STOP, D/S, RESET), YC 2, YI 2; 3 interlock diamonds |
| D1 | FRC 3, FIR 1, FI 1, FQI 1; TRC 3, TI 8; PRC 1, PIC 1, PDI 1, PI 6; LRC 1 (AH, AL), LIC 1, LI 3 (AH, AL); UC 1; YS 8 (actuated valves) |
| D3 | PI(Z) 2 (275003A/B), PIS*Z*A 1 |
| F2 | TE ≥3, TT ≥3, TC/TIC ≥3, TW ≥8; FE ≥4, FT ≥4, FY ≥4, FV ≥5, FC ≥5; LT 2, LIC 2, LG 1; PT 1, PIC 1, PI 2; AE ≥2, AT ≥2, AX 2, AIC ≥2; VSH 2; PSV 1 |
| HW1 | FT, FE, FY, FV, FI (5), FSH (3), FSL, FC, FIC (3), FQI, FAL; TE (2 multipoint), TW, TV (4), TY, TIC, TJI, TI; LT, LI; YIC (4), YV (3), YY (2); ZSH, ZSL; SC, IT, II; radiation XS, RIA, RSH, XL, RLH, RI, RAH, RC, RT, XA |

First letters seen across the 16 sheets: **A, C, F, H, I, J, L, M, P, Q, R, S, T, U, V, X, Y, Z** (18). [HC]

## 4. Standard trims observed (and how often)

| Trim | Where seen [HC] | Not seen / variant |
|---|---|---|
| Pump suction: block → strainer → reducer → pump | FB&D template (temporary strainer `SP-XXXX`); WTP H3 (block → item "NOTE 5" → reducer; strainer reading of NOTE 5 is [U]) | Wenatchee W2: block → flexible connector (no strainer); C08 D1: block only |
| Pump discharge: reducer → (PI tap) → **check → block** | FB&D template (PI on ¾" root before the check); WTP H3 (check + block, **no PI per pump**, PT on common header); Wenatchee W2 (PE/PI tap → check → block) | C08 D1: PI with root valve + block, **no check valve symbol identifiable** |
| Pump casing vent/drain | WTP H3 (1 vent + 2 drains per pump); FB&D template (¾" drains) | — |
| Minimum-flow recirculation through a restriction orifice | WTP H3 (`DEP-RO-00017` to "EVAPORATOR FEED RECIRCULATION") | — |
| Control-valve station with block valves **and bypass** | C08 D1: 5 of 8 actuated valves; FB&D F2: ≥4 | WTP H1, H3 and H2: control valves with blocks/drains but **no bypass** |
| PSV on vessel with car-sealed-open inlet/outlet blocks to relief header | FB&D template slide 75 (`CSO` both sides, ¾" bleed); FB&D F2 (PSV-605 → flare) | WTP: PSV/PSE "TO A SAFE LOCATION"; C08: safety valve AS001 to off-gas treatment |
| Thermal-relief PSV on cooling-water side of an exchanger | WTP H2 (PSV-8252, PSV-8253 set 100 psig on CW lines); OPEN100 O1 (PSV-xxx on the HX outlet) | — |
| Level instrument on a bridle with two isolation valves | FB&D template slide 75; WTP H1 (LT-8216 on the condensate pot) | — |
| Double block and bleed on fuel gas | FB&D F1 (XV – vent to atmosphere – XV on main burner line) | — |
| On-off valve with limit switches and solenoid | WTP H2 (YV + ZSL + ZSH + S + YY + HS/YC/ZI, "O/C"); HWVP HW1 (YV + S + YY, ZSH/ZSL) | tagged **YV**, not XV; FB&D F1 uses **XV** |
| Spectacle / skillet blinds as tagged items | FB&D F2 (`SKILLET #545`, `#546`, `#547`, `#720`) | — |
| Redundant transmitters A/B on one safety function | BASF D3 (`PI(Z) 275003A/B` → `PIS*Z*A 275003`) | — |

## 5. Comparison with generator v2's declared parameters (design §4–§7, §9)

"Sheets" in this table = the 16 inventoried sheets. These are small, heterogeneous samples; every statement
holds for the sheets named, not for "real P&IDs" in general.

| Design item | Design value | What the samples show | Verdict |
|---|---|---|---|
| §7.2 note: "no cascade loops", "no split-range loops" | excluded | Cascades on F2 (4: TC → FC, LIC → FC ×2, AIC → TIC), H3 (LC → FC → LV), H1 (TC → steam PC on the utility sheet [U]), HW1 (FIC → YIC set point [U]); split range possible on D1 (PIC P0022 → two valves [U]) | **Contradicted for cascade**: on the two real process sheets with dense control (F2, H3) cascade is the scheme of the level and temperature loops. Split range: one unconfirmed case |
| §9 `min_equipment_per_sheet` | 3 | Sheets with 1–2 equipment items: H1 (1), H3 (2), D3 (1), O1 (1) | **Contradicted**: one-item sheets exist on real sets (reboiler alone, pump pair alone) |
| §9 `max_equipment_per_sheet` | 10 | D1 has 16 tagged equipment items (6 pumps, 5 exchangers, 4 vessels, 1 column); H2 has 9; F2 has 4 | **Contradicted at the top end** (one sheet); 10 covers 15 of 16 sheets |
| §9 FB&D layout rule (one column per sheet, pumps with suction vessel) | adopted | D1 and F2 each hold exactly one column; D1 draws all its pumps on the column sheet; WTP puts each pump set on **its own sheet** (H3, and six more pump-set sheet titles in AR-03207) | **Confirmed for columns**; the "pumps with suction vessel" rule is company-specific (WTP separates them) |
| §7.1 `p_triple_pump_set` | 0.15 | WTP AR-03207 sheet titles name 8 lettered pump sets: 3 A/B/C (00012, 00004, 00015) and 5 A/B (00002, 00007, 00006, 00003, 00042) [R]; Covestro D1: 3 parallel pairs, 0 triples; Wenatchee W2: 2 pairs; SW Middlesex: 1 pair | **Calibrate within a range**: 3 of 8 (WTP) to 0 of 6 (others). 0.15 sits inside it |
| §7.1 `p_single_pump` | 0.2 | WTP: ≥1 unspared pump referenced (DEP-PMP-00017) against 8 spared sets; W2: 1 single (boiler circ. pump) against 2 pairs; D1: 0 singles among 6 pumps | 0.2 is plausible; samples range 0 to 1/3 |
| §5 spare naming `P-1203A/B` | A/B/C suffix | WTP, FB&D (P-551A/B), OPEN100 [P] use A/B/C; **Covestro numbers spares consecutively** (PA100/PA101, PA102/PA105, PA103/PA104); Wenatchee numbers them "No. 1 / No. 2" with consecutive tags (PMP-510-06/-07) | **Partly contradicted**: two of five tag styles do not use a suffix, which makes spare identity a harder (and realistic) resolver case |
| §6.7 `p_cv_station` (block + bypass) | 0.8 | D1: 5 of 8; F2: ≥4 of ≥6; WTP H1/H2/H3: 0 of 4 with bypass | **Company-dependent**: ≈ 0.6–0.7 on two sheets, 0 on WTP. Keep as a parameter; sweep it |
| §6.3 PI between pump nozzle and check | always | FB&D template, W2: yes; D1: PI yes, check not seen; WTP H3: no PI per pump | Mostly confirmed; WTP replaces it with a header PT |
| §6.10 PSV with blocks car-sealed open | `p_psv_blocks` 0.5 | FB&D template: CSO inlet and outlet; F2: single PSV, blocks not legible | Confirmed as a convention; frequency not countable |
| §6.14 thermal relief on CW return | `p_thermal_relief` 1.0 for CW coolers | H2: 2 PSVs on the CW side of the condensers; O1: PSV on the HX outlet | Confirmed on both sheets with CW consumers |
| §6.14 steam consumer: `SteamTrap` before the block | always for steam | F2: trap **station** (trap + blocks + bypass) on both reboilers; H1: **condensate drain pot with LT/LC/LV**, no trap; U1: no trap drawn | **Two real variants**; add the level-controlled condensate pot as a variant of 6.14 |
| §6.9 on-off valve tagged `XV`, solenoid `XY` | XV | WTP and HWVP: **YV** with solenoid "S" and **YY**; FB&D F1: XV; D1: YS (DIN-style) | **Contradicted as a universal**: the on-off tag letter is company-specific (X or Y) |
| §4.4 first letters A B F H L P S T V X Z | 11 letters | 18 first letters seen (§3.2); additions with real weight: **C** (conductivity, H1), **Y** (event/relay valves), **Z** (positions), **R** (radiation, HWVP), **U** (multivariable, D1, W2), **I**, **J**, **M**, **Q** | Extend by C, Y and U if cheap; R is nuclear-specific |
| §4.4 alarm/trip letters | `xAH`, `xSHH`, `xSLL` | PSLL, PSHH, FSLL, LSHH, LSLL, LSLLL, CSHH (H3, H1); alarms as letters **beside** the bubble (H, HH, L, LL) on WTP and FB&D | Confirmed; real sheets often write alarm levels next to an indicator instead of a separate xAH tag |
| §5 line number `SIZE-SVC-uSEQ4-SPEC-INS` | one grammar | WTP: `HPS-DR-00083-S11C-12` (system–fluid–seq–spec–size); El Paso: `P-12"-48D02-1070-03-H` (service–size–spec–drawing–seq–insulation); HWVP: `LPV-1"-480-340-G`; Covestro: `LA01-LR024.10000-25-10H1200 NV 221`; OPEN100: `SIZE-ACW-102160-SPEC-HC-X`; wastewater: **size + service only** (`6"-DG`, `1"-POLY`) | The design grammar is close to the El Paso one. Size position (first vs last) and the presence of a line number at all vary by company |
| §6.13/6.14 utility stubs "by descriptive title only" | open stub with service code | Every utility on every process sheet is an off-sheet arrow naming **service + source/destination equipment + partner drawing (and grid zone)**: H1, H2, D1, F2, HW1 | Confirmed, and richer: the stub names the utility *equipment* (e.g. `PCW-PMP-00030A/B`) on the utility P&ID, i.e. a cross-sheet identity hook the resolver could use |
| §9.5 / composition note: off-page per sheet ≈ 8.0 (OPEN100) | target 8.0 | 16 (D1), 13 (F2), ~21 (HW1), 11 (O1), 9 (W2), 5 + 6 signal (H1), 3 + 5 signal (H3), 3 (F1), 2 (D2), 1 (D3) | 8.0 is within the observed spread (1–21); signal off-sheet connectors are common on WTP sheets (5–6 per sheet) |
| §7.2 U3 fired heater: `BE → BSL → XV` flame trip | template | F1: flame scanner + PSL/PSH → burner management → 4 XVs (double block and bleed), no BE/BSL tags | Scheme confirmed, tag letters differ (vendor BMS package) |
| §7.2 U2 compressor anti-surge | template | **No compressor P&ID found** | Not testable with this set |

## 6. Utility examples (task 5)

| # | Pattern | File | Page | What is drawn [R]/[HC] |
|---|---|---|---|---|
| 1 | **Cooling water supply and return to exchangers, both ends referenced** | `hanford_wtp_bof/AR-03207_….pdf` | 24 (24590-BOF-M6-DEP-00003004) | Left edge: "COOLING WATER SUPPLY / PCW-PMP-00030A/B / BOF-M6-PCW-00005002 E2", line `PCW-WS-20161-S11C-08`, a PCW\|DEP spec-break flag, on-off valve YV-8217 (NO/FO, ZSL/ZSH); thermal-relief PSV-8252 and PSV-8253 (set 100 psig) on the CW lines, discharging "TO SAFE LOCATION"; right edge: "COOLING WATER RETURN / PCW-HX-00025 / BOF-M6-PCW-00005002 3B" |
| 2 | **Cooling water seen from the utility P&ID** (header + consumer) | `open100/open100_auxiliarycoolingwater_3.png` | 1 (ACW PID 210, sheet 2 of 2) | ACW headers with MOVs; consumer CVCS-HX-111 with TE on inlet/outlet, PSV-xxx thermal relief and TCV-1115 on the outlet; 11 off-sheet arrows to RCS PID 100-2, SWS PID 130-1, WPS PID 270-1 |
| 3 | **Steam to reboiler, condensate via level-controlled drain pot** | `hanford_wtp_bof/AR-03207_….pdf` | 22 (DEP-00003002) | "SECONDARY STEAM / HPS-HX-00011 / BOF-M6-HPS-00023001 G2" in at the left edge, line `HPS-DR-00083-S11C-12`; condensate leaves the reboiler into a vertical drain pot with LT/LI/LC-8216 and LV-8216 (FC), conductivity CE/CT-8218 with CSHH (tube-leak trip), out as "REBOILER CONDENSATE / DEP-VSL-00008"; TC-8214 output goes off-sheet to `HPS-PC-8902` on the steam P&ID |
| 4 | **Steam to reboilers with steam-trap stations** (refinery/gas-plant style) | `fbd_aiche/FordBaconDavis_ArtOfThePID_AIChE_2019.pdf` | 65 | Two reboilers E-651, E-607-07: "60 LB STEAM" from off-sheet 118K → FE/FT → FV in a station with blocks and bypass; condensate → steam trap "T" with blocks and bypass → "LP CONDENSATE" off-sheet 118K; tray temperature TC cascades onto the steam flow controller. Low resolution |
| 5 | **Motive steam to vacuum ejectors** | `hanford_wtp_bof/AR-03207_….pdf` | 24 | "HIGH PRESSURE STEAM / BOF-M6-HPS-00022C01" with an HPS\|DEP spec-break flag, to ejectors DEP-EJCTR-00001A/B and -00002A/B |
| 6 | **Nitrogen purge as capped taps, not a header** | `wenatchee_wwtp/Wenatchee_….pdf` | 7 (000Y-06) | Two notes "NITROGEN PURGE TAP WITH ISOLATION VALVE, HANDLE REMOVED AND CAP" on the digester-gas lines. Contrast: Covestro `dexpi/C08_UER-1234567.pdf` p1 shows N₂ as off-sheet arrow 284 "N2 / LA01-BA002 / UER-2345678" |
| 7 | **Relief to flare / relief header** | `fbd_aiche/…pdf` | 65 and 75 | p65: PSV-605 4"×6" set 320 psig on the column overhead → "224AX-6" TO FLARE", off-sheet 1161. p75 (template): PSV with CSO inlet and outlet blocks → "TO RELIEF HEADER" |
| 8 | **Flare unit itself (waste gas burner package)** | `wenatchee_wwtp/Wenatchee_….pdf` | 7 | Waste gas burner with natural-gas pilot from an NG meter, solenoids, flame arresters, back-flash preventer, burner LCP CP-510-03, drip trap with electric actuator; digester PRV-550-01/02 behind flame arresters FA-550-01/02 |
| 9 | **Fuel gas train to a fired heater** | `fbd_aiche/…pdf` | 81 | NATURAL GAS [PI-012] → block, PCV, XV, vent "TO ATMOS", XV, PCV to main burner; separate pilot line with PCV + 2 XVs; PSL, PSH, 3 PI; burner management |
| 10 | **Instrument air at every actuator** | `hanford_wtp_bof/…pdf` | 17, 22, 24 | "ISA" with 3/8" tubing and a root valve `ISA-V-nnnnn` at each control/on-off valve. HWVP uses "IAS" (p23) |

**Pattern across all ten:** utility *headers* never appear on a process sheet. Each consumer has an off-sheet
arrow whose label names the utility service, the utility-side equipment or system, and the utility drawing (often
with grid zone). The header appears only on the utility system's own P&ID (example 2). This matches
`pid-structural-rules.md` C4 [P] and adds the detail that the label names the *partner equipment*.

## 7. Multi-sheet structure seen in the two Hanford sets

- **WTP AR-03207:** drawing numbers `24590-BOF-M6-DEP-000NNSSS` group sheets by system: families 00001 (2 sheets),
  00002 (6), 00003 (6), 00004 (3), 00005 (5), 00006 (4), 00009 (5), 00010, 00011, 00012 (1 each), plus DVP-00001
  [R, from the permit's revision table]. Off-sheet arrows cite drawing **and grid zone** (`BOF-M6-DEP-00003001 C8`).
- **HWVP D196016874:** the table of contents lists drawing numbers with many sheets each, e.g. `H-2-123060`
  sheets 1–34 (System 20, waste tanks and headers) and `H-2-123150` sheets 1–22 (System 13, melter) [R, OCR text of
  the TOC]. Arrows cite `H-2-123357-3 C5` (drawing–sheet + grid).
- Both confirm what OPEN100 showed [P]: partner references point to sheets outside any subset one happens to hold.
  These two sets are the largest real, public, multi-sheet P&ID collections found by this project so far (35 and
  ~120 sheets), but they are **scans/PDF, not DEXPI**, so they serve as composition references, not importer input.

## 7a. Equipment beyond fluid processing seen on the drawings (pyDEXPI families)

For the plan to cover every concrete pyDEXPI class. Only what I saw on a page is listed; "not seen" means not on any
page I viewed, not "does not exist".

| pyDEXPI family / class (closest) | Seen on | File, page | What is drawn [R]/[HC] |
|---|---|---|---|
| Conveyor (`Conveyor`) | yes | `valdosta_wpcp/…pdf` p3 | CNY-276-1, -2, -3 (screw/belt conveyors, existing, grey) each with motor M and YC/YI/YA, HS HOA on LCP-CNV |
| Truck loading (`Truck`, `LoadingUnloadingSystem`) | yes | `valdosta_wpcp/…pdf` p3 | truck under CNY-276-3 with three air-actuated discharge gates fed from "AIR FROM COMPRESSORS" (B/L) |
| Mechanical separator / filter press (`MechanicalSeparator`, `FilteringCentrifuge` is the nearest centrifuge-type) | yes (belt filter press, not a centrifuge) | `valdosta_wpcp/…pdf` p3 | BFP-910-1 belt filter press with HYD-911-1 hydraulic pack, belt limit switches LS-910-1A..1D, motor temperature switches |
| Motor as driver (`AlternatingCurrentMotor`) | yes, as a circle "M" on the pump/conveyor/agitator, never as a separate tagged equipment item | `dexpi/C08_UER-1234567.pdf` p1 (every pump), `C08_UER-2345678.pdf` (agitator of RA001), `wenatchee_wwtp/…pdf` p9 (pumps), FB&D p74 template | motor symbol + HS/MS bubbles; VFD diamonds on Valdosta p3 |
| Agitator (`Agitator`) | yes | `dexpi/C08_UER-2345678.pdf` p1; `hanford_hwvp/…pdf` p23 | RA001 agitated jacketed reactor with motor M and MS M0001; SRAT TK-120-001 with SC-106 / IT-109 (speed, current) |
| Mixer (`RotaryMixer`/`StaticMixer`) | yes (rotary, existing) | `wenatchee_wwtp/…pdf` p9 | boiler water treatment mixer M-8510 (grey) |
| Fan / blower (`CentrifugalBlower`, `RadialFan`) | yes | `fbd_aiche/…pdf` p81; `valdosta_wpcp/…pdf` p3; `hanford_wtp_bof/…pdf` p47 (title) | F-0007 combustion air fan, F-0008 quench gas fan; exhaust fans No. 1–4 with FSL-912; vessel vent exhausters DVP-EXHR-00001A/B |
| Air-cooler fans (`AirCoolingSystem`) | yes | `fbd_aiche/…pdf` p65 | E-608-07 with 2 fans and VSH vibration switches |
| Ejector (`AirEjector` / `EjectorPump`) | yes (steam ejectors) | `hanford_wtp_bof/…pdf` p24 | DEP-EJCTR-00001A/B, -00002A/B, two stages, motive HP steam |
| Boiler (`Boiler`) | yes (existing) | `wenatchee_wwtp/…pdf` p9 | BOILER BO-8331 with boiler circulation pump; "BOILER NO.2" referenced from p7 (sheet 000Y-09, not viewed) |
| Furnace / burner (`Furnace`, `Burner`) | yes | `fbd_aiche/…pdf` p81 | H-0001 sodium heater with burner, flame scanner, electric ignitor, burner management |
| Flare (`Flare`) | yes (small package) | `wenatchee_wwtp/…pdf` p7 | WASTE GAS BURNER package with NG pilot, flame arresters, back-flash preventer |
| Chimney / stack (`Chimney`) | yes, as a stack outlet only | `fbd_aiche/…pdf` p81 | heater stack "TO ATMOS" with TT/TI; burner stack on Wenatchee p7 |
| Dryer (`ConvectionDryer` etc.) | slide title only | `fbd_aiche/…pdf` p80 | "Archive P&ID (Dryer)" – not inventoried, low resolution |
| Transport inside plant (`MobileTransportSystem`, `StationaryTransportSystem`) | yes (nuclear-specific) | `hanford_hwvp/…pdf` p40 | drain turntable and transfer cart TU-130-002 with position switches ZS and load cell WE-102 |
| Gas filter (`GasFilter`) | yes | `hanford_wtp_bof/…pdf` p24 | HEPA vacuum breakers DEP-HEPA-00001A/B on C3 area air intake |
| Liquid filter (`LiquidFilter`) | yes (title) | `hanford_wtp_bof/…pdf` p18 | evaporator feed vessel prefilter DEP-FILT-00003 (title block) |
| Silo, feeder, crusher, grinder, mill, extruder, sieve, weigher, packaging, centrifuge proper, rail waggon, ship, forklift, cooling tower, steam/gas turbine, generator | **not seen** on any viewed page | — | the downloaded set is fluid-process and wastewater; OPEN100 main-steam/feedwater sheets probably show a turbine but were not viewed today |

## 8. Searched for and not obtained

| Item | What happened |
|---|---|
| NRC ADAMS drawing packages | HTTP 403 again for every URL tried (also with a browser User-Agent), as in the earlier sweep [P] |
| OSTI.gov full texts | TCP connection to www.osti.gov timed out from this machine |
| NREL / H2FIRST reference hydrogen-station P&IDs (compressor, storage, PSVs) | `www.nrel.gov` did not resolve (DNS); the DOE download page no longer links the P&ID files; only the 2015 webinar slides were reachable (P&IDs at slide resolution, not kept) |
| DTIC technical reports | returned an HTML interstitial instead of the PDF |
| BSEE incident report WD-105-E (offshore heater-treater "P&ID" figure) | downloaded and viewed; figure 3 is a heavily simplified vessel sketch, not a P&ID; not kept |
| OGDCL (Pakistan) tender P&IDs | tender files reference P&ID numbers; the one PDF fetched was 4.5 kB, no drawings |
| NASA NTRS test-stand P&IDs | NTRS API search returned 0–1 unrelated hits |
| A public compressor-stage (anti-surge) P&ID | **not found** |
| A public flare-header / flare-KO-drum P&ID | **not found** (only connections to a flare and one small waste-gas burner package) |
| A public crude/refinery-unit P&ID at full resolution | **not found**; the only refinery-type unit is the El Paso depropanizer at 1146×744 px inside the FB&D deck |
| Cognite Open Industrial Data (Aker BP Valhall P&IDs) | not attempted: requires account registration |
| Dataset-P&ID, PID2Graph samples | not downloaded again: synthetic or already held locally (`Desktop/Munka/PID2Graph`, `real-pid-data-sweep-2026-10.md` [P]) |

## 9. Caveats

1. **Sample, not statistics.** 16 sheets, 11 sources, mixed industries (wastewater, nuclear waste, chemicals, gas
   processing, power). The "verdicts" in §5 are existence proofs and ranges, never frequencies for "real plants".
2. **Refinery coverage is weak.** The two refinery-style sheets (F1, F2) come from a teaching deck at low
   resolution; their small-item counts are lower bounds.
3. **Nuclear/DOE drawing conventions** (remote cells, jumpers, radiation monitors, YV tags) are over-represented
   via the two Hanford sets.
4. **Existing-vs-new screening.** Wastewater bid sets draw existing equipment in grey; my counts separate new and
   existing where stated, and are less reliable for the grey items.
5. **Interpretations marked [U]** (cascade where a set-point arrow is drawn, split range where one controller feeds
   two valves, the strainer reading of WTP "NOTE 5") were not checked against the drawings' legends.
6. OPEN100 process descriptions in `MANIFEST.csv` come from the system page names; only ACW sheet 2/2 was viewed
   in this session. C03, C04, C05 and two Wikimedia images were downloaded but not inspected in detail.

## 10. Sources

Every source URL is in `MANIFEST.csv`. Primary ones:
- DEXPI Public Example PIDs, https://gitlab.com/dexpi/TrainingTestCases (CC BY 4.0), files listed via the GitLab API
  tree and downloaded from `-/raw/master/`.
- OPEN100, https://www.open-100.com/ system pages (PNG URLs on `static.wixstatic.com`).
- City of Wenatchee, Digester #4 contract drawings, https://omwbe.wa.gov/sites/default/files/bids/Drawings.pdf.
- City of Valdosta, Withlacoochee WPCP drawings vol. 2,
  https://www.valdostacity.com/sites/default/files/uploads/2025.10.03_withlacoochee_drawings_vol_2_0.pdf.
- Southwest Middlesex, Glencoe Industrial Park SPS,
  https://www.southwestmiddlesex.ca/sites/default/files/2026-03/165630252-Industrial-PS-IFT%20%284%29.pdf.
- E. Chen, PhD dissertation, UT Austin 2007, https://sites.utexas.edu/rochelle/files/2015/02/Chen-Dissertation.pdf.
- Hanford Administrative Record, https://pdw.hanford.gov/download/v2/AR-03207 and
  https://pdw.hanford.gov/download/v2/D196016874 (found with the PDW search, `keywords=piping+and+instrumentation+diagram`).
- Ford, Bacon & Davis, "Art of the P&ID", AIChE 2019,
  https://www.aiche.org/sites/default/files/community/262801/aiche-community-site-event/514546/artofthepid-aiche-rbt11-15-19.pdf.
- Wikimedia Commons, File:P&ID.JPG, File:Schéma P&ID.jpg, File:Schéma P&ID1.jpg (licence via the Commons API).
- US CSB, Williams Geismar case study, https://www.csb.gov/assets/1/6/Williams_Case_Study_2016-10-19.pdf.

Method: PyMuPDF 1.28.2 (page extraction, rendering), Pillow 11.1 (crops); scripts in the session scratchpad, run
with `python -I` from outside the download folder; nothing from the downloads was executed.
