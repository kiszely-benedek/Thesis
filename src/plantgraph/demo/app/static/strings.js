"use strict";
/* The page's user-facing text (English), loaded before app.js. */

const USD_FORMAT = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const USD_SMALL_FORMAT = new Intl.NumberFormat("en-US", {
  style: "currency", currency: "USD", maximumSignificantDigits: 2,
});

// 0 -> "$0"; from one cent up "$2.00"; below that two significant digits, e.g. "$0.00071".
function usd(x) {
  const value = Number(x);
  if (value === 0) return "$0";
  return value >= 0.01 ? USD_FORMAT.format(value) : USD_SMALL_FORMAT.format(value);
}

// All user-facing text (English) lives here. Drawing labels come from the data.
const STRINGS = {
  title: "Plant-scale P&ID question answering",
  dwgLabel: "Go to drawing: DWG",
  dwgGo: "Go",
  dwgUnknown: (id) => `No such drawing in this corpus: ${id}`,
  dwgNoIndex: "The drawing index is not available yet.",
  corpus: "Corpus",
  benchmark: "Benchmark question",
  ownQuestion: "- your own question -",
  question: "Question (free text)",
  answerType: "Answer type",
  ask: "Ask",
  stateLabels: { waiting: "waiting to load", loading: "loading...", ready: "ready", error: "error" },
  noPdf: "no drawing PDF",
  noTier1: "the database step is not available, only step 2 answers",
  spend: (spent, cap) => `Session spend: ${spent} / limit ${cap}`,
  running: "Running...",
  elapsed: (s) => `${s.toFixed(1)} s`,
  capReached: (cap, spent) =>
    `The question was not answered: it would exceed the session spending limit (${cap}); ${spent} spent so far. ` +
    "Restart the server with a larger --session-cap-usd value.",
  answer: "Answer",
  noAnswer: "(no answer)",
  notPresent: "According to the system, this information is not on the drawings.",
  notice: (policy, text) => `Running a rule other than the evaluated one (${policy}). ${text ?? ""}`,
  outcome: "Outcome",
  answeredBy: "Answered by",
  nobody: "nobody (the question did not succeed)",
  fellBack: "fallback: no step was accepted, so the answer of the first step is given",
  latency: "Latency (cascade definition)",
  wall: "Wall-clock time",
  cost: "Cost",
  paid: (cost, spent) => `${usd(cost)}, of which paid now ${usd(spent)}`,
  cacheHit: "Warning: a model call of this answer was served from a cache. The demo should answer live only.",
  tierTable: "Per step",
  tierCols: ["Step", "Outcome", "Accepted", "Latency", "Cost", "Calls", "Steps", "Stop", "Rows"],
  yes: "yes",
  no: "no",
  answerSheets: "Drawings of the answer",
  readSheets: "Drawings read by the agent",
  goldSheets: "Reference evidence (drawings)",
  none: "-",
  reference: "Reference answer",
  verdict: "Verdict",
  correct: "correct",
  incorrect: "incorrect",
  crossSheet: (b) =>
    `k = ${b.k ?? "?"} (connector: ${b.k_connector ?? "?"}, identity: ${b.k_identity ?? "?"}), u = ${b.u ?? "?"}`,
  answerTypes: {
    FREE_TEXT: "free text", CLASS_NAME: "class name", UNIT_ID: "unit identifier",
    TAG: "tag", TAG_SET: "set of tags", UNIT_SET: "set of units",
    SHEET_SET: "set of drawings", TAG_PATH: "tag path", COUNT: "count", BOOLEAN: "yes/no",
  },
};
