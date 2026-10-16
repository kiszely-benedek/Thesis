/* Inline-SVG charts, no library: a line chart (linear or log axes, gaps, a vertical marker line, whiskers)
   and a grouped bar chart with whiskers. A chart is drawn at the width of its host element; the caller
   draws it again when that width changes. Colours are CSS variables (tokens.css), so a theme switch
   needs no redraw; each series also has its own marker shape, so colour is never the only cue. */

import { linePath, makeScale, markerPath } from "./chart_scale.js";
import { attachTip, enableArrowKeys } from "./chart_tip.js";
import { el } from "./dom.js";

const NS = "http://www.w3.org/2000/svg";
const MARKER_R = 5;
const HIT_R = 11;          // the invisible, larger target around a mark: easy to hover, tap and focus
const SERIES_SHIFT_PX = 4; // series sharing an x are drawn this far apart

function svgEl(tag, attrs = {}, ...children) {
  const node = document.createElementNS(NS, tag);
  for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, String(value));
  node.append(...children);
  return node;
}

/** The SVG for a host `width` px wide and `height` px high (1 SVG unit = 1 px, so text stays readable). */
function svgRoot(width, height, label) {
  return svgEl("svg", { width, height, viewBox: `0 0 ${width} ${height}`, role: "group", "aria-label": label });
}

/** The plot rectangle inside the svg, leaving room for tick labels and axis titles. */
function plotFrame(width, height) {
  return { left: 62, right: width - 14, top: 14, bottom: height - 50 };
}

/** One marker, drawn in the series colour with a thin halo in the surface colour. */
function markerShape(shape, cx, cy, color) {
  return svgEl("path", { d: markerPath(shape, cx, cy, MARKER_R), class: "shape", fill: color });
}

/** A focusable mark: the visible shape plus the invisible target; `tip` is the tooltip and screen-reader text. */
function markGroup(shapeNode, cx, cy, tip) {
  const hit = svgEl("circle", { cx, cy, r: HIT_R, class: "hit" });
  return svgEl("g", { class: "mark", role: "img", "aria-label": tip.replaceAll("\n", ". "), "data-tip": tip }, hit, shapeNode);
}

function axisText(x, y, text, attrs = {}) {
  return svgEl("text", { x, y, ...attrs }, text);
}

function drawYAxis(svg, frame, axis, sy) {
  for (const tick of axis.ticks) {
    const y = sy(tick);
    svg.append(svgEl("line", { x1: frame.left, x2: frame.right, y1: y, y2: y, class: "grid" }));
    svg.append(axisText(frame.left - 8, y + 4, axis.format(tick), { "text-anchor": "end" }));
  }
  const middle = (frame.top + frame.bottom) / 2;
  svg.append(axisText(14, middle, axis.label, { "text-anchor": "middle", transform: `rotate(-90 14 ${middle})`, class: "axis-title" }));
}

function drawXAxis(svg, frame, axis, sx) {
  svg.append(svgEl("line", { x1: frame.left, x2: frame.right, y1: frame.bottom, y2: frame.bottom, class: "axis" }));
  for (const tick of axis.ticks) {
    const x = sx(tick);
    svg.append(svgEl("line", { x1: x, x2: x, y1: frame.bottom, y2: frame.bottom + 5, class: "axis" }));
    svg.append(axisText(x, frame.bottom + 19, axis.format(tick), { "text-anchor": "middle" }));
  }
  const middle = (frame.left + frame.right) / 2;
  svg.append(axisText(middle, frame.bottom + 40, axis.label, { "text-anchor": "middle", class: "axis-title" }));
}

/** A dashed vertical line at `wall.x`; its label (one string per line) sits left of it, near the bottom. */
function drawWall(svg, frame, sx, wall) {
  const x = sx(wall.x);
  svg.append(svgEl("line", { x1: x, x2: x, y1: frame.top, y2: frame.bottom, class: "wall" }));
  (wall.label ?? []).forEach((line, i, lines) => {
    const y = frame.bottom - 8 - (lines.length - 1 - i) * 15;
    svg.append(axisText(x - 6, y, line, { "text-anchor": "end", class: "wall-label" }));
  });
}

/** A vertical whisker (the interval) with end caps, in the series colour. */
function whisker(x, yLow, yHigh, color) {
  const d = `M${x},${yLow}L${x},${yHigh}M${x - 3},${yLow}L${x + 3},${yLow}M${x - 3},${yHigh}L${x + 3},${yHigh}`;
  return svgEl("path", { d, class: "whisker", stroke: color });
}

