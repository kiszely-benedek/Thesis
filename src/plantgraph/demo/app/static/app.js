/* Entry module of the demo page. Plain ES modules, no build step.
   It wires the parts together and keeps them in step with the server's /api/status. */

import { getIndex, getStatus } from "./api.js";
import { $ } from "./dom.js";
import { initHeader, renderHeld, renderSpend } from "./header.js";
import { initIntro, renderIntro } from "./intro.js";
import { describeError, loadLabels } from "./labels.js";
import { showMessage } from "./message.js";
import { initAsk, loadQuestions, resetAsk, updateAskEnabled } from "./ask.js";
import {
  corpusStateText, followLoad, initPlantSwitch, loadPlant, renderPhase, renderPlantSwitch,
  renderStoreNotice,
} from "./plant.js";
import { currentCorpus, page } from "./state.js";
import { initTheme } from "./theme.js";
import { clearPdf, initViewer, showPdf } from "./viewer.js";

const STATUS_MS = 3000;

let loadingQuestions = false;

/** Redraw every part of the page that depends on the server's status. */
function render() {
  renderSpend();
  renderHeld();
  renderPlantSwitch();
  renderPhase();
  renderStoreNotice();
  const corpus = currentCorpus();
  const text = corpus ? corpusStateText(corpus) : "";
  $("corpus-state").textContent = text;
  $("corpus-state").hidden = text === "";
  updateAskEnabled();
}

function sheetCounts() {
  return page.status.corpora.map((c) => c.n_sheets);
}

/** Fetch the examples once the selected plant is loaded (the server serves them only then). */
async function ensureQuestions() {
  const corpus = currentCorpus();
  if (!corpus || corpus.state !== "ready" || page.questions.length > 0 || loadingQuestions) return;
  loadingQuestions = true;
  try {
    await loadQuestions();
  } finally {
    loadingQuestions = false;
  }
  updateAskEnabled();
}

async function refreshStatus() {
  page.status = await getStatus();
  renderIntro(sheetCounts());
  render();
  await ensureQuestions();
}

async function selectCorpus(corpusId) {
  page.corpusId = corpusId;
  page.index = null;
  resetAsk();
  showPdf(corpusId, 1);
  render();
  getIndex(corpusId).then((index) => { page.index = index; }).catch(() => {});
  await ensureQuestions();
}

/** The visitor chose a plant: show it, and load it into the database if the database holds another. */
async function onPlantChosen(corpusId) {
  await selectCorpus(corpusId);
  const plant = page.status.plant;
  if (plant.loading || plant.held.includes(corpusId)) return;
  await loadPlant(corpusId, render, refreshStatus);
}

/** The plant to start on: whichever one the database holds, or none. */
function heldCorpusId() {
  const known = page.status.corpora.map((c) => c.corpus_id);
  return page.status.plant.held.find((id) => known.includes(id)) ?? null;
}

async function start() {
  initTheme($("theme-toggle"));
  initHeader();
  initIntro();
  initViewer();
  initAsk(render);
  try {
    await loadLabels();
    page.status = await getStatus();
    renderIntro(sheetCounts());
    initPlantSwitch(onPlantChosen);
    const held = heldCorpusId();
    if (held === null) clearPdf();
    if (held !== null) await selectCorpus(held);
    render();
    if (page.status.plant.loading) followLoad(render, refreshStatus); // a load was already running
    setInterval(() => refreshStatus().catch(() => {}), STATUS_MS);
  } catch (error) {
    const { text, technical } = describeError(error);
    showMessage(text, true, technical);
  }
}

start();
