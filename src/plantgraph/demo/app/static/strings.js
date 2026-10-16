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

  // presentation mode
  presentOpen: "Present",
  presentBarLabel: "Presentation",
  presentChoose: "Choose a talk",
  presentNone: "No talks are configured in this demo.",
  presentSequence: (title, steps) => `${title} · ${steps} steps`,
  presentCounter: (n, total) => `${n} / ${total}`,
  presentBack: "◀ Back",
  presentNext: "Next ▶",
  presentExit: "Exit",
  presentResultsStep: "Recorded results: how the methods compare as the plant grows",
  presentKeys: "→ or Space: next question, asked live · ←: back · Esc: exit",
  presentSwitchFirst: (id) => `select plant ${id} above first`,
  presentPlantNotHeld: (id) => `wait until ${id} is in the graph database`,
  presentMissing: (id, why) => (why === "corpus_not_ready"
    ? "the plant is still loading" : `the plant has no example ${id}`),
  presentLoadFailed: "The talks could not be read from the server.",

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

  // tabs and the Results tab
  tabsLabel: "View",
  tabAsk: "Ask",
  tabResults: "Results",
  resultsHeading: "Recorded results",
  resultsIntro:
    "These figures come from two recorded experiments, not from this demo's live answers. They compare " +
    "ways of answering questions about {{pid|P&IDs}} as the plant grows. Every value is read from the " +
    "experiment's report file, named under each figure.",
  resultsLoading: "Loading the recorded results…",
  resultsEmpty: "No recorded results are available in this demo.",
  sourceLabel: "Source",
  resultRowLabel: "result row",
  modifiedLabel: "modified",
  allValues: "All values as a table",
  noRun: "no run",
  absentHeading: "Cells the experiment has no run for (shown as gaps in the lines):",
  ladderCols: ["Method", "Plant", "Questions", "Accuracy", "95 % interval", "Mean cost", "Median time"],
  sealedCols: ["Plant", "Method", "Accuracy", "95 % interval", "Correct", "Cost per question", "Median time", "90th percentile time"],

  // figure 1-3: the scale ladder
  ladderHeading: "Scale ladder: accuracy, cost and time as the plant grows",
  ladderMeta: (families, cutoff) =>
    `Common question families (${families}). A question counts as correct only if it is answered correctly within ${cutoff} s.`,
  accuracyTitle: "Accuracy by plant size",
  accuracyCaption: (hasGaps) =>
    "Each line is one way of answering the same questions on plants of growing size (the horizontal axis counts " +
    "drawing sheets and is logarithmic). Higher is better. Each marker has a bar showing its {{wilson|Wilson interval}}; " +
    "where the bars of two lines overlap, the difference between them is not reliable. The dashed vertical line is the " +
    "{{context_wall|context wall}}: to its right the whole drawing set no longer fits into one prompt, so putting it " +
    "there is not possible at all." +
    (hasGaps ? " A gap in a line means the experiment has no run for that plant size; it is not a zero." : "") +
    " The single-step rows are the comparison for the cascade.",
  costTitle: "Mean cost per question",
  costCaption:
    "The average price of answering one question, in US dollars. The vertical axis is logarithmic: each gridline " +
    "is ten times the one below. The lines are the same methods as above.",
  latencyTitle: "Median answer time",
  latencyCaption: "Half of the questions were answered faster than this. The lines are the same methods as above.",
  armNames: {
    "ctx-high": "ContextRAG (high effort)", "ctx-low": "ContextRAG (low effort)", cyp: "Always Cypher",
    ag: "Always graph agent", cascade_v3: "Cascade (v3)",
  },
  armNotes: {
    cascade_v3:
      "The demo's own method, a {{cascade|cascade}}: the database-query step first, then the graph agent when " +
      "the query's answer is not accepted.",
    ag: "Every question goes to the {{agent|graph agent}} alone. A comparison row.",
    cyp: "Every question goes to the database-query step ({{cypher|Cypher}}) alone. A comparison row.",
    "ctx-high":
      "{{context_rag|ContextRAG}}: the whole graph is written into the model's prompt as text; the model reasons with high effort.",
    "ctx-low": "The same, with low reasoning effort; run on the one- and ten-sheet plants only.",
  },
  accuracyChartLabel: "Accuracy of each method by plant size",
  costChartLabel: "Mean cost per question of each method by plant size",
  latencyChartLabel: "Median answer time of each method by plant size",
  axisSheets: "Drawing sheets in the plant (log scale)",
  axisAccuracy: "Accuracy",
  axisCost: "Cost per question (log scale)",
  axisLatency: "Median time",
  wallLabel: (sheets) => ["Context wall", `≈ ${sheets} sheets`],

  // figure 4: the sealed test
  sealedHeading: "Sealed test: the final comparison on two plants of different size",
  sealedTitle: "Accuracy on the sealed test",
  sealedCaption:
    "A separate experiment: its questions were held out of development and the method was frozen before they were " +
    "run. Bars show accuracy per plant and method; the whisker is the {{wilson|Wilson interval}}. This question set " +
    "differs from the ladder's, so the two experiments are not drawn on one chart. The {{cascade|cascade}} is the " +
    "demo's method; Always graph agent and Always Cypher answer every question with one step only and are the " +
    "comparison rows. The table gives the exact counts, cost and times.",
  sealedChartLabel: "Accuracy of each method on the two sealed-test plants",
  policyNames: { cascade_v3: "Cascade (v3)", always_g_luna: "Always graph agent", always_c_luna: "Always Cypher" },

  // chart tooltips (one line each; the chart adds the method and plant lines)
  tipAccuracy: (share, low, high) => `Accuracy ${share} (95 % interval ${low} to ${high})`,
  tipCost: (cost) => `Mean cost per question ${cost}`,
  tipLatency: (time) => `Median answer time ${time}`,
  tipQuestions: (n) => count(n, "question"),
  tipCorrect: (correct, n) => `${correct} of ${count(n, "question")} correct`,

  // drawings
  dwgLabel: "Find on the drawings: sheet or tag",
  dwgGo: "Find",
  dwgPlaceholder: "sheet number or tag",
  dwgNoPlant: "Select a plant first.",

  // the tag lookup under the drawing bar
  findNone: (query) => `No sheet or item tag "${query}" in this plant.`,
  findDidYouMean: "Did you mean:",
  findOnSheets: (n) => `on ${count(n, "sheet")}:`,
  findUnit: "unit",
  findNoSheets: "not drawn on any sheet",
  findSuggestionsLabel: "Matching tags",
  findNextSheet: (sheets) =>
    sheets.length < 2 ? `On DWG ${sheets[0]}` : `On ${sheets.length} sheets: DWG ${sheets.join(", ")} - click again for the next`,
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

  // live timeline of an ask (one line per attempt to the model provider)
  writingQuery: "Step 1 · writing the database query…",
  queryWritten: "Query written",
  queryEmpty: "The model replied with an empty query.",
  writingAnswer: "Writing the answer…",
  answerWritten: "Answer written",
  waitingForModel: "Waiting for the model…",
  modelReplied: "The model replied",
  agentWaiting: (n) => `Action ${n} · waiting for the model…`,
  agentAction: (n) => `Action ${n}`,
  agentNoCall: (n) => `Action ${n} · the reply holds no tool call`,
  providerFailed: (reason, next) => `The model provider did not answer (${reason}) — ${next}`,
  retrying: (next, max) => `retrying (attempt ${next} of ${max})`,
  gaveUp: (max) => `no attempts left (${max} made)`,
  timelineHeading: "What happened, attempt by attempt",
  timelineHint: "Every request to the model provider, in the order it was sent, with the seconds each took.",

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
  // amber addition to the facts line when the provider's errors cost time
  lostTime: (n, s) => ` · {{lost_time|${count(n, "failed provider attempt")}}}, ${s.toFixed(1)} s lost`,
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
  copyAnswer: "Copy answer",
  // the plain text a card's Copy puts on the clipboard, ready to paste into notes or a ticket
  copyText: (c) =>
    [
      `Question: ${c.question}`,
      `Plant: ${c.plant} (${count(c.nSheets, "sheet")})`,
      `Answer: ${c.answer}`,
      `Sheets: ${c.sheets.length === 0 ? "none" : c.sheets.map((id) => `DWG ${id}`).join(", ")}`,
      `Answered by: ${c.answeredBy}`,
      `Time: ${c.time}`,
      `Cost: ${c.cost}`,
    ].join("\n"),
  // a tag in the answer after a click: which of its sheets the drawing shows now
  tagShowing: (sheets, turn) =>
    `Showing DWG ${sheets[turn]} (${turn + 1} of ${sheets.length})` + (sheets.length > 1 ? " - click again for the next" : ""),
  sheetNotInIndex: (id) => `DWG ${id} is not in this plant's drawing index`,
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
  pickStep: (n) => `Show action ${n} in the route view`,
  callsHeading: "Model calls",
  callCols: ["Call", "Step", "Latency", "Cost", "From cache", "Problem"],

  // route view (an "action" is one database query or one agent tool call; "step" already names the cascade's tiers)
  routeViewHeading: "How the model got there",
  routeViewHint:
    "The plant items the system looked at, action by action, with the connections between them on the drawings. " +
    "Hover an item for details, click it to show it on the drawing.",
  routeSvgLabel: "Route of the answer through the plant",
  routeColumn: (key) => (key === "q" ? "Question" : key === "a" ? "Answer" : `Action ${key + 1}`),
  routeStepLabel: (n, total, text) => `Action ${n} of ${total}: ${text}`,
  routeNoSteps: "No action was recorded; these are the items the question and the answer name.",
  routePrevious: "Previous action",
  routeNext: "Next action",
  routeSlider: "Action",
  routePlay: "Play",
  routePause: "Pause",
  routePathToggle: "Answer path",
  routeZoomIn: "Zoom in",
  routeZoomOut: "Zoom out",
  routeFit: "Fit",
  routeGap: "no direct link",
  routeNoTag: "(no tag)",
  routeUnit: (id) => `Process unit ${id}`,
  routeNoUnit: "No process unit on record",
  routeSheets: "Drawings",
  routeFirstSeen: (n) => `First seen in action ${n}`,
  routeInAnswer: "Named in the answer",
  routeNotInReference: "Not in the reference answer",
  routeInQuestion: "Named in the question",
  routeClickHint: "Click to show it on the drawing",
  routeNoSheetHint: "No drawing on record",
  routeNoSheetNote: (name) => `${name} has no drawing on record.`,
  routeShowing: (name, sheet, n, total) => `${name}: showing DWG ${sheet} (${n} of ${total}).${total > 1 ? " Click again for the next drawing." : ""}`,
  routeOmitted: (n) => `${count(n, "more item")} not shown`,
  legendFamilies: { equipment: "equipment", valve: "valve", instrument: "instrument", other: "other item" },
  legendMarks: { now: "current action", answer: "in the answer", asked: "named in the question", wrong: "not in the reference answer" },
  legendLines: { flow: "flow", signal: "signal", gap: "no direct connection" },
};
