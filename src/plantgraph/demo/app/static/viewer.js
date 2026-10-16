/* The drawing set in the browser's own PDF viewer, and the jump to a sheet. */

import { $, el } from "./dom.js";
import { page } from "./state.js";
import { STRINGS } from "./strings.js";

/** Show page `pageNumber` of the plant's PDF. A fresh iframe each time: a hash-only change on an
    open PDF viewer does not reliably move the page in every browser. */
export function showPdf(corpusId, pageNumber) {
  const frame = el("iframe", { title: STRINGS.pdfTitle });
  frame.src = `/corpora/${encodeURIComponent(corpusId)}/drawings.pdf#page=${pageNumber}`;
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

function goToDrawing() {
  const id = $("dwg-input").value.trim().replace(/^DWG\s*/i, "");
  const message = $("dwg-message");
  message.textContent = "";
  if (!page.index) { message.textContent = STRINGS.dwgNoIndex; return; }
  const target = page.index.pages[id];
  if (target === undefined) { message.textContent = STRINGS.dwgUnknown(id); return; }
  jumpToPage(target);
}

/** Wire the "Go to sheet" box. */
export function initViewer() {
  $("dwg-label").textContent = STRINGS.dwgLabel;
  $("dwg-go").textContent = STRINGS.dwgGo;
  $("dwg-go").addEventListener("click", goToDrawing);
  $("dwg-input").addEventListener("keydown", (e) => { if (e.key === "Enter") goToDrawing(); });
}
