"""The Results tab's v2 views, run through node on fixtures cut from the EXP-0008 report shapes.

The page has no browser test runner, so a tiny stand-in for `document` is enough to build the tables
and chart specifications and read their text back. Skipped when node is not installed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

import pytest

from plantgraph.demo.app.server import STATIC_DIR

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

# A minimal `document`: elements are plain objects; `textOf` reads a tree back as text.
HARNESS = """
import { pathToFileURL } from "node:url";
const make = (tag) => ({ tag, children: [], dataset: {},
  append(...c) { this.children.push(...c); }, setAttribute() {} });
globalThis.document = { createElement: make };
const textOf = (n) => (typeof n === "string" ? n
  : [n.textContent ?? "", ...(n.children ?? []).map(textOf)].join(""));
const find = (n, test, hits = []) => {
  if (typeof n === "string") return hits;
  if (test(n)) hits.push(n);
  n.children.forEach((c) => find(c, test, hits));
  return hits;
};
const load = (name) => import(pathToFileURL(process.argv[1] + "/" + name).href);
const input = JSON.parse(process.argv[2]);
const out = {};
"""

INFRA = {
    "rows": [
        {
            "name": "ingest.build_total",
            "unit": "s",
            "from_corpus": "H100",
            "to_corpus": "H1000",
            "from_value": 9.38,
            "to_value": 427.27,
        },
        {
            "name": "store.data_bytes",
            "unit": "bytes",
            "from_corpus": "H100",
            "to_corpus": "H1000",
            "from_value": 6891281,
            "to_value": 58951570,
        },
        {
            "name": "size.sheets",
            "unit": "count",
            "from_corpus": "H100",
            "to_corpus": "H1000",
            "from_value": 100,
            "to_value": 1000,
        },
    ],
    "checks": [
        {"claim_id": "M1", "verdict": "FAIL", "text": "M1 replay: " + "long detail " * 30},
        {"claim_id": "M4", "verdict": "FLAG", "text": "M4 memory: close to the limit"},
    ],
}
INTERVAL = {"estimate": 0.9, "ci_low": 0.85, "ci_high": 0.95}
E2E = {
    "arms": [
        {
            "label": "R5",
            "corpus": "pooled",
            "n": 1100,
            "n_correct": 999,
            "accuracy": INTERVAL,
            "interval_method": "two-stage bootstrap",
        },
        {
            "label": "V-d2",
            "corpus": "H1000",
            "n": 220,
            "n_correct": 187,
            "accuracy": INTERVAL,
            "interval_method": "wilson",
        },
    ],
    "claims": [],
}


def _row(corpus: str, policy: str, pooled: bool, label: str = "V2T-A2") -> dict[str, Any]:
    return {
        "corpus_id": corpus,
        "n_sheets": 100,
        "policy": policy,
        "source_label": label,
        "scope": "headline",
        "n_questions": 220,
        "n_correct": 200,
        "accuracy": INTERVAL,
        "cost_per_question_usd": 0.0014,
        "latency_median_s": 8.1,
        "latency_p90_s": 44.5,
        "pooled": pooled,
        "n_plants": 5 if pooled else None,
        "interval_method": "two-stage bootstrap" if pooled else "wilson",
    }


ROWS = [
    _row("S100", "cascade_v4_iso", True),
    _row("H100", "cascade_v4_iso", False),
    _row("H100", "cascade_v3", False, "F1, previous system"),
]


def _run(body: str, **inputs: Any) -> dict[str, Any]:
    script = HARNESS + body + "\nconsole.log(JSON.stringify(out));"
    command = ["node", "--experimental-default-type=module", "--input-type=module", "-e", script]
    done = subprocess.run(
        [*command, str(STATIC_DIR), json.dumps(inputs)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert done.returncode == 0, f"node failed: {done.stderr}"
    return json.loads(done.stdout)  # type: ignore[no-any-return]


def test_the_infra_table_gives_each_row_its_unit_and_flags_the_checks() -> None:
    out = _run(
        """
        const { infraTable, infraChecks } = await load("results_infra.js");
        out.table = textOf(infraTable(input.infra));
        const checks = infraChecks(input.infra);
        out.checks = textOf(checks);
        out.pills = find(checks, (n) => String(n.className).startsWith("pill")).map(textOf);
        out.open = find(checks, (n) => n.tag === "details" && n.open).length;
        """,
        infra=INFRA,
    )

    assert "427 s" in out["table"] and "59.0 MB" in out["table"] and "1,000" in out["table"]
    assert out["pills"] == ["FAIL", "FLAG"]
    assert out["open"] == 0, "the long detail should start collapsed"


def test_the_e2e_table_names_each_interval_method_and_shows_no_spend() -> None:
    out = _run(
        """
        const { e2eTable } = await load("results_infra.js");
        out.table = textOf(e2eTable(input.e2e));
        """,
        e2e=E2E,
    )

    assert "two-stage bootstrap" in out["table"] and "Wilson interval" in out["table"]
    assert "R5 · clean tags" in out["table"]
    assert "spend" not in out["table"].lower() and "EXP-0004" not in out["table"]


def test_the_sealed_chart_labels_pooled_and_plant_groups_with_their_own_method() -> None:
    out = _run(
        """
        const { sealedSpec, policyName } = await load("results_sealed.js");
        out.groups = sealedSpec(input.rows, "headline").groups.map((g) => g.label);
        out.names = input.rows.map((r) => policyName(r.policy));
        out.v2 = policyName("cascade_v4_iso");
        """,
        rows=ROWS,
    )

    methods = {group[0].split(" ")[0]: group[2] for group in out["groups"]}
    assert methods == {"S100": "two-stage bootstrap", "H100": "Wilson interval"}
    assert any("pooled over 5 plants" in group for group in out["groups"])
    assert out["names"] == ["Cascade (V2T-A2)", "Cascade (V2T-A2)", "F1, previous system"]
    assert "v3" not in out["v2"]
