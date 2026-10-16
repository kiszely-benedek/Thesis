/* All page text that is not a code from the server (English). Codes (outcomes, error codes,
   topics, store states...) get their text from labels.en.json through labels.js. */

import { usd } from "./format.js";

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
    "This demo turns the piping and instrumentation diagrams (P&IDs) of a generated chemical plant " +
    "into a graph: equipment, valves and instruments are the nodes, pipes and signal lines are the " +
    "edges. Every question you ask is answered live by a language model working on the graph of the " +
    "whole plant, even when the answer runs across many drawing sheets — what you see is the " +
    "real time and cost. Next to every answer you see which sheets it came from, and one click " +
    "takes you there.",
  introSteps: (sheetsA, sheetsB) => [
    sheetsB === null ? `Pick a plant: ${sheetsA} drawing sheets.`
      : `Pick a plant: ${sheetsA} or ${sheetsB} drawing sheets.`,
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

  // answer
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
  incorrect: "does not match",
  crossSheet: (b) =>
    `k = ${b.k ?? "?"} (connector: ${b.k_connector ?? "?"}, identity: ${b.k_identity ?? "?"}), u = ${b.u ?? "?"}`,
};
