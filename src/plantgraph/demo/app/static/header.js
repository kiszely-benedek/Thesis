/* The title block (page header): spend, the plant the database holds, and the narrow-screen menu. */

import { $ } from "./dom.js";
import { term } from "./glossary.js";
import { page } from "./state.js";
import { STRINGS } from "./strings.js";

const SPEND_WARN_SHARE = 0.8;

/** Fill the static captions of the header. */
export function initHeader() {
  $("title").textContent = STRINGS.title;
  $("skip-link").textContent = STRINGS.skipToQuestion;
  document.title = STRINGS.pageTitle;
  $("plant-caption").textContent = STRINGS.plantCell;
  $("held-caption").replaceChildren(term("graph_db", STRINGS.graphDbCell));
  $("spend-caption").textContent = STRINGS.spendCell;
  $("intro-open").textContent = STRINGS.introOpen;
  $("menu-toggle").title = STRINGS.menuOpen;
  $("menu-toggle").setAttribute("aria-label", STRINGS.menuOpen);
  $("menu-toggle").addEventListener("click", toggleMenu);
}

function toggleMenu() {
  const open = $("tools").classList.toggle("open");
  $("menu-toggle").setAttribute("aria-expanded", String(open));
}

/** Show the session spend, in the warning colour once it passes 80 % of the cap. */
export function renderSpend() {
  const spend = page.status.spend;
  const cap = spend.session_cap_usd ?? 0;
  $("spend-value").textContent = STRINGS.spendValue(spend.session_spent_usd, cap);
  $("spend-cell").classList.toggle("warn", cap > 0 && spend.session_spent_usd > SPEND_WARN_SHARE * cap);
}

/** Show which plant the graph database holds. */
export function renderHeld() {
  const held = page.status.plant.held;
  $("held-value").textContent = held.length ? held.join(", ") : STRINGS.graphDbEmpty;
}
