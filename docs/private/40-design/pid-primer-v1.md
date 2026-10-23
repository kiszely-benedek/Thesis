---
title: P&ID reading primer v1 (R-PR1 of ADR-0041)
date: 2026-10-03
status: draft — awaiting architect check (ADR-0041 point 1 content rules only) and user approval
author: researcher agent (fresh session)
adr: 0041
design: 40-design/plant-graph-first-and-effort-routing.md Part C
---

# P&ID reading primer v1

## 1. Provenance and what the author saw

**Inputs read:** ADR-0041; Part C (lines 214–245 only) of `plant-graph-first-and-effort-routing.md`;
`10-literature/pid-structural-rules.md`; lines 90–115 of `Notes/pid-szerkezeti-szabalyok.md` (the line that marks the
check-valve function "not verified"); the public sources in section 4.

**Not read, as required:** `30-experiments/`, `src/plantgraph/qa/questions/`, `qa-system.md`,
`question-aware-retrieval.md`, `heldout-families.sealed.md`, `tests/`, Part B of the design note.
`graph/schema.py` was also not read. The ADR offers its vocabulary, but the primer uses only general P&ID words.

**Disclosed contamination:**
- ADR-0041's Context section itself names one dev failure: a check valve was named as an isolation point. It also
  says the generator treats only globe and ball valves as operated. The user's topic list (check valves, operated
  valves, signal lines, off-page connectors) is dev-influenced, as the ADR says. No line below was adjusted to
  agree or disagree with the generator. Line B4/B5 states the general rule from DOE: gate valves start and stop
  flow, and a valve with no actuator is assumed hand-operated. That may not match the generator's valve classes.
  This is the architect's call, not the primer's.
- The shared scratchpad folder listing showed other sessions' folder names (e.g. `questions/`, `paid01/`). None was
  opened. All work files for this task are in `scratchpad/rpr1/`.

**Output-path note:** ADR-0041 point 2 names `src/plantgraph/qa/prompts/primer_pid_v1.txt` and
`10-literature/primer-sources.md`. The R-PR1 task brief asked for this single file and no code. The text in
section 2 is the exact content for `primer_pid_v1.txt`: a coder (PR-T1) copies it byte for byte, no trailing
newline needed.

## 2. Primer text

**1,195 characters** including the 11 line breaks (1,184 without), pure ASCII, 12 lines. Counted with
Python `len()` on the text with the trailing newline stripped. Limit: 1,200.

```text
- P&IDs show equipment (pumps, tanks, exchangers), piping, valves, fittings and instruments.
- Arrows on lines show flow direction.
- Instrument signal lines differ from process piping.
- Gate valves and conventional ball valves start or stop flow; globe valves also regulate it.
- Valve + actuator = control valve, moved remotely or by a controller. No actuator shown: assume hand-operated.
- Control valve stations generally have block valves and a bypass; control valves are not generally suitable for isolation.
- Check (non-return) valves are self-acting: flow opens them, reverse flow closes them. Without a screw-down stop they are unsuitable for isolation.
- Relief/safety valves open on overpressure to protect equipment.
- Tag = measured-variable letter (F flow, L level, P pressure, T temperature) + function letters (I indicator, C controller, T transmitter, V valve) + loop number; one loop shares it: FIC045, FT045.
- Loop: transmitter -> controller -> final control element (e.g. control valve).
- A line continued on another sheet ends in a connector; both ends reference each other.
- Lines to other units or utilities end in boxes naming the service and the other unit/drawing.
```

## 3. Per-sentence source table

Verified = I read the quoted text in the named source on 2026-10-03 (PDF text extracted locally, or raw wikitext).
Grade as in `pid-structural-rules.md`: STD standard preview, ORG organisational standard/guidance, GOV
government handbook, SEC secondary.

