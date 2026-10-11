"""Blind review of EX01 answers and the tally of the verdicts (design §11 E-T1, ADR-0054 point 6).

EX01's answers are free text, so a person marks them against `ex01_checklist.json`. To keep the
reviewer from favouring an arm, the sheet shows answers in a shuffled order behind opaque ids
(`B001`...) with no arm or repeat; the secret behind each id is kept in a separate key file. The
tag check printed beside each answer is advisory: the verdict is the reviewer's.

    ex01-review  ->  ex01_blind_sheet.md (for the reviewer) + ex01_blind_key.json (hidden)
    ex01-tally   <-  ex01_verdicts.json (the reviewer's list of `Ex01Verdict`)  ->  correct / 5
"""

from __future__ import annotations

import random
from pathlib import Path

from pydantic import TypeAdapter

from plantgraph.qa.exp0001.ex01_arms import ARM_DEFINITIONS
from plantgraph.qa.exp0001.ex01_models import (
    CASCADE_ARM,
    BlindKeyEntry,
    Ex01AnswerRow,
    Ex01ChecklistItem,
    Ex01Verdict,
)
from plantgraph.qa.exp0001.ex01_tags import check_tags

#: Seed of the answer shuffle (design §11).
BLIND_SEED = 20261101
SHEET_NAME = "ex01_blind_sheet.md"
KEY_NAME = "ex01_blind_key.json"
VERDICTS_NAME = "ex01_verdicts.json"

_CHECKLIST = TypeAdapter(list[Ex01ChecklistItem])
_KEY = TypeAdapter(list[BlindKeyEntry])
_VERDICTS = TypeAdapter(list[Ex01Verdict])


def load_checklist(path: Path) -> dict[str, Ex01ChecklistItem]:
    """The checklist by question id.

    Raises:
        ValueError: two items share a question id.
    """
    items = _CHECKLIST.validate_json(path.read_text(encoding="utf-8"))
    by_qid = {item.qid: item for item in items}
    if len(by_qid) != len(items):
        raise ValueError(f"expected each qid once in {path}, found repeats")
    return by_qid


def shuffled_rows(rows: list[Ex01AnswerRow], seed: int = BLIND_SEED) -> list[Ex01AnswerRow]:
    """The rows in a seeded random order (sorted first, so the file order does not matter)."""
    ordered = sorted(rows, key=lambda row: (row.arm, row.qid, row.repeat))
    random.Random(seed).shuffle(ordered)
    return ordered


def build_key(
    rows: list[Ex01AnswerRow], checklist: dict[str, Ex01ChecklistItem]
) -> list[BlindKeyEntry]:
    """One key entry per row, in shuffled order, with ids `B001`... and the tag check.

    Raises:
        ValueError: a row's question has no checklist item.
    """
    entries: list[BlindKeyEntry] = []
    for number, row in enumerate(shuffled_rows(rows), start=1):
        item = checklist.get(row.qid)
        if item is None:
            raise ValueError(
                f"expected a checklist item for {row.qid!r}, found {sorted(checklist)}"
            )
        hits = None if row.answer_text is None else check_tags(row.answer_text, item)
        entries.append(
            BlindKeyEntry(
                blind_id=f"B{number:03d}",
                qid=row.qid,
                arm=row.arm,
                repeat=row.repeat,
                no_answer=row.answer_text is None,
                tag_hits=hits,
            )
        )
    return entries


def render_sheet(
    entries: list[BlindKeyEntry],
    rows: list[Ex01AnswerRow],
    checklist: dict[str, Ex01ChecklistItem],
    question_text: dict[str, str],
) -> str:
    """The markdown the reviewer reads: question, answer, checklist and tag check per blind id."""
    answers = {(row.arm, row.qid, row.repeat): row.answer_text for row in rows}
    blocks = ["# EX01 blind review sheet", "", f"Answers shuffled with seed {BLIND_SEED}.", ""]
    for entry in entries:
        text = answers[(entry.arm, entry.qid, entry.repeat)]
        if text is not None:  # an item without an answer is counted wrong without being shown
            blocks.append(_render_entry(entry, text, checklist[entry.qid], question_text))
    return "\n".join(blocks)


