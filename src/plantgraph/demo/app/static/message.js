/* The one message box of the ask panel: errors (with folded technical details) and plain notes. */

import { $, el } from "./dom.js";
import { STRINGS } from "./strings.js";

/** Show `text` in the box; `technical` goes in a folded "Technical details" block. */
export function showMessage(text, isError = false, technical = null) {
  const box = $("message");
  box.hidden = !text;
  box.className = isError ? "message error" : "message";
  box.replaceChildren();
  if (!text) return;
  box.append(el("div", {}, text));
  if (technical && technical !== text) {
    box.append(el("details", {}, el("summary", {}, STRINGS.technicalDetails), el("pre", {}, technical)));
  }
}

/** Hide the box. */
export function clearMessage() {
  showMessage(null);
}
