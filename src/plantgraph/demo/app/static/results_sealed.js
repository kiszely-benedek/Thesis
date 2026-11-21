/* The sealed test (frozen method against comparison rows) as chart specifications and a table.
   A row is identified by corpus + policy + scope + source label; a pooled row (several plants
   together) and a plant row each carry their own interval method, which is always shown. */

import { pct, seconds, usd } from "./format.js";
import { table } from "./parts.js";
import { armStyle } from "./results_data.js";
import { STRINGS } from "./strings.js";

// Each sealed policy is the same method as one ladder arm, so it shares that arm's style and note.
export const ARM_OF_POLICY = {
  cascade_v4_iso: "cascade_v4_iso", cascade_v4: "cascade_v4_iso", always_g_v2t: "ag", always_c_v2t: "cyp",
  cascade_v3: "cascade_v3", always_g_luna: "ag", always_c_luna: "cyp",
};
// The current system first, the previous system (F1) last.
const POLICY_ORDER = ["cascade_v4_iso", "cascade_v4", "always_g_v2t", "always_c_v2t", "cascade_v3", "always_g_luna", "always_c_luna"];

export function policyName(policy) {
  return STRINGS.policyNames[policy] ?? policy;
}

export function policyStyle(policy) {
  return armStyle(ARM_OF_POLICY[policy] ?? policy);
}

/** The policies of a set of rows, in display order. */
export function policiesIn(rows) {
  const present = [...new Set(rows.map((r) => r.policy))];
  return [...POLICY_ORDER.filter((p) => present.includes(p)), ...present.filter((p) => !POLICY_ORDER.includes(p))];
}

/** The rows of one scope (`headline` or `held-out`). */
export function rowsOfScope(sealed, scope) {
  return sealed.rows.filter((r) => r.scope === scope);
}

const methodName = (row) => STRINGS.intervalMethods[row.interval_method] ?? row.interval_method;

function barOf(row) {
  const accuracy = row.accuracy;
  const tip = [
    policyName(row.policy),
    `${STRINGS.groupName(row.corpus_id, row.n_sheets)}, ${STRINGS.groupKind(row)}`,
    STRINGS.tipAccuracy(pct(accuracy.estimate), pct(accuracy.ci_low), pct(accuracy.ci_high)),
    STRINGS.tipInterval(methodName(row)),
    STRINGS.tipCorrect(row.n_correct, row.n_questions),
  ].join("\n");
  return { value: accuracy.estimate, low: accuracy.ci_low, high: accuracy.ci_high, color: policyStyle(row.policy).color, tip };
}

/** Corpora ordered by plant size, a pooled one before a single plant of the same size. */
function corpusRows(rows) {
  const first = new Map();
  for (const row of rows) if (!first.has(row.corpus_id)) first.set(row.corpus_id, row);
  return [...first.values()].sort((a, b) => a.n_sheets - b.n_sheets || Number(b.pooled) - Number(a.pooled));
}

/** One scope as grouped bars: a group per corpus (named with its kind and interval method), a bar per policy. */
export function sealedSpec(rows, scope) {
  const groups = corpusRows(rows).map((first) => {
    const own = policiesIn(rows).map((p) => rows.find((r) => r.corpus_id === first.corpus_id && r.policy === p));
    const label = [STRINGS.groupName(first.corpus_id, first.n_sheets), STRINGS.groupKind(first), methodName(first)];
    return { label, bars: own.filter((r) => r !== undefined).map(barOf) };
  });
  return {
    height: 330,
    label: STRINGS.sealedChartLabel(STRINGS.scopeNames[scope] ?? scope),
    y: { domain: [0, 1], ticks: [0, 0.25, 0.5, 0.75, 1], format: (v) => pct(v, 0), label: STRINGS.axisAccuracy },
    groups,
  };
}

/** Every row of the sealed view with the counts behind the accuracy and the interval method. */
export function sealedTable(sealed) {
  const rank = (policy) => policiesIn(sealed.rows).indexOf(policy);
  const scopeRank = (scope) => sealed.scopes.indexOf(scope);
  const rows = [...sealed.rows]
    .sort((a, b) => scopeRank(a.scope) - scopeRank(b.scope) || a.n_sheets - b.n_sheets
      || a.corpus_id.localeCompare(b.corpus_id) || rank(a.policy) - rank(b.policy))
    .map((r) => [`${STRINGS.groupName(r.corpus_id, r.n_sheets)} (${STRINGS.groupKind(r)})`,
      STRINGS.scopeNames[r.scope] ?? r.scope, policyName(r.policy), pct(r.accuracy.estimate),
      `${pct(r.accuracy.ci_low)} to ${pct(r.accuracy.ci_high)}`, methodName(r), `${r.n_correct} / ${r.n_questions}`,
      usd(r.cost_per_question_usd), seconds(r.latency_median_s), seconds(r.latency_p90_s)]);
  return table(STRINGS.sealedCols, rows, [3, 4, 6, 7, 8, 9]);
}
