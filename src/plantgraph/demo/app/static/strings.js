"use strict";
/* The page's user-facing text (Hungarian), loaded before app.js. */

function usd(x) { return `$${Number(x).toFixed(5)}`; }

// All user-facing text (Hungarian) lives here. Drawing labels stay English: they come from the data.
const STRINGS = {
  title: "Üzemléptékű P&ID kérdezés",
  dwgLabel: "Ugrás a rajzra: DWG",
  dwgGo: "Ugrás",
  dwgUnknown: (id) => `Nincs ilyen rajz ebben a korpuszban: ${id}`,
  dwgNoIndex: "A rajzindex még nem érhető el.",
  corpus: "Korpusz",
  benchmark: "Benchmark-kérdés",
  ownQuestion: "— saját kérdés —",
  question: "Kérdés (szabad szöveg)",
  answerType: "Válasz formája",
  ask: "Kérdezés",
  stateLabels: { waiting: "vár a betöltésre", loading: "betöltés…", ready: "kész", error: "hiba" },
  noPdf: "nincs rajz-PDF",
  noTier1: "az adatbázis-szint nem elérhető, csak a 2. szint válaszol",
  paidOff: "Csak gyorsítótár (fizetős hívás tiltva)",
  spend: (spent, cap) => `Munkamenet költése: ${spent} / limit ${cap}`,
  running: "Fut…",
  elapsed: (s) => `${s.toFixed(1)} s`,
  needsPaidOff:
    "Ehhez a kérdéshez nincs gyorsítótárazott válasz, a szerver pedig csak visszajátszó módban fut. " +
    "Fizetős hívásokhoz indítsd újra a szervert --allow-paid-calls és --session-cap-usd kapcsolóval.",
  paidTitle: "Fizetős kérdés",
  paidIntro: (tier) => `A(z) „${tier}” szint válasza nincs a gyorsítótárban; az élő hívás pénzbe kerül.`,
  paidEstimateHead: "Becsült költség szintenként (kérdésenként)",
  paidTierRow: (tier, st) =>
    `${tier}: medián ${usd(st.median_usd)}, max ${usd(st.max_usd)} (${st.n_questions} kérdés` +
    `${st.other_corpus ? ", másik korpuszból" : ""})`,
  paidReservation: (r) => `Foglalás ehhez a kérdéshez: ${usd(r)}`,
  paidCancel: "Mégse",
  paidConfirm: "Élő kérdezés",
  answer: "Válasz",
  noAnswer: "(nincs válasz)",
  notPresent: "A rendszer szerint az információ nincs a rajzokon.",
  notice: (policy, text) => `Nem az értékelt szabály fut (${policy}). ${text ?? ""}`,
  outcome: "Kimenet",
  answeredBy: "Válaszolt",
  nobody: "senki (a kérdés nem járt sikerrel)",
  fellBack: "visszaesés: egyik szint sem lett elfogadva, az első szint válaszát adjuk",
  latency: "Késleltetés (kaszkád-definíció)",
  wall: "Valós idő",
  cost: "Költség",
  fromCache: (cost) => `${usd(cost)} (gyorsítótárból, most nem költöttünk)`,
  paid: (cost, spent) => `${usd(cost)}, ebből most fizetve ${usd(spent)}`,
  tierTable: "Szintenként",
  tierCols: ["Szint", "Kimenet", "Elfogadva", "Késl.", "Költség", "Hívás", "Cache", "Lépés", "Leállás", "Sor"],
  yes: "igen",
  no: "nem",
  answerSheets: "A válasz rajzai",
  readSheets: "Az ügynök által olvasott rajzok",
  goldSheets: "Referencia-bizonyíték (rajzok)",
  none: "—",
  reference: "Referencia-válasz",
  verdict: "Értékelés",
  correct: "helyes",
  incorrect: "helytelen",
  crossSheet: (b) =>
    `k = ${b.k ?? "?"} (összekötő: ${b.k_connector ?? "?"}, azonosság: ${b.k_identity ?? "?"}), u = ${b.u ?? "?"}`,
  answerTypes: {
    FREE_TEXT: "szabad szöveg", CLASS_NAME: "osztálynév", UNIT_ID: "egység azonosító",
    TAG: "jelölés (tag)", TAG_SET: "jelölések halmaza", UNIT_SET: "egységek halmaza",
    SHEET_SET: "rajzok halmaza", TAG_PATH: "jelölés-útvonal", COUNT: "darabszám", BOOLEAN: "igen/nem",
  },
};
