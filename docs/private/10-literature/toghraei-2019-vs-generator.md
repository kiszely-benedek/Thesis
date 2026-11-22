---
topic: Toghraei, Piping and Instrumentation Diagram Development (Wiley/AIChE 2019), full text, compared rule by rule with generator v2.1
date: 2026-11-22
status: read in full except ch. 1-3, 5 and parts of 18-19 (skimmed); all 34 example sheets of ch. 20 viewed
related: [10-literature/pid-structural-rules.md (TOG was preview-only there), 40-design/generator-v2-realism.md, 40-design/generator-v2-pid-vocabulary.md, src/plantgraph/benchmark/v2]
note: page numbers are the printed book pages. GEN = generator v2.1 code. Paraphrased, no long quotes.
---

# Toghraei (2019) vs generator v2 — working notes

Printed page = PDF page − 19. Chapter files chNN.c.txt.

## Ch4 General rules (pp. 21–44)
- p.22 rule 2: main equipment per sheet: some companies 4–5, others up to 10. GEN: band 3–10, none >10 → CONSISTENT.
- p.22-24 rules 8–9: all elements on a sheet connected; "no visiting stream" (a stream with no connection to other items on the sheet). GEN: ? check whether sheets can contain a pass-through line with no connection (visiting stream) → CHECK.
- p.22 fittings shown: only tees, reducers, process flanges, cap/plug/blind flanges. GEN: PipeTee, PipeReducer, BlindFlange, LineBlind → CONSISTENT.
- p.26 off-page connectors: incoming left, outgoing right; utility connectors may sit next to the user. (layout only)
- p.30 SPARE TAGGING: two approaches: P-125A/P-125B, or unrelated numbers P-125/P-126; "the current trend is the second approach" (noise / emergency confusion). GEN: A/B only → DEVIATION (affects identity resolution + realism of A/B share band).
- p.30-31 sparing philosophy notation 2×100%, 3×50% etc. in callouts (equipment data, out of scope ADR-0021) but 3-in-parallel filters example.
- p.32-36 P&ID TYPES: legend; system (process + utility generation); network (utility distribution/collection, relief & blowdown, fire water, sewer, blanket gas, VRU) — mainly pipes, no equipment, follow plot plan; interarea (battery-limit / tie-point and interconnecting); detail (typical: seal flush, sampling, safety shower, utility station; nontypical: lube oil, F&G). GEN: only process system P&IDs; utilities/networks parked → DEVIATION for multi-sheet structure: in a real set many off-page connectors go to network/utility/relief P&IDs and typical detail P&IDs are referenced by many sheets (many-to-one).
- p.34 B/L isolation arrangement: blind; isolation valve+blind; isolation valve+blind+check valve. GEN 6.17: GateValve→LineBlind, p=0.5 → PARTLY (no check variant).
- p.36 B/L custody transfer (LACT) metering. GEN U4 metering skid → consistent in spirit.
- p.43 vendor packages: dash-dot border, flange break at border. GEN: not modelled (C8) → known gap.

