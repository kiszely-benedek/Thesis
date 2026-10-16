/* Tags and sheet ids in an answer as buttons that move the drawing on the left. */

import { el } from "./dom.js";
import { jumpToPage } from "./viewer.js";
import { page } from "./state.js";
import { STRINGS } from "./strings.js";
import { sheetsByTag, splitByTags } from "./tagtext.js";

/** One tag as a button: the first click shows its first sheet, each further click the next one,
    round the list (the same behaviour as a tag in the route view and in the lookup card).
    `turns` (tag -> the sheet shown last) is shared by every mention of the tag in the card. */
function tagButton(tag, sheets, turns) {
  const ids = sheets.map((sheet) => sheet.sheet_id);
  const button = el("button", { type: "button", className: "tag-link", textContent: tag });
  button.title = STRINGS.findNextSheet(ids);
  button.addEventListener("click", () => {
    const turn = ((turns.get(tag) ?? -1) + 1) % sheets.length;
    turns.set(tag, turn);
    jumpToPage(sheets[turn].page);
    button.title = STRINGS.tagShowing(ids, turn);
  });
  return button;
}

/** Make a function turning a text into nodes, with the tags of `answerSheets` as buttons.
    Each call of this factory has its own click state, so one card never disturbs another. */
export function createTagLinker(answerSheets) {
  const byTag = sheetsByTag(answerSheets);
  const tags = [...byTag.keys()];
  const turns = new Map();
  return (text) => splitByTags(text, tags).map((piece) =>
    piece.tag === null ? piece.text : tagButton(piece.tag, byTag.get(piece.tag), turns));
}

/** One chip per sheet id of a SHEET_SET answer; a click jumps the drawing to that sheet.
    An id the drawing index does not know stays a disabled chip, so nothing silently disappears. */
export function sheetIdChips(ids) {
  const box = el("div", { className: "chips" });
  for (const id of ids) {
    const target = page.index?.pages[id];
    const chip = el("button", { type: "button", className: "chip", textContent: `DWG ${id}` });
    if (target === undefined) {
      chip.disabled = true;
      chip.title = STRINGS.sheetNotInIndex(id);
    } else {
      chip.addEventListener("click", () => jumpToPage(target));
    }
    box.append(chip);
  }
  return box;
}
