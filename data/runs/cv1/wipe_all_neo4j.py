"""Wipe every corpus from the local Neo4j (one plant at a time, user rule 2026-10)."""
from neo4j import GraphDatabase

from plantgraph.store.neo4j_loader import wipe_corpus
from plantgraph.store.neo4j_settings import from_env

settings = from_env()
driver = GraphDatabase.driver(settings.uri, auth=(settings.username, settings.password.get_secret_value()))
with driver.session(database=settings.database) as session:
    ids = [r["c"] for r in session.run("MATCH (n) WHERE n.corpus_id IS NOT NULL RETURN DISTINCT n.corpus_id AS c")]
driver.close()
for corpus_id in ids:
    wipe_corpus(settings, corpus_id)
print("wiped", ids)
