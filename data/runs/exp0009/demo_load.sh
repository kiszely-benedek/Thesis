#!/bin/sh
# Restore the demo plant (H1000g21p1, plant_lines) into Neo4j on its own, e.g. after a stopped launch:
#   sh data/runs/exp0009/demo_load.sh        (set E10_NEO4J_HOME as launch.sh does)
# It wipes the database first, like every load of the launcher. Needs EXP-0008's drawn seeds.
set -eu
cd "$(git rev-parse --show-toplevel)"
SCRIPTS=data/runs/exp0009
. "$SCRIPTS/lib.sh"
. "$SCRIPTS/lib_plants.sh"
CUR_STAGE=demo_load
ensure_dirs
demo_database
