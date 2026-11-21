/* The Results tab: the recorded experiments drawn as figures. All numbers come from /api/results;
   the page text only describes what a figure shows. */

import { getResults } from "./api.js";
import { barChart, legend, lineChart } from "./charts.js";
import { $, el } from "./dom.js";
import { richText } from "./glossary.js";
import { describeError } from "./labels.js";
import { accuracySpec, armName, armStyle, armsIn, costSpec, latencySpec } from "./results_data.js";
import { e2eTable, infraChecks, infraTable } from "./results_infra.js";
import { ARM_OF_POLICY, policiesIn, policyName, policyStyle, rowsOfScope, sealedSpec, sealedTable } from "./results_sealed.js";
import { absentList, claimList, ladderTable, provenance } from "./results_tables.js";
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

/** A figure: title, caption, legend (none when `legendItems` is empty), chart, any notes, and the provenance line. */
function figure(title, captionText, legendItems, host, ...notes) {
  const key = legendItems.length > 0 ? legend(legendItems) : null;
  return el("figure", { className: "figure" },
    ...[el("h3", {}, title), caption(captionText), key, host, ...notes].filter(Boolean));
}

function armLegend(ladder) {
  return armsIn(ladder).map((arm) => ({ name: armName(arm), ...armStyle(arm) }));
}

/** What each line is, in plain words: a definition list over the given arms. */
function armNotes(arms) {
  const rows = arms.flatMap((arm) => [
    el("dt", {}, armName(arm)),
    el("dd", {}, ...richText(STRINGS.armNotes[arm] ?? "")),
  ]);
  return el("dl", { className: "arm-notes" }, ...rows);
}

function ladderFigures(ladder) {
  const items = armLegend(ladder);
  const source = provenance(ladder.source);
  const accuracy = figure(STRINGS.accuracyTitle, STRINGS.accuracyCaption(ladder.absent.length > 0), items,
    chartHost((host) => lineChart(host, accuracySpec(ladder))), armNotes(armsIn(ladder)), source.cloneNode(true));
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
    claimList(ladder.claims),
    fullTable(STRINGS.allValues, ladderTable(ladder), absentList(ladder)));
}

/** One scope of the sealed test as a figure; every source file is cited under it. */
function sealedFigure(sealed, scope, notes) {
  const rows = rowsOfScope(sealed, scope);
  const items = policiesIn(rows).map((policy) => ({ name: policyName(policy), ...policyStyle(policy) }));
  const text = (STRINGS.sealedScopeCaptions[scope] ?? "") + STRINGS.sealedIntervalCaption;
  const sources = sealed.sources.map(provenance);
  return figure(STRINGS.sealedScopeTitles[scope] ?? scope, text, items,
    chartHost((host) => barChart(host, sealedSpec(rows, scope))), notes, ...sources);
}

function sealedSection(sealed) {
  const arms = [...new Set(sealed.rows.map((r) => ARM_OF_POLICY[r.policy] ?? r.policy))];
  const figures = sealed.scopes.map((scope, i) => sealedFigure(sealed, scope, i === 0 ? armNotes(arms) : null));
  return el("section", { className: "results-section", "aria-labelledby": "sealed-heading" },
    el("h2", { id: "sealed-heading" }, STRINGS.sealedHeading),
    ...figures, claimList(sealed.claims), fullTable(STRINGS.allValues, sealedTable(sealed)));
}

function infraSection(infra) {
  const body = figure(STRINGS.infraTitle, STRINGS.infraCaption, [], el("div", {}, infraTable(infra)),
    infraChecks(infra), provenance(infra.source));
  return el("section", { className: "results-section", "aria-labelledby": "infra-heading" },
    el("h2", { id: "infra-heading" }, STRINGS.infraHeading), body);
}

function e2eSection(e2e) {
  const body = figure(STRINGS.e2eTitle, STRINGS.e2eCaption, [], el("div", {}, e2eTable(e2e)),
    claimList(e2e.claims), provenance(e2e.source));
  return el("section", { className: "results-section", "aria-labelledby": "e2e-heading" },
    el("h2", { id: "e2e-heading" }, STRINGS.e2eHeading), body);
}

function render(view) {
  const sections = [];
  if (view.ladder) sections.push(ladderSection(view.ladder));
  if (view.sealed) sections.push(sealedSection(view.sealed));
  if (view.infra) sections.push(infraSection(view.infra));
  if (view.e2e) sections.push(e2eSection(view.e2e));
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
