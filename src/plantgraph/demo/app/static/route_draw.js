/* The route view's picture: SVG elements for the items (as P&ID glyphs) and the edges between them.
   `buildScene` creates every element once; `placeScene` moves them to a layout. Showing or hiding a
   step only toggles classes (route.js), so nothing jumps and keyboard focus stays where it is. */

import { el } from "./dom.js";
import { CELL_W, HEADER_H } from "./route_layout.js";
import { STRINGS } from "./strings.js";

const SVG_NS = "http://www.w3.org/2000/svg";
// the glyph is drawn a little above the cell centre so the tag fits under it
const GLYPH_DY = -6;
// edges stop this far from an item's centre, outside its glyph, so the arrowhead is visible
const GLYPH_RADIUS = 20;
const TAG_CHARS = 13;
// beyond this many sheet-crossing edges the "DWG 3 -> DWG 8" text would crowd the picture (the flag stays)
const MAX_FLAG_TEXTS = 40;
const ARROW = " → ";
const MARKERS = ["flow", "signal", "path"];
// an edge label sits this far from the edge, to the side, so it never covers the line or a glyph
const LABEL_OFFSET = 13;
// above this many items the dotted gap line is named only in its hover title
const MAX_GAP_TEXT_NODES = 40;

/** An SVG element with attributes and children (strings become text). */
export function svgEl(tag, attrs = {}, ...children) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, value);
  node.append(...children);
  return node;
}

// ---------- glyphs: the PDF's own vocabulary ----------

const GLYPH_SHAPES = {
  equipment: () => svgEl("rect", { x: -22, y: -14, width: 44, height: 28, rx: 3 }),
  valve: () => svgEl("polygon", { points: "-15,-11 15,11 15,-11 -15,11" }),   // the bow-tie
  instrument: () => svgEl("circle", { r: 14 }),                               // the instrument bubble
  other: () => svgEl("polygon", { points: "0,-14 19,0 0,14 -19,0" }),
};

/** The glyph of an item family, centred on (0, 0). */
export function glyph(family) {
  const shape = (GLYPH_SHAPES[family] ?? GLYPH_SHAPES.other)();
  shape.setAttribute("class", "glyph");
  return shape;
}

/** The plain-words class name, e.g. "centrifugal pump"; an unknown class shows as the system names it. */
export function plainClass(node, names) {
  return names[node.node_class] ?? node.node_class;
}

function shortText(text) {
  return text.length <= TAG_CHARS ? text : `${text.slice(0, TAG_CHARS - 1)}…`;
}

function buildNode(node, names, ariaLabel, wrong) {
  const group = svgEl("g", { class: `rnode fam-${node.family}`, tabindex: 0, role: "button", "aria-label": ariaLabel });
  group.dataset.id = node.item_id;
  const shown = svgEl("g", { transform: `translate(0 ${GLYPH_DY})` }, glyph(node.family));
  if (node.in_question) shown.append(svgEl("circle", { class: "qmark", cx: -20, cy: -14, r: 4 }));
  // a cross on an answer item that the reference answer does not contain (shown at the end)
  if (wrong) shown.append(svgEl("g", { class: "xmark", transform: "translate(20 12)" }, svgEl("circle", { r: 7 }), svgEl("text", { y: 3.5 }, "\u2715")));
  group.append(
    // the invisible hit area makes the small glyph easy to hover and gives the focus ring a shape
    svgEl("rect", { class: "hit", x: -(CELL_W / 2 - 8), y: -30, width: CELL_W - 16, height: 62, rx: 4 }),
    shown,
    svgEl("text", { class: "rtag", y: 24 }, shortText(node.tag ?? plainClass(node, names))),
  );
  return group;
}

// ---------- edges ----------

function edgeKind(edge) {
  if (edge.relation === "none") return "gap";
  return edge.relation === "send_to" ? "flow" : "signal";
}

/** "DWG 3 -> DWG 8": the sheets an edge passes through. */
function crossingText(edge) {
  return edge.crossed_sheets.map((sheet) => `DWG ${sheet}`).join(ARROW);
}

