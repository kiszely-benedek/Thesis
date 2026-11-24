"""The readiness checklist before EXP-0009's P0, as far as a program can check it (§19.7, §19.13).

    python -m plantgraph.qa.exp0009.readiness [--prereg-only] [--smoke-passed FILE] [--no-neo4j]

EXP-0008's readiness items (`qa/exp0008/readiness.py`) are reused where they are not about E9's
paths: disk, balance, power, Neo4j. What differs is part A: it must hold no `<<FILL` marker, name
its code commit, agree with the drawn plan, and be **committed** (clean in git). Nothing here
starts a stage, writes a file or makes a paid call.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
from collections.abc import Sequence
from pathlib import Path

from plantgraph.qa.exp0008 import balance
from plantgraph.qa.exp0008.freeze import FreezeRefused, check_clean
from plantgraph.qa.exp0008.readiness import (
    Check,
    check_balance,
    check_disk,
    check_neo4j,
    check_neo4j_home,
    check_power,
    hand_checks,
    neo4j_database_names,
)
from plantgraph.qa.exp0009.freeze import named_head

PREREG = Path("data/runs/exp0009/prereg")
FROZEN_PATHS = (
    "src", ":!src/plantgraph/demo", "scripts/audit_export_subgraphs.py",
    "data/runs/exp0009/run_all.sh", "data/runs/exp0009/lib.sh", "data/runs/exp0009/lib_plants.sh",
    "data/runs/exp0009/lib_runs.sh", "data/runs/exp0009/stages", "data/runs/exp0009/inputs",
)  # fmt: skip
PREREG_FILES = ("PREREG_A.md", "seeds.json", "plan.json", "position_prior.json")


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False)  # noqa: S603, S607


def check_prereg_a(prereg: Path = PREREG) -> Check:
    """Part A is there, filled in, names a commit, agrees with the plan, and is committed."""
    item = "PREREG_A.md filled, consistent and committed"
    missing = [n for n in PREREG_FILES if not (prereg / n).is_file()]
    if missing:
        return Check(item=item, status="FAIL", detail=f"missing in {prereg}: {missing}")
    text = (prereg / "PREREG_A.md").read_text(encoding="utf-8")
    problems = []
    if "<<FILL" in text:
        problems.append("a <<FILL ...>> marker is still in the text")
    try:
        named_head(text)
    except FreezeRefused as error:
        problems.append(str(error))
    prior = hashlib.sha256((prereg / "position_prior.json").read_bytes()).hexdigest()
    if prior not in (prereg / "plan.json").read_text(encoding="utf-8"):
        problems.append("plan.json does not hold the sha256 of position_prior.json")
    problems += _uncommitted(prereg)
    return Check(item=item, status="FAIL" if problems else "OK", detail="; ".join(problems) or "ok")


def _uncommitted(prereg: Path) -> list[str]:
    files = [str(prereg / n) for n in PREREG_FILES]
    tracked = _git("ls-files", "--error-unmatch", *files)
    if tracked.returncode != 0:
        return ["part A files are not all tracked by git (commit them first)"]
    dirty = _git("status", "--porcelain", "--", *files).stdout.strip()
    return [f"part A files have uncommitted changes: {dirty.splitlines()[0]}"] if dirty else []


def check_tree_clean() -> Check:
    """Nothing under the frozen paths is modified or untracked."""
    item = "working tree clean under src/ and the EXP-0009 scripts"
    try:
        check_clean(_git("status", "--porcelain", "--", *FROZEN_PATHS).stdout)
    except FreezeRefused as error:
        return Check(item=item, status="FAIL", detail=str(error))
    return Check(item=item, status="OK", detail="clean")


def check_smoke(smoke_passed: Path | None) -> Check:
    """`run_all.sh --smoke` ended with SMOKE_PASSED at a commit with the same frozen paths."""
    item = "run_all.sh --smoke passed at this HEAD"
    if smoke_passed is None:
        return Check(
            item=item, status="SKIP", detail="pass --smoke-passed <smoke root>/SMOKE_PASSED"
        )
    if not smoke_passed.is_file():
        return Check(item=item, status="FAIL", detail=f"no {smoke_passed}")
    recorded = smoke_passed.read_text(encoding="utf-8").strip()
    head = _git("rev-parse", "HEAD").stdout.strip()
    changed = _git("diff", "--name-only", recorded, head, "--", *FROZEN_PATHS).stdout.split()
    if recorded != head and changed:
        return Check(item=item, status="FAIL", detail=f"changed since the smoke: {changed[:3]}")
    return Check(item=item, status="OK", detail=f"passed at {recorded[:10]}")


def main(argv: Sequence[str] | None = None) -> int:
    """Print the checklist; exit 1 if any item failed."""
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.exp0009.readiness")
    parser.add_argument("--prereg-only", action="store_true", help="only part A (what P0 checks)")
    parser.add_argument("--smoke-passed", type=Path)
    parser.add_argument("--no-neo4j", action="store_true")
    parser.add_argument("--no-network", action="store_true")
    args = parser.parse_args(argv)
    checks = [check_prereg_a()]
    if not args.prereg_only:
        checks += [
            check_tree_clean(),
            check_smoke(args.smoke_passed),
            check_neo4j(None if args.no_neo4j else neo4j_database_names),
            check_neo4j_home(os.environ.get("E10_NEO4J_HOME")),
            check_disk(),
            check_balance(None if args.no_network else balance.fetch_credits_json),
            check_power(),
            *hand_checks(),
        ]
    for check in checks:
        print(f"[{check.status:^4}] {check.item}: {check.detail}")
    return 1 if any(c.status == "FAIL" for c in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
