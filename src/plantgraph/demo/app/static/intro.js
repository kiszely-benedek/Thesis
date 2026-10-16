/* The "What is this?" box: three sentences and three steps, hideable, remembered per viewer. */

import { $, el } from "./dom.js";
import { STRINGS } from "./strings.js";

const KEY = "pgdemo.introHidden";

function wasHidden() {
  try { return localStorage.getItem(KEY) === "1"; } catch { return false; }
}

function remember(hidden) {
  try { localStorage.setItem(KEY, hidden ? "1" : "0"); } catch { /* not remembered; that is fine */ }
}

function stepList(sheetCounts) {
  const shown = sheetCounts.map((n) => n ?? "?"); // a plant that has not loaded yet has no count
  const steps = STRINGS.introSteps(shown[0] ?? "?", shown[1] ?? null);
  const items = steps.map((text, i) => el(
    "li", {}, el("span", { className: "bubble", textContent: String(i + 1) }), el("span", {}, text),
  ));
  return el("ol", { className: "steps" }, ...items);
}

/** Fill the box. `sheetCounts` are the plants' drawing-sheet counts, taken from /api/status. */
export function renderIntro(sheetCounts) {
  const box = $("intro");
  const hide = el("button", { type: "button", className: "link-button", textContent: STRINGS.introHide });
  hide.addEventListener("click", () => setIntroHidden(true));
  box.replaceChildren(
    el("h2", {}, STRINGS.introHeading),
    el("p", {}, STRINGS.introText),
    stepList(sheetCounts),
    el("div", { className: "intro-actions" }, hide),
  );
}

/** Show or hide the box and remember the choice. */
export function setIntroHidden(hidden) {
  $("intro").hidden = hidden;
  $("intro-open").setAttribute("aria-pressed", String(!hidden));
  remember(hidden);
}

/** Wire the header button and apply the remembered state. */
export function initIntro() {
  $("intro").hidden = wasHidden();
  $("intro-open").setAttribute("aria-pressed", String(!$("intro").hidden));
  $("intro-open").addEventListener("click", () => setIntroHidden(false));
}