/** The pennant on a sheet-crossing edge: the shape of an off-page connector. */
function flagShape() {
  return svgEl("g", { class: "rflag" }, svgEl("polygon", { points: "-8,-5 4,-5 9,0 4,5 -8,5" }));
}

function buildEdge(edge, tagOf, showTexts) {
  const group = svgEl("g", { class: `redge ${edgeKind(edge)}${edge.on_answer_path ? " onpath" : ""}` });
  group.append(svgEl("line"));
  const crossed = edge.crossed_sheets.length > 0;
  if (crossed) group.append(flagShape());
  if (crossed && showTexts.flags) group.append(svgEl("text", { class: "elabel" }, crossingText(edge)));
  if (edge.relation === "none" && showTexts.gaps) group.append(svgEl("text", { class: "elabel gap-text" }, STRINGS.routeGap));
  const sheets = crossed ? ` (${crossingText(edge)})` : "";
  group.append(svgEl("title", {}, `${tagOf(edge.source)} → ${tagOf(edge.target)}${sheets}`));
  return group;
}

/** Arrowheads, one per line colour (a marker cannot inherit its line's colour in every browser). */
function arrowDefs() {
  const defs = svgEl("defs");
  for (const name of MARKERS) {
    defs.append(svgEl(
      "marker",
      {
        id: `route-arrow-${name}`, class: `arrow-${name}`, viewBox: "0 0 10 10", refX: 9, refY: 5,
        markerWidth: 8, markerHeight: 8, orient: "auto", markerUnits: "userSpaceOnUse",
      },
      svgEl("path", { d: "M0 0 L10 5 L0 10 z" }),
    ));
  }
  return defs;
}

/** Build the picture once: `{ svg, nodeEls: Map(id -> element), edgeEls: [{edge, el}], headers }`. */
export function buildScene(route, names, ariaLabelOf, wrongIds) {
  const tagOf = (id) => route.nodes.find((n) => n.item_id === id)?.tag ?? id;
  const crossings = route.edges.filter((e) => e.crossed_sheets.length > 0).length;
  const showTexts = { flags: crossings <= MAX_FLAG_TEXTS, gaps: route.nodes.length <= MAX_GAP_TEXT_NODES };
  const headers = svgEl("g", { class: "rheaders" });
  const edgeLayer = svgEl("g", { class: "redges" });
  const nodeLayer = svgEl("g", { class: "rnodes" });
  const nodeEls = new Map();
  for (const node of route.nodes) {
    const el = buildNode(node, names, ariaLabelOf(node), wrongIds.has(node.item_id));
    nodeEls.set(node.item_id, el);
    nodeLayer.append(el);
  }
  const edgeEls = route.edges.map((edge) => ({ edge, el: buildEdge(edge, tagOf, showTexts) }));
  edgeLayer.append(...edgeEls.map((entry) => entry.el));
  const attrs = { class: "route-svg", role: "group", "aria-label": STRINGS.routeSvgLabel };
  return { svg: svgEl("svg", attrs, arrowDefs(), headers, edgeLayer, nodeLayer), nodeEls, edgeEls, headers };
}

// ---------- moving the scene to a layout ----------

/** Shorten the segment a -> b by `GLYPH_RADIUS` at both ends (unless it is already short). */
function trimmed(a, b) {
  const length = Math.hypot(b.x - a.x, b.y - a.y);
  if (length < GLYPH_RADIUS * 2 + 6) return [a, b];
  const dx = ((b.x - a.x) / length) * GLYPH_RADIUS;
  const dy = ((b.y - a.y) / length) * GLYPH_RADIUS;
  return [{ x: a.x + dx, y: a.y + dy }, { x: b.x - dx, y: b.y - dy }];
}

