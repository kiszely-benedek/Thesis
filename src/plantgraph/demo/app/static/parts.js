/* Small building blocks shared by the answer card and its details. */

import { el } from "./dom.js";

/** A card section: a small upper-case heading over its content. */
export function cardSection(heading, ...content) {
  return el("section", { className: "card-section" }, el("h2", { className: "field-label" }, heading), ...content);
}

/** A caption over a value; each is a string, a node, or an array of nodes. */
function pair(caption, value) {
  return [el("dt", {}, ...[caption].flat()), el("dd", {}, ...[value].flat())];
}

/** A caption/value list: `rows` is [[caption, value], ...]. */
export function facts(rows) {
  return el("dl", { className: "facts" }, ...rows.flatMap(([caption, value]) => pair(caption, value)));
}

/** A table with a header row; `cells` is an array of rows, each an array of strings or nodes.
    Columns whose index is in `numeric` are right-aligned, in the figures' monospace face. */
export function table(headings, cells, numeric = [], className = "") {
  const kind = (column) => (numeric.includes(column) ? "num" : "");
  const head = el("tr", {}, ...headings.map((name, c) => el("th", { scope: "col", className: kind(c) }, name)));
  const rows = cells.map((row) => el("tr", {}, ...row.map((cell, c) => el("td", { className: kind(c) }, cell))));
  const grid = el("table", {}, el("thead", {}, head), el("tbody", {}, ...rows));
  return el("div", { className: `table-wrap ${className}`.trim() }, grid);
}