| # | Primer sentence (short) | Source (grade) | Location | Quote or paraphrase | Status |
|---|---|---|---|---|---|
| B1 | P&IDs show equipment, piping, valves, fittings, instruments | DOE-HDBK-1016/1-93 (GOV) | Module 2, p. 15 (Summary); p. 13; p. 8 | "the common symbols found on P&IDs for valves, valve operators, process piping, instrumentation, and common system components"; "major components such as pumps, tanks, heat exchangers, and fans"; "individual fittings comprising the piping runs" | verified |
| B1 | (same) | ISO 10628-1:2014 (STD) | 4.1 | "All equipment, machinery, flow lines (e.g. pipelines, transport routes), and valves shall be represented in accordance with ISO 10628-2." | verified |
| B2 | Arrows on lines show flow direction | ISO 10628-1:2014 (STD) | 4.1; 5.3.3.3 | "Flow routes and flow directions shall be indicated by lines and arrows."; "Arrows are to be incorporated in the lines to indicate the direction of the flows within the flow diagram." | verified |
| B3 | Signal lines differ from process piping | DOE-HDBK-1016/1-93 (GOV) | Module 2, p. 7 | "a fluid system diagram may also depict instrument signals and electrical wires as well as piping. Figure 7 shows commonly used symbols ... for differentiating between piping, instrumentation signals, and electrical wires." | verified |
| B3 | (same) | ISO 10628-1:2014 (STD) | 5.3.1 a), c) | Main flow lines are 1,0 mm. Line class c) is 0,25 mm and covers "symbols representing process measuring and control functions, control and data transmission lines" (paraphrase of the width list) | verified |
| B4 | Gate valves start/stop, no throttling | DOE-HDBK-1018/2-93 (GOV) | Module 4 Valves, p. 8 | "A gate valve is a linear motion valve used to start or stop fluid flow; however, it does not regulate or throttle flow." | verified |
| B4 | Conventional ball valves start/stop | DOE-HDBK-1018/2-93 (GOV) | pp. 18–19 | "uses a ball-shaped disk to stop or start fluid flow"; "quick, quarter turn on-off operation"; "Conventional ball valves have relatively poor throttling characteristics." (some eccentric designs "can be used for throttling service", hence "conventional") | verified |
| B4 | Globe valves also regulate | DOE-HDBK-1018/2-93 (GOV) | p. 15 | "A globe valve is a linear motion valve used to stop, start, and regulate fluid flow." | verified |
| B5a | Valve + actuator = control valve, remote or by controller | DOE-HDBK-1016/1-93 (GOV) | Module 2, pp. 4–5 | "The combination of a valve and an actuator is commonly called a control valve."; "The most commonly found configurations are to manually control the actuator from a remote operating station, to automatically control the actuator from an instrument, or both."; "the output of the controlling instrument goes to the valve actuator" | verified |
| B5b | No actuator shown: assume hand-operated | DOE-HDBK-1016/1-93 (GOV) | Module 2, p. 4 | "If no actuator is shown on a valve symbol, it may be assumed the valve is equipped only with a handwheel for manual operation." | verified |
| B6a | Control valve stations generally have block valves and a bypass | HNF-64103 Rev. 0 (ORG) | 3.2.4.2 | "In general, control valve stations have block valves and a by-pass." | verified (re-read today; also L9 in `pid-structural-rules.md`) |
| B6b | Control valves not generally suitable for isolation | HSE HSG253, 2nd ed. 2006 (GOV) | Appendix 4, para. 2, p. 50 of 81 (web version) | "control or choke valves are not generally suitable for isolation" | verified |
| B6b | (same, corroborating) | CEA BG10, Edition 1, June 2023 (ORG) | p. 29 | "2-port and 3-port control valves are usually not designed as isolating valves and should not be used in the isolation scheme." | verified |
| B7a | Check = non-return valve | Wikipedia "Check valve" (SEC) | lead sentence | "A check valve, non-return valve, reflux valve, retention valve, foot valve, or one-way valve is a valve that normally allows fluid (liquid or gas) to flow through it in only one direction." | verified (raw wikitext) |
| B7a | Self-acting: flow opens, reverse flow closes | DOE-HDBK-1018/2-93 (GOV) | p. 35 | "Check valves are designed to prevent the reversal of flow in a piping system. These valves are activated by the flowing material in the pipeline. The pressure of the fluid passing through the system opens the valve, while any reversal of flow will close the valve." | verified |
| B7b | Without a screw-down stop: unsuitable for isolation | CEA BG10, Edition 1, June 2023 (ORG) | p. 29 | "Non return valves in piped systems are not suitable for isolation purposes and should not be included in the isolation process unless they have a full 'screw down stop' actuator." | verified |
| B7b | (corroborating) | HSE HSG253 (GOV) | Appendix 4, Table A, p. 51 of 81 | Table A lists isolation valve types (ball, plug, butterfly, globe, gate, screwdown non-return, needle). Plain non-return valves are not listed. This is an absence, not a statement. | verified (absence) |
| B7b | (what a screw-down stop is) | DOE-HDBK-1018/2-93 (GOV) | p. 40 | "A stop check valve ... is a combination of a lift check valve and a globe valve. It has a stem which, when closed, prevents the disk from coming off the seat and provides a tight seal" | verified |
| B8 | Relief/safety valves open on overpressure, protect equipment | DOE-HDBK-1018/2-93 (GOV) | p. 40 | "Relief and safety valves prevent equipment damage by relieving accidental over-pressurization of fluid systems."; a relief valve "gradually opens as the inlet pressure increases above the setpoint"; a safety valve "rapidly pops fully open as soon as the pressure setting is reached" | verified |
| B9 | First letter = measured variable; F, L, P, T | DOE-HDBK-1016/1-93 (GOV) | Module 2, pp. 8–9, Table 1 | "The first column of Table 1 lists the letters used to identify the parameter being sensed or monitored"; Table 1: "F = flow", "T = temperature", "P = pressure", "L = level" | verified |
| B9 | Function letters I, C, T, V | DOE-HDBK-1016/1-93 (GOV) | pp. 6, 9 | Table 1: "I = indicator", "C = controller", "T = transmitter"; p. 6: "The third letter is a 'V' to indicate that the piece of equipment is a valve." | verified |
| B9 | Loop number shared within a loop; FIC045/FT045 | Wikipedia "Piping and instrumentation diagram" (SEC) | "Identification and reference designation" | "This is followed by loop number, which is unique to that loop. For instance FIC045 means it is the Flow Indicating Controller in control loop 045 ... The same loop may have FT045 - which is the flow transmitter in the same loop." | verified (raw wikitext); primary ANSI/ISA-5.1 **not read** (also L17) |
| B10 | Loop: transmitter → controller → final control element | DOE-HDBK-1013/2-92 (GOV) | Module "Process Controls", pp. 4–5, 10, 12 | "The three functional elements ... A measurement element / An error detection element / A final control element"; "The final control element responds to the error signal by correcting the manipulated variable"; "control elements ... are also called the 'controller'"; "The temperature control loop consists of a temperature transmitter, a temperature controller, and a temperature control valve." | verified |
| B11 | Continued line ends in a connector; ends mutually referenced | ISO 10628-1:2014 (STD) | 5.3.3.2, Figure 3 | "When a connection line continues to another diagram the end should be mutually referenced. The reference should consist of a designation"; Figure 3 caption "Arrow for connection line continuing on another diagram (with reference)" | verified (also S1). The word "connector" follows DEXPI's off-page connector classes (`ontology-landscape.md`, prior note). |
| B12 | Lines to other units: box with service and unit/drawing | KLM P&ID Standard Rev 01, Feb 2011 (ORG) | pp. 11–12, items 6–7 | "Process lines to/from other Units should be terminated at the bottom of the drawing at a box indicating ... a. The line service b. Source or destination Unit name and number c. The drawing number of the connecting flow diagrams" | verified (re-read today; also C5) |
| B12 | Utility lines: box with service | KLM (ORG); HNF-64103 (ORG) | KLM p. 12 item 7; HNF 3.2.5.2 | KLM: "All utility lines entering or leaving the diagram shall be terminated ... at a box indicating the relevant utility service abbreviation (e.g., CWS, CWR, IA, etc.)", with a "Utilities Identification Table" giving reference drawings. HNF: "Utility line origin and terminus is indicated by descriptive title only." | verified (re-read today; also C4) |

