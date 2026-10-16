/* The plant switch: choose a plant (which loads it into the graph database), watch the load phase
   with live seconds, and keep asking disabled meanwhile. An ask never loads a plant. */

import { getPlant, switchPlant } from "./api.js";
import { $, el, sleep } from "./dom.js";
import { describeError, label } from "./labels.js";
import { fillTemplate } from "./format.js";
import { showMessage } from "./message.js";
import { currentCorpus, page } from "./state.js";
import { STRINGS } from "./strings.js";

const POLL_MS = 1000;
const TICK_MS = 200;
const NO_NOTICE_KINDS = ["ready", "not_needed"];

// The running load's seconds as of the last poll, so the display can count between polls.
const loadClock = { elapsedAtPoll: 0, polledAt: 0 };
let following = false; // one polling loop at a time, however often a load is started

/** Build the radio buttons once, one per configured plant; `onChoose(corpusId)` runs on a change. */
export function initPlantSwitch(onChoose) {
  const group = $("plant-switch");
  for (const corpus of page.status.corpora) {
    const input = el("input", { type: "radio", name: "plant", value: corpus.corpus_id });
    const text = el("span", {}, STRINGS.plantOption(corpus.corpus_id, corpus.n_sheets));
    group.append(el("label", { className: "segment" }, input, text));
    input.addEventListener("change", () => onChoose(corpus.corpus_id));
  }
}

/** Check the selected plant's radio and disable the group while a load or an ask runs. */
export function renderPlantSwitch() {
  const busy = Boolean(page.status.plant.loading) || page.asking;
  for (const input of $("plant-switch").querySelectorAll("input")) {
    input.checked = input.value === page.corpusId;
    input.disabled = busy;
  }
  for (const corpus of page.status.corpora) updateSheetCount(corpus);
}

function updateSheetCount(corpus) {
  const input = $("plant-switch").querySelector(`input[value="${corpus.corpus_id}"]`);
  input.nextElementSibling.textContent = STRINGS.plantOption(corpus.corpus_id, corpus.n_sheets);
}

function loadingText(plant) {
  const elapsed = loadClock.elapsedAtPoll + (performance.now() - loadClock.polledAt) / 1000;
  return STRINGS.plantLoading(plant.loading, elapsed, plant.last_load_s[plant.loading]);
}

function phaseOf(plant) {
  if (plant.loading) return { text: loadingText(plant), kind: "loading" };
  if (plant.error) return { text: STRINGS.plantFailed(page.corpusId ?? "?"), kind: "error" };
  if (plant.last && plant.held.includes(plant.last.corpus_id)) {
    return { text: STRINGS.plantLoaded(plant.last), kind: "done" };
  }
  const text = plant.held.length ? STRINGS.plantHeld(plant.held.join(", ")) : STRINGS.plantNone;
  return { text, kind: plant.held.length ? "idle" : "empty" };
}

/** Show the load phase line (with the running bar while loading). */
export function renderPhase() {
  const { text, kind } = phaseOf(page.status.plant);
  const box = $("plant-phase");
  box.className = `phase ${kind}`;
  $("plant-phase-text").textContent = text;
  $("plant-phase-bar").hidden = kind !== "loading";
}

/** The store notice: why the graph database cannot serve the selected plant right now. */
export function renderStoreNotice() {
  const box = $("store-notice");
  const corpus = currentCorpus();
  const kind = corpus?.store?.kind;
  const quiet = !kind || NO_NOTICE_KINDS.includes(kind) || page.status.plant.loading;
  box.hidden = quiet;
  if (quiet) return;
  const held = (corpus.store.held ?? []).join(", ");
  box.textContent = fillTemplate(label("store_states", kind), { held });
}

/** One-line state of the selected plant (waiting, loading, error) for the status line. */
export function corpusStateText(corpus) {
  const parts = [];
  if (corpus.state !== "ready") parts.push(STRINGS.corpusStates[corpus.state] ?? corpus.state);
  if (!corpus.pdf_present) parts.push(STRINGS.noPdf);
  if (corpus.error_code) parts.push(label("error_codes", corpus.error_code));
  return parts.join("; ");
}

function noteServerElapsed(plant) {
  loadClock.elapsedAtPoll = plant.elapsed_s ?? 0;
  loadClock.polledAt = performance.now();
}

/** Ask the server to load `corpusId`, then follow the load until it ends; `onRender` redraws. */
export async function loadPlant(corpusId, onRender, onFinished) {
  try {
    page.status.plant = await switchPlant(corpusId);
  } catch (error) {
    const { text, technical } = describeError(error);
    showMessage(text, true, technical);
  }
  noteServerElapsed(page.status.plant);
  await followLoad(onRender, onFinished);
}

/** Poll /api/plant once a second while a load runs, redrawing the phase every 200 ms. */
export async function followLoad(onRender, onFinished) {
  if (following) return;
  following = true;
  const ticker = setInterval(renderPhase, TICK_MS);
  onRender();
  try {
    while (page.status.plant.loading) {
      await sleep(POLL_MS);
      page.status.plant = await getPlant();
      noteServerElapsed(page.status.plant);
      onRender();
    }
  } finally {
    clearInterval(ticker);
    following = false;
  }
  await onFinished();
}
