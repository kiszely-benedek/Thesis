/* Presentation mode: a step bar over a short talk on one plant. "Next" puts the step's example
   question in the box and asks it live; nothing is pre-answered. The talks come from the
   server (`/api/presentation`, read from the local demo config). */

import { getPresentation } from "./api.js";
import { askNow, fillExample } from "./ask.js";
import { $, el } from "./dom.js";
import { clearMessage, showMessage } from "./message.js";
import { canAsk, currentCorpus, page } from "./state.js";
import { STRINGS } from "./strings.js";
import { showTab } from "./tabs.js";

const talk = {
  active: false,
  sequences: [],  // the server's sequences: {corpus_id, title, items}
  current: null,  // the running sequence, or null while the visitor is choosing
  index: 0,       // the running sequence's current step
};

// Presentation clickers send PageDown/PageUp; Space and the arrows are the keyboard's.
const NEXT_KEYS = ["ArrowRight", "PageDown", " "];
const BACK_KEYS = ["ArrowLeft", "PageUp"];
// Keys that a focused control of this kind uses itself, so the talk must not take them.
const TYPING_TAGS = ["INPUT", "TEXTAREA", "SELECT"];
const CLICKABLE_TAGS = ["BUTTON", "A", "SUMMARY"];

// --- state of the talk -----------------------------------------------------------------------

function item() {
  return talk.current.items[talk.index];
}

function isLast() {
  return talk.index >= talk.current.items.length - 1;
}

/** Why `sequence` cannot start right now, or null when it can. */
function blocker(sequence) {
  const corpus = currentCorpus();
  if (sequence.corpus_id !== page.corpusId || !corpus || corpus.state !== "ready") {
    return STRINGS.presentSwitchFirst(sequence.corpus_id);
  }
  if (!page.status.plant.held.includes(sequence.corpus_id) || page.status.plant.loading) {
    return STRINGS.presentPlantNotHeld(sequence.corpus_id);
  }
  const missing = sequence.items.find((i) => i.missing !== null);
  return missing ? STRINGS.presentMissing(missing.question_id ?? "?", missing.missing) : null;
}

/** Show step `index`: its example in the box and, when `ask`, asked live now. */
async function goTo(index, ask) {
  talk.index = index;
  clearMessage();
  if (item().kind === "results") {
    showTab("results");
  } else {
    showTab("ask");
    if (!fillExample(item().question_id)) showMessage(STRINGS.presentMissing(item().question_id, "unknown_question"), true);
    else if (ask) await askNow();
  }
  renderPresent();
}

function start(sequence) {
  if (blocker(sequence) !== null) return; // the picker disables such a button; this is a guard
  talk.current = sequence;
  goTo(0, true);
}

/** Move one step; going forward asks the next example live, going back only shows its question. */
function step(delta) {
  const target = talk.index + delta;
  if (talk.current === null || page.asking) return;
  if (target < 0 || target >= talk.current.items.length) return;
  const asks = delta > 0 && talk.current.items[target].kind === "example";
  if (asks && !canAsk()) return; // plant loading or not held: asking now would be refused
  goTo(target, asks);
}

// --- the bar ---------------------------------------------------------------------------------

function sequenceButton(sequence) {
  const reason = blocker(sequence);
  const text = STRINGS.presentSequence(sequence.title, sequence.items.length);
  const button = el("button", { type: "button", className: "text-button", textContent: text });
  button.disabled = reason !== null;
  button.addEventListener("click", () => start(sequence));
  return button;
}

/** One line per sequence that cannot start, so a refusal is explained, not just greyed out. */
function blockedNote() {
  const lines = talk.sequences.map((s) => [s, blocker(s)]).filter(([, reason]) => reason !== null);
  return lines.map(([s, reason]) => `${s.title}: ${reason}`).join(" · ");
}

function renderChoice() {
  $("present-counter").textContent = "";
  $("present-title").textContent = talk.sequences.length ? STRINGS.presentChoose : STRINGS.presentNone;
  $("present-sequences").replaceChildren(...talk.sequences.map(sequenceButton));
  $("present-question").textContent = "";
  $("present-note").textContent = blockedNote();
}

function renderRunning() {
  const { items } = talk.current;
  $("present-counter").textContent = STRINGS.presentCounter(talk.index + 1, items.length);
  $("present-title").textContent = talk.current.title;
  $("present-sequences").replaceChildren();
  $("present-question").textContent = item().kind === "results" ? STRINGS.presentResultsStep : item().text;
  $("present-note").textContent = STRINGS.presentKeys;
}

/** Redraw the bar from the talk's state (called by the page's render and after every step). */
export function renderPresent() {
  document.documentElement.classList.toggle("present", talk.active);
  $("present-bar").hidden = !talk.active;
  if (!talk.active) return;
  const running = talk.current !== null;
  if (running) renderRunning(); else renderChoice();
  $("present-back").disabled = !running || talk.index === 0 || page.asking;
  $("present-next").disabled = !running || isLast() || page.asking;
  $("present-back").hidden = $("present-next").hidden = !running;
}

// --- entering, leaving, keys -------------------------------------------------------------------

async function loadSequences() {
  talk.sequences = (await getPresentation()).sequences;
  renderPresent();
}

/** Re-read the sequences while the visitor is choosing, so a plant that finished loading shows up. */
export async function refreshPresent() {
  if (talk.active && talk.current === null) await loadSequences().catch(() => {});
}

async function enter() {
  talk.active = true;
  talk.current = null;
  renderPresent();
  try {
    await loadSequences();
  } catch (error) {
    showMessage(STRINGS.presentLoadFailed, true, String(error.message));
  }
}

function exit() {
  talk.active = false;
  talk.current = null;
  showTab("ask");
  renderPresent();
}

function onKey(event) {
  if (!talk.active || event.ctrlKey || event.metaKey || event.altKey) return;
  if (event.key === "Escape" && !TYPING_TAGS.includes(event.target.tagName)) { exit(); return; }
  if (TYPING_TAGS.includes(event.target.tagName)) return;
  const forward = NEXT_KEYS.includes(event.key);
  if (event.key === " " && CLICKABLE_TAGS.includes(event.target.tagName)) return; // Space presses a button
  if (!forward && !BACK_KEYS.includes(event.key)) return;
  event.preventDefault();
  step(forward ? 1 : -1);
}

/** Label the controls and wire them; opens at once when the address says `?mode=present`. */
export function initPresent() {
  $("present-open").textContent = STRINGS.presentOpen;
  $("present-back").textContent = STRINGS.presentBack;
  $("present-next").textContent = STRINGS.presentNext;
  $("present-exit").textContent = STRINGS.presentExit;
  $("present-bar").setAttribute("aria-label", STRINGS.presentBarLabel);
  $("present-open").addEventListener("click", enter);
  $("present-back").addEventListener("click", () => step(-1));
  $("present-next").addEventListener("click", () => step(1));
  $("present-exit").addEventListener("click", exit);
  document.addEventListener("keydown", onKey);
  if (new URLSearchParams(location.search).get("mode") === "present") enter();
}
