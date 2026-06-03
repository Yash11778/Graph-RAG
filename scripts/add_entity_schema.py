"""
Add Entity vertex and HAS_ENTITY edge to TigerGraph MyDatabase.
Run once â€” safe to re-run (TigerGraph ignores duplicate definitions).
"""
import sys
import requests

TG_HOST = 'https://tg-cddb2056-27e0-4388-87a8-8be8de814ed5.tg-2635877100.i.tgcloud.io'
TG_TOKEN = os.getenv('TG_PASSWORD', '')
HEADERS = {'Authorization': f'Bearer {TG_TOKEN}', 'Content-Type': 'text/plain'}

# Entity: stores a single extracted fact about a named entity.
# HAS_ENTITY: directed edge from Chunk to Entity (chunk contains this entity fact).
# ENTITY_COREF: undirected edge linking Entity vertices that refer to the same real-world entity
#               across different chunks â€” enables cross-document reasoning.
GSQL = """
USE GRAPH MyDatabase
CREATE VERTEX Entity (
    PRIMARY_ID id STRING,
    name       STRING,
    fact       STRING,
    chunk_id   STRING
) WITH STATS="OUTDEGREE_BY_EDGETYPE"
CREATE DIRECTED EDGE HAS_ENTITY (FROM Chunk, TO Entity)
CREATE UNDIRECTED EDGE ENTITY_COREF (FROM Entity, TO Entity)
ALTER GRAPH MyDatabase ADD (Entity, HAS_ENTITY, ENTITY_COREF)
"""


def run():
    print('Adding Entity schema to TigerGraph MyDatabase...')
    r = requests.post(
        f'{TG_HOST}/gsql/v1/statements',
        headers=HEADERS,
        data=GSQL.encode('utf-8'),
        timeout=120,
    )
    print(f'Status: {r.status_code}')
    print(r.text[:1000])
    if r.status_code not in (200, 201):
        print('ERROR: schema update failed')
        sys.exit(1)
    print('\nEntity schema added successfully.')
    print('Next step: run  python scripts/extract_entities.py')


if __name__ == '__main__':
    run()

