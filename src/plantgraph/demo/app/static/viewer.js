/* The drawing set in the browser's own PDF viewer, and the jump to a sheet. */

import { $, el } from "./dom.js";
import { page } from "./state.js";
import { STRINGS } from "./strings.js";

/** One stamp per page load. It is the `?v=` of every PDF URL, so the URL is stable while the page
    lives (the browser keeps the PDF in its cache, a jump never re-downloads it) and new after a
    reload (a regenerated PDF is never served stale). */
const PDF_VERSION = Date.now().toString(36);

/** The plant's PDF address, opened at `pageNumber`. */
export function pdfUrl(corpusId, pageNumber) {
  const base = `/corpora/${encodeURIComponent(corpusId)}/drawings.pdf?v=${PDF_VERSION}`;
  return `${base}#page=${pageNumber}`;
}

/** Show page `pageNumber` of the plant's PDF in a fresh iframe.
    Measured in headless Edge and Chrome (DP-T8): changing only the `#page=N` of an open viewer
    does not move it (it stayed on page 1 for every jump), and an unchanged address does nothing at
    all. A new iframe always opens at the asked page, and the cached PDF makes that cheap. */
export function showPdf(corpusId, pageNumber) {
  const frame = el("iframe", { title: STRINGS.pdfTitle });
  frame.src = pdfUrl(corpusId, pageNumber);
  $("pdf-host").replaceChildren(frame);
}

/** Empty the viewer (no plant selected). */
export function clearPdf() {
  $("pdf-host").replaceChildren();
}

/** Jump the viewer to a PDF page of the selected plant. */
export function jumpToPage(pageNumber) {
  if (page.corpusId !== null) showPdf(page.corpusId, pageNumber);
}
