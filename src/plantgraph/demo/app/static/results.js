/* The Results tab: the recorded experiments drawn as figures. All numbers come from /api/results;
   the page text only describes what a figure shows. */

import { getResults } from "./api.js";
import { barChart, legend, lineChart } from "./charts.js";
import { $, el } from "./dom.js";
import { richText } from "./glossary.js";
import { describeError } from "./labels.js";
import {
  accuracySpec, armName, armStyle, armsIn, costSpec, latencySpec, policiesIn, policyName, policyStyle, sealedSpec,
} from "./results_data.js";
import { absentList, ladderTable, provenance, sealedTable } from "./results_tables.js";
import { STRINGS } from "./strings.js";

let loading = null; // the one request for the views; cleared on failure so the next visit retries

/** A chart's host element, drawn now and again whenever its width changes (window resize, tab shown). */
function chartHost(draw) {
  const host = el("div", { className: "chart" });
  let width = 0;
  new ResizeObserver(() => {
    if (host.clientWidth === width) return;
    width = host.clientWidth;
    draw(host);
  }).observe(host);
  return host;
}

function caption(text) {
  return el("p", { className: "caption" }, ...richText(text));
}

/** A figure: title, caption, legend, chart, any notes, and the provenance line. */
function figure(title, captionText, legendItems, host, ...notes) {
  return el("figure", { className: "figure" },
    el("h3", {}, title), caption(captionText), legend(legendItems), host, ...notes.filter(Boolean));
}

function armLegend(ladder) {
  return armsIn(ladder).map((arm) => ({ name: armName(arm), ...armStyle(arm) }));
}

/** What each line is, in plain words, for the arms the ladder has. */
function armNotes(ladder) {
  const rows = armsIn(ladder).flatMap((arm) => [
    el("dt", {}, armName(arm)),
    el("dd", {}, ...richText(STRINGS.armNotes[arm] ?? "")),
  ]);
  return el("dl", { className: "arm-notes" }, ...rows);
}

function ladderFigures(ladder) {
  const items = armLegend(ladder);
  const source = provenance(ladder.source);
  const accuracy = figure(STRINGS.accuracyTitle, STRINGS.accuracyCaption(ladder.absent.length > 0), items,
    chartHost((host) => lineChart(host, accuracySpec(ladder))), armNotes(ladder), source.cloneNode(true));
  const cost = figure(STRINGS.costTitle, STRINGS.costCaption, items,
    chartHost((host) => lineChart(host, costSpec(ladder))), source.cloneNode(true));
  const latency = figure(STRINGS.latencyTitle, STRINGS.latencyCaption, items,
    chartHost((host) => lineChart(host, latencySpec(ladder))), source);
  return [accuracy, el("div", { className: "figure-pair" }, cost, latency)];
}

function fullTable(summary, ...content) {
  return el("details", { className: "full-table" }, el("summary", {}, summary), ...content.filter(Boolean));
}

function ladderSection(ladder) {
  return el("section", { className: "results-section", "aria-labelledby": "ladder-heading" },
    el("h2", { id: "ladder-heading" }, STRINGS.ladderHeading),
    el("p", { className: "hint" }, STRINGS.ladderMeta(ladder.n_families, ladder.cutoff_s)),
    ...ladderFigures(ladder),
    fullTable(STRINGS.allValues, ladderTable(ladder), absentList(ladder)));
}

function sealedSection(sealed) {
  const items = policiesIn(sealed).map((policy) => ({ name: policyName(policy), ...policyStyle(policy) }));
  const chart = figure(STRINGS.sealedTitle, STRINGS.sealedCaption, items,
    chartHost((host) => barChart(host, sealedSpec(sealed))), provenance(sealed.source));
  return el("section", { className: "results-section", "aria-labelledby": "sealed-heading" },
    el("h2", { id: "sealed-heading" }, STRINGS.sealedHeading),
    chart, fullTable(STRINGS.allValues, sealedTable(sealed)));
}

function render(view) {
  const sections = [];
  if (view.ladder) sections.push(ladderSection(view.ladder));
  if (view.sealed) sections.push(sealedSection(view.sealed));
  $("results-body").replaceChildren(...sections);
  $("results-status").textContent = sections.length ? "" : STRINGS.resultsEmpty;
}

async function load() {
  $("results-status").textContent = STRINGS.resultsLoading;
  try {
    render(await getResults());
  } catch (error) {
    loading = null;
    const { text, technical } = describeError(error);
    $("results-status").replaceChildren(el("span", { className: "results-error" }, text),
      el("details", {}, el("summary", {}, STRINGS.technicalDetails), el("pre", {}, technical)));
  }
}

/** Fetch and draw the views the first time the tab is opened (and again after a failed try). */
export function showResults() {
  loading ??= load();
  return loading;
}

/** Fill the tab's static text (call once at start-up). */
export function initResults() {
  $("results-heading").textContent = STRINGS.resultsHeading;
  $("results-intro").replaceChildren(...richText(STRINGS.resultsIntro));
}
