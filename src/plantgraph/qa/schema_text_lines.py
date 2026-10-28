"""The schema paragraph for the `plant_lines` store profile (V2T, qa-tuning-v2 QT-3).

Kept apart from `schema_text.py` so the `occurrence` and `plant` paragraphs that F1 was run with
stay untouched. It describes the plant layer as `_PLANT_PARAGRAPH` does, then the line view
(`line_to`, `kind`, `:Valve`, line-end marks, see `store/plant_line_rows.py`) and the facts of a
v2 plant the v1 text got wrong: the instrument vocabulary, `unit_id` as a string, columns.
"""

from __future__ import annotations

#: Node properties the `plant_lines` profile adds to the shared item-property list.
LINE_NODE_PROPERTIES: tuple[str, ...] = ("kind", "no_inflow", "no_outflow")
#: Relationship properties of `line_to` (never on the other relationships).
LINE_EDGE_PROPERTIES: tuple[str, ...] = ("via_tags", "n_fittings")

PLANT_LINES_PARAGRAPH = """How the graph is organised:
- Every plant item (equipment, valve, instrument function) is one (:PlantItem) node, however many
  sheets it is drawn on. It also has its class labels, a specific class and the general ones above
  it, for example :PlantItem:CentrifugalPump:Pump:Equipment, so MATCH on a general label such as
  :Equipment to cover a family. Every valve also has the label :Valve. A column is a
  :ProcessColumn (also :Equipment), not a :Tank.
- Material flows along -[:send_to]->: (a)-[:send_to]->(b) means flow runs from a to b, also when a
  and b are drawn on different sheets: lines that continue on another sheet are already joined.
  A relationship that crosses sheets has crossed_sheets, the sheet the line leaves and the sheet
  it continues on. send_to is drawn pipe part by pipe part: between two real items a pipe carries
  parts that have no tag (pipe tees, flanges, blind flanges, reducers) and sometimes tagged inline
  components (strainers, orifices, flow elements), and each of them is a node.
- (a)-[:line_to]->(b) skips those parts. It joins one line item to the next line item, where a
  line item is an equipment item or a valve (kind 'equipment' or 'valve'). line_to has via_tags,
  the tags of the tagged inline components the pipe passes through, and n_fittings, the number of
  untagged parts it passes through. For "what is upstream or downstream of an item or a valve",
  follow line_to, not send_to: send_to stops at every tee and flange.
- Every item has kind: 'equipment', 'valve', 'instrument', 'actuator', 'connector' (a line end whose
  continuation was not found) or 'inline' (a pipe part such as a tee, flange, strainer or flow
  element). An equipment item or valve also has no_inflow and no_outflow, true or false:
  no_inflow = true means no line_to relationship enters it, so a line starts there and nothing
  flows into it; no_outflow = true means no line_to leaves it.
- Instrument wiring uses send_signal_to, control and measured_by, and reads source to target:
  equipment -measured_by-> sensor -send_signal_to-> ... -send_signal_to-> controller or switch
  -send_signal_to-> actuator -control-> valve. measured_by reaches the sensor, the first
  instrument; the instrument that heads the loop (a controller, an indicator, a high-level switch)
  can be several send_signal_to hops further. Loop heads are :ProcessInstrumentationFunction (an
  indicator PI, a switch LSHH or CSHH) or :ProcessControlFunction (a controller FIC; it also has
  the label :ProcessInstrumentationFunction). Match instrument functions of one loop by loop_tag,
  the number of their control loop, rather than by one label. Actuators have no tag.
- (item)-[:is_drawn_on]->(:Sheet {sheet_id}) for every sheet the item appears on;
  (:DrawingSet)-[:has_sheet]->(:Sheet). Items have no sheet_id property.
- (item)-[:is_located_in]->(:PlantSection {unit_id})-[:is_located_in]->(:ProcessPlant {plant_id}).
  unit_id is also an item property. unit_id is a string, for example '17': write {unit_id: '17'},
  not {unit_id: 17}.
- tag is the identifier printed next to an item, for example P-101. piping_component_name is the
  printed name of an imported valve. A tag the plant does not have matches no node.
- A (:PlantItem:UnresolvedOffPageConnector) is a line end whose continuation was not found; the
  line stops there."""
