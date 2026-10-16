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
