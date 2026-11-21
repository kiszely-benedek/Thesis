/* From the /api/results views to chart specifications (charts.js). Every number comes from the API
   reply; this file only picks, orders, names and formats them. No DOM code. */

import { decadeDomain, decadeTicks, niceTicks } from "./chart_scale.js";
import { pct, seconds, usd } from "./format.js";
import { STRINGS } from "./strings.js";

// The report's own arm names, in drawing order (the demo's method last, so it lies on top).
const ARM_ORDER = ["ctx-high", "ctx-low", "cyp", "ag", "cascade_v3", "cascade_v4_iso"];
const ARM_STYLE = {
  "ctx-high": { color: "var(--series-2)", marker: "square" },
  "ctx-low": { color: "var(--series-4)", marker: "diamond", dash: "3 3" },
  cyp: { color: "var(--series-3)", marker: "triangle" },
  ag: { color: "var(--series-5)", marker: "triangle-down" },
  cascade_v4_iso: { color: "var(--series-1)", marker: "circle" },
  // F1, the previous system: its own dashed series, never styled like the current cascade
  cascade_v3: { color: "var(--series-4)", marker: "circle", dash: "3 3" },
};
const UNKNOWN_STYLE = { color: "var(--ink-muted)", marker: "circle" };
const X_MARGIN_LEFT = 1.5;  // room left of the first point, as a factor on the log axis
const X_MARGIN_RIGHT = 1.12; // and right of the last point or the context wall

export function armName(arm) {
  return STRINGS.armNames[arm] ?? arm;
}

export function armStyle(arm) {
  if (!(arm in ARM_STYLE)) console.warn(`expected a known arm in the ladder, found "${arm}"; drawn in a neutral style`);
  return ARM_STYLE[arm] ?? UNKNOWN_STYLE;
}

/** The arms present in the ladder, known ones in drawing order, unknown ones after them. */
export function armsIn(ladder) {
  const present = [...new Set(ladder.points.map((p) => p.arm))];
  const known = ARM_ORDER.filter((arm) => present.includes(arm));
  return [...known, ...present.filter((arm) => !ARM_ORDER.includes(arm))];
}

/** The plant sizes (sheet counts) of the ladder, ascending. */
export function sheetSizes(ladder) {
  return [...new Set(ladder.points.map((p) => p.n_sheets))].sort((a, b) => a - b);
}

function xAxis(ladder) {
  const sizes = sheetSizes(ladder);
  const last = Math.max(sizes[sizes.length - 1], ladder.wall_sheets);
  return { domain: [sizes[0] / X_MARGIN_LEFT, last * X_MARGIN_RIGHT], ticks: sizes, format: String, label: STRINGS.axisSheets };
}

function wallMark(ladder, withLabel) {
  const label = withLabel ? STRINGS.wallLabel(Math.round(ladder.wall_sheets)) : undefined;
  return { x: ladder.wall_sheets, label };
}

// What each ladder chart plots: the value, the line of the tooltip that states it, and the interval if any.
const METRICS = {
  accuracy: {
    value: (p) => p.accuracy.estimate,
    interval: (p) => p.accuracy,
    tipLine: (p) => STRINGS.tipAccuracy(pct(p.accuracy.estimate), pct(p.accuracy.ci_low), pct(p.accuracy.ci_high)),
  },
  cost: { value: (p) => p.cost_mean_usd, tipLine: (p) => STRINGS.tipCost(usd(p.cost_mean_usd)) },
  latency: { value: (p) => p.latency_median_s, tipLine: (p) => STRINGS.tipLatency(seconds(p.latency_median_s)) },
};

function pointOf(metric, arm, cell, size) {
  if (cell === undefined) return { x: size, y: null }; // no run: a gap in the line
  const interval = metric.interval?.(cell);
  const tip = [armName(arm), STRINGS.plantOption(cell.corpus_id, cell.n_sheets), metric.tipLine(cell), STRINGS.tipQuestions(cell.n)];
  const band = interval ? { low: interval.ci_low, high: interval.ci_high } : {};
  return { x: size, y: metric.value(cell), tip: tip.join("\n"), ...band };
}

function seriesOf(ladder, metric, arm) {
  const points = sheetSizes(ladder).map((size) => {
    const cell = ladder.points.find((p) => p.arm === arm && p.n_sheets === size);
    return pointOf(metric, arm, cell, size);
  });
  return { name: armName(arm), ...armStyle(arm), points };
}

function ladderSeries(ladder, metric) {
  return armsIn(ladder).map((arm) => seriesOf(ladder, METRICS[metric], arm));
}

/** The spec of the accuracy chart: y from 0 to 100 %, Wilson whiskers, the context wall labelled. */
export function accuracySpec(ladder) {
  return {
    height: 320,
    label: STRINGS.accuracyChartLabel,
    x: xAxis(ladder),
    y: { domain: [0, 1], ticks: [0, 0.25, 0.5, 0.75, 1], format: (v) => pct(v, 0), label: STRINGS.axisAccuracy },
    series: ladderSeries(ladder, "accuracy"),
    wall: wallMark(ladder, true),
  };
}

/** Mean cost per question: a log y axis, since the arms differ by more than a factor of ten. */
export function costSpec(ladder) {
  const series = ladderSeries(ladder, "cost");
  const values = series.flatMap((s) => s.points.filter((p) => p.y !== null).map((p) => p.y));
  const domain = decadeDomain(values);
  return {
    height: 250,
    label: STRINGS.costChartLabel,
    x: xAxis(ladder),
    y: { domain, log: true, ticks: decadeTicks(domain), format: usd, label: STRINGS.axisCost },
    series,
    wall: wallMark(ladder, false),
  };
}

/** Median answer time: linear seconds from zero. */
export function latencySpec(ladder) {
  const series = ladderSeries(ladder, "latency");
  const values = series.flatMap((s) => s.points.filter((p) => p.y !== null).map((p) => p.y));
  const ticks = niceTicks(Math.max(...values));
  return {
    height: 250,
    label: STRINGS.latencyChartLabel,
    x: xAxis(ladder),
    y: { domain: [0, ticks[ticks.length - 1]], ticks, format: (v) => `${v} s`, label: STRINGS.axisLatency },
    series,
    wall: wallMark(ladder, false),
  };
}
