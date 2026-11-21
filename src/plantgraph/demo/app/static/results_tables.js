/* The Results tab's tables and provenance lines: every value of a view, so the charts hide nothing. */

import { el } from "./dom.js";
import { isoDate, pct, seconds, usd } from "./format.js";
import { table } from "./parts.js";
import { armName, armsIn, sheetSizes } from "./results_data.js";
import { STRINGS } from "./strings.js";

const SHORT_HASH = 8;
const interval = (a) => `${pct(a.ci_low)} to ${pct(a.ci_high)}`;

/** "Source: path · result row · sha256 (first 8) · modified date", set in monospace under a figure. */
export function provenance(source) {
  const hash = el("span", { title: source.sha256, textContent: source.sha256.slice(0, SHORT_HASH) });
  return el("p", { className: "provenance mono" },
    `${STRINGS.sourceLabel}: ${source.path} · ${STRINGS.resultRowLabel} ${source.result_row} · sha256 `,
    hash, ` · ${STRINGS.modifiedLabel} ${isoDate(source.modified)}`);
}

/** One table row; a cell with no run keeps the plant label and says so in the "questions" column. */
function ladderRow(arm, plant, cell) {
  if (cell === undefined) return [armName(arm), plant, STRINGS.noRun, "", "", "", ""];
  return [armName(arm), plant, String(cell.n), pct(cell.accuracy.estimate), interval(cell.accuracy),
    usd(cell.cost_mean_usd), seconds(cell.latency_median_s)];
}

function plantLabel(ladder, size) {
  const any = ladder.points.find((p) => p.n_sheets === size);
  return STRINGS.plantOption(any.corpus_id, size);
}

/** Every arm at every plant size; a cell the experiment has no run for says "no run". */
export function ladderTable(ladder) {
  const rows = sheetSizes(ladder).flatMap((size) => armsIn(ladder).map((arm) => (
    ladderRow(arm, plantLabel(ladder, size), ladder.points.find((p) => p.arm === arm && p.n_sheets === size))
  )));
  return table(STRINGS.ladderCols, rows, [2, 3, 4, 5, 6]);
}

/** The API's own list of the cells with no run, as the experiment words them. */
export function absentList(ladder) {
  if (ladder.absent.length === 0) return null;
  return el("div", {}, el("p", { className: "hint" }, STRINGS.absentHeading),
    el("ul", { className: "hint" }, ...ladder.absent.map((text) => el("li", {}, text))));
}

const PILL_OF_VERDICT = { PASS: "pill good", FAIL: "pill bad", FLAG: "pill warn" };

/** The verdict as a pill (colour repeats the word; REPORTED and NOT_RUN stay plain). */
export function verdictPill(verdict) {
  return el("span", { className: PILL_OF_VERDICT[verdict] ?? "pill", textContent: verdict });
}

/** Claim lines as a list: verdict, the claim's id when the text does not start with it, the report's words. */
export function claimList(claims) {
  if (claims.length === 0) return null;
  const items = claims.map((claim) => {
    const named = claim.text.startsWith(claim.claim_id) ? claim.text : `${claim.claim_id}: ${claim.text}`;
    return el("li", {}, verdictPill(claim.verdict), " ", named);
  });
  return el("div", { className: "claims" },
    el("h4", {}, STRINGS.claimsHeading), el("p", { className: "hint" }, STRINGS.claimsNote), el("ul", {}, ...items));
}
