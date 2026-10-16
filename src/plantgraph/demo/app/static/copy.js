/* A "Copy" button for a block of text (the Cypher query). */

import { el } from "./dom.js";
import { STRINGS } from "./strings.js";

const RESET_MS = 2000;

/** A button that writes `text` to the clipboard and says so for two seconds. */
export function copyButton(text) {
  const button = el("button", { type: "button", className: "text-button copy-button", textContent: STRINGS.copy });
  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(text); // 127.0.0.1 counts as a secure context
      button.textContent = STRINGS.copied;
    } catch {
      button.textContent = STRINGS.copyFailed;
    }
    setTimeout(() => { button.textContent = STRINGS.copy; }, RESET_MS);
  });
  return button;
}
