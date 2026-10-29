"""`exp0001 report --system v2t`: the V2T tiers and cascade_v4_iso stand in for the F1 arms."""

from __future__ import annotations

import argparse
from pathlib import Path

from plantgraph.qa.exp0001 import report_cli
from plantgraph.qa.exp0001.report_models import AG, CASCADE, CYP

INPUTS = Path(__file__).resolve().parents[3] / "data" / "runs" / "exp0007"


def _args(system: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    report_cli.add_report_arguments(parser)
    return parser.parse_args(["--system", system, "--root", str(INPUTS)])


def test_the_v2t_system_swaps_the_tiers_and_the_cascade() -> None:
    f1 = report_cli._policies(_args("f1"))
    v2t = report_cli._policies(_args("v2t"))

    assert [f1[a].tiers[0].strategy for a in (CYP, AG)] == [
        "cypher_rag_plant",
        "graph_agent_low_steps",
    ]
    assert [v2t[a].tiers[0].strategy for a in (CYP, AG)] == [
        "cypher_rag_lines",
        "graph_agent_lines",
    ]
    assert f1[CASCADE].name == "cascade_v3" and v2t[CASCADE].name == "cascade_v4_iso"


def test_the_cascade_arm_is_renamed_in_the_files_and_the_footnote_is_appended(
    tmp_path: Path,
) -> None:
    report = tmp_path / "report.md"
    report.write_text("| cascade_v3 | 0.9 |\nX1: ctx-high vs cascade_v3\n")
    figure = tmp_path / "figure.csv"
    figure.write_text("1,cascade_v3,0.9\n")

    report_cli._relabel([report, figure], "v2t", "Not run at H30g2.")

    assert "cascade_v3" not in report.read_text() + figure.read_text()
    assert report.read_text().count("cascade_v4_iso") == 2
    assert report.read_text().endswith("\n\nNot run at H30g2.\n")
    assert "Not run" not in figure.read_text()


def test_f1_keeps_its_names_and_gets_no_footnote_by_default(tmp_path: Path) -> None:
    report = tmp_path / "report.md"
    report.write_text("cascade_v3\n")

    report_cli._relabel([report], "f1", None)

    assert report.read_text() == "cascade_v3\n"
