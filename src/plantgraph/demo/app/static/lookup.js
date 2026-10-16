/* The one search box over the drawings. A sheet number jumps to that sheet; a tag shows its card
   and opens its first sheet; typing a prefix lists matching tags (an ARIA combobox: arrow keys move
   through the list, Enter picks, Escape closes). The tags come from the server, which reads them
   from the selected plant's in-memory graph, so it works for any plant on the page. */

import { getTags } from "./api.js";
import { $, el } from "./dom.js";
import { describeError } from "./labels.js";
import { renderHits, renderNone } from "./lookup_card.js";
import { page } from "./state.js";
import { STRINGS } from "./strings.js";
import { jumpToPage } from "./viewer.js";

const TYPING_DELAY_MS = 180;
/** A sheet number, with or without the "DWG" in front. */
const SHEET_NUMBER = /^(?:DWG\s*)?(\d+)$/i;

let suggestions = [];  // the tags in the open list
let active = -1;       // index of the highlighted option, -1 for none
let typingTimer = null;
let latestRequest = 0; // answers of older requests are dropped

const input = () => $("dwg-input");
const message = (text) => { $("dwg-message").textContent = text; };

function closeList() {
  suggestions = [];
  active = -1;
  $("find-list").hidden = true;
  $("find-list").replaceChildren();
  input().setAttribute("aria-expanded", "false");
  input().removeAttribute("aria-activedescendant");
}

function highlight(index) {
  active = index;
  const options = [...$("find-list").children];
  options.forEach((option, i) => option.setAttribute("aria-selected", String(i === index)));
  if (index < 0) { input().removeAttribute("aria-activedescendant"); return; }
  input().setAttribute("aria-activedescendant", options[index].id);
  options[index].scrollIntoView({ block: "nearest" });
}

function openList(tags) {
  suggestions = tags;
  const list = $("find-list");
  list.setAttribute("aria-label", STRINGS.findSuggestionsLabel);
  list.replaceChildren(...tags.map((tag, i) => {
    const option = el("li", { id: `find-option-${i}`, className: "find-option", textContent: tag });
    option.setAttribute("role", "option");
    option.setAttribute("aria-selected", "false");
    // mousedown, not click: the click would first blur the box and close the list
    option.addEventListener("mousedown", (event) => { event.preventDefault(); pick(tag); });
    return option;
  }));
  list.hidden = tags.length === 0;
  input().setAttribute("aria-expanded", String(tags.length > 0));
  active = -1;
}

/** Ask the server about `query`; null if the plant changed or a newer request has replaced this one. */
async function fetchTags(query) {
  const request = ++latestRequest;
  const corpusId = page.corpusId;
  try {
    const found = await getTags(corpusId, query);
    return request === latestRequest && corpusId === page.corpusId ? found : null;
  } catch (error) {
    if (request === latestRequest) message(describeError(error).text);
    return null;
  }
}

/** Show the card (or the "nothing found" message) for `query`; the first hit opens on the drawing. */
async function showResult(query) {
  const found = await fetchTags(query);
  if (found === null) return;
  closeList();
  const host = $("find-card");
  if (found.hits.length === 0) {
    renderNone(host, query, found.suggestions, pick);
    return;
  }
  renderHits(host, found.hits);
  const first = found.hits[0].sheets[0];
  if (first) jumpToPage(first.page);
}

/** Take a tag from the list or from a "did you mean" button. */
function pick(tag) {
  input().value = tag;
  closeList();
  message("");
  showResult(tag);
}

async function suggest(query) {
  const found = await fetchTags(query);
  if (found !== null) openList(found.suggestions);
}

/** The Find button and Enter: a sheet number jumps, anything else is looked up as a tag. */
function submit() {
  clearTimeout(typingTimer);
  const query = input().value.trim();
  message("");
  if (query === "") { hideCard(); closeList(); return; }
  if (page.corpusId === null) { message(STRINGS.dwgNoPlant); return; }
  const sheet = SHEET_NUMBER.exec(query)?.[1];
  const target = sheet === undefined ? undefined : page.index?.pages[sheet];
  if (target !== undefined) { closeList(); hideCard(); jumpToPage(target); return; }
  showResult(query);
}

function hideCard() {
  $("find-card").hidden = true;
  $("find-card").replaceChildren();
}

function onTyping() {
  clearTimeout(typingTimer);
  const query = input().value.trim();
  if (query === "" || page.corpusId === null || SHEET_NUMBER.test(query)) { closeList(); return; }
  typingTimer = setTimeout(() => suggest(query), TYPING_DELAY_MS);
}

function onKey(event) {
  const open = suggestions.length > 0;
  const step = { ArrowDown: 1, ArrowUp: -1 }[event.key];
  if (step !== undefined && open) {
    event.preventDefault();
    // positions run -1 (the box itself), 0 ... n-1 (the options), then wrap round
    const positions = suggestions.length + 1;
    highlight((((active + 1 + step) % positions) + positions) % positions - 1);
  } else if (event.key === "Enter") {
    event.preventDefault();
    if (open && active >= 0) pick(suggestions[active]);
    else submit();
  } else if (event.key === "Escape" && open) {
    closeList();
  }
}

/** Forget the box and the card (the plant on the page changed). */
export function resetLookup() {
  clearTimeout(typingTimer);
  latestRequest += 1;
  input().value = "";
  message("");
  closeList();
  hideCard();
}

/** Wire the search box (call once at start-up). */
export function initLookup() {
  $("dwg-label").textContent = STRINGS.dwgLabel;
  $("dwg-go").textContent = STRINGS.dwgGo;
  input().placeholder = STRINGS.dwgPlaceholder;
  $("dwg-go").addEventListener("click", submit);
  input().addEventListener("input", onTyping);
  input().addEventListener("keydown", onKey);
  input().addEventListener("blur", closeList);
}
