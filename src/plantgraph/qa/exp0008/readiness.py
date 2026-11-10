"""The readiness checklist of review-fixes §5.4, as far as a program can check it.

    python -m plantgraph.qa.exp0008.readiness [--smoke-passed FILE] [--no-neo4j] [--no-network]

Each item prints `[ OK ]`, `[FAIL]`, `[SKIP]` (a probe the caller switched off),
`[INFO]` (worth knowing, not a failure) or `[HAND]` (only a person can say). The exit code is 1
if any item failed. Nothing here starts a stage, writes a file or makes a paid call; the balance
check reads the credit endpoint, Neo4j is only asked for its database names.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal

import psutil
from pydantic import BaseModel, ConfigDict

from plantgraph.ingest.seed_plan import SeedPlan, load_seed_plan
from plantgraph.qa.audit.judge import template_sha256
from plantgraph.qa.exp0008 import balance
from plantgraph.qa.exp0008.freeze import FreezeRefused, check_clean, check_head, named_head

Status = Literal["OK", "FAIL", "SKIP", "HAND", "INFO"]
SCRIPTS = Path("data/runs/exp0008")
# Same list as FROZEN_PATHS in stages/m3_freeze.sh (the demo is built in parallel: not frozen).
FROZEN_PATHS = ("src", ":!src/plantgraph/demo", "scripts/audit_export_subgraphs.py",
                "data/runs/exp0008/run_all.sh", "data/runs/exp0008/lib.sh",
                "data/runs/exp0008/lib_plants.sh", "data/runs/exp0008/lib_runs.sh",
                "data/runs/exp0008/stages",
                "data/runs/exp0007/inputs", "data/runs/exp0001/inputs",
                "data/external/C01V04-VER.EX01.xml")  # fmt: skip
# What E9.sha256 hashes: the frozen paths plus the dependency pins. A commit that changes none of
# these (a note, the study map) leaves the frozen code as it was: part A and the smoke still hold.
HASHED_PATHS = (*FROZEN_PATHS, "pyproject.toml", "uv.lock")
MIN_FREE_DISK_GB = 10
MIN_BALANCE_USD = 40.0
PILOT_INPUTS = ("valves_ids.txt", "runs.txt", "subgraphs.json")
TEMPORARY_DATABASE = "e7tune"


class Check(BaseModel):
    """One checklist line."""

    model_config = ConfigDict(frozen=True)

    item: str
    status: Status
    detail: str


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=False)  # noqa: S603, S607
    if result.returncode != 0:
        raise RuntimeError(
            f"expected `git {' '.join(args)}` to succeed, found: {result.stderr.strip()}"
        )
    return result.stdout


def frozen_changes_since(commit: str) -> list[str]:
    """The hashed files that differ between `commit` and HEAD (empty when only other files changed).

    Raises:
        RuntimeError: `commit` is not HEAD or an ancestor of HEAD, or git fails.
    """
    head = _git("rev-parse", "HEAD").strip()
    if commit == head:
        return []
    if commit not in _git("rev-list", "HEAD").split():
        raise RuntimeError(f"expected {commit[:10]} to be HEAD or an ancestor of it, found neither")
    return _git("diff", "--name-only", commit, "HEAD", "--", *HASHED_PATHS).split()


def check_tree_clean() -> Check:
    """Item 1/3: nothing under the frozen paths is modified or untracked."""
    try:
        check_clean(_git("status", "--porcelain", "--", *FROZEN_PATHS))
    except (FreezeRefused, RuntimeError) as error:
        return Check(
            item="1. working tree clean under src/ and the scripts",
            status="FAIL",
            detail=str(error),
        )
    return Check(
        item="1. working tree clean under src/ and the scripts", status="OK", detail="clean"
    )


def check_prereg_a(prereg: Path = SCRIPTS / "prereg") -> Check:
    """Item 3: part A is there with the seeds and the current judge prompt hash, and names HEAD."""
    item = "3. PREREG_A.md with seeds, judge hashes, naming HEAD"
    part_a = prereg / "PREREG_A.md"
    if not part_a.is_file():
        return Check(item=item, status="FAIL", detail=f"no {part_a}")
    text = part_a.read_text(encoding="utf-8")
    problems = []
    if "<<FILL" in text:
        problems.append("a <<FILL ...>> marker is still in the text")
    if template_sha256() not in text:
        problems.append(f"the judge prompt hash {template_sha256()[:12]}... is not in part A")
    seeds = load_seed_plan(prereg / "seeds.json")
    if not isinstance(seeds, SeedPlan):
        problems.append(f"no drawn seeds at {prereg / 'seeds.json'}")
    try:
        head = _git("rev-parse", "HEAD").strip()
        named = named_head(text)
        check_head(head, named, frozen_changes_since(named))
    except (FreezeRefused, RuntimeError) as error:
        problems.append(str(error))
    return Check(item=item, status="FAIL" if problems else "OK", detail="; ".join(problems) or "ok")


def check_smoke(smoke_passed: Path | None) -> Check:
    """Item 4: `run_all.sh --smoke` ended with SMOKE_PASSED at HEAD's frozen code.

    That is HEAD itself, or an ancestor of HEAD with no hashed file changed since (only notes, say).
    """
    item = "4. run_all.sh --smoke passed at this HEAD"
    if smoke_passed is None:
        return Check(
            item=item, status="SKIP", detail="pass --smoke-passed <smoke root>/SMOKE_PASSED"
        )
    if not smoke_passed.is_file():
        return Check(item=item, status="FAIL", detail=f"no {smoke_passed}")
    try:
        head = _git("rev-parse", "HEAD").strip()
    except RuntimeError as error:
        return Check(item=item, status="FAIL", detail=str(error))
    recorded = smoke_passed.read_text(encoding="utf-8").strip()
    if recorded == head:
        return Check(item=item, status="OK", detail=f"passed at {head[:10]}")
    try:
        changed = frozen_changes_since(recorded)
    except RuntimeError as error:
        changed = [str(error)]
    if changed:
        return Check(
            item=item,
            status="FAIL",
            detail=(
                f"the smoke passed at {recorded[:10]}, HEAD is {head[:10]}; "
                f"changed since: {changed[:3]}"
            ),
        )
    return Check(
        item=item,
        status="OK",
        detail=f"passed at {recorded[:10]}; HEAD {head[:10]} changed no frozen file since",
    )


def check_neo4j(list_databases: Callable[[], list[str]] | None) -> Check:
    """Item 5a: the server answers; a leftover `e7tune` is only noted, because M0 drops it."""
    item = "5. Neo4j up, database `neo4j` reachable (`e7tune` is dropped by M0)"
    if list_databases is None:
        return Check(item=item, status="SKIP", detail="--no-neo4j")
    try:
        names = list_databases()
    except Exception as error:  # noqa: BLE001 - any driver failure means "not reachable"
        return Check(
            item=item, status="FAIL", detail=f"cannot list databases: {type(error).__name__}"
        )
    if "neo4j" not in names:
        return Check(item=item, status="FAIL", detail=f"no database `neo4j` among {names}")
    if TEMPORARY_DATABASE in names:
        return Check(
            item=item,
            status="INFO",
            detail=f"`{TEMPORARY_DATABASE}` exists; M0 drops it first. databases: {names}",
        )
    return Check(item=item, status="OK", detail=f"databases: {names}")


def check_neo4j_home(home: str | None) -> Check:
    """Item 5c: M7 measures store sizes in the server's home folder, so it must be set and exist."""
    item = "5. E9_NEO4J_HOME names the Neo4j server's home folder (M7 store sizes)"
    if not home:
        return Check(
            item=item, status="FAIL", detail="E9_NEO4J_HOME is not set (launch.sh sets it)"
        )
    if not Path(home).is_dir():
        return Check(item=item, status="FAIL", detail=f"expected a folder at {home}, found none")
    return Check(item=item, status="OK", detail=home)