def _render_entry(
    entry: BlindKeyEntry, text: str, item: Ex01ChecklistItem, question_text: dict[str, str]
) -> str:
    hits = entry.tag_hits
    if hits is None:
        raise ValueError(f"expected a tag check for the answered item {entry.blind_id}, found none")
    quoted = "\n".join("> " + line for line in text.splitlines()) or "> "
    order = "n/a" if hits.order_ok is None else ("yes" if hits.order_ok else "NO")
    lines = [
        f"## {entry.blind_id} ({entry.qid})",
        f"**Question:** {question_text[entry.qid]}",
        "",
        quoted,
        "",
        f"- required tags found: {_join(hits.found)}; missing: {_join(hits.missing)}",
        f"- forbidden tags mentioned: {_join(hits.forbidden_present)}; in order: {order}",
    ]
    lines += [f"- required statement: {statement}" for statement in item.required_statements]
    return "\n".join([*lines, ""])


def _join(tags: list[str]) -> str:
    return ", ".join(tags) or "-"


def write_review(
    out_dir: Path, rows: list[Ex01AnswerRow], checklist_path: Path, question_text: dict[str, str]
) -> tuple[Path, Path]:
    """Write the blind sheet and its key into `out_dir`; returns both paths."""
    checklist = load_checklist(checklist_path)
    entries = build_key(rows, checklist)
    sheet_path, key_path = out_dir / SHEET_NAME, out_dir / KEY_NAME
    sheet_path.write_text(render_sheet(entries, rows, checklist, question_text), encoding="utf-8")
    key_path.write_bytes(_KEY.dump_json(entries, indent=2))
    return sheet_path, key_path


def load_verdicts(path: Path) -> list[Ex01Verdict]:
    """The reviewer's verdict file."""
    return _VERDICTS.validate_json(path.read_text(encoding="utf-8"))


def load_key(path: Path) -> list[BlindKeyEntry]:
    """The key file written by `write_review`."""
    return _KEY.validate_json(path.read_text(encoding="utf-8"))


def tally(
    key: list[BlindKeyEntry], verdicts: list[Ex01Verdict]
) -> dict[str, dict[int, tuple[int, int]]]:
    """Per arm and repeat: (correct, asked). An item with no answer is wrong without a verdict.

    Raises:
        ValueError: a verdict names an unknown blind id or the wrong question, or an answered
            item has no verdict (the list of missing ids is in the message).
    """
    by_id = {verdict.blind_id: verdict for verdict in verdicts}
    _check_verdicts(key, by_id)
    counts: dict[str, dict[int, tuple[int, int]]] = {}
    for entry in key:
        verdict = by_id.get(entry.blind_id)
        correct = verdict is not None and verdict.verdict == "correct"
        right, asked = counts.setdefault(entry.arm, {}).get(entry.repeat, (0, 0))
        counts[entry.arm][entry.repeat] = (right + correct, asked + 1)
    return counts


def _check_verdicts(key: list[BlindKeyEntry], by_id: dict[str, Ex01Verdict]) -> None:
    known = {entry.blind_id: entry for entry in key}
    unknown = sorted(set(by_id) - set(known))
    if unknown:
        raise ValueError(f"expected verdicts only for blind ids in the key, found {unknown}")
    wrong_question = [i for i, v in by_id.items() if v.qid != known[i].qid]
    if wrong_question:
        raise ValueError(
            f"expected each verdict's qid to match the key, found mismatch: {wrong_question}"
        )
    missing = [e.blind_id for e in key if not e.no_answer and e.blind_id not in by_id]
    if missing:
        raise ValueError(f"expected a verdict for every answered item, missing: {missing}")


def render_tally(counts: dict[str, dict[int, tuple[int, int]]]) -> str:
    """A markdown table: one row per arm, one column per repeat, cells `correct / asked`."""
    repeats = sorted({repeat for by_repeat in counts.values() for repeat in by_repeat})
    header = "| arm | " + " | ".join(f"repeat {r}" for r in repeats) + " |"
    lines = [header, "|" + "---|" * (len(repeats) + 1)]
    for arm in [*ARM_DEFINITIONS, CASCADE_ARM]:
        if arm in counts:
            cells = [_cell(counts[arm].get(r)) for r in repeats]
            lines.append(f"| {arm} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _cell(count: tuple[int, int] | None) -> str:
    return "-" if count is None else f"{count[0]} / {count[1]}"
