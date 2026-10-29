"""Re-score round 3 under the line-view LOOPS_NEAR_ITEM gold (ADR-0061, "After tuning"). Free, offline.

Recomputes the references of the drawn LOOPS_NEAR_ITEM questions on T with the current generator,
re-scores the stored round-3 answers against them, and re-runs `tune-report` on the re-scored copies
(in a scratch directory; the round's own files are never touched). Prints the numbers as JSON.

    uv run python data/runs/exp0007/tune/rounds/r3/rescore_loops_near_item.py <scratch-dir>
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.harness.freeze import question_set_sha256
from plantgraph.qa.questions.families_dev2_local import loops_near_item_candidates
from plantgraph.qa.scoring import score_set

CORPUS = "X100g2s211"
TUNE = Path("data/runs/exp0007/tune")
RUNS = {"AG": "agent-v2t", "CYP-A": "cypher-v2t", "CYP-B": "cypher-v2t"}
FAMILY = "LOOPS_NEAR_ITEM"


def new_references() -> dict[str, list[str]]:
    """question_id -> reference under the line-view rule, for every candidate on T."""
    artifacts = load_corpus_artifacts(CORPUS, TUNE / "corpora" / CORPUS / "ingest.json")
    plant, manifest = artifacts.gold.plant, artifacts.gold.manifest
    assert plant is not None and manifest is not None
    candidates = loops_near_item_candidates(
        plant, manifest, artifacts.gold.sheets, corpus_id=CORPUS, seed=1
    )
    return {q.question_id: list(q.reference) for q in candidates if isinstance(q.reference, list)}


def rewrite_questions(
    scratch: Path, references: dict[str, list[str]]
) -> dict[str, tuple[list, list]]:
    """Write the drawn questions with new LOOPS_NEAR_ITEM references; return old/new per id."""
    changes: dict[str, tuple[list, list]] = {}
    lines = []
    for line in (TUNE / "questions" / CORPUS / "questions.jsonl").read_text("utf-8").splitlines():
        question = json.loads(line)
        if question["family"] == FAMILY:
            new = references[question["question_id"]]
            changes[question["question_id"]] = (question["reference"], new)
            question["reference"] = new
        lines.append(json.dumps(question, separators=(",", ":")))
    out = scratch / "questions" / CORPUS
    out.mkdir(parents=True, exist_ok=True)
    (out / "questions.jsonl").write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return changes


def rescore_run(
    run_id: str, scratch: Path, references: dict[str, list[str]]
) -> dict[str, list[bool]]:
    """Copy a run with `correct`/`f1` recomputed for LOOPS_NEAR_ITEM rows; return (old, new) verdicts."""
    src, dst = TUNE / "runs" / run_id, scratch / "runs" / run_id
    shutil.copytree(src, dst)
    verdicts: dict[str, list[bool]] = {}
    rows = []
    for line in (src / "answers.jsonl").read_text("utf-8").splitlines():
        row = json.loads(line)
        if f":{FAMILY}:" in row["question_id"]:
            answer = row["final_answer"]["answer"]
            score = score_set(
                references[row["question_id"]], answer if isinstance(answer, list) else []
            )
            verdicts[row["question_id"]] = [row["correct"], score.correct]
            if row["outcome"] == "ANSWERED" and not row["final_answer"]["not_present"]:
                row["correct"], row["f1"] = score.correct, score.f1
        rows.append(json.dumps(row, separators=(",", ":")))
    # the join refuses runs whose pinned question-file hash differs: pin the re-written file
    config = json.loads((dst / "run_config.json").read_text("utf-8"))
    config["question_set_sha256"] = question_set_sha256(
        [scratch / "questions" / CORPUS / "questions.jsonl"]
    )
    (dst / "run_config.json").write_text(json.dumps(config, indent=2), "utf-8")
    (dst / "answers.jsonl").write_bytes(("\n".join(rows) + "\n").encode("utf-8"))
    return verdicts


def tune_report(scratch: Path, setting: str) -> dict:
    cyp, ag = f"T7R3-CYP-{setting}-{CORPUS}", f"T7R3-AG-{CORPUS}"
    out = scratch / f"report_{setting}"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "plantgraph.qa.cascade",
            "tune-report",
            "--corpus",
            CORPUS,
            "--setting",
            setting,
            "--questions-root",
            str(scratch / "questions"),
            "--corpora-root",
            str(TUNE / "corpora"),
            "--run",
            f"cypher-v2t={scratch / 'runs' / cyp}",
            "--run",
            f"agent-v2t={scratch / 'runs' / ag}",
            "--out",
            str(out),
        ],
        check=True,
        capture_output=True,
    )
    return json.loads((out / "tune_report.json").read_text("utf-8"))


def main() -> None:
    scratch = Path(sys.argv[1])
    references = new_references()
    result: dict = {"references": rewrite_questions(scratch, references)}
    result["verdicts"] = {
        arm: rescore_run(f"T7R3-{arm}-{CORPUS}", scratch, references) for arm in RUNS
    }
    for setting in ("A", "B"):
        report = tune_report(scratch, setting)
        result[f"cascade_{setting}"] = {
            name: res["n_correct_uncut"] for name, res in report["results"].items()
        } | {"oracle": report["oracle_correct"]}
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
