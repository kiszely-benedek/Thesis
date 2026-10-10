"use strict";
/* The demo page. Plain JS, no build step. It talks to the FastAPI server in server.py:
   status -> corpus -> questions -> ask -> poll the job -> render the answer. */

const POLL_MS = 1000;
const STATUS_MS = 3000;

// The page's whole mutable state: what the server last said and what the user is doing.
const page = { status: null, corpusId: null, index: null, questions: [], asking: false, startedAt: 0 };

function $(id) { return document.getElementById(id); }

/** Build a DOM element; children are strings (shown as text, never as HTML) or nodes. */
function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ? JSON.stringify(body.detail) : `${path}: HTTP ${response.status}`);
  }
  return response.json();
}

/* ---------- PDF: jump to a page ---------- */

/** Show page `pageNumber` of the corpus's PDF. A fresh iframe each time: a hash-only change on an
    open PDF viewer does not reliably move the page in every browser. */
function showPdf(corpusId, pageNumber) {
  const frame = el("iframe", { title: "Rajzok" });
  frame.src = `/corpora/${encodeURIComponent(corpusId)}/drawings.pdf#page=${pageNumber}`;
  $("pdf-host").replaceChildren(frame);
}

function jumpToPage(pageNumber) { showPdf(page.corpusId, pageNumber); }

function goToDrawing() {
  const id = $("dwg-input").value.trim().replace(/^DWG\s*/i, "");
  const message = $("dwg-message");
  message.textContent = "";
  if (!page.index) { message.textContent = STRINGS.dwgNoIndex; return; }
  const target = page.index.pages[id];
  if (target === undefined) { message.textContent = STRINGS.dwgUnknown(id); return; }
  jumpToPage(target);
}

/* ---------- status, corpus, questions ---------- */

function spendText(status) {
  if (!status.paid_allowed) return STRINGS.paidOff;
  const spend = status.spend;
  return STRINGS.spend(usd(spend.session_spent_usd), usd(spend.session_cap_usd ?? 0));
}

function corpusStateText(corpus) {
  const parts = [STRINGS.stateLabels[corpus.state] ?? corpus.state];
  if (!corpus.pdf_present) parts.push(STRINGS.noPdf);
  if (corpus.state === "ready" && !corpus.tier1_store) parts.push(STRINGS.noTier1);
  if (corpus.message) parts.push(corpus.message);
  return parts.join("; ");
}

function currentCorpus() {
  return page.status?.corpora.find((c) => c.corpus_id === page.corpusId) ?? null;
}

function renderStatus() {
  const select = $("corpus-select");
  if (select.options.length === 0) {
    for (const c of page.status.corpora) select.append(el("option", { value: c.corpus_id, textContent: c.corpus_id }));
  }
  $("status-line").textContent = spendText(page.status);
  const corpus = currentCorpus();
  if (corpus) $("corpus-state").textContent = corpusStateText(corpus);
  updateAskEnabled();
}

function updateAskEnabled() {
  const corpus = currentCorpus();
  $("ask-button").disabled = page.asking || !corpus || corpus.state !== "ready";
}

async function refreshStatus() {
  const wasReady = currentCorpus()?.state === "ready";
  page.status = await api("/api/status");
  renderStatus();
  // questions are only served once the corpus has loaded
  if (!wasReady && currentCorpus()?.state === "ready") await loadQuestions();
}

async function selectCorpus(corpusId) {
  page.corpusId = corpusId;
  page.index = null;
  page.questions = [];
  fillBenchmarkSelect();
  $("result").replaceChildren();
  showPdf(corpusId, 1);
  renderStatus();
  api(`/api/corpora/${encodeURIComponent(corpusId)}/index`).then((index) => { page.index = index; }).catch(() => {});
  if (currentCorpus()?.state === "ready") await loadQuestions();
}

async function loadQuestions() {
  page.questions = await api(`/api/corpora/${encodeURIComponent(page.corpusId)}/questions`);
  fillBenchmarkSelect();
}

function fillBenchmarkSelect() {
  const select = $("benchmark-select");
  select.replaceChildren(el("option", { value: "", textContent: STRINGS.ownQuestion }));
  for (const q of page.questions) {
    const label = `${q.question_id} [${q.family}] ${q.text}`;
    select.append(el("option", { value: q.question_id, textContent: label.slice(0, 160) }));
  }
  onBenchmarkChosen();
}

/** A benchmark question fixes the text and the answer form; a typed question frees them. */
function onBenchmarkChosen() {
  const chosen = page.questions.find((q) => q.question_id === $("benchmark-select").value);
  $("question-text").readOnly = Boolean(chosen);
  $("answer-type").disabled = Boolean(chosen);
  if (!chosen) return;
  $("question-text").value = chosen.text;
  $("answer-type").value = chosen.answer_type;
}

