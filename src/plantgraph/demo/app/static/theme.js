/* Light / dark theme. The choice is auto (follow the system), light or dark; "auto" is resolved
   here, so the CSS only ever sees data-theme="light" or "dark". */

import { STRINGS } from "./strings.js";

const KEY = "pgdemo.theme";
const ORDER = ["auto", "light", "dark"];
const SYSTEM_DARK = window.matchMedia("(prefers-color-scheme: dark)");

let choice = "auto";

function readChoice() {
  try {
    const saved = localStorage.getItem(KEY);
    return ORDER.includes(saved) ? saved : "auto";
  } catch {
    return "auto"; // storage blocked (private mode): the choice lasts for this visit only
  }
}

function saveChoice() {
  try { localStorage.setItem(KEY, choice); } catch { /* not remembered; that is fine */ }
}

function apply(button) {
  const dark = choice === "dark" || (choice === "auto" && SYSTEM_DARK.matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  button.textContent = STRINGS.themeIcon[choice];
  button.title = STRINGS.themeLabel[choice];
  button.setAttribute("aria-label", STRINGS.themeLabel[choice]);
}

/** Apply the saved choice to `button` and make a click cycle auto -> light -> dark. */
export function initTheme(button) {
  choice = readChoice();
  apply(button);
  SYSTEM_DARK.addEventListener("change", () => apply(button));
  button.addEventListener("click", () => {
    choice = ORDER[(ORDER.indexOf(choice) + 1) % ORDER.length];
    saveChoice();
    apply(button);
  });
}
