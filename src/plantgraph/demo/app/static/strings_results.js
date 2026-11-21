/* The text of the Results tab (English). Captions state rules and describe what a figure shows; no
   measured number is ever typed here: every value comes from /api/results. Merged into STRINGS (strings.js).
   Double braces around "key | word" mark a glossary word. */

import { count } from "./format.js";

export const RESULTS_STRINGS = {
  resultsHeading: "Recorded results",
  resultsIntro:
    "These figures come from recorded experiments, not from this demo's live answers. They compare " +
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
  sealedCols: [
    "Plant", "Scope", "Method", "Accuracy", "95 % interval", "Interval made by", "Correct",
    "Cost per question", "Median time", "90th percentile time",
  ],
  claimsHeading: "Registered claims and their verdicts",
  claimsNote:
    "Each claim was written down before the run. PASS: it held. FAIL: it did not hold in this experiment. " +
    "REPORTED: measured and shown, with no pass or fail rule. NOT_RUN: not measured. The wording is the report's own.",

  // figures 1-3: the scale ladder
  ladderHeading: "Scale ladder: accuracy, cost and time as the plant grows",
  ladderMeta: (families, cutoff) =>
    `Question families every method was run on (${families}). A question counts as correct only if it is answered correctly within ${cutoff} s.`,
  accuracyTitle: "Accuracy by plant size",
  accuracyCaption: (hasGaps) =>
    "Each line is one way of answering the same questions on plants of growing size (the horizontal axis counts " +
    "drawing sheets and is logarithmic). Higher is better. Each marker has a bar showing its {{wilson|Wilson interval}}; " +
    "where the bars of two lines overlap, the difference between them is not reliable. The dashed vertical line is the " +
    "{{context_wall|context wall}}: to its right the whole drawing set no longer fits into one prompt, so putting it " +
    "there is not possible at all." +
    (hasGaps ? " A gap in a line means the experiment has no run for that plant size; it is not a zero." : "") +
    " The chart only draws the measurements; whether a registered expectation held is stated by the claim lines below.",
  costTitle: "Mean cost per question",
  costCaption:
    "The average price of answering one question, in US dollars. The vertical axis is logarithmic: each gridline " +
    "is ten times the one below. The lines are the same methods as above.",
  latencyTitle: "Median answer time",
  latencyCaption: "Half of the questions were answered faster than this. The lines are the same methods as above.",
  armNames: {
    "ctx-high": "ContextRAG (high effort)", "ctx-low": "ContextRAG (low effort)", cyp: "Always Cypher",
    ag: "Always graph agent", cascade_v4_iso: "Cascade (V2T-A2)", cascade_v3: "F1, previous system",
  },
  armNotes: {
    cascade_v4_iso:
      "The demo's own method, a {{cascade|cascade}} with {{need_routing|need routing}}: the database-query step first " +
      "(or the graph agent at once for questions that ask for the path up to the first valve), then the graph " +
      "agent when the query's answer is not accepted.",
    cascade_v3: "The previous version of the cascade (F1), drawn only for comparison; the demo no longer runs it.",
    ag: "Every question goes to the {{agent|graph agent}} alone. A comparison row.",
    cyp: "Every question goes to the database-query step ({{cypher|Cypher}}) alone. A comparison row.",
    "ctx-high":
      "{{context_rag|ContextRAG}}: the whole graph is written into the model's prompt as text; the model reasons with high effort.",
    "ctx-low": "The same, with low reasoning effort; run on the smallest plants only.",
  },
  accuracyChartLabel: "Accuracy of each method by plant size",
  costChartLabel: "Mean cost per question of each method by plant size",
  latencyChartLabel: "Median answer time of each method by plant size",
  axisSheets: "Drawing sheets in the plant (log scale)",
  axisAccuracy: "Accuracy",
  axisCost: "Cost per question (log scale)",
  axisLatency: "Median time",
  wallLabel: (sheets) => ["Context wall", `≈ ${sheets} sheets`],

  // figures 4-5: the sealed test, one chart per scope
  sealedHeading: "Sealed test: the frozen method against its comparison rows",
  sealedScopeTitles: { headline: "Accuracy on the sealed test: headline question families", "held-out": "Accuracy on the sealed test: held-out question families" },
  sealedScopeCaptions: {
    headline:
      "A separate experiment: the method was frozen before these questions were run. One group per test " +
      "corpus, one bar per method. The headline scope leaves out the LOOP_ACTUATED_VALVE question family. ",
    "held-out":
      "The held-out families were kept out of tuning. Where they score below the headline chart, the headline " +
      "figure is partly tuned to its families. ",
  },
  sealedIntervalCaption:
    "The whisker on a bar is its confidence interval, and each group says how it was made. A single plant gets a " +
    "{{wilson|Wilson interval}}. A group {{pooled|pooled}} over several plants gets a " +
    "{{two_stage_bootstrap|two-stage bootstrap}}, which understates the differences between plants, so the two kinds " +
    "of interval are not comparable. The previous system is drawn as its own bars; no difference with an interval " +
    "between it and the current system was computed, so none is drawn. The table gives the exact counts, cost and times.",
  sealedChartLabel: (scope) => `Accuracy of each method on the sealed-test corpora, ${scope} question families`,
  policyNames: {
    cascade_v4_iso: "Cascade (V2T-A2)", cascade_v4: "Cascade (v4)", always_g_v2t: "Always graph agent",
    always_c_v2t: "Always Cypher", cascade_v3: "F1, previous system", always_g_luna: "Always graph agent",
    always_c_luna: "Always Cypher",
  },
  scopeNames: { headline: "headline", "held-out": "held-out" },
  intervalMethods: { wilson: "Wilson interval", "two-stage bootstrap": "two-stage bootstrap" },
  groupName: (corpusId, sheets) => `${corpusId} · ${count(sheets, "sheet")}`,
  groupKind: (row) => (row.pooled ? `pooled over ${row.n_plants} plants` : "one plant"),

  // infrastructure
  infraHeading: "Infrastructure: what a larger plant costs to build and run",
  infraTitle: "Build, start-up, memory and database latency by plant size",
  infraCaption:
    "What it takes to build the graph from the drawings, keep it, start the server and run a database query, " +
    "measured on a small and a large plant. Each row names its unit. The check lines are the report's own " +
    "self-checks: a FAIL or FLAG limits how far the rows can be trusted, so read it before quoting a figure.",
  infraCols: ["Measure", "Unit"],
  infraChecksHeading: "The report's self-checks (click one for its detail)",
  infraUnits: { count: "count", s: "seconds", bytes: "bytes", usd: "US dollars" },
  infraMeasures: {
    "size.sheets": "Drawing sheets in the plant",
    "store.data_bytes": "Graph store size on disk",
    "ingest.build_total": "Time to build the graph from the drawings",
    "startup.total": "Server start-up, including a rebuild",
    "startup.without_rebuild": "Server start-up, graph already built",
    "process.peak_bytes": "Peak memory of the server process",
    "neo4j.rss_bytes": "Memory held by the graph database",
    "cypher_db_only.local_median_s": "Database query alone, median time",
    "cypher_db_only.local_p90_s": "Database query alone, 90th percentile time",
  },

  // tag identity, end to end
  e2eHeading: "Tag identity: clean tags against inconsistent tags, end to end",
  e2eTitle: "Accuracy with clean and with inconsistent tags",
  e2eCaption:
    "The same questions answered on the clean plants (the first row below) and on copies in which the same item is written with " +
    "inconsistent tags (the V arms). Each V arm uses one {{tag_deciders|tag-identity decider}} to decide when two " +
    "tags are the same item. Tags that differ by one letter, such as {{spare_ab|spare A/B pairs}}, are the hard " +
    "case: they are two items. Pooled arms use a {{two_stage_bootstrap|two-stage bootstrap}} interval, single " +
    "plants a {{wilson|Wilson interval}}. The registered claims are below.",
  e2eCols: ["Arm", "Corpus", "Correct", "Accuracy", "95 % interval", "Interval made by"],
  e2eArmNames: {
    R5: "R5 · clean tags",
    "V-d0": "V-d0 · decider D0",
    "V-d2": "V-d2 · decider D2",
    "V-d4": "V-d4 · decider D4",
  },
  e2eCorpus: (corpus) => (corpus === "pooled" ? "{{pooled|pooled}}, all test plants" : corpus),

  // chart tooltips (one line each; the chart adds the method and plant lines)
  tipAccuracy: (share, low, high) => `Accuracy ${share} (95 % interval ${low} to ${high})`,
  tipInterval: (method) => `Interval: ${method}`,
  tipCost: (cost) => `Mean cost per question ${cost}`,
  tipLatency: (time) => `Median answer time ${time}`,
  tipQuestions: (n) => count(n, "question"),
  tipCorrect: (correct, n) => `${correct} of ${count(n, "question")} correct`,
};
