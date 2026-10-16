/* The route view's toolbar: step back / forward, Play, a slider over the steps, the answer-path toggle
   and the zoom buttons. The current step lives in the shared `sync` (step_sync.js), not here. */

import { el } from "./dom.js";
import { STRINGS } from "./strings.js";

const PLAY_INTERVAL_MS = 1000;

function iconButton(text, ariaLabel, onClick) {
  const button = el("button", { type: "button", className: "icon-button", textContent: text });
  button.setAttribute("aria-label", ariaLabel);
  button.addEventListener("click", onClick);
  return button;
}

/** Under prefers-reduced-motion nothing may advance by itself, so Play is not offered. */
function reducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function textButton(text, onClick) {
  const button = el("button", { type: "button", className: "text-button", textContent: text });
  button.addEventListener("click", onClick);
  return button;
}

/** Play: one step per second from the current one (from the start when already at the end). */
function playControl(sync, last, button) {
  let timer = null;
  const stop = () => {
    clearInterval(timer);
    timer = null;
    button.textContent = STRINGS.routePlay;
  };
  const tick = () => {
    // the card may have been replaced by a newer answer: stop instead of ticking on a detached view
    if (!button.isConnected || sync.current >= last) return stop();
    sync.select(sync.current + 1);
    if (sync.current >= last) stop();
  };
  button.addEventListener("click", () => {
    if (timer !== null) return stop();
    if (sync.current >= last) sync.select(0);
    button.textContent = STRINGS.routePause;
    timer = setInterval(tick, PLAY_INTERVAL_MS);
  });
  return stop;
}

function stepRow(steps, sync) {
  const last = steps.length - 1;
  let locked = false;
  const label = el("span", { className: "route-step-label" });
  label.setAttribute("aria-live", "polite");
  const previous = iconButton("◀", STRINGS.routePrevious, () => sync.select(sync.current - 1));
  const next = iconButton("▶", STRINGS.routeNext, () => sync.select(sync.current + 1));
  const slider = el("input", { type: "range", min: 0, max: last, step: 1, className: "route-slider" });
  slider.setAttribute("aria-label", STRINGS.routeSlider);
  slider.addEventListener("input", () => sync.select(Number(slider.value)));
  const play = textButton(STRINGS.routePlay, () => {});
  const controls = [previous, next, slider];
  let stopPlay = () => {};
  if (!reducedMotion()) {
    stopPlay = playControl(sync, last, play);
    controls.push(play);
  }
  const show = (index) => {
    label.textContent = STRINGS.routeStepLabel(index + 1, steps.length, steps[index]);
    slider.value = index;
    previous.disabled = locked || index <= 0;
    next.disabled = locked || index >= last;
    slider.disabled = locked;
    play.disabled = locked;
  };
  sync.onChange(show);
  show(sync.current);
  const lock = (on) => {
    locked = on;
    if (on) stopPlay();
    show(sync.current);
  };
  return { row: el("div", { className: "route-bar" }, ...controls, label), lock };
}

/** The toolbar. `view` gives it `onPath(on)`, `onZoom(kind)`; returns its node and `setPathMode(on)`. */
export function routeControls({ steps, sync, hasPath, view }) {
  // a one-step route (a database query alone) has nothing to step through: just name the step
  const stepping = steps.length > 1;
  const stepBar = stepping ? stepRow(steps, sync) : null;
  const rows = [];
  if (stepBar) rows.push(stepBar.row);
  else rows.push(el("p", { className: "route-step-label", textContent: steps[0] ?? STRINGS.routeNoSteps }));
  const tools = el("div", { className: "route-bar" });
  let pathButton = null;
  if (hasPath) {
    pathButton = textButton(STRINGS.routePathToggle, () => view.onPath(pathButton.getAttribute("aria-pressed") !== "true"));
    pathButton.setAttribute("aria-pressed", "false");
    tools.append(pathButton);
  }
  tools.append(
    iconButton("−", STRINGS.routeZoomOut, () => view.onZoom("out")),
    iconButton("+", STRINGS.routeZoomIn, () => view.onZoom("in")),
    textButton(STRINGS.routeFit, () => view.onZoom("fit")),
  );
  rows.push(tools);
  return {
    node: el("div", { className: "route-controls" }, ...rows),
    setPathMode(on) {
      pathButton?.setAttribute("aria-pressed", String(on));
      // in the path layout every step is already shown, so stepping would change nothing
      stepBar?.lock(on);
    },
  };
}
