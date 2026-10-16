/* What makes a chart's marks usable without a mouse: one tooltip per chart that opens on hover,
   focus or tap, and arrow-key movement from mark to mark (one Tab stop per chart, not one per mark). */

import { el } from "./dom.js";

const TIP_GAP_PX = 10;
const KEY_STEP = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };

/** The mark (an element carrying `data-tip`) an event happened on, or null. */
function markOf(event) {
  return event.target instanceof Element ? event.target.closest("[data-tip]") : null;
}

/** Put the tooltip above the mark (below when there is no room), kept inside the chart's width. */
function place(tip, host, mark) {
  const hostBox = host.getBoundingClientRect();
  const markBox = mark.getBoundingClientRect();
  const centre = markBox.left + markBox.width / 2 - hostBox.left;
  const left = Math.max(0, Math.min(centre - tip.offsetWidth / 2, host.clientWidth - tip.offsetWidth));
  const above = markBox.top - hostBox.top - TIP_GAP_PX - tip.offsetHeight;
  const top = above >= 0 ? above : markBox.bottom - hostBox.top + TIP_GAP_PX;
  tip.style.left = `${left}px`;
  tip.style.top = `${top}px`;
}

/** Give a chart host its tooltip (once); the marks' `data-tip` text is what it shows. */
export function attachTip(host) {
  const tip = el("div", { className: "chart-tip", role: "tooltip" });
  host.append(tip);
  const show = (mark) => {
    tip.textContent = mark.dataset.tip;
    tip.classList.add("shown");
    place(tip, host, mark);
  };
  const hide = () => tip.classList.remove("shown");
  host.addEventListener("pointerover", (event) => { const mark = markOf(event); if (mark) show(mark); });
  host.addEventListener("pointerout", (event) => { if (event.pointerType === "mouse") hide(); });
  host.addEventListener("focusin", (event) => { const mark = markOf(event); if (mark) show(mark); });
  host.addEventListener("focusout", hide);
  host.addEventListener("keydown", (event) => { if (event.key === "Escape") hide(); });
  host.addEventListener("click", (event) => { const mark = markOf(event); if (mark) show(mark); else hide(); });
}

/** Where a key sends the focus: the same index when the key does nothing here or the end is reached. */
function targetIndex(key, current, last) {
  if (key === "Home") return 0;
  if (key === "End") return last;
  const moved = current + (KEY_STEP[key] ?? 0);
  return Math.max(0, Math.min(last, moved));
}

/** Arrow keys, Home and End move focus along the marks of `svg`, in drawing order (series by series). */
export function enableArrowKeys(svg) {
  const marks = [...svg.querySelectorAll(".mark")];
  marks.forEach((mark, i) => { mark.tabIndex = i === 0 ? 0 : -1; }); // roving tabindex
  svg.addEventListener("keydown", (event) => {
    const current = marks.indexOf(event.target);
    if (current < 0) return;
    const next = targetIndex(event.key, current, marks.length - 1);
    if (next === current) return;
    event.preventDefault();
    marks[current].tabIndex = -1;
    marks[next].tabIndex = 0;
    marks[next].focus();
  });
}
