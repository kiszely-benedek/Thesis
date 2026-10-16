/* The Ask | Results tab switch in the header (the ARIA tabs pattern: arrow keys move between tabs).
   The Ask view is hidden, never removed, so the PDF viewer keeps its page when the visitor comes back. */

import { $ } from "./dom.js";
import { showResults } from "./results.js";
import { STRINGS } from "./strings.js";

const TABS = ["ask", "results"];
const RESULTS_HASH = "#results"; // lets a reload or a shared link open the Results tab

/** Show one tab's view and mark its button selected; the other tab's view is hidden. */
function select(name, focus = false) {
  for (const tab of TABS) {
    const button = $(`tab-${tab}`);
    button.setAttribute("aria-selected", String(tab === name));
    button.tabIndex = tab === name ? 0 : -1; // roving tabindex: one Tab stop for the pair
    $(`${tab}-view`).hidden = tab !== name;
  }
  if (focus) $(`tab-${name}`).focus();
  history.replaceState(null, "", name === "results" ? RESULTS_HASH : location.pathname + location.search);
  if (name === "results") showResults();
}

/** Left/Right move between the two tabs (wrapping), Home and End jump to the first and last. */
function onKey(event) {
  const current = TABS.findIndex((tab) => $(`tab-${tab}`) === event.target);
  const target = { ArrowRight: current + 1, ArrowLeft: current - 1, Home: 0, End: TABS.length - 1 }[event.key];
  if (current < 0 || target === undefined) return;
  event.preventDefault();
  select(TABS[(target + TABS.length) % TABS.length], true);
}

/** Label the tabs, wire them, and open the tab the address asks for (Ask by default). */
export function initTabs() {
  $("tablist").setAttribute("aria-label", STRINGS.tabsLabel);
  $("tab-ask").textContent = STRINGS.tabAsk;
  $("tab-results").textContent = STRINGS.tabResults;
  for (const tab of TABS) $(`tab-${tab}`).addEventListener("click", () => select(tab));
  $("tablist").addEventListener("keydown", onKey);
  select(location.hash === RESULTS_HASH ? "results" : "ask");
}