def check_disk(path: Path = Path(".")) -> Check:
    """Item 5b: free space for the stores and logs."""
    free_gb = shutil.disk_usage(path).free / 2**30
    ok = free_gb >= MIN_FREE_DISK_GB
    return Check(
        item=f"5. free disk >= {MIN_FREE_DISK_GB} GB",
        status="OK" if ok else "FAIL",
        detail=f"{free_gb:.1f} GB free",
    )


def check_balance(fetch: balance.CreditsFetcher | None) -> Check:
    """Item 6: the OpenRouter balance covers the program cap, read by the launcher's own code."""
    item = f"6. OpenRouter balance >= ${MIN_BALANCE_USD:.0f}"
    if fetch is None:
        return Check(item=item, status="SKIP", detail="--no-network")
    try:
        amount = balance.require_balance(MIN_BALANCE_USD, fetch)
    except balance.BalanceError as error:
        return Check(item=item, status="FAIL", detail=str(error))
    return Check(item=item, status="OK", detail=f"${amount:.2f}")


def check_power() -> Check:
    """Item 7a: the laptop is plugged in (sleep settings and other jobs stay a hand check)."""
    item = "7. laptop plugged in"
    battery = psutil.sensors_battery()
    if battery is None:
        return Check(item=item, status="OK", detail="no battery (a desktop)")
    return Check(
        item=item,
        status="OK" if battery.power_plugged else "FAIL",
        detail=f"plugged: {battery.power_plugged}",
    )


