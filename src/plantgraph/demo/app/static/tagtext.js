/* Finding item tags inside answer text. Pure functions: no DOM, no network.
   A tag is the label printed on a drawing for one piece of equipment, for example "P-151-1". */

function escapeRegex(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** One pattern for all tags: the longest first (so "P-151-1" wins over "P-151"), and only where the
    neighbours are not a letter or digit, or a hyphen joined to one (so "P-1" is not found inside
    "P-12" or "P-1-2"). */
function tagPattern(tags) {
  const longestFirst = [...tags].sort((a, b) => b.length - a.length).map(escapeRegex);
  const before = "(?<![A-Za-z0-9])(?<![A-Za-z0-9]-)";
  const after = "(?![A-Za-z0-9])(?!-[A-Za-z0-9])";
  return new RegExp(`${before}(?:${longestFirst.join("|")})${after}`, "g");
}

/** Cut `text` into pieces: `[{text, tag}]`, where `tag` is the matched tag or null for plain text. */
export function splitByTags(text, tags) {
  if (tags.length === 0 || text === "") return [{ text, tag: null }];
  const pieces = [];
  let from = 0;
  for (const match of text.matchAll(tagPattern(tags))) {
    if (match.index > from) pieces.push({ text: text.slice(from, match.index), tag: null });
    pieces.push({ text: match[0], tag: match[0] });
    from = match.index + match[0].length;
  }
  if (from < text.length) pieces.push({ text: text.slice(from), tag: null });
  return pieces;
}

/** Tag -> the sheets it is drawn on, from the answer's sheet list (the server already resolved them,
    in page order). A tag that is on no listed sheet is absent. */
export function sheetsByTag(answerSheets) {
  const byTag = new Map();
  for (const sheet of answerSheets) {
    for (const tag of sheet.tags) byTag.set(tag, [...(byTag.get(tag) ?? []), sheet]);
  }
  return byTag;
}
