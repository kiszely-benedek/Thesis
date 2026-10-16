/* The interactive route view of an answer card: the plant items the system looked at, step by step,
   drawn as P&ID glyphs with the direct drawing connections between them (the server's `route`).
   This module wires state and events; the picture is route_draw.js, the positions route_layout.js,
   the toolbar route_controls.js. All of the route's elements exist from the start; a step only shows
   or hides them, so the picture holds still while it is stepped through. */

import { el } from "./dom.js";
import { labelSection } from "./labels.js";
import { cardSection } from "./parts.js";
import { buildScene, legend, placeScene, plainClass } from "./route_draw.js";
import { routeControls } from "./route_controls.js";
import { pathLayout, stepLayout } from "./route_layout.js";
import { STRINGS } from "./strings.js";
import { jumpToPage } from "./viewer.js";

const ZOOM_MIN = 0.3;
const ZOOM_MAX = 2.5;
const ZOOM_STEP = 1.25;
// the picture starts shrunk to the card's width, but never so small that tags become unreadable
const START_ZOOM_MIN = 0.8;
const TIP_GAP_PX = 8;

const clamp = (value, low, high) => Math.min(high, Math.max(low, value));

function sheetsText(node) {
  return node.sheets.length === 0 ? STRINGS.noSheets : node.sheets.map((s) => `DWG ${s.sheet_id}`).join(", ");
}

/** Whether an item is drawn at `step`: shown from the step that first showed it; question-only items
    from the start; answer-only items at the last step. */
function shownAt(node, step, last) {
  if (node.first_step !== null) return node.first_step <= step;
  return node.in_question || step >= last;
}

/** An answer item the reference answer does not contain (only judged when a reference is known). */
function isWrong(node, reference) {
  return reference !== null && node.in_answer && !reference.has(node.tag);
}

function tipContent(node, names, wrong) {
  const lines = [
    el("strong", { className: "mono", textContent: node.tag ?? STRINGS.routeNoTag }),
    el("span", {}, plainClass(node, names)),
    el("span", {}, node.unit_id === null ? STRINGS.routeNoUnit : STRINGS.routeUnit(node.unit_id)),
    el("span", {}, `${STRINGS.routeSheets}: ${sheetsText(node)}`),
  ];
  if (node.first_step !== null) lines.push(el("span", {}, STRINGS.routeFirstSeen(node.first_step + 1)));
  if (node.in_answer) lines.push(el("span", {}, STRINGS.routeInAnswer));
  if (wrong) lines.push(el("span", {}, STRINGS.routeNotInReference));
  if (node.in_question) lines.push(el("span", {}, STRINGS.routeInQuestion));
  lines.push(el("span", { className: "hint" }, node.sheets.length > 0 ? STRINGS.routeClickHint : STRINGS.routeNoSheetHint));
  return lines;
}

/** The route-view card section for `route`. `reference` is the set of tags of the reference answer
    when the example's answer was wrong (else null): answer items outside it get a cross. */
