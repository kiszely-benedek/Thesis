/* The infrastructure and end-to-end tag-identity views of the Results tab: tables and check lines.
   Every value comes from the API; this file only formats it (units come with each row). */

import { el } from "./dom.js";
import { pct, usd } from "./format.js";
import { richText } from "./glossary.js";
import { table } from "./parts.js";
import { verdictPill } from "./results_tables.js";
import { STRINGS } from "./strings.js";

const BYTE_UNITS = ["B", "kB", "MB", "GB", "TB"];
const SIGNIFICANT = 3;

/** Bytes with a decimal prefix ("1.20 GB"), the exact count in the tooltip. */
function bytesText(value) {
  let scaled = value;
  let unit = 0;
  while (scaled >= 1000 && unit < BYTE_UNITS.length - 1) { scaled /= 1000; unit += 1; }
  return unit === 0 ? `${value} B` : `${scaled.toPrecision(SIGNIFICANT)} ${BYTE_UNITS[unit]}`;
}

/** Seconds to three significant digits, so 0.045 s does not read "0.0 s". */
function secondsText(value) {
  return `${Number(value.toPrecision(SIGNIFICANT))} s`;
}

/** One measured value in its row's unit; a unit the page does not know is an error, not a guess. */
function valueCell(value, unit) {
  if (unit === "count") return value.toLocaleString("en-US");
  if (unit === "s") return secondsText(value);
  if (unit === "usd") return usd(value);
  if (unit === "bytes") return el("span", { title: `${value.toLocaleString("en-US")} B`, textContent: bytesText(value) });
  throw new Error(`expected an infrastructure unit of count, s, bytes or usd, found "${unit}"`);
}

/** A check line: its verdict and name always visible, the report's (often long) detail folded away. */
function checkNode(check) {
  const [name, ...rest] = check.text.split(": ");
  const detail = rest.join(": ");
  const summary = el("summary", {}, verdictPill(check.verdict), " ", name);
  return el("details", { className: "check" }, summary, ...(detail ? [el("p", {}, detail)] : []));
}

/** The infrastructure rows (a measure, its unit, the value at each plant) and the check lines under them. */
export function infraTable(infra) {
  const first = infra.rows[0];
  if (first === undefined) throw new Error("expected the infrastructure view to hold at least one row, found none");
  const columns = [...STRINGS.infraCols, first.from_corpus, first.to_corpus];
  const rows = infra.rows.map((r) => [STRINGS.infraMeasures[r.name] ?? r.name, STRINGS.infraUnits[r.unit] ?? r.unit,
    valueCell(r.from_value, r.unit), valueCell(r.to_value, r.unit)]);
  return table(columns, rows, [2, 3]);
}

export function infraChecks(infra) {
  if (infra.checks.length === 0) return null;
  return el("div", { className: "checks" }, el("h4", {}, STRINGS.infraChecksHeading), ...infra.checks.map(checkNode));
}

const interval = (a) => `${pct(a.ci_low)} to ${pct(a.ci_high)}`;

/** The end-to-end arms: pooled over the plants and on the configured plant. No spend column. */
export function e2eTable(e2e) {
  const rows = e2e.arms.map((arm) => [
    STRINGS.e2eArmNames[arm.label] ?? arm.label,
    el("span", {}, ...richText(STRINGS.e2eCorpus(arm.corpus))),
    `${arm.n_correct} / ${arm.n}`, pct(arm.accuracy.estimate), interval(arm.accuracy),
    STRINGS.intervalMethods[arm.interval_method] ?? arm.interval_method,
  ]);
  return table(STRINGS.e2eCols, rows, [2, 3, 4]);
}
