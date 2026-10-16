/* All page text that is not a code from the server (English). Codes (outcomes, error codes,
   topics, store states...) get their text from labels.en.json through labels.js. */

import { count, usd } from "./format.js";

export const STRINGS = {
  title: "Plant-scale P&ID questions",
  pageTitle: "Plant-scale P&ID demo",

  // header
  plantCell: "Plant",
  plantOption: (id, sheets) => (sheets === null ? id : `${id} · ${sheets} sheets`),
  graphDbCell: "Graph DB",
  graphDbEmpty: "empty",
  spendCell: "Spend",
  spendValue: (spent, cap) => `${usd(spent)} / ${usd(cap)}`,
  introOpen: "What is this?",
  skipToQuestion: "Skip to the question",
  menuOpen: "More",
  themeLabel: { auto: "Theme: automatic", light: "Theme: light", dark: "Theme: dark" },
  themeIcon: { auto: "◐", light: "☀", dark: "☾" },

  // "What is this?" box
  introHeading: "What is this?",
  introText:
    "This demo turns the {{pid|piping and instrumentation diagrams (P&IDs)}} of a generated chemical plant " +
    "into a graph: equipment, valves and instruments are the nodes, pipes and signal lines are the " +
    "edges. Every question you ask is answered live by a language model working on the graph of the " +
    "whole plant, even when the answer runs across many drawing sheets — what you see is the " +
    "real time and cost. Next to every answer you see which {{sheet|drawing sheets}} it came from, and one click " +
    "takes you there.",
  introSteps: (sheetsA, sheetsB) => [
    sheetsB === null ? `Pick a plant: ${sheetsA} {{sheet|drawing sheets}}.`
      : `Pick a plant: ${sheetsA} or ${sheetsB} {{sheet|drawing sheets}}.`,
    "Click an example question, or type your own.",
    "Click a DWG label: the drawing on the left jumps to that sheet.",
  ],
  introHide: "Got it, hide this",

  // drawings
  dwgLabel: "Go to sheet: DWG",
  dwgGo: "Go",
  dwgUnknown: (id) => `No such drawing in this plant: ${id}`,
  dwgNoIndex: "The drawing index is not available yet.",
  pdfTitle: "Drawings",
  noPdf: "no drawing PDF",

  // plant
  plantNone: "The graph database holds no plant. Select a plant above to load it.",
  plantHeld: (id) => `The graph database holds plant ${id}.`,
  plantLoading: (id, s, last) =>
    `Loading ${id} into the graph database… ${s.toFixed(1)} s` +
    (last === undefined ? "" : ` (last time ${last.toFixed(1)} s)`),
  plantLoaded: (load) =>
    `${load.corpus_id} loaded in ${load.load_s.toFixed(1)} s` +
    (load.wiped.length ? ` (${load.wiped.join(", ")} wiped in ${load.wipe_s.toFixed(1)} s)` : ""),
  plantFailed: (id) => `Loading ${id} into the graph database failed.`,
  corpusStates: { waiting: "waiting to load", loading: "loading…", ready: "ready", error: "error" },

  // ask panel
  questionLabel: "Question",
  questionFallback: "Type a question about the plant…",
  ask: "Ask",
  askKeys: "Ctrl+Enter asks",
  examples: (n) => `Example questions (${n})`,
  examplesNeedPlant: "Select a plant to see its example questions.",
  examplesLoading: "Loading the example questions…",
  asking: (s) => `Asking… ${s.toFixed(1)} s`,
  prepared: (s) => `Model cache emptied in ${s.toFixed(1)} s before the ask.`,
  capReached: (cap, spent) =>
    `The question was not answered: it would exceed the session spending limit (${cap}); ${spent} spent so far. ` +
    "Restart the server with a larger --session-cap-usd value.",
  technicalDetails: "Technical details",
  unexpectedError: "Something unexpected went wrong.",

  // answer card
  answer: "Answer",
  noAnswer: "(no answer)",
  notPresent: "According to the system, this information is not on the drawings.",
  fallbackLine:
    "The system accepted none of the steps' answers; this is the first step's answer. Treat it with care.",
  notice: (policy, text) => `Running a rule other than the evaluated one (${policy}). ${text ?? ""}`,
  cacheHit: "Warning: a model call of this answer was served from a cache. The demo should answer live only.",
  nobody: "nobody (the question did not succeed)",
  // the one facts line under the answer; double braces around "key | word" mark a glossary word
  // (the tier's name follows, as its own glossary word)
  factsLine: (wall, model, cost) =>
    `{{wall_time|Answered in}} ${wall} · {{model_time|model time}} ${model} · cost ${cost} · by `,
  preparing: (s) => `Preparing took ${s.toFixed(1)} s (emptying the model cache) - not part of the answer time.`,
  knowHeading: "How does it know?",
  answerSheets: "Drawings of the items in the answer",
  readSheets: "Drawings the agent read",
  noSheets: "none",
  checkHeading: "Check against the reference",
  reference: "Reference answer",
  verdict: "The system's answer",
  correct: "correct",
  incorrect: "does not match",
  goldSheets: "Drawings needed for the correct answer",
  notRecorded: "not recorded for this question",
  kValue: (b) =>
    b.k === null ? STRINGS.notRecorded
      : `${count(b.k, "link")} between sheets: ${b.k_connector ?? "?"} through ` +
        `{{off_page_connector|off-page connectors}}, ${b.k_identity ?? "?"} because the same item is drawn on both sheets`,
  uValue: (b) => (b.u === null ? STRINGS.notRecorded : `${count(b.u, "link")} between {{unit|process units}}`),
  copy: "Copy",
  copied: "Copied",
  copyFailed: "Copying failed.",
  howHeading: "How it works",
  howText: (cutoff) =>
    "The question first goes to a {{cypher|database-query step}}: the language model writes a query for the " +
    "{{graph_db|graph database}} that holds the whole plant, and words an answer from the rows it gets back. " +
    "If that step finds no rows, says the data is not on the drawings, or gives a reply that cannot be read, " +
    "the question goes to the {{agent|graph agent}}: it explores the graph, which spans many " +
    "{{sheet|drawing sheets}}, step by step with tools (search, neighbours, path). Together the two steps are " +
    `a {{cascade|cascade}}. One question gets ${cutoff} seconds in total. The drawings on the left were made ` +
    "from the system's own input, so they show what the system sees. Every question runs live: it makes real " +
    "model calls, so the time and cost shown are the real ones.",

  // details: tiers, route, calls
  detailsHeading: "Details",
  tierTable: "Per step",
  tierCols: ["Step", "Outcome", "Accepted", "Model time", "Cost", "Calls", "From cache", "Tool calls", "Stopped because", "Rows"],
  yes: "yes",
  no: "no",
  none: "-",
  routeHeading: "The route",
  routeHint: "What the system actually did, recorded from the real model traffic.",
  noRoute: "No route was recorded for this answer.",
  traceFailed: (why) => `The route could not be built (the answer above is still valid): ${why}`,
  unloggedAttempts: (n) => `${count(n, "request attempt")} had no logged reply (retried after an error or still running).`,
  queryHeading: "Query written by the model",
  rowsHeader: (n) => count(n, "row"),
  rowsShownNote: "The model saw these rows.",
  rowsCutNote: "The result was cut off at the row limit: the model saw only these rows.",
  noRows: "The query returned no rows.",
  unparsed: "unreadable",
  unparsedNote: "This part could not be split into its pieces; it is shown exactly as it was recorded.",
  toolItems: "Tags and items named",
  observation: (chars) => `What came back (${count(chars, "character")})`,
  noObservation: "no observation found",
  callsHeading: "Model calls",
  callCols: ["Call", "Step", "Latency", "Cost", "From cache", "Problem"],
};