/* ---------- asking ---------- */

function askBody(allowPaid) {
  const benchmarkId = $("benchmark-select").value;
  if (benchmarkId) return { corpus_id: page.corpusId, benchmark_question_id: benchmarkId, allow_paid: allowPaid };
  return {
    corpus_id: page.corpusId,
    text: $("question-text").value,
    answer_type: $("answer-type").value,
    allow_paid: allowPaid,
  };
}

function showMessage(text, isError) {
  const box = $("message");
  box.hidden = !text;
  box.textContent = text ?? "";
  box.className = isError ? "message error" : "message";
}

/** Ask once; a cache miss that the user confirms asks again with `allowPaid` set. */
async function ask(allowPaid) {
  showMessage(null);
  $("result").replaceChildren();
  page.asking = true;
  page.startedAt = performance.now();
  updateAskEnabled();
  try {
    const { job_id } = await api("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(askBody(allowPaid)),
    });
    const job = await waitForJob(job_id);
    await onJobEnded(job);
  } catch (error) {
    showMessage(error.message, true);
  } finally {
    page.asking = false;
    $("timer").textContent = "";
    updateAskEnabled();
  }
}

/** Poll the job once a second, with a ticking timer, until it is no longer running. */
async function waitForJob(jobId) {
  const ticker = setInterval(() => {
    const seconds = (performance.now() - page.startedAt) / 1000;
    $("timer").textContent = `${STRINGS.running} ${STRINGS.elapsed(seconds)}`;
  }, 200);
  try {
    for (;;) {
      const job = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
      if (job.state !== "running") return job;
      await new Promise((resolve) => setTimeout(resolve, POLL_MS));
    }
  } finally {
    clearInterval(ticker);
  }
}

async function onJobEnded(job) {
  page.status.spend = job.spend;
  renderStatus();
  if (job.state === "done") { renderResult(job.result); return; }
  if (job.state === "needs_paid") { await onNeedsPaid(job); return; }
  showMessage(job.message ?? job.state, true); // refused or error
}

async function onNeedsPaid(job) {
  if (!page.status.paid_allowed) { showMessage(STRINGS.needsPaidOff, true); return; }
  if (await confirmPaid(job)) {
    page.asking = false; // the nested ask() takes over the button and the timer
    await ask(true);
  }
}

/** Show the estimate and spend in the dialog; resolves to true when the user confirms. */
function confirmPaid(job) {
  const body = $("paid-body");
  body.replaceChildren(
    el("p", {}, STRINGS.paidIntro(job.needs_paid.missing_tier)),
    el("p", { className: "hint" }, job.needs_paid.reason),
    el("h2", {}, STRINGS.paidEstimateHead),
  );
  for (const [tier, stats] of Object.entries(job.estimate.per_tier)) {
    body.append(el("div", {}, STRINGS.paidTierRow(tier, stats)));
  }
  body.append(el("p", {}, el("strong", {}, STRINGS.paidReservation(job.estimate.reservation_usd))));
  body.append(el("p", {}, spendText(page.status)));
  const dialog = $("paid-dialog");
  return new Promise((resolve) => {
    dialog.onclose = () => resolve(dialog.returnValue === "confirm");
    dialog.returnValue = "cancel"; // Esc closes without setting it
    dialog.showModal();
  });
}

/* ---------- the answer ---------- */

function valueText(value) {
  if (value === null || value === undefined) return "";
  return Array.isArray(value) ? value.join(", ") : String(value);
}

function answerText(live) {
  const final = live.final_answer;
  if (!final) return STRINGS.noAnswer;
  if (final.not_present) return STRINGS.notPresent;
  return valueText(final.answer) || STRINGS.noAnswer;
}

/** One clickable chip per sheet; a click jumps the PDF to the sheet's page. */
function chips(sheets) {
  const box = el("div", { className: "chips" });
  if (sheets.length === 0) box.append(el("span", { className: "hint" }, STRINGS.none));
  for (const sheet of sheets) {
    const chip = el("button", { type: "button", className: "chip", textContent: `DWG ${sheet.sheet_id}` });
    chip.title = sheet.tags.join(", ");
    chip.addEventListener("click", () => jumpToPage(sheet.page));
    box.append(chip);
  }
  return box;
}

function facts(rows) {
  const list = el("dl", { className: "facts" });
  for (const [label, value] of rows) list.append(el("dt", {}, label), el("dd", {}, value));
  return list;
}

function costText(live) {
  return live.from_cache ? STRINGS.fromCache(live.cost_usd) : STRINGS.paid(live.cost_usd, live.spent_usd);
}

