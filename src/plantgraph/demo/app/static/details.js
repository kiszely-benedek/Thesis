/* The folded "Details" of an answer card: the per-step table, the route, and the model calls. */

import { el } from "./dom.js";
import { seconds, usd } from "./format.js";
import { label } from "./labels.js";
import { cardSection, table } from "./parts.js";
import { routeView } from "./steps.js";
import { STRINGS } from "./strings.js";

const NOT_APPLICABLE = "–";

function yesNo(flag) {
  return flag ? STRINGS.yes : STRINGS.no;
}

/** A count that only some tiers have (agent steps, query rows), or a dash. */
function optional(value) {
  return value === null || value === undefined ? NOT_APPLICABLE : String(value);
}

function tierRow(t) {
  return [
    label("tiers", t.tier), label("outcomes", t.outcome), yesNo(t.accepted),
    seconds(t.latency_s), usd(t.cost_usd), String(t.n_calls), String(t.n_cached), optional(t.n_steps),
    t.stop_reason ? label("stop_reasons", t.stop_reason) : NOT_APPLICABLE, optional(t.n_rows),
  ];
}

// the figure columns of STRINGS.tierCols: model time, cost, calls, from cache, tool calls, rows
const TIER_NUMERIC = [3, 4, 5, 6, 7, 9];
// the figure columns of STRINGS.callCols: latency, cost
const CALL_NUMERIC = [2, 3];

function callRow(call) {
  return [
    label("call_purposes", call.purpose), label("strategies", call.strategy),
    seconds(call.latency_s), usd(call.cost_usd), yesNo(call.from_cache),
    call.error_kind ? label("call_errors", call.error_kind) : NOT_APPLICABLE,
  ];
}

/** The folded details, closed by default. */
export function renderDetails(result) {
  const { live, trace } = result;
  return el(
    "details", { className: "details" },
    el("summary", {}, STRINGS.detailsHeading),
    el(
      "div", { className: "details-body" },
      cardSection(STRINGS.tierTable, table(STRINGS.tierCols, live.tiers.map(tierRow), TIER_NUMERIC)),
      cardSection(STRINGS.routeHeading, routeView(trace, live)),
      cardSection(STRINGS.callsHeading, table(STRINGS.callCols, trace.calls.map(callRow), CALL_NUMERIC)),
    ),
  );
}
