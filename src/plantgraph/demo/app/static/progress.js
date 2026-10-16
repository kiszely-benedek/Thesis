/* The timeline of an ask: one line per attempt to the model provider, newest last. While the ask runs it
   sits under the "Asking..." timer; when the answer arrives the same lines move into the card's Details. */

import { $, el } from "./dom.js";
import { seconds } from "./format.js";
import { STRINGS } from "./strings.js";

let fetchedAt = 0; // performance.now() when the shown progress was received

/** The reason a provider attempt failed: "HTTP 502", "ReadTimeout" or both. */
function failureReason(event) {
  const parts = [];
  if (event.http_status !== null) parts.push(`HTTP ${event.http_status}`);
  if (event.error !== null) parts.push(event.error);
  return parts.join(" / ");
}

function retryText(event, maxAttempts) {
  const next = event.attempt + 1;
  return next > maxAttempts ? STRINGS.gaveUp(maxAttempts) : STRINGS.retrying(next, maxAttempts);
}

/** What the visitor reads for an attempt that is running or has failed; null if the line is more than text. */
function plainText(event, maxAttempts) {
  if (event.state === "failed") return STRINGS.providerFailed(failureReason(event), retryText(event, maxAttempts));
  const running = event.state === "running";
  if (event.phase === "cypher") return running ? STRINGS.writingQuery : codeOrText(event, STRINGS.queryEmpty);
  if (event.phase === "answer") return running ? STRINGS.writingAnswer : STRINGS.answerWritten;
  if (event.phase === "agent_step") {
    return running ? STRINGS.agentWaiting(event.action) : codeOrText(event, STRINGS.agentNoCall(event.action));
  }
  return running ? STRINGS.waitingForModel : STRINGS.modelReplied;
}

/** A finished step with nothing to quote is a plain sentence; with a query or tool call it is a code line (null). */
function codeOrText(event, emptyText) {
  return event.summary ? null : emptyText;
}

/** A finished query or agent step: its label, then the query or tool call in one line of monospace. */
function codeLine(event) {
  const head = event.phase === "cypher" ? STRINGS.queryWritten : STRINGS.agentAction(event.action);
  const code = el("code", { className: "timeline-code", textContent: event.summary ?? "" });
  code.title = event.summary ?? "";
  const nodes = [head, " · ", code];
  if (event.detail) nodes.push(el("span", { className: "timeline-detail", textContent: ` → ${event.detail}` }));
  return nodes;
}

/** The elapsed seconds: ticking for a running attempt (see `tickProgress`), fixed otherwise. */
function elapsedNode(event) {
  const node = el("span", { className: "timeline-time", textContent: seconds(event.elapsed_s) });
  if (event.state === "running") {
    node.classList.add("ticking");
    node.dataset.base = String(event.elapsed_s);
  }
  return node;
}

function timelineItem(event, maxAttempts) {
  const text = plainText(event, maxAttempts);
  const content = text === null ? codeLine(event) : [text];
  const item = el("li", { className: `timeline-item ${event.state}` });
  const mark = el("span", { className: "timeline-mark" });
  mark.setAttribute("aria-hidden", "true"); // a decoration: the state is in the words
  item.append(mark, el("span", { className: "timeline-text" }, ...content), elapsedNode(event));
  return item;
}

/** The lines of a progress object as a list (no live ticking unless an attempt is still running). */
export function timelineList(progress) {
  const items = progress.events.map((event) => timelineItem(event, progress.max_attempts));
  return el("ol", { className: "timeline" }, ...items);
}

/** Show the progress under the timer (replaces what was shown before). */
export function showProgress(progress) {
  fetchedAt = performance.now();
  if (progress === null || progress.events.length === 0) { clearProgress(); return; }
  $("ask-progress").replaceChildren(timelineList(progress));
}

/** Move the running attempt's counter on between polls. */
export function tickProgress() {
  const waited = (performance.now() - fetchedAt) / 1000;
  for (const node of $("ask-progress").querySelectorAll(".ticking")) {
    node.textContent = seconds(Number(node.dataset.base) + waited);
  }
}

/** Empty the timeline area. */
export function clearProgress() {
  $("ask-progress").replaceChildren();
}
