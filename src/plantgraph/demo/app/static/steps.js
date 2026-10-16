/* The route of one ask as a step list: the database query with its rows, and the agent's tool calls.
   Everything shown was recorded from the real model traffic (the server's `trace`), never rebuilt. */

import { copyButton } from "./copy.js";
import { el } from "./dom.js";
import { cellText, columnsOf } from "./format.js";
import { strategyTerm, term } from "./glossary.js";
import { label } from "./labels.js";
import { table } from "./parts.js";
import { STRINGS } from "./strings.js";

/** "Step 1: database query (Cypher)": the cascade's name for the tier that ran `strategy`. */
function tierHeading(live, strategy) {
  const tier = live.tiers.find((t) => t.strategy === strategy);
  const text = tier ? label("tiers", tier.tier) : label("strategies", strategy);
  return el("h3", { className: "route-heading" }, strategyTerm(strategy, text));
}

function unreadableFlag() {
  return el("span", { className: "pill warn" }, STRINGS.unparsed);
}

/** The step's number bubble. With a route view (`sync`) it is a button that makes this the current
    step there, and it shows when it is; `index` is the step's 0-based place in the whole route. */
function stepBubble(index, sync) {
  const text = String(index + 1);
  if (sync === null) return el("span", { className: "bubble", textContent: text });
  const bubble = el("button", { type: "button", className: "bubble step-pick", textContent: text });
  bubble.setAttribute("aria-label", STRINGS.pickStep(index + 1));
  bubble.addEventListener("click", () => sync.select(index));
  const mark = (current) => {
    bubble.classList.toggle("current", current === index);
    bubble.setAttribute("aria-pressed", String(current === index));
  };
  sync.onChange(mark);
  mark(sync.current);
  return bubble;
}

/** Text exactly as recorded, in a scrollable monospace block. */
function rawBlock(text) {
  return el("pre", { className: "code" }, text);
}

// ---------- the database query step ----------

function rowsTable(step) {
  const columns = columnsOf(step.rows);
  const cells = step.rows.map((row) => columns.map((name) => cellText(row[name])));
  return table(columns, cells, [], "rows-table");
}

/** The rows the model was given, under an "N rows" header with the truncation note. */
function rowsBlock(step) {
  if (step.rows.length === 0) return el("p", { className: "hint" }, STRINGS.noRows);
  const note = step.truncated ? STRINGS.rowsCutNote : STRINGS.rowsShownNote;
  return el(
    "div", {},
    el("h4", { className: "field-label" }, STRINGS.rowsHeader(step.rows.length)),
    el("p", { className: step.truncated ? "hint warn-text" : "hint" }, note),
    rowsTable(step),
  );
}

function cypherStepView(step, live, index, sync) {
  const heading = el("div", { className: "tier-head" }, stepBubble(index, sync), tierHeading(live, step.tier));
  const parts = [heading];
  const head = el("div", { className: "block-head" }, el("h4", { className: "field-label" }, STRINGS.queryHeading));
  head.append(copyButton(step.query));
  parts.push(head, rawBlock(step.query));
  if (step.parsed) {
    parts.push(rowsBlock(step));
    return el("div", { className: "route-tier" }, ...parts);
  }
  // the context had an unexpected shape: show it whole instead of guessing
  parts.push(unreadableFlag(), el("p", { className: "hint" }, STRINGS.unparsedNote), rawBlock(step.context));
  return el("div", { className: "route-tier" }, ...parts);
}

// ---------- the graph agent step ----------

/** `search_tag(tag="P-151-1")`: the call as an engineer would write it. */
function callText(step) {
  const args = Object.entries(step.args).map(([name, value]) => `${name}=${JSON.stringify(value)}`);
  return `${step.tool}(${args.join(", ")})`;
}

function itemChips(items) {
  if (items.length === 0) return null;
  const chips = items.map((item) => el("span", { className: "tag", textContent: item }));
  return el("div", { className: "items" }, el("span", { className: "hint" }, term("tag", STRINGS.toolItems), ": "), ...chips);
}

/** The tool's answer, folded: it can be long. */
function observationBlock(step) {
  if (step.observation === "") return el("p", { className: "hint" }, STRINGS.noObservation);
  const summary = el("summary", {}, STRINGS.observation(step.observation.length));
  return el("details", { className: "observation" }, summary, rawBlock(step.observation));
}

function toolStepView(step, index, sync) {
  const body = step.parsed
    ? [el("code", { className: "tool-call", textContent: callText(step) })]
    : [unreadableFlag(), el("p", { className: "hint" }, STRINGS.unparsedNote), rawBlock(step.reply)];
  const bubble = stepBubble(index, sync);
  const content = [...body, itemChips(step.items), observationBlock(step)].filter(Boolean);
  return el("li", { className: "tool-step" }, bubble, el("div", { className: "tool-body" }, ...content));
}

function agentTierView(steps, live, firstIndex, sync) {
  const list = el("ol", { className: "tool-steps" }, ...steps.map((step) => toolStepView(step, firstIndex + step.position, sync)));
  return el("div", { className: "route-tier" }, tierHeading(live, steps[0].tier), list);
}

/** Agent steps grouped by the tier that took them, in the order the tiers first appear. */
function groupByTier(steps) {
  const groups = new Map();
  for (const step of steps) groups.set(step.tier, [...(groups.get(step.tier) ?? []), step]);
  return [...groups.values()];
}

// ---------- the whole route ----------

/** The route as a list of tiers, each with its query or tool calls. `sync` (step_sync.js) is null
    when the card has no route view to keep in step with. */
export function routeView(trace, live, sync) {
  // a step's place in the route view: database queries first, then the agent's tool calls
  const agent = trace.agent.map((step, position) => ({ ...step, position }));
  const views = [
    ...trace.cypher.map((step, i) => cypherStepView(step, live, i, sync)),
    ...groupByTier(agent).map((steps) => agentTierView(steps, live, trace.cypher.length, sync)),
  ];
  const notes = [];
  if (trace.error) notes.push(el("p", { className: "notice" }, STRINGS.traceFailed(trace.error)));
  if (trace.unlogged_attempts > 0) notes.push(el("p", { className: "hint" }, STRINGS.unloggedAttempts(trace.unlogged_attempts)));
  if (views.length === 0 && !trace.error) notes.push(el("p", { className: "hint" }, STRINGS.noRoute));
  return el("div", { className: "route" }, el("p", { className: "hint" }, STRINGS.routeHint), ...notes, ...views);
}
