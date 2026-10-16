/* Rendering of a finished ask as a result card: the answer, one facts line, the sheets it points at,
   the check against the reference (examples only), and two folded parts (details, how it works). */

import { $, el } from "./dom.js";
import { seconds, usd, valueWithClasses } from "./format.js";
import { renderDetails } from "./details.js";
import { richText, strategyTerm, term } from "./glossary.js";
import { label, labelSection } from "./labels.js";
import { cardSection, facts } from "./parts.js";
import { routeSection } from "./route.js";
import { page } from "./state.js";
import { createStepSync } from "./step_sync.js";
import { STRINGS } from "./strings.js";
import { jumpToPage } from "./viewer.js";

// emptying the model cache is normally instant; only a slower one is worth a line on the card
const SLOW_CLEAR_S = 0.5;

/** Empty the answer area. */
export function clearAnswer() {
  $("result").replaceChildren();
}

function answerText(live) {
  const final = live.final_answer;
  if (!final) return STRINGS.noAnswer;
  if (final.not_present) return STRINGS.notPresent;
  if (final.answer === true) return label("answer_values", "yes");
  if (final.answer === false) return label("answer_values", "no");
  return valueWithClasses(final.answer, labelSection("class_names")) || STRINGS.noAnswer;
}

/** One clickable chip per sheet; a click jumps the PDF to the sheet's page. */
function sheetChips(sheets) {
  const box = el("div", { className: "chips" });
  if (sheets.length === 0) box.append(el("span", { className: "hint" }, STRINGS.noSheets));
  for (const sheet of sheets) {
    const chip = el("button", { type: "button", className: "chip", textContent: `DWG ${sheet.sheet_id}` });
    chip.title = sheet.tags.join(", ");
    chip.addEventListener("click", () => jumpToPage(sheet.page));
    box.append(chip);
  }
  return box;
}

function captioned(caption, content) {
  return el("div", { className: "captioned" }, el("h3", { className: "field-label" }, caption), content);
}

/** The tier that gave the answer, as a glossary word: "Step 1: database query (Cypher)". */
function answeredByNode(live) {
  if (!live.answered_by) return STRINGS.nobody;
  const tier = live.tiers.find((t) => t.tier === live.answered_by);
  const text = label("tiers", live.answered_by);
  return tier ? strategyTerm(tier.strategy, text) : text;
}

/** "Answered in 4.2 s · model time 3.9 s · cost $0.0021 · by Step 1: ...". The answer time leaves out
    the seconds spent emptying the model cache first (`clearS`), which the job's clock includes. */
function factsLine(job) {
  const live = job.result.live;
  const answerS = Math.max(0, job.elapsed_s - (job.clear_s ?? 0));
  const text = STRINGS.factsLine(seconds(answerS), seconds(live.latency_s), usd(live.spent_usd));
  return el("p", { className: "facts-line" }, ...richText(text), answeredByNode(live));
}

function verdictNode(correct) {
  if (correct === null) return STRINGS.none;
  const className = correct ? "pill good" : "pill bad";
  return el("span", { className }, correct ? STRINGS.correct : STRINGS.incorrect);
}

function benchmarkBlock(benchmark) {
  const names = labelSection("class_names");
  return cardSection(
    STRINGS.checkHeading,
    facts([
      [STRINGS.reference, valueWithClasses(benchmark.reference, names) || STRINGS.none],
      [STRINGS.verdict, verdictNode(benchmark.correct)],
      [term("k", "k"), richText(STRINGS.kValue(benchmark))],
      [term("u", "u"), richText(STRINGS.uValue(benchmark))],
    ]),
    captioned(STRINGS.goldSheets, sheetChips(benchmark.gold_sheets)),
  );
}

function statusLines(result, live) {
  const lines = [];
  if (result.cache_hit_detected) lines.push(el("div", { className: "message error" }, STRINGS.cacheHit));
  if (!live.evaluated_policy) lines.push(el("div", { className: "notice" }, STRINGS.notice(live.policy, live.notice)));
  return lines;
}

function answerBlock(job) {
  const live = job.result.live;
  const block = el(
    "section", { className: "card-section" },
    el("h2", { className: "field-label" }, STRINGS.answer),
    el("div", { className: "answer-text" }, answerText(live)),
  );
  if (live.fell_back) block.append(el("p", { className: "notice" }, STRINGS.fallbackLine));
  block.append(factsLine(job));
  if ((job.clear_s ?? 0) >= SLOW_CLEAR_S) block.append(el("p", { className: "hint" }, STRINGS.preparing(job.clear_s)));
  return block;
}

function sourcesBlock(result) {
  const parts = [captioned(STRINGS.answerSheets, sheetChips(result.answer_sheets))];
  // sheets the agent read exist only when the graph agent ran
  if (result.read_sheets.length > 0) parts.push(captioned(STRINGS.readSheets, sheetChips(result.read_sheets)));
  return cardSection(STRINGS.knowHeading, ...parts);
}

function howItWorks() {
  const summary = el("summary", {}, STRINGS.howHeading);
  const text = el("p", {}, ...richText(STRINGS.howText(page.status.cutoff_s)));
  return el("details", { className: "details" }, summary, el("div", { className: "details-body" }, text));
}

const TAG_ANSWERS = ["TAG", "TAG_SET", "TAG_PATH"];

/** The tags of the reference answer when a tag answer was judged wrong, else null (no cross is drawn). */
function wrongReference(benchmark) {
  if (!benchmark || benchmark.correct !== false || !TAG_ANSWERS.includes(benchmark.answer_type)) return null;
  return new Set([benchmark.reference].flat().map(String));
}

/** Show the answer of a finished ask (`job`: the server's JobStatus with a result). */
export function renderAnswer(job) {
  const result = job.result;
  // the route view and the step list in Details share one "current step"
  const route = result.route;
  const sync = createStepSync(route ? Math.max(0, route.steps.length - 1) : 0);
  const card = el(
    "article", { className: "card" },
    ...statusLines(result, result.live),
    answerBlock(job),
    sourcesBlock(result),
  );
  if (route) card.append(routeSection(route, sync, wrongReference(result.benchmark)));
  if (result.benchmark) card.append(benchmarkBlock(result.benchmark));
  card.append(renderDetails(result, route ? sync : null), howItWorks());
  $("result").replaceChildren(card);
}
