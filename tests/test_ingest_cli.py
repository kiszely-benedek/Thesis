"""`python -m plantgraph.ingest` — argument parsing, JSON output, and exit codes (design §8, T8).

`missing_required_vars`/`from_env` are isolated the same way `test_neo4j_settings.py`
does it: `_ENV_FILE` is redirected to a path that does not exist, and the four
`NEO4J_*` variables are cleared, so these tests can never read this machine's
real `.env` credentials.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plantgraph.ingest import __main__ as ingest_main
from plantgraph.ingest.models import IngestResult
from plantgraph.store import neo4j_settings

_EX01_PATH = Path(__file__).resolve().parent.parent / "data" / "external" / "C01V04-VER.EX01.xml"

_NEO4J_VARS = ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE")


@pytest.fixture(autouse=True)
def _isolated_neo4j_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No test in this file may see this machine's real Neo4j credentials (see module docstring)."""
    for name in _NEO4J_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(neo4j_settings, "_ENV_FILE", tmp_path / ".env")


# --- argument parsing --------------------------------------------------------------------


def test_synthetic_defaults_match_the_adr_0017_headline_configuration() -> None:
    args = ingest_main._parse_args(["synthetic", "--n-units", "4"])

    assert args.command == "synthetic"
    assert args.budget == 16
    assert args.seed == 0
    assert args.strategy == "flow_greedy"
    assert args.corpus_id is None
    assert args.check is False
    assert args.no_neo4j is False


def test_synthetic_requires_n_units() -> None:
    with pytest.raises(SystemExit):
        ingest_main._parse_args(["synthetic"])


def test_proteus_requires_a_path() -> None:
    with pytest.raises(SystemExit):
        ingest_main._parse_args(["proteus"])


def test_a_command_is_required() -> None:
    with pytest.raises(SystemExit):
        ingest_main._parse_args([])


def test_sanitize_corpus_id_replaces_unsafe_characters() -> None:
    assert ingest_main._sanitize_corpus_id("C01V04-VER.EX01") == "C01V04-VER.EX01"
    assert ingest_main._sanitize_corpus_id("a file with spaces") == "a-file-with-spaces"


# --- synthetic, --no-neo4j --check: the acceptance case from the design's task table ------


@pytest.mark.parametrize("n_units", [4, 25])
def test_synthetic_no_neo4j_check_exits_zero_and_prints_a_valid_result(
    n_units: int, capsys: pytest.CaptureFixture[str]
) -> None:
    ingest_main.main(
        ["synthetic", "--n-units", str(n_units), "--budget", "3", "--no-neo4j", "--check"]
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["gate_equal"] is True
    for key in ("corpus_id", "config", "counts", "stage_seconds", "resolution", "neo4j_version"):
        assert key in payload
    assert payload["load_report"] is None


def test_synthetic_default_corpus_id_encodes_units_budget_and_seed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ingest_main.main(["synthetic", "--n-units", "4", "--budget", "3", "--seed", "7", "--no-neo4j"])

    payload = json.loads(capsys.readouterr().out)
    assert payload["corpus_id"] == "syn-u4-b3-s7"


# --- proteus, --no-neo4j -------------------------------------------------------------------


def test_proteus_no_neo4j_prints_the_import_report(capsys: pytest.CaptureFixture[str]) -> None:
    if not _EX01_PATH.exists():
        pytest.skip(f"{_EX01_PATH} is absent; data/ is untracked (see CLAUDE.md)")

    ingest_main.main(["proteus", str(_EX01_PATH), "--no-neo4j"])

    payload = json.loads(capsys.readouterr().out)
    assert payload["import_report"] is not None
    assert payload["gate_equal"] is None, "proteus has no answer key to check the resolver against"
    # cross-checked against the importer's own violation count, never a hardcoded number: the
    # design note's own figure (3) predates ADR-0016's generic fallback and is now stale (§3.1)
    violation_kinds = [v["kind"] for v in payload["import_report"]["violations"]]
    assert violation_kinds.count("duplicate_tag") == 7


# --- missing Neo4j settings, without --no-neo4j: a clear error naming all three variables --


def test_missing_neo4j_settings_without_no_neo4j_names_all_three_variables() -> None:
    with pytest.raises(SystemExit) as excinfo:
        ingest_main.main(["synthetic", "--n-units", "4"])

    message = str(excinfo.value)
    for variable in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"):
        assert variable in message


# --- --out: writing the IngestResult to disk (design `qa-system.md` §2.1 R6, QA-T0) --------


def test_out_writes_ingest_json_matching_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out_dir = tmp_path / "corpus"

    ingest_main.main(
        [
            "synthetic",
            "--n-units",
            "4",
            "--budget",
            "3",
            "--no-neo4j",
            "--check",
            "--out",
            str(out_dir),
        ]
    )

    stdout_result = IngestResult.model_validate_json(capsys.readouterr().out)
    written_path = out_dir / "ingest.json"
    file_result = IngestResult.model_validate_json(written_path.read_text(encoding="utf-8"))
    assert file_result == stdout_result


def test_out_creates_missing_parent_directories(tmp_path: Path) -> None:
    out_dir = tmp_path / "does" / "not" / "exist" / "yet"

    ingest_main.main(["synthetic", "--n-units", "4", "--no-neo4j", "--out", str(out_dir)])

    assert (out_dir / "ingest.json").exists()


def test_out_is_deterministic_ignoring_wall_clock_timings(tmp_path: Path) -> None:
    """Same seed twice gives the same config, counts and gate result — timing floats aside."""
    for label in ("first", "second"):
        ingest_main.main(
            [
                "synthetic",
                "--n-units",
                "4",
                "--budget",
                "3",
                "--seed",
                "0",
                "--no-neo4j",
                "--check",
                "--out",
                str(tmp_path / label),
            ]
        )
    first = IngestResult.model_validate_json(
        (tmp_path / "first" / "ingest.json").read_text(encoding="utf-8")
    )
    second = IngestResult.model_validate_json(
        (tmp_path / "second" / "ingest.json").read_text(encoding="utf-8")
    )
    assert first.model_copy(update={"stage_seconds": {}}) == second.model_copy(
        update={"stage_seconds": {}}
    )
    assert set(first.stage_seconds) == set(second.stage_seconds)


def test_out_is_absent_by_default(capsys: pytest.CaptureFixture[str]) -> None:
    """No `--out` flag: no behaviour change from before QA-T0 (only stdout is written)."""
    args = ingest_main._parse_args(["synthetic", "--n-units", "4"])
    assert args.out is None


def test_proteus_out_writes_ingest_json_matching_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    if not _EX01_PATH.exists():
        pytest.skip(f"{_EX01_PATH} is absent; data/ is untracked (see CLAUDE.md)")
    out_dir = tmp_path / "ex01"

    ingest_main.main(["proteus", str(_EX01_PATH), "--no-neo4j", "--out", str(out_dir)])

    stdout_result = IngestResult.model_validate_json(capsys.readouterr().out)
    file_result = IngestResult.model_validate_json(
        (out_dir / "ingest.json").read_text(encoding="utf-8")
    )
    assert file_result == stdout_result
