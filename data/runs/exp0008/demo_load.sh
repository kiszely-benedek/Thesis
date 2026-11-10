#!/bin/sh
# Load the demo plant (H1000g21p1, plant_lines) into Neo4j on its own, e.g. after a stopped launch:
#   sh data/runs/exp0008/demo_load.sh        (set E9_NEO4J_HOME as launch.sh does)
# It wipes the database first, like every load of the launcher. Needs the drawn seeds (prereg/seeds.json).
set -eu
cd "$(git rev-parse --show-toplevel)"
SCRIPTS=data/runs/exp0008
. "$SCRIPTS/lib.sh"
. "$SCRIPTS/lib_plants.sh"
CUR_STAGE=demo_load
ensure_dirs
demo_database
