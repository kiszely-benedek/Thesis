/* The page's whole mutable state, shared by the modules: what the server last said and what the
   visitor is doing. Modules read it and the entry module (app.js) re-renders after a change. */

export const page = {
  status: null,       // the last /api/status
  corpusId: null,     // the plant being viewed and asked about; null until one is held or chosen
  index: null,        // the drawing index of that plant (sheet id -> PDF page)
  questions: [],      // its example questions
  asking: false,      // a question is running
};

/** The status entry of the selected plant, or null. */
export function currentCorpus() {
  return page.status?.corpora.find((c) => c.corpus_id === page.corpusId) ?? null;
}

/** Whether the graph database holds the selected plant (not needed for a plant without a database step). */
export function plantAvailable(corpus) {
  const plant = page.status.plant;
  if (plant.loading) return false;
  return corpus.store?.kind === "not_needed" || plant.held.includes(corpus.corpus_id);
}

/** Whether a question can be asked right now. */
export function canAsk() {
  const corpus = currentCorpus();
  return !page.asking && Boolean(corpus) && corpus.state === "ready" && plantAvailable(corpus);
}
