/* The label table (labels.en.json): the one place codes from the server get their English text. */

import { ApiError } from "./api.js";
import { STRINGS } from "./strings.js";

let table = null;

/** Fetch the table once at start-up. */
export async function loadLabels() {
  const response = await fetch("/static/labels.en.json");
  if (!response.ok) throw new Error(`expected /static/labels.en.json, found HTTP ${response.status}`);
  table = await response.json();
}

/** The text of `code` in `section`; an unknown code is shown as it is, so nothing disappears. */
export function label(section, code) {
  return table?.[section]?.[code] ?? String(code);
}

/** The topic codes in the order the table lists them. */
export function topicOrder() {
  return Object.keys(table?.topics ?? {});
}

/** The visitor-facing text of any failure, plus the technical message to fold under it. */
export function describeError(error) {
  if (error instanceof ApiError && table?.error_codes?.[error.code]) {
    return { text: label("error_codes", error.code), technical: error.message };
  }
  return { text: STRINGS.unexpectedError, technical: String(error?.message ?? error) };
}
