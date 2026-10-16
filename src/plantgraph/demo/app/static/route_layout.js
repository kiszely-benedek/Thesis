/* Where each item of the route view sits. Pure functions, no DOM; deterministic, so the same answer
   always draws the same picture (a force layout would jitter between runs).

   Stepwise layout: one column per step that showed items, in order. Items only the question names go
   in a first column, items only the answer names in a last one. Rows keep order of appearance, then
   two relaxation passes reorder each column by the mean row of its neighbours to shorten the edges. */

export const CELL_W = 104;
export const CELL_H = 80;
export const HEADER_H = 34;
export const PAD = 16;
// a column taller than this wraps into a second, third... lane so 50 items stay legible
const MAX_ROWS = 9;
const PATH_ROW_LENGTH = 6;
// room right of the last column for the text of a sheet-crossing edge that runs straight down
const RIGHT_MARGIN = 60;
const RELAX_PASSES = 2;

/** The column an item sits in: "q" (question only), a step number, or "a" (answer only). */
export function columnKey(node) {
  if (node.first_step !== null) return node.first_step;
  return node.in_question ? "q" : "a";
}

function sortColumnKeys(keys) {
  const rank = (key) => (key === "q" ? -1 : key === "a" ? Infinity : key);
  return [...keys].sort((a, b) => rank(a) - rank(b));
}

function groupByColumn(nodes) {
  const groups = new Map();
  for (const node of nodes) {
    const key = columnKey(node);
    groups.set(key, [...(groups.get(key) ?? []), node.item_id]);
  }
  return new Map(sortColumnKeys(groups.keys()).map((key) => [key, groups.get(key)]));
}

/** Item id -> the ids it shares an edge with. */
function neighbourMap(nodes, edges) {
  const map = new Map(nodes.map((node) => [node.item_id, []]));
  for (const edge of edges) {
    map.get(edge.source)?.push(edge.target);
    map.get(edge.target)?.push(edge.source);
  }
  return map;
}

/** Mean row of an item's neighbours, or its own row when it has none placed. */
function pull(id, row, neighbours, ownRow) {
  const rows = neighbours.get(id).filter((other) => row.has(other)).map((other) => row.get(other));
  return rows.length === 0 ? ownRow : rows.reduce((a, b) => a + b, 0) / rows.length;
}

/** Reorder the rows of every column by their neighbours' mean row (barycenter heuristic). */
function relax(columns, neighbours) {
  const row = new Map();
  for (const ids of columns.values()) ids.forEach((id, i) => row.set(id, i));
  for (let pass = 0; pass < RELAX_PASSES; pass += 1) {
    for (const [key, ids] of columns) {
      const ranked = ids.map((id, i) => ({ id, rank: pull(id, row, neighbours, i) }));
      ranked.sort((a, b) => a.rank - b.rank);   // stable: ties keep order of appearance
      columns.set(key, ranked.map((entry) => entry.id));
      ranked.forEach((entry, i) => row.set(entry.id, i));
    }
  }
}

/** Positions of the stepwise layout: `{ places: Map(id -> {x, y}), columns: [{key, x}], width, height }`.
    (x, y) is the centre of the item's cell. */
export function stepLayout(route) {
  const columns = groupByColumn(route.nodes);
  relax(columns, neighbourMap(route.nodes, route.edges));
  const places = new Map();
  const headers = [];
  let lane = 0;
  let tallest = 1;
  for (const [key, ids] of columns) {
    headers.push({ key, x: PAD + lane * CELL_W });
    for (let start = 0; start < ids.length; start += MAX_ROWS) {
      const chunk = ids.slice(start, start + MAX_ROWS);
      chunk.forEach((id, i) => places.set(id, cellCentre(lane, i)));
      tallest = Math.max(tallest, chunk.length);
      lane += 1;
    }
  }
  return { places, columns: headers, width: PAD * 2 + lane * CELL_W + RIGHT_MARGIN, height: HEADER_H + PAD * 2 + tallest * CELL_H };
}

function cellCentre(lane, row) {
  return { x: PAD + lane * CELL_W + CELL_W / 2, y: HEADER_H + PAD + row * CELL_H + CELL_H / 2 };
}

/** The answer path as a snake: rows of six, left to right then right to left, so each hop stays short. */
export function pathLayout(route) {
  const ids = [...new Set(route.answer_path)];
  const places = new Map();
  ids.forEach((id, i) => {
    const row = Math.floor(i / PATH_ROW_LENGTH);
    const offset = i % PATH_ROW_LENGTH;
    places.set(id, cellCentre(row % 2 === 0 ? offset : PATH_ROW_LENGTH - 1 - offset, row));
  });
  const rows = Math.max(1, Math.ceil(ids.length / PATH_ROW_LENGTH));
  return { places, columns: [], width: PAD * 2 + PATH_ROW_LENGTH * CELL_W + RIGHT_MARGIN, height: HEADER_H + PAD * 2 + rows * CELL_H };
}
