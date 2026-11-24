"""The E10 freeze (stage F10) and the B-code hashes (design §19.8).

**Freeze** means: from this point nothing that decides what a sealed run does may change. F10
proves it by hashing every such file (`E10.sha256`), the B files with the cascade policy
(`B_FILES.sha256`) and the pre-registration (`PREREG.sha256`) before the first sealed plant is
built. The git facts (HEAD, tree state, changed files) arrive as text, so every rule here is a
plain function that a test runs without a repository. The pure helpers of EXP-0008's freeze are
imported, not copied.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from plantgraph.qa.exp0008.freeze import FreezeRefused, check_clean, sha256_of, write_hash_file
from plantgraph.qa.v2tb.policy_b import policy_b

__all__ = ["FreezeRefused", "check_clean", "sha256_of", "write_hash_file"]

#: part A names the code commit it was written against, on a line like this
NAMED_HEAD_PATTERN = re.compile(r"^Part A code commit:\s*`?([0-9a-f]{40})`?\s*$", re.MULTILINE)
#: Between part A's commit and E10 only these may change (§19.3): the B files and their tests
#: (tuning), the T17 analysis, the pre-registration folder and the documents.
ALLOWED_CHANGE_PREFIXES = (
    "src/plantgraph/qa/v2tb/",
    "tests/v2tb/",
    "src/plantgraph/qa/exp0009/analysis",
    "tests/qa/exp0009/test_analysis",
    "data/runs/exp0009/prereg/",
    "docs/",
)
POLICY_LINE_NAME = "policy:cascade_v4_iso_b"
B_DIR = Path("src/plantgraph/qa/v2tb")


def named_head(part_a_text: str) -> str:
    """The code commit part A names.

    Raises:
        FreezeRefused: no `Part A code commit: <40 hex>` line.
    """
    match = NAMED_HEAD_PATTERN.search(part_a_text)
    if match is None:
        raise FreezeRefused(
            "expected a 'Part A code commit: <40 hex>' line in PREREG_A.md, found none"
        )
    return match.group(1)


def check_head(head: str, named: str, changed_since_named: Sequence[str]) -> None:
    """Refuse changes since part A's commit outside the allowed list.

    Raises:
        FreezeRefused: HEAD is not the named commit and a changed path is not allowed.
    """
    if head == named:
        return
    stray = [p for p in changed_since_named if not p.startswith(ALLOWED_CHANGE_PREFIXES)]
    if stray:
        raise FreezeRefused(
            f"expected only B files, the T17 analysis, prereg/ and docs/ to change since "
            f"{named[:10]}, found {stray[:3]}"
        )


def _canonical(value: Any) -> Any:
    """Sort what is a set in disguise: a list of plain strings (a tier's `accept` rules)."""
    if isinstance(value, dict):
        return {key: _canonical(item) for key, item in value.items()}
    if isinstance(value, list):
        if all(isinstance(item, str) for item in value):
            return sorted(value)
        return [_canonical(item) for item in value]
    return value


def policy_digest() -> str:
    """sha256 of `policy_b()`'s JSON dump in canonical form: the cascade rules B runs under (R15).

    The raw `model_dump_json()` is not stable between processes: a tier's `accept` rules are a
    set, written in hash-seed order. Sets become sorted lists and keys are sorted before hashing.
    """
    document = _canonical(json.loads(policy_b().model_dump_json()))
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def b_code_hashes(b_dir: Path = B_DIR) -> dict[str, str]:
    """File name -> sha256 of every B source file, plus the policy line."""
    hashes = {p.as_posix(): sha256_of(p) for p in sorted(b_dir.rglob("*.py"))}
    hashes[POLICY_LINE_NAME] = policy_digest()
    return hashes


def digest_of_hashes(hashes: Mapping[str, str]) -> str:
    """The sha256 of the `b_code.sha256` text those hashes would give (to compare with a file's)."""
    lines = [f"{digest} *{name}" for name, digest in sorted(hashes.items())]
    text = "\n".join(lines) + "\n"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_b_code_sha256(out: Path, b_dir: Path = B_DIR) -> str:
    """Write `b_code.sha256` for a round or a run; never overwrites. Returns its own sha256."""
    lines = [f"{digest} *{name}" for name, digest in sorted(b_code_hashes(b_dir).items())]
    with out.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    return sha256_of(out)


def read_hash_file(path: Path) -> dict[str, str]:
    """`sha256sum`-style lines back into name -> digest."""
    rows = (line.split(" *", 1) for line in path.read_text(encoding="utf-8").splitlines() if line)
    return {name: digest for digest, name in rows}


def check_b_files(chosen: Mapping[str, str], current: Mapping[str, str], label: str) -> None:
    """The B files now equal the hashes of `label` (a tuning round or a run).

    Raises:
        FreezeRefused: naming the files that differ.
    """
    differ = sorted(n for n in set(chosen) | set(current) if chosen.get(n) != current.get(n))
    if differ:
        raise FreezeRefused(
            f"expected the B files to equal {label}'s hashes, found {differ[:3]} differ"
        )


def write_e10(prereg: Path, head: str, frozen_files: Iterable[Path]) -> int:
    """Write `E10.commit` and `E10.sha256` (every tracked frozen file); never overwrites."""
    with (prereg / "E10.commit").open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(head + "\n")
    return write_hash_file(prereg / "E10.sha256", frozen_files)


def write_b_files_hash(prereg: Path, b_dir: Path = B_DIR) -> None:
    """Write `B_FILES.sha256`: every file under `qa/v2tb/` and the policy line."""
    write_b_code_sha256(prereg / "B_FILES.sha256", b_dir)


def write_prereg_sha(prereg: Path, extra: Iterable[Path]) -> int:
    """`PREREG.sha256` over part A, part B, seeds, plan, prior, the E10 files and `extra`."""
    names = (
        "PREREG_A.md", "PREREG_B.md", "seeds.json", "plan.json", "position_prior.json",
        "E10.commit", "E10.sha256", "B_FILES.sha256",
    )  # fmt: skip
    return write_hash_file(prereg / "PREREG.sha256", [*(prereg / n for n in names), *extra])