export function routeSection(route, sync, reference) {
  const names = labelSection("class_names");
  const last = Math.max(0, route.steps.length - 1);
  const byId = new Map(route.nodes.map((node) => [node.item_id, node]));
  const wrongIds = new Set(route.nodes.filter((n) => isWrong(n, reference)).map((n) => n.item_id));
  const notInReference = (node) => (wrongIds.has(node.item_id) ? `, ${STRINGS.routeNotInReference}` : "");
  const describe = (node) => `${node.tag ?? plainClass(node, names)}, ${plainClass(node, names)}, ${sheetsText(node)}${notInReference(node)}`;
  const scene = buildScene(route, names, describe, wrongIds);
  const layouts = { step: stepLayout(route), path: route.answer_path.length > 0 ? pathLayout(route) : null };
  const pathIds = new Set(route.answer_path);
  const sheetTurn = new Map();   // item id -> index of the sheet its last click showed
  let pathMode = false;
  let zoom = 1;

  const canvas = el("div", { className: "route-canvas" }, scene.svg);
  const tip = el("div", { className: "route-tip", role: "tooltip" });
  const note = el("p", { className: "hint route-note" });
  note.setAttribute("aria-live", "polite");
  const stage = el("div", { className: "route-stage" }, canvas, tip);

  // ---------- which items and edges are drawn ----------

  function showStep() {
    const step = sync.current;
    const final = pathMode || step >= last;
    const stepping = route.steps.length > 1 && !pathMode;
    const visible = new Set();
    for (const node of route.nodes) {
      const shown = pathMode ? pathIds.has(node.item_id) : shownAt(node, step, last);
      if (shown) visible.add(node.item_id);
      const nodeEl = scene.nodeEls.get(node.item_id);
      nodeEl.toggleAttribute("hidden", !shown);
      nodeEl.classList.toggle("now", shown && stepping && node.first_step === step);
      nodeEl.classList.toggle("answer", shown && final && node.in_answer);
    }
    for (const { edge, el: edgeEl } of scene.edgeEls) {
      const ends = visible.has(edge.source) && visible.has(edge.target);
      const wanted = edge.relation !== "none" || final;   // a path gap only means something at the end
      edgeEl.toggleAttribute("hidden", !(ends && wanted && (!pathMode || edge.on_answer_path)));
    }
    scene.svg.classList.toggle("final", final);
  }

  // ---------- zoom ----------

  function setZoom(value) {
    zoom = clamp(value, ZOOM_MIN, ZOOM_MAX);
    const { width, height } = scene.svg.dataset;
    scene.svg.setAttribute("width", Math.round(width * zoom));
    scene.svg.setAttribute("height", Math.round(height * zoom));
  }

  function startZoom() {
    setZoom(clamp(canvas.clientWidth / scene.svg.dataset.width, START_ZOOM_MIN, 1));
  }

  function zoomBy(kind) {
    if (kind === "in") setZoom(zoom * ZOOM_STEP);
    if (kind === "out") setZoom(zoom / ZOOM_STEP);
    if (kind === "fit") {
      const { width, height } = scene.svg.dataset;
      setZoom(Math.min(canvas.clientWidth / width, canvas.clientHeight / height));
    }
  }

  // ---------- layouts ----------

  function layOut() {
    const layout = pathMode ? layouts.path : layouts.step;
    placeScene(scene, layout, (key) => STRINGS.routeColumn(key));
    showStep();
    startZoom();
    canvas.scrollTo(0, 0);
  }

  const controls = routeControls({
    steps: route.steps,
    sync,
    hasPath: layouts.path !== null,
    view: {
      onPath(on) { pathMode = on; controls.setPathMode(on); layOut(); },
      onZoom: zoomBy,
    },
  });

  // ---------- tooltip, click, keyboard ----------

  function hideTip() {
    tip.classList.remove("shown");
  }

  function showTip(nodeEl) {
    tip.replaceChildren(...tipContent(byId.get(nodeEl.dataset.id), names, wrongIds.has(nodeEl.dataset.id)));
    tip.classList.add("shown");
    const at = nodeEl.getBoundingClientRect();
    const box = stage.getBoundingClientRect();
    const half = tip.offsetWidth / 2;
    const centre = clamp(at.left + at.width / 2 - box.left, half + 4, Math.max(half + 4, box.width - half - 4));
    const below = at.bottom - box.top + TIP_GAP_PX;
    const fitsBelow = below + tip.offsetHeight <= box.height;
    tip.style.left = `${centre}px`;
    tip.style.top = `${fitsBelow ? below : at.top - box.top - tip.offsetHeight - TIP_GAP_PX}px`;
  }

  /** Jump the PDF to the item's next sheet: its first on the first click, then round the others. */
  function showOnDrawing(nodeEl) {
    const node = byId.get(nodeEl.dataset.id);
    if (node.sheets.length === 0) {
      note.textContent = STRINGS.routeNoSheetNote(node.tag ?? node.item_id);
      return;
    }
    const turn = ((sheetTurn.get(node.item_id) ?? -1) + 1) % node.sheets.length;
    sheetTurn.set(node.item_id, turn);
    jumpToPage(node.sheets[turn].page);
    note.textContent = STRINGS.routeShowing(node.tag ?? node.item_id, node.sheets[turn].sheet_id, turn + 1, node.sheets.length);
  }

  const nodeOf = (event) => event.target.closest?.(".rnode") ?? null;
  scene.svg.addEventListener("click", (event) => { const n = nodeOf(event); if (n) showOnDrawing(n); });
  scene.svg.addEventListener("pointerover", (event) => { const n = nodeOf(event); if (n) showTip(n); });
  scene.svg.addEventListener("pointerout", hideTip);
  scene.svg.addEventListener("focusin", (event) => { const n = nodeOf(event); if (n) showTip(n); });
  scene.svg.addEventListener("focusout", hideTip);
  scene.svg.addEventListener("keydown", (event) => {
    const n = nodeOf(event);
    if (n && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); showOnDrawing(n); }
  });

  const root = el("div", { className: "route-view" }, controls.node, stage, note, legend(wrongIds.size > 0));
  root.addEventListener("keydown", (event) => {
    if (event.key === "Escape") hideTip();
    const direction = { ArrowLeft: -1, ArrowRight: 1 }[event.key];
    // the slider already steps with the arrow keys itself
    if (!direction || pathMode || route.steps.length < 2 || event.target.matches("input")) return;
    event.preventDefault();
    sync.select(clamp(sync.current + direction, 0, last));
  });

  sync.onChange(showStep);
  placeScene(scene, layouts.step, (key) => STRINGS.routeColumn(key));
  showStep();
  requestAnimationFrame(startZoom);   // the card is in the page by then, so the width is known

  const parts = [el("p", { className: "hint" }, STRINGS.routeViewHint), root];
  if (route.omitted_nodes > 0) parts.push(el("p", { className: "notice" }, STRINGS.routeOmitted(route.omitted_nodes)));
  return cardSection(STRINGS.routeViewHeading, ...parts);
}
