/* The ask panel: the question box, the examples grouped by topic, and one live ask from click to
   answer. Clicking an example fills the box and remembers its id; any edit forgets the id. */

import { getJob, getQuestions, startAsk } from "./api.js";
import { renderAnswer, clearAnswer } from "./answer.js";
import { $, el, sleep } from "./dom.js";
import { usd } from "./format.js";
import { describeError, label, topicOrder } from "./labels.js";
import { clearMessage, showMessage } from "./message.js";
import { canAsk, page } from "./state.js";
import { STRINGS } from "./strings.js";

const POLL_MS = 1000;
const TICK_MS = 200;

let chosenId = null; // the example the box text was filled from, if unedited
let redraw = () => {};

/** Wire the panel; `render` redraws the status parts of the page (spend, switch, button). */
export function initAsk(render) {
  redraw = render;
  $("question-label").textContent = STRINGS.questionLabel;
  $("ask-button").textContent = STRINGS.ask;
  $("ask-keys").textContent = STRINGS.askKeys;
  $("question-text").placeholder = STRINGS.questionFallback;
  $("question-text").addEventListener("input", onTextEdited);
  $("question-text").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && canAskNow()) ask();
  });
  $("ask-button").addEventListener("click", ask);
}

function canAskNow() {
  return canAsk() && $("question-text").value.trim() !== "";
}

/** Enable the button only when a question can be asked right now. */
export function updateAskEnabled() {
  $("ask-button").disabled = !canAskNow();
  $("question-text").disabled = page.corpusId === null; // nothing to ask about yet
}

function exampleOfId(id) {
  return page.questions.find((q) => q.question_id === id) ?? null;
}

function onTextEdited() {
  const example = exampleOfId(chosenId);
  if (example && example.text.trim() !== $("question-text").value.trim()) chosenId = null;
  markChosen();
  growTextarea();
  updateAskEnabled();
}

function growTextarea() {
  const box = $("question-text");
  box.style.height = "auto";
  box.style.height = `${box.scrollHeight}px`; // CSS max-height stops it at about six rows
}

function markChosen() {
  for (const button of $("examples-list").querySelectorAll("button")) {
    button.classList.toggle("chosen", button.dataset.id === chosenId);
  }
}

function chooseExample(question) {
  chosenId = question.question_id;
  $("question-text").value = question.text;
  markChosen();
  growTextarea();
  updateAskEnabled();
  $("question-text").focus();
}

function exampleButton(question) {
  const button = el("button", { type: "button", className: "example", textContent: question.text });
  button.dataset.id = question.question_id;
  button.addEventListener("click", () => chooseExample(question));
  return button;
}

function topicGroup(topic, questions) {
  return el(
    "section", { className: "topic" },
    el("h3", { className: "field-label" }, label("topics", topic)),
    ...questions.map(exampleButton),
  );
}

/** Group the loaded examples by topic, in the label table's topic order. */
export function renderExamples() {
  const list = $("examples-list");
  const groups = topicOrder()
    .map((topic) => [topic, page.questions.filter((q) => q.topic === topic)])
    .filter(([, questions]) => questions.length > 0);
  list.replaceChildren(...groups.map(([topic, questions]) => topicGroup(topic, questions)));
  $("examples-summary").textContent = STRINGS.examples(page.questions.length);
  if (page.questions.length === 0) list.append(el("p", { className: "hint" }, examplesHint()));
  $("question-text").placeholder = page.questions[0]?.text ?? STRINGS.questionFallback;
  markChosen();
}

function examplesHint() {
  return page.corpusId === null ? STRINGS.examplesNeedPlant : STRINGS.examplesLoading;
}

/** Fetch the selected plant's example questions (served once the plant is loaded) and show them. */
export async function loadQuestions() {
  page.questions = await getQuestions(page.corpusId);
  renderExamples();
}

/** Forget everything about the previous plant's question and answer. */
export function resetAsk() {
  chosenId = null;
  page.questions = [];
  $("question-text").value = "";
  growTextarea();
  clearAnswer();
  clearMessage();
  renderExamples();
  updateAskEnabled();
}

function askBody() {
  return { corpus_id: page.corpusId, text: $("question-text").value, example_id: chosenId };
}

/** Ask once; the server answers live with real model calls, within the session cap. */
async function ask() {
  clearMessage();
  clearAnswer();
  $("examples").open = false; // the list is open until the first ask
  page.asking = true;
  redraw();
  const startedAt = performance.now();
  const ticker = setInterval(() => showElapsed(startedAt), TICK_MS);
  setRunning(true);
  try {
    const { job_id } = await startAsk(askBody());
    await onJobEnded(await waitForJob(job_id));
  } catch (error) {
    const { text, technical } = describeError(error);
    showMessage(text, true, technical);
  } finally {
    clearInterval(ticker);
    page.asking = false;
    setRunning(false);
    redraw();
  }
}

function showElapsed(startedAt) {
  $("ask-status").textContent = STRINGS.asking((performance.now() - startedAt) / 1000);
}

function setRunning(running) {
  $("ask-bar").hidden = !running;
  if (!running) $("ask-status").textContent = "";
}

/** Poll the job once a second until it is no longer running. */
async function waitForJob(jobId) {
  for (;;) {
    const job = await getJob(jobId);
    if (job.state !== "running") return job;
    await sleep(POLL_MS);
  }
}

async function onJobEnded(job) {
  page.status.spend = job.spend;
  if (job.state === "done") { renderAnswer(job.result, job.clear_s); return; }
  if (job.state === "refused") {
    const cap = usd(job.spend.session_cap_usd ?? 0);
    showMessage(STRINGS.capReached(cap, usd(job.spend.session_spent_usd)), true);
    return;
  }
  showMessage(label("job_states", "error"), true, job.message); // state "error"
}