def check_inputs(scripts: Path = SCRIPTS) -> Check:
    """The files M2b and M9 read that a person prepares once, and a clean start."""
    item = "inputs of M2b (judge pilot) and M9 (EX01), and a fresh output folder"
    problems = [f"missing {scripts / 'inputs' / 'pilot' / name}" for name in PILOT_INPUTS
                if not (scripts / "inputs" / "pilot" / name).is_file()]  # fmt: skip
    for path in (Path("data/external/C01V04-VER.EX01.xml"), Path("data/runs/exp0001/inputs")):
        if not path.exists():
            problems.append(f"missing {path}")
    if (scripts / "state").exists():
        problems.append(
            f"{scripts / 'state'} exists: a previous launch left state (move it away on purpose)"
        )
    return Check(item=item, status="FAIL" if problems else "OK", detail="; ".join(problems) or "ok")


def hand_checks() -> list[Check]:
    """The items only a person can answer."""
    hand = (
        ("2. second read-only review done, findings fixed or recorded", "ask the main session"),
        ("7. sleep off, no other heavy job", "the latency claims depend on it"),
        ('8. study map read; the user says "mehet"', "nothing starts before this"),
    )
    return [Check(item=item, status="HAND", detail=detail) for item, detail in hand]


def neo4j_database_names() -> list[str]:
    """Names of the server's databases, through the project's own Neo4j settings."""
    from neo4j import GraphDatabase

    from plantgraph.store.neo4j_settings import from_env

    settings = from_env()
    if settings is None:
        raise ValueError("expected NEO4J_URI, NEO4J_USERNAME and NEO4J_PASSWORD, found some unset")
    auth = (settings.username, settings.password.get_secret_value())
    with (
        GraphDatabase.driver(settings.uri, auth=auth) as driver,
        driver.session(database="system") as session,
    ):
        return [str(record["name"]) for record in session.run("SHOW DATABASES")]


def run_checks(smoke_passed: Path | None, use_neo4j: bool, use_network: bool) -> list[Check]:
    """All checks in checklist order."""
    return [
        check_tree_clean(),
        *hand_checks()[:1],
        check_prereg_a(),
        check_smoke(smoke_passed),
        check_neo4j(neo4j_database_names if use_neo4j else None),
        check_neo4j_home(os.environ.get("E9_NEO4J_HOME")),
        check_disk(),
        check_balance(balance.fetch_credits_json if use_network else None),
        check_power(),
        check_inputs(),
        *hand_checks()[1:],
    ]


def main(argv: Sequence[str] | None = None) -> int:
    """Print the checklist; exit 1 if any item failed."""
    parser = argparse.ArgumentParser(
        prog="python -m plantgraph.qa.exp0008.readiness", description=__doc__
    )
    parser.add_argument("--smoke-passed", type=Path)
    parser.add_argument("--no-neo4j", action="store_true", help="skip the Neo4j probe")
    parser.add_argument("--no-network", action="store_true", help="skip the balance probe")
    args = parser.parse_args(argv)
    checks = run_checks(args.smoke_passed, not args.no_neo4j, not args.no_network)
    for check in checks:
        print(f"[{check.status:^4}] {check.item}: {check.detail}")
    return 1 if any(c.status == "FAIL" for c in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
