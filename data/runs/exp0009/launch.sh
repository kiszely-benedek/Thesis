#!/bin/sh
# Launch wrapper for a detached run (README, "Start"): sets the environment run_all.sh needs, then runs it.
#   bash.exe -l C:/path/to/repo/data/runs/exp0009/launch.sh [run_all.sh options, e.g. --from P1b]
# E10_NEO4J_HOME is the Neo4j server's home folder (order: the environment, a line in the git-ignored .env, then
# the Neo4j Desktop folder that EXP-0008's launch.sh names). Output is appended to data/runs/exp0009/run_all.log.
set -eu
cd "$(dirname "$0")/../../.."

if [ -z "${E10_NEO4J_HOME:-}" ] && [ -f .env ]; then
  E10_NEO4J_HOME=$(sed -n 's/^E10_NEO4J_HOME=//p' .env | tail -n 1 | tr -d '\r"')
fi
if [ -z "${E10_NEO4J_HOME:-}" ]; then
  E10_NEO4J_HOME="${USERPROFILE:-$HOME}/.Neo4jDesktop2/Data/dbmss/dbms-056b4b53-d140-455c-a624-5850769f9dbc"
fi
if [ ! -d "$E10_NEO4J_HOME" ]; then
  echo "ERROR: expected the Neo4j home at $E10_NEO4J_HOME, found no such folder (set E10_NEO4J_HOME)" >&2
  exit 2
fi
export E10_NEO4J_HOME

# Every load runs CREATE OR REPLACE DATABASE on the database named by NEO4J_DATABASE, and an exported variable beats the
# git-ignored .env (store/neo4j_settings.py). A login profile exporting another name (a database that is not ours)
# would have it replaced, so refuse to start on anything but `neo4j` and pin the name for every child process.
if [ -n "${NEO4J_DATABASE:-}" ] && [ "$NEO4J_DATABASE" != neo4j ]; then
  echo "ERROR: expected NEO4J_DATABASE unset or 'neo4j', found '$NEO4J_DATABASE' (every load replaces that database)" >&2
  exit 2
fi
export NEO4J_DATABASE=neo4j

exec sh data/runs/exp0009/run_all.sh "$@" >> data/runs/exp0009/run_all.log 2>&1