## Ch6 Pipes (pp. 69–104)
- p.72-73 pipe tag anatomy: area/unit, commodity, spec, NPS, sequence, insulation, tracing, U/G-A/G; order company-specific. GEN: SIZE-SVC-uSEQ4-SPEC-INS → CONSISTENT.
- p.74 Table 6.4 commodity acronyms NG FW IA UA PA D V UW LPS MPS HPS HGS HGR CWS CWR; S/R suffix supply/return, H/M/L prefix. GEN SVC set → CONSISTENT (subset).
- p.72-73 Table 6.3: NOT tagged: short pipe to a plugged/blinded drain or vent valve; bypass pipe around a control valve. Tag = span between two equipment (or mid-point of another pipe); split only where T/P/fluid change warrants. "Pipe tag shown once per sheet." GEN: CHECK whether drains/vents and CV bypass get own line numbers.
- p.80-82 spec break: border = flange (default) / blocking valve / blocking valve+check; reasons (Table 6.5): CV or RO pressure drop, pump/compressor pressure rise, cooler/heater/fired heater, addition of a fluid (e.g. acid injection). Extension (Table 6.6): pump discharge high-pressure spec extended to first block valve on suction; acid spec extended to first block valve on water line; low-T spec 600–900 mm upstream of RO. GEN L20: spec break only at compressor discharge and letdown CV → PARTIAL (pump discharge, heaters, chemical injection, RO not encoded).
- p.84-86 backflow: check valve on discharge of centrifugal pumps & compressors (CONSISTENT); 2 checks 3000–7000 kPag, 3 above (needs pressure data, out of scope); backflow-preventer, air gap, inverted U (water).
- p.87 flow distribution to parallel users: CVs on all branches but one, or "symmetrical piping" note. GEN: CHECK splits (tank farm receipt, parallel trains).
- p.94 Table 6.7 strainers only upstream of tight-clearance items: centrifugal pumps, PD pumps, steam traps, turbine meters. Temporary: Y-type NPS<3, cone-type NPS>6; permanent: T-type / bucket. GEN: ConicalStrainer on centrifugal (temp), Strainer on PD/rotary (perm) → CONSISTENT; steam trap strainer missing (drip-leg exempt) → minor.
- p.92-93 steam traps on drip legs; isolation valves; bypass debatable/often forbidden. GEN 6.14 SteamTrap before block → OK.
- p.96 bypass of a unit: ≥1 block valve near start (+1 near end if long); trimmer (last unit in series) commonly bypassed. GEN U5 bypass around last exchanger → CONSISTENT.
- p.98-99 reducers: at pump suction/discharge, PSV inlet/outlet, control valves; shown as "4×2"; eccentric FOT on centrifugal pump suction, FOB on CV. GEN: reducers only around CV (p=0.5) → PARTIAL (pump/PSV reducers missing; very common on real sheets).
- p.100 end of pipe: cap/plug < 2", blind flange or welded cap > 2". GEN: BlindFlange on every vent/drain → minor (vent/drain valves are ¾–1", so cap/plug would be the realistic class).
- p.101-102 SP items: non-slam check, injection quill (chemical injection), flexible joint (tank connections > 4–6"), insulating gasket at dissimilar-metal spec break. GEN: none → minor gap (U8 dosing has no quill).
- p.97 parallel 2×50% branch size = header/√2; header sizes. GEN: no size logic on headers → minor.
- p.78 sizes: 2" practical minimum; main 6–26"; non-primary 2–6". GEN size set {1..24} → OK.

## Ch7 Valves (pp. 105–128)
- p.108 Fig 7.4/7.5 selection: blocking default GATE, BALL for small sizes (≤ ~3"), plug all sizes (less common, typical for HC gas); throttling default GLOBE, BUTTERFLY for large (>4–6"), NEEDLE small, ANGLE for high ΔP (>1000 kPa); butterfly common in water service; pinch/diaphragm for aggressive / hygienic. GEN: gate for blocks, ball root valves, butterfly large block, needle DP taps, angle letdown CV → MOSTLY CONSISTENT; but class is not tied to line size (a 1–2" block valve as GateValve is atypical) and plug valve in tank-farm manifold (book: HC gas) → minor.
- p.112-113 Table 7.9 automatic valve tags: control valve xV (FV…), hand control valve HCV; switching: KV (time/sequence), XV or UV (event), XV (remote manual shutoff). GEN: XV trip + HS→XV; no KV, no HCV → PARTIAL (KV belongs to filter backwash sequences — U7 has none).
- p.113 MANUAL VALVE TAGS: "Some companies do not tag their manual valves… in critical plants (nuclear, explosives, herbicide) it is common to see tagged manual valves." GEN: EVERY manual valve tagged (GTV-…, BV-…) — matches OPEN100 (nuclear) but not the typical process plant → IMPORTANT for question validity: valve-set answers by tag assume tagged manual valves.
- p.113-114 valve positions: blocking NO/NC, LO/LC (equipment protection), CSO/CSC (safety); default = NO unless marked; vents/drains NC; automatic FO/FC/FL/FI (high-energy streams FC, low-energy FO; min-flow CV FO). GEN: no position attribute (PSV blocks "car-sealed open" only in design text) → GAP: matters for isolation / flow-path questions (NC bypass and drains, CSO PSV blocks change the right answer).
- p.119-121 CV station: 2 block valves + bypass with manual GLOBE (butterfly or 2 globes if >4–6"); drain between blocks — 1 or 2 (debated; 2 for FC/toxic), vent on top for large lines; reducers on CV (eccentric FOB for aggressive liquid >3"); extra block before bypass in critical service; some companies: no bypass on PRESSURE control loops; spec break at CV station placed downstream of bypass and block valve. GEN 6.7 (p_cv_station 0.8, reducers 0.5, drain 0.3, bypass GlobeValve) → CONSISTENT; refinements: bypass class by size, PIC loops without bypass.
- p.122 switching-valve station rare; if present, bypass is a BLOCKING valve. GEN bare XV → CONSISTENT.
- p.118 series: manual block + manual throttle (toxic/HP); adjacent isolation valves of two close items merged into one; parallel small pressure-equalising/warm-up valve around big HP block valves (>3000 kPa).
- p.123-125 regulators (self-acting PCV/FCV/TCV/LCV), set point shown on P&ID, natural fail position, NO bypass, clean small services ≤6". GEN: none → GAP (typical on blanket gas, fuel gas, utility headers, seal systems).
- p.125-126 safety valves: PSV, vacuum relief, thermal relief, excess-flow valve (LPG); some tag check valves FSV.
- p.127 CV body typically ONE SIZE SMALLER than pipe (half to same); small bore (<4") same size. → reducers around most CVs on ≥4" lines. GEN p_cv_reducers 0.5 → plausible, could depend on line size.

## Ch8 Maintenance provisions (pp. 129–142)
- p.131-132 isolation only when MTBF < turnaround interval; "some companies don't provide isolation for heat exchangers" except spares in parallel / auto-cleaning / outlet into a big container. GEN: CHECK exchanger isolation in U5/U1 trims.
- p.132-134 Table 8.2 isolation types (weak→positive): block valve; block valve + BLIND; double block & bleed (two blocks + bleed valve between); block + blind + removable spool. Spectacle blind for < 12", spade blind > 10". Root valve alone is accepted for instruments and utility sub-headers. GEN: blinds only at unit battery limit (LineBlind, p 0.5); equipment isolation is single gate valves → PARTIAL; DB&B absent. Matters for isolation questions (which items close a boundary).
- p.135 isolation on ALL connecting pipes, close to the equipment; some question isolation on pipes to atmosphere. Utility streams crossing an area border get an isolation set.
- p.136-137 drain/vent: at least one drain per pipe span between two isolation valves, isolation+check, isolation+PSV, isolation+concentric reducer; high-point vents / low-point drains often NOT shown (some companies add them after the piping model). Drain/vent valves are GATE or BALL, ¾"–2" (1" default; vent one size smaller). Fig 8.10: vents/drains on tank, vessel, HX, pump casing. GEN: equipment vents/drains (6.4, 6.11, 6.15) CONSISTENT; pipe-span drains only at CV station (p 0.3) → PARTIAL.
- p.140-141 Table 8.9 destination: innocent drains → open drain trench (no hard pipe), vents → atmosphere; non-innocent → CLOSED DRAIN hard-piped (closed hydrocarbon drain CHD), flare, VRU. GEN: every vent/drain ends at a BlindFlange; no closed-drain / flare collection lines → GAP (on real sheets these are pipes with off-page connectors to the drain/flare network P&IDs).
- p.141-142 removable spools (RS) at PD pump discharge, centrifugal pump suction/discharge, HX tube side. GEN: none → minor.
- p.130 test points (PP pressure point, TW thermowell) for rounding operators; sight glasses, peep holes. GEN: local PI/TI exist → OK.
- p.139-140 cleaning connections: flushing, steam-out, chemical cleaning valves; CIP with switching valves. GEN: none → minor.

## Ch9 Containers (pp. 143–168)
- p.143 tank (atmospheric, design < 15 psig, typically < 3 psig) vs (pressure) vessel; tags T/TK, V. GEN Tank/PressureVessel, TK/V → CONSISTENT.
- p.144 roles: edge storage (raw/product tanks, days residence), intermediate day/feed/surge containers (feed drum before critical units e.g. furnace, column), conversion vessels. GEN grammar FeedFarm…ProductFarm + intermediate tankage between trains → CONSISTENT; no feed/surge drum before fired heater or column → minor.
- p.145-146, 158-161 breathing/blanketing: free vent (water tanks), vent treatment (scrubber/condenser) or VRU network; fixed-roof volatile → BLANKETED: two roof pipes — blanket gas (N2 / natural gas / CO2) in through a regulator/PCV, out to VRU through a back-pressure regulator/PCV; or floating roof. Flame arrestor if flammable vapour vented. GEN 6.19 roof → FlameArrestor → BreatherValve → open end → PARTIAL: no blanket-gas supply line with PCV and no VRU line (both are utility/network connections with off-page connectors on real sheets).
- p.157 overflow nozzle (above HHLL) on tanks, to dyke/sump; NOT used on flammable tanks → reliable trip instead. GEN: overfill trip LSHH→XV → CONSISTENT (overflow nozzle absent, minor).
- p.150 liquid levels HHLL/HLL/NLL/LLL/LLLL written on the P&ID (data, out of scope ADR-0021).
- p.151-156 nozzles: process, instrument, manway (MW), overflow, thief hatch, PSV/VSV, free vent, drain, steam-out, purge, spare (10–20 %). Nozzle numbering N1, N2… GEN: one nozzle per line end + sensing nozzles → OK.
- p.155-156 several inlets merged into one nozzle; check valve on the intermittent / low-pressure tie-in. GEN: CHECK merges into vessels.
- p.161 tank heating coils (steam/hot glycol) for temperature maintenance; electric heaters; complementary recirculation exchanger. GEN: none → minor.
- p.162 mixers: top-mounted (D < 5 m), side-mounted for large tanks; hydraulic mixing by recirculation from pump discharge. GEN: Agitator in U8 → OK.
- p.164, 167 tanks in parallel/series with interconnecting piping; one spare tank shared by several; sumps with pumps collect drains. GEN: none → minor.

## NOTE: GEN = v2.1 CODE (src/plantgraph/benchmark/v2), not only the design note. v2.1 already has: removable spool at centrifugal suction strainer, flex connector (Compensator, p .3), orifice flange sets, open drains to Funnel (p_open_drain .3), flush connections (p .3), skillet blinds (p .5), spec_break trim, dosing isolation, sight glasses, tank bottom drains, cascade loops (p .5), motor HS, bearing TT, VFD, UC. Correct earlier "none" notes for RS/flexible joint/open drain accordingly.

## Ch10 Pumps & compressors (pp. 169–200)
- p.173-174 centrifugal: reducer allowed on suction, enlarger on discharge, NEVER the reverse; eccentric FOT (gas risk) / FOB (solids) on horizontal suction; two reducers in series if >1 size. GEN: no pump nozzle reducers (only CV reducers) → GAP (very common symbol pair on real sheets).
- p.175 Fig 10.5 typical centrifugal pump: suction isolation valve WITH BLIND, TSS/strainer, [reducer], PG (rounding check) on suction, pump, PG, CHECK "as close as possible", isolation valve WITH BLIND. GEN 6.1/6.3: block→ConicalStrainer(+RS)→[flex]→pump→[PI tap]→SwingCheck→[min-flow tee]→block → CONSISTENT except no blinds at the pump isolation valves and no suction PG.
- p.176-177 MIN-FLOW: needed for continuous large (>5 hp) pumps and pumps on LEVEL control; usually not for pumps with a FLOW control loop or VSD, intermittent, closed-loop or small pumps. Take-off: upstream of the check valve (preferred, also protects against dead-head heating of flammables) or downstream of the isolation valve; "the second option, between the check valve and the isolation valve, has no process benefit". Destination: upstream container (best) or suction (needs cooler). Control by size: >35 hp FT(upstream of take-off)→FIC→FV (FO); 20–35 hp switching valve; <20 hp RO only; or ARC valve. Parallel operating pumps: dedicated min-flow lines with a check each.
  GEN code trims.py:110-131,170-182: min-flow tee AFTER the check, before the block (the position the book says has no benefit); RO + GlobeCheck + Gate back to vessel; drawn at random p_min_flow=0.3, independent of the pump's control; also drawn for PD pumps → DEVIATIONS (position, rule, PD pumps).
- p.183-184 parallel pumps: dedicated min-flow lines merged after the CVs, check valve on each.
- p.185-186 warm-up bypass around check + isolation of the idle spare (RO / ¾" needle) when ΔT > 100–250 °C. GEN: not encoded (L7, known).
- p.187 discharge high-pressure spec may extend back to the suction isolation valve (parallel pumps).
- p.187-189 drives: motors often not shown; steam turbines/engines shown. Seal flush plan (API 682) drawn at each pump OR referenced by plan number to a typical detail P&ID. GEN: no driver nodes; no seal plan → consistent with "not shown" option.
- p.190-192 RECIPROCATING pump: pulsation dampener on discharge (if destination sensitive), PSV ALWAYS on discharge, NO external check valve ("has internal check valve"), NO min-flow; reducer or enlarger either side. ROTARY pump: PSV on discharge (some trust internal), CHECK valve yes, no min-flow, no dampener. PD pumps in parallel: extra PSV on suction side. Start-up spillback with isolation valve.
  GEN code: pump_discharge always appends PUMP_CHECK (SwingCheckValve) even for ReciprocatingPump; min-flow possible on PD pumps; relief to suction CONSISTENT (6.5). → DEVIATION: reciprocating pumps get a check valve they should not have; PD pumps can get a min-flow line they should not have; no pulsation dampener.
- p.194-195 dosing (metering) pumps: reciprocating; calibration (draw-down) column on suction; BACK-PRESSURE REGULATOR on discharge; stroke/VSD control. GEN U8 dosing: ReciprocatingPump + relief + PI (+VFD p .5) → PARTIAL (no calibration column, no BPR).
- p.196-198 gas movers: most industrial gas movers are PD (reciprocating/screw); centrifugal for large gas processing; KO/scrubber upstream; multi-stage with intercoolers (+ KO drums); anti-surge system for centrifugal; lube-oil and seal-gas systems (often auxiliary P&IDs); vibration/temperature sensors. GEN U2 single stage with anti-surge FIC recycle, KO drum, aftercooler, ST/VT → CONSISTENT; multi-stage absent (minor); anti-surge applied also to ReciprocatingCompressor? CHECK.

## Ch11 Heat transfer (pp. 201–216)
- p.202-203 Table 11.1/11.3/11.4 selection: S&T default; P&F where room is short and P/T mild; air cooler when ~65 °C outlet is enough; CW to ~40 °C; chilled water ~20 °C; hot water <100 °C; steam (saturated) <150 °C; hot oil <400 °C; fired heater above. GEN exchanger classes/utility choice not tied to temperature (no temperatures in the model) → fine within scope.
- p.206 vents AND drains on EACH enclosure (shell & tube → 2 vents + 2 drains). GEN 6.15 shell and channel nozzles p .5 → CONSISTENT.
- p.206 isolation valves around exchangers "subjective"; most companies put NO bypass around a heat exchanger; justified with a spare or CIP. GEN: CHECK whether exchangers get isolation blocks.
- p.206-207 pressure safety device on EACH side (shell side and tube side, on connected pipe). GEN: thermal relief on CW return (6.14) and PSV on blockable shell side (U5) → PARTIAL.
- p.207-208 series: rough (process/process) + trim (utility) exchanger; counter-current; stacked exchangers share one vent (top) and one drain (bottom), no gauges between. Parallel 2×50% for large duty; spare exchanger rare (fouling service). GEN U5 train + trim heater + bypass on last → CONSISTENT.
- p.203 steam: only saturated; steam trap on the condensate outlet; desuperheater for superheated steam. GEN 6.14 SteamTrap → CONSISTENT.
- p.209-211 air coolers: one tag = unit of several bundles/bays; distribution header on top, collection header below (symmetrical); vents/drains on each header; isolation valves; PSD; fans with motors; LOUVERS tagged like control valves; series air coolers avoided, parallel common. GEN AirCoolingSystem single node with no fan/louver/headers → minor.
- p.213-215 FIRED HEATER: process side split into 2–6 PASSES (coils < 4–6") with even distribution (pass flow control or symmetric piping), preheat by feed/effluent exchanger; flue gas side: stack, natural/induced draft fan, convection coils, soot blowers; firing side: fuel gas/oil header → isolation valves → drain/vent/purge valves → fuel preparation (PCV regulator, DUPLEX filter) → safety shutdown valves (often two in series) → control valve station → burner header/ring; separate PILOT GAS line with its own switching valve; snuffing steam; peep holes; BMS by code; combustion air forced/induced draft, air preheat. GEN U3: Furnace + blower/fan, fuel-gas TV, fuel-gas PIC, BE→BSL→XV, GasFilter, feed/effluent exchanger → PARTIAL: no passes / pass flow control, no pilot gas line, single XV (no double SDV), no snuffing steam.

## Ch12 Pressure relief (pp. 217–238)
- p.218-221 PRD "in all enclosures": pressure vessels (legally required), tanks, pipes (thermal expansion of trapped liquid; regulated in some areas), equipment casings; vacuum protection unless designed FV (common for vessels, not for tanks). PD pump blocked outlet → PRD mandatory. Centrifugal pump dead-head → passive solution allowed. GEN S6: ≥1 safety device reachable from every PressureVessel/column/separator → CONSISTENT; tanks: breather only (see below).
- p.223-224 Table 12.8 PSV position: top of the enclosure, vertical; inlet line short, full-bore; manual valve on inlet/outlet FULL PORT + CSO; no check, no control valve; outlet to header with "no pocket". GEN 6.10 optional car-sealed inlet/outlet blocks → CONSISTENT (no FP/CSO attribute; see valve-position gap).
- p.228-229 single PSV default; if in-line care needed: isolation + bleed + PG + manual bypass; or 2×100% spare PSVs with CSO/CSC blocks and change-over valve. GEN: no spare PSV pairs → minor.
- p.229-230 rupture disk UNDER a PSV for aggressive/dirty service, with PG / pressure switch / PAH or burst sensor on the space between; RD also on PSV outlet. GEN U3 reactor RuptureDisc (+PSV) → PARTIAL (check for the PG between).
- p.230-235 Table 12.12 disposal: liquids → system relieving (PD pump PSV back to suction; pipeline thermal PSV across the block valve), open/closed drain, catch pot; gas → atmosphere only if innocent ("to atm"/"to safe location": ≥3 m above grade, 2 m above equipment within 7.5 m), FLARE if combustible, scrubber/quench, VRU. Emergency collection network: headers sloped to the KO drum, PSV outlets tie in at the TOP of the header, root valves CSO. GEN: PSV outlets are FL lines ending open ("flare header parked") → GAP: on a real sheet each PSV outlet ends at an off-page connector to the flare/relief network P&ID (a cross-sheet edge type our corpus lacks).
- p.227 tags: PSV, PSE (rupture disk), VSV, VSE, PVSV/PVRV; technical info: set/burst pressure, size "2 D 3", governing case. GEN tags PSV/PSE/PVSV → CONSISTENT.
- p.235-236 atmospheric tanks: PVRV/PVSV (breather/conservation valve) for normal breathing (16–24" nozzles) PLUS an emergency PSV or emergency vent (fire case); or seal locks. GEN 6.19: FlameArrestor→BreatherValve only → PARTIAL (no emergency vent/PSV on tanks).
- p.236-237 one PRD may cover interconnected enclosures without a valve between; with a valve between, each needs its own.

## Ch13 Instrumentation fundamentals (pp. 239–268)
- p.247-249 ISA acronym: 1st letter L T F P A (+ others), modifier D Q F, function E T C I (V, Y…), function modifier L LL H HH; "all the elements in one control loop have the same tag number … helps us to find elements of one control loop when they are on different P&ID sheets". GEN ISA grammar (11 first letters, ~20 templates) → CONSISTENT and richer; loop members may sit on different sheets (GEN signal cuts 0.54/sheet) → CONSISTENT.
- p.253-255 GAUGES (TG PG LG FG/sight glass) vs SENSORS (TE PE LE FE AE) vs GAUGE POINTS (TW thermowell, PP pressure point) — gauges and gauge points are NEVER connected to other instruments. GEN local PI/TI/LG as single PSGF (degree 1) → CONSISTENT (tag letters PI vs PG = company style).
- p.262-263 indicators: field indicators often built into transmitters (XIT); separate control-room indicators; "these days … we no longer need to use tags like TIC or FIC" (HMI shows everything). GEN uses xIC → acceptable older/OPEN100 style; note as style choice.
- p.257 pressure gauge hook-up: root valve + drain/calibration valve; DB&B for critical; diaphragm seal / flush ring for dirty service. GEN pressure tap: tee → root (Ball/Needle) → BlindFlange/sensor → CONSISTENT (no calibration drain, minor).
- p.258-259 level: LG on standpipe with drain + vent valves; LT by DP with capillaries/diaphragm; radar/ultrasonic non-contact. GEN LG/LT on dedicated nozzle → OK.
- p.260-261 Table 13.19 flow meters: orifice most common; venturi; magmeter (conductive liquids, water); Coriolis (custody, mass); turbine (clean, needs STRAINER upstream); vortex; ultrasonic; rotameter (low flow, vertical); PD meter (custody). Meter reducer/enlarger pair when higher velocity needed; meter bypass if off-line inspection affordable. GEN primary-element vocabulary incl. orifice flange sets → CONSISTENT.
- p.256 temperature on small pipes: enlarger-reducer pair or on an elbow; skin temperature.
- p.264 I/P transducer (LY) shown by some companies, omitted by others; VFD as final element. GEN AF untagged, VFD p .5 → CONSISTENT.
- p.266-267 sensor vs CV position: FLOW element always UPSTREAM of and close to the FV; pressure either (fore-pressure vs back-pressure loop); T and A either.
## Ch14 Control architectures (pp. 269–292) — first part
- p.270 Table 14.1: control inventory always; level in non-flooded containers; pressure on gas containers / gas movers / pressure-dependent units (flash drums, separators); FLOW "on pipes and generally around fluid movers" — "for pumps, we always control flow"; compressors flow (FE on SUCTION) or pressure; temperature wherever T changes (exchanger outlet of the target stream, furnace); composition rare (analyzers slow/unreliable) → inferred temperature control. GEN pattern control schemes → CONSISTENT.
- p.270 RULE: "Don't put more than one control valve on liquid-filled pipelines" (a flooded vessel counts as pipe); gas lines may have more but not close together. GEN: CHECK — a liquid line between two containers carrying e.g. FV and TV/LV in series would violate it (candidate invariant).
- p.271 set points: level always manual (NLL); flow MSP mainly at plant edges, RSP inside (cascade); utility exchangers RSP. (not graph-visible)
## Ch14 (cont.)
- p.274-276 cascade: master = slow parameter (composition < temperature < level), slave = fast (flow, sometimes pressure); typical TC→FC (steam), LC→FC (small drums, steam drum), AC→TC→FC (column). GEN p_cascade .5 on eligible slots → CONSISTENT.
- p.279-280 ratio control FFC or FY+FC (blending, chemical injection), often trimmed by AC feedback. GEN U8 FFIC + AT→AIC → CONSISTENT.
- p.280-281 selective control: several TT → high selector TY (">") → TC (reactor hot spot); low selector on parallel pump discharge flows for min-flow. GEN reactor multi-point TT without selector → minor.
- p.281-286 override (selector on controller outputs): steam generator PC/LC, compressor PC overridden by motor-current IC, steam header PC over a big user's TC; limit control on furnace. GEN: IT→II on compressor without override → minor.
- p.286-288 split range: blanket gas in/out PCVs (reverse), wide-range FV pair (straight). GEN: none (no blanketing) → minor.
- p.289-290 Table 14.12 monitoring ladder: PP (portable) < PI field < PI in control room < PC loop.
- p.290 fluid movers: PG on centrifugal DISCHARGE "almost always"; suction PG when cavitation risk (hot/volatile); PG upstream AND downstream of a strainer for dirty service; PD pumps no suction PG. GEN 6.3 per-pump PI (pressure_mode) → CONSISTENT; strainer ΔP gauges absent → minor.
- p.290-291 heat exchangers: TC on the target stream outlet + "all the streams around a heat exchanger are equipped with a temperature sensor and a pressure sensor" (utility side often without TI; stacked HX → TW/PP only). GEN: TI on exchanger outlets, PI in/out in U5 → PARTIAL (not all four nozzles).
- p.291-292 fired heater monitoring: total and per-PASS flow, fuel and air flows, stack pressure (draft), outlet T per pass, tube SKIN T, firebox T, flue gas O2/CO analyzers; fuel gas and pilot gas each with double SDV and PI. GEN U3 → PARTIAL (no passes, no skin TI, no O2 AI, no pilot line).

## Ch15 Plant process control (pp. 293–332)
- p.294 Table 15.1 hydraulics: gas container P-loop; non-flooded liquid container L-loop; flooded liquid container F-loop; gas pipe P (or F around a mover); liquid pipe F. Flow loops with manual set point only at plant EDGES. GEN → CONSISTENT in spirit.
- p.298-301 level loop pairing: upstream strategy (LV downstream of the vessel, takes order from upstream container — popular for process) vs downstream strategy (utility). Containers roles: storage, day tank (8–24 h), surge tank, FEED TANK before critical units (furnace, distillation tower), feed+surge in series before a critical fired heater; LC→FC cascade on small feed drums. GEN: no feed drum before furnace / column → minor.
- p.304-305 Table 15.7 flow control needs one CV only if one end is at fairly fixed pressure (storage tank, level- or pressure-controlled vessel); flow to a large storage tank or intermittent flow often not controlled.
- p.306-308 merging: carrier (one FC), composition loop, AC→FC cascade, ratio FFC, ratio + AC trim, cross-limiting fuel/air. GEN U8 → CONSISTENT.
- p.308-310 splitting: from a drum, FC on the SMALLER branch and LC on the larger (reflux drum: which one depends on reflux ratio); "preferred destination" with PC on the second branch; parallel units: parallel/split range FCs or symmetrical piping. GEN U1 fixed reflux FIC + distillate LV → acceptable (one of the two book variants).
- p.310-314 CENTRIFUGAL PUMP control = capacity (FC → CV on discharge, or VSD/VFD, or split range) + minimum-flow: <5 hp none; 5–20 hp continuous RO line; 10–30 hp on/off switching valve; >35 hp min-flow CONTROL VALVE loop = "the most common method"; FT inside the recirculation loop, close to the pump; spared (not parallel-operating) pumps: one spillback from the common header; parallel operating pumps: dedicated lines merged downstream (most common). GEN: RO-only min-flow line at p .3, per pump → PARTIAL (no FIC/FV min-flow loops; no common-header spillback for A/B sets).
- p.314-316 PD PUMP control: NOT by discharge throttling ("If you put a flow loop on the discharge side of the pump, it won't change the flow at all"); options: recirculation line with CV (FT outside the loop) or back-pressure control/regulator, VSD, stroke adjustment (reciprocating). GEN: CHECK whether a PD pump ever gets an FV on its discharge (U4 rotary transfer FIC→FV; U8 dosing additive FV in the ratio loop) → likely DEVIATION.
- p.316-319 GAS MOVER capacity: recirculation (cooler + check + CV), VSD/governor, suction throttling (popular for centrifugal), discharge throttling (dynamic only, never PD), guide vanes / blade pitch / suction-valve unloading / clearance pockets (reciprocating). ANTI-SURGE only for dynamic movers with ΔP > 15 kPa and > 150 BHP; "We don't need them for PD gas movers". GEN U2: anti-surge FIC recycle — CHECK if also on ReciprocatingCompressor → likely DEVIATION.
- p.319-320 lead–lag pumps (sumps, LSH starts the lag pump).
- p.320-322 EXCHANGER control: TC on the target stream outlet; CV on the NON-target stream; utility exchanger → direct control on the utility; process exchanger → bypass of the non-target stream (or two CVs parallel range, or 3-way valve); PDC bypass for a bank of parallel exchangers. p.327-328: heat-RECOVERY exchanger needs NO control (trim utility exchanger after it if T matters). GEN U5 outlet TIC → bypass TV around the last exchanger; steam heater TIC → steam TV → CONSISTENT (check which stream the bypass is on).
- p.322-324 reactor temperature: TC→TC cascade via jacket/coil/recirculation cooler; AC→TC→FC three level; split-range hot/cold. GEN U3 reactor inlet TIC via feed/effluent bypass → acceptable.
- p.324-327 steam heaters: TC → steam CV + steam trap; large condensate → condensate pot with LC (pump for LP steam); partial flooding → CV on condensate, NO trap. GEN 6.14 → CONSISTENT (simplest variant).
- p.326-327 air cooler: TC → louvers / blade pitch / fan VSD (split range possible). GEN: AirCoolingSystem has no T loop on fan → minor.
- p.328-331 fired heater: COT TC → fuel FC (or PC for gas) cascade; override from firebox TT; air FFC ratio to fuel or O2 AC trim; Wobbe/SG analyzer for variable fuel gas; SKIN temperature control/trip; PASS BALANCE control. Drum boiler LC→FC. GEN U3 TIC→fuel TV + PIC + BSL trip → PARTIAL.
- p.331-332 containers: gas → P loop, non-flooded liquid → L loop, flooded → none. BLANKET GAS: PCV in + back-pressure regulator out, or FCV in, or O2 AC. GEN: no blanketing → gap (see ch9).

## Ch16 Interlocks and alarms (pp. 333–356)
- p.337, 343 switching valve tags: XV (one initiating event), UV (several events), KV (time-based, DISCRETE process control, not SIS). GEN: XV only → minor.
- p.338 limit switches ZSO/ZSC → XI in control room on critical SIS valves (e.g. BMS). GEN p_limit_switches .5 on every XV → acceptable.
- p.338-339 merging a switching valve with a control valve (solenoid on the CV air supply) possible but unpopular.
- p.340-342 SIS FUNCTIONS ON P&IDs: to avoid crowding, the signal lines are often REMOVED and each element carries an interlock diamond "I nnn" that refers to a cause-and-effect table (shutdown key); OR/AND logic only in simple cases. GEN: trips drawn as explicit signal chains LT→LSHH→AF→XV → realism caveat for trip-chain questions (on many real sets the chain is only an interlock number, not edges).
- p.343-344 discrete (process interlock) control with KV valves for batch / filter backwash / regeneration. GEN U7 filter A/B has none → minor.
- p.345-347 alarms: if a SIS exists for a parameter, it needs an alarm too; HH/LL reserved for SIS, H/L for alarms; shown as TAH balloon or "H" beside a TI. GEN alarm letters in PIF, p_indicator_alarm → CONSISTENT.
- p.347 common alarm XA for motors/compressor packages. p.348-350 FGS on dedicated FGS P&IDs, detectors on plot plans. GEN none → out of scope.
- p.351-356 motor control: MCC, HOA switch (HS H/O/A), local S/S HS, XCR/XSR/XA/XL, SC/VFD; companies range from no motor symbol to full detail. GEN p_motor_hs 1.0 → one acceptable style.
- p.334-335 SIS types: ESD (minimise energy: close fuel, open vents, stop machines), emergency isolation (automatic double block & bleed switching valves), emergency depressurisation/blowdown (BDV to flare), HIPPS (2oo3 PT voting → two SDVs in series), BMS (snuffing steam). GEN: single-XV trips only → PARTIAL (no BDV, no HIPPS, no double SDV).

## Ch17 Utilities (pp. 357–380)
- p.359-360 every utility has a generation unit + DISTRIBUTION network, many also a COLLECTION network (steam→condensate, CWS→CWR, HGS→HGR, CGS→CGR, blanket gas→VRU); tree vs loop (ring) topology; root valves at sub-header roots. Table 17.2 users: IA → every control/switching valve; UA/PA; UW → seal flush, cleaning; potable → safety showers; steam → heaters, strippers; fuel gas/oil → burners; blanket gas → blanketed tanks; inert gas → purging; emergency release network → every PSV; surface drainage → everywhere; fire water; condensate → steam users.
  GEN: utilities parked (ADR, design §1) — only consumer stubs (6.13/6.14, CWS/CWR/LPS/MPS/CD/FG/FL services ending open) → KNOWN GAP; book confirms that on a real set these stubs are the most frequent cross-sheet links (to utility/network P&IDs).
- p.365-366 steam headers: drip legs + steam traps at intervals, branches from TOP of header; LPS 100–200 kPag, MPS 1000–2700, HPS > 4000.
- p.367-368 flare network: local and main KO drums, headers sloped, valves LO/CSO, gate valves stem down.
- p.368-370 fire water ring, main + jockey pumps (different drivers), valves LO/CSO, regulators FO, automatic min-flow valves.
- p.371-372 drains: "to drain system" note on the main P&ID; oily/non-oily, acid/base, open/closed segregated sewers; closed sump for low-flash liquids.
- p.376-377 distribution–collection connection: globe valve or DPC; steam–condensate via steam trap.
## Ch18 Ancillary (pp. 381–404) — skimmed parts read
- p.382-386 insulation PP (personal protection, >60–70 °C, accessible), HC heat conservation (~1" per 100 °C), CC cold conservation; shown in the pipe tag (e.g. "38H") or as a symbol; tracing (steam/electric) for winterization. GEN line-number INS code N/H/C/P/HT → CONSISTENT.
- p.383 safety showers/eye washers: typical detail P&ID + symbol on the potable water network. GEN: none (out of scope).

## Ch20 Examples (pp. 417–452 = PDF 429–464; images, viewed all 34 sheets)
Sheets: acid system, air cooler ×2, caustic tank, closed drain sump, double-pipe HX, plate HX, centrifugal pump, in-line pump A/B, vertical canned pump, caustic injection (metering) pump, gear pump A/B, waste-water filter, RELIEF FLARE HEADER, GLYCOL DISTRIBUTION HEADER, vertical vessel (steam separator), fuel gas KO drum, flare KO drum, flare diffuser, building sump, typical utility station ×2, building HVAC, S&T HX, FGS/ESD controls, instrument air package (vendor border), PLANT BATTERY LIMIT, TIE-IN POINTS, INTER-CONNECTION, instrument details, SAC ion-exchange system, ponds, sloped tank, spiral HX, UV system.
Observations relevant to the generator:
- EQUIPMENT PER SHEET is small: 1–3 tagged items on most sheets (book p.22 says 4–5 or up to 10). GEN band 3–10, ≥90 % in 3–10 → GEN sheets are on the busy end.
- Many sheets carry NO process equipment: relief flare header, glycol distribution header, battery limit, tie-in points, inter-connection, utility stations — pure network/interarea sheets made of off-page connectors. GEN has none of these sheet types.
- OFF-PAGE CONNECTORS on almost every process sheet go to NETWORKS: PSV outlets → "To Relief Header", drains → "Open Drain / To Building Sump", utility supply/return headers, KO drum liquid → pumps drawn on ANOTHER sheet (flare KO drum V-123 → P-7310A/B on another P&ID — pumps not always with their suction vessel), filter F-123A on one sheet with cross-connections to F-123B on another sheet (A/B spares split over sheets).
- SIGNAL off-page connectors exist: S&T HX sheet receives "Level Control Signal from Steam Separator LIC-123" (the LV is on this sheet, its controller on another); sloped tank sends "Level Signal to LV-124". GEN signal cuts 0.54/sheet → CONSISTENT in kind.
- Pump sheets: suction gate + T-type/Y/conical strainer + ECC FOT reducer (8x6, 16x8) → pump → enlarger (6x4) → check → gate; PG on discharge (and on suction for some); drip pans; seal-water line with Y-strainer, FG, PG. A/B in-line pumps: ONE min-flow FE/FIT→FIC→FV (FO) loop on the common discharge, the FV in a CV station with globe bypass, returned to the tank via off-page. Gear pumps A/B: PSV per pump (blocked flow) routed off-page, conical start-up strainer, check valves present (rotary). Metering pump: pulsation dampener, PSV (blocked outlet), magmeter FE/FIT, flush, open-drain line.
- Exchanger sheets: PG/TG (or PIT/TIT) on ALL FOUR nozzles; PSVs on both sides (fire / thermal / tube-rupture cases) with CSO FP blocks, routed to relief header or "safe location"; TV in a CV station with globe bypass and drains; high-point vents, NC drains.
- Vessel sheets: nozzle numbers N1…, MW, spare nozzles, LG with block valves and drains, LIT→LIC→LV in a CV station (FC) leaving via off-page; PSV (fire) to flare header off-page; outlet FE/FIT/TIT/PIT; level SIS with voting diamonds (LIT A/B).
- Valve positions written everywhere: CSO, NC, FO, FC, LO.
- Tags: P-123A/B (A/B suffix used in the book's own examples), sparing "2×100%", "3×50%" in callouts.
- Manual valves are NOT tagged in the examples (only sizes) — automatic valves, PSVs, instruments and SP items are tagged.

## Verified in code (2026-11-22)
- trims.py:103-131 every pump discharge gets PUMP_CHECK (SwingCheckValve), also ReciprocatingPump; min-flow tee after the check; trims.py:209-224 min-flow drawn by p_min_flow=0.3 for any pump class, PD included.
- patterns/compression.py:117 anti_surge for every compressor class (centrifugal, reciprocating, rotary).
- patterns/blending_parts.py:54-70 dosing (reciprocating) pumps: ratio FV on the discharge header when there is no VFD (p_vfd .5).
- patterns/storage_parts.py:76-88 transfer header FIC->FV also when the farm uses RotaryPump (viscous variant).
- patterns/exchanger.py: no isolation blocks around exchangers (CONSISTENT with p.206).
- trim_plan.py: branches (vents, drains, bypasses, taps) get their own line numbers (book p.72-73: usually untagged).

## Corrections (page re-check during the v2.2 design, 2026-11-22)
The page offset is not constant. Checked: printed = PDF − 19 at pp. 24–34, − 18 at pp. 173–236, − 17 at pp. 265–271, − 16 at pp. 295–328. Pages above that were derived with − 19 may be one to three pages off; the design note `40-design/generator-v2-2-handbook-rules.md` carries the checked pages and supersedes this note where they differ.
- Spare tagging is p. 28 (not p. 30).
- The one-control-valve-on-liquid-lines rule is p. 271 (not p. 270).
- Table 15.1 is p. 295; exchanger isolation, no bypass and relief on both sides are p. 207.
- Fired-heater double switching valves are "in some designs" (p. 214), not "often".
- "GEN: A/B only" is wrong: v2.1 already draws suffix or consecutive spare numbering per train at 3:2 (`vocabulary.py`, `SpareNaming`).
- "GEN band 3–10, none > 10" is wrong: EXP-0008 measured equipment per sheet min 1, max 7 (H100g21p1) and max 11 (H1000g21p1).
