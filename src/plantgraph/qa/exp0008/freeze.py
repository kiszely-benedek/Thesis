"""The E9 freeze at stage M3: what must be true, and the hash files it writes (review-fixes §5.4).

**Freeze** here means: from this point no file that decides what a test run does may change. The
launcher proves it by hashing every such file (`E9.sha256`) and the pre-registration
(`PREREG.sha256`) before the first test plant is built. The git facts (HEAD, tree state, changed
files) are passed in as text, so the rules are plain functions that tests run without a repository.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Sequence
from pathlib import Path

#: part A states which code commit it was written against, on a line like this
NAMED_HEAD_PATTERN = re.compile(r"^Frozen code commit:\s*`?([0-9a-f]{40})`?\s*$", re.MULTILINE)
#: a commit made after the named one may add the pre-registration (part A + the drawn seeds);
#: callers pass only the changes under the hashed paths, so notes and the study map never count
PREREG_PREFIX = "data/runs/exp0008/prereg/"


class FreezeRefused(RuntimeError):
    """A precondition of the freeze does not hold; the launcher stops before any test plant."""


def named_head(part_a_text: str) -> str:
    """The code commit part A names.

    Raises:
        FreezeRefused: part A has no `Frozen code commit:` line with a 40-hex commit.
    """
    match = NAMED_HEAD_PATTERN.search(part_a_text)
    if match is None:
        raise FreezeRefused(
            "expected a 'Frozen code commit: <40 hex>' line in PREREG_A.md, found none"
        )
    return match.group(1)


def check_clean(porcelain: str) -> None:
    """Refuse a working tree with changes under the frozen paths.

    Raises:
        FreezeRefused: `porcelain` (git status --porcelain over the frozen paths) is not empty.
    """
    lines = [line for line in porcelain.splitlines() if line.strip()]
    if lines:
        raise FreezeRefused(
            f"expected a clean tree under src/ and the EXP-0008 scripts, found {len(lines)} "
            f"changed path(s), first: {lines[0].strip()}"
        )


def check_head(head: str, named: str, changed_between: Sequence[str]) -> None:
    """Refuse a HEAD that is not the commit part A names.

    HEAD is the named commit itself, or a later commit that changed no frozen file other than the
    pre-registration (part A cannot name the commit that contains it). `changed_between` lists the
    files changed since the named commit under the hashed paths only (git filters by pathspec), so a
    later note or study-map commit does not count.

    Raises:
        FreezeRefused: HEAD differs from the named commit and the commits between touch other files.
    """
    if head == named:
        return
    stray = [path for path in changed_between if not path.startswith(PREREG_PREFIX)]
    if stray:
        raise FreezeRefused(
            f"expected HEAD {named[:10]} (named in PREREG_A.md), found {head[:10]} with other "
            f"changes since: {stray[:3]}"
        )


def sha256_of(path: Path) -> str:
    """Hex sha256 of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_hash_file(out: Path, files: Iterable[Path]) -> int:
    """Write `sha256sum -c`-readable lines for `files` (sorted, forward slashes); never overwrites.

    Raises:
        FileExistsError: `out` exists (a freeze is written once).
    """
    lines = [f"{sha256_of(p)} *{p.as_posix()}" for p in sorted(set(files))]
    with out.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    return len(lines)