/** Put an edge's text beside the middle of the edge: right of a vertical line, above a sloping one. */
function placeLabel(label, a, b, mid) {
  if (!label) return;
  const vertical = Math.abs(b.x - a.x) < Math.abs(b.y - a.y) * 0.5;
  const x = vertical ? mid.x + LABEL_OFFSET : mid.x;
  const y = vertical ? mid.y + 3 : mid.y - LABEL_OFFSET + 3;
  label.setAttribute("transform", `translate(${x.toFixed(1)} ${y.toFixed(1)})`);
  label.setAttribute("text-anchor", vertical ? "start" : "middle");
}

function placeEdge({ edge, el }, places) {
  const from = places.get(edge.source);
  const to = places.get(edge.target);
  if (!from || !to) return;   // an edge to an item the current layout does not show
  const [a, b] = trimmed({ x: from.x, y: from.y + GLYPH_DY }, { x: to.x, y: to.y + GLYPH_DY });
  const line = el.querySelector("line");
  for (const [name, value] of [["x1", a.x], ["y1", a.y], ["x2", b.x], ["y2", b.y]]) line.setAttribute(name, value.toFixed(1));
  const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
  el.querySelector(".rflag")?.setAttribute("transform", `translate(${mid.x.toFixed(1)} ${mid.y.toFixed(1)})`);
  placeLabel(el.querySelector(".elabel"), a, b, mid);
}

function placeHeaders(scene, layout, labelOf) {
  if (layout.columns.length === 0) {
    scene.headers.replaceChildren();
    return;
  }
  const rule = svgEl("line", { class: "rrule", x1: 8, x2: layout.width - 8, y1: HEADER_H, y2: HEADER_H });
  const texts = layout.columns.map((col) => svgEl("text", { class: "rhead", x: col.x + CELL_W / 2, y: HEADER_H - 10 }, labelOf(col.key)));
  scene.headers.replaceChildren(rule, ...texts);
}

/** Move every element to `layout` (see route_layout.js) and size the picture. */
export function placeScene(scene, layout, labelOf) {
  for (const [id, el] of scene.nodeEls) {
    const spot = layout.places.get(id);
    if (spot) el.setAttribute("transform", `translate(${spot.x.toFixed(1)} ${spot.y.toFixed(1)})`);
  }
  scene.edgeEls.forEach((entry) => placeEdge(entry, layout.places));
  placeHeaders(scene, layout, labelOf);
  scene.svg.setAttribute("viewBox", `0 0 ${layout.width} ${layout.height}`);
  scene.svg.dataset.width = layout.width;
  scene.svg.dataset.height = layout.height;
}

// ---------- legend ----------

function legendItem(picture, text) {
  const box = document.createElement("span");
  box.className = "legend-item";
  box.append(picture, text);
  return box;
}

function legendGlyph(family) {
  return svgEl("svg", { class: "legend-glyph", viewBox: "-26 -18 52 36", "aria-hidden": "true" }, glyph(family));
}

function legendLine(kind) {
  const line = svgEl("g", { class: `redge ${kind}` }, svgEl("line", { x1: 2, y1: 5, x2: 34, y2: 5 }));
  const picture = svgEl("svg", { class: "legend-line", viewBox: "0 0 36 10", "aria-hidden": "true" }, line);
  return legendItem(picture, STRINGS.legendLines[kind]);
}

/** What the shapes and lines mean, for a reader who has never seen a P&ID. */
export function legend(hasWrong) {
  const row = document.createElement("div");
  row.className = "route-legend";
  for (const family of ["equipment", "valve", "instrument", "other"]) {
    row.append(legendItem(legendGlyph(family), STRINGS.legendFamilies[family]));
  }
  row.append(legendLine("flow"), legendLine("signal"), legendLine("gap"));
  const marks = hasWrong ? ["now", "answer", "asked", "wrong"] : ["now", "answer", "asked"];
  for (const mark of marks) {
    const swatch = el("span", { className: `legend-swatch ${mark}`, textContent: mark === "wrong" ? "\u2715" : "" });
    row.append(legendItem(swatch, STRINGS.legendMarks[mark]));
  }
  return row;
}
