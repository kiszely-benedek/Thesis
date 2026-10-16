/* Rendering of a finished ask: the answer, how it was reached, and the sheets it points at.
   (DP-T7 reshapes the card; the trace of the ask is rendered there too.) */

import { $, el } from "./dom.js";
import { seconds, usd, valueText } from "./format.js";
import { label } from "./labels.js";
import { STRINGS } from "./strings.js";
import { jumpToPage } from "./viewer.js";

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
  return valueText(final.answer) || STRINGS.noAnswer;
}

/** One clickable chip per sheet; a click jumps the PDF to the sheet's page. */
function sheetChips(sheets) {
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
  for (const [caption, value] of rows) list.append(el("dt", {}, caption), el("dd", {}, value));
  return list;
}

function section(heading, ...content) {
  return el("section", { className: "card-section" }, el("h2", { className: "field-label" }, heading), ...content);
}

function answeredByText(live) {
  if (!live.answered_by) return STRINGS.nobody;
  const tier = live.tiers.find((t) => t.tier === live.answered_by);
  const detail = tier ? ` (${tier.model_id})` : "";
  return label("tiers", live.answered_by) + detail + (live.fell_back ? ` — ${STRINGS.fellBack}` : "");
}

function tierRow(t) {
  const cells = [
    label("tiers", t.tier), label("outcomes", t.outcome), t.accepted ? STRINGS.yes : STRINGS.no,
    seconds(t.latency_s), usd(t.cost_usd), t.n_calls, t.n_steps ?? "–",
    t.stop_reason ? label("stop_reasons", t.stop_reason) : "–", t.n_rows ?? "–",
  ];
  return el("tr", {}, ...cells.map((c) => el("td", {}, String(c))));
}

function tierTable(tiers) {
  const head = el("tr", {}, ...STRINGS.tierCols.map((name) => el("th", {}, name)));
  const table = el("table", {}, el("thead", {}, head), el("tbody", {}, ...tiers.map(tierRow)));
  return el("div", { className: "table-wrap" }, table);
}

function verdictNode(correct) {
  if (correct === null) return STRINGS.none;
  const className = correct ? "pill good" : "pill bad";
  return el("span", { className }, correct ? STRINGS.correct : STRINGS.incorrect);
}

function benchmarkBlock(benchmark) {
  return section(
    STRINGS.reference,
    facts([
      [STRINGS.reference, valueText(benchmark.reference)],
      [STRINGS.verdict, verdictNode(benchmark.correct)],
      ["k / u", STRINGS.crossSheet(benchmark)],
    ]),
    el("h3", { className: "field-label" }, STRINGS.goldSheets),
    sheetChips(benchmark.gold_sheets),
  );
}

function statusLines(result, live) {
  const lines = [];
  if (result.cache_hit_detected) lines.push(el("div", { className: "message error" }, STRINGS.cacheHit));
  if (!live.evaluated_policy) lines.push(el("div", { className: "notice" }, STRINGS.notice(live.policy, live.notice)));
  return lines;
}

/** Show the answer of a finished ask; `clearS` is the seconds spent emptying the model cache first. */
export function renderAnswer(result, clearS) {
  const live = result.live;
  const card = el(
    "article", { className: "card" },
    ...statusLines(result, live),
    section(STRINGS.answer, el("div", { className: "answer-text" }, answerText(live))),
    facts([
      [STRINGS.outcome, label("outcomes", live.outcome)],
      [STRINGS.answeredBy, answeredByText(live)],
      [STRINGS.latency, seconds(live.latency_s)],
      [STRINGS.wall, seconds(live.wall_s)],
      [STRINGS.cost, STRINGS.paid(live.cost_usd, live.spent_usd)],
    ]),
    section(STRINGS.tierTable, tierTable(live.tiers)),
    section(STRINGS.answerSheets, sheetChips(result.answer_sheets)),
    section(STRINGS.readSheets, sheetChips(result.read_sheets)),
  );
  if (result.benchmark) card.append(benchmarkBlock(result.benchmark));
  if (clearS !== null && clearS !== undefined) card.append(el("p", { className: "hint" }, STRINGS.prepared(clearS)));
  $("result").replaceChildren(card);
}
