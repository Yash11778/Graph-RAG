"""
Quick sanity-check: confirms Entity vertices and HAS_ENTITY edges exist in TigerGraph,
and prints the graph traversal path for a sample chunk.
"""
import pickle, requests

TG_HOST  = 'https://tg-cddb2056-27e0-4388-87a8-8be8de814ed5.tg-2635877100.i.tgcloud.io'
TG_TOKEN = 'YOUR_TG_JWT_TOKEN_HERE'
TG_GRAPH = 'MyDatabase'
H = {'Authorization': f'Bearer {TG_TOKEN}'}


def get(path):
    r = requests.get(f'{TG_HOST}{path}', headers=H, timeout=10)
    return r.json() if r.status_code == 200 else None


chunks = pickle.load(open('data/chunks/chunks.pkl', 'rb'))
sample_id = chunks[0]['id']

print(f'Sample chunk: {sample_id}')
print(f'Chunk text:   {chunks[0]["text"][:120]}...\n')

# Count total Entity vertices
stats = get(f'/restpp/graph/{TG_GRAPH}/vertices/Entity?limit=1&count_only=true')
print(f'Total Entity vertices in TigerGraph: {stats}')

# Traverse Chunk → HAS_ENTITY → Entity
edges = get(f'/restpp/graph/{TG_GRAPH}/edges/Chunk/{sample_id}/HAS_ENTITY')
if not edges or not edges.get('results'):
    print('No HAS_ENTITY edges found for this chunk — run extract_entities.py first.')
else:
    print(f'\nHAS_ENTITY edges from chunk [{sample_id}]:')
    for e in edges['results']:
        eid = e['to_id']
        ev  = get(f'/restpp/graph/{TG_GRAPH}/vertices/Entity/{eid}')
        if ev and ev.get('results'):
            a = ev['results'][0]['attributes']
            print(f'  [{a["name"]}] → "{a["fact"]}"')

    # Check ENTITY_COREF for first entity
    first_eid = edges['results'][0]['to_id']
    corefs = get(f'/restpp/graph/{TG_GRAPH}/edges/Entity/{first_eid}/ENTITY_COREF')
    coref_count = len(corefs.get('results', [])) if corefs else 0
    print(f'\nENTITY_COREF links on first entity: {coref_count} (cross-document connections)')
