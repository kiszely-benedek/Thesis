#!/bin/sh
# F1 freeze (ADR-0053 point 5). Run once, right after the user's ST-T1 commit.
set -eu
S=data/runs/sealed; C=data/runs/cv1; P=.venv/Scripts/python
die() { echo "ERROR: $*" >&2; exit 1; }
[ ! -e $S/F1.commit ] || die "F1 already exists; never overwrite it"
[ -z "$(git status --porcelain)" ] || die "commit first: the working tree is not clean"
mkdir -p $S/inputs $S/logs
git rev-parse HEAD > $S/F1.commit
cp $C/pins_bakeoff/F_cypher.json $S/inputs/pin_cypher_luna_low.json
cp $C/pin_luna_final_high.json $S/inputs/pin_agent_luna_final_high.json
cp $C/params_cypher_plant.json $C/params_agent_low.json $S/inputs/
$P - <<'EOF'
import json
from pathlib import Path
from plantgraph.llm.models import ModelPin
policy = json.loads(Path("src/plantgraph/qa/cascade/policies/cascade_v3.json").read_text(encoding="utf-8"))
pins = {"cypher-luna": "pin_cypher_luna_low.json", "agent-luna": "pin_agent_luna_final_high.json"}
for tier in policy["tiers"]:
    text = Path("data/runs/sealed/inputs", pins[tier["name"]]).read_text(encoding="utf-8")
    found = ModelPin.model_validate_json(text).pin_hash()
    assert found == tier["pin_sha256"], f"{tier['name']}: pin {found} is not the policy's"
print("pins match cascade_v3")
EOF
sha256sum $S/F1.commit $S/inputs/* docs/private/40-design/heldout-families.sealed.md \
  docs/private/40-design/sealed-test-run.md docs/private/20-decisions/ADR-0053-sealed-test-run-protocol.md \
  > $S/F1.sha256
grep -q 905c7984dfc1d346cb696c47590d972d545455fd1149517534ad2309955ff63b $S/F1.sha256 || die "the seal hash changed"
date -u +%Y-%m-%dT%H:%M:%SZ > $S/F1.time
cat $S/F1.commit $S/F1.time