function answeredByText(live) {
  if (!live.answered_by) return STRINGS.nobody;
  const tier = live.tiers.find((t) => t.tier === live.answered_by);
  const detail = tier ? ` (${tier.strategy}, ${tier.model_id})` : "";
  return live.answered_by + detail + (live.fell_back ? ` — ${STRINGS.fellBack}` : "");
}

function tierTable(tiers) {
  const head = el("tr", {}, ...STRINGS.tierCols.map((name) => el("th", {}, name)));
  const rows = tiers.map((t) => {
    const cells = [
      t.tier, t.outcome, t.accepted ? STRINGS.yes : STRINGS.no, `${t.latency_s.toFixed(1)} s`,
      usd(t.cost_usd), t.n_calls, t.n_cached, t.n_steps ?? "–", t.stop_reason ?? "–", t.n_rows ?? "–",
    ];
    return el("tr", {}, ...cells.map((c) => el("td", {}, String(c))));
  });
  return el("table", {}, el("thead", {}, head), el("tbody", {}, ...rows));
}

function verdictNode(correct) {
  if (correct === null) return STRINGS.none;
  const className = correct ? "verdict-correct" : "verdict-wrong";
  return el("span", { className }, correct ? STRINGS.correct : STRINGS.incorrect);
}

function benchmarkBlock(benchmark) {
  return el(
    "div", {},
    facts([
      [STRINGS.reference, valueText(benchmark.reference)],
      [STRINGS.verdict, verdictNode(benchmark.correct)],
      ["k / u", STRINGS.crossSheet(benchmark)],
    ]),
    el("h2", {}, STRINGS.goldSheets),
    chips(benchmark.gold_sheets),
  );
}

function renderResult(result) {
  const live = result.live;
  const box = el("div", {});
  if (!live.evaluated_policy) {
    box.append(el("div", { className: "notice" }, STRINGS.notice(live.policy, live.notice)));
  }
  box.append(
    el("h2", {}, STRINGS.answer),
    el("div", { className: "answer-box" }, el("div", { className: "answer-text" }, answerText(live))),
    facts([
      [STRINGS.outcome, live.outcome],
      [STRINGS.answeredBy, answeredByText(live)],
      [STRINGS.latency, `${live.latency_s.toFixed(1)} s`],
      [STRINGS.wall, `${live.wall_s.toFixed(1)} s`],
      [STRINGS.cost, costText(live)],
    ]),
    el("h2", {}, STRINGS.tierTable),
    tierTable(live.tiers),
    el("h2", {}, STRINGS.answerSheets),
    chips(result.answer_sheets),
    el("h2", {}, STRINGS.readSheets),
    chips(result.read_sheets),
  );
  if (result.benchmark) box.append(benchmarkBlock(result.benchmark));
  $("result").replaceChildren(box);
}

/* ---------- start-up ---------- */

function setLabels() {
  document.title = STRINGS.title;
  $("title").textContent = STRINGS.title;
  $("dwg-label").textContent = STRINGS.dwgLabel;
  $("dwg-go").textContent = STRINGS.dwgGo;
  $("corpus-label").textContent = STRINGS.corpus;
  $("benchmark-label").textContent = STRINGS.benchmark;
  $("question-label").textContent = STRINGS.question;
  $("answer-type-label").textContent = STRINGS.answerType;
  $("ask-button").textContent = STRINGS.ask;
  $("paid-title").textContent = STRINGS.paidTitle;
  $("paid-cancel").textContent = STRINGS.paidCancel;
  $("paid-confirm").textContent = STRINGS.paidConfirm;
  for (const [value, label] of Object.entries(STRINGS.answerTypes)) {
    $("answer-type").append(el("option", { value, textContent: label }));
  }
}

function wireEvents() {
  $("dwg-go").addEventListener("click", goToDrawing);
  $("dwg-input").addEventListener("keydown", (e) => { if (e.key === "Enter") goToDrawing(); });
  $("corpus-select").addEventListener("change", (e) => selectCorpus(e.target.value));
  $("benchmark-select").addEventListener("change", onBenchmarkChosen);
  $("ask-button").addEventListener("click", () => ask(false));
  $("paid-cancel").addEventListener("click", () => $("paid-dialog").close("cancel"));
  $("paid-confirm").addEventListener("click", () => $("paid-dialog").close("confirm"));
}

async function start() {
  setLabels();
  wireEvents();
  try {
    page.status = await api("/api/status");
    renderStatus();
    await selectCorpus(page.status.corpora[0].corpus_id);
    setInterval(() => refreshStatus().catch(() => {}), STATUS_MS);
  } catch (error) {
    showMessage(error.message, true);
  }
}

start();