function drawSeries(svg, series, index, count, sx, sy) {
  const dx = (index - (count - 1) / 2) * SERIES_SHIFT_PX;
  const layer = svgEl("g", { class: "series" });
  const dash = series.dash ? { "stroke-dasharray": series.dash } : {};
  layer.append(svgEl("path", { d: linePath(series.points, sx, sy, dx), class: "line", stroke: series.color, ...dash }));
  for (const point of series.points.filter((p) => p.y !== null)) {
    const [cx, cy] = [sx(point.x) + dx, sy(point.y)];
    if (point.low !== undefined) layer.append(whisker(cx, sy(point.low), sy(point.high), series.color));
    layer.append(markGroup(markerShape(series.marker, cx, cy, series.color), cx, cy, point.tip));
  }
  svg.append(layer);
}

/** Replace the chart's old svg in `host` (the tooltip element stays) and wire the tooltip and keys. */
function mount(host, svg) {
  host.querySelector("svg")?.remove();
  host.prepend(svg);
  if (!host.querySelector(".chart-tip")) attachTip(host);
  enableArrowKeys(svg);
}

/** Draw a line chart in `host`.
    spec: { height, label, x: {domain, ticks, format, label}, y: {domain, log, ticks, format, label},
            series: [{name, color, marker, dash?, points: [{x, y | null, low?, high?, tip}]}],
            wall?: {x, label?: [line, ...]} } */
export function lineChart(host, spec) {
  const width = host.clientWidth;
  if (width === 0) return; // the tab is hidden: the host's resize observer calls again once it is shown
  const frame = plotFrame(width, spec.height);
  const svg = svgRoot(width, spec.height, spec.label);
  const sx = makeScale(spec.x.domain, true, [frame.left, frame.right]);
  const sy = makeScale(spec.y.domain, spec.y.log === true, [frame.bottom, frame.top]);
  drawYAxis(svg, frame, spec.y, sy);
  drawXAxis(svg, frame, spec.x, sx);
  if (spec.wall) drawWall(svg, frame, sx, spec.wall);
  spec.series.forEach((series, i) => drawSeries(svg, series, i, spec.series.length, sx, sy));
  mount(host, svg);
}

function drawBar(svg, frame, sy, bar, left, barWidth, format) {
  const top = sy(bar.value);
  const rect = svgEl("rect", { x: left, y: top, width: barWidth, height: frame.bottom - top, class: "bar-rect", fill: bar.color });
  const centre = left + barWidth / 2;
  const group = markGroup(rect, centre, top, bar.tip);
  group.firstChild.setAttribute("r", Math.max(HIT_R, barWidth / 2)); // the hit area covers the bar's top
  svg.append(group);
  svg.append(whisker(centre, sy(bar.low), sy(bar.high), "var(--ink)"));
  svg.append(axisText(centre, sy(bar.high) - 6, format(bar.value), { "text-anchor": "middle", class: "bar-value" }));
}

function drawGroup(svg, frame, sy, group, left, groupWidth, format) {
  const barWidth = Math.min(46, (groupWidth * 0.8) / group.bars.length);
  const used = barWidth * group.bars.length;
  const start = left + (groupWidth - used) / 2;
  group.bars.forEach((bar, i) => drawBar(svg, frame, sy, bar, start + i * barWidth, barWidth * 0.86, format));
  svg.append(axisText(left + groupWidth / 2, frame.bottom + 19, group.label, { "text-anchor": "middle" }));
}

/** Draw a grouped bar chart in `host`.
    spec: { height, label, y: {domain, ticks, format, label},
            groups: [{label, bars: [{value, low, high, color, tip}]}] } */
export function barChart(host, spec) {
  const width = host.clientWidth;
  if (width === 0) return;
  const frame = plotFrame(width, spec.height);
  const svg = svgRoot(width, spec.height, spec.label);
  const sy = makeScale(spec.y.domain, false, [frame.bottom, frame.top]);
  drawYAxis(svg, frame, spec.y, sy);
  svg.append(svgEl("line", { x1: frame.left, x2: frame.right, y1: frame.bottom, y2: frame.bottom, class: "axis" }));
  const groupWidth = (frame.right - frame.left) / spec.groups.length;
  spec.groups.forEach((group, i) => drawGroup(svg, frame, sy, group, frame.left + i * groupWidth, groupWidth, spec.y.format));
  mount(host, svg);
}

/** A legend row: a swatch (the series' marker, or a plain square for bars) and its name. */
export function legend(items) {
  const entries = items.map((item) => {
    const swatch = svgEl("svg", { width: 18, height: 18, viewBox: "0 0 18 18", "aria-hidden": "true" });
    swatch.append(svgEl("path", { d: markerPath(item.marker, 9, 9, 5), fill: item.color }));
    return el("li", {}, swatch, el("span", {}, item.name));
  });
  return el("ul", { className: "legend" }, ...entries);
}
