/* The result card of the tag lookup: one row per item that carries the searched tag.
   Reads, from the top: tag, plain class name, unit, then the sheets the item is drawn on. */

import { el } from "./dom.js";
import { labelSection } from "./labels.js";
import { STRINGS } from "./strings.js";
import { term } from "./glossary.js";
import { jumpToPage } from "./viewer.js";

/** The class in plain words (`centrifugal pump`); a class without a plain name is shown as it is. */
function plainClass(code) {
  const names = labelSection("class_names");
  if (!(code in names)) console.warn(`expected a plain name for the class "${code}" in labels.en.json, found none`);
  return names[code] ?? code;
}

/** One chip per sheet; a click jumps the drawing to that sheet. */
function sheetChips(sheets) {
  const box = el("div", { className: "chips" });
  for (const sheet of sheets) {
    const chip = el("button", { type: "button", className: "chip", textContent: `DWG ${sheet.sheet_id}` });
    chip.addEventListener("click", () => jumpToPage(sheet.page));
    box.append(chip);
  }
  return box;
}

/** The tag as a button: each click shows the item's next sheet, round the list. `turn` is the sheet
    the drawing already shows (0 for the first row, which the lookup opened; -1 for a row not shown yet). */
function tagButton(hit, turn) {
  const ids = hit.sheets.map((sheet) => sheet.sheet_id);
  const button = el("button", { type: "button", className: "find-tag", textContent: hit.tag ?? hit.item_id });
  if (ids.length === 0) { button.disabled = true; return button; }
  button.title = STRINGS.findNextSheet(ids);
  button.addEventListener("click", () => {
    turn = (turn + 1) % ids.length;
    jumpToPage(hit.sheets[turn].page);
  });
  return button;
}

function hitRow(hit, row) {
  const facts = el("span", { className: "find-facts" },
    el("span", { className: "find-class" }, plainClass(hit.node_class)),
    el("span", { className: "hint mono" }, hit.node_class));
  if (hit.unit_id !== null) facts.append(el("span", {}, term("unit", STRINGS.findUnit), ` ${hit.unit_id}`));
  const where = hit.sheets.length === 0
    ? el("span", { className: "hint" }, STRINGS.findNoSheets)
    : el("span", { className: "find-where" }, el("span", { className: "hint" }, STRINGS.findOnSheets(hit.sheets.length)), sheetChips(hit.sheets));
  return el("div", { className: "find-row" }, tagButton(hit, row === 0 ? 0 : -1), facts, where);
}

/** Fill `host` with one row per hit and show it (the caller opens the first row's first sheet). */
export function renderHits(host, hits) {
  host.replaceChildren(...hits.map(hitRow));
  host.hidden = false;
}

/** Fill `host` with the "nothing found" message and up to ten suggestion buttons. */
export function renderNone(host, query, suggestions, onPick) {
  const buttons = suggestions.map((tag) => {
    const button = el("button", { type: "button", className: "text-button mono", textContent: tag });
    button.addEventListener("click", () => onPick(tag));
    return button;
  });
  const extra = buttons.length === 0 ? [] : [
    el("span", { className: "hint" }, STRINGS.findDidYouMean),
    el("div", { className: "find-suggest" }, ...buttons),
  ];
  host.replaceChildren(el("div", { className: "find-row" }, el("span", {}, STRINGS.findNone(query)), ...extra));
  host.hidden = false;
}