### Sources (full references)

- **DOE-HDBK-1016/1-93**, *DOE Fundamentals Handbook: Engineering Symbology, Prints, and Drawings*, Vol. 1, US DOE,
  Jan 1993, "Approved for public release; distribution is unlimited." The official PDF
  (standards.doe.gov) returned an HTML page. The text was read from the verbatim reproduction in PDHonline
  course G253 (https://pdhonline.com/courses/g253/Engineering_Drawings.pdf). Each page there carries the DOE
  running header and footer ("DOE-HDBK-1016/1-93 ... PR-02 Page n"). Page numbers above are DOE's.
- **DOE-HDBK-1018/2-93**, *Mechanical Science*, Vol. 2, Module 4 "Valves", US DOE, Jan 1993; read from the
  Cambridge mirror (https://www-mdp.eng.cam.ac.uk/web/library/enginfo/textbooks_dvd_only/doe_handbooks/mech2.pdf),
  130 pp.
- **DOE-HDBK-1013/2-92**, *Instrumentation and Control*, Vol. 2, Module "Process Controls" (IC-07), US DOE,
  Jun 1992; Cambridge mirror `.../doe_handbooks/inst2.pdf`, 168 pp.
- **ISO 10628-1:2014**, official iTeh preview (clauses 1–5.4.3):
  https://cdn.standards.iteh.ai/samples/51840/688f149554ee4443b3396c01f82da2ba/ISO-10628-1-2014.pdf
- **HSE HSG253**, *The safe isolation of plant and equipment*, 2nd ed. 2006, free web version:
  https://books.hse.gov.uk/gempdf/hsg253.pdf
- **CEA BG10**, *Guidance on Safe Isolation of Plant and Equipment*, Combustion Engineering Association,
  Edition 1, June 2023: https://cea.org.uk/wp-content/uploads/2025/07/CEA-BG10.pdf. It is industry guidance for
  the combustion sector, but the sentence used is about "piped systems" in general.
- **HNF-64103 Rev. 0** (Oct 2020): https://hmis.hanford.gov/files.cfm/HNF-64103_-_Rev_00.pdf
- **KLM Technology Group**, P&ID Project Engineering Standard Rev 01 (Feb 2011), free pp. 1–23 of 146:
  https://www.klmtechgroup.com/PDF/ess/PROJECT_STANDARDS_AND_SPECIFICATIONS_piping_and_instrument_diagram_REV01.pdf
- **Wikipedia**, "Check valve" and "Piping and instrumentation diagram", raw wikitext fetched 2026-10-03.

## 4. Rules left out on purpose

### 4a. Wanted, but no source supports them as stated

| Rule | Why it is out |
|---|---|
| "A check valve cannot be closed by an operator" (the user's wording) | It is false as a universal rule. DOE-HDBK-1018/2-93 p. 40 describes stop-check valves, whose stem closes them. The primer states what is sourced instead: self-acting, and unsuitable for isolation without a screw-down stop. |
| Which valve kinds count as "operated" | No source draws that line by valve type. DOE ties operability to the actuator or handwheel, not the body type. |
| "Signal lines carry information, not material" | DOE-HDBK-1013/2-92 p. 9 says a *block diagram* "represents flowpaths of control signals, but does not represent flow of energy". That is about block diagrams, not P&IDs. No P&ID source read says it. |
| Full ISA-5.1 letter table (modifiers, A alarm, S switch, Y relay, etc.) | ANSI/ISA-5.1 itself was not readable (403, see `ontology-landscape.md`). Only DOE Table 1 and Wikipedia were read. Letters outside them are left out. |
| A finer loop chain "sensor → transmitter → controller → actuator → valve" as a rule | DOE gives the three functional elements and a transmitter–controller–valve example. It does not give a fixed five-step chain (also L18: "[recalled]"). |
| Off-page connectors pair one-to-one | No rule found. The Covestro two-drawing example shows 13 of 15 references without a counterpart label (S5, observation). |
| How a plant is split into units or sheets | No source codifies it (`pid-structural-rules.md` S16, gap 2). |
| "Upstream/downstream" definitions | Not defined in any source read. The primer relies on the arrow rule (B2) only. |
| Where relief-valve discharge goes (flare, atmosphere, vessel) | Not stated generally in sources read. HNF and DEXPI C01 give one PD-pump instance only (L5). |

### 4b. Sourced, but cut for the 1,200-character budget or as too specific

- Valves are drawn in their "normal" position unless stated; safety systems in standby (DOE-HDBK-1016/1-93 p. 16).
- Fail-open / fail-closed / fail-last action is shown for control valves (HNF 3.2.4.2; DOE-HDBK-1016/1-93 p. 16).
- PSV block valves are locked or car-sealed open (HNF 3.2.4.3). Relief valves are not used for isolation without a
  purpose-designed closed-securing method (HSG253 App. 4 para. 2).
- Pump discharge: check valve between pump and block valve (HNF 3.2.5.3, L1). It is an equipment pattern, not a
  reading convention, and is too close to a specific answer shape.
- Main utility headers sit on the utility P&ID for the process area, not on the unit P&ID (HNF 3.2.5.2, C4).
- Sheet-to-sheet instrument signals end at a box with the continuation instrument number and drawing (KLM item 8, C7).
- P&IDs are used to plan isolations / lockout–tagout (HSG253 para. 142 box, p. 31; TOG 1.1).
- Every line has a line number; a specification change starts a new line number (HNF 3.2.5.1–2, C3, L20).
- Flow reads left to right across sheets (ISO 10628-1 5.3.3.1; HNF 3.2.2). This is a rendering convention and
  carries no meaning in a graph.
- Globe and gate valves often share one symbol on drawings (DOE-HDBK-1016/1-93 p. 3).

**Approved by the user 2026-10-03 (in chat).**
