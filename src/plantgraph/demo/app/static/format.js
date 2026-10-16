/* Pure formatting helpers: no DOM, no network. */

const USD_FORMAT = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const USD_SMALL_FORMAT = new Intl.NumberFormat("en-US", {
  style: "currency", currency: "USD", maximumSignificantDigits: 2,
});

/** 0 -> "$0"; from one cent up "$2.00"; below that two significant digits, e.g. "$0.00071". */
export function usd(amount) {
  const value = Number(amount);
  if (value === 0) return "$0";
  return value >= 0.01 ? USD_FORMAT.format(value) : USD_SMALL_FORMAT.format(value);
}

/** Seconds with one decimal, e.g. "4.3 s". */
export function seconds(value) {
  return `${Number(value).toFixed(1)} s`;
}

/** An answer value (text, number, list or null) as one display string. */
export function valueText(value) {
  if (value === null || value === undefined) return "";
  return Array.isArray(value) ? value.join(", ") : String(value);
}

/** Replace `{name}` placeholders in a label with the given values. */
export function fillTemplate(text, values) {
  return text.replace(/\{(\w+)\}/g, (whole, name) => values[name] ?? whole);
}

/** "3 rows", "1 row" (a count that is not known, shown as "?", takes the plural). */
export function count(n, singular, plural = `${singular}s`) {
  return `${n} ${n === 1 ? singular : plural}`;
}

/** A plant class in plain words plus the system's own name, e.g. "centrifugal pump (CentrifugalPump)".
    `names` is the label table's class_names; an unknown class is returned as it is (and logged). */
export function className(code, names) {
  if (!(code in names)) {
    console.warn(`expected a plain name for the class "${code}" in labels.en.json, found none`);
    return code;
  }
  return `${names[code]} (${code})`;
}

/** An answer value with every plant class name in it spelled out; other text stays as it is. */
export function valueWithClasses(value, names) {
  const spell = (item) => (typeof item === "string" && item in names ? className(item, names) : item);
  return valueText(Array.isArray(value) ? value.map(spell) : spell(value));
}

/** One value of a result row (a database cell) as text: lists joined, nested objects as JSON. */
export function cellText(value) {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.map(cellText).join(", ");
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

/** The column names of a set of result rows, in the order they first appear. */
export function columnsOf(rows) {
  return [...new Set(rows.flatMap((row) => Object.keys(row)))];
}
