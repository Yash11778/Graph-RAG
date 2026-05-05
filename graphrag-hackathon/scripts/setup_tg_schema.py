import sys
import requests
from dotenv import load_dotenv

load_dotenv()

TG_HOST = 'https://tg-cddb2056-27e0-4388-87a8-8be8de814ed5.tg-2635877100.i.tgcloud.io'
TG_TOKEN = 'YOUR_TG_JWT_TOKEN_HERE'
HEADERS = {'Authorization': f'Bearer {TG_TOKEN}', 'Content-Type': 'text/plain'}

GSQL = """
USE GLOBAL
DROP GRAPH MyDatabase

CREATE VERTEX Article (PRIMARY_ID id STRING, title STRING)
CREATE VERTEX Chunk (PRIMARY_ID id STRING, text STRING, chunk_index INT)
CREATE UNDIRECTED EDGE NEXT_CHUNK (FROM Chunk, TO Chunk)
CREATE DIRECTED EDGE HAS_CHUNK (FROM Article, TO Chunk)
CREATE GRAPH MyDatabase (Article, Chunk, NEXT_CHUNK, HAS_CHUNK)
"""

def run():
    print('Dropping old graph and creating new schema...')
    r = requests.post(
        f'{TG_HOST}/gsql/v1/statements',
        headers=HEADERS,
        data=GSQL.encode('utf-8'),
        timeout=120,
        verify=True,
    )
    print(f'Status: {r.status_code}')
    print(r.text)
    if r.status_code not in (200, 201):
        print('ERROR: schema setup failed')
        sys.exit(1)
    print('Schema created successfully.')

if __name__ == '__main__':
    run()
