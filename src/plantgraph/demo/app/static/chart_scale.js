/* The arithmetic of the charts: scales, tick positions and line paths. Pure functions, no DOM,
   so charts.js only has to draw what these return. */

/** A function from a data value to a pixel position; `log` axes space values by their logarithm. */
export function makeScale(domain, log, [from, to]) {
  const [low, high] = log ? domain.map(Math.log) : domain;
  return (value) => from + (((log ? Math.log(value) : value) - low) / (high - low)) * (to - from);
}

/** About five round tick values from 0 up to and including `max` (steps of 1, 2 or 5 times a power of ten). */
export function niceTicks(max) {
  const rough = max / 5;
  const power = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 5, 10].map((m) => m * power).find((s) => s >= rough);
  const ticks = [];
  for (let value = 0; value < max + step * 0.999; value += step) ticks.push(Number(value.toFixed(12)));
  return ticks;
}

/** The decade (power of ten) domain around positive values, e.g. 0.0004 .. 0.025 -> [0.0001, 0.1]. */
export function decadeDomain(values) {
  const low = Math.floor(Math.log10(Math.min(...values)));
  const high = Math.ceil(Math.log10(Math.max(...values)));
  return [10 ** low, 10 ** high];
}

/** Every power of ten inside a decade domain (the tick values of a log axis). */
export function decadeTicks([low, high]) {
  const ticks = [];
  for (let power = Math.round(Math.log10(low)); power <= Math.round(Math.log10(high)); power += 1) {
    ticks.push(10 ** power);
  }
  return ticks;
}

/** The "d" attribute of a line through points; a point with `y === null` breaks the line (a gap).
    `dx` shifts the whole series sideways, so series sharing an x do not hide each other. */
export function linePath(points, sx, sy, dx = 0) {
  let pen = "M"; // "M" lifts the pen: the first point after a gap starts a new piece
  let path = "";
  for (const point of points) {
    if (point.y === null) { pen = "M"; continue; }
    path += `${pen}${(sx(point.x) + dx).toFixed(1)},${sy(point.y).toFixed(1)}`;
    pen = "L";
  }
  return path;
}

/** The path "d" of a marker shape centred on (cx, cy) with half-size r (the circle is drawn as an arc pair). */
export function markerPath(shape, cx, cy, r) {
  const at = (dx, dy) => `${(cx + dx).toFixed(1)},${(cy + dy).toFixed(1)}`;
  const shapes = {
    circle: `M${at(-r, 0)}a${r},${r} 0 1,0 ${2 * r},0a${r},${r} 0 1,0 ${-2 * r},0Z`,
    square: `M${at(-r, -r)}L${at(r, -r)}L${at(r, r)}L${at(-r, r)}Z`,
    diamond: `M${at(0, -r * 1.3)}L${at(r * 1.3, 0)}L${at(0, r * 1.3)}L${at(-r * 1.3, 0)}Z`,
    triangle: `M${at(0, -r * 1.2)}L${at(r * 1.2, r)}L${at(-r * 1.2, r)}Z`,
    "triangle-down": `M${at(0, r * 1.2)}L${at(r * 1.2, -r)}L${at(-r * 1.2, -r)}Z`,
  };
  if (!(shape in shapes)) throw new Error(`expected a marker shape in ${Object.keys(shapes)}, found "${shape}"`);
  return shapes[shape];
}
