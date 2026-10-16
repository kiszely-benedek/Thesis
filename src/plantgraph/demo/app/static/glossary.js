/* Glossary tooltips: a dotted-underlined word that explains itself on hover, focus or tap.
   One shared tooltip element serves every term, and the listeners sit on `document`, so a term
   added to the page later needs no wiring. */

import { $, el } from "./dom.js";
import { label } from "./labels.js";

const HOVER_DELAY_MS = 150;
const EDGE_PX = 8;   // keep this far from the window edge
const GAP_PX = 8;    // space between the word and the tooltip (room for the arrow)
const MARKUP = /\{\{(\w+)\|([^}]*)\}\}/g;

let activeTerm = null;  // the term whose explanation is showing
let pinned = false;     // opened by a click or tap: stays until Escape, a second click or a click elsewhere
let hoverTimer = null;

/** A word with a glossary explanation; `key` is a key of the `glossary` section of labels.en.json. */
export function term(key, visibleText) {
  const node = el("span", { className: "term", textContent: visibleText, tabIndex: 0 });
  node.dataset.term = key;
  node.setAttribute("aria-describedby", "glossary-tip");
  return node;
}

/** A tier's name as a glossary word: the database-query step or the graph agent, by its strategy. */
export function strategyTerm(strategy, visibleText) {
  return strategy.startsWith("cypher") ? term("cypher", visibleText) : term("agent", visibleText);
}

/** Text with glossary words marked as double braces around "glossary key | visible text", as DOM nodes ready to append. */
export function richText(text) {
  const nodes = [];
  let end = 0;
  for (const match of text.matchAll(MARKUP)) {
    nodes.push(text.slice(end, match.index), term(match[1], match[2]));
    end = match.index + match[0].length;
  }
  nodes.push(text.slice(end));
  return nodes.filter((node) => node !== "");
}

function termOf(event) {
  return event.target instanceof Element ? event.target.closest(".term") : null;
}

function hide() {
  clearTimeout(hoverTimer);
  activeTerm = null;
  pinned = false;
  $("glossary-tip").classList.remove("shown");
}

/** Put the tooltip under the word, or above it when there is no room below. */
function place(tip, word) {
  const wordBox = word.getBoundingClientRect();
  const width = Math.min(tip.offsetWidth, window.innerWidth - 2 * EDGE_PX);
  const left = Math.max(EDGE_PX, Math.min(wordBox.left, window.innerWidth - width - EDGE_PX));
  const fitsBelow = wordBox.bottom + GAP_PX + tip.offsetHeight <= window.innerHeight - EDGE_PX;
  tip.style.left = `${left}px`;
  tip.style.top = `${fitsBelow ? wordBox.bottom + GAP_PX : wordBox.top - GAP_PX - tip.offsetHeight}px`;
  tip.classList.toggle("above", !fitsBelow);
  // the arrow points at the middle of the word, wherever the tooltip box ended up
  tip.style.setProperty("--arrow-x", `${Math.max(12, wordBox.left + wordBox.width / 2 - left)}px`);
}

function show(word) {
  clearTimeout(hoverTimer);
  const tip = $("glossary-tip");
  tip.textContent = label("glossary", word.dataset.term);
  activeTerm = word;
  place(tip, word);
  tip.classList.add("shown");
}

function onHover(event) {
  const word = termOf(event);
  if (word === null || word === activeTerm || event.pointerType !== "mouse") return;
  clearTimeout(hoverTimer);
  hoverTimer = setTimeout(() => show(word), HOVER_DELAY_MS);
}

function onLeave(event) {
  if (termOf(event) === null || event.pointerType !== "mouse") return;
  clearTimeout(hoverTimer);
  if (!pinned) hide();
}

function onFocus(event) {
  const word = termOf(event);
  if (word !== null) show(word); // a keyboard user gets the text at once
}

function onBlur(event) {
  if (termOf(event) !== null) hide();
}

/** A click or tap pins the tooltip (touch has no hover); a second one, or a click elsewhere, closes it. */
function onClick(event) {
  const word = termOf(event);
  if (word === null) { hide(); return; }
  if (pinned && word === activeTerm) { hide(); return; }
  show(word);
  pinned = true;
}

/** The word moves when the page scrolls: follow it, or close the tooltip once the word is out of view. */
function onScroll() {
  if (activeTerm === null) return;
  const box = activeTerm.getBoundingClientRect();
  if (box.bottom < 0 || box.top > window.innerHeight) { hide(); return; }
  place($("glossary-tip"), activeTerm);
}

function onKey(event) {
  if (event.key === "Escape") hide();
}

/** Wire the shared tooltip (call once at start-up). */
export function initGlossary() {
  $("glossary-tip").setAttribute("role", "tooltip");
  document.addEventListener("pointerover", onHover);
  document.addEventListener("pointerout", onLeave);
  document.addEventListener("focusin", onFocus);
  document.addEventListener("focusout", onBlur);
  document.addEventListener("click", onClick);
  document.addEventListener("keydown", onKey);
  document.addEventListener("scroll", onScroll, true); // capture: the panel scrolls, not the page
}
