"""EXP-0009's judge entry point: the frozen judge plus help text for B's answer types (ADR-0069).

The **judge** is a second model that reads an answered row and says whether the programmatic scorer
was right. The frozen judge (`qa/audit/judge.py`) describes each answer type to the model in one
help line, and it has none for VALVE_SET or POSITION, the only types of the B stratum. Editing the
frozen module would change nothing the pre-registration hashes (the prompt template file and the
judge pin stay byte-identical), but the module is EXP-0008's code and stays untouched. So this
entry point adds the two missing lines to the frozen table in its own process, then runs the frozen
`python -m plantgraph.qa.audit` command line unchanged:

    python -m plantgraph.qa.exp0009.audit_judge judge --run ... --stage audit ...

It prints the two added lines and their sha256, for the amendment of PREREG A that records them.
"""

from __future__ import annotations

import hashlib
import sys
from collections.abc import Sequence

from plantgraph.qa.audit import cli, judge
from plantgraph.qa.models import AnswerType

#: The two lines added to the frozen help table; the order below is the order they are hashed in.
EXTRA_ANSWER_TYPE_HELP: dict[AnswerType, str] = {
    AnswerType.VALVE_SET: (
        "VALVE_SET (a set of valves to operate, order irrelevant; a valve without a tag is "
        "named by its class, line number, side and nearest tag)"
    ),
    AnswerType.POSITION: "POSITION (one normal operating position code, e.g. NO, NC, CSO)",
}


def extra_lines_sha256() -> str:
    """sha256 of the two added lines, joined by newlines (what PREREG A's amendment records)."""
    text = "\n".join(EXTRA_ANSWER_TYPE_HELP.values())
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def install_extra_help() -> None:
    """Add the two lines to the frozen judge's table; never replace one it already has.

    Raises:
        ValueError: the frozen table already describes one of the types differently.
    """
    table = judge._ANSWER_TYPE_HELP
    for answer_type, line in EXTRA_ANSWER_TYPE_HELP.items():
        if table.setdefault(answer_type, line) != line:
            raise ValueError(
                f"expected no help line for {answer_type.value} in the frozen judge, "
                f"found {table[answer_type]!r}"
            )


def main(argv: Sequence[str] | None = None) -> int:
    """Install the two lines, print them with their hash, then run the frozen audit command."""
    install_extra_help()
    for line in EXTRA_ANSWER_TYPE_HELP.values():
        print(f"added judge help line: {line}")
    print(f"added judge help lines sha256: {extra_lines_sha256()}")
    return cli.main(None if argv is None else list(argv))


if __name__ == "__main__":
    sys.exit(main())
